"""
Combinador de Coincidencia de Palabras Clave (`gram.core.combinators.match.match_keyword`).
=========================================================================================
Evalúa si el token bajo el cursor del analizador corresponde a una palabra clave
(Token.KEYWORD) debidamente registrada en el catálogo global `words` y con el valor exacto.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from gram import config, errors
from gram.core.combinators.base import Combinator
from gram.core.lexer import words
from gram.core.lexer.tokens import Token, TokenType
from gram.core.lexer.words import Keyword
from gram.utilities import error

if TYPE_CHECKING:
    from gram.core.ast import ASTAnalyzer
    from gram.core.parser.core import Parser


class MatchKeyword(Combinator):
    """
    ES:
        Combinador atómico que valida que el token actual sea una palabra clave
        (Token.KEYWORD) debidamente registrada en el catálogo léxico y con el texto esperado.

    EN:
        Atomic combinator validating that current token is a registered KEYWORD.
    """

    def __init__(self, keyword: str | Keyword) -> None:
        """
        Inicializa el combinador con el nombre de la palabra clave esperada.

        Args:
            keyword: Identificador de la palabra clave (ej. 'def', 'if', 'return') o instancia Keyword.
        """
        if isinstance(keyword, Keyword):
            self.keyword: str = keyword.name
        else:
            self.keyword = str(keyword)

    def parse(
        self,
        analyzer: ASTAnalyzer | Parser | Any,
        current: TokenType | None = None,
        ignore_errors: bool = False,
    ) -> TokenType | None:
        """
        Verifica si el token actual es la palabra clave esperada.

        Args:
            analyzer: Instancia activa del analizador sintáctico o parser.
            current: Token actual posicionado bajo el cursor, o None para consumir del parser.
            ignore_errors: Si True, retorna None en vez de lanzar excepciones ante discrepancias.

        Returns:
            TokenType | None: El token reconocido si coincide; None en caso contrario.

        Raises:
            ParserError: Si el token no es KEYWORD, la keyword no existe o el valor no coincide.
        """
        parser = self._get_parser(analyzer)
        target_node = self._get_node(analyzer)

        if target_node and getattr(config, "PARSER_ADD_INFO", True):
            target_node.note(f"MatchKeyword: esperando {self.keyword!r}", "Normal")

        checkpoint = parser.savepoint(node=target_node)

        if current is None:
            if not parser.not_empty():
                if not ignore_errors:
                    if target_node and getattr(config, "PARSER_ADD_ERROR", True):
                        target_node.note(
                            f"Error sintáctico: se esperaba palabra clave {self.keyword!r} pero se alcanzó EOF",
                            "Error",
                        )
                    error.ParserError(
                        "Palabra clave inesperada",
                        errors.PARSER_EARLY_EOF,
                        f"Se esperaba la palabra reservada {self.keyword!r} pero se alcanzó el final del archivo.",
                    ).raise_error()
                return None
            tok = parser.consume(node=target_node)
        else:
            tok = current

        current_token = tok.token
        current_name = getattr(current_token, "name", str(current_token))

        # 1. El token debe ser de categoría KEYWORD
        if current_token != Token.KEYWORD and current_name != "KEYWORD":
            parser.restore(checkpoint, node=target_node)

            if target_node and getattr(config, "PARSER_ADD_INFO", True):
                target_node.note(
                    f"Se recibió {current_name!r}; se esperaba KEYWORD",
                    "Warn",
                )

            if not ignore_errors:
                if target_node and getattr(config, "PARSER_ADD_ERROR", True):
                    target_node.note(
                        f"Error sintáctico: se esperaba palabra clave {self.keyword!r}",
                        "Error",
                    )
                error.ParserError(
                    "Palabra clave inesperada",
                    errors.PARSER_UNEXPECTED_TOKEN,
                    f"Se esperaba la palabra reservada {self.keyword!r} pero se encontró {current_name}.",
                    f"Encontrado en línea {tok.line}, columna {tok.col}.",
                ).raise_error()

            return None

        # 2. La palabra clave debe existir en el catálogo global del lexer
        if not words.keyword_exists(self.keyword):
            parser.restore(checkpoint, node=target_node)

            if target_node and getattr(config, "PARSER_ADD_ERROR", True):
                target_node.note(
                    f"La palabra clave {self.keyword!r} no está registrada en el lexer",
                    "Error",
                )
            if not ignore_errors:
                error.ParserError(
                    "Palabra clave no registrada",
                    errors.KEYWORD_NOT_FOUND,
                    f"La palabra clave {self.keyword!r} no está registrada.",
                    "Asegúrese de registrarla con gram.core.lexer.words.add_keyword().",
                ).raise_error()
            return None

        # 3. Coincidencia exacta del valor textual de la palabra clave
        if tok.value != self.keyword:
            parser.restore(checkpoint, node=target_node)

            if target_node and getattr(config, "PARSER_ADD_INFO", True):
                target_node.note(
                    f"Keyword no coincide: se esperaba {self.keyword!r}, se recibió {tok.value!r}",
                    "Warn",
                )

            if not ignore_errors:
                if target_node and getattr(config, "PARSER_ADD_ERROR", True):
                    target_node.note(
                        f"Discrepancia en palabra clave: {self.keyword!r} != {tok.value!r}",
                        "Error",
                    )
                error.ParserError(
                    "Palabra clave discrepante",
                    errors.PARSER_UNEXPECTED_TOKEN,
                    f"Se esperaba {self.keyword!r} pero se recibió {tok.value!r}.",
                    f"En línea {tok.line}, columna {tok.col}.",
                ).raise_error()

            return None

        # Si current fue pasado explícitamente y el parser aún apuntaba a él, avanzar cursor físico
        if current is not None and parser.not_empty() and parser.tokens[parser.pos] is current:
            parser.advance()

        if target_node and getattr(config, "PARSER_ADD_INFO", True):
            target_node.note(
                f"MatchKeyword exitoso: {self.keyword!r}",
                "Success",
            )

        return tok

    def __repr__(self) -> str:
        return f"MatchKeyword({self.keyword!r})"


__all__ = ["MatchKeyword"]
