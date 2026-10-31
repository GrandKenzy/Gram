"""
Specialized Lexical Visitors Subpackage (`gram.core.lexer.visitors`).
=====================================================================
Dispatches character scanning to specialized lexical category visitors:
  - `numbers`: Integer, floating-point, scientific, hex, binary, and octal literals.
  - `strings`: Single-line strings, triple-quoted docstrings, and escape sequences.
  - `symbols`: Maximal-munch operators, arrows, and delimiters.
  - `words`: Identifiers, booleans, null literals, and registered keywords.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from gram.core.lexer.visitors import numbers, strings, symbols, words

if TYPE_CHECKING:
    from gram.core.lexer.control import LexerState
    from gram.core.lexer.tokens import TokenType


_ASCII_DIGITS = frozenset("0123456789")


def _should_start_word_on_underscore(lexer: LexerState) -> bool:
    """Return whether the underscore at lexer.col starts an identifier according to ident_underscores."""
    mode = lexer.ident_underscores
    if mode == 0:
        return False
    if mode == -1:
        return True

    col = lexer.col
    if getattr(lexer, "_cached_u_line", -1) == lexer.line and col < getattr(lexer, "_cached_u_end", -1):
        u_count = lexer._cached_u_end - col
        has_alnum_after = lexer._cached_u_has_alnum
    else:
        line = lexer.currline
        i = col
        while i < len(line) and line[i] == "_":
            i += 1
        has_alnum_after = i < len(line) and (line[i].isalnum() or line[i].isalpha())
        lexer._cached_u_line = lexer.line
        lexer._cached_u_end = i
        lexer._cached_u_has_alnum = has_alnum_after
        u_count = i - col

    if mode == -2:
        return has_alnum_after

    if mode >= 1:
        if not has_alnum_after:
            return False
        return u_count <= mode

    return True


def visit(lexer: LexerState, char: str) -> TokenType:
    """
    Classify the current character under the lexer cursor and dispatch it
    to the corresponding specialized visitor while managing the diagnostic
    target stack.

    Args:
        lexer (LexerState): Active lexical analyzer instance.
        char (str): Current character under the cursor.

    Returns:
        TokenType: Lexed token emitted by the selected visitor.
    """
    if lexer.get_config("LEXER_SUPPORT_PREFIXED_STRINGS", True) and char in "LuU" and (
        lexer.peek(1) in "\"'"
        or (char == "u" and lexer.peek(1) == "8" and lexer.peek(2) in "\"'")
    ):
        prefix_length = 2 if char == "u" and lexer.peek(1) == "8" else 1
        prefix = lexer.currline[lexer.col : lexer.col + prefix_length]
        start = lexer.col
        lexer.advance(prefix_length)
        quote = lexer.peek()
        visitor_name = "VISITOR-PREFIXED-STRING"
        handler = lambda active_lexer, _char: strings.process(
            active_lexer,
            quote,
            prefix=prefix,
            start_override=start,
        )
    elif char in "\"'":
        visitor_name = "VISITOR-STRING"
        handler = strings.process
    elif char in _ASCII_DIGITS or (
        lexer.get_config("LEXER_SUPPORT_LEADING_DOT_NUMBERS", True)
        and char == "."
        and lexer.peek(1) in _ASCII_DIGITS
    ):
        visitor_name = "VISITOR-NUMBER"
        handler = numbers.process
    elif char.isalpha() or (char == "_" and _should_start_word_on_underscore(lexer)):
        visitor_name = "VISITOR-WORD"
        handler = words.process
    else:
        visitor_name = "VISITOR-SYMBOL"
        handler = symbols.process

    if lexer.telemetry_enabled:
        lexer.node(
            visitor_name,
            f"Procesando carácter {char!r} en línea {lexer.line + 1}, columna {lexer.col}",
            set_target=True,
            from_target=True,
        )
    lexer.debug(f"Carácter recibido: {char!r}")

    try:
        return handler(lexer, char)
    finally:
        if lexer.telemetry_enabled:
            lexer.down()


__all__ = [
    "numbers",
    "strings",
    "symbols",
    "visit",
    "words",
]
