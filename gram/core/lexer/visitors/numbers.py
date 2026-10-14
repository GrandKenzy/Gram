"""
Numeric Literal Lexical Visitor (`gram.core.lexer.visitors.numbers`).
=====================================================================
Processes decimal integers, floating-point numbers, scientific notation
(`e`/`E`), and prefixed radix literals (`0x` hex, `0b` binary, `0o` octal)
with support for underscore (`_`) digit separators.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from gram import errors
from gram.core.lexer.tokens import Token, TokenType

if TYPE_CHECKING:
    from gram.core.lexer.control import LexerState

_HEX_CHARS: frozenset[str] = frozenset("0123456789abcdefABCDEF_")
_BIN_CHARS: frozenset[str] = frozenset("01_")
_OCT_CHARS: frozenset[str] = frozenset("01234567_")

_BASE_SPECS: dict[str, tuple[int, frozenset[str], str, str]] = {
    "x": (16, _HEX_CHARS, "hexadecimal", "0-9, A-F"),
    "b": (2, _BIN_CHARS, "binario", "0 y 1"),
    "o": (8, _OCT_CHARS, "octal", "0 a 7"),
}


def _parse_prefixed_base(
    lexer: LexerState,
    prefix_key: str,
    start: int,
    start_line: int,
) -> TokenType:
    """Scan and parse a prefixed integer literal (`0x`, `0b`, or `0o`)."""
    base, allowed_chars, label, range_hint = _BASE_SPECS[prefix_key]
    lexer.advance(2)  # Consume '0' and radix prefix
    digits_start = lexer.col
    line_len = len(lexer.currline)

    while lexer.col < line_len and lexer.peek() in allowed_chars:
        lexer.advance()

    raw_slice = lexer.currline[start : lexer.col]
    clean_val = raw_slice.replace("_", "")

    if lexer.col == digits_start or len(clean_val) <= 2:
        lexer.error(f"Prefijo {label} sin dígitos")
        lexer.report_error(
            errors.LexerError(
                "IncompleteRadixNumber",
                errors.LEXER_INVALID_NUMBER,
                f"Literal {label} incompleto ({raw_slice!r}) en línea {start_line + 1}, columna {start}.",
                f"Se esperaba al menos un dígito {label} ({range_hint}) tras el prefijo '0{prefix_key}'.",
            )
        )
        return TokenType(Token.ERROR, raw_slice, start_line, start)

    try:
        parsed = int(clean_val, base)
        lexer.success(f"Número {label} procesado: {parsed!r}")
        return TokenType(Token.NUMBER, parsed, start_line, start)
    except ValueError:
        lexer.error(f"Literal {label} inválido: {raw_slice!r}")
        lexer.report_error(
            errors.LexerError(
                "InvalidRadixNumber",
                errors.LEXER_INVALID_NUMBER,
                f"Literal {label} inválido ({raw_slice!r}) en línea {start_line + 1}, columna {start}.",
                f"Verifique que los dígitos correspondan al rango {range_hint}.",
            )
        )
        return TokenType(Token.ERROR, raw_slice, start_line, start)


def process(
    lexer: LexerState,
    char: str,
    node: Any = None,
) -> TokenType:
    """
    Scan and convert a numeric literal (`int` or `float`) starting at the
    current lexer cursor.
    """
    start = lexer.col
    start_line = lexer.line
    line_str = lexer.currline
    line_len = len(line_str)

    lexer.debug(f"Inicio de número en línea {start_line + 1}, columna {start}")

    # 1. Check for radix prefixes: 0x, 0b, 0o
    if char == "0" and lexer.col + 1 < line_len:
        next_lower = line_str[lexer.col + 1].lower()
        if next_lower in _BASE_SPECS:
            return _parse_prefixed_base(lexer, next_lower, start, start_line)

    # 2. Standard decimal integer / floating-point scanning
    lexer.advance()

    while lexer.col < line_len:
        curr = lexer.peek()
        if curr.isdigit() or curr == "_":
            lexer.advance()
        else:
            break

    # Fractional part (avoid consuming range/ellipsis operators '..' or '...')
    if (
        lexer.col + 1 < line_len
        and lexer.peek() == "."
        and line_str[lexer.col + 1].isdigit()
    ):
        lexer.advance()  # Consume '.'
        while lexer.col < line_len:
            curr = lexer.peek()
            if curr.isdigit() or curr == "_":
                lexer.advance()
            else:
                break

    # Scientific notation exponent ('e' or 'E')
    if lexer.col < line_len and lexer.peek() in "eE":
        exponent_start = lexer.col
        lexer.advance()

        if lexer.col < line_len and lexer.peek() in "+-":
            lexer.advance()

        digits_start = lexer.col
        while lexer.col < line_len:
            curr = lexer.peek()
            if curr.isdigit() or curr == "_":
                lexer.advance()
            else:
                break

        if digits_start == lexer.col:
            raw_err = line_str[start : lexer.col]
            lexer.error("Exponente sin dígitos válidos")
            lexer.report_error(
                errors.LexerError(
                    "InvalidExponentNumber",
                    errors.LEXER_INVALID_NUMBER,
                    f"Exponente inválido en línea {start_line + 1}, columna {exponent_start}.",
                    "Un exponente en notación científica debe contener al menos un dígito.",
                )
            )
            return TokenType(Token.ERROR, raw_err, start_line, start)

    raw_value = line_str[start : lexer.col]
    clean_value = raw_value.replace("_", "")

    try:
        if "." in clean_value or "e" in clean_value.lower():
            parsed_number: int | float = float(clean_value)
        else:
            parsed_number = int(clean_value)
    except ValueError:
        lexer.error(f"Fallo al convertir {raw_value!r} a número")
        lexer.report_error(
            errors.LexerError(
                "MalformedNumericLiteral",
                errors.LEXER_INVALID_NUMBER,
                f"Literal numérico inválido ({raw_value!r}) en línea {start_line + 1}, columna {start}.",
                "Verifique el uso de separadores '_' y puntos decimales.",
            )
        )
        return TokenType(Token.ERROR, raw_value, start_line, start)

    lexer.success(
        f"Número procesado: {parsed_number!r} ({type(parsed_number).__name__})"
    )
    return TokenType(Token.NUMBER, parsed_number, start_line, start)


__all__ = ["process"]