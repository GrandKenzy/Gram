"""
Despachador Central de Visitantes Léxicos (`gram.core.lexer.visit`).
===================================================================
Determina la categoría léxica del carácter actual y transfiere el control
al visitor especializado correspondiente (numbers, strings, words, symbols).
"""
from __future__ import annotations

from typing import Any

from gram import config
from gram.core.lexer.tokens import TokenType
from gram.core.lexer.visitors import numbers, strings, symbols, words


def process(lexer: Any, char: str) -> TokenType:
    """
    Despacha el carácter actual al visitor especializado correspondiente
    según su clasificación inicial.

    Args:
        lexer: Instancia activa del analizador léxico.
        char: Carácter actual bajo el cursor.

    Returns:
        TokenType generado por el visitor respectivo.
    """
    node = lexer.info_node.node(
        'VISITOR-UNKNOWN',
        f'Procesando carácter {char!r} en línea {lexer.line}, columna {lexer.col}',
        priority=1,
    )

    if getattr(config, 'LEXER_ADD_INFO', True) and hasattr(node, 'note'):
        node.note(f'Carácter recibido: {char!r}', 'normal')

    # 1. Cadenas simples, dobles o docstrings
    if char in '"\'':
        node.name = 'VISITOR-STRING'
        return strings.process(lexer, char, node)

    # 2. Literales numéricos
    if char.isdigit():
        node.name = 'VISITOR-NUMBER'
        return numbers.process(lexer, char, node)

    # 3. Identificadores, palabras clave o booleanos
    if char.isalpha() or char == '_':
        node.name = 'VISITOR-WORD'
        return words.process(lexer, char, node)

    # 4. Operadores y delimitadores
    node.name = 'VISITOR-SYMBOL'
    return symbols.process(lexer, char, node)


__all__ = ['process']
