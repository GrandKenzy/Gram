#include "gram_lexer_internal.h"
#include <string.h>

int gram_scan_symbol(GramLexer *lexer, GramToken *out_token) {
    uint32_t start_pos = lexer->position;
    uint32_t start_col = lexer->column;
    uint32_t line_end = lexer->line_end;
    const char *src = lexer->source;

    if (lexer->tables != NULL && lexer->tables->symbols != NULL) {
        uint32_t count = lexer->tables->symbol_count;
        const GramSymbolEntry *symbols = lexer->tables->symbols;

        for (uint32_t i = 0; i < count; ++i) {
            const GramSymbolEntry *sym = &symbols[i];
            if (sym->length == 0 || sym->text == NULL) {
                continue;
            }
            if (sym->length == 3u &&
                sym->text[0] == '.' && sym->text[1] == '.' && sym->text[2] == '.' &&
                !lexer->config.support_triple_dot) {
                continue;
            }
            if (start_pos + sym->length <= line_end &&
                memcmp(src + start_pos, sym->text, sym->length) == 0) {
                uint32_t cp_len = sym->codepoint_length;
                if (cp_len == 0) {
                    cp_len = gram_utf8_count_codepoints(sym->text, sym->length);
                }
                memset(out_token, 0, sizeof(GramToken));
                out_token->kind = sym->token_kind;
                out_token->flags = GRAM_TOKEN_FLAG_NONE;
                out_token->start = start_pos;
                out_token->length = sym->length;
                out_token->line = lexer->line;
                out_token->column = start_col;
                out_token->content_start = start_pos;
                out_token->content_length = sym->length;

                lexer->position = start_pos + sym->length;
                lexer->column = start_col + cp_len;
                return GRAM_LEXER_TOKEN;
            }
        }
    }

    /* Unrecognized symbol or invalid UTF-8 byte sequence */
    uint32_t cp = 0;
    uint32_t step = 1u;
    int valid_utf8 = gram_utf8_decode(src, line_end, start_pos, &cp, &step);
    if (step == 0) {
        step = 1u;
    }

    lexer->position = start_pos + step;
    lexer->column = start_col + 1u;

    memset(out_token, 0, sizeof(GramToken));
    out_token->kind = GRAM_TOKEN_ERROR;
    out_token->flags = GRAM_TOKEN_FLAG_NONE;
    out_token->start = start_pos;
    out_token->length = step;
    out_token->line = lexer->line;
    out_token->column = start_col;
    out_token->content_start = start_pos;
    out_token->content_length = step;

    uint32_t diag_code = valid_utf8
        ? GRAM_DIAG_CODE_UNEXPECTED_CHARACTER
        : GRAM_DIAG_CODE_INVALID_UTF8;
    const char *msg = valid_utf8
        ? "Unexpected character or unrecognized symbol"
        : "Invalid or truncated UTF-8 byte sequence";

    int halted = gram_lexer_emit_error(
        lexer,
        diag_code,
        start_pos,
        start_pos + step,
        lexer->line,
        start_col,
        msg
    );
    return halted ? GRAM_LEXER_FATAL : GRAM_LEXER_ERROR;
}
