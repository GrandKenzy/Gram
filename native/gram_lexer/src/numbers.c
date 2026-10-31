#include "gram_lexer_internal.h"
#include <string.h>

static int is_ascii_digit(char c) {
    return (c >= '0' && c <= '9') ? 1 : 0;
}

static int is_hex_digit_or_underscore(char c) {
    return ((c >= '0' && c <= '9') ||
            (c >= 'a' && c <= 'f') ||
            (c >= 'A' && c <= 'F') ||
            c == '_') ? 1 : 0;
}

static int is_dec_digit_or_underscore(char c) {
    return ((c >= '0' && c <= '9') || c == '_') ? 1 : 0;
}

static int is_int_suffix(char c) {
    return (c == 'u' || c == 'U' || c == 'l' || c == 'L') ? 1 : 0;
}

static int is_float_suffix(char c) {
    return (c == 'f' || c == 'F' || c == 'l' || c == 'L') ? 1 : 0;
}

/* Match [eE][+-]?[0-9][0-9_]* starting at pos; return new pos or 0 if no match. */
static uint32_t match_dec_exponent(const char *src, uint32_t end_limit, uint32_t pos) {
    if (pos >= end_limit || (src[pos] != 'e' && src[pos] != 'E')) {
        return 0;
    }
    uint32_t p = pos + 1u;
    if (p < end_limit && (src[p] == '+' || src[p] == '-')) {
        p += 1u;
    }
    if (p >= end_limit || !is_ascii_digit(src[p])) {
        return 0;
    }
    p += 1u;
    while (p < end_limit && is_dec_digit_or_underscore(src[p])) {
        p += 1u;
    }
    return p;
}

/* Match [pP][+-]?[0-9][0-9_]* starting at pos; return new pos or 0 if no match. */
static uint32_t match_bin_exponent(const char *src, uint32_t end_limit, uint32_t pos) {
    if (pos >= end_limit || (src[pos] != 'p' && src[pos] != 'P')) {
        return 0;
    }
    uint32_t p = pos + 1u;
    if (p < end_limit && (src[p] == '+' || src[p] == '-')) {
        p += 1u;
    }
    if (p >= end_limit || !is_ascii_digit(src[p])) {
        return 0;
    }
    p += 1u;
    while (p < end_limit && is_dec_digit_or_underscore(src[p])) {
        p += 1u;
    }
    return p;
}

/* 1. _HEX_FLOAT_RE */
static uint32_t match_hex_float(const char *src, uint32_t end_limit, uint32_t start) {
    if (start + 2u >= end_limit || src[start] != '0' || (src[start + 1u] != 'x' && src[start + 1u] != 'X')) {
        return 0;
    }
    uint32_t p = start + 2u;
    uint32_t exp_end = 0;

    if (src[p] == '.') {
        uint32_t q = p + 1u;
        while (q < end_limit && is_hex_digit_or_underscore(src[q])) {
            q += 1u;
        }
        if (q > p + 1u) {
            exp_end = match_bin_exponent(src, end_limit, q);
        }
    } else if (is_hex_digit_or_underscore(src[p])) {
        uint32_t q = p;
        while (q < end_limit && is_hex_digit_or_underscore(src[q])) {
            q += 1u;
        }
        if (q < end_limit && src[q] == '.') {
            uint32_t r = q + 1u;
            while (r < end_limit && is_hex_digit_or_underscore(src[r])) {
                r += 1u;
            }
            exp_end = match_bin_exponent(src, end_limit, r);
        } else {
            exp_end = match_bin_exponent(src, end_limit, q);
        }
    }

    if (exp_end == 0) {
        return 0;
    }
    if (exp_end < end_limit && is_float_suffix(src[exp_end])) {
        exp_end += 1u;
    }
    return exp_end;
}

/* 2. _HEX_INTEGER_RE */
static uint32_t match_hex_integer(const char *src, uint32_t end_limit, uint32_t start) {
    if (start + 2u >= end_limit || src[start] != '0' || (src[start + 1u] != 'x' && src[start + 1u] != 'X')) {
        return 0;
    }
    uint32_t p = start + 2u;
    if (p >= end_limit || !is_hex_digit_or_underscore(src[p])) {
        return 0;
    }
    while (p < end_limit && is_hex_digit_or_underscore(src[p])) {
        p += 1u;
    }
    while (p < end_limit && is_int_suffix(src[p])) {
        p += 1u;
    }
    return p;
}

