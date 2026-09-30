"""
Visitante Léxico para Palabras e Identificadores (`gram.core.lexer.visitors.words`).
==================================================================================
Reconoce identificadores, literales booleanos (true, false), literales nulos (null)
y palabras clave registradas en gram.core.lexer.words.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from gram.utilities.info import Node

from gram import config
from gram.core.lexer import words
from gram.core.lexer.tokens import Token, TokenType

BOOLS: dict[str, bool] = {
    'true': True,
    'false': False,
}

NULLS: set[str] = {
    'null',
}


def process(
    lexer: Any,
    char: str,
    node: Node | Any,
) -> TokenType:
    """
    Procesa identificadores, booleanos, nulls y palabras reservadas (keywords).

    Args:
        lexer: Instancia activa del analizador léxico.
        char: Primer carácter de la palabra.
        node: Nodo de telemetría asignado a esta operación.

    Returns:
        TokenType generado (BOOL, NULL, KEYWORD o IDENT).
    """
    start = lexer.col
    start_line = lexer.line

    node.name = 'VISITOR-WORD'

    if getattr(config, 'LEXER_ADD_INFO', True) and hasattr(node, 'note'):
        node.note(
            f'Inicio de palabra en línea {start_line}, columna {start}',
            'normal',
        )

    lexer.advance()

    while lexer.col < len(lexer.currline):
        current = lexer.peek()
        if not (current.isalnum() or current == '_'):
            break
        lexer.advance()

    value = lexer.currline[start:lexer.col]
    lower = value.lower()

    # 1. Literales booleanos
    if lower in BOOLS:
        parsed_bool = BOOLS[lower]
        if getattr(config, 'LEXER_ADD_INFO', True) and hasattr(node, 'note'):
            node.note(f'Booleano reconocido: {value!r} -> {parsed_bool}', 'success')

        return TokenType(
            Token.BOOL,
            parsed_bool,
            start_line,
            start,
        )

    # 2. Literal nulo
    if lower in NULLS:
        if getattr(config, 'LEXER_ADD_INFO', True) and hasattr(node, 'note'):
            node.note(f'Literal nulo reconocido: {value!r}', 'success')

        return TokenType(
            Token.NULL,
            None,
            start_line,
            start,
        )

    # 3. Palabras clave registradas en words.py
    keyword = words.get_keyword(value)
    if keyword is not None:
        if getattr(config, 'LEXER_ADD_INFO', True) and hasattr(node, 'note'):
            node.note(f'Palabra clave reconocida: {keyword.name!r}', 'success')

        return TokenType(
            Token.KEYWORD,
            keyword.name,
            start_line,
            start,
        )

    # 4. Identificador genérico
    if getattr(config, 'LEXER_ADD_INFO', True) and hasattr(node, 'note'):
        node.note(f'Identificador reconocido: {value!r}', 'advice')

    return TokenType(
        Token.IDENT,
        value,
        start_line,
        start,
    )


__all__ = ['process', 'BOOLS', 'NULLS']
