"""
Combinador ArithmeticExpr para gram Framework.
==============================================
Permite analizar expresiones aritméticas completas con precedencia de operadores,
anidamiento arbitrario, paréntesis y operadores unarios directamente sobre el flujo
de tokens del Parser de gram.
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
    is_binary_op,
    BINARY_PRECEDENCE,
    is_right_associative,
    UNARY_PRECEDENCE,
    ArithmeticSyntaxError,
)


class ArithmeticExpr(Combinator):
    """
    Combinador sintáctico para expresiones aritméticas en gram.

    Soporta:
    - Suma (+), Resta (-), Multiplicación (*), División (/), División entera (//), Módulo (%), Potencia (**)
    - Operadores unarios (+, -, --, ++)
    - Paréntesis con anidación a cualquier profundidad: ((1 + 2) * (3 - 4))
    - Literales numéricos (enteros y flotantes)
    - Variables / identificadores (opcional)
    """

    code: int = 7001
    name: str = "ArithmeticExpr"
    description: str = "Analizador de expresiones aritméticas completas con precedencia y anidamiento."

    def __init__(self, allow_ident: bool = True):
        super().__init__()
        self.allow_ident = allow_ident

    def parse(
        self,
        analyzer: Any,
        current: TokenType,
        ignore_errors: bool = False,
    ) -> list[TokenType] | None:
        target_node = self._get_node(analyzer)
        parser = analyzer.parser
        saved_pos = parser.pos

        tok_type = current.token
        valid_start = (
            tok_type in (Token.NUMBER, Token.PLUS, Token.MINUS, Token.DECREMENT, Token.INCREMENT, Token.LPAREN)
            or (self.allow_ident and tok_type == Token.IDENT)
            or isinstance(current.value, (int, float))
        )

        if not valid_start:
            if ignore_errors:
                return None
            err_code = codes.CodeError((2, 1, 1, 0, 1), "Arithmetic.InvalidStart")
            error.ParserError(
                f"Token '{current.value}' ({tok_type.name}) no puede iniciar una expresión aritmética.",
                err_code,
                f"Línea {current.line}, columna {current.col}.",
            ).raise_error()

        class StreamAdapter:
            def __init__(self, first_token: TokenType, prs: Any):
                self.first_token = first_token
                self.parser = prs
                self.first_used = False
                self.consumed: list[TokenType] = []

            def peek(self) -> TokenType | None:
                if not self.first_used:
                    return self.first_token
                if self.parser.not_empty():
                    return self.parser.current()
                return None

            def consume(self) -> TokenType:
                if not self.first_used:
                    self.first_used = True
                    self.consumed.append(self.first_token)
                    return self.first_token
                if self.parser.not_empty():
                    tok = self.parser.consume()
                    self.consumed.append(tok)
                    return tok
                raise ArithmeticSyntaxError("Fin de tokens inesperado en stream.")

        stream = StreamAdapter(current, parser)

        def parse_expr(min_prec: int = 0) -> ArithmeticNode:
            left = parse_pref()
            while True:
                cur = stream.peek()
                if cur is None:
                    break
                tt = cur.token
                if not is_binary_op(tt):
                    break
                prec = BINARY_PRECEDENCE[tt]
                if prec < min_prec:
                    break
                op_tok = stream.consume()
                next_prec = prec if is_right_associative(tt) else prec + 1
                right = parse_expr(next_prec)
                left = BinaryOpNode(op_tok, left, right)
            return left

        def parse_pref() -> ArithmeticNode:
            cur = stream.peek()
            if cur is None:
                raise ArithmeticSyntaxError("Fin de tokens inesperado al inicio de operando aritmético.")
            tt = cur.token

            if tt in (Token.PLUS, Token.MINUS):
                op_tok = stream.consume()
                operand = parse_expr(UNARY_PRECEDENCE)
                return UnaryOpNode(op_tok, operand)

            if tt == Token.DECREMENT:
                dec = stream.consume()
                m1 = TokenType(token=Token.MINUS, value="-", line=dec.line - 1, col=dec.col)
                m2 = TokenType(token=Token.MINUS, value="-", line=dec.line - 1, col=dec.col + 1)
                operand = parse_expr(UNARY_PRECEDENCE)
                return UnaryOpNode(m1, UnaryOpNode(m2, operand))

            if tt == Token.INCREMENT:
                inc = stream.consume()
                p1 = TokenType(token=Token.PLUS, value="+", line=inc.line - 1, col=inc.col)
                p2 = TokenType(token=Token.PLUS, value="+", line=inc.line - 1, col=inc.col + 1)
                operand = parse_expr(UNARY_PRECEDENCE)
                return UnaryOpNode(p1, UnaryOpNode(p2, operand))

            if tt == Token.LPAREN:
                lp = stream.consume()
                inner = parse_expr(0)
                nxt = stream.peek()
                if nxt is None or nxt.token != Token.RPAREN:
                    col = nxt.col if nxt else "EOF"
                    line = nxt.line if nxt else "EOF"
                    raise ArithmeticSyntaxError(
                        f"Se esperaba ')' para cerrar paréntesis abierto en lín {lp.line}, col {lp.col}."
                    )
                rp = stream.consume()
                return GroupNode(lp, inner, rp)

            if tt == Token.NUMBER or isinstance(cur.value, (int, float)):
                num_tok = stream.consume()
                return NumberNode(num_tok)

            if self.allow_ident and tt == Token.IDENT:
                var_tok = stream.consume()
                return VariableNode(var_tok)

            raise ArithmeticSyntaxError(
                f"Token inesperado '{cur.value}' ({tt.name}) en lín {cur.line}, col {cur.col}."
            )

        try:
            ast_tree = parse_expr(0)
            tokens = stream.consumed

            # Inyectamos el árbol y el método evaluate en el resultado
            return tokens
        except Exception as exc:
            parser.restore(saved_pos, node=target_node)
            if ignore_errors:
                return None
            err_code = codes.CodeError((2, 1, 1, 0, 1), "Arithmetic.ParseError")
            error.ParserError(
                f"Error al analizar expresión aritmética: {exc}",
                err_code,
                f"Línea {current.line}, columna {current.col}.",
            ).raise_error()

    def __repr__(self) -> str:
        return "ArithmeticExpr()"


CombinatorAdditionalStack.register(ArithmeticExpr)
