"""Regression coverage for multiline literals and configurable comments."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from gram import config
from gram.core.lexer import Lexer, LexerState, Token, flags, words


class LexerRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        settings = patch.dict(config.__dict__, {
            "LEXER_COMMENT_TOKEN": "#",
                "LEXER_BLOCK_COMMENT_TOKEN": None,
                "LEXER_SUPPORT_BLOCK_COMMENTS": True,
                "SUPPORT_TRIPLE_DOT": True,
            "LEXER_IGNORE_EMPTY_LINES": True,
            "LEXER_IGNORE_NEWLINES": True,
            "LEXER_SAVE_COMMENTS": True,
            "LEXER_SUPPORT_DOCSTRINGS": True,
                "LEXER_SUPPORT_PREFIXED_STRINGS": True,
                "LEXER_SUPPORT_LEADING_DOT_NUMBERS": True,
                "TOKEN_BOOL_TRUE": "true",
                "TOKEN_BOOL_FALSE": "false",
                "TOKEN_NULL": "null",
                "SUPPORT_INDENT": True,
            "LEXER_ADD_INFO": False,
            "INFO_GENERATE_LOGFILE": False,
            "INFO_GENERATE_LOGFILE_ON_ERROR": False,
            "ERROR_EXIT_ON_ERROR": False,
            "ERROR_HIDE_CONSOLE": True,
        })
        keywords = patch.dict(words.MAP_KEYWORDS, clear=True)
        active_lexer = patch.object(LexerState, "_active_instance", None)
        for patcher in (settings, keywords, active_lexer):
            patcher.start()
            self.addCleanup(patcher.stop)
        words.add_keyword("if")

    def test_multiline_docstring_preserves_suffix_on_longer_closing_line(self) -> None:
        for quote in ('"""', "'''"):
            with self.subTest(quote=quote):
                tokens = Lexer(f"{quote}\nbody{quote} + 1\nnext").process()
                self.assertEqual(
                    [(t.token, t.value) for t in tokens],
                    [(Token.STRING, "\nbody"), (Token.PLUS, "+"),
                     (Token.NUMBER, 1), (Token.IDENT, "next"), (Token.EOF, None)],
                )
                self.assertEqual((tokens[1].line, tokens[1].col), (2, 8))

    def test_multiline_docstring_newline_uses_shorter_closing_line(self) -> None:
        config.__dict__["LEXER_IGNORE_NEWLINES"] = False
        tokens = Lexer('"""a much longer opening line\n""" + 1\nnext').process()
        self.assertEqual(
            [(t.token, t.line, t.col) for t in tokens],
            [(Token.STRING, 1, 0), (Token.PLUS, 2, 4),
             (Token.NUMBER, 2, 6), (Token.NEWLINE, 2, 7),
             (Token.IDENT, 3, 0), (Token.NEWLINE, 3, 4), (Token.EOF, 4, 0)],
        )

    def test_multiline_docstring_preserves_following_indented_statements(self) -> None:
        tokens = Lexer('if\n  """\n  body""" + 1\n  value\nnext').process()
        self.assertEqual(
            [t.token for t in tokens],
            [Token.KEYWORD, Token.INDENT, Token.STRING, Token.PLUS,
             Token.NUMBER, Token.IDENT, Token.DEDENT, Token.IDENT, Token.EOF],
        )
        self.assertEqual((tokens[3].line, tokens[3].col), (3, 10))

    def test_multichar_comments_preserve_single_slash_and_ignore_comment_indent(self) -> None:
        config.__dict__["LEXER_COMMENT_TOKEN"] = "//"
        for save_comments in (True, False):
            with self.subTest(save_comments=save_comments):
                config.__dict__["LEXER_SAVE_COMMENTS"] = save_comments
                lexer = Lexer("  // header\nvalue / 2 // inline\nnext")
                tokens = lexer.process()
                self.assertEqual(
                    [(t.token, t.value) for t in tokens],
                    [(Token.IDENT, "value"), (Token.SLASH, "/"),
                     (Token.NUMBER, 2), (Token.IDENT, "next"), (Token.EOF, None)],
                )
                self.assertEqual(
                    [(t.value, t.line, t.col) for t in lexer.comments],
                    [(" header", 1, 2), (" inline", 2, 10)] if save_comments else [],
                )

    def test_three_character_comment_marker_is_removed_completely(self) -> None:
        config.__dict__["LEXER_COMMENT_TOKEN"] = "<->"
        lexer = Lexer("value <-> content\nnext")
        self.assertEqual([t.value for t in lexer.process()], ["value", "next", None])
        self.assertEqual([t.value for t in lexer.comments], [" content"])

    def test_default_comment_marker_is_unchanged(self) -> None:
        lexer = Lexer("# header\nvalue # inline\nnext")
        self.assertEqual([t.value for t in lexer.process()], ["value", "next", None])
        self.assertEqual([t.value for t in lexer.comments], [" header", " inline"])

    def test_multiline_docstring_suffix_can_contain_multichar_comment(self) -> None:
        config.__dict__["LEXER_COMMENT_TOKEN"] = "//"
        lexer = Lexer('"""\nbody""" + 1 // trailing\nnext')
        self.assertEqual(
            [t.token for t in lexer.process()],
            [Token.STRING, Token.PLUS, Token.NUMBER, Token.IDENT, Token.EOF],
        )
        self.assertEqual([(t.value, t.line, t.col) for t in lexer.comments],
                         [(" trailing", 2, 12)])

    def test_token_comment_marker_recognizes_and_removes_complete_symbol(self) -> None:
        lexer = Lexer("value // content\nnext")
        lexer.comment_token = Token.FLOOR_DIV
        self.assertEqual([t.value for t in lexer.process()], ["value", "next", None])
        self.assertEqual([t.value for t in lexer.comments], [" content"])

    def test_mixed_comment_markers_keep_complete_delimiters_out_of_content(self) -> None:
        lexer = Lexer("value // first\nnext ## second\nlast")
        lexer.comment_token = (Token.FLOOR_DIV, "##")
        self.assertEqual([t.value for t in lexer.process()],
                         ["value", "next", "last", None])
        self.assertEqual([t.value for t in lexer.comments], [" first", " second"])

    def test_c_character_and_prefixed_string_literals(self) -> None:
        tokens = Lexer("'x' L'ñ' u\"wide\" U\"unicode\" u8\"utf8\"").process()

        self.assertEqual(
            [token.token for token in tokens],
            [Token.STRING, Token.STRING, Token.STRING, Token.STRING, Token.STRING, Token.EOF],
        )
        self.assertEqual(
            [token.value for token in tokens[:-1]],
            ["x", "ñ", "wide", "unicode", "utf8"],
        )
        self.assertEqual(
            [token.description for token in tokens[:-1]],
            ["", "L", "u", "U", "u8"],
        )
        self.assertTrue(tokens[0].flags & flags.CHAR)
        self.assertTrue(tokens[0].flags & flags.SIMPLE_QUOTE)
        self.assertTrue(tokens[1].flags & flags.CHAR)
        self.assertTrue(tokens[1].flags & flags.SIMPLE_QUOTE)

    def test_multiline_c_block_comments_preserve_following_tokens(self) -> None:
        config.__dict__["LEXER_BLOCK_COMMENT_TOKEN"] = "/*"
        lexer = Lexer("value /* hidden\ncomment */ + next")

        tokens = lexer.process()

        self.assertEqual(
            [(token.token, token.value) for token in tokens],
            [
                (Token.IDENT, "value"),
                (Token.PLUS, "+"),
                (Token.IDENT, "next"),
                (Token.EOF, None),
            ],
        )

    def test_block_comments_can_be_disabled_independently(self) -> None:
        config.__dict__["LEXER_BLOCK_COMMENT_TOKEN"] = "/*"
        config.__dict__["LEXER_SUPPORT_BLOCK_COMMENTS"] = False
        lexer = Lexer("value /* hidden */")

        tokens = lexer.process()

        self.assertEqual(
            [token.token for token in tokens],
            [Token.IDENT, Token.SLASH, Token.STAR, Token.IDENT, Token.STAR, Token.SLASH, Token.EOF],
        )

    def test_triple_dot_support_is_switchable(self) -> None:
        enabled = Lexer("...").process()
        self.assertEqual(
            [token.token for token in enabled],
            [Token.THREE_DOTS, Token.EOF],
        )

        config.__dict__["SUPPORT_TRIPLE_DOT"] = False
        disabled = Lexer("...").process()
        self.assertEqual(
            [token.token for token in disabled],
            [Token.DOT, Token.DOT, Token.DOT, Token.EOF],
        )


if __name__ == "__main__":
    unittest.main()
