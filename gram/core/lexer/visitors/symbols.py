"""
Symbol and Operator Lexical Visitor (`gram.core.lexer.visitors.symbols`).
=========================================================================
Identifies arithmetic, assignment, comparison, logical, delimiter, arrow,
and Unicode operators using maximal-munch matching against `MAP_SYMBOLS`.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from gram import errors
from gram.core.lexer.tokens import Token, TokenType

if TYPE_CHECKING:
    from gram.core.lexer.control import LexerState


def process(
    lexer: LexerState,
    char: str,
    node: Any = None,
) -> TokenType:
    """
    Match the longest registered operator or delimiter starting at `lexer.col`
    (maximal munch), or report `LEXER_UNEXPECTED_CHARACTER` if unrecognized.
    """
    start = lexer.col
    start_line = lexer.line
    line = lexer.currline

    lexer.debug(f"Buscando símbolo desde línea {start_line + 1}, columna {start}")

    symbol_map = lexer.get_symbols()
    for symbol in lexer.sorted_symbols():
        if symbol == '...' and not lexer.get_config("SUPPORT_TRIPLE_DOT", True):
            continue
        end = start + len(symbol)
        if line[start:end] == symbol:
            lexer.col = end
            token_type = symbol_map[symbol]
            lexer.success(f"Símbolo reconocido: {symbol!r} -> {token_type}")
            return TokenType(token_type, symbol, start_line, start)

    lexer.error(f"Carácter o símbolo desconocido: {char!r}")
    lexer.advance()
    lexer.report_error(
        errors.LexerError(
            "UnexpectedCharacter",
            errors.LEXER_UNEXPECTED_CHARACTER,
            f"Carácter o símbolo desconocido {char!r} en línea {start_line + 1}, columna {start}.",
            f"El analizador léxico no reconoce el símbolo {char!r} en el catálogo MAP_SYMBOLS.",
        )
    )
    return TokenType(Token.ERROR, char, start_line, start)


__all__ = ["process"]
