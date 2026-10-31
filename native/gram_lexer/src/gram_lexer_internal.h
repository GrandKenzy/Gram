#ifndef GRAM_LEXER_INTERNAL_H
#define GRAM_LEXER_INTERNAL_H

#include "../include/gram_lexer.h"

/* UTF-8 & Unicode classification helpers (utf8.c) */
int gram_utf8_decode(
    const char *src,
    uint32_t length,
    uint32_t pos,
    uint32_t *out_codepoint,
    uint32_t *out_byte_len
);

uint32_t gram_utf8_count_codepoints(const char *src, uint32_t byte_len);
int gram_unicode_is_alpha(uint32_t cp);
int gram_unicode_is_alnum(uint32_t cp);
int gram_unicode_is_whitespace(uint32_t cp);
int gram_ascii_strncasecmp(const char *a, const char *b, uint32_t len);

/* Line boundary navigation & diagnostics helper (lexer.c) */
void gram_lexer_load_line_at(GramLexer *lexer, uint32_t line_start_pos);
int gram_lexer_emit_error(
    GramLexer *lexer,
    uint32_t code,
    uint32_t start,
    uint32_t end,
    uint32_t line,
    uint32_t column,
    const char *message
);

/* Indentation scanner (indentation.c) */
uint32_t gram_indent_measure_line(
    const GramLexer *lexer,
    uint32_t line_start,
    uint32_t line_end,
    uint32_t *out_leading_bytes,
    uint32_t *out_leading_cols
);

int gram_indent_process_line(
    GramLexer *lexer,
    uint32_t indent_width,
    uint32_t leading_bytes,
    uint32_t leading_cols,
    GramToken *out_token,
    int *out_emitted
);

/* Symbol scanner (symbols.c) */
int gram_scan_symbol(GramLexer *lexer, GramToken *out_token);

/* Number scanner (numbers.c) */
int gram_scan_number(GramLexer *lexer, GramToken *out_token);

/* String and multiline scanner (strings.c) */
const GramMultilineEntry *gram_match_multiline(
    const GramLexer *lexer,
    uint32_t byte_pos
);

int gram_scan_multiline(
    GramLexer *lexer,
    const GramMultilineEntry *entry,
    uint32_t start_byte,
    uint32_t start_line,
    uint32_t start_col,
    uint32_t prefix_start,
    uint32_t prefix_len,
    GramToken *out_token
);

int gram_scan_string(
    GramLexer *lexer,
    char quote,
    uint32_t start_byte,
    uint32_t start_line,
    uint32_t start_col,
    uint32_t prefix_start,
    uint32_t prefix_len,
    GramToken *out_token
);

#endif /* GRAM_LEXER_INTERNAL_H */
