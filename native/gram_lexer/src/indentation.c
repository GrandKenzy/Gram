#include "gram_lexer_internal.h"
#include <string.h>

uint32_t gram_indent_measure_line(
    const GramLexer *lexer,
    uint32_t line_start,
    uint32_t line_end,
    uint32_t *out_leading_bytes,
    uint32_t *out_leading_cols
) {
    const char *src = lexer->source;
    uint32_t pos = line_start;

    while (pos < line_end && (src[pos] == ' ' || src[pos] == '\t')) {
        pos += 1u;
    }

    uint32_t leading = pos - line_start;
    if (out_leading_bytes) *out_leading_bytes = leading;
    if (out_leading_cols) *out_leading_cols = leading;

    uint32_t tab_width = (lexer->config.tab_width >= 1u) ? lexer->config.tab_width : 4u;
    uint8_t mode = lexer->config.indentation_mode;

    if (mode == GRAM_INDENT_TABS) {
        uint32_t tabs = 0;
        for (uint32_t i = line_start; i < pos; ++i) {
            if (src[i] == '\t') {
                tabs += 1u;
            }
        }
        return tabs * tab_width;
    }

    if (mode == GRAM_INDENT_MIXED) {
        uint32_t width = 0;
        for (uint32_t i = line_start; i < pos; ++i) {
            if (src[i] == '\t') {
                width += tab_width - (width % tab_width);
            } else {
                width += 1u;
            }
        }
        return width;
    }

    /* Default: GRAM_INDENT_SPACES */
    uint32_t spaces = 0;
    for (uint32_t i = line_start; i < pos; ++i) {
        if (src[i] == ' ') {
            spaces += 1u;
        }
    }
    return spaces;
}

int gram_indent_process_line(
    GramLexer *lexer,
    uint32_t indent_width,
    uint32_t leading_bytes,
    uint32_t leading_cols,
    GramToken *out_token,
    int *out_emitted
) {
    if (out_emitted) *out_emitted = 0;

    lexer->position = lexer->line_start + leading_bytes;
    lexer->column = leading_cols;

    if (!lexer->config.support_indent) {
        return GRAM_LEXER_TOKEN;
    }

    if (lexer->indent_depth == 0) {
        lexer->indents[0] = 0;
        lexer->indent_depth = 1u;
    }

    uint32_t current_indent = lexer->indents[lexer->indent_depth - 1u];

    if (indent_width > current_indent) {
        if (lexer->indent_depth < GRAM_LEXER_MAX_INDENT_DEPTH) {
            lexer->indents[lexer->indent_depth] = indent_width;
            lexer->indent_depth += 1u;
        }

        memset(out_token, 0, sizeof(GramToken));
        out_token->kind = GRAM_TOKEN_INDENT;
        out_token->flags = GRAM_TOKEN_FLAG_NONE;
        out_token->start = lexer->line_start;
        out_token->length = leading_bytes;
        out_token->line = lexer->line;
        out_token->column = 0;
        out_token->content_start = lexer->line_start;
        out_token->content_length = indent_width;

        if (out_emitted) *out_emitted = 1;
        return GRAM_LEXER_TOKEN;
    }

    if (indent_width < current_indent) {
        uint32_t target_idx = lexer->indent_depth - 1u;
        while (target_idx > 0 && indent_width < lexer->indents[target_idx]) {
            target_idx -= 1u;
        }
        uint32_t num_dedents = (lexer->indent_depth - 1u) - target_idx;

        if (indent_width != lexer->indents[target_idx]) {
            int halted = gram_lexer_emit_error(
                lexer,
                GRAM_DIAG_CODE_INDENTATION_MISMATCH,
                lexer->line_start,
                lexer->line_start + leading_bytes,
                lexer->line,
                0,
                "Indentation level does not match any outer block"
            );
            if (halted) {
                lexer->indent_depth = target_idx + 1u;
                memset(out_token, 0, sizeof(GramToken));
                out_token->kind = GRAM_TOKEN_ERROR;
                out_token->start = lexer->line_start;
                out_token->length = leading_bytes;
                out_token->line = lexer->line;
                out_token->column = 0;
                if (out_emitted) *out_emitted = 1;
                return GRAM_LEXER_FATAL;
            }
        }

        /* Pop the first indentation level and queue any remaining DEDENT tokens */
        lexer->indent_depth -= 1u;
        uint32_t first_target = lexer->indents[lexer->indent_depth - 1u];

        if (num_dedents > 1u) {
            lexer->pending_dedents = num_dedents - 1u;
            lexer->pending_dedent_line = lexer->line;
            lexer->pending_dedent_col = 0;
            lexer->pending_dedent_offset = lexer->line_start;
        }

        memset(out_token, 0, sizeof(GramToken));
        out_token->kind = GRAM_TOKEN_DEDENT;
        out_token->flags = GRAM_TOKEN_FLAG_NONE;
        out_token->start = lexer->line_start;
        out_token->length = 0;
        out_token->line = lexer->line;
        out_token->column = 0;
        out_token->content_start = lexer->line_start;
        out_token->content_length = first_target;

        if (out_emitted) *out_emitted = 1;
        return GRAM_LEXER_TOKEN;
    }

    return GRAM_LEXER_TOKEN;
}