/* 3. _RADIX_RE (0b / 0o) */
static uint32_t match_radix_integer(const char *src, uint32_t end_limit, uint32_t start) {
    if (start + 2u >= end_limit || src[start] != '0') {
        return 0;
    }
    char r = src[start + 1u];
    uint32_t p = start + 2u;
    if (r == 'b' || r == 'B') {
        if (p >= end_limit || (src[p] != '0' && src[p] != '1' && src[p] != '_')) {
            return 0;
        }
        while (p < end_limit && (src[p] == '0' || src[p] == '1' || src[p] == '_')) {
            p += 1u;
        }
    } else if (r == 'o' || r == 'O') {
        if (p >= end_limit || ((src[p] < '0' || src[p] > '7') && src[p] != '_')) {
            return 0;
        }
        while (p < end_limit && ((src[p] >= '0' && src[p] <= '7') || src[p] == '_')) {
            p += 1u;
        }
    } else {
        return 0;
    }
    while (p < end_limit && is_int_suffix(src[p])) {
        p += 1u;
    }
    return p;
}

/* 4. _DECIMAL_FLOAT_RE */
static uint32_t match_decimal_float(const char *src, uint32_t end_limit, uint32_t start) {
    uint32_t p = start;
    uint32_t base_end = 0;

    if (p < end_limit && src[p] == '.') {
        if (p + 1u < end_limit && is_ascii_digit(src[p + 1u])) {
            uint32_t q = p + 2u;
            while (q < end_limit && is_dec_digit_or_underscore(src[q])) {
                q += 1u;
            }
            base_end = q;
        }
    } else if (p < end_limit && is_ascii_digit(src[p])) {
        uint32_t q = p + 1u;
        while (q < end_limit && is_dec_digit_or_underscore(src[q])) {
            q += 1u;
        }
        if (q < end_limit && src[q] == '.') {
            uint32_t r = q + 1u;
            while (r < end_limit && is_dec_digit_or_underscore(src[r])) {
                r += 1u;
            }
            base_end = r;
        } else {
            base_end = match_dec_exponent(src, end_limit, q);
        }
    }

    if (base_end == 0) {
        return 0;
    }

    uint32_t exp2_end = match_dec_exponent(src, end_limit, base_end);
    if (exp2_end != 0) {
        base_end = exp2_end;
    }

    if (base_end < end_limit && is_float_suffix(src[base_end])) {
        base_end += 1u;
    }
    return base_end;
}

/* 5. _DECIMAL_INTEGER_RE */
static uint32_t match_decimal_integer(const char *src, uint32_t end_limit, uint32_t start) {
    if (start >= end_limit || !is_ascii_digit(src[start])) {
        return 0;
    }
    uint32_t p = start + 1u;
    while (p < end_limit && is_dec_digit_or_underscore(src[p])) {
        p += 1u;
    }
    while (p < end_limit && is_int_suffix(src[p])) {
        p += 1u;
    }
    return p;
}

/* Consume contiguous malformed tail matching Python's _numeric_tail. */
static uint32_t consume_numeric_tail(
    const char *src,
    uint32_t line_end,
    uint32_t start,
    uint32_t end,
    uint32_t *out_extra_codepoints
) {
    uint32_t extra_cp = 0;
    while (end < line_end) {
        uint8_t b = (uint8_t)src[end];
        if (b < 0x80u) {
            char c = (char)b;
            if ((c >= '0' && c <= '9') ||
                (c >= 'a' && c <= 'z') ||
                (c >= 'A' && c <= 'Z') ||
                c == '.' || c == '_') {
                end += 1u;
                extra_cp += 1u;
                continue;
            }
            if ((c == '+' || c == '-') && end > start) {
                char prev = src[end - 1u];
                if (prev == 'e' || prev == 'E' || prev == 'p' || prev == 'P') {
                    end += 1u;
                    extra_cp += 1u;
                    continue;
                }
            }
            break;
        } else {
            uint32_t cp = 0;
            uint32_t step = 1u;
            int valid = gram_utf8_decode(src, line_end, end, &cp, &step);
            if (valid && gram_unicode_is_alnum(cp)) {
                end += step;
                extra_cp += 1u;
                continue;
            }
            break;
        }
    }
    if (out_extra_codepoints) {
        *out_extra_codepoints = extra_cp;
    }
    return end;
}

