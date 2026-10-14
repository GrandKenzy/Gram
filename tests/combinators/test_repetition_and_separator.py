"""
Tests for Repetition and Separator Combinators (Many, Some, Until, Separator).
"""
from __future__ import annotations

from gram import errors
from gram.core.ast.nodes import Identifier, LiteralNumber
from gram.core.combinators.many import Many
from gram.core.combinators.match import MatchKeyword, MatchToken
from gram.core.combinators.separator import Sep, Separator, SeparatorResult
from gram.core.combinators.some import Some
from gram.core.combinators.until import Until
from gram.core.lexer.tokens import Token
from tests.combinators.base import CombinatorTestCase


class TestRepetitionAndSeparator(CombinatorTestCase):
    """
    Validates result shape, operational variants, and errors for:
    - Many (0..n)
    - Some (1..n)
    - Until
    - Separator / Sep
    """

    # =========================================================================
    # 1. Many (0..n)
    # =========================================================================

    def test_many_shape_and_variants(self) -> None:
        """1. Result shape: list[Any]."""
        many_idents = Many(MatchToken(Token.IDENT))

        # Variant A: Multiple matches (3 items)
        res_three, a1 = self.parse_with_analyzer(many_idents, "foo bar baz 123")
        self.assertIsInstance(res_three, list)
        self.assertEqual(len(res_three), 3)
        self.assertTrue(all(isinstance(x, Identifier) for x in res_three))
        self.assertEqual([x.token.value for x in res_three], ["foo", "bar", "baz"])
        self.assertEqual(a1.parser.pos, 3)

        # Variant B: Zero matches returns empty list [] without error
        res_zero, a2 = self.parse_with_analyzer(many_idents, "123 456")
        self.assertIsInstance(res_zero, list)
        self.assertEqual(len(res_zero), 0)
        self.assertEqual(a2.parser.pos, 0)

    # =========================================================================
    # 2. Some (1..n)
    # =========================================================================

    def test_some_shape_and_variants(self) -> None:
        """1. Result shape: list[Any] on match, None on 0 matches."""
        some_numbers = Some(MatchToken(Token.NUMBER))

        # Variant A: Multiple matches
        res_multi, a1 = self.parse_with_analyzer(some_numbers, "10 20 30 ident")
        self.assertIsInstance(res_multi, list)
        self.assertEqual(len(res_multi), 3)
        self.assertTrue(all(isinstance(x, LiteralNumber) for x in res_multi))
        self.assertEqual([x.token.value for x in res_multi], [10, 20, 30])
        self.assertEqual(a1.parser.pos, 3)

        # Variant B: Exactly 1 match
        res_one, a2 = self.parse_with_analyzer(some_numbers, "42 ident")
        self.assertIsInstance(res_one, list)
        self.assertEqual(len(res_one), 1)

        # Variant C: Zero matches returns None (mandatory match not met)
        res_zero, a3 = self.parse_with_analyzer(some_numbers, "ident 10")
        self.assertIsNone(res_zero)
        self.assertEqual(a3.parser.pos, 0)

    # =========================================================================
    # 3. Until
    # =========================================================================

    def test_until_shape_and_variants(self) -> None:
        """1. Result shape: list[Any]."""
        # Variant A: Stop before target (consume_target=False)
        until_semi = Until(MatchToken("SEMICOLON"), consume_target=False)
        res, a1 = self.parse_with_analyzer(until_semi, "a b c ; rest")
        self.assertIsInstance(res, list)
        self.assertEqual(len(res), 3)
        # Semicolon is still the next unconsumed token
        self.assertEqual(a1.parser.peek().token, Token.SEMICOLON)

        # Variant B: Consume target (consume_target=True)
        until_semi_consume = Until(MatchToken("SEMICOLON"), consume_target=True)
        res_cons, a2 = self.parse_with_analyzer(until_semi_consume, "x y ; rest")
        self.assertIsInstance(res_cons, list)
        self.assertEqual(len(res_cons), 3)  # x, y, and semicolon
        self.assertEqual(a2.parser.peek().token, Token.IDENT)

    # =========================================================================
    # 4. Separator / Sep
    # =========================================================================

    def test_separator_shape_and_variants(self) -> None:
        """1. Result shape: SeparatorResult (subclass of list)."""
        sep_comb = Separator(values=[Token.NUMBER], sep=Token.COMMA)

        # Variant A: Multiple comma-separated numbers
        res, a1 = self.parse_with_analyzer(sep_comb, "1, 2, 3 + 4")
        self.assertIsInstance(res, SeparatorResult)
        self.assertIsInstance(res, list)
        self.assertEqual(len(res), 3)
        self.assertEqual([x.token.value for x in res], [1, 2, 3])
        self.assertFalse(res.trailing_separator)
        self.assertEqual(a1.parser.pos, 5)

        # Variant B: Trailing separator allowed
        sep_trailing = Sep(values=[Token.IDENT], sep=Token.COMMA, allow_trailing=True)
        res_tr, a2 = self.parse_with_analyzer(sep_trailing, "x, y,")
        self.assertIsInstance(res_tr, SeparatorResult)
        self.assertEqual(len(res_tr), 2)
        self.assertTrue(res_tr.trailing_separator)

        # Variant C: Single item without separator
        res_single, a3 = self.parse_with_analyzer(sep_comb, "999")
        self.assertIsInstance(res_single, SeparatorResult)
        self.assertEqual(len(res_single), 1)
        self.assertEqual(res_single[0].token.value, 999)

    def test_separator_errors(self) -> None:
        """3. Errors: Invalid value configuration in Separator raises GrammarError."""
        with self.assertRaises(errors.GrammarError) as ctx:
            Separator(values=[12345], sep=Token.COMMA)
        self.assertEqual(ctx.exception.name, "UnsupportedSeparatorValue")
