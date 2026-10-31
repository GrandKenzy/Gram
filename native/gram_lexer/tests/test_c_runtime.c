#include "../include/gram_lexer.h"
#include <stdio.h>
#include <string.h>
#include <assert.h>

static const GramKeywordEntry TEST_KEYWORDS[] = {
    { "def",    3u, 0u, 0u, 1u },
    { "if",     2u, 1u, 1u, 1u },
    { "return", 6u, 2u, 2u, 1u }
};

static const GramGroupEntry TEST_GROUPS[] = {
    { "control", 7u, 0u, 0u, 3u }
};

static const uint32_t TEST_GROUP_MEMBERSHIPS[] = { 0u, 0u, 0u };

static const GramSymbolEntry TEST_SYMBOLS[] = {
    { "...", 3u, GRAM_TOKEN_THREE_DOTS, 3u },
    { ">>=", 3u, GRAM_TOKEN_SHR_ASSIGN, 3u },
    { "<<=", 3u, GRAM_TOKEN_SHL_ASSIGN, 3u },
    { "<=>", 3u, GRAM_TOKEN_CUSTOM_BASE + 1u, 3u },
    { "==",  2u, GRAM_TOKEN_EQUAL,      2u },
    { "!=",  2u, GRAM_TOKEN_NOT_EQUAL,  2u },
    { "->",  2u, GRAM_TOKEN_ARROW,      2u },
    { ">>",  2u, GRAM_TOKEN_SHR,        2u },
    { "+",   1u, GRAM_TOKEN_PLUS,       1u },
    { "-",   1u, GRAM_TOKEN_MINUS,      1u },
    { "*",   1u, GRAM_TOKEN_STAR,       1u },
    { "/",   1u, GRAM_TOKEN_SLASH,      1u },
    { "=",   1u, GRAM_TOKEN_ASSIGN,     1u },
    { ">",   1u, GRAM_TOKEN_GREATER,    1u },
    { "<",   1u, GRAM_TOKEN_LESS,       1u },
    { "(",   1u, GRAM_TOKEN_LPAREN,     1u },
    { ")",   1u, GRAM_TOKEN_RPAREN,     1u },
    { ":",   1u, GRAM_TOKEN_COLON,      1u },
    { ".",   1u, GRAM_TOKEN_DOT,        1u },
    { "#",   1u, GRAM_TOKEN_HASH,       1u }
};

static const GramMultilineEntry TEST_MULTILINE[] = {
    { "\"\"\"", 3u, 3u, "\"\"\"", 3u, 3u, GRAM_TOKEN_STRING,  1u, 0u },
    { "'''",    3u, 3u, "'''",    3u, 3u, GRAM_TOKEN_STRING,  1u, 0u },
    { "/*",     2u, 2u, "*/",     2u, 2u, GRAM_TOKEN_COMMENT, 0u, 1u }
};

static GramLexerTables make_test_tables(void) {
    GramLexerTables t;
    memset(&t, 0, sizeof(t));
    t.keywords = TEST_KEYWORDS;
    t.keyword_count = 3u;
    t.groups = TEST_GROUPS;
    t.group_count = 1u;
    t.group_memberships = TEST_GROUP_MEMBERSHIPS;
    t.group_membership_count = 3u;
    t.symbols = TEST_SYMBOLS;
    t.symbol_count = (uint32_t)(sizeof(TEST_SYMBOLS) / sizeof(TEST_SYMBOLS[0]));
    t.multiline = TEST_MULTILINE;
    t.multiline_count = 3u;
    t.line_comment = "#";
    t.line_comment_length = 1u;
    t.block_comment_open = "/*";
    t.block_comment_open_length = 2u;
    t.block_comment_close = "*/";
    t.block_comment_close_length = 2u;
    t.bool_true = "true";
    t.bool_true_length = 4u;
    t.bool_false = "false";
    t.bool_false_length = 5u;
    t.null_literal = "null";
    t.null_literal_length = 4u;
    return t;
}

static void user_sink_counter(void *ctx, const GramDiagnostic *diag) {
    int *counter = (int *)ctx;
    (void)diag;
    *counter += 1;
}