static int has_invalid_separator_or_conversion(const char *raw, uint32_t len, int *out_has_suffix) {
    if (out_has_suffix) *out_has_suffix = 0;
    if (len == 0) return 1;
    if (raw[0] == '_' || raw[len - 1u] == '_') return 1;

    for (uint32_t i = 0; i + 1u < len; ++i) {
        if (raw[i] == '_' && raw[i + 1u] == '_') {
            return 1;
        }
    }

    if (len >= 3u && raw[0] == '0') {
        char r = raw[1];
        if ((r == 'x' || r == 'X' || r == 'b' || r == 'B' || r == 'o' || r == 'O') && raw[2] == '_') {
            return 1;
        }
    }

    /* Check _convert_number edge cases (e.g. double exponent 1e2e3 without suffix, or 0x._p1) */
    int is_hex = (len >= 2u && raw[0] == '0' && (raw[1] == 'x' || raw[1] == 'X'));
    int is_bin_oct = (len >= 2u && raw[0] == '0' && (raw[1] == 'b' || raw[1] == 'B' || raw[1] == 'o' || raw[1] == 'O'));

    if (is_hex) {
        int has_p_or_dot = 0;
        for (uint32_t i = 2u; i < len; ++i) {
            if (raw[i] == '.' || raw[i] == 'p' || raw[i] == 'P') {
                has_p_or_dot = 1;
                break;
            }
        }
        if (has_p_or_dot) {
            uint32_t end_body = len;
            while (end_body > 2u && is_float_suffix(raw[end_body - 1u])) {
                end_body -= 1u;
            }
            if (end_body < len && out_has_suffix) *out_has_suffix = 1;
            /* Ensure at least one hex digit before 'p'/'P' */
            int has_sig_digit = 0;
            for (uint32_t i = 2u; i < end_body; ++i) {
                if (raw[i] == 'p' || raw[i] == 'P') break;
                if ((raw[i] >= '0' && raw[i] <= '9') ||
                    (raw[i] >= 'a' && raw[i] <= 'f') ||
                    (raw[i] >= 'A' && raw[i] <= 'F')) {
                    has_sig_digit = 1;
                }
            }
            if (!has_sig_digit) return 1;
        } else {
            uint32_t end_body = len;
            while (end_body > 2u && is_int_suffix(raw[end_body - 1u])) {
                end_body -= 1u;
            }
            if (end_body < len && out_has_suffix) *out_has_suffix = 1;
            int has_digit = 0;
            for (uint32_t i = 2u; i < end_body; ++i) {
                if (raw[i] != '_') has_digit = 1;
            }
            if (!has_digit) return 1;
        }
    } else if (is_bin_oct) {
        uint32_t end_body = len;
        while (end_body > 2u && is_int_suffix(raw[end_body - 1u])) {
            end_body -= 1u;
        }
        if (end_body < len && out_has_suffix) *out_has_suffix = 1;
        int has_digit = 0;
        for (uint32_t i = 2u; i < end_body; ++i) {
            if (raw[i] != '_') has_digit = 1;
        }
        if (!has_digit) return 1;
    } else {
        uint32_t end_body = len;
        while (end_body > 0 && (is_int_suffix(raw[end_body - 1u]) || is_float_suffix(raw[end_body - 1u]))) {
            end_body -= 1u;
        }
        if (end_body < len) {
            if (out_has_suffix) *out_has_suffix = 1;
        } else {
            /* Unsuffixed decimal: cannot contain more than one 'e'/'E' */
            uint32_t e_count = 0;
            for (uint32_t i = 0; i < end_body; ++i) {
                if (raw[i] == 'e' || raw[i] == 'E') {
                    e_count += 1u;
                }
            }
            if (e_count > 1u) return 1;
        }
    }

    return 0;
}

