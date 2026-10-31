#include "gram_lexer_internal.h"
#include <string.h>

static const char * const TOKEN_KIND_NAMES[85] = {
    "EOF",              /* 0 */
    "NEWLINE",          /* 1 */
    "IDENT",            /* 2 */
    "INDENT",           /* 3 */
    "DEDENT",           /* 4 */
    "COMMENT",          /* 5 */
    "KEYWORD",          /* 6 */
    "STRING",           /* 7 */
    "NUMBER",           /* 8 */
    "BOOL",             /* 9 */
    "NULL",             /* 10 */
    "PLUS",             /* 11 */
    "MINUS",            /* 12 */
    "STAR",             /* 13 */
    "SLASH",            /* 14 */
    "PERCENT",          /* 15 */
    "POW",              /* 16 */
    "FLOOR_DIV",        /* 17 */
    "INCREMENT",        /* 18 */
    "DECREMENT",        /* 19 */
    "ASSIGN",           /* 20 */
    "PLUS_ASSIGN",      /* 21 */
    "MINUS_ASSIGN",     /* 22 */
    "STAR_ASSIGN",      /* 23 */
    "SLASH_ASSIGN",     /* 24 */
    "PERCENT_ASSIGN",   /* 25 */
    "POW_ASSIGN",       /* 26 */
    "FLOOR_DIV_ASSIGN", /* 27 */
    "AND_ASSIGN",       /* 28 */
    "OR_ASSIGN",        /* 29 */
    "XOR_ASSIGN",       /* 30 */
    "SHL_ASSIGN",       /* 31 */
    "SHR_ASSIGN",       /* 32 */
    "WALRUS",           /* 33 */
    "EQUAL",            /* 34 */
    "NOT_EQUAL",        /* 35 */
    "LESS",             /* 36 */
    "GREATER",          /* 37 */
    "LESS_EQUAL",       /* 38 */
    "GREATER_EQUAL",    /* 39 */
    "NOT",              /* 40 */
    "NOT_LOGIC",        /* 41 */
    "AND_LOGIC",        /* 42 */
    "OR_LOGIC",         /* 43 */
    "AND",              /* 44 */
    "OR",               /* 45 */
    "XOR",              /* 46 */
    "SHL",              /* 47 */
    "SHR",              /* 48 */
    "LPAREN",           /* 49 */
    "RPAREN",           /* 50 */
    "LBRACKET",         /* 51 */
    "RBRACKET",         /* 52 */
    "LBRACE",           /* 53 */
    "RBRACE",           /* 54 */
    "COMMA",            /* 55 */
    "DOT",              /* 56 */
    "COLON",            /* 57 */
    "SEMICOLON",        /* 58 */
    "AT",               /* 59 */
    "HASH",             /* 60 */
    "DOLLAR",           /* 61 */
    "QUESTION",         /* 62 */
    "QUESTION_ASSIGN",  /* 63 */
    "EXCLAMATION",      /* 64 */
    "BACKSLASH",        /* 65 */
    "UNDERSCORE",       /* 66 */
    "ARROW",            /* 67 */
    "FAT_ARROW",        /* 68 */
    "LEFT_ARROW",       /* 69 */
    "DOUBLE_ARROW",     /* 70 */
    "LOGIC_AND",        /* 71 */
    "LOGIC_OR",         /* 72 */
    "LOGIC_NOT",        /* 73 */
    "SQRT",             /* 74 */
    "INFINITY",         /* 75 */
    "DEGREE",           /* 76 */
    "MIDDLE_DOT",       /* 77 */
    "BULLET",           /* 78 */
    "SECTION",          /* 79 */
    "THREE_DOTS",       /* 80 */
    "ERROR",            /* 81 */
    "UNKNOWN",          /* 82 */
    "EMPTY_LINE",       /* 83 */
    "DECIMAL"           /* 84 */
};

const char *gram_token_kind_name(uint32_t kind) {
    if (kind < 85u) {
        return TOKEN_KIND_NAMES[kind];
    }
    if (kind >= GRAM_TOKEN_CUSTOM_BASE) {
        return "CUSTOM";
    }
    return "UNKNOWN";
}

