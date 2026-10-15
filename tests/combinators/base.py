"""
Test Infrastructure and Base Test Case for Combinator Testing.
"""
from __future__ import annotations

import unittest
from typing import Any

from gram import config, errors, lexer, parser
from gram.core.ast.analyzer import ASTAnalyzer
from gram.core.combinators.alternative import Alt
from gram.core.combinators.base import Combinator, RuleItem
from gram.core.combinators.reference import Ref
from gram.core.lexer import words
from gram.core.lexer.tokens import Token, TokenType
from gram.utilities import Diagnostics


class DummyEntryRule(RuleItem):
    """Fallback dummy rule for creating ASTAnalyzer instances."""
    pass


class DummyEntrypoint(RuleItem):
    """Valid entrypoint rule configured with Alt(Ref(DummyEntryRule))."""
    entrypoint = Alt(Ref(DummyEntryRule))


class CombinatorTestCase(unittest.TestCase):
    """
    Standard test fixture for testing Gram combinators.
    Configures safe error handling, registers base keywords, and exposes
    fluent helpers to parse tokens and assert result shapes.
    """

    def setUp(self) -> None:
        super().setUp()
        # Save previous config state
        self._prev_exit = config.ERROR_EXIT_ON_ERROR
        self._prev_hide_console = config.ERROR_HIDE_CONSOLE
        self._prev_log_hide = config.LOG_HIDE_CONSOLE
        self._prev_info_init = config.INFO_INIT

        # Mute console output and prevent sys.exit() during negative tests
        config.ERROR_EXIT_ON_ERROR = False
        config.ERROR_HIDE_CONSOLE = True
        config.LOG_HIDE_CONSOLE = True
        config.INFO_INIT = False

        # Clear existing keywords/groups and register clean test baseline
        words.clear_all()
        lexer.add_group("types")
        lexer.add_keyword("int", group="types")
        lexer.add_keyword("str", group="types")
        lexer.add_keyword("bool", group="types")
        lexer.add_group("control")
        lexer.add_keyword("return", group="control")
        lexer.add_keyword("if", group="control")
        lexer.add_keyword("else", group="control")
        lexer.add_keyword("block")
        lexer.add_keyword("end")

    def tearDown(self) -> None:
        # Restore configuration
        config.ERROR_EXIT_ON_ERROR = self._prev_exit
        config.ERROR_HIDE_CONSOLE = self._prev_hide_console
        config.LOG_HIDE_CONSOLE = self._prev_log_hide
        config.INFO_INIT = self._prev_info_init
        words.clear_all()
        super().tearDown()

    def tokenize(self, code: str) -> list[TokenType]:
        """Lex a source code string into a list of tokens."""
        lex = lexer.Lexer(code)
        return lex.process()

    def create_analyzer(
        self,
        tokens_or_code: list[TokenType] | str,
        entrypoint: type[RuleItem] | None = None,
    ) -> ASTAnalyzer:
        """Create an active ASTAnalyzer over the given tokens or code."""
        if isinstance(tokens_or_code, str):
            tokens = self.tokenize(tokens_or_code)
        else:
            tokens = list(tokens_or_code)

        p = parser.Parser(tokens)
        root = entrypoint or DummyEntrypoint
        return ASTAnalyzer(p, root)

    def parse(
        self,
        combinator: Combinator,
        tokens_or_code: list[TokenType] | str,
        entrypoint: type[RuleItem] | None = None,
    ) -> Any:
        """Execute a combinator through analyzer.visitor and return the parsed result."""
        analyzer = self.create_analyzer(tokens_or_code, entrypoint=entrypoint)
        return analyzer.visitor(combinator)

    def parse_with_analyzer(
        self,
        combinator: Combinator,
        tokens_or_code: list[TokenType] | str,
        entrypoint: type[RuleItem] | None = None,
    ) -> tuple[Any, ASTAnalyzer]:
        """Execute combinator and return both result and the updated analyzer."""
        analyzer = self.create_analyzer(tokens_or_code, entrypoint=entrypoint)
        res = analyzer.visitor(combinator)
        return res, analyzer
