"""
Visitante Léxico para Literales Numéricos (`gram.core.lexer.visitors.numbers`).
================================================================================
Procesa números enteros decimales, flotantes, notación científica y bases
especiales (hexadecimal 0x, binario 0b, octal 0o) con soporte completo para
separadores de dígitos con guion bajo ('_').
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
    Procesa literales numéricos enteros, flotantes y en bases alternativas (0x, 0b, 0o).

    Args:
        lexer: Instancia activa del analizador léxico.
        char: Primer carácter numérico encontrado ('0'..'9').
        node: Nodo de telemetría asignado a esta operación.

    Returns:
        TokenType con categoría Token.NUMBER y el valor int o float interpretado.

    Raises:
        LexerError: Si la sintaxis numérica es inválida o está incompleta.
    """
    start = lexer.col
    start_line = lexer.line

    if getattr(config, 'LEXER_ADD_INFO', True) and hasattr(node, 'note'):
        node.note(
            f'Inicio de número en línea {start_line}, columna {start}',
            'normal',
        )

    # 1. Detección de prefijos de bases: 0x (hex), 0b (bin), 0o (oct)
    if char == '0' and lexer.col + 1 < len(lexer.currline):
        next_char = lexer.currline[lexer.col + 1]

        # Hexadecimal (0x / 0X)
        if next_char in 'xX':
            lexer.advance()  # '0'
            lexer.advance()  # 'x'
            hex_start = lexer.col
            while lexer.col < len(lexer.currline) and lexer.peek() in '0123456789abcdefABCDEF_':
                lexer.advance()

            raw_val = lexer.currline[start:lexer.col].replace('_', '')
            if lexer.col == hex_start:
                if getattr(config, 'LEXER_ADD_ERROR', True) and hasattr(node, 'note'):
                    node.note('Prefijo hexadecimal sin dígitos', 'error')
                error.LexerError(
                    f'Literal hexadecimal incompleto en línea {start_line}, columna {start}',
                    errors.LEXER_INVALID_NUMBER,
                    'Se esperaba al menos un dígito hexadecimal tras 0x.',
                ).raise_error()

            try:
                parsed = int(raw_val, 16)
                return TokenType(Token.NUMBER, parsed, start_line, start)
            except ValueError:
                error.LexerError(
                    f'Literal hexadecimal inválido: {raw_val!r}',
                    errors.LEXER_INVALID_NUMBER,
                    'Verifique que los dígitos correspondan al rango hexadecimal 0-9, A-F.',
                ).raise_error()

        # Binario (0b / 0B)
        elif next_char in 'bB':
            lexer.advance()  # '0'
            lexer.advance()  # 'b'
            bin_start = lexer.col
            while lexer.col < len(lexer.currline) and lexer.peek() in '01_':
                lexer.advance()

            raw_val = lexer.currline[start:lexer.col].replace('_', '')
            if lexer.col == bin_start:
                if getattr(config, 'LEXER_ADD_ERROR', True) and hasattr(node, 'note'):
                    node.note('Prefijo binario sin dígitos', 'error')
                error.LexerError(
                    f'Literal binario incompleto en línea {start_line}, columna {start}',
                    errors.LEXER_INVALID_NUMBER,
                    'Se esperaba al menos un dígito binario tras 0b.',
                ).raise_error()

            try:
                parsed = int(raw_val, 2)
                return TokenType(Token.NUMBER, parsed, start_line, start)
            except ValueError:
                error.LexerError(
                    f'Literal binario inválido: {raw_val!r}',
                    errors.LEXER_INVALID_NUMBER,
                    'Un literal binario solo puede contener dígitos 0 y 1.',
                ).raise_error()

        # Octal (0o / 0O)
        elif next_char in 'oO':
            lexer.advance()  # '0'
            lexer.advance()  # 'o'
            oct_start = lexer.col
            while lexer.col < len(lexer.currline) and lexer.peek() in '01234567_':
                lexer.advance()

            raw_val = lexer.currline[start:lexer.col].replace('_', '')
            if lexer.col == oct_start:
                if getattr(config, 'LEXER_ADD_ERROR', True) and hasattr(node, 'note'):
                    node.note('Prefijo octal sin dígitos', 'error')
                error.LexerError(
                    f'Literal octal incompleto en línea {start_line}, columna {start}',
                    errors.LEXER_INVALID_NUMBER,
                    'Se esperaba al menos un dígito octal tras 0o.',
                ).raise_error()

            try:
                parsed = int(raw_val, 8)
                return TokenType(Token.NUMBER, parsed, start_line, start)
            except ValueError:
                error.LexerError(
                    f'Literal octal inválido: {raw_val!r}',
                    errors.LEXER_INVALID_NUMBER,
                    'Un literal octal solo puede contener dígitos entre 0 y 7.',
                ).raise_error()

    # 2. Procesamiento decimal estándar (enteros y flotantes)
    lexer.advance()

    # Parte entera
    while lexer.col < len(lexer.currline):
        current = lexer.peek()
        if current.isdigit() or current == '_':
            lexer.advance()
            continue
        break

    # Parte decimal
    if lexer.col < len(lexer.currline) and lexer.peek() == '.':
        # Asegurarse de no consumir operadores como '..' o '...'
        if lexer.col + 1 < len(lexer.currline) and lexer.currline[lexer.col + 1].isdigit():
            lexer.advance()
            while lexer.col < len(lexer.currline):
                current = lexer.peek()
                if current.isdigit() or current == '_':
                    lexer.advance()
                    continue
                break

    # Exponente (notación científica)
    if lexer.col < len(lexer.currline) and lexer.peek() in 'eE':
        exponent_start = lexer.col
        lexer.advance()

        if lexer.col < len(lexer.currline) and lexer.peek() in '+-':
            lexer.advance()

        digits_start = lexer.col
        while lexer.col < len(lexer.currline):
            current = lexer.peek()
            if current.isdigit() or current == '_':
                lexer.advance()
                continue
            break

        if digits_start == lexer.col:
            if getattr(config, 'LEXER_ADD_ERROR', True) and hasattr(node, 'note'):
                node.note('Exponente sin dígitos válidos', 'error')
            error.LexerError(
                f'Exponente inválido en línea {start_line}, columna {exponent_start}',
                errors.LEXER_INVALID_NUMBER,
                'Un exponente en notación científica debe contener al menos un dígito.',
            ).raise_error()

    raw_value = lexer.currline[start:lexer.col]
    clean_value = raw_value.replace('_', '')

    try:
        if '.' in clean_value or 'e' in clean_value.lower():
            parsed_number: int | float = float(clean_value)
        else:
            parsed_number = int(clean_value)
    except ValueError:
        if getattr(config, 'LEXER_ADD_ERROR', True) and hasattr(node, 'note'):
            node.note(f'Fallo al convertir {raw_value!r} a número', 'error')
        error.LexerError(
            f'Literal numérico inválido: {raw_value!r}',
            errors.LEXER_INVALID_NUMBER,
            f'No se pudo interpretar el número en línea {start_line}, columna {start}.',
        ).raise_error()

    if getattr(config, 'LEXER_ADD_INFO', True) and hasattr(node, 'note'):
        node.note(
            f'Número procesado: {parsed_number!r} ({type(parsed_number).__name__})',
            'success',
        )

    return TokenType(
        Token.NUMBER,
        parsed_number,
        start_line,
        start,
    )


__all__ = ['process']
