"""
Tests for Sequence (Seq) and Alternative (Alt) Structural Combinators.
"""
from __future__ import annotations

from gram import errors
from gram.core.ast.nodes import ASTKeyword, ASTNode, Identifier, LiteralNumber
from gram.core.combinators.alternative import Alt
from gram.core.combinators.match import MatchKeyword, MatchToken
from gram.core.combinators.sequence import Seq
from gram.core.lexer.tokens import Token
from tests.combinators.base import CombinatorTestCase


class TestSequenceAndAlternative(CombinatorTestCase):
    """
    Validates result shape, operational variants, and raised errors
    for Seq and Alt combinators.
    """

    # =========================================================================
    # 1. Seq (Sequence)
    # =========================================================================

    def test_seq_shape_and_variants(self) -> None:
        """1. Result shape: list[Any] of child AST nodes."""
        # Variant A: Standard sequence
        seq = Seq(MatchKeyword("int"), MatchToken(Token.IDENT))
        res, analyzer = self.parse_with_analyzer(seq, "int my_var = 10")
        self.assertIsInstance(res, list)
        self.assertEqual(len(res), 2)
        self.assertIsInstance(res[0], ASTKeyword)
        self.assertEqual(res[0].token.value, "int")
        self.assertIsInstance(res[1], Identifier)
        self.assertEqual(res[1].token.value, "my_var")
        self.assertEqual(analyzer.parser.pos, 2)

        # Variant B: Nested sequences
        nested_seq = Seq(
            MatchKeyword("int"),
            Seq(MatchToken(Token.IDENT), MatchToken("ASSIGN")),
            MatchToken(Token.NUMBER),
        )
        res_nested, analyzer2 = self.parse_with_analyzer(nested_seq, "int x = 42")
        self.assertIsInstance(res_nested, list)
        self.assertEqual(len(res_nested), 3)
        self.assertIsInstance(res_nested[1], list)  # inner list
        self.assertEqual(analyzer2.parser.pos, 4)

        # Variant C: Partial failure and atomic backtracking
        # 'int' matches, but second element fails -> entire sequence fails, cursor restores
        seq_fail = Seq(MatchKeyword("int"), MatchToken(Token.STRING))
        res_fail, analyzer3 = self.parse_with_analyzer(seq_fail, "int my_var")
        self.assertIsNone(res_fail)
        self.assertEqual(analyzer3.parser.pos, 0)

    def test_seq_errors(self) -> None:
        """3. Errors: EmptySequence raised when no combinators are supplied."""
        with self.assertRaises(errors.GrammarError) as ctx:
            Seq()
        self.assertEqual(ctx.exception.name, "EmptySequence")

    # =========================================================================
    # 2. Alt (Alternative)
    # =========================================================================

    def test_alt_shape_and_variants(self) -> None:
        """1. Result shape: exact return type of the first matching candidate."""
        alt = Alt(
            MatchKeyword("int"),
            MatchKeyword("str"),
            MatchToken(Token.IDENT),
        )

        # Variant A: First branch matches
        res_first, a1 = self.parse_with_analyzer(alt, "int x")
        self.assertIsInstance(res_first, ASTKeyword)
        self.assertEqual(res_first.token.value, "int")
        self.assertEqual(a1.parser.pos, 1)

        # Variant B: Second branch matches (first backtracks atomically)
        res_second, a2 = self.parse_with_analyzer(alt, "str y")
        self.assertIsInstance(res_second, ASTKeyword)
        self.assertEqual(res_second.token.value, "str")
        self.assertEqual(a2.parser.pos, 1)

        # Variant C: Third branch matches (ident)
        res_third, a3 = self.parse_with_analyzer(alt, "foo_bar")
        self.assertIsInstance(res_third, Identifier)
        self.assertEqual(res_third.token.value, "foo_bar")
        self.assertEqual(a3.parser.pos, 1)

        # Variant D: All branches fail -> returns None without moving cursor
        res_none, a4 = self.parse_with_analyzer(alt, "12345")
        self.assertIsNone(res_none)
        self.assertEqual(a4.parser.pos, 0)

        # Variant E: ignore=True attribute for raytracing exclusion
        alt_ignored = Alt(MatchToken(Token.NUMBER), ignore=True)
        self.assertTrue(alt_ignored.ignore)
        res_ign, a5 = self.parse_with_analyzer(alt_ignored, "555")
        self.assertIsInstance(res_ign, LiteralNumber)
        self.assertEqual(res_ign.token.value, 555)

    def test_alt_errors(self) -> None:
        """3. Errors: EmptyAlternatives raised when no candidate is supplied."""
        with self.assertRaises(errors.GrammarError) as ctx:
            Alt()
        self.assertEqual(ctx.exception.name, "EmptyAlternatives")
