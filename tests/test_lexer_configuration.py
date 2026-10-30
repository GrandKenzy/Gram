"""Coverage for configurable lexer spellings, flags, and multiline delimiters."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from gram import config
from gram.core.lexer import (
    Lexer,
    LexerState,
    Token,
    add_multline,
    flags,
    list_multline,
    remove_multline,
    words,
)


class ConfigurableLexerTests(unittest.TestCase):
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
        self.active_lexer = patch.object(LexerState, "_active_instance", None)
        for patcher in (self.settings, self.keywords, self.active_lexer):
            patcher.start()
            self.addCleanup(patcher.stop)
        words.add_keyword("if")

    def test_prefixed_strings_can_be_disabled(self) -> None:
        enabled = Lexer('L"wide"').process()
        self.assertEqual(
            [(token.token, token.value, token.description) for token in enabled],
            [(Token.STRING, "wide", "L"), (Token.EOF, None, "")],
        )

        config.LEXER_SUPPORT_PREFIXED_STRINGS = False
        disabled = Lexer('L"wide"').process()
        self.assertEqual(
            [(token.token, token.value) for token in disabled],
            [(Token.IDENT, "L"), (Token.STRING, "wide"), (Token.EOF, None)],
        )

    def test_leading_dot_numbers_can_be_disabled(self) -> None:
        enabled = Lexer(".5").process()
        self.assertEqual([(token.token, token.value) for token in enabled],
                         [(Token.DECIMAL, 0.5), (Token.EOF, None)])

        config.LEXER_SUPPORT_LEADING_DOT_NUMBERS = False
        disabled = Lexer(".5").process()
        self.assertEqual([(token.token, token.value) for token in disabled],
                         [(Token.DOT, "."), (Token.NUMBER, 5), (Token.EOF, None)])

    def test_quoted_strings_use_flags_instead_of_token_char(self) -> None:
        tokens = Lexer("'x' \"x\" \"text\"").process()
        self.assertEqual([token.token for token in tokens],
                         [Token.STRING, Token.STRING, Token.STRING, Token.EOF])
        self.assertEqual(tokens[0].flags, flags.SIMPLE_QUOTE | flags.CHAR)
        self.assertEqual(tokens[1].flags, flags.SIMPLE_QUOTE | flags.CHAR)
        self.assertEqual(tokens[2].flags, flags.SIMPLE_QUOTE)
        self.assertFalse(hasattr(Token, "CHAR"))

    def test_multiline_registry_is_extensible_and_list_is_detached(self) -> None:
        original = list_multline()
        add_multline("<<<", ">>>")
        self.addCleanup(remove_multline, "<<<")

        registered = list_multline()
        self.assertEqual(registered["<<<"], ">>>")
        registered["<<<"] = "changed"
        self.assertEqual(list_multline()["<<<"], ">>>")

        tokens = Lexer("before <<<body\ncontinues>>> after").process()
        self.assertEqual(
            [(token.token, token.value) for token in tokens],
            [
                (Token.IDENT, "before"),
                (Token.STRING, "body\ncontinues"),
                (Token.IDENT, "after"),
                (Token.EOF, None),
            ],
        )
        self.assertEqual(list_multline()['"""'], '"""')
        self.assertEqual(
            {key: value for key, value in original.items() if key in list_multline()},
            {key: value for key, value in list_multline().items() if key in original},
        )

    def test_multiline_strings_preserve_escape_decoding(self) -> None:
        tokens = Lexer(r'"""line\n\u0042"""').process()
        self.assertEqual(tokens[0].token, Token.STRING)
        self.assertEqual(tokens[0].value, "line\nB")

    def test_configured_c_block_comment_uses_multiline_scanner(self) -> None:
        config.LEXER_BLOCK_COMMENT_TOKEN = "/*"
        tokens = Lexer("value /* hidden\ncomment */ + next").process()
        self.assertEqual(
            [(token.token, token.value) for token in tokens],
            [
                (Token.IDENT, "value"),
                (Token.PLUS, "+"),
                (Token.IDENT, "next"),
                (Token.EOF, None),
            ],
        )
        second_lexer = Lexer("value /* hidden\ncomment */ + next")
        second_lexer.process()
        self.assertEqual([comment.value for comment in second_lexer.comments],
                         [" hidden\ncomment "])

    def test_boolean_and_null_spellings_are_configurable(self) -> None:
        config.TOKEN_BOOL_TRUE = "verdadero"
        config.TOKEN_BOOL_FALSE = "falso"
        config.TOKEN_NULL = "nulo"

        tokens = Lexer("VERDADERO falso nulo true").process()
        self.assertEqual(
            [(token.token, token.value) for token in tokens],
            [
                (Token.BOOL, True),
                (Token.BOOL, False),
                (Token.NULL, None),
                (Token.IDENT, "true"),
                (Token.EOF, None),
            ],
        )

    def test_indentation_can_be_disabled(self) -> None:
        config.SUPPORT_INDENT = False
        tokens = Lexer("if\n  value\nnext").process()
        self.assertEqual(
            [token.token for token in tokens],
            [Token.KEYWORD, Token.IDENT, Token.IDENT, Token.EOF],
        )


if __name__ == "__main__":
    unittest.main()