static void test_diagnostics_lite(void) {
    GramDiagnostic storage[4];
    char arena[256];
    GramDiagBuffer buf;
    int callback_hits = 0;

    gram_diag_buffer_init(&buf, storage, 4u, GRAM_ERROR_POLICY_RECOVER);
    gram_diag_buffer_set_message_arena(&buf, arena, sizeof(arena));
    gram_diag_buffer_set_max_limit(&buf, 2u);

    GramDiagSink user_cb = { &callback_hits, user_sink_counter };
    gram_diag_buffer_set_user_sink(&buf, user_cb);

    GramDiagSeverityOverride overrides[1] = {
        { GRAM_DIAG_CODE_CUSTOM_BASE + 7u, GRAM_DIAG_WARN }
    };
    gram_diag_buffer_set_overrides(&buf, overrides, 1u);

    GramDiagSink sink = gram_diag_buffer_as_sink(&buf);

    gram_diag_emit(&sink, GRAM_DIAG_CODE_CUSTOM_BASE + 7u, GRAM_DIAG_ERROR, 0u, 3u, 1u, 0u, "custom one", 10u);
    gram_diag_emit(&sink, GRAM_DIAG_CODE_UNEXPECTED_CHARACTER, GRAM_DIAG_ERROR, 4u, 5u, 1u, 4u, "bad char", 8u);
    gram_diag_emit(&sink, GRAM_DIAG_CODE_INVALID_NUMBER, GRAM_DIAG_ERROR, 6u, 9u, 1u, 6u, "dropped", 7u);

    assert(buf.count == 2u);
    assert(buf.total_emitted == 3u);
    assert(buf.dropped_count == 1u);
    assert(callback_hits == 2);
    assert(buf.items[0].severity == GRAM_DIAG_WARN);
    assert(strcmp(buf.items[0].message, "custom one") == 0);
    assert(buf.items[1].severity == GRAM_DIAG_ERROR);
    assert(buf.halted == 0u);
}

static void test_tokens_and_maximal_munch(void) {
    GramLexerTables tables = make_test_tables();
    GramLexerConfig cfg = gram_lexer_default_config();
    GramLexer lexer;
    GramToken tok;

    const char *src = "def x = 0x10 + .5 >>= ... <=>";
    gram_lexer_init(&lexer, src, (uint32_t)strlen(src), &cfg, &tables, gram_diag_null_sink(), NULL);

    assert(gram_lexer_next(&lexer, &tok) == GRAM_LEXER_TOKEN && tok.kind == GRAM_TOKEN_KEYWORD);
    assert(gram_lexer_next(&lexer, &tok) == GRAM_LEXER_TOKEN && tok.kind == GRAM_TOKEN_IDENT);
    assert(gram_lexer_next(&lexer, &tok) == GRAM_LEXER_TOKEN && tok.kind == GRAM_TOKEN_ASSIGN);
    assert(gram_lexer_next(&lexer, &tok) == GRAM_LEXER_TOKEN && tok.kind == GRAM_TOKEN_NUMBER);
    assert(gram_lexer_next(&lexer, &tok) == GRAM_LEXER_TOKEN && tok.kind == GRAM_TOKEN_PLUS);
    assert(gram_lexer_next(&lexer, &tok) == GRAM_LEXER_TOKEN && tok.kind == GRAM_TOKEN_DECIMAL);
    assert(gram_lexer_next(&lexer, &tok) == GRAM_LEXER_TOKEN && tok.kind == GRAM_TOKEN_SHR_ASSIGN);
    assert(gram_lexer_next(&lexer, &tok) == GRAM_LEXER_TOKEN && tok.kind == GRAM_TOKEN_THREE_DOTS);
    assert(gram_lexer_next(&lexer, &tok) == GRAM_LEXER_TOKEN && tok.kind == GRAM_TOKEN_CUSTOM_BASE + 1u);
    assert(gram_lexer_next(&lexer, &tok) == GRAM_LEXER_EOF && tok.kind == GRAM_TOKEN_EOF);
}

