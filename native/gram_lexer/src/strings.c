#include "gram_lexer_internal.h"
#include <string.h>

static const GramMultilineEntry DEFAULT_TRIPLE_QUOTES[2] = {
    { "\"\"\"", 3u, 3u, "\"\"\"", 3u, 3u, GRAM_TOKEN_STRING, 1u, 0u },
    { "'''",    3u, 3u, "'''",    3u, 3u, GRAM_TOKEN_STRING, 1u, 0u }
};

static int is_hex_char(char c, uint32_t *out_val) {
    if (c >= '0' && c <= '9') {
        if (out_val) *out_val = (uint32_t)(c - '0');
        return 1;
    }
    if (c >= 'a' && c <= 'f') {
        if (out_val) *out_val = (uint32_t)(c - 'a' + 10);
        return 1;
    }
    if (c >= 'A' && c <= 'F') {
        if (out_val) *out_val = (uint32_t)(c - 'A' + 10);
        return 1;
    }
    return 0;
}

static int parse_u4_hex(const char *src, uint32_t limit, uint32_t pos, uint32_t *out_cp) {
    if (pos + 4u > limit) {
        return 0;
    }
    uint32_t cp = 0;
    for (uint32_t i = 0; i < 4u; ++i) {
        uint32_t v = 0;
        if (!is_hex_char(src[pos + i], &v)) {
            return 0;
        }
        cp = (cp << 4) | v;
    }
    if (out_cp) {
        *out_cp = cp;
    }
    return 1;
}

static uint32_t encode_utf8_cp(uint32_t cp, char out[4]) {
    if (cp <= 0x7Fu) {
        out[0] = (char)cp;
        return 1u;
    }
    if (cp <= 0x7FFu) {
        out[0] = (char)(0xC0u | ((cp >> 6) & 0x1Fu));
        out[1] = (char)(0x80u | (cp & 0x3Fu));
        return 2u;
    }
    if (cp <= 0xFFFFu) {
        out[0] = (char)(0xE0u | ((cp >> 12) & 0x0Fu));
        out[1] = (char)(0x80u | ((cp >> 6) & 0x3Fu));
        out[2] = (char)(0x80u | (cp & 0x3Fu));
        return 3u;
    }
    out[0] = (char)(0xF0u | ((cp >> 18) & 0x07u));
    out[1] = (char)(0x80u | ((cp >> 12) & 0x3Fu));
    out[2] = (char)(0x80u | ((cp >> 6) & 0x3Fu));
    out[3] = (char)(0x80u | (cp & 0x3Fu));
    return 4u;
}

const GramMultilineEntry *gram_match_multiline(
    const GramLexer *lexer,
    uint32_t byte_pos
) {
    uint32_t line_end = lexer->line_end;
    const char *src = lexer->source;

    if (lexer->tables != NULL && lexer->tables->multiline != NULL && lexer->tables->multiline_count > 0) {
        for (uint32_t i = 0; i < lexer->tables->multiline_count; ++i) {
            const GramMultilineEntry *entry = &lexer->tables->multiline[i];
            if (entry->opening == NULL || entry->opening_length == 0) {
                continue;
            }
            if (entry->is_block_comment && !lexer->config.support_block_comments) {
                continue;
            }
            if (!entry->is_block_comment &&
                entry->opening_length == 3u &&
                (memcmp(entry->opening, "\"\"\"", 3) == 0 || memcmp(entry->opening, "'''", 3) == 0) &&
                !lexer->config.support_triple_strings) {
                continue;
            }
            if (byte_pos + entry->opening_length <= line_end &&
                memcmp(src + byte_pos, entry->opening, entry->opening_length) == 0) {
                return entry;
            }
        }
        return NULL;
    }

    /* Default fallback when no custom multiline table is provided */
    if (lexer->config.support_triple_strings) {
        for (uint32_t i = 0; i < 2u; ++i) {
            const GramMultilineEntry *entry = &DEFAULT_TRIPLE_QUOTES[i];
            if (byte_pos + entry->opening_length <= line_end &&
                memcmp(src + byte_pos, entry->opening, entry->opening_length) == 0) {
                return entry;
            }
        }
    }
    return NULL;
}

