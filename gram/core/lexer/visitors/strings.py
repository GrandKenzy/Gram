"""
String and Docstring Lexical Visitor (`gram.core.lexer.visitors.strings`).
==========================================================================
Processes single-quoted (`'...'`), double-quoted (`"..."`), and triple-quoted
multiline docstring literals (`'''...'''` and `\"\"\"...\"\"\"`), including
standard escape sequences and 4-digit Unicode escapes (`\\uXXXX`).
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from gram import errors
from gram.core.lexer.flags import CHAR, SIMPLE_QUOTE
from gram.core.lexer.tokens import Token, TokenType

if TYPE_CHECKING:
    from gram.core.lexer.control import LexerState

_ESCAPES: dict[str, str] = {
    "n": "\n",
    "r": "\r",
    "t": "\t",
    "b": "\b",
    "f": "\f",
    "v": "\v",
    "0": "\0",
    "\\": "\\",
    '"': '"',
    "'": "'",
}


def process(
    lexer: LexerState,
    char: str,
    node: Any = None,
    *,
    prefix: str = "",
    start_override: int | None = None,
) -> TokenType:
    """
    Dispatch string scanning through the active lexer multiline registry or
    the single-line scanner. Registered multiline delimiters are consumed by
    ``LexerState.process_multiline``; ``process_string`` handles ordinary
    quoted literals.
    """
    start = lexer.col if start_override is None else start_override
    start_line = lexer.line
    quote = char

    lexer.debug(f"Inicio de literal de cadena con delimitador {quote!r}")

    multiline = lexer.multiline_match()
    if multiline is not None:
        opening, closing = multiline
        result = lexer.process_multiline(
            opening,
            closing,
            token=Token.STRING,
            description=prefix,
            decode_escapes=True,
        )
        result.col = start
        return result

    lexer.success("Procesando cadena estándar")
    return process_string(lexer, quote, start, start_line, prefix=prefix)


def process_string(
    lexer: LexerState,
    quote: str,
    start: int,
    start_line: int,
    node: Any = None,
    *,
    prefix: str = "",
) -> TokenType:
    """Scan a single-line string literal delimited by `quote`."""
    lexer.advance()  # Consume opening quote
    chars: list[str] = []
    line_str = lexer.currline
    line_len = len(line_str)

    while lexer.col < line_len:
        char = lexer.advance()

        if char == "\\":
            if lexer.col >= line_len:
                lexer.error("Barra invertida sin carácter de escape al final de la línea")
                lexer.report_error(
                    errors.LexerError(
                        "UnclosedStringEscape",
                        errors.LEXER_UNCLOSED_STRING,
                        f"Cadena sin cerrar en línea {start_line + 1}, columna {start}.",
                        'La cadena finalizó inesperadamente tras un carácter de escape "\\".',
                    )
                )
                return TokenType(Token.ERROR, "".join(chars), start_line, start)

            escaped = lexer.advance()
            chars.append(process_escape(escaped, lexer))
            continue

        if char == quote:
            value = "".join(chars)
            lexer.success(f"Cadena cerrada con éxito: {value!r}")
            flags = SIMPLE_QUOTE
            if len(value) == 1:
                flags |= CHAR
            return TokenType(
                Token.STRING,
                value,
                start_line,
                start,
                description=prefix,
                flags=flags,
            )

        chars.append(char)

    lexer.error("Fin de línea alcanzado sin encontrar comilla de cierre")
    lexer.report_error(
        errors.LexerError(
            "UnclosedStringLiteral",
            errors.LEXER_UNCLOSED_STRING,
            f"Cadena sin cerrar en línea {start_line + 1}, columna {start}.",
            f"Se esperaba comilla de cierre {quote!r} antes del final de la línea.",
        )
    )
    return TokenType(Token.ERROR, "".join(chars), start_line, start)


def process_docstring(
    lexer: LexerState,
    quote: str,
    start: int,
    start_line: int,
    node: Any = None,
) -> TokenType:
    """Scan a multiline docstring literal delimited by triple `quote` characters."""
    triple = quote * 3
    lexer.col += 3  # Consume opening triple quotes
    chars: list[str] = []

    while lexer.has_lines():
        line_str = lexer.currline
        line_len = len(line_str)

        if lexer.col + 2 < line_len and line_str[lexer.col : lexer.col + 3] == triple:
            lexer.col += 3
            value = "".join(chars)
            lexer.success(f"Docstring completado ({len(value)} caracteres)")
            return TokenType(Token.STRING, value, start_line, start)

        if lexer.col >= line_len:
            chars.append("\n")
            lexer.line += 1
            lexer.col = 0
            continue

        char = lexer.advance()

        if char == "\\":
            if lexer.col >= line_len:
                chars.append("\\")
                continue

            escaped = lexer.advance()
            chars.append(process_escape(escaped, lexer))
            continue

        chars.append(char)

    lexer.error("Fin de archivo alcanzado sin cerrar docstring")
    lexer.report_error(
        errors.LexerError(
            "UnclosedDocstringLiteral",
            errors.LEXER_UNCLOSED_STRING,
            f"Docstring sin cerrar iniciado en línea {start_line + 1}, columna {start}.",
            f"Se esperaban tres comillas de cierre ({triple}) antes del final del archivo.",
        )
    )
    return TokenType(Token.ERROR, "".join(chars), start_line, start)


def process_escape(char: str, lexer: LexerState | None = None) -> str:
    r"""Resolve standard escape sequences (`\n`, `\t`, etc.) and `\uXXXX` Unicode escapes."""
    if char == "u" and lexer is not None and lexer.col + 4 <= len(lexer.currline):
        hex_digits = lexer.currline[lexer.col : lexer.col + 4]
        try:
            code_point = int(hex_digits, 16)
            lexer.col += 4
            return chr(code_point)
        except ValueError:
            pass

    return _ESCAPES.get(char, f"\\{char}")


__all__ = [
    "process",
    "process_docstring",
    "process_escape",
    "process_string",
]