static void test_strings_and_escapes(void) {
    GramLexerTables tables = make_test_tables();
    GramLexerConfig cfg = gram_lexer_default_config();
    GramLexer lexer;
    GramToken tok;
    char decoded[128];
    uint32_t dec_len = 0;
    uint32_t dec_cp = 0;

    const char *src = "'a' \"\\u0041\" u8\"hello\\nworld\" \"\"\"line1\r\nline2\"\"\"";
    gram_lexer_init(&lexer, src, (uint32_t)strlen(src), &cfg, &tables, gram_diag_null_sink(), NULL);

    /* 'a' -> SIMPLE_QUOTE | CHAR */
    assert(gram_lexer_next(&lexer, &tok) == GRAM_LEXER_TOKEN);
    assert(tok.kind == GRAM_TOKEN_STRING);
    assert((tok.flags & GRAM_TOKEN_PUBLIC_FLAGS_MASK) == (GRAM_TOKEN_FLAG_SIMPLE_QUOTE | GRAM_TOKEN_FLAG_CHAR));

    /* "\u0041" -> decoded is "A" (1 codepoint), so SIMPLE_QUOTE | CHAR */
    assert(gram_lexer_next(&lexer, &tok) == GRAM_LEXER_TOKEN);
    assert(tok.kind == GRAM_TOKEN_STRING);
    assert((tok.flags & GRAM_TOKEN_PUBLIC_FLAGS_MASK) == (GRAM_TOKEN_FLAG_SIMPLE_QUOTE | GRAM_TOKEN_FLAG_CHAR));
    assert(gram_lexer_decode_string(&lexer, &tok, decoded, sizeof(decoded), &dec_len, &dec_cp) == 0);
    assert(dec_len == 1u && decoded[0] == 'A');

    /* u8"hello\nworld" -> prefix="u8", SIMPLE_QUOTE */
    assert(gram_lexer_next(&lexer, &tok) == GRAM_LEXER_TOKEN);
    assert(tok.kind == GRAM_TOKEN_STRING);
    assert(tok.prefix_length == 2u && memcmp(src + tok.prefix_start, "u8", 2) == 0);
    assert(gram_lexer_decode_string(&lexer, &tok, decoded, sizeof(decoded), &dec_len, &dec_cp) == 0);
    assert(dec_len == 11u && memcmp(decoded, "hello\nworld", 11) == 0);

    /* """line1\r\nline2""" -> multiline normalized to "line1\nline2", flags=NONE */
    assert(gram_lexer_next(&lexer, &tok) == GRAM_LEXER_TOKEN);
    assert(tok.kind == GRAM_TOKEN_STRING);
    assert((tok.flags & GRAM_TOKEN_PUBLIC_FLAGS_MASK) == GRAM_TOKEN_FLAG_NONE);
    assert(gram_lexer_decode_string(&lexer, &tok, decoded, sizeof(decoded), &dec_len, &dec_cp) == 0);
    assert(dec_len == 11u && memcmp(decoded, "line1\nline2", 11) == 0);
}

static void test_indentation_and_errors(void) {
    GramLexerTables tables = make_test_tables();
    GramLexerConfig cfg = gram_lexer_default_config();
    GramDiagnostic diags[8];
    GramDiagBuffer dbuf;
    gram_diag_buffer_init(&dbuf, diags, 8u, GRAM_ERROR_POLICY_RECOVER);

    const char *src =
        "if true:\n"
        "    # comment only line\n"
        "    if false:\n"
        "        return 1\n"
        "  x = @\n";

    GramLexer lexer;
    GramToken tok;
    gram_lexer_init(&lexer, src, (uint32_t)strlen(src), &cfg, &tables, gram_diag_buffer_as_sink(&dbuf), NULL);

    /* Line 1: if true : */
    assert(gram_lexer_next(&lexer, &tok) == GRAM_LEXER_TOKEN && tok.kind == GRAM_TOKEN_KEYWORD);
    assert(gram_lexer_next(&lexer, &tok) == GRAM_LEXER_TOKEN && tok.kind == GRAM_TOKEN_BOOL);
    assert(gram_lexer_next(&lexer, &tok) == GRAM_LEXER_TOKEN && tok.kind == GRAM_TOKEN_COLON);

    /* Line 3: INDENT(4) if false : */
    assert(gram_lexer_next(&lexer, &tok) == GRAM_LEXER_TOKEN && tok.kind == GRAM_TOKEN_INDENT && tok.content_length == 4u);
    assert(gram_lexer_next(&lexer, &tok) == GRAM_LEXER_TOKEN && tok.kind == GRAM_TOKEN_KEYWORD);
    assert(gram_lexer_next(&lexer, &tok) == GRAM_LEXER_TOKEN && tok.kind == GRAM_TOKEN_BOOL);
    assert(gram_lexer_next(&lexer, &tok) == GRAM_LEXER_TOKEN && tok.kind == GRAM_TOKEN_COLON);

    /* Line 4: INDENT(8) return 1 */
    assert(gram_lexer_next(&lexer, &tok) == GRAM_LEXER_TOKEN && tok.kind == GRAM_TOKEN_INDENT && tok.content_length == 8u);
    assert(gram_lexer_next(&lexer, &tok) == GRAM_LEXER_TOKEN && tok.kind == GRAM_TOKEN_KEYWORD);
    assert(gram_lexer_next(&lexer, &tok) == GRAM_LEXER_TOKEN && tok.kind == GRAM_TOKEN_NUMBER);

    /* Line 5: indent=2 pops 8->4 and 4->0, emits DEDENT(4), DEDENT(0), records INDENTATION_MISMATCH, then scans x = @ */
    assert(gram_lexer_next(&lexer, &tok) == GRAM_LEXER_TOKEN && tok.kind == GRAM_TOKEN_DEDENT && tok.content_length == 4u);
    assert(gram_lexer_next(&lexer, &tok) == GRAM_LEXER_TOKEN && tok.kind == GRAM_TOKEN_DEDENT && tok.content_length == 0u);
    assert(gram_lexer_next(&lexer, &tok) == GRAM_LEXER_TOKEN && tok.kind == GRAM_TOKEN_IDENT);
    assert(gram_lexer_next(&lexer, &tok) == GRAM_LEXER_TOKEN && tok.kind == GRAM_TOKEN_ASSIGN);
    assert(gram_lexer_next(&lexer, &tok) == GRAM_LEXER_ERROR && tok.kind == GRAM_TOKEN_ERROR);
    assert(gram_lexer_next(&lexer, &tok) == GRAM_LEXER_EOF && tok.kind == GRAM_TOKEN_EOF);

    assert(dbuf.count == 2u);
    assert(dbuf.items[0].code == GRAM_DIAG_CODE_INDENTATION_MISMATCH);
    assert(dbuf.items[1].code == GRAM_DIAG_CODE_UNEXPECTED_CHARACTER);
}