int gram_scan_string(
    GramLexer *lexer,
    char quote,
    uint32_t start_byte,
    uint32_t start_line,
    uint32_t start_col,
    uint32_t prefix_start,
    uint32_t prefix_len,
    GramToken *out_token
) {
    const char *src = lexer->source;
    uint32_t line_end = lexer->line_end;

    /* Consume opening quote */
    lexer->position += 1u;
    lexer->column += 1u;

    uint32_t content_start = lexer->position;
    uint32_t decoded_codepoints = 0;
    uint32_t has_escapes = 0;

    while (lexer->position < line_end) {
        uint32_t cp = 0;
        uint32_t step = 1u;
        int valid = gram_utf8_decode(src, line_end, lexer->position, &cp, &step);
        if (!valid) {
            uint32_t err_pos = lexer->position;
            uint32_t err_col = lexer->column;
            lexer->position += 1u;
            lexer->column += 1u;
            int halted = gram_lexer_emit_error(
                lexer,
                GRAM_DIAG_CODE_INVALID_UTF8,
                err_pos,
                err_pos + 1u,
                lexer->line,
                err_col,
                "Invalid UTF-8 byte inside string literal"
            );
            if (halted) {
                memset(out_token, 0, sizeof(GramToken));
                out_token->kind = GRAM_TOKEN_ERROR;
                out_token->start = start_byte;
                out_token->length = lexer->position - start_byte;
                out_token->line = start_line;
                out_token->column = start_col;
                out_token->content_start = content_start;
                out_token->content_length = lexer->position - content_start;
                return GRAM_LEXER_FATAL;
            }
            decoded_codepoints += 1u;
            continue;
        }

        if (cp == (uint32_t)'\\') {
            has_escapes = 1u;
            uint32_t backslash_pos = lexer->position;
            lexer->position += 1u;
            lexer->column += 1u;

            if (lexer->position >= line_end) {
                memset(out_token, 0, sizeof(GramToken));
                out_token->kind = GRAM_TOKEN_ERROR;
                out_token->flags = GRAM_TOKEN_FLAG_HAS_ESCAPES;
                out_token->start = start_byte;
                out_token->length = lexer->position - start_byte;
                out_token->line = start_line;
                out_token->column = start_col;
                out_token->content_start = content_start;
                out_token->content_length = backslash_pos - content_start;
                out_token->prefix_start = prefix_start;
                out_token->prefix_length = prefix_len;

                int halted = gram_lexer_emit_error(
                    lexer,
                    GRAM_DIAG_CODE_UNCLOSED_STRING,
                    start_byte,
                    lexer->position,
                    start_line,
                    start_col,
                    "Unclosed string escape at end of line"
                );
                return halted ? GRAM_LEXER_FATAL : GRAM_LEXER_ERROR;
            }

            uint32_t esc_cp = 0;
            uint32_t esc_step = 1u;
            (void)gram_utf8_decode(src, line_end, lexer->position, &esc_cp, &esc_step);
            lexer->position += esc_step;
            lexer->column += 1u;

            uint32_t u_cp = 0;
            if (esc_cp == (uint32_t)'u' && parse_u4_hex(src, line_end, lexer->position, &u_cp)) {
                lexer->position += 4u;
                lexer->column += 4u;
                decoded_codepoints += 1u;
            } else if (esc_cp == 'n' || esc_cp == 'r' || esc_cp == 't' ||
                       esc_cp == 'b' || esc_cp == 'f' || esc_cp == 'v' ||
                       esc_cp == '0' || esc_cp == '\\' || esc_cp == '"' || esc_cp == '\'') {
                decoded_codepoints += 1u;
            } else {
                /* Unknown escape produces both '\' and the escaped character */
                decoded_codepoints += 2u;
            }
            continue;
        }

        if (cp == (uint32_t)(uint8_t)quote) {
            uint32_t quote_pos = lexer->position;
            lexer->position += 1u;
            lexer->column += 1u;

            uint32_t flags = GRAM_TOKEN_FLAG_SIMPLE_QUOTE;
            if (decoded_codepoints == 1u) {
                flags |= GRAM_TOKEN_FLAG_CHAR;
            }
            if (has_escapes) {
                flags |= GRAM_TOKEN_FLAG_HAS_ESCAPES;
            }

            memset(out_token, 0, sizeof(GramToken));
            out_token->kind = GRAM_TOKEN_STRING;
            out_token->flags = flags;
            out_token->start = start_byte;
            out_token->length = lexer->position - start_byte;
            out_token->line = start_line;
            out_token->column = start_col;
            out_token->content_start = content_start;
            out_token->content_length = quote_pos - content_start;
            out_token->prefix_start = prefix_start;
            out_token->prefix_length = prefix_len;
            return GRAM_LEXER_TOKEN;
        }

        lexer->position += step;
        lexer->column += 1u;
        decoded_codepoints += 1u;
    }

    /* End of line reached without closing quote */
    memset(out_token, 0, sizeof(GramToken));
    out_token->kind = GRAM_TOKEN_ERROR;
    out_token->flags = has_escapes ? GRAM_TOKEN_FLAG_HAS_ESCAPES : GRAM_TOKEN_FLAG_NONE;
    out_token->start = start_byte;
    out_token->length = lexer->position - start_byte;
    out_token->line = start_line;
    out_token->column = start_col;
    out_token->content_start = content_start;
    out_token->content_length = lexer->position - content_start;
    out_token->prefix_start = prefix_start;
    out_token->prefix_length = prefix_len;

    int halted = gram_lexer_emit_error(
        lexer,
        GRAM_DIAG_CODE_UNCLOSED_STRING,
        start_byte,
        lexer->position,
        start_line,
        start_col,
        "Unclosed string literal"
    );
    return halted ? GRAM_LEXER_FATAL : GRAM_LEXER_ERROR;
}

