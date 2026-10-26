"""Regression tests for generic parser performance features."""
from __future__ import annotations

import inspect
import os
import unittest

from gram import config, lexer
from gram.core.ast.raytracing import RayTracing
from gram.core.combinators import Alt, MatchKeyword, MatchToken, Ref, RuleItem, Seq
from gram.core.lexer.tokens import Token
from gram.core.parser import Parser
from gram.sessions import Session
from gram.utilities.error import _resolve_origin


class PerformanceDeclaration(RuleItem):
    entrypoint = Seq(
        MatchKeyword("let"),
        MatchToken(Token.IDENT),
        MatchToken(Token.ASSIGN),
        MatchToken(Token.NUMBER),
        MatchToken(Token.SEMICOLON),
    )


class PerformanceProgram(RuleItem):
    entrypoint = Alt(Ref(PerformanceDeclaration))


class TestPerformanceFeatures(unittest.TestCase):
    def setUp(self) -> None:
        self._exit_on_error = config.ERROR_EXIT_ON_ERROR
        self._hide_console = config.ERROR_HIDE_CONSOLE
        config.ERROR_EXIT_ON_ERROR = False
        config.ERROR_HIDE_CONSOLE = True
        lexer.clear_all()
        lexer.add_keyword("let")

    def tearDown(self) -> None:
        lexer.clear_all()
        config.ERROR_EXIT_ON_ERROR = self._exit_on_error
        config.ERROR_HIDE_CONSOLE = self._hide_console

    def tokens(self):
        return lexer.Lexer("let value = 1;").process()

    def test_parser_accepts_all_trace_modes(self) -> None:
        for trace in ("off", "basic", "detailed"):
            with self.subTest(trace=trace):
                result = Parser(self.tokens()).parse(
                    PerformanceProgram, trace=trace
                )
                self.assertEqual(len(result), 1)

    def test_session_forwards_trace_mode(self) -> None:
        session = Session("performance", "Many", PerformanceProgram)
        result = session.parse(self.tokens(), "performance.gram", trace="off")
        self.assertEqual(len(result), 1)

    def test_raytracing_checkpoint_restores_prefix_without_eager_copy(self) -> None:
        raytracing = RayTracing()
        before = MatchToken(Token.IDENT)
        after = MatchToken(Token.NUMBER)
        checkpoint = object()

        raytracing.add(before)
        raytracing.lift(checkpoint)
        raytracing.add(after)
        raytracing.unreach(checkpoint)

        self.assertEqual(raytracing.trace.values, [before])
        self.assertEqual(raytracing.trace.levels, [1])

    def test_error_origin_resolution_is_cached_by_path_and_cwd(self) -> None:
        _resolve_origin.cache_clear()
        caller = inspect.currentframe()
        self.assertIsNotNone(caller)
        first = _resolve_origin(caller.f_code.co_filename, os.getcwd())
        second = _resolve_origin(caller.f_code.co_filename, os.getcwd())
        self.assertEqual(first, second)
        self.assertGreaterEqual(_resolve_origin.cache_info().hits, 1)


if __name__ == "__main__":
    unittest.main()