static void test_utf8_and_policies_and_groups(void) {
    GramLexerTables tables = make_test_tables();
    GramLexerConfig cfg = gram_lexer_default_config();
    GramDiagnostic diags[8];
    GramDiagBuffer dbuf;

    /* 1. Word-group lookup */
    const GramKeywordEntry *kw_def = gram_tables_find_keyword(&tables, "def", 3u);
    const GramGroupEntry *grp_ctrl = gram_tables_find_group(&tables, "control", 7u);
    assert(kw_def != NULL && grp_ctrl != NULL);
    assert(gram_tables_keyword_in_group(&tables, kw_def, grp_ctrl->group_id) == 1);
    assert(gram_tables_keyword_in_group(&tables, kw_def, 99u) == 0);

    /* 2. Invalid UTF-8 sequences: overlong 0xC0 0xAF and surrogate 0xED 0xA0 0x80 */
    const char bad_utf8[] = { 'x', ' ', (char)0xC0, (char)0xAF, ' ', (char)0xED, (char)0xA0, (char)0x80, '\0' };
    gram_diag_buffer_init(&dbuf, diags, 8u, GRAM_ERROR_POLICY_RECOVER);
    GramLexer lexer;
    GramToken tok;
    gram_lexer_init(&lexer, bad_utf8, 8u, &cfg, &tables, gram_diag_buffer_as_sink(&dbuf), NULL);

    assert(gram_lexer_next(&lexer, &tok) == GRAM_LEXER_TOKEN && tok.kind == GRAM_TOKEN_IDENT);
    assert(gram_lexer_next(&lexer, &tok) == GRAM_LEXER_ERROR && tok.kind == GRAM_TOKEN_ERROR);
    assert(dbuf.count >= 1u && dbuf.items[0].code == GRAM_DIAG_CODE_INVALID_UTF8);

    /* 3. Reentrancy with gram_lexer_reset and STOP_ON_ERROR */
    cfg.error_policy = (uint8_t)GRAM_ERROR_POLICY_STOP_ON_ERROR;
    gram_diag_buffer_init(&dbuf, diags, 8u, GRAM_ERROR_POLICY_STOP_ON_ERROR);
    lexer.config = cfg;
    lexer.diagnostics = gram_diag_buffer_as_sink(&dbuf);
    gram_lexer_reset(&lexer, "@ + 1", 5u);
    assert(gram_lexer_next(&lexer, &tok) == GRAM_LEXER_FATAL);
    assert(dbuf.halted == 1u);

    /* 4. Mixed and tab indentation modes */
    cfg = gram_lexer_default_config();
    cfg.indentation_mode = (uint8_t)GRAM_INDENT_MIXED;
    cfg.tab_width = 4u;
    lexer.config = cfg;
    lexer.diagnostics = gram_diag_null_sink();
    const char *mixed_src = "if true:\n  \treturn 1\n";
    gram_lexer_reset(&lexer, mixed_src, (uint32_t)strlen(mixed_src));
    assert(gram_lexer_next(&lexer, &tok) == GRAM_LEXER_TOKEN && tok.kind == GRAM_TOKEN_KEYWORD);
    assert(gram_lexer_next(&lexer, &tok) == GRAM_LEXER_TOKEN && tok.kind == GRAM_TOKEN_BOOL);
    assert(gram_lexer_next(&lexer, &tok) == GRAM_LEXER_TOKEN && tok.kind == GRAM_TOKEN_COLON);
    /* 2 spaces + 1 tab (tab_width=4) advances to tab stop 4 */
    assert(gram_lexer_next(&lexer, &tok) == GRAM_LEXER_TOKEN && tok.kind == GRAM_TOKEN_INDENT && tok.content_length == 4u);
}

int main(void) {
    test_diagnostics_lite();
    test_tokens_and_maximal_munch();
    test_strings_and_escapes();
    test_indentation_and_errors();
    test_utf8_and_policies_and_groups();
    printf("All C runtime unit tests passed successfully.\n");
    return 0;
}