GramLexerConfig gram_lexer_default_config(void) {
    GramLexerConfig cfg;
    memset(&cfg, 0, sizeof(GramLexerConfig));
    cfg.tab_width = 4u;
    cfg.indentation_mode = (uint8_t)GRAM_INDENT_SPACES;
    cfg.add_info = 1u;
    cfg.support_triple_strings = 1u;
    cfg.support_prefixed_strings = 1u;
    cfg.support_indent = 1u;
    cfg.error_policy = (uint8_t)GRAM_ERROR_POLICY_RECOVER;
    cfg.support_leading_dot_numbers = 1u;
    cfg.support_triple_dot = 1u;
    cfg.support_block_comments = 1u;
    cfg.ignore_empty_lines = 1u;
    cfg.ignore_newlines = 1u;
    cfg.save_comments = 0u;
    cfg.add_error = 1u;
    return cfg;
}

void gram_lexer_load_line_at(GramLexer *lexer, uint32_t line_start_pos) {
    const char *src = lexer->source;
    uint32_t len = lexer->length;

    if (src == NULL || line_start_pos >= len) {
        lexer->line_start = len;
        lexer->line_end = len;
        lexer->next_line_start = len;
        lexer->position = len;
        lexer->column = 0;
        lexer->has_current_line = 0;
        lexer->line_indent_processed = 0;
        lexer->line_newline_pending = 0;
        return;
    }

    uint32_t scan = line_start_pos;
    while (scan < len && src[scan] != '\n' && src[scan] != '\r') {
        scan += 1u;
    }

    uint32_t next_start = scan;
    if (scan < len) {
        if (src[scan] == '\r' && (scan + 1u) < len && src[scan + 1u] == '\n') {
            next_start = scan + 2u;
        } else {
            next_start = scan + 1u;
        }
    }

    lexer->line_start = line_start_pos;
    lexer->line_end = scan;
    lexer->next_line_start = next_start;
    lexer->position = line_start_pos;
    lexer->column = 0;
    lexer->has_current_line = 1u;
    lexer->line_indent_processed = 0;
    lexer->line_newline_pending = 0;
}

static void advance_to_next_line(GramLexer *lexer) {
    if (lexer->next_line_start < lexer->length) {
        gram_lexer_load_line_at(lexer, lexer->next_line_start);
        lexer->line += 1u;
        lexer->column = 0;
    } else {
        lexer->has_current_line = 0;
        lexer->position = lexer->length;
        lexer->line_start = lexer->length;
        lexer->line_end = lexer->length;
        lexer->line += 1u;
        lexer->column = 0;
        lexer->line_indent_processed = 0;
    }
}

void gram_lexer_reset(
    GramLexer *lexer,
    const char *source,
    uint32_t length
) {
    if (lexer == NULL) {
        return;
    }
    lexer->source = (source != NULL) ? source : "";
    lexer->length = (source != NULL) ? length : 0u;
    lexer->position = 0;
    lexer->line = 1u;
    lexer->column = 0;
    lexer->eof_emitted = 0;
    lexer->halted = 0;
    lexer->state_checked = 0;
    lexer->indents[0] = 0;
    lexer->indent_depth = 1u;
    lexer->pending_dedents = 0;
    lexer->pending_dedent_line = 1u;
    lexer->pending_dedent_col = 0;
    lexer->pending_dedent_offset = 0;

    if (lexer->length > 0) {
        gram_lexer_load_line_at(lexer, 0);
    } else {
        lexer->line_start = 0;
        lexer->line_end = 0;
        lexer->next_line_start = 0;
        lexer->has_current_line = 0;
        lexer->line_indent_processed = 0;
        lexer->line_newline_pending = 0;
    }
}

void gram_lexer_init(
    GramLexer *lexer,
    const char *source,
    uint32_t length,
    const GramLexerConfig *config,
    const GramLexerTables *tables,
    GramDiagSink diagnostics,
    void *user_context
) {
    if (lexer == NULL) {
        return;
    }
    memset(lexer, 0, sizeof(GramLexer));
    lexer->config = (config != NULL) ? *config : gram_lexer_default_config();
    lexer->tables = tables;
    lexer->diagnostics = diagnostics;
    lexer->user_context = user_context;
    gram_lexer_reset(lexer, source, length);
}

