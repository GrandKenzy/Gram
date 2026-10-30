"""Regression coverage for C-compatible numeric literal tokenization."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from gram import config
from gram.core.lexer import Lexer, Token, words


class CNumericLiteralTests(unittest.TestCase):
    def tearDown(self) -> None:
        words.clear_all()
        super().tearDown()

    def test_c_suffixes_and_hex_float_keep_numeric_token_kinds(self) -> None:
        with patch.dict(
            config.__dict__,
            {
                "LEXER_COMMENT_TOKEN": "#",
                "LEXER_IGNORE_EMPTY_LINES": True,
                "LEXER_IGNORE_NEWLINES": True,
                "LEXER_ADD_INFO": False,
                "INFO_GENERATE_LOGFILE": False,
                "INFO_GENERATE_LOGFILE_ON_ERROR": False,
                "ERROR_EXIT_ON_ERROR": False,
                "ERROR_HIDE_CONSOLE": True,
            },
        ):
            words.clear_all()
            words.add_keyword("dummy")
            tokens = Lexer("1.0f 0x10ULL 0x1.fp2 .5 42").process()

        self.assertEqual(
            [token.token for token in tokens],
            [Token.DECIMAL, Token.NUMBER, Token.DECIMAL, Token.DECIMAL, Token.NUMBER, Token.EOF],
        )
        self.assertEqual(
            [token.value for token in tokens[:-1]],
            ["1.0f", "0x10ULL", 7.75, 0.5, 42],
        )


if __name__ == "__main__":
    unittest.main()
