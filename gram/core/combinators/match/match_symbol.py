"""
Combinador de Coincidencia de Símbolos y Patrones (`gram.core.combinators.match.match_symbol`).
=============================================================================================
Valida secuencias de caracteres, operadores o patrones textuales mediante expresiones
regulares sobre el valor del token bajo el cursor, con soporte para reetiquetado a CustomToken.
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from gram import config, errors
from gram.core.combinators.base import Combinator
from gram.core.lexer.tokens import CustomToken, TokenType
from gram.utilities import error

if TYPE_CHECKING:
    from gram.core.ast import ASTAnalyzer
    from gram.core.parser.core import Parser


def generador_expr(*parts: Any) -> str:
    """
    Construye una expresión regular a partir de literales y rangos de caracteres.

    Ejemplo:
        generador_expr('#', ['A', 'F'], ['a', 'f'], [0, 9]) -> '#[A-Fa-f0-9]'

    Args:
        *parts: Cadenas literales o tuplas/listas de 2 elementos representando rangos [inicio, fin].

    Returns:
        str: Expresión regular compilable resultante.

    Raises:
        ValueError: Si un componente no es una cadena ni un rango válido de 2 elementos.
    """
    result: list[str] = []
    char_class: list[str] = []

    def flush_class() -> None:
        if char_class:
            result.append("[" + "".join(char_class) + "]")
            char_class.clear()

    for part in parts:
        if isinstance(part, str):
            flush_class()
            result.append(re.escape(part))
            continue

        if isinstance(part, (list, tuple)) and len(part) == 2:
            start, end = part
            if isinstance(start, str) and isinstance(end, str):
                char_class.append(f"{re.escape(start)}-{re.escape(end)}")
                continue

            if isinstance(start, int) and isinstance(end, int):
                char_class.append(f"{start}-{end}")
                continue

        raise ValueError(f"Componente de expresión regular inválido: {part!r}")

    flush_class()
    return "".join(result)


class MatchSeqSymbol(Combinator):
    """
    ES:
        Combinador que evalúa el valor textual del token bajo el cursor contra un patrón regex,
        una lista de símbolos permitidos o una cadena literal.

    EN:
        Combinator evaluating token text against a regex pattern, symbol list, or literal string.
    """

    def __init__(
        self,
        pattern: str | None = None,
        symbols: list[str] | None = None,
        regex: str | None = None,
        custom_token_name: str | None = None,
        is_pattern: bool = True,
        case_sensitive: bool = False,
        raw: bool = False,
    ) -> None:
        """
        Inicializa el combinador de patrón de símbolos.

        Args:
            pattern: Patrón o texto literal a comparar.
            symbols: Lista alternativa de símbolos candidatos (combinados mediante '|').
            regex: Expresión regular explícita (prevalece sobre pattern).
            custom_token_name: Nombre opcional para reetiquetar el token con CustomToken al coincidir.
            is_pattern: Si False, escapa el texto para coincidencia literal.
            case_sensitive: Si False, ignora diferencias entre mayúsculas y minúsculas.
            raw: Si True, opera sin normalizaciones adicionales.
        """
        if regex is not None:
            actual_pattern = regex
            is_pattern = True
        elif symbols is not None:
            actual_pattern = "|".join(re.escape(s) for s in symbols)
            is_pattern = True
        elif pattern is not None:
            actual_pattern = pattern
        else:
            actual_pattern = ""

        self.pattern = actual_pattern
        self.symbols = symbols
        self.regex = regex
        self.custom_token_name = custom_token_name
        self.is_pattern = is_pattern
        self.case_sensitive = case_sensitive
        self.raw = raw

        flags = 0 if case_sensitive else re.IGNORECASE
        pattern_str = actual_pattern if is_pattern else re.escape(actual_pattern)
        self._regex = re.compile(pattern_str, flags)

    def parse(
        self,
        analyzer: ASTAnalyzer | Parser | Any,
        current: TokenType | None = None,
        ignore_errors: bool = False,
    ) -> TokenType | None:
        """
        Evalúa el valor del token actual contra la expresión regular configurada.

        Args:
            analyzer: Instancia activa del analizador sintáctico o parser.
            current: Token posicionado bajo el cursor, o None para consumir del parser.
            ignore_errors: Si True, no genera excepciones ante discrepancias.

        Returns:
            TokenType | None: El token evaluado (posiblemente reetiquetado) si coincide; None en caso contrario.

        Raises:
            ParserError: Si el valor no cumple el patrón e ignore_errors es False.
        """
        parser = self._get_parser(analyzer)
        target_node = self._get_node(analyzer)

        if target_node and getattr(config, "PARSER_ADD_INFO", True):
            target_node.note(
                f"MatchSeqSymbol: evaluando patrón {self.pattern!r}",
                "Normal",
            )

        checkpoint = parser.savepoint(node=target_node)

        if current is None:
            if not parser.not_empty():
                if not ignore_errors:
                    if target_node and getattr(config, "PARSER_ADD_ERROR", True):
                        target_node.note(
                            f"Error sintáctico: se esperaba patrón {self.pattern!r} pero se alcanzó EOF",
                            "Error",
                        )
                    error.ParserError(
                        "Símbolo no coincide",
                        errors.PARSER_EARLY_EOF,
                        f"Se esperaba coincidencia con patrón '{self.pattern}' pero se alcanzó EOF.",
                    ).raise_error()
                return None
            tok = parser.consume(node=target_node)
        else:
            tok = current

        val_str = str(tok.value) if tok.value is not None else ""
        match = self._regex.fullmatch(val_str)

        if not match:
            parser.restore(checkpoint, node=target_node)

            if target_node and getattr(config, "PARSER_ADD_INFO", True):
                target_node.note(
                    f"Patrón {self.pattern!r} no coincidió con {val_str!r}",
                    "Warn",
                )

            if not ignore_errors:
                if target_node and getattr(config, "PARSER_ADD_ERROR", True):
                    target_node.note(
                        f"Error sintáctico: {val_str!r} no cumple el patrón {self.pattern!r}",
                        "Error",
                    )
                error.ParserError(
                    "Símbolo no coincide",
                    errors.PARSER_UNEXPECTED_TOKEN,
                    f"El valor {val_str!r} no coincide con el patrón esperado {self.pattern!r}.",
                    f"En línea {tok.line}, columna {tok.col}.",
                ).raise_error()

            return None

        # Si current fue pasado explícitamente y el parser aún apuntaba a él, avanzar cursor físico
        if current is not None and parser.not_empty() and parser.tokens[parser.pos] is current:
            parser.advance()

        if self.custom_token_name:
            tok.token = CustomToken(self.custom_token_name)

        if target_node and getattr(config, "PARSER_ADD_INFO", True):
            target_node.note(
                f"MatchSeqSymbol exitoso: {val_str!r}",
                "Success",
            )

        return tok

    def __repr__(self) -> str:
        return f"MatchSeqSymbol({self.pattern!r})"


# Alias de conveniencia
MatchSymbol = MatchSeqSymbol


__all__ = [
    "MatchSeqSymbol",
    "MatchSymbol",
    "generador_expr",
]
