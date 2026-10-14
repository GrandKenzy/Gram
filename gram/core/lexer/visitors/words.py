"""
Word, Keyword, and Identifier Lexical Visitor (`gram.core.lexer.visitors.words`).
=================================================================================
Recognizes boolean literals (`true`, `false`), null literals (`null`),
registered language keywords (`Token.KEYWORD`), and user-defined identifiers
(`Token.IDENT`).
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from gram.core.lexer import words
from gram.core.lexer.tokens import Token, TokenType

if TYPE_CHECKING:
    from gram.core.lexer.control import LexerState

BOOLS: dict[str, bool] = {
    "true": True,
    "false": False,
}

NULLS: frozenset[str] = frozenset({"null"})


def process(
    lexer: LexerState,
    char: str,
    node: Any = None,
) -> TokenType:
    """
    Scan an alphanumeric/underscore word and classify it as `Token.BOOL`,
    `Token.NULL`, `Token.KEYWORD`, or `Token.IDENT`.
    """
    start = lexer.col
    start_line = lexer.line
    line_str = lexer.currline
    line_len = len(line_str)

    lexer.debug(f"Inicio de palabra en línea {start_line + 1}, columna {start}")
    lexer.advance()

    while lexer.col < line_len:
        current = lexer.peek()
        if current.isalnum() or current == "_":
            lexer.advance()
        else:
            break

    value = line_str[start : lexer.col]
    lower = value.lower()

    # 1. Boolean literals
    if lower in BOOLS:
        parsed_bool = BOOLS[lower]
        lexer.success(f"Booleano reconocido: {value!r} -> {parsed_bool}")
        return TokenType(Token.BOOL, parsed_bool, start_line, start)

    # 2. Null literal
    if lower in NULLS:
        lexer.success(f"Literal nulo reconocido: {value!r}")
        return TokenType(Token.NULL, None, start_line, start)

    # 3. Registered language keywords
    keyword = words.get_keyword(value)
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