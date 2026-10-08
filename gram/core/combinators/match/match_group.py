"""
Combinador de Coincidencia por Grupos Léxicos (`gram.core.combinators.match.match_group`).
========================================================================================
Valida si el valor del token bajo el cursor pertenece a un grupo semántico de palabras
clave registrado en `gram.core.lexer.words` (ej. '$TYPES', '$MODIFIERS'), admitiendo filtros
adicionales de exclusión e inclusión estricta.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from gram import config, errors
from gram.core.combinators.base import Combinator
from gram.core.lexer import words
from gram.core.lexer.tokens import Token, TokenType
from gram.core.lexer.words import WordGroup
from gram.utilities import error

if TYPE_CHECKING:
    from gram.core.ast import ASTAnalyzer
    from gram.core.parser.core import Parser


class MatchGroup(Combinator):
    """
    ES:
        Combinador que evalúa si el token actual forma parte de un conjunto semántico
        o grupo de palabras clave (WordGroup), con soporte para listas 'exclude' y 'only'.

    EN:
        Combinator evaluating whether the current token belongs to a lexical WordGroup.
    """

    def __init__(
        self,
        group: str | WordGroup,
        exclude: list[str | Token] | None = None,
        only: list[str | Token] | None = None,
    ) -> None:
        """
        Inicializa el combinador de grupo.

        Args:
            group: Nombre del grupo o instancia de WordGroup.
            exclude: Lista opcional de tokens o identificadores excluidos.
            only: Lista opcional restrictiva; solo tokens presentes aquí serán aceptados.
        """
        self.group: str = group.name if isinstance(group, WordGroup) else str(group)
        self.exclude: list[str] = []
        if exclude:
            for item in exclude:
                self.exclude.append(item if isinstance(item, str) else item.name)

        self.only: list[str] | None = None
        if only is not None:
            self.only = []
            for item in only:
                self.only.append(item if isinstance(item, str) else item.name)

    def parse(
        self,
        analyzer: ASTAnalyzer | Parser | Any,
        current: TokenType | None = None,
        ignore_errors: bool = False,
    ) -> TokenType | None:
        """
        Evalúa la pertenencia del token actual al grupo léxico.

        Args:
            analyzer: Instancia activa del analizador sintáctico o parser.
            current: Token posicionado bajo el cursor, o None para consumir del parser.
            ignore_errors: Si True, no genera excepciones ante discrepancias.

        Returns:
            TokenType | None: El token actual si pertenece al grupo; None en caso contrario.

        Raises:
            ParserError: Si el token no pertenece al grupo e ignore_errors es False.
        """
        parser = self._get_parser(analyzer)
        target_node = self._get_node(analyzer)

        if config.PARSER_ADD_INFO:
            target_node.note(
                f"MatchGroup: buscando pertenencia al grupo {self.group!r}",
                "Normal",
            )

        checkpoint = parser.savepoint(node=target_node)

        if current is None:
            if not parser.not_empty():
                self._record_failure(
                    analyzer,
                    f"miembro del grupo {self.group!r}",
                    checkpoint.pos,
                    None,
                )
                if not ignore_errors:
                    if config.PARSER_ADD_ERROR:
                        target_node.note(
                            f"Error sintáctico: se esperaba miembro del grupo {self.group!r} pero se alcanzó EOF",
                            "Error",
                        )
                    error.ParserError(
                        "Token no pertenece al grupo",
                        errors.PARSER_EARLY_EOF,
                        f"Se esperaba token perteneciente al grupo '{self.group}' pero se alcanzó EOF.",
                    ).raise_error()
                return None
            tok = parser.consume(node=target_node)
        else:
            tok = current

        token_value = str(tok.value) if tok.value is not None else ""
        current_token = tok.token
        token_name = current_token.name

        # 1. Verificar lista de exclusiones
        if token_value in self.exclude or token_name in self.exclude:
            self._record_failure(
                analyzer,
                f"miembro no excluido del grupo {self.group!r}",
                checkpoint.pos,
                tok,
            )
            parser.restore(checkpoint, node=target_node)

            if config.PARSER_ADD_INFO:
                target_node.note(
                    f"Token {token_value!r} descartado por lista de exclusión",
                    "Advice",
                )
            if not ignore_errors:
                error.ParserError(
                    "Token excluido",
                    errors.PARSER_UNEXPECTED_TOKEN,
                    f"El token {token_value!r} se encuentra en la lista de exclusiones del grupo {self.group!r}.",
                    f"Encontrado en línea {tok.line}, columna {tok.col}.",
                ).raise_error()
            return None

        # 2. Verificar lista restrictiva (only)
        if self.only is not None and (token_value not in self.only and token_name not in self.only):
            self._record_failure(
                analyzer,
                f"token permitido por el grupo {self.group!r}",
                checkpoint.pos,
                tok,
            )
            parser.restore(checkpoint, node=target_node)

            if config.PARSER_ADD_INFO:
                target_node.note(
                    f"Token {token_value!r} descartado por no pertenecer a la lista 'only'",
                    "Advice",
                )
            if not ignore_errors:
                error.ParserError(
                    "Token no permitido",
                    errors.PARSER_UNEXPECTED_TOKEN,
                    f"El token {token_value!r} no pertenece a la lista permitida del grupo {self.group!r}.",
                    f"Encontrado en línea {tok.line}, columna {tok.col}.",
                ).raise_error()
            return None

        # 3. Comprobar pertenencia en el grupo léxico
        in_group = words.exists_in_group(token_value, self.group) or words.exists_in_group(token_name, self.group)

        if not in_group:
            self._record_failure(
                analyzer,
                f"miembro del grupo {self.group!r}",
                checkpoint.pos,
                tok,
            )
            parser.restore(checkpoint, node=target_node)

            if config.PARSER_ADD_INFO:
                target_node.note(
                    f"El valor {token_name} ({token_value!r}) no pertenece al grupo {self.group!r}",
                    "Warn",
                )

            if not ignore_errors:
                if config.PARSER_ADD_ERROR:
                    target_node.note(
                        f"Error sintáctico: {token_value!r} no pertenece al grupo {self.group!r}",
                        "Error",
                    )
                error.ParserError(
                    "Token no pertenece al grupo",
                    errors.PARSER_UNEXPECTED_TOKEN,
                    f"El token {token_value!r} no pertenece al grupo de palabras '{self.group}'.",
                    f"Encontrado en línea {tok.line}, columna {tok.col}.",
                ).raise_error()

            return None

        # Si current fue pasado explícitamente y el parser aún apuntaba a él, avanzar cursor físico
        if current is not None and parser.not_empty() and parser.tokens[parser.pos] is current:
            parser.advance()

        if config.PARSER_ADD_INFO:
            target_node.note(
                f"MatchGroup exitoso: {token_value!r} pertenece al grupo {self.group!r}",
                "Success",
            )

        return tok

    def __repr__(self) -> str:
        parts = [repr(self.group)]
        if self.exclude:
            parts.append(f"exclude={self.exclude!r}")
        if self.only:
            parts.append(f"only={self.only!r}")
        return f"MatchGroup({', '.join(parts)})"


__all__ = ["MatchGroup"]
