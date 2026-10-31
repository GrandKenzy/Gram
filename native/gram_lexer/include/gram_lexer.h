#ifndef GRAM_LEXER_H
#define GRAM_LEXER_H

#include <stdint.h>
#include <stddef.h>
#include "gram_lexer_tokens.h"
#include "gram_diagnostics_lite.h"

#ifdef __cplusplus
extern "C" {
#endif

#define GRAM_LEXER_MAX_INDENT_DEPTH 256

/**
 * Return status codes for gram_lexer_next().
 */
typedef enum {
    GRAM_LEXER_TOKEN = 0,
    GRAM_LEXER_EOF   = 1,
    GRAM_LEXER_ERROR = 2,
    GRAM_LEXER_FATAL = 3
} GramLexerStatus;

/**
 * Indentation calculation mode matching LEXER_INDENT_STYLE.
 */
typedef enum {
    GRAM_INDENT_SPACES = 0,
    GRAM_INDENT_TABS   = 1,
    GRAM_INDENT_MIXED  = 2
} GramIndentMode;

/**
 * Flat token emitted by the C lexer runtime.
 * `start` and `length` are UTF-8 byte offsets into `lexer->source`.
 * `line` is 1-based; `column` is 0-based Unicode codepoint index on that line.
 * `content_start` and `content_length` hold the inner payload span (for strings/comments)
 * or indentation level (for INDENT/DEDENT).
 */
typedef struct {
    uint32_t kind;
    uint32_t flags;
    uint32_t start;
    uint32_t length;
    uint32_t line;
    uint32_t column;
    uint32_t content_start;
    uint32_t content_length;
    uint32_t prefix_start;
    uint32_t prefix_length;
} GramToken;

/**
 * Flat configuration structure for the C lexer runtime.
 */
typedef struct {
    uint32_t tab_width;
    uint8_t indentation_mode;
    uint8_t add_info;
    uint8_t support_triple_strings;
    uint8_t support_prefixed_strings;
    uint8_t support_indent;
    uint8_t error_policy;
    uint8_t support_leading_dot_numbers;
    uint8_t support_triple_dot;
    uint8_t support_block_comments;
    uint8_t ignore_empty_lines;
    uint8_t ignore_newlines;
    uint8_t save_comments;
    uint8_t add_error;
    int32_t ident_underscores;
} GramLexerConfig;

/**
 * Static/exported keyword entry.
 */
typedef struct {
    const char *text;
    uint32_t length;
    uint32_t keyword_id;
    uint32_t group_offset;
    uint32_t group_count;
} GramKeywordEntry;

/**
 * Static/exported word-group entry.
 */
typedef struct {
    const char *name;
    uint32_t length;
    uint32_t group_id;
    uint32_t keyword_offset;
    uint32_t keyword_count;
} GramGroupEntry;

/**
 * Static/exported operator or delimiter entry, ordered for maximal-munch matching.
 */
typedef struct {
    const char *text;
    uint32_t length;
    uint32_t token_kind;
    uint32_t codepoint_length;
} GramSymbolEntry;

/**
 * Static/exported multiline delimiter entry (e.g. triple quotes or block comments).
 */
typedef struct {
    const char *opening;
    uint32_t opening_length;
    uint32_t opening_codepoints;
    const char *closing;
    uint32_t closing_length;
    uint32_t closing_codepoints;
    uint32_t token_kind;
    uint8_t decode_escapes;
    uint8_t is_block_comment;
} GramMultilineEntry;

/**
 * Immutable lexical tables exported from a Gram Session or constructed in memory.
 */
typedef struct {
    const GramKeywordEntry *keywords;
    uint32_t keyword_count;
    const GramGroupEntry *groups;
    uint32_t group_count;
    const uint32_t *group_memberships;
    uint32_t group_membership_count;
    const GramSymbolEntry *symbols;
    uint32_t symbol_count;
    const GramMultilineEntry *multiline;
    uint32_t multiline_count;
    const char *line_comment;
    uint32_t line_comment_length;
    const char *block_comment_open;
    uint32_t block_comment_open_length;
    const char *block_comment_close;
    uint32_t block_comment_close_length;
    const char *bool_true;
    uint32_t bool_true_length;
    const char *bool_false;
    uint32_t bool_false_length;
    const char *null_literal;
    uint32_t null_literal_length;
} GramLexerTables;

/**
 * Reentrant, zero-allocation C lexer state.
 */
typedef struct {
    const char *source;
    uint32_t length;
    uint32_t position;
    uint32_t line;
    uint32_t column;
    GramLexerConfig config;
    const GramLexerTables *tables;
    GramDiagSink diagnostics;
    void *user_context;

    /* Internal reentrant scanner state */
    uint32_t line_start;
    uint32_t line_end;
    uint32_t next_line_start;
    uint32_t total_lines;
    uint8_t has_current_line;
    uint8_t line_indent_processed;
    uint8_t line_newline_pending;
    uint8_t eof_emitted;
    uint8_t halted;
    uint8_t state_checked;
    uint32_t indents[GRAM_LEXER_MAX_INDENT_DEPTH];
    uint32_t indent_depth;
    uint32_t pending_dedents;
    uint32_t pending_dedent_line;
    uint32_t pending_dedent_col;
    uint32_t pending_dedent_offset;
} GramLexer;

/**
 * Return the default GramLexerConfig matching Gram's standard Python defaults.
 */
GramLexerConfig gram_lexer_default_config(void);

/**
 * Initialize a GramLexer instance over a UTF-8 buffer.
 */
void gram_lexer_init(
    GramLexer *lexer,
    const char *source,
    uint32_t length,
    const GramLexerConfig *config,
    const GramLexerTables *tables,
    GramDiagSink diagnostics,
    void *user_context
);

/**
 * Reset an already-initialized GramLexer over a new (or the same) UTF-8 buffer.
 */
void gram_lexer_reset(
    GramLexer *lexer,
    const char *source,
    uint32_t length
);

/**
 * Scan the next token from the input stream.
 * Returns one of GramLexerStatus (GRAM_LEXER_TOKEN, GRAM_LEXER_EOF, GRAM_LEXER_ERROR, GRAM_LEXER_FATAL).
 */
int gram_lexer_next(GramLexer *lexer, GramToken *out_token);

/**
 * Reset `lexer` over `source[0..length)` and scan all tokens until EOF or fatal halt.
 * Returns the total number of tokens produced (including EOF).
 */
uint32_t gram_lexer_scan_all(
    GramLexer *lexer,
    const char *source,
    uint32_t length
);

/**
 * Decode a string or multiline token payload (resolving escapes and normalizing line breaks)
 * into a caller-provided UTF-8 buffer without heap allocation.
 * If `out_buffer` is NULL, computes the required UTF-8 byte length in `*out_length`
 * and Unicode codepoint count in `*out_codepoints`.
 * Returns 0 on success, or non-zero if `out_capacity` is insufficient.
 */
int gram_lexer_decode_string(
    const GramLexer *lexer,
    const GramToken *token,
    char *out_buffer,
    uint32_t out_capacity,
    uint32_t *out_length,
    uint32_t *out_codepoints
);

/**
 * Look up a keyword entry by exact UTF-8 byte slice.
 */
const GramKeywordEntry *gram_tables_find_keyword(
    const GramLexerTables *tables,
    const char *text,
    uint32_t length
);

/**
 * Look up a word-group entry by exact UTF-8 byte slice.
 */
const GramGroupEntry *gram_tables_find_group(
    const GramLexerTables *tables,
    const char *name,
    uint32_t length
);

/**
 * Return 1 if `keyword` belongs to `group_id`, 0 otherwise.
 */
int gram_tables_keyword_in_group(
    const GramLexerTables *tables,
    const GramKeywordEntry *keyword,
    uint32_t group_id
);

#ifdef __cplusplus
}
#endif

#endif /* GRAM_LEXER_H */