int gram_scan_multiline(
    GramLexer *lexer,
    const GramMultilineEntry *entry,
    uint32_t start_byte,
    uint32_t start_line,
    uint32_t start_col,
    uint32_t prefix_start,
    uint32_t prefix_len,
    GramToken *out_token
) {
    const char *src = lexer->source;
    uint32_t open_cp = entry->opening_codepoints > 0
        ? entry->opening_codepoints
        : gram_utf8_count_codepoints(entry->opening, entry->opening_length);
    uint32_t close_cp = entry->closing_codepoints > 0
        ? entry->closing_codepoints
        : gram_utf8_count_codepoints(entry->closing, entry->closing_length);

    lexer->position += entry->opening_length;
    lexer->column += open_cp;

    uint32_t content_start = lexer->position;
    uint32_t has_escapes = 0;

    while (lexer->has_current_line) {
        if (lexer->position + entry->closing_length <= lexer->line_end &&
            memcmp(src + lexer->position, entry->closing, entry->closing_length) == 0) {
            uint32_t content_end = lexer->position;
            lexer->position += entry->closing_length;
            lexer->column += close_cp;

            uint32_t flags = GRAM_TOKEN_FLAG_MULTILINE;
            if (has_escapes) {
                flags |= GRAM_TOKEN_FLAG_HAS_ESCAPES;
            }
            if (entry->is_block_comment) {
                flags |= GRAM_TOKEN_FLAG_BLOCK_COMMENT;
            }

            memset(out_token, 0, sizeof(GramToken));
            out_token->kind = entry->token_kind;
            out_token->flags = flags;
            out_token->start = start_byte;
            out_token->length = lexer->position - start_byte;
            out_token->line = start_line;
            out_token->column = start_col;
            out_token->content_start = content_start;
            out_token->content_length = content_end - content_start;
            out_token->prefix_start = prefix_start;
            out_token->prefix_length = prefix_len;
            return GRAM_LEXER_TOKEN;
        }

        if (lexer->position >= lexer->line_end) {
            /* Advance to next physical line (keep line_indent_processed = 1 so the line
             * where the multiline construct closes is not re-indented from column 0). */
            if (lexer->next_line_start < lexer->length) {
                gram_lexer_load_line_at(lexer, lexer->next_line_start);
                lexer->line_indent_processed = 1u;
                lexer->line += 1u;
                lexer->column = 0;
            } else {
                lexer->has_current_line = 0;
                lexer->position = lexer->length;
                lexer->line_end = lexer->length;
                lexer->line += 1u;
                lexer->column = 0;
            }
            continue;
        }

        uint32_t cp = 0;
        uint32_t step = 1u;
        (void)gram_utf8_decode(src, lexer->line_end, lexer->position, &cp, &step);
        lexer->position += step;
        lexer->column += 1u;

        if (entry->decode_escapes && cp == (uint32_t)'\\') {
            has_escapes = 1u;
            if (lexer->position >= lexer->line_end) {
                continue;
            }
            uint32_t esc_cp = 0;
            uint32_t esc_step = 1u;
            (void)gram_utf8_decode(src, lexer->line_end, lexer->position, &esc_cp, &esc_step);
            lexer->position += esc_step;
            lexer->column += 1u;

            uint32_t u_cp = 0;
            if (esc_cp == (uint32_t)'u' && parse_u4_hex(src, lexer->line_end, lexer->position, &u_cp)) {
                lexer->position += 4u;
                lexer->column += 4u;
            }
        }
    }

    /* Unclosed multiline construct at EOF:
     * In Python, the outer `while self.has_lines():` loop body still completes its
     * end-of-line step (`if not ignore_newlines: append(NEWLINE); self.line += 1; self.col = 0`).
     */
    if (!lexer->config.ignore_newlines) {
        lexer->line_newline_pending = 1u;
    } else {
        lexer->line += 1u;
        lexer->column = 0;
    }

    uint32_t flags = GRAM_TOKEN_FLAG_MULTILINE;
    if (has_escapes) {
        flags |= GRAM_TOKEN_FLAG_HAS_ESCAPES;
    }
    if (entry->is_block_comment) {
        flags |= GRAM_TOKEN_FLAG_BLOCK_COMMENT;
    }

    memset(out_token, 0, sizeof(GramToken));
    out_token->kind = GRAM_TOKEN_ERROR;
    out_token->flags = flags;
    out_token->start = start_byte;
    out_token->length = lexer->position - start_byte;
    out_token->line = start_line;
    out_token->column = start_col;
    out_token->content_start = content_start;
    out_token->content_length = lexer->position - content_start;
    out_token->prefix_start = prefix_start;
    out_token->prefix_length = prefix_len;

    int halted = gram_lexer_emit_error(
        lexer,
        GRAM_DIAG_CODE_UNCLOSED_STRING,
        start_byte,
        lexer->position,
        start_line,
        start_col,
        "Unclosed multiline literal"
    );
    return halted ? GRAM_LEXER_FATAL : GRAM_LEXER_ERROR;
}

