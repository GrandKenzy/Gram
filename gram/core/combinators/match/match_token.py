"""
Combinador de Coincidencia de Tokens (`gram.core.combinators.match.match_token`).
=================================================================================
Valida que el token bajo el cursor del analizador coincida con un tipo de token
específico (Token enum, CustomToken o nombre textual).
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from gram import config, errors
from gram.core.combinators.base import Combinator
from gram.core.lexer.tokens import CustomToken, Token, TokenType
from gram.utilities import error

if TYPE_CHECKING:
    from gram.core.ast import ASTAnalyzer
    from gram.core.parser.core import Parser


class MatchToken(Combinator):
    """
    ES:
        Combinador atómico que valida que el token actual coincida con
        el tipo de token configurado (Token enum, CustomToken o string identificador).
        Si coincide, avanza el cursor del parser y retorna el TokenType;
        si discrepa, revierte el cursor y retorna None (o levanta ParserError).

    EN:
        Atomic combinator validating that current token matches expected type.
    """

    def __init__(self, token: Token | CustomToken | str) -> None:
        """
        Inicializa el combinador de token esperado.

        Args:
            token: Instancia de Token, CustomToken o identificador textual del token.
        """
        if isinstance(token, str):
            resolved = Token.from_string(token)
            self.token: Token | CustomToken | str = resolved if resolved is not None else token
        else:
            self.token = token

    @property
    def token_name(self) -> str:
        """Devuelve el nombre representativo del token esperado."""
        if isinstance(self.token, Token):
            return self.token.name
        return str(self.token)

    def parse(
        self,
        analyzer: ASTAnalyzer | Parser | Any,
        current: TokenType | None = None,
        ignore_errors: bool = False,
    ) -> TokenType | None:
        """
        Evalúa si el token actual coincide con el token esperado.

        Args:
            analyzer: Instancia activa del analizador sintáctico o parser.
            current: Token léxico posicionado bajo el cursor, o None para consumir del parser.
            ignore_errors: Si True, no genera excepción ante falta de coincidencia.

        Returns:
            TokenType | None: El token reconocido si coincide; None en caso contrario.

        Raises:
            ParserError: Si el token no coincide e ignore_errors es False.
        """
        parser = self._get_parser(analyzer)
        target_node = self._get_node(analyzer)

        if config.PARSER_ADD_INFO:
            target_node.note(f"MatchToken: buscando <{self.token_name}>", "Normal")

        checkpoint = parser.savepoint(node=target_node)

        if current is None:
            if not parser.not_empty():
                self._record_failure(
                    analyzer,
                    self.token_name,
                    checkpoint.pos,
                    None,
                )
                if not ignore_errors:
                    if config.PARSER_ADD_ERROR:
                        target_node.note(
                            f"Error sintáctico: se esperaba <{self.token_name}> pero se alcanzó EOF",
                            "Error",
                        )
                    error.ParserError(
                        "Token inesperado",
                        errors.PARSER_EARLY_EOF,
                        f"Se esperaba token '{self.token_name}' pero se alcanzó el final del archivo.",
                    ).raise_error()
                return None
            tok = parser.consume(node=target_node)
        else:
            tok = current

        current_token = tok.token
        current_name = current_token.name

        matched = False
        if isinstance(self.token, Token):
            matched = (current_token == self.token) or (current_name == self.token.name)
        elif isinstance(self.token, CustomToken):
            matched = (current_token == self.token) or (current_name == self.token.name)
        else:
            matched = (current_name == self.token) or (str(tok.value) == self.token)

        if not matched:
            self._record_failure(
                analyzer,
                self.token_name,
                checkpoint.pos,
                tok,
            )
            parser.restore(checkpoint, node=target_node)

            if config.PARSER_ADD_INFO:
                target_node.note(
                    f"Token no coincidente: se esperaba {self.token_name}, se recibió {current_name}",
                    "Warn",
                )

            if not ignore_errors:
                if config.PARSER_ADD_ERROR:
                    target_node.note(
                        f"Error sintáctico: se esperaba {self.token_name}, se encontró {current_name}",
                        "Error",
                    )
                error.ParserError(
                    "Token inesperado",
                    errors.PARSER_UNEXPECTED_TOKEN,
                    f"Se esperaba token '{self.token_name}' pero se encontró '{current_name}' con valor {tok.value!r}.",
                    f"Encontrado en línea {tok.line}, columna {tok.col}.",
                ).raise_error()

            return None

        # Si current fue pasado explícitamente y el parser aún apuntaba a él, avanzar cursor físico
        if current is not None and parser.not_empty() and parser.tokens[parser.pos] is current:
            parser.advance()

        if config.PARSER_ADD_INFO:
            target_node.note(
                f"Token reconocido: {self.token_name} ({tok.value!r})",
                "Success",
            )

        return tok

    def __repr__(self) -> str:
        return f"MatchToken({self.token_name})"


__all__ = ["MatchToken"]