int gram_scan_number(GramLexer *lexer, GramToken *out_token) {
    uint32_t start = lexer->position;
    uint32_t start_col = lexer->column;
    uint32_t line_end = lexer->line_end;
    const char *src = lexer->source;

    uint32_t match_end = match_hex_float(src, line_end, start);
    if (match_end == 0) {
        match_end = match_hex_integer(src, line_end, start);
    }
    if (match_end == 0) {
        match_end = match_radix_integer(src, line_end, start);
    }
    if (match_end == 0) {
        match_end = match_decimal_float(src, line_end, start);
    }
    if (match_end == 0) {
        match_end = match_decimal_integer(src, line_end, start);
    }

    if (match_end == 0) {
        uint32_t extra_cp = 0;
        uint32_t invalid_end = consume_numeric_tail(src, line_end, start, start + 1u, &extra_cp);
        uint32_t byte_len = invalid_end - start;
        lexer->position = invalid_end;
        lexer->column = start_col + 1u + extra_cp;

        memset(out_token, 0, sizeof(GramToken));
        out_token->kind = GRAM_TOKEN_ERROR;
        out_token->flags = GRAM_TOKEN_FLAG_NONE;
        out_token->start = start;
        out_token->length = byte_len;
        out_token->line = lexer->line;
        out_token->column = start_col;
        out_token->content_start = start;
        out_token->content_length = byte_len;

        int halted = gram_lexer_emit_error(
            lexer,
            GRAM_DIAG_CODE_INVALID_NUMBER,
            start,
            invalid_end,
            lexer->line,
            start_col,
            "Unrecognized numeric literal"
        );
        return halted ? GRAM_LEXER_FATAL : GRAM_LEXER_ERROR;
    }

    uint32_t raw_len = match_end - start;
    uint32_t extra_cp = 0;
    uint32_t tail_end = consume_numeric_tail(src, line_end, start, match_end, &extra_cp);
    int has_suffix = 0;

    if (tail_end != match_end || has_invalid_separator_or_conversion(src + start, raw_len, &has_suffix)) {
        uint32_t total_len = tail_end - start;
        lexer->position = tail_end;
        lexer->column = start_col + raw_len + extra_cp;

        memset(out_token, 0, sizeof(GramToken));
        out_token->kind = GRAM_TOKEN_ERROR;
        out_token->flags = GRAM_TOKEN_FLAG_NONE;
        out_token->start = start;
        out_token->length = total_len;
        out_token->line = lexer->line;
        out_token->column = start_col;
        out_token->content_start = start;
        out_token->content_length = total_len;

        int halted = gram_lexer_emit_error(
            lexer,
            GRAM_DIAG_CODE_INVALID_NUMBER,
            start,
            tail_end,
            lexer->line,
            start_col,
            "Malformed numeric literal"
        );
        return halted ? GRAM_LEXER_FATAL : GRAM_LEXER_ERROR;
    }

    lexer->position = match_end;
    lexer->column = start_col + raw_len;

    const char *raw = src + start;
    int is_hex = (raw_len >= 2u && raw[0] == '0' && (raw[1] == 'x' || raw[1] == 'X'));
    int is_decimal = 0;
    for (uint32_t i = 0; i < raw_len; ++i) {
        char c = raw[i];
        if (c == '.' || c == 'p' || c == 'P') {
            is_decimal = 1;
            break;
        }
        if ((c == 'e' || c == 'E') && !is_hex) {
            is_decimal = 1;
            break;
        }
    }

    memset(out_token, 0, sizeof(GramToken));
    out_token->kind = is_decimal ? GRAM_TOKEN_DECIMAL : GRAM_TOKEN_NUMBER;
    out_token->flags = has_suffix ? GRAM_TOKEN_FLAG_NUMERIC_SUFF : GRAM_TOKEN_FLAG_NONE;
    out_token->start = start;
    out_token->length = raw_len;
    out_token->line = lexer->line;
    out_token->column = start_col;
    out_token->content_start = start;
    out_token->content_length = raw_len;
    return GRAM_LEXER_TOKEN;
}
