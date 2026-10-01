"""
Combinador Separator (`gram.core.combinators.separator`).
=========================================================
Proporciona el combinador `Separator` (y alias `Sep`) para procesar secuencias
de elementos delimitados por separadores léxicos (por ejemplo listas separadas
por comas, parámetros separados por punto y coma, etc.).
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Iterable, Sequence

from gram import config, errors
from gram.core.combinators.base import Combinator
from gram.core.combinators.item import Item, ItemResult, Literal
from gram.core.combinators.match import MatchKeyword, MatchSeqSymbol, MatchToken
from gram.core.combinators.optional import OptResult
from gram.core.lexer.tokens import MAP_SYMBOLS, Token, TokenType
from gram.utilities import error

if TYPE_CHECKING:
    from gram.core.ast import ASTAnalyzer
    from gram.core.parser.core import Parser


class SeparatorResult(list):
    """
ES:
    Resultado de la evaluación del combinador Separator().
    Hereda de list y aporta metadatos sobre separador final colgante (trailing).

EN:
    Result container for Separator combinator evaluation, subclassing list.
"""
    is_match: bool = True

    def __init__(
        self,
        items: Iterable[Any] | None = None,
        ended_token: TokenType | None = None,
        trailing_separator: bool = False,
    ) -> None:
        super().__init__(items if items is not None else [])
        self.ended_token = ended_token
        self.trailing_separator = trailing_separator

    def to_list(self) -> list[Any]:
        """
        Convierte recursivamente a lista nativa de Python.

        Returns:
            list[Any]: Lista pura recursivamente normalizada.
        """
        result = []
        for item in self:
            if isinstance(item, (SeparatorResult, ItemResult)):
                result.append(item.to_list())
            else:
                result.append(item)
        return result

    @property
    def items(self) -> list[Any]:
        """Retorna los elementos como una lista nativa."""
        return list(self)

    def __bool__(self) -> bool:
        """Verdadero si contiene elementos."""
        return len(self) > 0

    def __repr__(self) -> str:
        return f"SeparatorResult({super().__repr__()})"


def _normalize_value(val: Any) -> Combinator:
    """Normaliza un valor arbitrario al combinador adecuado."""
    if isinstance(val, Combinator):
        return val
    if isinstance(val, Token):
        return MatchToken(val)
    if isinstance(val, str):
        tok_enum = Token.from_string(val)
        if tok_enum is not None:
            return MatchToken(tok_enum)
        if val in MAP_SYMBOLS:
            return MatchToken(MAP_SYMBOLS[val])
        return Literal(val)
    if isinstance(val, (int, float)):
        return Literal(val)
    if isinstance(val, type) and issubclass(val, Combinator):
        return val()
    raise TypeError(f"Valor no permitido en Separator: {val!r}")


class Separator(Combinator):
    """
