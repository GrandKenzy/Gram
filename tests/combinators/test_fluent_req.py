"""
Tests for Fluent Token Validation and Transformation Combinator (Req).
"""
from __future__ import annotations

from gram import errors
from gram.core.ast.nodes import Identifier, LiteralNumber
from gram.core.combinators.req import Req
from gram.core.lexer.tokens import Token
from tests.combinators.base import CombinatorTestCase


class TestFluentReq(CombinatorTestCase):
    """
    Validates result shape, validation variants, transformations, and error handling
    for the fluent Req combinator.
    """

    def test_req_shape_and_variants(self) -> None:
        """1. Result shape: returns ASTNode wrapping validated/transformed token."""
        # Variant A: Simple validation (is_lower, min length)
        req_lower = Req(Token.IDENT).is_lower().min(3)
        res, a1 = self.parse_with_analyzer(req_lower, "my_var 123")
        self.assertIsInstance(res, Identifier)
        self.assertEqual(res.token.value, "my_var")
        self.assertEqual(a1.parser.pos, 1)

        # Variant B: Numeric validation (min and max)
        req_num = Req(Token.NUMBER).min(10).max(100)
        res_num, a2 = self.parse_with_analyzer(req_num, "42")
        self.assertIsInstance(res_num, LiteralNumber)
        self.assertEqual(res_num.token.value, 42)

        # Variant C: Value transformation (apply_upper)
        req_upper = Req(Token.IDENT).apply_upper()
        res_up, _ = self.parse_with_analyzer(req_upper, "lowercase_name")
        self.assertIsInstance(res_up, Identifier)
        self.assertEqual(res_up.token.value, "LOWERCASE_NAME")

        # Variant D: Snake case validation
        req_snake = Req(Token.IDENT).is_snake_case()
        res_snake, _ = self.parse_with_analyzer(req_snake, "snake_cased_word")
        self.assertIsNotNone(res_snake)

    def test_req_errors(self) -> None:
        """3. Errors: ReqConstraintFailed and ReqTokenMismatch reported."""
        # Error 1: Constraint failed (e.g., is_lower fails on uppercase)
        req_lower = Req(Token.IDENT).is_lower()
        res_fail, a1 = self.parse_with_analyzer(req_lower, "UPPERCASE_VAR")
        self.assertIsNone(res_fail)
        self.assertTrue(any(e.name == "ReqConstraintFailed" for e in a1._errors))

        # Error 2: Token mismatch (expecting NUMBER, found IDENT)
        req_num = Req(Token.NUMBER)
        res_mismatch, a2 = self.parse_with_analyzer(req_num, "not_a_number")
        self.assertIsNone(res_mismatch)
        self.assertTrue(any(e.name == "ReqTokenMismatch" for e in a2._errors))

        # Error 3: Unexpected EOF
        res_eof, a3 = self.parse_with_analyzer(req_num, [])
        self.assertIsNone(res_eof)
        self.assertTrue(any(e.name == "ReqUnexpectedEOF" for e in a3._errors))
