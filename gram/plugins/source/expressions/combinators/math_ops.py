"""
Combinadores atómicos para operaciones aritméticas individuales en gram.
========================================================================
Permite definir o reconocer operaciones binarias (+, -, *, /, //, %, **),
unarias (+, -) y agrupaciones de paréntesis de forma modular en gramáticas.
"""
from __future__ import annotations

from typing import Any
from gram.core.combinators.base import Combinator
from gram.core.combinators.additional_stack import CombinatorAdditionalStack
from gram.core.lexer.tokens import Token, TokenType
from gram.errors import codes
from gram.utilities import error
from gram.plugins.source.expressions.evaluator import (
    ArithmeticNode,
    BinaryOpNode,
    UnaryOpNode,
    GroupNode,
    NumberNode,
    VariableNode,
    evaluate,
)


class MathBinaryOp(Combinator):
    """
    Reconoce una operación binaria específica o genérica: <operando> <operador> <operando>.
    """
    code: int = 7002
    name: str = "MathBinaryOp"

    OP_MAP: dict[str, Token] = {
        "+": Token.PLUS,
        "-": Token.MINUS,
        "*": Token.STAR,
        "/": Token.SLASH,
        "//": Token.FLOOR_DIV,
        "%": Token.PERCENT,
        "**": Token.POW,
    }

    def __init__(self, op: str | Token | None = None):
        super().__init__()
        self.expected_token: Token | None = None
        if isinstance(op, str):
            self.expected_token = self.OP_MAP.get(op)
        elif isinstance(op, Token):
            self.expected_token = op

    def parse(self, analyzer: Any, current: TokenType, ignore_errors: bool = False) -> list[TokenType] | None:
        parser = analyzer.parser
        saved_pos = parser.pos

        # Primer operando debe ser NUMBER, IDENT o LPAREN
        from gram.plugins.source.expressions.combinators.arithmetic_expr import ArithmeticExpr
        expr_comb = ArithmeticExpr()
        res1 = analyzer.process_combinator(expr_comb, current, ignore_errors=True)
        if res1 is None:
            parser.restore(saved_pos)
            if ignore_errors:
                return None
            err_code = codes.CodeError((2, 1, 1, 0, 1), "MathBinaryOp.Failed")
            error.ParserError("Fallo al reconocer operando inicial.", err_code).raise_error()

        return res1

    def __repr__(self) -> str:
        return f"MathBinaryOp({self.expected_token})"


class MathUnaryOp(Combinator):
    """
    Reconoce una operación unaria (+ o -) seguida de un operando o expresión.
    """
    code: int = 7003
    name: str = "MathUnaryOp"

    def parse(self, analyzer: Any, current: TokenType, ignore_errors: bool = False) -> list[TokenType] | None:
        parser = analyzer.parser
        saved_pos = parser.pos

        if current.token not in (Token.PLUS, Token.MINUS, Token.DECREMENT, Token.INCREMENT):
            if ignore_errors:
                return None
            err_code = codes.CodeError((2, 1, 1, 0, 1), "MathUnaryOp.Failed")
            error.ParserError("Se esperaba operador unario '+' o '-'.", err_code).raise_error()

        from gram.plugins.source.expressions.combinators.arithmetic_expr import ArithmeticExpr
        expr_comb = ArithmeticExpr()
        if not parser.not_empty():
            if ignore_errors:
                return None
            err_code = codes.CodeError((2, 1, 1, 0, 1), "MathUnaryOp.Incomplete")
            error.ParserError("Expresión unaria incompleta.", err_code).raise_error()

        nxt = parser.consume()
        res = analyzer.process_combinator(expr_comb, nxt, ignore_errors=True)
        if res is None:
            parser.restore(saved_pos)
            if ignore_errors:
                return None
            err_code = codes.CodeError((2, 1, 1, 0, 1), "MathUnaryOp.OperandFailed")
            error.ParserError("Fallo al reconocer operando tras unario.", err_code).raise_error()

        return [current] + list(res)


class MathGroup(Combinator):
    """
    Reconoce una expresión agrupada entre paréntesis: '(' <expr> ')'.
    """
    code: int = 7004
    name: str = "MathGroup"

    def parse(self, analyzer: Any, current: TokenType, ignore_errors: bool = False) -> list[TokenType] | None:
        parser = analyzer.parser
        saved_pos = parser.pos

        if current.token != Token.LPAREN:
            if ignore_errors:
                return None
            err_code = codes.CodeError((2, 1, 1, 0, 1), "MathGroup.ExpectedLParen")
            error.ParserError("Se esperaba '('.", err_code).raise_error()

        from gram.plugins.source.expressions.combinators.arithmetic_expr import ArithmeticExpr
        expr_comb = ArithmeticExpr()
        if not parser.not_empty():
            if ignore_errors:
                return None
            err_code = codes.CodeError((2, 1, 1, 0, 1), "MathGroup.Incomplete")
            error.ParserError("Paréntesis incompleto.", err_code).raise_error()

        nxt = parser.consume()
        res = analyzer.process_combinator(expr_comb, nxt, ignore_errors=True)
        if res is None:
            parser.restore(saved_pos)
            if ignore_errors:
                return None
            err_code = codes.CodeError((2, 1, 1, 0, 1), "MathGroup.ExprFailed")
            error.ParserError("Fallo al reconocer expresión interna en paréntesis.", err_code).raise_error()

        if not parser.not_empty() or parser.current().token != Token.RPAREN:
            parser.restore(saved_pos)
            if ignore_errors:
                return None
            err_code = codes.CodeError((2, 1, 1, 0, 1), "MathGroup.ExpectedRParen")
            error.ParserError("Se esperaba ')' de cierre.", err_code).raise_error()

        rparen = parser.consume()
        return [current] + list(res) + [rparen]


CombinatorAdditionalStack.register(MathBinaryOp)
CombinatorAdditionalStack.register(MathUnaryOp)
CombinatorAdditionalStack.register(MathGroup)
