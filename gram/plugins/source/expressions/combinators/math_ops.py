"""
Combinadores atómicos para operaciones aritméticas individuales en gram.
========================================================================
Permite definir o reconocer operaciones binarias (+, -, *, /, //, %, **),
unarias (+, -) y agrupaciones de paréntesis de forma modular en gramáticas.
"""
from __future__ import annotations

from typing import Any
from gram.core.ast.nodes import ASTNode
from gram.core.combinators.base import Combinator
from gram.core.combinators.additional_stack import CombinatorAdditionalStack
from gram.core.lexer.tokens import Token, TokenType
from gram.errors import codes
from gram.utilities import error


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

    def parse(
        self,
        analyzer: Any,
        current: TokenType,
        ignore_errors: bool = False,
    ) -> ASTNode | None:
        from gram.plugins.source.expressions.combinators.arithmetic_expr import ArithmeticExpr
        return ArithmeticExpr().parse(analyzer, current, ignore_errors=ignore_errors)

    def __repr__(self) -> str:
        return f"MathBinaryOp({self.expected_token})"


class MathUnaryOp(Combinator):
    """
    Reconoce una operación unaria (+ o -) seguida de un operando o expresión.
    """
    code: int = 7003
    name: str = "MathUnaryOp"

    def parse(
        self,
        analyzer: Any,
        current: TokenType,
        ignore_errors: bool = False,
    ) -> ASTNode | None:
        if current.token not in (Token.PLUS, Token.MINUS, Token.DECREMENT, Token.INCREMENT):
            if ignore_errors:
                return None
            err_code = codes.CodeError((2, 1, 1, 0, 1), "MathUnaryOp.Failed")
            error.ParserError("Se esperaba operador unario '+' o '-'.", err_code).raise_error()

        from gram.plugins.source.expressions.combinators.arithmetic_expr import ArithmeticExpr
        return ArithmeticExpr().parse(analyzer, current, ignore_errors=ignore_errors)


class MathGroup(Combinator):
    """
    Reconoce una expresión agrupada entre paréntesis: '(' <expr> ')'.
    """
    code: int = 7004
    name: str = "MathGroup"

    def parse(
        self,
        analyzer: Any,
        current: TokenType,
        ignore_errors: bool = False,
    ) -> ASTNode | None:
        if current.token != Token.LPAREN:
            if ignore_errors:
                return None
            err_code = codes.CodeError((2, 1, 1, 0, 1), "MathGroup.ExpectedLParen")
            error.ParserError("Se esperaba '('.", err_code).raise_error()

        from gram.plugins.source.expressions.combinators.arithmetic_expr import ArithmeticExpr
        return ArithmeticExpr().parse(analyzer, current, ignore_errors=ignore_errors)


CombinatorAdditionalStack.register(MathBinaryOp)
CombinatorAdditionalStack.register(MathUnaryOp)
CombinatorAdditionalStack.register(MathGroup)
