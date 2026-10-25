"""Tests for Preprocess, Convert and Expected combinators."""
from __future__ import annotations

from gram.core.ast.nodes import LiteralSymbol
from gram.core.combinators import (
    Alt,
    Convert,
    Expected,
    MatchToken,
    Preprocess,
    Seq,
)
from gram.core.lexer import Token
from tests.combinators.base import CombinatorTestCase


class TestPreprocessConvertExpected(CombinatorTestCase):
    def test_preprocess_receives_analyzer_and_current_token(self) -> None:
        seen = []

        def check(analyzer, token):
            seen.append((analyzer, token.value))
            return True

        result, analyzer = self.parse_with_analyzer(
            Seq(Preprocess(check), MatchToken(Token.IDENT)),
            "name",
        )

        self.assertEqual(seen, [(analyzer, "name")])
        self.assertEqual(len(result), 1)
        self.assertEqual(analyzer.parser.pos, 1)

    def test_preprocess_rejects_false_and_none_without_consuming(self) -> None:
        for callback in (lambda analyzer, token: False, lambda analyzer, token: None):
            with self.subTest(callback=callback):
                result, analyzer = self.parse_with_analyzer(
                    Preprocess(callback),
                    "name",
                )
                self.assertIsNone(result)
                self.assertEqual(analyzer.parser.pos, 0)
                self.assertTrue(
                    any(error.name == "PreprocessRejected" for error in analyzer._errors)
                )

    def test_preprocess_sees_active_logical_conversion(self) -> None:
        seen = []

        def check(analyzer, token):
            seen.append(token.token)
            return token.token == Token.DOT

        result, _ = self.parse_with_analyzer(
            Seq(
                Convert("Bunga", Token.DOT, scope=True),
                Preprocess(check),
                MatchToken(Token.DOT),
            ),
            "Bunga",
        )

        self.assertEqual(seen, [Token.DOT])
        self.assertIsNotNone(result)

    def test_convert_local_only_changes_current_identifier(self) -> None:
        result, analyzer = self.parse_with_analyzer(
            Seq(
                Convert("Bunga", Token.DOT),
                MatchToken(Token.DOT),
                MatchToken(Token.IDENT),
            ),
            "Bunga Bunga",
        )

        self.assertIsNotNone(result)
        self.assertEqual(analyzer.parser.pos, 2)
        self.assertEqual(analyzer.parser.tokens[1].token, Token.IDENT)
        self.assertIsInstance(result[0], LiteralSymbol)

    def test_convert_scoped_applies_to_future_tokens(self) -> None:
        result, analyzer = self.parse_with_analyzer(
            Seq(
                Convert("Bunga", Token.DOT, scope=True),
                MatchToken(Token.DOT),
                MatchToken(Token.DOT),
            ),
            "Bunga Bunga",
        )

        self.assertIsNotNone(result)
        self.assertEqual(analyzer.parser.pos, 2)
        self.assertEqual(analyzer.parser.conversions, {"Bunga": Token.DOT})
        self.assertEqual(analyzer.parser.tokens[1].token, Token.IDENT)

    def test_convert_scope_is_rolled_back_when_branch_fails(self) -> None:
        result, analyzer = self.parse_with_analyzer(
            Alt(
                Seq(
                    Convert("Bunga", Token.DOT, scope=True),
                    MatchToken(Token.NUMBER),
                ),
                MatchToken(Token.IDENT),
            ),
            "Bunga",
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.token.value, "Bunga")
        self.assertEqual(analyzer.parser.conversions, {})

    def test_convert_rejects_conflicting_scoped_definition(self) -> None:
        result, analyzer = self.parse_with_analyzer(
            Seq(
                Convert("Bunga", Token.DOT, scope=True),
                Convert("Bunga", Token.COMMA, scope=True),
            ),
            "Bunga",
        )

        self.assertIsNone(result)
        self.assertTrue(
            any(error.name == "ConversionConflict" for error in analyzer._errors)
        )

    def test_expected_newline_count_and_indent(self) -> None:
        result, analyzer = self.parse_with_analyzer(
            Seq(
                MatchToken(Token.IDENT),
                Expected.newline(),
                MatchToken(Token.INDENT),
                MatchToken(Token.IDENT),
                Expected.count(1),
                Expected.indent(4),
            ),
            "first\n    second",
        )

        self.assertIsNotNone(result)
        self.assertEqual(analyzer.parser.pos, 3)

    def test_expected_ncount_rejects_exact_remaining_count(self) -> None:
        result, analyzer = self.parse_with_analyzer(
            Expected.ncount(2),
            "one two",
        )

        self.assertIsNone(result)
        self.assertTrue(
            any(error.name == "ExpectedNCountMismatch" for error in analyzer._errors)
        )

    def test_expected_constructor_validation(self) -> None:
        with self.assertRaisesRegex(Exception, "InvalidExpectedKind"):
            Expected("unknown")

        with self.assertRaisesRegex(Exception, "InvalidExpectedValue"):
            Expected.count(-1)
