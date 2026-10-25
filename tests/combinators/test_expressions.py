"""
Tests for Pratt Expression Combinators (DualExpr, ArithmeticExpr, ConditionalExpr).
"""
from __future__ import annotations

from gram import errors
from gram.core.ast.nodes import ASTNode, ASTRef, Identifier, LiteralNumber
from gram.core.combinators.base import RuleItem
from gram.core.combinators.sequence import Seq
from gram.core.combinators.match import MatchToken
from gram.core.combinators.expressions import (
    ASTBinaryOp,
    ASTUnaryOp,
    ArithmeticExpr,
    ConditionalExpr,
    DualExpr,
)
from gram.core.combinators.reference import Ref
from gram.core.lexer.tokens import Token
from tests.combinators.base import CombinatorTestCase


class UnnamedNonNodeable(RuleItem):
    nodeable = False
    entrypoint = None


class ParenthesizedNumber(RuleItem):
    """Specialized atom used to guard Ref-before-native-grouping behavior."""

    nodeable = True
    entrypoint = Seq(
        MatchToken(Token.LPAREN),
        MatchToken(Token.NUMBER),
        MatchToken(Token.RPAREN),
    )


class TestExpressionCombinators(CombinatorTestCase):
    """
    Validates result shape (ASTBinaryOp, ASTUnaryOp, terminal ASTNode),
    precedence variants, and error handling for expression combinators.
    """

    # =========================================================================
    # 1. ArithmeticExpr & Operator Precedence
    # =========================================================================

    def test_arithmetic_expr_shape_and_variants(self) -> None:
        """1. Result shape: ASTBinaryOp tree respecting operator precedence."""
        arith = ArithmeticExpr(Token.NUMBER, Token.IDENT)

        # Variant A: Single literal (no operators) -> returns LiteralNumber
        res_atom, a1 = self.parse_with_analyzer(arith, "42")
        self.assertIsInstance(res_atom, LiteralNumber)
        self.assertEqual(res_atom.token.value, 42)
        self.assertEqual(a1.parser.pos, 1)

        # Variant B: Binary operation -> ASTBinaryOp
        res_bin, a2 = self.parse_with_analyzer(arith, "10 + 20")
        self.assertIsInstance(res_bin, ASTBinaryOp)
        self.assertIsInstance(res_bin.left, LiteralNumber)
        self.assertEqual(res_bin.left.token.value, 10)
        self.assertEqual(res_bin.operator.token, Token.PLUS)
        self.assertIsInstance(res_bin.right, LiteralNumber)
        self.assertEqual(res_bin.right.token.value, 20)
        self.assertEqual(a2.parser.pos, 3)

        # Variant C: Precedence climbing (10 + 20 * 30 -> 10 + (20 * 30))
        res_prec, _ = self.parse_with_analyzer(arith, "10 + 20 * 30")
        self.assertIsInstance(res_prec, ASTBinaryOp)
        self.assertEqual(res_prec.operator.token, Token.PLUS)
        self.assertIsInstance(res_prec.right, ASTBinaryOp)
        self.assertEqual(res_prec.right.operator.token, Token.STAR)

        # Variant D: Parenthesized grouping overrides precedence ((10 + 20) * 30)
        res_paren, _ = self.parse_with_analyzer(arith, "(10 + 20) * 30")
        self.assertIsInstance(res_paren, ASTBinaryOp)
        self.assertEqual(res_paren.operator.token, Token.STAR)
        self.assertIsInstance(res_paren.left, ASTBinaryOp)
        self.assertEqual(res_paren.left.operator.token, Token.PLUS)

    # =========================================================================
    # 2. ConditionalExpr
    # =========================================================================

    def test_conditional_expr_shape_and_variants(self) -> None:
        """1. Result shape: ASTBinaryOp with comparison/logical operators."""
        cond = ConditionalExpr(Token.IDENT, Token.NUMBER)

        # Relational comparison
        res, a = self.parse_with_analyzer(cond, "x >= 100")
        self.assertIsInstance(res, ASTBinaryOp)
        self.assertEqual(res.operator.token, Token.GREATER_EQUAL)
        self.assertIsInstance(res.left, Identifier)
        self.assertIsInstance(res.right, LiteralNumber)

    # =========================================================================
    # 3. DualExpr (Arithmetic + Conditional Unified)
    # =========================================================================

    def test_dual_expr_shape_and_variants(self) -> None:
        """1. Result shape & Variants: DualExpr mixing arithmetic and logic."""
        dual = DualExpr(Token.IDENT, Token.NUMBER)

        # Arithmetic comparison mixed (x + 5 >= 10)
        res, _ = self.parse_with_analyzer(dual, "x + 5 >= 10")
        self.assertIsInstance(res, ASTBinaryOp)
        self.assertEqual(res.operator.token, Token.GREATER_EQUAL)
        self.assertIsInstance(res.left, ASTBinaryOp)
        self.assertEqual(res.left.operator.token, Token.PLUS)

    def test_specialized_ref_can_override_native_parentheses(self) -> None:
        class RefFirstDualExpr(DualExpr):
            refs_before_grouping = True

        expr = RefFirstDualExpr(Ref(ParenthesizedNumber), Token.NUMBER)

        result, analyzer = self.parse_with_analyzer(expr, "(42)")

        self.assertIsInstance(result, ASTRef)
        self.assertEqual(result.name, "ParenthesizedNumber")
        self.assertEqual(analyzer.parser.pos, 3)

    # =========================================================================
    # 4. Errors
    # =========================================================================

    def test_expression_errors(self) -> None:
        """3. Errors: UnsupportedExpressionValue and UnnamedRefInExpression."""
        # Error A: Unsupported value type (e.g., int literal passed to values)
        with self.assertRaises(errors.GrammarError) as ctx:
            DualExpr(99999)  # type: ignore[arg-type]
        self.assertEqual(ctx.exception.name, "UnsupportedExpressionValue")

        # Error B: Unnamed, non-nodeable RuleItem passed as operand
        with self.assertRaises(errors.GrammarError) as ctx2:
            DualExpr(Ref(UnnamedNonNodeable))
        self.assertEqual(ctx2.exception.name, "UnnamedRefInExpression")
