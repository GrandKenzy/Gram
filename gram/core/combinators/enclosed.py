"""
EN:
    Enclosed and Bracketed Combinator (`gram.core.combinators.enclosed`).
    =====================================================================
    Wraps an inner content combinator between opening and closing delimiter tokens
    and automatically activates the parser's *bracket-aware* mode during content analysis.

    In bracket-aware mode, NEWLINE, INDENT, and DEDENT tokens are automatically
    skipped during token consumption, enabling multi-line expressions inside parentheses,
    brackets, and braces.

ES:
    Combinador Enclosed / Bracketed (`gram.core.combinators.enclosed`).
    ===================================================================
    Envuelve un combinador de contenido entre un par de tokens delimitadores
    (apertura y cierre) y activa automáticamente el modo *bracket-aware* del
    parser durante el análisis del contenido interior.

    En modo bracket-aware los tokens NEWLINE, INDENT y DEDENT se omiten
    automáticamente al consumir, lo que permite formateo libre dentro de
    paréntesis, corchetes y llaves.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from gram import config, errors
from gram.core.combinators.base import Combinator
from gram.core.lexer.tokens import Token, TokenType
from gram.utilities import error

if TYPE_CHECKING:
    from gram.core.ast import ASTAnalyzer
    from gram.core.parser.core import Parser

# Mapeos de strings de delimitador a Token canónico
_OPEN_MAP: dict[str, Token] = {
    "(": Token.LPAREN,
    "[": Token.LBRACKET,
    "{": Token.LBRACE,
}
_CLOSE_MAP: dict[str, Token] = {
    ")": Token.RPAREN,
    "]": Token.RBRACKET,
    "}": Token.RBRACE,
}


def _resolve_delimiter(delim: Token | str, mapping: dict[str, Token]) -> Token:
    """
    EN: Convert a delimiter (Token or str) into its corresponding canonical Token enum.
    ES: Convierte un delimitador (Token o str) al Token canónico correspondiente.
    """
    if isinstance(delim, Token):
        return delim
    resolved = mapping.get(delim)
    if resolved is None:
        raise ValueError(
            f"Delimitador desconocido: {delim!r}. Valores permitidos: {list(mapping)}"
        )
    return resolved


class Enclosed(Combinator):
    """
    EN:
        Combinator evaluating inner content enclosed within opening and closing bracket delimiters.
        Activates *bracket-aware* mode during inner content parsing to automatically suppress
        newlines and indentations in collections, argument lists, and tuples.

    ES:
        Combinador que evalúa un contenido delimitado por tokens de apertura y cierre.
        Activa el modo *bracket-aware* durante el análisis del contenido para suprimir
        automáticamente saltos de línea e indentaciones en colecciones y listas de argumentos.
    """

    def __init__(
        self,
        open: Token | str,
        content: Combinator,
        close: Token | str,
        skip_whitespace: bool = True,
    ) -> None:
        """
        EN: Initialize Enclosed combinator with opening delimiter, content, and closing delimiter.
        ES: Inicializa el combinador Enclosed con delimitador de apertura, contenido y cierre.

        Args:
            open: Opening token or string delimiter ('(', '[', '{' or Token enum).
                  Token o string de apertura ('(', '[', '{' o Token enum).
            content: Child combinator evaluated within the enclosing pair.
                     Combinador que se evalúa dentro del par delimitador.
            close: Matching closing token or string delimiter (')', ']', '}').
                   Token o string de cierre correspondiente (')', ']', '}').
            skip_whitespace: If True, activates bracket-aware mode suppressing NEWLINE/INDENT/DEDENT.
                             Si True, activa el modo bracket-aware suprimiendo saltos e indentación.
        """
        self.open_token: Token = _resolve_delimiter(open, _OPEN_MAP)
        self.close_token: Token = _resolve_delimiter(close, _CLOSE_MAP)
        self.content: Combinator = content
        self.skip_whitespace: bool = skip_whitespace

    def parse(
        self,
        analyzer: ASTAnalyzer | Parser | Any,
        current: TokenType | None = None,
        ignore_errors: bool = False,
    ) -> Any:
        """
        EN: Evaluate content enclosed between delimiter tokens.
        ES: Evalúa el contenido encerrado entre los tokens delimitadores.

        Args:
            analyzer: Active syntax analyzer or Parser instance.
                      Analizador sintáctico o parser activo.
            current: Current token positioned (expected opening) or None.
                     Token actual posicionado (apertura esperada) o None.
            ignore_errors: If True, suppress exceptions on mismatch.
                           Si True, suprime excepciones ante discrepancias.

        Returns:
            Result of inner content combinator, or None on failure.
            Resultado del combinador de contenido, o None si no coincidió.
        """
        parser = self._get_parser(analyzer)
        target_node = self._get_node(analyzer)
        checkpoint = parser.savepoint(node=target_node)

        # 1. Validar token de apertura
        if current is None:
            if not parser.not_empty():
                if not ignore_errors:
                    error.ParserError(
                        "Enclosed: EOF inesperado antes de apertura",
                        errors.PARSER_EARLY_EOF,
                        f"Se esperaba '{self.open_token.name}' pero se alcanzó el fin del archivo.",
                    ).raise_error()
                return None
            open_tok = parser.consume(node=target_node)
        else:
            open_tok = current
            if parser.not_empty() and parser.tokens[parser.pos] is current:
                parser.advance()

        if open_tok.token != self.open_token:
            parser.restore(checkpoint, node=target_node)
            return None

        if target_node and getattr(config, "PARSER_ADD_INFO", True):
            target_node.note(f"Enclosed: apertura '{self.open_token.name}' aceptada", "Normal")

        # 2. Análisis del contenido interior
        if self.skip_whitespace:
            with parser.bracket_context():
                if hasattr(parser, "control"):
                    parser.control._skip_whitespace()

                # Caso de bloque vacío inmediato: "( )"
                if parser.not_empty() and parser.current().token == self.close_token:
                    parser.consume(node=target_node)
                    if target_node and getattr(config, "PARSER_ADD_INFO", True):
                        target_node.note("Enclosed: contenido vacío", "Normal")
                    return None

                res = self._dispatch_sub(
                    self.content,
                    analyzer,
                    None,
                    ignore_errors=ignore_errors,
                )

                if res is None:
                    parser.restore(checkpoint, node=target_node)
                    if not ignore_errors:
                        error.ParserError(
                            "Enclosed: contenido no coincidió",
                            errors.COMBINATOR_FAILED,
                            f"El contenido dentro de '{self.open_token.name}...{self.close_token.name}' no coincidió.",
                        ).raise_error()
                    return None

                if hasattr(parser, "control"):
                    parser.control._skip_whitespace()

                # 3. Token de cierre
                if not parser.not_empty():
                    parser.restore(checkpoint, node=target_node)
                    if not ignore_errors:
                        error.ParserError(
                            "Enclosed: EOF antes del delimitador de cierre",
                            errors.PARSER_EARLY_EOF,
                            f"Se esperaba '{self.close_token.name}' pero se alcanzó EOF.",
                        ).raise_error()
                    return None

                close_tok = parser.consume(node=target_node)
                if close_tok.token != self.close_token:
                    parser.restore(checkpoint, node=target_node)
                    if not ignore_errors:
                        error.ParserError(
                            f"Enclosed: se esperaba '{self.close_token.name}'",
                            errors.PARSER_UNEXPECTED_TOKEN,
                            f"Token recibido: '{close_tok.token.name}' ({close_tok.value!r}) en línea {close_tok.line}.",
                        ).raise_error()
                    return None

                if target_node and getattr(config, "PARSER_ADD_INFO", True):
                    target_node.note(f"Enclosed: cierre '{self.close_token.name}' aceptado", "Success")

                return res
        else:
            res = self._dispatch_sub(
                self.content,
                analyzer,
                None,
                ignore_errors=ignore_errors,
            )

            if res is None:
                parser.restore(checkpoint, node=target_node)
                if not ignore_errors:
                    error.ParserError(
                        "Enclosed: contenido no coincidió",
                        errors.COMBINATOR_FAILED,
                    ).raise_error()
                return None

            if not parser.not_empty():
                parser.restore(checkpoint, node=target_node)
                if not ignore_errors:
                    error.ParserError(
                        "Enclosed: EOF antes de cierre",
                        errors.PARSER_EARLY_EOF,
                    ).raise_error()
                return None

            close_tok = parser.consume(node=target_node)
            if close_tok.token != self.close_token:
                parser.restore(checkpoint, node=target_node)
                if not ignore_errors:
                    error.ParserError(
                        f"Enclosed: se esperaba '{self.close_token.name}'",
                        errors.PARSER_UNEXPECTED_TOKEN,
                    ).raise_error()
                return None

            return res

    def __repr__(self) -> str:
        return (
            f"Enclosed({self.open_token.name!r}, "
            f"{self.content!r}, "
            f"{self.close_token.name!r})"
        )


# Alias idiomático
Bracketed = Enclosed


__all__ = [
    "Bracketed",
    "Enclosed",
]