int gram_lexer_emit_error(
    GramLexer *lexer,
    uint32_t code,
    uint32_t start,
    uint32_t end,
    uint32_t line,
    uint32_t column,
    const char *message
) {
    uint32_t msg_len = (message != NULL) ? (uint32_t)strlen(message) : 0u;
    gram_diag_emit(
        &lexer->diagnostics,
        code,
        GRAM_DIAG_ERROR,
        start,
        end,
        line,
        column,
        message,
        msg_len
    );

    int sink_halted = gram_diag_sink_is_halted(&lexer->diagnostics);
    if (sink_halted == 1) {
        lexer->halted = 1u;
        return 1;
    }
    if (sink_halted < 0 &&
        gram_diag_should_halt(GRAM_DIAG_ERROR, (GramErrorPolicy)lexer->config.error_policy)) {
        lexer->halted = 1u;
        return 1;
    }
    return (int)lexer->halted;
}

const GramKeywordEntry *gram_tables_find_keyword(
    const GramLexerTables *tables,
    const char *text,
    uint32_t length
) {
    if (tables == NULL || tables->keywords == NULL || text == NULL) {
        return NULL;
    }
    for (uint32_t i = 0; i < tables->keyword_count; ++i) {
        const GramKeywordEntry *kw = &tables->keywords[i];
        if (kw->length == length && kw->text != NULL && memcmp(kw->text, text, length) == 0) {
            return kw;
        }
    }
    return NULL;
}

const GramGroupEntry *gram_tables_find_group(
    const GramLexerTables *tables,
    const char *name,
    uint32_t length
) {
    if (tables == NULL || tables->groups == NULL || name == NULL) {
        return NULL;
    }
    for (uint32_t i = 0; i < tables->group_count; ++i) {
        const GramGroupEntry *grp = &tables->groups[i];
        if (grp->length == length && grp->name != NULL && memcmp(grp->name, name, length) == 0) {
            return grp;
        }
    }
    return NULL;
}

int gram_tables_keyword_in_group(
    const GramLexerTables *tables,
    const GramKeywordEntry *keyword,
    uint32_t group_id
) {
    if (tables == NULL || keyword == NULL || tables->group_memberships == NULL) {
        return 0;
    }
    uint32_t end = keyword->group_offset + keyword->group_count;
    if (end > tables->group_membership_count) {
        end = tables->group_membership_count;
    }
    for (uint32_t i = keyword->group_offset; i < end; ++i) {
        if (tables->group_memberships[i] == group_id) {
            return 1;
        }
    }
    return 0;
}

static int is_line_empty(const char *src, uint32_t start, uint32_t end) {
    uint32_t pos = start;
    while (pos < end) {
        uint32_t cp = 0;
        uint32_t step = 1u;
        int valid = gram_utf8_decode(src, end, pos, &cp, &step);
        if (!valid || !gram_unicode_is_whitespace(cp)) {
            return 0;
        }
        pos += (step > 0) ? step : 1u;
    }
    return 1;
}

static uint32_t match_line_comment_at(const GramLexer *lexer, uint32_t pos) {
    const char *marker = "#";
    uint32_t marker_len = 1u;

    if (lexer->tables != NULL && lexer->tables->line_comment != NULL && lexer->tables->line_comment_length > 0) {
        marker = lexer->tables->line_comment;
        marker_len = lexer->tables->line_comment_length;
    }

    if (pos + marker_len <= lexer->line_end &&
        memcmp(lexer->source + pos, marker, marker_len) == 0) {
        return marker_len;
    }
    return 0;
}

static int match_block_comment_at(const GramLexer *lexer, uint32_t pos) {
    if (!lexer->config.support_block_comments || lexer->tables == NULL) {
        return 0;
    }
    if (lexer->tables->block_comment_open != NULL && lexer->tables->block_comment_open_length > 0) {
        uint32_t len = lexer->tables->block_comment_open_length;
        if (pos + len <= lexer->line_end &&
            memcmp(lexer->source + pos, lexer->tables->block_comment_open, len) == 0) {
            return 1;
        }
    }
    return 0;
}

