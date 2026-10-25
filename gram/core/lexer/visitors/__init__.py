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

from gram import config
from gram.core.lexer.visitors import numbers, strings, symbols, words

if TYPE_CHECKING:
    from gram.core.lexer.control import LexerState
    from gram.core.lexer.tokens import TokenType


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
    if config.LEXER_SUPPORT_PREFIXED_STRINGS and char in "LuU" and (
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
    elif char.isdigit() or (
        config.LEXER_SUPPORT_LEADING_DOT_NUMBERS
        and char == "."
        and lexer.peek(1).isdigit()
    ):
        visitor_name = "VISITOR-NUMBER"
        handler = numbers.process
    elif char.isalpha() or char == "_":
        visitor_name = "VISITOR-WORD"
        handler = words.process
    else:
        visitor_name = "VISITOR-SYMBOL"
        handler = symbols.process

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
        lexer.down()


__all__ = [
    "numbers",
    "strings",
    "symbols",
    "visit",
    "words",
]