int gram_lexer_decode_string(
    const GramLexer *lexer,
    const GramToken *token,
    char *out_buffer,
    uint32_t out_capacity,
    uint32_t *out_length,
    uint32_t *out_codepoints
) {
    if (lexer == NULL || token == NULL || lexer->source == NULL) {
        if (out_length) *out_length = 0;
        if (out_codepoints) *out_codepoints = 0;
        return -1;
    }

    const char *src = lexer->source;
    uint32_t pos = token->content_start;
    uint32_t end = token->content_start + token->content_length;
    if (end > lexer->length) {
        end = lexer->length;
    }

    int is_multiline = (token->flags & GRAM_TOKEN_FLAG_MULTILINE) != 0;
    int is_block_comment = (token->flags & GRAM_TOKEN_FLAG_BLOCK_COMMENT) != 0;
    int decode_escapes = !is_block_comment &&
                         ((token->flags & GRAM_TOKEN_FLAG_HAS_ESCAPES) != 0 ||
                          token->kind == GRAM_TOKEN_STRING ||
                          token->kind == GRAM_TOKEN_ERROR);

    uint32_t written = 0;
    uint32_t cp_count = 0;
    int overflow = 0;

    while (pos < end) {
        /* Determine current line end within [pos, end) if multiline */
        uint32_t seg_end = end;
        uint32_t next_seg_start = end;
        int has_line_break = 0;

        if (is_multiline) {
            uint32_t scan = pos;
            while (scan < end && src[scan] != '\n' && src[scan] != '\r') {
                scan += 1u;
            }
            seg_end = scan;
            if (scan < end) {
                has_line_break = 1;
                if (src[scan] == '\r' && scan + 1u < end && src[scan + 1u] == '\n') {
                    next_seg_start = scan + 2u;
                } else {
                    next_seg_start = scan + 1u;
                }
            }
        }

        while (pos < seg_end) {
            uint32_t cp = 0;
            uint32_t step = 1u;
            (void)gram_utf8_decode(src, seg_end, pos, &cp, &step);
            if (step == 0) step = 1u;

            if (decode_escapes && cp == (uint32_t)'\\') {
                pos += 1u;
                if (pos >= seg_end) {
                    /* Trailing backslash on a multiline line is preserved literally */
                    if (is_multiline) {
                        if (out_buffer != NULL) {
                            if (written + 1u <= out_capacity) {
                                out_buffer[written] = '\\';
                            } else {
                                overflow = 1;
                            }
                        }
                        written += 1u;
                        cp_count += 1u;
                    }
                    break;
                }

                uint32_t esc_cp = 0;
                uint32_t esc_step = 1u;
                (void)gram_utf8_decode(src, seg_end, pos, &esc_cp, &esc_step);
                if (esc_step == 0) esc_step = 1u;
                pos += esc_step;

                uint32_t u_cp = 0;
                if (esc_cp == (uint32_t)'u' && parse_u4_hex(src, seg_end, pos, &u_cp)) {
                    pos += 4u;
                    char utf8_tmp[4];
                    uint32_t utf8_len = encode_utf8_cp(u_cp, utf8_tmp);
                    if (out_buffer != NULL) {
                        if (written + utf8_len <= out_capacity) {
                            memcpy(out_buffer + written, utf8_tmp, utf8_len);
                        } else {
                            overflow = 1;
                        }
                    }
                    written += utf8_len;
                    cp_count += 1u;
                } else {
                    char mapped = 0;
                    int known = 1;
                    switch (esc_cp) {
                        case 'n':  mapped = '\n'; break;
                        case 'r':  mapped = '\r'; break;
                        case 't':  mapped = '\t'; break;
                        case 'b':  mapped = '\b'; break;
                        case 'f':  mapped = '\f'; break;
                        case 'v':  mapped = '\v'; break;
                        case '0':  mapped = '\0'; break;
                        case '\\': mapped = '\\'; break;
                        case '"':  mapped = '"';  break;
                        case '\'': mapped = '\''; break;
                        default:   known = 0;     break;
                    }
                    if (known) {
                        if (out_buffer != NULL) {
                            if (written + 1u <= out_capacity) {
                                out_buffer[written] = mapped;
                            } else {
                                overflow = 1;
                            }
                        }
                        written += 1u;
                        cp_count += 1u;
                    } else {
                        /* Unknown escape: preserve '\' followed by original character bytes */
                        if (out_buffer != NULL) {
                            if (written + 1u + esc_step <= out_capacity) {
                                out_buffer[written] = '\\';
                                memcpy(out_buffer + written + 1u, src + (pos - esc_step), esc_step);
                            } else {
                                overflow = 1;
                            }
                        }
                        written += 1u + esc_step;
                        cp_count += 2u;
                    }
                }
                continue;
            }

            if (out_buffer != NULL) {
                if (written + step <= out_capacity) {
                    memcpy(out_buffer + written, src + pos, step);
                } else {
                    overflow = 1;
                }
            }
            written += step;
            cp_count += 1u;
            pos += step;
        }

        if (is_multiline && has_line_break) {
            if (out_buffer != NULL) {
                if (written + 1u <= out_capacity) {
                    out_buffer[written] = '\n';
                } else {
                    overflow = 1;
                }
            }
            written += 1u;
            cp_count += 1u;
            pos = next_seg_start;
        }
    }

    /* In Python, an unclosed multiline literal at EOF appends one final '\n' when finishing the last line */
    if (is_multiline && token->kind == GRAM_TOKEN_ERROR) {
        if (end == 0 || (src[end - 1u] != '\n' && src[end - 1u] != '\r')) {
            if (out_buffer != NULL) {
                if (written + 1u <= out_capacity) {
                    out_buffer[written] = '\n';
                } else {
                    overflow = 1;
                }
            }
            written += 1u;
            cp_count += 1u;
        }
    }

    if (out_length) *out_length = written;
    if (out_codepoints) *out_codepoints = cp_count;
    return overflow ? -1 : 0;
}
