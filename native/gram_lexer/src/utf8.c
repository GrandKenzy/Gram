#include "gram_lexer_internal.h"

int gram_utf8_decode(
    const char *src,
    uint32_t length,
    uint32_t pos,
    uint32_t *out_codepoint,
    uint32_t *out_byte_len
) {
    if (src == NULL || pos >= length) {
        if (out_codepoint) *out_codepoint = 0;
        if (out_byte_len) *out_byte_len = 0;
        return 0;
    }

    uint8_t b0 = (uint8_t)src[pos];
    if (b0 < 0x80u) {
        if (out_codepoint) *out_codepoint = (uint32_t)b0;
        if (out_byte_len) *out_byte_len = 1u;
        return 1;
    }

    /* 2-byte sequence: 0xC2..0xDF, 0x80..0xBF */
    if (b0 >= 0xC2u && b0 <= 0xDFu) {
        if (pos + 1u < length) {
            uint8_t b1 = (uint8_t)src[pos + 1u];
            if ((b1 & 0xC0u) == 0x80u) {
                if (out_codepoint) {
                    *out_codepoint = (((uint32_t)(b0 & 0x1Fu)) << 6) | (uint32_t)(b1 & 0x3Fu);
                }
                if (out_byte_len) *out_byte_len = 2u;
                return 1;
            }
        }
    }
    /* 3-byte sequence: 0xE0..0xEF */
    else if (b0 >= 0xE0u && b0 <= 0xEFu) {
        if (pos + 2u < length) {
            uint8_t b1 = (uint8_t)src[pos + 1u];
            uint8_t b2 = (uint8_t)src[pos + 2u];
            int valid_b1 = ((b1 & 0xC0u) == 0x80u);
            if (b0 == 0xE0u && b1 < 0xA0u) valid_b1 = 0; /* overlong */
            if (b0 == 0xEDu && b1 >= 0xA0u) valid_b1 = 0; /* UTF-16 surrogates U+D800..U+DFFF */
            if (valid_b1 && ((b2 & 0xC0u) == 0x80u)) {
                if (out_codepoint) {
                    *out_codepoint = (((uint32_t)(b0 & 0x0Fu)) << 12)
                                   | (((uint32_t)(b1 & 0x3Fu)) << 6)
                                   | (uint32_t)(b2 & 0x3Fu);
                }
                if (out_byte_len) *out_byte_len = 3u;
                return 1;
            }
        }
    }
    /* 4-byte sequence: 0xF0..0xF4 */
    else if (b0 >= 0xF0u && b0 <= 0xF4u) {
        if (pos + 3u < length) {
            uint8_t b1 = (uint8_t)src[pos + 1u];
            uint8_t b2 = (uint8_t)src[pos + 2u];
            uint8_t b3 = (uint8_t)src[pos + 3u];
            int valid_b1 = ((b1 & 0xC0u) == 0x80u);
            if (b0 == 0xF0u && b1 < 0x90u) valid_b1 = 0; /* overlong */
            if (b0 == 0xF4u && b1 >= 0x90u) valid_b1 = 0; /* > U+10FFFF */
            if (valid_b1 && ((b2 & 0xC0u) == 0x80u) && ((b3 & 0xC0u) == 0x80u)) {
                if (out_codepoint) {
                    *out_codepoint = (((uint32_t)(b0 & 0x07u)) << 18)
                                   | (((uint32_t)(b1 & 0x3Fu)) << 12)
                                   | (((uint32_t)(b2 & 0x3Fu)) << 6)
                                   | (uint32_t)(b3 & 0x3Fu);
                }
                if (out_byte_len) *out_byte_len = 4u;
                return 1;
            }
        }
    }

    if (out_codepoint) *out_codepoint = 0xFFFDu;
    if (out_byte_len) *out_byte_len = 1u;
    return 0;
}

uint32_t gram_utf8_count_codepoints(const char *src, uint32_t byte_len) {
    uint32_t pos = 0;
    uint32_t count = 0;
    while (pos < byte_len) {
        uint32_t cp = 0;
        uint32_t step = 1;
        (void)gram_utf8_decode(src, byte_len, pos, &cp, &step);
        pos += (step > 0) ? step : 1u;
        count += 1u;
    }
    return count;
}