static int scan_word(GramLexer *lexer, GramToken *out_token) {
    const char *src = lexer->source;
    uint32_t line_end = lexer->line_end;
    uint32_t start_pos = lexer->position;
    uint32_t start_col = lexer->column;

    while (lexer->position < line_end) {
        uint32_t cp = 0;
        uint32_t step = 1u;
        int valid = gram_utf8_decode(src, line_end, lexer->position, &cp, &step);
        if (valid && (gram_unicode_is_alnum(cp) || cp == (uint32_t)'_')) {
            lexer->position += step;
            lexer->column += 1u;
        } else {
            break;
        }
    }

    const char *word = src + start_pos;
    uint32_t word_len = lexer->position - start_pos;

    /* 1. Boolean literals (case-insensitive) */
    const char *true_lit = "true";
    uint32_t true_len = 4u;
    const char *false_lit = "false";
    uint32_t false_len = 5u;
    const char *null_lit = "null";
    uint32_t null_len = 4u;

    if (lexer->tables != NULL) {
        true_lit = lexer->tables->bool_true;
        true_len = lexer->tables->bool_true_length;
        false_lit = lexer->tables->bool_false;
        false_len = lexer->tables->bool_false_length;
        null_lit = lexer->tables->null_literal;
        null_len = lexer->tables->null_literal_length;
    }

    if (true_lit != NULL && true_len > 0 && word_len == true_len &&
        gram_ascii_strncasecmp(word, true_lit, word_len) == 0) {
        memset(out_token, 0, sizeof(GramToken));
        out_token->kind = GRAM_TOKEN_BOOL;
        out_token->flags = GRAM_TOKEN_FLAG_BOOL_TRUE;
        out_token->start = start_pos;
        out_token->length = word_len;
        out_token->line = lexer->line;
        out_token->column = start_col;
        out_token->content_start = start_pos;
        out_token->content_length = word_len;
        return GRAM_LEXER_TOKEN;
    }

    if (false_lit != NULL && false_len > 0 && word_len == false_len &&
        gram_ascii_strncasecmp(word, false_lit, word_len) == 0) {
        memset(out_token, 0, sizeof(GramToken));
        out_token->kind = GRAM_TOKEN_BOOL;
        out_token->flags = GRAM_TOKEN_FLAG_NONE;
        out_token->start = start_pos;
        out_token->length = word_len;
        out_token->line = lexer->line;
        out_token->column = start_col;
        out_token->content_start = start_pos;
        out_token->content_length = word_len;
        return GRAM_LEXER_TOKEN;
    }

    /* 2. Null literal (case-insensitive) */
    if (null_lit != NULL && null_len > 0 && word_len == null_len &&
        gram_ascii_strncasecmp(word, null_lit, word_len) == 0) {
        memset(out_token, 0, sizeof(GramToken));
        out_token->kind = GRAM_TOKEN_NULL;
        out_token->flags = GRAM_TOKEN_FLAG_NONE;
        out_token->start = start_pos;
        out_token->length = word_len;
        out_token->line = lexer->line;
        out_token->column = start_col;
        out_token->content_start = start_pos;
        out_token->content_length = word_len;
        return GRAM_LEXER_TOKEN;
    }

    /* 3. Exact registered keyword */
    const GramKeywordEntry *kw = gram_tables_find_keyword(lexer->tables, word, word_len);
    if (kw != NULL) {
        memset(out_token, 0, sizeof(GramToken));
        out_token->kind = GRAM_TOKEN_KEYWORD;
        out_token->flags = GRAM_TOKEN_FLAG_NONE;
        out_token->start = start_pos;
        out_token->length = word_len;
        out_token->line = lexer->line;
        out_token->column = start_col;
        out_token->content_start = start_pos;
        out_token->content_length = word_len;
        return GRAM_LEXER_TOKEN;
    }

    /* 4. Generic identifier */
    memset(out_token, 0, sizeof(GramToken));
    out_token->kind = GRAM_TOKEN_IDENT;
    out_token->flags = GRAM_TOKEN_FLAG_NONE;
    out_token->start = start_pos;
    out_token->length = word_len;
    out_token->line = lexer->line;
    out_token->column = start_col;
    out_token->content_start = start_pos;
    out_token->content_length = word_len;
    return GRAM_LEXER_TOKEN;
}

