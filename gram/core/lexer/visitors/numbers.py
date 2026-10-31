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
_INTEGER_SUFFIX_RE = re.compile(r"[uUlL]+$")
_FLOAT_SUFFIX_RE = re.compile(r"[fFlL]+$")
_DECIMAL_SUFFIX_RE = re.compile(r"[uUlLfF]+$")


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


def _numeric_tail(line: str, start: int, end: int) -> int:
    """Consume the contiguous malformed suffix of a numeric candidate."""
    while end < len(line):
        char = line[end]
        if char.isalnum() or char in "._":
            end += 1
            continue
        if char in "+-" and end > start and line[end - 1] in "eEpP":
            end += 1
            continue
        break
    return end


def _has_invalid_separator(raw_value: str) -> bool:
    """Return whether an underscore is not between two literal characters."""
    return (
        raw_value.startswith("_")
        or raw_value.endswith("_")
        or "__" in raw_value
        or raw_value.lower().startswith(("0x_", "0b_", "0o_"))
    )


def _convert_number(raw_value: str) -> int | float | str:
    """Convert a literal while retaining suffix spelling for later phases."""
    clean_value = raw_value.replace("_", "")
    lower_value = clean_value.lower()

    # Resolve radix before suffix/exponent checks. Hexadecimal digits may end
    # in ``e`` or ``f``; treating those as decimal exponents or float suffixes
    # corrupts valid literals such as ``0xface`` and ``0x1f``.
    if lower_value.startswith("0x"):
        if "p" in lower_value or "." in lower_value:
            suffix_match = _FLOAT_SUFFIX_RE.search(clean_value)
            suffix = suffix_match.group(0) if suffix_match else ""
            if suffix:
                return raw_value
            return float.fromhex(clean_value)

        suffix_match = _INTEGER_SUFFIX_RE.search(clean_value)
        suffix = suffix_match.group(0) if suffix_match else ""
        if suffix:
            return raw_value
        return int(clean_value, 16)

    if lower_value.startswith(("0b", "0o")):
        suffix_match = _INTEGER_SUFFIX_RE.search(clean_value)
        suffix = suffix_match.group(0) if suffix_match else ""
        if suffix:
            return raw_value
        return int(clean_value, 2 if lower_value.startswith("0b") else 8)

    suffix_match = _DECIMAL_SUFFIX_RE.search(clean_value)
    suffix = suffix_match.group(0) if suffix_match else ""
    body = clean_value[:-len(suffix)] if suffix else clean_value

    # Suffixes are part of the C token. Keep the complete spelling so the
    # semantic phase can distinguish `1U`, `1UL`, `1.0f`, and `1.0L`.
    if suffix:
        return raw_value

    if "." in body or "e" in body.lower():
        return float(body)
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
        invalid_end = _numeric_tail(line_str, start, start + 1)
        lexer.col = invalid_end
        return _invalid_number(
            lexer,
            line_str[start:invalid_end] or remainder[:1] or char,
            start,
            start_line,
            "No se pudo reconocer el literal numérico.",
        )

    raw_value = match.group(0)
    end = start + len(raw_value)
    tail_end = _numeric_tail(line_str, start, end)
    if tail_end != end or _has_invalid_separator(raw_value):
        lexer.col = tail_end
        return _invalid_number(
            lexer,
            line_str[start:tail_end],
            start,
            start_line,
            "La escritura del literal numérico no es válida.",
        )

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
    lower_raw = raw_value.lower()
    is_decimal = (
        "." in raw_value
        or "p" in lower_raw
        or ("e" in lower_raw and not lower_raw.startswith("0x"))
    )
    token_kind = Token.DECIMAL if is_decimal else Token.NUMBER
    return TokenType(token_kind, parsed, start_line, start)


__all__ = ["process"]
