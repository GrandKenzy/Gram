"""
Numeric Literal Lexical Visitor (`gram.core.lexer.visitors.numbers`).
=====================================================================
Processes decimal, hexadecimal, binary and octal literals, including C-style
floating-point forms and integer/floating suffixes. Unsuffixed literals keep
their historical int/float values; suffixed literals preserve their spelling
so a later semantic phase can inspect the suffix without reparsing source.
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from gram import errors
from gram.core.lexer.tokens import Token, TokenType

if TYPE_CHECKING:
    from gram.core.lexer.control import LexerState


_DECIMAL_FLOAT_RE = re.compile(
    r"(?:"
    r"(?:[0-9][0-9_]*\.[0-9_]*)"
    r"|\.[0-9][0-9_]*"
    r"|[0-9][0-9_]*[eE][+-]?[0-9][0-9_]*"
    r")(?:[eE][+-]?[0-9][0-9_]*)?"
    r"(?:[fFlL])?"
)
_HEX_FLOAT_RE = re.compile(
    r"0[xX](?:"
    r"(?:[0-9A-Fa-f_]+\.[0-9A-Fa-f_]*|\.[0-9A-Fa-f_]+)"
    r"[pP][+-]?[0-9][0-9_]*"
    r"|[0-9A-Fa-f_]+[pP][+-]?[0-9][0-9_]*"
    r")(?:[fFlL])?"
)
_HEX_INTEGER_RE = re.compile(r"0[xX][0-9A-Fa-f_]+(?:[uUlL]*)")
_RADIX_RE = re.compile(r"(?:0[bB][01_]+|0[oO][0-7_]+)(?:[uUlL]*)")
_DECIMAL_INTEGER_RE = re.compile(r"[0-9][0-9_]*(?:[uUlL]*)")


def _invalid_number(
    lexer: LexerState,
    raw_value: str,
    start: int,
    start_line: int,
    message: str,
) -> TokenType:
    lexer.error(message)
    lexer.report_error(
        errors.LexerError(
            "MalformedNumericLiteral",
            errors.LEXER_INVALID_NUMBER,
            f"Literal numérico inválido ({raw_value!r}) en línea {start_line + 1}, columna {start}.",
            "Verifique la base, el exponente y los sufijos del literal.",
        )
    )
    return TokenType(Token.ERROR, raw_value, start_line, start)


def _convert_number(raw_value: str) -> int | float | str:
    """Convert a literal while retaining suffix spelling for later phases."""
    clean_value = raw_value.replace("_", "")
    suffix_match = re.search(r"[uUlLfF]+$", clean_value)
    suffix = suffix_match.group(0) if suffix_match else ""
    body = clean_value[:-len(suffix)] if suffix else clean_value

    # Suffixes are part of the C token. Keep the complete spelling so the
    # semantic phase can distinguish `1U`, `1UL`, `1.0f`, and `1.0L`.
    if suffix:
        return raw_value

    if body.lower().startswith("0x") and ("." in body or "p" in body.lower()):
        return float.fromhex(body)
    if "." in body or "e" in body.lower():
        return float(body)
    if body.lower().startswith("0x"):
        return int(body, 16)
    if body.lower().startswith("0b"):
        return int(body, 2)
    if body.lower().startswith("0o"):
        return int(body, 8)
    return int(body, 10)


def process(
    lexer: LexerState,
    char: str,
    node: Any = None,
) -> TokenType:
    """Scan one C-compatible numeric literal at the current cursor."""
    start = lexer.col
    start_line = lexer.line
    line_str = lexer.currline
    remainder = line_str[start:]

    # Hexadecimal floating point must be checked before radix integers.
    match = _HEX_FLOAT_RE.match(remainder)
    if match is None:
        match = _HEX_INTEGER_RE.match(remainder)
    if match is None:
        match = _RADIX_RE.match(remainder)
    if match is None:
        match = _DECIMAL_FLOAT_RE.match(remainder)
    if match is None:
        match = _DECIMAL_INTEGER_RE.match(remainder)
    if match is None:
        return _invalid_number(
            lexer,
            remainder[:1] or char,
            start,
            start_line,
            "No se pudo reconocer el literal numérico.",
        )

    raw_value = match.group(0)
    lexer.advance(len(raw_value))

    # A hexadecimal floating point literal requires a binary exponent.
    try:
        parsed = _convert_number(raw_value)
    except ValueError:
        return _invalid_number(
            lexer,
            raw_value,
            start,
            start_line,
            "No se pudo convertir el literal numérico.",
        )

    lexer.success(f"Número procesado: {parsed!r}")
    # Keep the historical NUMBER token for integers and radix literals. A
    # decimal-point/exponent spelling gets the new generic DECIMAL token.
    token_kind = (
        Token.DECIMAL
        if "." in raw_value or "e" in raw_value.lower()
        else Token.NUMBER
    )
    return TokenType(token_kind, parsed, start_line, start)


__all__ = ["process"]