int gram_lexer_next(GramLexer *lexer, GramToken *out_token) {
    if (lexer == NULL || out_token == NULL) {
        return GRAM_LEXER_FATAL;
    }

    if (lexer->halted) {
        memset(out_token, 0, sizeof(GramToken));
        out_token->kind = GRAM_TOKEN_EOF;
        out_token->start = lexer->position;
        out_token->line = lexer->line;
        out_token->column = lexer->column;
        return GRAM_LEXER_FATAL;
    }

    if (!lexer->state_checked) {
        lexer->state_checked = 1u;
        if (lexer->tables == NULL || lexer->tables->keyword_count == 0) {
            int halted = gram_lexer_emit_error(
                lexer,
                GRAM_DIAG_CODE_EMPTY_KEYWORDS,
                0,
                0,
                1u,
                0,
                "No keywords are registered in the active lexical catalog"
            );
            if (halted) {
                memset(out_token, 0, sizeof(GramToken));
                out_token->kind = GRAM_TOKEN_EOF;
                out_token->line = 1u;
                out_token->column = 0;
                return GRAM_LEXER_FATAL;
            }
        }
    }

    /* Emit queued multi-level DEDENT tokens */
    if (lexer->pending_dedents > 0) {
        lexer->pending_dedents -= 1u;
        if (lexer->indent_depth > 1u) {
            lexer->indent_depth -= 1u;
        }
        uint32_t target_indent = lexer->indents[lexer->indent_depth - 1u];

        memset(out_token, 0, sizeof(GramToken));
        out_token->kind = GRAM_TOKEN_DEDENT;
        out_token->flags = GRAM_TOKEN_FLAG_NONE;
        out_token->start = lexer->pending_dedent_offset;
        out_token->length = 0;
        out_token->line = lexer->pending_dedent_line;
        out_token->column = lexer->pending_dedent_col;
        out_token->content_start = lexer->pending_dedent_offset;
        out_token->content_length = target_indent;
        return GRAM_LEXER_TOKEN;
    }

    /* Emit pending end-of-line NEWLINE (e.g. after a multiline construct or comment) */
    if (lexer->line_newline_pending) {
        lexer->line_newline_pending = 0;
        memset(out_token, 0, sizeof(GramToken));
        out_token->kind = GRAM_TOKEN_NEWLINE;
        out_token->flags = GRAM_TOKEN_FLAG_NONE;
        out_token->start = lexer->position;
        out_token->length = 0;
        out_token->line = lexer->line;
        out_token->column = lexer->column;
        out_token->content_start = lexer->position;
        out_token->content_length = 0;

        if (lexer->has_current_line) {
            advance_to_next_line(lexer);
        } else {
            lexer->line += 1u;
            lexer->column = 0;
        }
        return GRAM_LEXER_TOKEN;
    }

    const char *src = lexer->source;

    while (lexer->has_current_line) {
        if (!lexer->line_indent_processed) {
            /* 1a. Empty or whitespace-only line check */
            if (is_line_empty(src, lexer->line_start, lexer->line_end)) {
                if (!lexer->config.ignore_empty_lines && !lexer->config.ignore_newlines) {
                    uint32_t cur_line = lexer->line;
                    uint32_t l_start = lexer->line_start;
                    advance_to_next_line(lexer);

                    memset(out_token, 0, sizeof(GramToken));
                    out_token->kind = GRAM_TOKEN_NEWLINE;
                    out_token->flags = GRAM_TOKEN_FLAG_NONE;
                    out_token->start = l_start;
                    out_token->length = 0;
                    out_token->line = cur_line;
                    out_token->column = 0;
                    out_token->content_start = l_start;
                    out_token->content_length = 0;
                    return GRAM_LEXER_TOKEN;
                }
                advance_to_next_line(lexer);
                continue;
            }

            /* 1b. Comment-only line check (line comments only, not block comments) */
            uint32_t leading_bytes = 0;
            uint32_t leading_cols = 0;
            uint32_t indent_width = gram_indent_measure_line(
                lexer,
                lexer->line_start,
                lexer->line_end,
                &leading_bytes,
                &leading_cols
            );

            uint32_t first_non_ws = lexer->line_start + leading_bytes;
            uint32_t comment_marker_len = match_line_comment_at(lexer, first_non_ws);
            if (comment_marker_len > 0 && !match_block_comment_at(lexer, first_non_ws)) {
                if (lexer->config.save_comments) {
                    uint32_t cur_line = lexer->line;
                    uint32_t c_start = first_non_ws;
                    uint32_t c_len = lexer->line_end - first_non_ws;
                    uint32_t body_start = first_non_ws + comment_marker_len;
                    uint32_t body_len = lexer->line_end - body_start;
                    advance_to_next_line(lexer);

                    memset(out_token, 0, sizeof(GramToken));
                    out_token->kind = GRAM_TOKEN_COMMENT;
                    out_token->flags = GRAM_TOKEN_FLAG_NONE;
                    out_token->start = c_start;
                    out_token->length = c_len;
                    out_token->line = cur_line;
                    out_token->column = leading_cols;
                    out_token->content_start = body_start;
                    out_token->content_length = body_len;
                    return GRAM_LEXER_TOKEN;
                }
                advance_to_next_line(lexer);
                continue;
            }

            /* 1c. Process leading indentation */
            lexer->line_indent_processed = 1u;
            int emitted = 0;
            int ind_status = gram_indent_process_line(
                lexer,
                indent_width,
                leading_bytes,
                leading_cols,
                out_token,
                &emitted
            );
            if (emitted) {
                return ind_status;
            }
        }

        /* 2. Scan characters across the current line */
        while (lexer->position < lexer->line_end) {
            char ch = src[lexer->position];
            if (ch == ' ' || ch == '\r' || ch == '\t') {
                lexer->position += 1u;
                lexer->column += 1u;
                continue;
            }

            /* Multiline construct check */
            const GramMultilineEntry *ml = gram_match_multiline(lexer, lexer->position);
            if (ml != NULL) {
                int ml_status = gram_scan_multiline(
                    lexer,
                    ml,
                    lexer->position,
                    lexer->line,
                    lexer->column,
                    0,
                    0,
                    out_token
                );
                if (ml->is_block_comment && !lexer->config.save_comments) {
                    if (ml_status == GRAM_LEXER_FATAL) {
                        return GRAM_LEXER_FATAL;
                    }
                    if (!lexer->has_current_line) {
                        break;
                    }
                    continue;
                }
                return ml_status;
            }

            /* Inline comment check */
            uint32_t cm_len = match_line_comment_at(lexer, lexer->position);
            int is_blk = match_block_comment_at(lexer, lexer->position);
            if (cm_len > 0 || is_blk) {
                if (cm_len == 0) {
                    cm_len = 1u;
                }
                uint32_t c_start = lexer->position;
                uint32_t c_col = lexer->column;
                uint32_t c_len = lexer->line_end - c_start;
                uint32_t body_start = c_start + cm_len;
                uint32_t body_len = lexer->line_end - body_start;
                uint32_t rem_cp = gram_utf8_count_codepoints(src + c_start, c_len);

                lexer->position = lexer->line_end;
                lexer->column = c_col + rem_cp;

                if (lexer->config.save_comments) {
                    memset(out_token, 0, sizeof(GramToken));
                    out_token->kind = GRAM_TOKEN_COMMENT;
                    out_token->flags = GRAM_TOKEN_FLAG_NONE;
                    out_token->start = c_start;
                    out_token->length = c_len;
                    out_token->line = lexer->line;
                    out_token->column = c_col;
                    out_token->content_start = body_start;
                    out_token->content_length = body_len;
                    return GRAM_LEXER_TOKEN;
                }
                break;
            }

            /* Visitor dispatch */
            uint32_t cp = 0;
            uint32_t step = 1u;
            int valid_utf8 = gram_utf8_decode(src, lexer->line_end, lexer->position, &cp, &step);

            /* 2a. Prefixed string visitor */
            if (lexer->config.support_prefixed_strings &&
                valid_utf8 &&
                (cp == 'L' || cp == 'u' || cp == 'U')) {
                uint32_t p = lexer->position;
                uint32_t prefix_len = 0;
                if (p + 1u < lexer->line_end && (src[p + 1u] == '"' || src[p + 1u] == '\'')) {
                    prefix_len = 1u;
                } else if (cp == 'u' && p + 2u < lexer->line_end &&
                           src[p + 1u] == '8' &&
                           (src[p + 2u] == '"' || src[p + 2u] == '\'')) {
                    prefix_len = 2u;
                }
                if (prefix_len > 0) {
                    uint32_t s_byte = lexer->position;
                    uint32_t s_col = lexer->column;
                    uint32_t s_line = lexer->line;
                    lexer->position += prefix_len;
                    lexer->column += prefix_len;

                    const GramMultilineEntry *pml = gram_match_multiline(lexer, lexer->position);
                    if (pml != NULL && !pml->is_block_comment) {
                        return gram_scan_multiline(
                            lexer,
                            pml,
                            s_byte,
                            s_line,
                            s_col,
                            s_byte,
                            prefix_len,
                            out_token
                        );
                    }
                    return gram_scan_string(
                        lexer,
                        src[lexer->position],
                        s_byte,
                        s_line,
                        s_col,
                        s_byte,
                        prefix_len,
                        out_token
                    );
                }
            }

            /* 2b. Standard string visitor */
            if (valid_utf8 && (cp == '"' || cp == '\'')) {
                const GramMultilineEntry *sml = gram_match_multiline(lexer, lexer->position);
                if (sml != NULL && !sml->is_block_comment) {
                    return gram_scan_multiline(
                        lexer,
                        sml,
                        lexer->position,
                        lexer->line,
                        lexer->column,
                        0,
                        0,
                        out_token
                    );
                }
                return gram_scan_string(
                    lexer,
                    (char)cp,
                    lexer->position,
                    lexer->line,
                    lexer->column,
                    0,
                    0,
                    out_token
                );
            }

            /* 2c. Number visitor */
            if (valid_utf8 &&
                ((cp >= '0' && cp <= '9') ||
                 (lexer->config.support_leading_dot_numbers &&
                  cp == '.' &&
                  (lexer->position + 1u) < lexer->line_end &&
                  src[lexer->position + 1u] >= '0' &&
                  src[lexer->position + 1u] <= '9'))) {
                return gram_scan_number(lexer, out_token);
            }

            /* 2d. Word visitor */
            if (valid_utf8 && (gram_unicode_is_alpha(cp) || cp == '_')) {
                return scan_word(lexer, out_token);
            }

            /* 2e. Symbol / fallback visitor */
            return gram_scan_symbol(lexer, out_token);
        }

        if (!lexer->has_current_line) {
            break;
        }

        /* 3. End of physical line: emit NEWLINE if configured */
        if (!lexer->config.ignore_newlines) {
            uint32_t nl_line = lexer->line;
            uint32_t nl_col = lexer->column;
            uint32_t nl_pos = lexer->position;
            advance_to_next_line(lexer);

            memset(out_token, 0, sizeof(GramToken));
            out_token->kind = GRAM_TOKEN_NEWLINE;
            out_token->flags = GRAM_TOKEN_FLAG_NONE;
            out_token->start = nl_pos;
            out_token->length = 0;
            out_token->line = nl_line;
            out_token->column = nl_col;
            out_token->content_start = nl_pos;
            out_token->content_length = 0;
            return GRAM_LEXER_TOKEN;
        }

        advance_to_next_line(lexer);
    }

    /* 4. Flush remaining open indentation levels before EOF */
    if (lexer->config.support_indent && lexer->indent_depth > 1u) {
        lexer->indent_depth -= 1u;
        uint32_t target_indent = lexer->indents[lexer->indent_depth - 1u];

        memset(out_token, 0, sizeof(GramToken));
        out_token->kind = GRAM_TOKEN_DEDENT;
        out_token->flags = GRAM_TOKEN_FLAG_NONE;
        out_token->start = lexer->length;
        out_token->length = 0;
        out_token->line = lexer->line;
        out_token->column = lexer->column;
        out_token->content_start = lexer->length;
        out_token->content_length = target_indent;
        return GRAM_LEXER_TOKEN;
    }

    /* 5. Terminal EOF token */
    lexer->eof_emitted = 1u;
    memset(out_token, 0, sizeof(GramToken));
    out_token->kind = GRAM_TOKEN_EOF;
    out_token->flags = GRAM_TOKEN_FLAG_NONE;
    out_token->start = lexer->length;
    out_token->length = 0;
    out_token->line = lexer->line;
    out_token->column = lexer->column;
    out_token->content_start = lexer->length;
    out_token->content_length = 0;
    return GRAM_LEXER_EOF;
}

uint32_t gram_lexer_scan_all(
    GramLexer *lexer,
    const char *source,
    uint32_t length
) {
    if (lexer == NULL) {
        return 0u;
    }
    gram_lexer_reset(lexer, source, length);
    GramToken tok;
    uint32_t count = 0u;
    for (;;) {
        int st = gram_lexer_next(lexer, &tok);
        count += 1u;
        if (st == GRAM_LEXER_EOF || st == GRAM_LEXER_FATAL) {
            break;
        }
    }
    return count;
}
