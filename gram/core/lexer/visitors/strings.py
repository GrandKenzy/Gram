"""
Visitante Léxico para Cadenas y Docstrings (`gram.core.lexer.visitors.strings`).
================================================================================
Procesa literales de cadena simples ('...'), dobles ("..."), cadenas multilínea
o docstrings triples ('''...''' y \"\"\"...\"\"\"), secuencias de escape estándar
y secuencias Unicode (\\uXXXX).
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from gram.utilities.info import Node

from gram import config, errors
from gram.core.lexer.tokens import Token, TokenType
from gram.utilities import error


def process(
    lexer: Any,
    char: str,
    node: Node | Any,
) -> TokenType:
    """
    Despacha el procesamiento de cadenas estándar o docstrings triples según el delimitador.
    """
    start = lexer.col
    start_line = lexer.line
    quote = char

    if config.LEXER_ADD_INFO:
        node.note(
            f'Inicio de literal de cadena con delimitador {quote!r}',
            'normal',
        )

    # Detección de triple comilla para docstring
    if (
        config.LEXER_SUPPORT_DOCSTRINGS
        and lexer.currline[lexer.col:lexer.col + 3] == quote * 3
    ):
        node.name = 'VISITOR-DOCSTRING'
        if config.LEXER_ADD_INFO:
            node.note('Triple comilla detectada; procesando docstring multilínea', 'success')

        return process_docstring(lexer, quote, start, start_line, node)

    node.name = 'VISITOR-STRING'
    if config.LEXER_ADD_INFO:
        node.note('Procesando cadena estándar', 'success')

    return process_string(lexer, quote, start, start_line, node)


def process_string(
    lexer: Any,
    quote: str,
    start: int,
    start_line: int,
    node: Node | Any,
) -> TokenType:
    """
    Procesa una cadena de texto en una sola línea física.
    """
    lexer.advance()  # Consumir la comilla inicial
    chars: list[str] = []

    while lexer.col < len(lexer.currline):
        char = lexer.advance()

        if char == '\\':
            if lexer.col >= len(lexer.currline):
                if config.LEXER_ADD_ERROR:
                    node.note('Barra invertida sin carácter de escape al final de la línea', 'error')
                error.LexerError(
                    f'Cadena sin cerrar en línea {start_line}, columna {start}',
                    errors.LEXER_UNCLOSED_STRING,
                    'La cadena finalizó inesperadamente tras un carácter de escape "\\".',
                ).raise_error()

            escaped = lexer.advance()
            processed = process_escape(escaped, lexer)
            chars.append(processed)
            continue

        if char == quote:
            value = ''.join(chars)
            if config.LEXER_ADD_INFO:
                node.note(f'Cadena cerrada con éxito: {value!r}', 'success')

            return TokenType(
                Token.STRING,
                value,
                start_line,
                start,
            )

        chars.append(char)

    if config.LEXER_ADD_ERROR:
        node.note('Fin de línea alcanzado sin encontrar comilla de cierre', 'error')

    error.LexerError(
        f'Cadena sin cerrar en línea {start_line}, columna {start}',
        errors.LEXER_UNCLOSED_STRING,
        f'Se esperaba comilla de cierre {quote!r} antes del final de línea.',
    ).raise_error()


def process_docstring(
    lexer: Any,
    quote: str,
    start: int,
    start_line: int,
    node: Node | Any,
) -> TokenType:
    """
    Procesa cadenas multilínea delimitadas por tres comillas.
    """
    lexer.col += 3  # Consumir las 3 comillas de apertura
    chars: list[str] = []

    while lexer.has_lines():
        # Comprobar cierre de docstring
        if (
            lexer.col + 2 < len(lexer.currline)
            and lexer.currline[lexer.col:lexer.col + 3] == quote * 3
        ):
            lexer.col += 3
            value = ''.join(chars)
            if config.LEXER_ADD_INFO:
                node.note(f'Docstring completado ({len(value)} caracteres)', 'success')

            return TokenType(
                Token.DOCSTRING,
                value,
                start_line,
                start,
            )

        # Salto a la siguiente línea del docstring
        if lexer.col >= len(lexer.currline):
            chars.append('\n')
            lexer.line += 1
            lexer.col = 0
            continue

        char = lexer.advance()

        if char == '\\':
            if lexer.col >= len(lexer.currline):
                chars.append('\\')
                continue

            escaped = lexer.advance()
            processed = process_escape(escaped, lexer)
            chars.append(processed)
            continue

        chars.append(char)

    if config.LEXER_ADD_ERROR:
        node.note('Fin de archivo alcanzado sin cerrar docstring', 'error')

    error.LexerError(
        f'Docstring sin cerrar iniciado en línea {start_line}, columna {start}',
        errors.LEXER_UNCLOSED_STRING,
        f'Se esperaban tres comillas de cierre ({quote * 3}) antes del final del archivo.',
    ).raise_error()


def process_escape(char: str, lexer: Any = None) -> str:
    r"""
    Interpreta secuencias de escape estándar (\n, \r, \t, etc.) y Unicode (\uXXXX).
    """
    escapes: dict[str, str] = {
        'n': '\n',
        'r': '\r',
        't': '\t',
        'b': '\b',
        'f': '\f',
        'v': '\v',
        '0': '\0',
        '\\': '\\',
        '"': '"',
        "'": "'",
    }

    if char == 'u' and lexer is not None and lexer.col + 4 <= len(lexer.currline):
        hex_digits = lexer.currline[lexer.col:lexer.col + 4]
        try:
            code_point = int(hex_digits, 16)
            lexer.col += 4
            return chr(code_point)
        except ValueError:
            pass

    return escapes.get(char, f"\\{char}")


__all__ = [
    'process',
    'process_string',
    'process_docstring',
    'process_escape',
]
