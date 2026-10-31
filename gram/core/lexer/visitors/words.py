"""
Word, Keyword, and Identifier Lexical Visitor (`gram.core.lexer.visitors.words`).
=================================================================================
Recognizes boolean literals (`true`, `false`), null literals (`null`),
registered language keywords (`Token.KEYWORD`), and user-defined identifiers
(`Token.IDENT`).
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from gram.core.lexer.tokens import Token, TokenType

if TYPE_CHECKING:
    from gram.core.lexer.control import LexerState

def _boolean_literals(lexer: LexerState) -> dict[str, bool]:
    """Return configured boolean spellings without hardcoded language words."""
    values: dict[str, bool] = {}
    true_name = lexer.get_config("TOKEN_BOOL_TRUE", None)
    false_name = lexer.get_config("TOKEN_BOOL_FALSE", None)
    if isinstance(true_name, str) and true_name:
        values[true_name.lower()] = True
    if isinstance(false_name, str) and false_name:
        values[false_name.lower()] = False
    return values


def _null_literal(lexer: LexerState) -> str | None:
    value = lexer.get_config("TOKEN_NULL", None)
    return value.lower() if isinstance(value, str) and value else None


# Compatibility views; process() reads config dynamically.
BOOLS: dict[str, bool] = {"true": True, "false": False}
NULLS: frozenset[str] = frozenset({"null"})


def process(
    lexer: LexerState,
    char: str,
    node: Any = None,
) -> TokenType:
    """
    Scan an alphanumeric/underscore word and classify it using this priority:
    configured boolean spelling, configured null spelling, exact registered
    keyword spelling, then generic identifier. Boolean and null comparisons
    are case-insensitive; keyword lookup remains exact.
    """
    start = lexer.col
    start_line = lexer.line
    line_str = lexer.currline
    line_len = len(line_str)

    lexer.debug(f"Inicio de palabra en línea {start_line + 1}, columna {start}")
    lexer.advance()

    while lexer.col < line_len:
        current = lexer.peek()
        if current.isalnum() or (current == "_" and lexer.ident_underscores != 0):
            lexer.advance()
        else:
            break

    value = line_str[start : lexer.col]
    lower = value.lower()

    # 1. Boolean literals
    bools = _boolean_literals(lexer)
    if lower in bools:
        parsed_bool = bools[lower]
        lexer.success(f"Booleano reconocido: {value!r} -> {parsed_bool}")
        return TokenType(Token.BOOL, parsed_bool, start_line, start)

    # 2. Null literal
    if lower == _null_literal(lexer):
        lexer.success(f"Literal nulo reconocido: {value!r}")
        return TokenType(Token.NULL, None, start_line, start)

    # 3. Registered language keywords
    keyword = lexer.get_keyword(value)
    if keyword is not None:
        lexer.success(f"Palabra clave reconocida: {keyword.name!r}")
        return TokenType(Token.KEYWORD, keyword.name, start_line, start)

    # 4. Generic identifier
    lexer.advice(f"Identificador reconocido: {value!r}")
    return TokenType(Token.IDENT, value, start_line, start)


__all__ = [
    "BOOLS",
    "NULLS",
    "process",
]
