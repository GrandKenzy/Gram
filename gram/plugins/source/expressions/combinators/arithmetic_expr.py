"""
Combinador de expresiones aritméticas para Gram Framework.
==========================================================
Analiza expresiones con precedencia y asociatividad, y devuelve un AST
operacional cuyos nodos conservan la estructura izquierda/derecha.
"""
from __future__ import annotations

from typing import Any

from gram.core.ast.nodes import ASTNode
from gram.core.combinators.additional_stack import CombinatorAdditionalStack
from gram.core.combinators.base import Combinator
from gram.core.lexer.tokens import Token, TokenType
from gram.errors import codes
from gram.plugins.source.expressions.evaluator import (
    ArithmeticParser,
    ArithmeticSyntaxError,
)
from gram.utilities import error


class ArithmeticExpr(Combinator):
    """Pratt parser que devuelve un AST procesable de operandos y operaciones."""

    code: int = 7001
    name: str = "ArithmeticExpr"
    description: str = "Analizador de expresiones con precedencia y anidamiento."

    def __init__(
        self,
        allow_ident: bool = True,
        allow_logical: bool = False,
    ) -> None:
        super().__init__()
        self.allow_ident = allow_ident
        self.allow_logical = allow_logical

    def parse(
        self,
        analyzer: Any,
        current: TokenType | None = None,
        ignore_errors: bool = False,
    ) -> ASTNode | None:
        target_node = self._get_node(analyzer)
        parser = self._get_parser(analyzer)
        start_pos = parser.pos
        remaining = parser.tokens[start_pos:]
        current_is_in_stream = (
            current is None
            or (remaining and remaining[0] is current)
        )
        input_tokens = remaining if current_is_in_stream else [current, *remaining]
        if not input_tokens:
            if ignore_errors:
                return None
            self._raise_parse_error(
                ArithmeticSyntaxError("Se esperaba una expresión aritmética, pero se alcanzó EOF."),
                None,
            )

        start_token = input_tokens[0]
        valid_start = (
            start_token.token
            in (
                Token.NUMBER,
                Token.BOOL,
                Token.PLUS,
                Token.MINUS,
                Token.NOT,
                Token.NOT_LOGIC,
                Token.LOGIC_NOT,
                Token.EXCLAMATION,
                Token.DECREMENT,
                Token.INCREMENT,
                Token.LPAREN,
            )
            or (self.allow_ident and start_token.token == Token.IDENT)
            or isinstance(start_token.value, (int, float, bool))
        )
        if not valid_start:
            if ignore_errors:
                return None
            self._raise_parse_error(
                ArithmeticSyntaxError(
                    f"Token {start_token.value!r} ({start_token.token.name}) "
                    "no puede iniciar una expresión."
                ),
                start_token,
            )

        expression_parser = ArithmeticParser(
            input_tokens,
            allow_logical=self.allow_logical,
            allow_ident=self.allow_ident,
        )
        try:
            expression = expression_parser.parse_expression()
        except ArithmeticSyntaxError as exc:
            if ignore_errors:
                return None
            self._raise_parse_error(exc, start_token)

        consumed = expression_parser.pos
        if consumed == 0:
            return None
        parser.pos = start_pos + consumed - (0 if current_is_in_stream else 1)
        return expression.to_ast_node(level=0)

    @staticmethod
    def _raise_parse_error(
        exc: ArithmeticSyntaxError,
        token: TokenType | None,
    ) -> None:
        err_code = codes.CodeError((2, 1, 1, 0, 1), "Arithmetic.ParseError")
        location = (
            f"Línea {token.line}, columna {token.col}."
            if token is not None
            else "No hay tokens disponibles."
        )
        error.ParserError(
            f"Error al analizar expresión aritmética: {exc}",
            err_code,
            location,
        ).raise_error()

    def __repr__(self) -> str:
        return (
            f"ArithmeticExpr(allow_ident={self.allow_ident}, "
            f"allow_logical={self.allow_logical})"
        )


CombinatorAdditionalStack.register(ArithmeticExpr)
