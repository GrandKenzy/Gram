"""
Visitante Léxico para Símbolos y Operadores (`gram.core.lexer.visitors.symbols`).
=================================================================================
Identifica operadores aritméticos, de asignación, comparación, delimitadores,
flechas y símbolos Unicode utilizando coincidencia máxima (maximal munch).
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from gram.utilities.info import Node

from gram import config, errors
from gram.core.lexer.tokens import MAP_SYMBOLS, TokenType, get_sorted_symbols
from gram.utilities import error


def process(
    lexer: Any,
    char: str,
    node: Node | Any,
) -> TokenType:
    """
    Identifica y procesa operadores simples, compuestos y delimitadores a partir del catálogo base.

    Args:
        lexer: Instancia activa del analizador léxico.
        char: Primer carácter del símbolo.
        node: Nodo de telemetría asignado a esta operación.

    Returns:
        TokenType generado con el token correspondiente.

    Raises:
        LexerError: Si el carácter o secuencia de caracteres no corresponde a ningún símbolo reconocido.
    """
    start = lexer.col
    start_line = lexer.line
    line = lexer.currline

    if getattr(config, 'LEXER_ADD_INFO', True) and hasattr(node, 'note'):
        node.note(
            f'Buscando símbolo desde línea {start_line}, columna {start}',
            'normal',
        )

    # Evaluación por longitud descendente para maximal munch (ej. '<<=' antes que '<<' y '<')
    for symbol in get_sorted_symbols():
        end = lexer.col + len(symbol)

        if line[lexer.col:end] == symbol:
            lexer.col = end
            token_type = MAP_SYMBOLS[symbol]

            if getattr(config, 'LEXER_ADD_INFO', True) and hasattr(node, 'note'):
                node.note(f'Símbolo reconocido: {symbol!r} -> {token_type}', 'success')

            return TokenType(
                token_type,
                symbol,
                start_line,
                start,
            )

    # Carácter o símbolo no reconocido en el catálogo
    if getattr(config, 'LEXER_ADD_ERROR', True) and hasattr(node, 'note'):
        node.note(f'Carácter o símbolo desconocido: {char!r}', 'error')

    lexer.advance()

    error.LexerError(
        f'Carácter o símbolo desconocido {char!r} en línea {start_line}, columna {start}',
        errors.LEXER_UNEXPECTED_CHARACTER,
        f'El lexer no reconoce el símbolo {char!r} en la sintaxis del lenguaje.',
    ).raise_error()


__all__ = ['process']
