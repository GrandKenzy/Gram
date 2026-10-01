"""
Combinadores ChainL y ChainR para el plugin Expressions de Gram Framework.
==========================================================================
Provee combinadores de alto nivel para analizar secuencias de elementos
separados por operadores con asociatividad explícita:
- ChainL: Asociatividad izquierda (left-associative): a - b - c -> ((a - b) - c)
- ChainR: Asociatividad derecha (right-associative): a = b = c -> (a = (b = c)) o 2 ^ 3 ^ 4
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from gram.core.ast import ASTAnalyzer
    from gram.core.lexer.tokens import TokenType
    from gram.utilities.info import Node

from gram import config
from gram.core.combinators.base import Combinator
from gram.core.combinators.mods import register_custom_mod
from gram.core.lexer.tokens import Token
from gram.errors import codes
from gram.utilities import error
from gram.plugins.source.expressions.evaluator import BinaryOpNode, ArithmeticNode


class ChainL(Combinator):
    """
    Combinador de asociatividad izquierda (Left-Associative Chaining).
    Parsea elementos separados por operadores y los agrupa hacia la izquierda:
        a - b - c  ->  ((a - b) - c)

    Parámetros:
        element: Combinador o regla del elemento / operando.
        operator: Combinador del operador separador (ej. Alt(MatchToken(Token.PLUS), MatchToken(Token.MINUS))).
        reducer: Función reductora opcional f(left, op, right). Por defecto genera un BinaryOpNode.
    """
    code: int = 7010
    name: str = "ChainL"
    description: str = "Parsea elementos separados por operadores con asociatividad izquierda: a - b - c -> ((a - b) - c)."
    header_class: bool = True

    def __init__(
        self,
        element: Any,
        operator: Any,
        reducer: Callable[[Any, Any, Any], Any] | None = None,
    ):
        super().__init__()
        self.header_class = True
        self.element = element
        self.operator = operator
        self.reducer = reducer

    def _apply_reduce(self, left: Any, op: Any, right: Any) -> Any:
        if self.reducer is not None:
            return self.reducer(left, op, right)
        return BinaryOpNode(op, left, right)

    def parse(
        self,
        analyzer: ASTAnalyzer,
        current: TokenType,
        ignore_errors: bool = False,
    ) -> Any:
        target_node = self._get_node(analyzer)
        parser = analyzer.parser
        saved_pos = parser.pos
        saved_level = getattr(analyzer, "current_level", 0)

        # 1. Parsear el primer elemento
        try:
            left = analyzer.process_combinator(
                self.element,
                current,
                ignore_errors=ignore_errors,
            )
        except Exception:
            left = None

        if left is None:
            parser.restore(saved_pos, node=target_node)
            if hasattr(analyzer, "current_level"):
                analyzer.current_level = saved_level
            if ignore_errors:
                return None
            err_code = codes.CodeError((2, 1, 1, 0, 1), "ChainL.ElementExpected")
            error.ParserError(
                f"ChainL esperaba un operando inicial pero falló en '{current.value}'.",
                err_code,
                f"Línea {current.line}, Columna {current.col}",
            ).raise_error()

        # 2. Plegado secuencial hacia la izquierda mientras haya operador + elemento
        while parser.not_empty():
            loop_pos = parser.pos
            loop_level = getattr(analyzer, "current_level", 0)

            op_token = parser.consume(node=target_node)
            try:
                op_res = analyzer.process_combinator(
                    self.operator,
                    op_token,
                    ignore_errors=True,
                )
            except Exception:
                op_res = None

            if op_res is None:
                # El siguiente token no es el operador esperado; revertir y salir con éxito
                parser.restore(loop_pos, node=target_node)
                if hasattr(analyzer, "current_level"):
                    analyzer.current_level = loop_level
                break

            if not parser.not_empty():
                parser.restore(loop_pos, node=target_node)
                if hasattr(analyzer, "current_level"):
                    analyzer.current_level = loop_level
                if ignore_errors:
                    break
                err_code = codes.CodeError((2, 1, 1, 0, 1), "ChainL.IncompleteChain")
                error.ParserError(
                    f"ChainL: se esperaba un operando después del operador '{op_token.value}'.",
                    err_code,
                    f"Línea {op_token.line}, Columna {op_token.col}",
                ).raise_error()

            next_elem_token = parser.consume(node=target_node)
            try:
                right_res = analyzer.process_combinator(
                    self.element,
                    next_elem_token,
                    ignore_errors=ignore_errors,
                )
            except Exception:
                right_res = None

            if right_res is None:
                parser.restore(loop_pos, node=target_node)
                if hasattr(analyzer, "current_level"):
                    analyzer.current_level = loop_level
                if ignore_errors:
                    break
                err_code = codes.CodeError((2, 1, 1, 0, 1), "ChainL.ElementExpectedAfterOp")
                error.ParserError(
                    f"ChainL: operando no válido tras operador '{op_token.value}'.",
                    err_code,
                    f"Línea {next_elem_token.line}, Columna {next_elem_token.col}",
                ).raise_error()

            left = self._apply_reduce(left, op_res, right_res)

        if target_node and config.PARSER_ADD_INFO:
            target_node.note(f"ChainL completado exitosamente: {left}", "Success")

        return left

    def __repr__(self) -> str:
        return f"ChainL(element={self.element!r}, operator={self.operator!r})"


class ChainR(Combinator):
    """
    Combinador de asociatividad derecha (Right-Associative Chaining).
    Parsea elementos separados por operadores y los agrupa hacia la derecha:
        a = b = c  ->  (a = (b = c))
        2 ^ 3 ^ 4  ->  (2 ^ (3 ^ 4))

    Parámetros:
        element: Combinador o regla del elemento / operando.
        operator: Combinador del operador separador (ej. MatchToken(Token.POW) o MatchToken(Token.ASSIGN)).
        reducer: Función reductora opcional f(left, op, right). Por defecto genera un BinaryOpNode.
    """
    code: int = 7011
    name: str = "ChainR"
    description: str = "Parsea elementos separados por operadores con asociatividad derecha: a = b = c -> (a = (b = c))."
    header_class: bool = True

    def __init__(
        self,
        element: Any,
        operator: Any,
        reducer: Callable[[Any, Any, Any], Any] | None = None,
    ):
        super().__init__()
        self.header_class = True
        self.element = element
        self.operator = operator
        self.reducer = reducer

    def _apply_reduce(self, left: Any, op: Any, right: Any) -> Any:
        if self.reducer is not None:
            return self.reducer(left, op, right)
        return BinaryOpNode(op, left, right)

    def parse(
        self,
        analyzer: ASTAnalyzer,
        current: TokenType,
        ignore_errors: bool = False,
    ) -> Any:
        target_node = self._get_node(analyzer)
        parser = analyzer.parser
        saved_pos = parser.pos
        saved_level = getattr(analyzer, "current_level", 0)

        # 1. Parsear el primer elemento
        try:
            first_elem = analyzer.process_combinator(
                self.element,
                current,
                ignore_errors=ignore_errors,
            )
        except Exception:
            first_elem = None

        if first_elem is None:
            parser.restore(saved_pos, node=target_node)
            if hasattr(analyzer, "current_level"):
                analyzer.current_level = saved_level
            if ignore_errors:
                return None
            err_code = codes.CodeError((2, 1, 1, 0, 1), "ChainR.ElementExpected")
            error.ParserError(
                f"ChainR esperaba un operando inicial pero falló en '{current.value}'.",
                err_code,
                f"Línea {current.line}, Columna {current.col}",
            ).raise_error()

        elements: list[Any] = [first_elem]
        operators: list[Any] = []

        # 2. Recolectar la secuencia completa de operadores y elementos
        while parser.not_empty():
            loop_pos = parser.pos
            loop_level = getattr(analyzer, "current_level", 0)

            op_token = parser.consume(node=target_node)
            try:
                op_res = analyzer.process_combinator(
                    self.operator,
                    op_token,
                    ignore_errors=True,
                )
            except Exception:
                op_res = None

            if op_res is None:
                parser.restore(loop_pos, node=target_node)
                if hasattr(analyzer, "current_level"):
                    analyzer.current_level = loop_level
                break

            if not parser.not_empty():
                parser.restore(loop_pos, node=target_node)
                if hasattr(analyzer, "current_level"):
                    analyzer.current_level = loop_level
                if ignore_errors:
                    break
                err_code = codes.CodeError((2, 1, 1, 0, 1), "ChainR.IncompleteChain")
                error.ParserError(
                    f"ChainR: se esperaba un operando después del operador '{op_token.value}'.",
                    err_code,
                    f"Línea {op_token.line}, Columna {op_token.col}",
                ).raise_error()

            next_elem_token = parser.consume(node=target_node)
            try:
                right_res = analyzer.process_combinator(
                    self.element,
                    next_elem_token,
                    ignore_errors=ignore_errors,
                )
            except Exception:
                right_res = None

            if right_res is None:
                parser.restore(loop_pos, node=target_node)
                if hasattr(analyzer, "current_level"):
                    analyzer.current_level = loop_level
                if ignore_errors:
                    break
                err_code = codes.CodeError((2, 1, 1, 0, 1), "ChainR.ElementExpectedAfterOp")
                error.ParserError(
                    f"ChainR: operando no válido tras operador '{op_token.value}'.",
                    err_code,
                    f"Línea {next_elem_token.line}, Columna {next_elem_token.col}",
                ).raise_error()

            operators.append(op_res)
            elements.append(right_res)

        # 3. Plegado hacia la derecha (Right-associative fold)
        acc = elements[-1]
        for i in range(len(operators) - 1, -1, -1):
            acc = self._apply_reduce(elements[i], operators[i], acc)

        if target_node and config.PARSER_ADD_INFO:
            target_node.note(f"ChainR completado exitosamente: {acc}", "Success")

        return acc

    def __repr__(self) -> str:
        return f"ChainR(element={self.element!r}, operator={self.operator!r})"


# Registro oficial como Custom Mods en Gram
register_custom_mod(ChainL)
register_custom_mod(ChainR)

__all__ = ["ChainL", "ChainR"]
