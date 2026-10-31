"""Regression coverage for the resolved lexer pending items."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from gram import config, errors
from gram.core.lexer import Lexer, LexerState, Token, TokenType, tokens, words
from gram.sessions import Session


class PendingLexerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = patch.dict(
            config.__dict__,
            {
                "LEXER_COMMENT_TOKEN": "#",
                "LEXER_BLOCK_COMMENT_TOKEN": None,
                "LEXER_SUPPORT_BLOCK_COMMENTS": True,
                "LEXER_SUPPORT_DOCSTRINGS": True,
                "LEXER_SUPPORT_PREFIXED_STRINGS": True,
                "LEXER_SUPPORT_LEADING_DOT_NUMBERS": True,
                "LEXER_TAB_WIDTH": 4,
                "LEXER_INDENT_STYLE": "spaces",
                "TOKEN_BOOL_TRUE": "true",
                "TOKEN_BOOL_FALSE": "false",
                "TOKEN_NULL": "null",
                "SUPPORT_INDENT": True,
                "LEXER_IGNORE_EMPTY_LINES": True,
                "LEXER_IGNORE_NEWLINES": True,
                "LEXER_SAVE_COMMENTS": True,
                "LEXER_ADD_INFO": False,
                "INFO_GENERATE_LOGFILE": False,
                "INFO_GENERATE_LOGFILE_ON_ERROR": False,
                "ERROR_EXIT_ON_ERROR": False,
                "ERROR_HIDE_CONSOLE": True,
            },
        )
        self.keywords = patch.dict(words.MAP_KEYWORDS, clear=True)
        self.groups = patch.dict(words._GLOBAL_GROUPS, clear=True)
        self.active_lexer = patch.object(LexerState, "_active_instance", None)
        for patcher in (self.settings, self.keywords, self.groups, self.active_lexer):
            patcher.start()
            self.addCleanup(patcher.stop)
        words.add_keyword("if")

    def test_info_disabled_skips_structural_lexer_nodes(self) -> None:
        lexer = Lexer("if value")
        lexer.process()

        self.assertFalse(lexer.telemetry_enabled)
        self.assertIsNone(lexer.info_node)
        self.assertEqual(lexer._targets, [])
        self.assertEqual(lexer.stack.main.nodes, [])

    def test_fail_uses_the_same_exit_policy_as_report_error(self) -> None:
        lexer = Lexer("if")

        lexer.fail("DeferredFailure", errors.LEXER_INDENTATION_MISMATCH, "hint")

        self.assertEqual(len(lexer._errors), 1)
        self.assertEqual(lexer._errors[0].name, "DeferredFailure")

    def test_tabs_and_mixed_indentation_use_session_configuration(self) -> None:
        config.LEXER_INDENT_STYLE = "tabs"
        config.LEXER_TAB_WIDTH = 2
        tab_tokens = Lexer("if\n\tvalue\nnext").process()
        self.assertEqual(
            [token.token for token in tab_tokens],
            [Token.KEYWORD, Token.INDENT, Token.IDENT, Token.DEDENT, Token.IDENT, Token.EOF],
        )
        self.assertEqual(tab_tokens[1].value, 2)

        config.LEXER_INDENT_STYLE = "mixed"
        mixed_tokens = Lexer("if\n \tvalue\nnext").process()
        self.assertEqual(mixed_tokens[1].token, Token.INDENT)
        self.assertEqual(mixed_tokens[1].value, 2)

    def test_session_configuration_controls_indentation_without_global_mutation(self) -> None:
        session = Session("session-indent", "Many")
        session.init()
        session.add_keyword("if")
        session.migrate()
        session.config["LEXER_INDENT_STYLE"] = "tabs"
        session.config["LEXER_TAB_WIDTH"] = 3

        result = session.tokenize("if\n\tvalue\nnext", "session-indent.gram")

        self.assertEqual(result[1].token, Token.INDENT)
        self.assertEqual(result[1].value, 3)
        self.assertEqual(config.LEXER_INDENT_STYLE, "spaces")

    def test_session_preserves_symbol_indexes_across_load_and_migrate(self) -> None:
        original = tuple(tokens.MAP_SYMBOLS.items())
        session = Session("symbol-indexes", "Many")
        try:
            session.init()
            tokens.insert_symbol("@@", Token.AT)
            session.migrate()

            session.load()
            self.assertEqual(tokens.MAP_SYMBOLS[Token.AT], "@@")
            self.assertIn("@@", tokens.get_sorted_symbols())
            self.assertEqual(session.symbols[Token.AT], "@@")
            self.assertIn("@@", session.symbol_order)

            session.migrate()
            self.assertNotIn("@@", tokens.MAP_SYMBOLS)
            self.assertNotIn("@@", tokens.get_sorted_symbols())
        finally:
            tokens.MAP_SYMBOLS.clear()
            tokens.MAP_SYMBOLS.update(original)
            tokens._sync_symbol_indexes()

    def test_clearing_a_group_clears_keyword_back_references(self) -> None:
        keyword = words.add_keyword("type")
        group = words.add_group("types", [keyword])

        self.assertTrue(group.contains("type"))
        self.assertFalse(group.contains("TYPE"))
        self.assertEqual(keyword.group, "types")

        group.clear()

        self.assertEqual(group.values, [])
        self.assertIsNone(keyword.group)

    def test_token_formatter_len_is_payload_length(self) -> None:
        token = TokenType(Token.IDENT, "hello", line=2, col=3)

        self.assertEqual(token.formatter("$len/$long/$line/$col"), "5/8/3/3")


if __name__ == "__main__":
    unittest.main()
