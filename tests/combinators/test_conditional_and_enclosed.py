"""
Tests for Optional (Opt), Enclosed, and Conditional (If) Combinators.
"""
from __future__ import annotations

from gram import errors
from gram.core.ast.nodes import (
    ASTKeyword,
    Identifier,
    LiteralNumber,
    LiteralString,
)
from gram.core.combinators.conditional import If
from gram.core.combinators.enclosed import Enclosed
from gram.core.combinators.match import MatchKeyword, MatchToken
from gram.core.combinators.optional import Opt
from gram.core.lexer.tokens import Token
from tests.combinators.base import CombinatorTestCase


class TestConditionalAndEnclosed(CombinatorTestCase):
    """
    Validates result shapes, operational variants, and errors for:
    - Opt (0..1)
    - Enclosed (delimited block)
    - If (conditional branching)
    """

    # =========================================================================
    # 1. Opt (Optional)
    # =========================================================================

    def test_opt_shape_and_variants(self) -> None:
        """1. Result shape: matched ASTNode when present, [] when omitted."""
        opt_ident = Opt(MatchToken(Token.IDENT))

        # Variant A: Present in stream (matches and consumes)
        res_present, a1 = self.parse_with_analyzer(opt_ident, "my_name 123")
        self.assertIsInstance(res_present, Identifier)
        self.assertEqual(res_present.token.value, "my_name")
        self.assertEqual(a1.parser.pos, 1)

        # Variant B: Omitted cleanly (returns [] to preserve sequence flow without error)
        res_omitted, a2 = self.parse_with_analyzer(opt_ident, "123 456")
        self.assertIsInstance(res_omitted, list)
        self.assertEqual(len(res_omitted), 0)
        self.assertEqual(a2.parser.pos, 0)

    def test_opt_errors(self) -> None:
        """3. Errors: Invalid non-combinator target raises GrammarError."""
        with self.assertRaises(errors.GrammarError) as ctx:
            Opt("not_a_combinator")  # type: ignore[arg-type]
        self.assertEqual(ctx.exception.name, "InvalidOptionalTarget")

    # =========================================================================
    # 2. Enclosed
    # =========================================================================

    def test_enclosed_shape_and_variants(self) -> None:
        """1. Result shape: returns inner content result."""
        # Variant A: Parens enclosing an identifier
        enc = Enclosed(open=Token.LPAREN, content=MatchToken(Token.IDENT), close=Token.RPAREN)
        res, a1 = self.parse_with_analyzer(enc, "( hello )")
        self.assertIsInstance(res, Identifier)
        self.assertEqual(res.token.value, "hello")
        self.assertEqual(a1.parser.pos, 3)

        # Variant B: Enclosed empty allowed
        enc_empty = Enclosed(open=Token.LPAREN, content=MatchToken(Token.IDENT), close=Token.RPAREN, allow_empty=True)
        res_emp, a2 = self.parse_with_analyzer(enc_empty, "()")
        self.assertIsInstance(res_emp, list)
        self.assertEqual(len(res_emp), 0)

        # Variant C: Missing open delimiter fails cleanly
        res_fail, a3 = self.parse_with_analyzer(enc, "hello )")
        self.assertIsNone(res_fail)
        self.assertEqual(a3.parser.pos, 0)

    def test_enclosed_errors(self) -> None:
        """3. Errors: Invalid delimiter type raises GrammarError."""
        with self.assertRaises(errors.GrammarError) as ctx:
            Enclosed(open="(", content=MatchToken(Token.IDENT), close=Token.RPAREN)  # type: ignore[arg-type]
        self.assertEqual(ctx.exception.name, "InvalidDelimiterType")

    # =========================================================================
    # 3. If (Conditional Branching)
    # =========================================================================

    def test_if_shape_and_variants(self) -> None:
        """1. Result shape: returns result of evaluated branch."""
        cond = If(
            conditions=MatchKeyword("int"),
            ok=MatchToken(Token.NUMBER),
            fail=MatchToken(Token.STRING),
        )

        # Variant A: Condition true -> ok branch executed (returns [*cond_results, ok_res])
        res_ok, a1 = self.parse_with_analyzer(cond, "int 100")
        self.assertIsInstance(res_ok, list)
        self.assertEqual(len(res_ok), 2)
        self.assertIsInstance(res_ok[0], ASTKeyword)
        self.assertIsInstance(res_ok[1], LiteralNumber)
        self.assertEqual(res_ok[1].token.value, 100)
        self.assertEqual(a1.parser.pos, 2)

        # Variant B: Condition false -> fail branch executed
        res_fail, a2 = self.parse_with_analyzer(cond, "\"fallback_str\"")
        self.assertIsInstance(res_fail, LiteralString)
        self.assertEqual(res_fail.token.value, "fallback_str")
        self.assertEqual(a2.parser.pos, 1)

        # Variant C: Condition true with restore=True (lookahead condition, returns ok result directly)
        cond_restore = If(
            conditions=MatchKeyword("int"),
            ok=MatchKeyword("int"),
            restore=True,
        )
        res_res, a3 = self.parse_with_analyzer(cond_restore, "int")
        self.assertIsInstance(res_res, ASTKeyword)
        self.assertEqual(a3.parser.pos, 1)

    def test_if_errors(self) -> None:
        """3. Errors: Empty conditions raise GrammarError."""
        with self.assertRaises(errors.GrammarError) as ctx:
            If(conditions=[])
        self.assertEqual(ctx.exception.name, "EmptyIfConditions")