int gram_unicode_is_alpha(uint32_t cp) {
    if (cp < 0x80u) {
        return ((cp >= 'A' && cp <= 'Z') || (cp >= 'a' && cp <= 'z')) ? 1 : 0;
    }
    /* Latin-1 Supplement letters */
    if (cp == 0x00AAu || cp == 0x00B5u || cp == 0x00BAu) return 1;
    if (cp >= 0x00C0u && cp <= 0x00D6u) return 1;
    if (cp >= 0x00D8u && cp <= 0x00F6u) return 1;
    if (cp >= 0x00F8u && cp <= 0x02C1u) return 1;
    if (cp >= 0x02C6u && cp <= 0x02D1u) return 1;
    if (cp >= 0x02E0u && cp <= 0x02E4u) return 1;
    if (cp == 0x02ECu || cp == 0x02EEu) return 1;
    /* Greek and Coptic */
    if (cp >= 0x0370u && cp <= 0x0374u) return 1;
    if (cp >= 0x0376u && cp <= 0x0377u) return 1;
    if (cp >= 0x037Au && cp <= 0x037Du) return 1;
    if (cp == 0x037Fu || cp == 0x0386u) return 1;
    if (cp >= 0x0388u && cp <= 0x038Au) return 1;
    if (cp == 0x038Cu) return 1;
    if (cp >= 0x038Eu && cp <= 0x03A1u) return 1;
    if (cp >= 0x03A3u && cp <= 0x03F5u) return 1;
    if (cp >= 0x03F7u && cp <= 0x0481u) return 1;
    /* Cyrillic */
    if (cp >= 0x048Au && cp <= 0x052Fu) return 1;
    /* Armenian & Hebrew */
    if (cp >= 0x0531u && cp <= 0x0556u) return 1;
    if (cp >= 0x0560u && cp <= 0x0588u) return 1;
    if (cp >= 0x05D0u && cp <= 0x05EAu) return 1;
    /* Arabic letters (excluding Arabic-Indic digits 0x0660..0x0669 and 0x06F0..0x06F9) */
    if (cp >= 0x0620u && cp <= 0x064Au) return 1;
    if (cp >= 0x066Eu && cp <= 0x066Fu) return 1;
    if (cp >= 0x0671u && cp <= 0x06D3u) return 1;
    if (cp == 0x06D5u || (cp >= 0x06E5u && cp <= 0x06E6u)) return 1;
    if (cp >= 0x06EEu && cp <= 0x06EFu) return 1;
    if (cp >= 0x06FAu && cp <= 0x06FCu) return 1;
    if (cp == 0x06FFu) return 1;
    /* Devanagari and Indic letters */
    if (cp >= 0x0904u && cp <= 0x0939u) return 1;
    if (cp >= 0x0958u && cp <= 0x0961u) return 1;
    /* Phonetic Extensions, Latin Extended Additional, Greek Extended */
    if (cp >= 0x1D00u && cp <= 0x1DBFu) return 1;
    if (cp >= 0x1E00u && cp <= 0x1EFFu) return 1;
    if (cp >= 0x1F00u && cp <= 0x1FFFu) return 1;
    /* Hiragana & Katakana */
    if (cp >= 0x3041u && cp <= 0x3096u) return 1;
    if (cp >= 0x30A1u && cp <= 0x30FAu) return 1;
    if (cp >= 0x30FCu && cp <= 0x30FFu) return 1;
    /* CJK Unified Ideographs & Extensions */
    if (cp >= 0x3400u && cp <= 0x4DBFu) return 1;
    if (cp >= 0x4E00u && cp <= 0x9FFFu) return 1;
    /* Hangul Syllables */
    if (cp >= 0xAC00u && cp <= 0xD7A3u) return 1;
    /* Halfwidth and Fullwidth Latin letters */
    if (cp >= 0xFF21u && cp <= 0xFF3Au) return 1;
    if (cp >= 0xFF41u && cp <= 0xFF5Au) return 1;
    /* Mathematical Alphanumeric Symbols (letters) & CJK Extension B+ */
    if (cp >= 0x1D400u && cp <= 0x1D7CDu) return 1;
    if (cp >= 0x20000u && cp <= 0x2FA1Fu) return 1;
    return 0;
}

static int gram_unicode_is_numeric_only(uint32_t cp) {
    if (cp >= '0' && cp <= '9') return 1;
    /* Superscript digits ², ³, ¹ and vulgar fractions ¼, ½, ¾ */
    if (cp == 0x00B2u || cp == 0x00B3u || cp == 0x00B9u) return 1;
    if (cp >= 0x00BCu && cp <= 0x00BEu) return 1;
    /* Arabic-Indic and Extended Arabic-Indic digits */
    if (cp >= 0x0660u && cp <= 0x0669u) return 1;
    if (cp >= 0x06F0u && cp <= 0x06F9u) return 1;
    /* Devanagari digits */
    if (cp >= 0x0966u && cp <= 0x096Fu) return 1;
    /* Fullwidth digits */
    if (cp >= 0xFF10u && cp <= 0xFF19u) return 1;
    /* Mathematical alphanumeric digits */
    if (cp >= 0x1D7CEu && cp <= 0x1D7FFu) return 1;
    return 0;
}

int gram_unicode_is_alnum(uint32_t cp) {
    if (cp < 0x80u) {
        return ((cp >= '0' && cp <= '9') || (cp >= 'A' && cp <= 'Z') || (cp >= 'a' && cp <= 'z')) ? 1 : 0;
    }
    return (gram_unicode_is_alpha(cp) || gram_unicode_is_numeric_only(cp)) ? 1 : 0;
}

int gram_unicode_is_whitespace(uint32_t cp) {
    if (cp == ' ' || cp == '\t' || cp == '\n' || cp == '\r' || cp == '\v' || cp == '\f') {
        return 1;
    }
    if (cp >= 0x1Cu && cp <= 0x1Fu) return 1;
    if (cp == 0x0085u || cp == 0x00A0u || cp == 0x1680u) return 1;
    if (cp >= 0x2000u && cp <= 0x200Au) return 1;
    if (cp == 0x2028u || cp == 0x2029u || cp == 0x202Fu || cp == 0x205Fu || cp == 0x3000u) return 1;
    return 0;
}

int gram_ascii_strncasecmp(const char *a, const char *b, uint32_t len) {
    if (a == NULL || b == NULL) return -1;
    for (uint32_t i = 0; i < len; ++i) {
        uint8_t ca = (uint8_t)a[i];
        uint8_t cb = (uint8_t)b[i];
        if (ca >= 'A' && ca <= 'Z') ca = (uint8_t)(ca - 'A' + 'a');
        if (cb >= 'A' && cb <= 'Z') cb = (uint8_t)(cb - 'A' + 'a');
        if (ca != cb) {
            return (int)ca - (int)cb;
        }
    }
    return 0;
}