ES:
    Combinador que procesa secuencias de elementos delimitados por un separador.
    Soporta separadores finales opcionales (trailing separator) y límites min/max.

    EN:
        Delimited repetition combinator matching elements separated by a delimiter token.
    """
    header_class: bool = True

    def __init__(
        self,
        values: Sequence[Any] | Combinator | Token | str,
        sep: Combinator | Token | str = Token.COMMA,
        min: int = 0,
        max: int | None = None,
        allow_trailing: bool = True,
    ) -> None:
        """
        Inicializa el combinador de secuencias con separador.

        Args:
            values: Combinador(es) esperados para los valores de la secuencia.
            sep: Combinador, Token o símbolo usado como separador (por defecto Token.COMMA).
            min: Cantidad mínima obligatoria de elementos.
            max: Cantidad máxima permitida de elementos (o None para ilimitado).
            allow_trailing: Permite un separador colgante al final de la secuencia.
        """
        self.header_class: bool = True
        if isinstance(values, (list, tuple)):
            self.values = tuple(_normalize_value(v) for v in values)
        else:
            self.values = (_normalize_value(values),)
        self.sep = _normalize_value(sep)
        self.min = min
        self.max = max
        self.allow_trailing = allow_trailing

    def _match_val(self, analyzer: Any, token: TokenType | None) -> Any:
        """Intenta hacer coincidir el token con alguna de las opciones de valor."""
        parser = self._get_parser(analyzer)
        target_node = self._get_node(analyzer)
        saved = parser.savepoint(node=target_node)

        for val_comb in self.values:
            parser.restore(saved, node=target_node)
            try:
                res = self._dispatch_sub(val_comb, analyzer, token, ignore_errors=True)
            except error.ParserError:
                res = None

            if res is None:
                continue
            if isinstance(res, OptResult) and not res.matched:
                continue
            return res

        parser.restore(saved, node=target_node)
        return None

    def parse(
        self,
        analyzer: ASTAnalyzer | Parser | Any,
        current: TokenType | None = None,
        ignore_errors: bool = False,
    ) -> SeparatorResult | None:
        """
        Ejecuta el análisis sintáctico de la secuencia delimitada por separadores.

        Args:
            analyzer: Analizador sintáctico o parser activo.
            current: Token actual posicionado o None.
            ignore_errors: Si True, suprime errores sintácticos.

        Returns:
            SeparatorResult con los elementos extraídos, o None si no cumple el mínimo.
        """
        parser = self._get_parser(analyzer)
        target_node = self._get_node(analyzer)

        if target_node and getattr(config, "PARSER_ADD_INFO", True):
            target_node.note("Iniciando evaluación de Separator", "Normal")

        initial_checkpoint = parser.savepoint(node=target_node)
        items = []
        trailing_sep = False

        first_val = self._match_val(analyzer, current)
        if first_val is None:
            parser.restore(initial_checkpoint, node=target_node)
            if self.min > 0:
                if not ignore_errors:
                    curr_tok = current if current else parser.peek()
                    tok_info = f" en {curr_tok}" if curr_tok else ""
                    error.ParserError(
                        "Elementos insuficientes",
                        errors.COMBINATOR_FAILED,
                        f"Separator requería al menos {self.min} elementos pero no se encontró ninguno{tok_info}.",
                    ).raise_error()
                return None
            return SeparatorResult([], trailing_separator=False)

        items.append(first_val)

        while True:
            if self.max is not None and len(items) >= self.max:
                break
            if not parser.not_empty():
                break

            sep_checkpoint = parser.savepoint(node=target_node)
            try:
                sep_res = self._dispatch_sub(self.sep, analyzer, None, ignore_errors=True)
            except error.ParserError:
                sep_res = None

            if sep_res is None or (isinstance(sep_res, OptResult) and not sep_res.matched):
                parser.restore(sep_checkpoint, node=target_node)
                break

            if not parser.not_empty():
                if self.allow_trailing:
                    trailing_sep = True
                    break
                else:
                    parser.restore(sep_checkpoint, node=target_node)
                    break

            val_checkpoint = parser.savepoint(node=target_node)
            val_res = self._match_val(analyzer, None)

            if val_res is not None:
                items.append(val_res)
                trailing_sep = False
            else:
                if self.allow_trailing:
                    parser.restore(val_checkpoint, node=target_node)
                    trailing_sep = True
                    break
                else:
                    parser.restore(sep_checkpoint, node=target_node)
                    break

        if len(items) < self.min:
            parser.restore(initial_checkpoint, node=target_node)
            if not ignore_errors:
                error.ParserError(
                    "Elementos insuficientes",
                    errors.COMBINATOR_FAILED,
                    f"Se requerían al menos {self.min} elementos en Separator (obtenidos: {len(items)}).",
                ).raise_error()
            return None

        return SeparatorResult(items, trailing_separator=trailing_sep)

    def __repr__(self) -> str:
        return f"Separator(values={self.values!r}, sep={self.sep!r})"


Sep = Separator

__all__ = ["Sep", "Separator", "SeparatorResult"]