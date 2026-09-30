"""
EN:
    Item and Literal Combinators (`gram.core.combinators.item`).
    ============================================================
    Provides the `Item` combinator for grouping atomic sequences of fixed match
    combinators (Match/Literal) and the `Literal` combinator for validating direct
    primitive token literal values.

ES:
    Combinadores Item y Literal (`gram.core.combinators.item`).
    ==========================================================
    Proporciona el combinador `Item` para agrupar secuencias atómicas de combinadores
    de coincidencia fija (Match/Literal) y el combinador `Literal` para validar
    valores literales directos de tokens.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Iterable

from gram import config, errors
from gram.core.combinators.base import Combinator
from gram.core.lexer.tokens import Token, TokenType
from gram.utilities import error

if TYPE_CHECKING:
    from gram.core.ast import ASTAnalyzer
    from gram.core.parser.core import Parser

_ANY_LITERAL = object()


class ItemResult(list):
    """
    EN:
        Evaluation result container for Item() combinator.
        Inherits from Python's built-in list to behave natively as a list,
        providing ergonomic access utilities (first, last, to_list).

    ES:
        Resultado de la evaluación del combinador Item().
        Hereda de list para comportarse de forma nativa como una lista en Python,
        proporcionando utilidades de acceso ergonómico (first, last, to_list).
    """

    _is_item_result: bool = True
    is_match: bool = True

    def __init__(self, items: Iterable[Any] | None = None) -> None:
        super().__init__(items if items is not None else [])

    def to_list(self) -> list[Any]:
        """
        EN: Recursively convert into standard native Python list.
        ES: Convierte recursivamente a lista estándar de Python.

        Returns:
            list[Any]: Pure unwrapped Python list.
        """
        result: list[Any] = []
        for item in self:
            if isinstance(item, ItemResult):
                result.append(item.to_list())
            else:
                result.append(item)
        return result

    @property
    def items(self) -> list[Any]:
        """
        EN: Return a copy as standard Python list.
        ES: Retorna una copia como lista de Python.
        """
        return list(self)

    @property
    def first(self) -> Any:
        """
        EN: First element or None if empty.
        ES: Primer elemento o None si la lista está vacía.
        """
        return self[0] if self else None

    @property
    def last(self) -> Any:
        """
        EN: Last element or None if empty.
        ES: Último elemento o None si la lista está vacía.
        """
        return self[-1] if self else None

    def __bool__(self) -> bool:
        """
        EN: True if container holds at least one element.
        ES: Verdadero si contiene al menos un elemento.
        """
        return len(self) > 0

    def __repr__(self) -> str:
        return f"ItemResult({super().__repr__()})"


class Item(Combinator):
    """
    EN:
        Combinator grouping Match combinators into an atomic sequential unit.
        If any element fails to match, fully rewinds parser state (atomic backtracking).

    ES:
        Combinador que agrupa combinadores Match en una unidad atómica secuencial.
        Si cualquiera no coincide, retrocede completamente el parser (backtracking atómico).
    """

    def __init__(self, *matchs: Combinator) -> None:
        """
        EN: Initialize atomic Item sequence with match combinators.
        ES: Inicializa la secuencia atómica Item con combinadores de coincidencia.

        Args:
            *matchs: Combinators that must match in exact sequence.
                     Combinadores que deben coincidir en secuencia exacta.
        """
        self.matchs: tuple[Combinator, ...] = matchs
        self.combinators: tuple[Combinator, ...] = matchs

    def items(self) -> tuple[Combinator, ...]:
        """
        EN: Return configured match combinators.
        ES: Retorna los combinadores configurados.
        """
        return self.matchs

    def __iter__(self):
        return iter(self.matchs)

    def __len__(self) -> int:
        return len(self.matchs)

    def parse(
        self,
        analyzer: ASTAnalyzer | Parser | Any,
        current: TokenType | None = None,
        ignore_errors: bool = False,
    ) -> ItemResult | None:
        """
        EN: Execute atomic evaluation of the match sequence.
        ES: Ejecuta la evaluación atómica de la secuencia de combinadores.

        Args:
            analyzer: Active syntax analyzer or Parser instance.
                      Analizador sintáctico o parser activo.
            current: Current token available under cursor or None.
                     Token actual posicionado o None.
            ignore_errors: If True, suppress error exceptions on mismatch.
                           Si True, no levanta excepciones ante fallos.

        Returns:
            ItemResult with matched elements, or None on failure.
            ItemResult con los resultados coincidentes, o None si falló la secuencia.
        """
        parser = self._get_parser(analyzer)
        target_node = self._get_node(analyzer)

        if target_node and getattr(config, "PARSER_ADD_INFO", True):
            target_node.note(
                f"Item iniciado con {len(self.matchs)} matchs",
                "Normal",
            )

        if not self.matchs:
            return ItemResult([])

        checkpoint = parser.savepoint(node=target_node)
        results: list[Any] = []

        try:
            for idx, match_comb in enumerate(self.matchs):
                active_token = current if idx == 0 else None

                res = self._dispatch_sub(
                    match_comb,
                    analyzer,
                    active_token,
                    ignore_errors=True,
                )

                if res is None:
                    parser.restore(checkpoint, node=target_node)
                    if not ignore_errors:
                        curr_tok = parser.peek()
                        tok_info = f" en {curr_tok}" if curr_tok else ""
                        error.ParserError(
                            "Item incompleto",
                            errors.COMBINATOR_FAILED,
                            f"Fallo en componente {idx + 1} de Item({match_comb!r}){tok_info}.",
                        ).raise_error()
                    return None

                results.append(res)

            if target_node and getattr(config, "PARSER_ADD_INFO", True):
                target_node.note(
                    f"Item completado con éxito ({len(results)} elementos)",
                    "Success",
                )

            return ItemResult(results)

        except error.ParserError:
            parser.restore(checkpoint, node=target_node)
            raise

    def __repr__(self) -> str:
        items = ", ".join(repr(m) for m in self.matchs)
        return f"Item({items})"


class Literal(Combinator):
    """
    EN:
        Combinator matching the literal value of current token against an expected primitive.
        Reserved keywords (Token.KEYWORD) never match against a Literal.

    ES:
        Combinador que evalúa la coincidencia del valor literal del token actual
        con un valor esperado (número, cadena o booleano). Las palabras clave (KEYWORD)
        nunca coinciden con un Literal.
    """

    def __init__(self, literal: Any = _ANY_LITERAL) -> None:
        """
        EN: Initialize literal matching with target primitive value or wildcard.
        ES: Inicializa la coincidencia de valor literal con valor esperado o comodín.

        Args:
            literal: Target literal value or wildcard (_ANY_LITERAL).
                     Valor esperado o comodín (_ANY_LITERAL si no se especifica).
        """
        self.literal: Any = literal

    def parse(
        self,
        analyzer: ASTAnalyzer | Parser | Any,
        current: TokenType | None = None,
        ignore_errors: bool = False,
    ) -> TokenType | None:
        """
        EN: Evaluate whether the current token possesses the expected literal value.
        ES: Evalúa si el token actual posee el valor literal esperado.

        Args:
            analyzer: Active syntax analyzer or Parser instance.
                      Analizador sintáctico o parser activo.
            current: Token to test or None to consume from parser.
                     Token a comparar o None para consumir del parser.
            ignore_errors: If True, suppress error exceptions on mismatch.
                           Si True, no levanta excepciones ante discrepancias.

        Returns:
            Matched TokenType or None on failure.
            TokenType si coincide el valor literal, o None en caso contrario.
        """
        parser = self._get_parser(analyzer)
        target_node = self._get_node(analyzer)

        if target_node and getattr(config, "PARSER_ADD_INFO", True):
            target_node.note(f"Procesando Literal: {self.literal!r}", "Normal")

        checkpoint = parser.savepoint(node=target_node)

        if current is None:
            if not parser.not_empty():
                if not ignore_errors:
                    if target_node and getattr(config, "PARSER_ADD_ERROR", True):
                        target_node.note("Error: se esperaba Literal pero se alcanzó EOF", "Error")
                    error.ParserError(
                        "Token no disponible",
                        errors.PARSER_EARLY_EOF,
                        "No hay un token disponible para evaluar el literal.",
                    ).raise_error()
                return None
            tok = parser.consume(node=target_node)
        else:
            tok = current

        # Las palabras reservadas (KEYWORD) nunca coinciden con un Literal
        if tok.token == Token.KEYWORD or getattr(tok.token, "name", "") == "KEYWORD":
            parser.restore(checkpoint, node=target_node)
            if not ignore_errors:
                if target_node and getattr(config, "PARSER_ADD_ERROR", True):
                    target_node.note(f"Literal no admite KEYWORD: {tok.value!r}", "Error")
                error.ParserError(
                    "Literal no admite palabra clave",
                    errors.PARSER_UNEXPECTED_TOKEN,
                    f"Literal no puede coincidir con una palabra reservada (KEYWORD): {tok.value!r}.",
                ).raise_error()
            return None

        # Comparación del valor literal
        if not self._match_value(tok.value):
            parser.restore(checkpoint, node=target_node)
            if target_node and getattr(config, "PARSER_ADD_INFO", True):
                target_node.note(
                    f"Literal rechazado: se esperaba {self.literal!r}, se recibió {tok.value!r}",
                    "Warn",
                )
            if not ignore_errors:
                if target_node and getattr(config, "PARSER_ADD_ERROR", True):
                    target_node.note(
                        f"Error: se esperaba literal {self.literal!r}, se recibió {tok.value!r}",
                        "Error",
                    )
                error.ParserError(
                    "Literal incorrecto",
                    errors.PARSER_UNEXPECTED_TOKEN,
                    f"Literal incorrecto: se esperaba {self.literal!r}, se recibió {tok.value!r}.",
                    f"En línea {tok.line}, columna {tok.col}.",
                ).raise_error()
            return None

        # Si current fue pasado explícitamente y el parser aún apuntaba a él, avanzar cursor físico
        if current is not None and parser.not_empty() and parser.tokens[parser.pos] is current:
            parser.advance()

        if target_node and getattr(config, "PARSER_ADD_INFO", True):
            target_node.note(f"Literal aceptado: {tok.value!r}", "Success")

        return tok

    def _match_value(self, token_value: Any) -> bool:
        """
        EN: Check equality between token primitive value and expected literal.
        ES: Comprueba igualdad entre el valor del token y el esperado.
        """
        if self.literal is _ANY_LITERAL:
            return True
        if token_value == self.literal:
            return True
        if isinstance(self.literal, (int, float)) and isinstance(token_value, (int, float)):
            return self.literal == token_value
        return False

    def __repr__(self) -> str:
        if self.literal is _ANY_LITERAL:
            return "Literal()"
        return f"Literal({self.literal!r})"


__all__ = [
    "Item",
    "ItemResult",
    "Literal",
]
