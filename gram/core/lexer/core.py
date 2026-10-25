"""
Core Lexical Analyzer Engine (`gram.core.lexer.core`).
======================================================
Defines the high-level `Lexer` class and `check_state()` validator, transforming
source lines into a traceable stream of `TokenType` instances.
"""
from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from gram import config, errors
from gram.core.lexer import visitors, words
from gram.core.lexer.control import LexerState
from gram.core.lexer.items import TokenStream
from gram.core.lexer.tokens import Token, TokenType


def check_state() -> int:
    """
    Verify that at least one keyword is registered in `words` before lexing.

    Returns:
        int: Total number of registered keywords.
    """
    if words.is_empty():
        errors.LexerError(
            "EmptyKeywords",
            errors.LEXER_EMPTY_KEYWORDS,
            "No se encontró ninguna palabra clave registrada.",
            "Registre al menos una palabra clave mediante words.add_keyword() antes de ejecutar el Lexer.",
        ).raise_error()
    return words.count_keywords()


class Lexer(LexerState):
    """
    Main lexical analyzer for the Gram Framework.

    Transforms structured source code into a sequence of `TokenType` objects
    with hierarchical `Diagnostics` telemetry.
    """

    def __init__(
        self,
        source: Sequence[str] | str | Path,
        logfile: str | None = None,
    ) -> None:
        super().__init__(source, logfile=logfile)

    def process(self) -> list[TokenType]:
        """
        Execute the lexical analysis loop across all loaded source lines.

        Returns:
            list[TokenType]: Complete ordered list of lexed tokens ending with `Token.EOF`.
        """
        check_state()
        tokens_list: list[TokenType] = []

        self.node("LexingProcess", "Ejecutando análisis léxico", set_target=True)
        self.debug("Iniciando análisis léxico")

        try:
            while self.has_lines():
                if self.is_empty():
                    if (
                        not config.LEXER_IGNORE_EMPTY_LINES
                        and not config.LEXER_IGNORE_NEWLINES
                    ):
                        tokens_list.append(
                            TokenType(Token.NEWLINE, None, self.line, 0)
                        )
                    self.line += 1
                    self.col = 0
                    continue

                # Check if the line only contains a comment before mutating indentation
                stripped = self.currline.lstrip(" ")
                first_col = len(self.currline) - len(stripped)
                if (
                    stripped
                    and self.is_comment_start(stripped[0], col_override=first_col)
                    and not self.is_block_comment_start(first_col)
                ):
                    self.col = first_col
                    if config.LEXER_SAVE_COMMENTS:
                        self.comments.append(self.process_comment())
                    self.line += 1
                    self.col = 0
                    continue

                # 1. Process leading indentation
                indent_tokens = self.process_indent()
                if indent_tokens:
                    tokens_list.extend(indent_tokens)

                # 2. Scan characters across the current line
                # A multiline literal can move the cursor to a different line.
                while self.col < len(self.currline):
                    char = self.peek()

                    if char in " \r\t":
                        self.advance()
                        continue

                    multiline = self.multiline_match()
                    if multiline is not None:
                        opening, closing = multiline
                        is_block_comment = (
                            opening == self.block_comment_token
                            and getattr(config, "LEXER_SUPPORT_BLOCK_COMMENTS", True)
                        )
                        token = self.process_multiline(
                            opening,
                            closing,
                            token=Token.COMMENT if is_block_comment else Token.STRING,
                            decode_escapes=not is_block_comment,
                        )
                        if is_block_comment:
                            if config.LEXER_SAVE_COMMENTS:
                                self.comments.append(token)
                        else:
                            tokens_list.append(token)
                        continue

                    if self.is_comment_start(char):
                        is_block_comment = self.is_block_comment_start()
                        comment = self.process_comment()
                        if config.LEXER_SAVE_COMMENTS:
                            self.comments.append(comment)
                        if is_block_comment:
                            continue
                        break

                    token = visitors.visit(self, char)
                    if token is not None:
                        tokens_list.append(token)

                # 3. Emit end-of-line NEWLINE token if enabled
                if not config.LEXER_IGNORE_NEWLINES:
                    tokens_list.append(
                        TokenType(Token.NEWLINE, None, self.line, self.col)
                    )

                self.line += 1
                self.col = 0

            # 4. Flush remaining open indentation blocks before EOF
            while getattr(config, "SUPPORT_INDENT", True) and len(self.indents) > 1:
                self.indents.pop()
                tokens_list.append(
                    TokenType(Token.DEDENT, self.indents[-1], self.line, self.col)
                )

            # 5. Append terminal EOF token
            tokens_list.append(TokenType(Token.EOF, None, self.line, self.col))

            self.success(
                f"Análisis léxico completado. Total de tokens generados: {len(tokens_list)}"
            )
            return tokens_list
        finally:
            self.down()

    def stream(self) -> TokenStream:
        """Execute lexical analysis and wrap the resulting tokens in a `TokenStream`."""
        return TokenStream(self.process())


__all__ = [
    "Lexer",
    "check_state",
]
