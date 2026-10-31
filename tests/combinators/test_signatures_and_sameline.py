"""
Tests for formal Combinator Signatures and the SameLine Combinator.
"""
from __future__ import annotations

import unittest

from gram.core.combinators import (
    Alt,
    ArithmeticExpr,
    Combinator,
    CombinatorKind,
    COMPILABLE_COMBINATOR_KINDS,
    ConditionalExpr,
    Convert,
    DualExpr,
    Enclosed,
    ErrorCombinator,
    Expected,
    If,
    Item,
    Literal,
    Load,
    Many,
    MatchGroup,
    MatchKeyword,
    MatchSeqSymbol,
    MatchToken,
    Not,
    Opt,
    Peek,
    Preprocess,
    Ref,
    Req,
    SameLine,
    Save,
    Separator,
    Seq,
    Skip,
    Some,
    Tag,
    Tokenize,
    Until,
    UntilIndent,
    get_combinator_kind,
    is_compilable_combinator,
    is_semantic_combinator,
)
from gram.core.combinators.signals import SkipFlowSignal
from gram.core.lexer.tokens import Token, TokenType
from tests.combinators.base import CombinatorTestCase, DummyEntryRule


class CustomExternalCombinator(Combinator):
    """External/user-defined combinator without formal Gram signature."""

    def parse(self, analyzer):
        return []


class TestCombinatorSignatures(unittest.TestCase):
    """Tests verification of formal semantic signatures on all combinators."""

    def test_all_builtin_combinators_have_valid_signatures(self) -> None:
        samples = [
            (MatchToken(Token.IDENT), CombinatorKind.TERMINAL_TOKEN),
            (MatchKeyword("test"), CombinatorKind.TERMINAL_KEYWORD),
            (MatchGroup("types"), CombinatorKind.TERMINAL_GROUP),
            (MatchSeqSymbol(";"), CombinatorKind.TERMINAL_SYMBOL),
            (Literal("abc"), CombinatorKind.TERMINAL_LITERAL),
            (Seq(MatchToken(Token.IDENT)), CombinatorKind.SEQUENCE),
            (Alt(MatchToken(Token.IDENT)), CombinatorKind.ALTERNATIVE),
            (Opt(MatchToken(Token.IDENT)), CombinatorKind.OPTIONAL),
            (Many(MatchToken(Token.IDENT)), CombinatorKind.MANY),
            (Some(MatchToken(Token.IDENT)), CombinatorKind.SOME),
            (Ref(DummyEntryRule, name="dummy"), CombinatorKind.REFERENCE),
            (Enclosed(Token.LPAREN, MatchToken(Token.IDENT), Token.RPAREN), CombinatorKind.ENCLOSED),
            (Item(MatchToken(Token.IDENT)), CombinatorKind.ITEM),
            (Peek(MatchToken(Token.IDENT)), CombinatorKind.LOOKAHEAD_POS),
            (Not(MatchToken(Token.IDENT)), CombinatorKind.LOOKAHEAD_NEG),
            (SameLine(MatchToken(Token.IDENT)), CombinatorKind.SAME_LINE),
            (ArithmeticExpr(Token.IDENT), CombinatorKind.EXPR_ARITHMETIC),
            (ConditionalExpr(Token.IDENT), CombinatorKind.EXPR_CONDITIONAL),
            (DualExpr(Token.IDENT), CombinatorKind.EXPR_DUAL),
            (Convert("x", Token.IDENT), CombinatorKind.CONVERT),
            (Separator(Token.IDENT, sep=Token.COMMA), CombinatorKind.SEPARATOR),
            (Until(MatchToken(Token.SEMICOLON)), CombinatorKind.UNTIL),
            (UntilIndent(0), CombinatorKind.UNTIL_INDENT),
            (If(MatchToken(Token.IDENT)), CombinatorKind.IF),
            (ErrorCombinator(), CombinatorKind.ERROR),
            (Expected.newline(), CombinatorKind.EXPECTED),
            (Preprocess(lambda a, t: True), CombinatorKind.PREPROCESS),
            (Skip(SkipFlowSignal), CombinatorKind.SKIP),
            (Tag("my_tag"), CombinatorKind.TAG),
            (Load("var"), CombinatorKind.LOAD),
            (Save("var"), CombinatorKind.SAVE),
            (Req(Token.IDENT), CombinatorKind.REQ),
            (Tokenize(MatchToken(Token.IDENT)), CombinatorKind.TOKENIZE),
        ]

        for comb, expected_kind in samples:
            with self.subTest(combinator=type(comb).__name__):
                self.assertIs(get_combinator_kind(comb), expected_kind)
                self.assertTrue(is_semantic_combinator(comb))
                self.assertIsInstance(comb.combinator_kind, CombinatorKind)

    def test_external_combinators_rejected_as_non_semantic(self) -> None:
        external = CustomExternalCombinator()
        self.assertIsNone(external.combinator_kind)
        self.assertIsNone(get_combinator_kind(external))
        self.assertFalse(is_semantic_combinator(external))
        self.assertFalse(is_compilable_combinator(external))

    def test_compilable_combinators_classification(self) -> None:
        compilable_sample = Seq(MatchToken(Token.IDENT), SameLine(MatchToken(Token.NUMBER)))
        self.assertTrue(is_compilable_combinator(compilable_sample))

        # Preprocess contains an arbitrary Python callable; not compilable directly to C
        opaque_sample = Preprocess(lambda a, t: True)
        self.assertFalse(is_compilable_combinator(opaque_sample))


class TestSameLineCombinator(CombinatorTestCase):
    """Tests execution and line-continuity assertions of SameLine."""

    def test_same_line_matches_when_on_same_line(self) -> None:
        comb = Seq(MatchKeyword("return"), SameLine(MatchToken(Token.NUMBER)))
        tokens = [
            TokenType(Token.KEYWORD, "return", line=1, col=1),
            TokenType(Token.NUMBER, "42", line=1, col=8),
        ]
        res, analyzer = self.parse_with_analyzer(comb, tokens)
        self.assertIsNotNone(res)
        self.assertEqual(len(res), 2)
        self.assertEqual(res[1].token.value, "42")
        self.assertEqual(analyzer.parser.pos, 2)

    def test_same_line_fails_and_rewinds_when_on_next_line(self) -> None:
        comb = Seq(MatchKeyword("return"), SameLine(MatchToken(Token.NUMBER)))
        tokens = [
            TokenType(Token.KEYWORD, "return", line=1, col=1),
            TokenType(Token.NUMBER, "42", line=2, col=1),
        ]
        res, analyzer = self.parse_with_analyzer(comb, tokens)
        self.assertIsNone(res)
        # Because Seq failed on the second element, parser must be rewound to position 0
        self.assertEqual(analyzer.parser.pos, 0)

    def test_same_line_fails_and_rewinds_when_inner_fails(self) -> None:
        comb = Seq(MatchKeyword("return"), SameLine(MatchToken(Token.STRING)))
        tokens = [
            TokenType(Token.KEYWORD, "return", line=1, col=1),
            TokenType(Token.NUMBER, "42", line=1, col=8),
        ]
        res, analyzer = self.parse_with_analyzer(comb, tokens)
        self.assertIsNone(res)
        self.assertEqual(analyzer.parser.pos, 0)


if __name__ == "__main__":
    unittest.main()
