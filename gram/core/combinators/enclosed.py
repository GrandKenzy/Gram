"""
Enclosed and Bracketed Combinator (`gram.core.combinators.enclosed`).
=====================================================================
Wraps an inner content combinator between any arbitrary opening and closing
`Token` delimiters and optionally activates the parser's bracket-aware mode
during content analysis so `NEWLINE`, `INDENT`, and `DEDENT` tokens are skipped.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from gram import errors
from gram.core.combinators.base import Combinator
from gram.core.combinators.kinds import CombinatorKind
from gram.core.lexer.tokens import Token

if TYPE_CHECKING:
    from gram.core.ast import ASTAnalyzer


def _validate_token(delim: Token, role: str) -> Token:
    """Validate that a delimiter is a strict `Token` enum member."""
    if not isinstance(delim, Token):
        errors.GrammarError(
            "InvalidDelimiterType",
            errors.GRAMMAR_COMBINATOR_UNSUPPORTED,
            f"El delimitador de {role} en Enclosed debe ser una instancia de Token, "
            f"pero se recibió '{type(delim).__name__}' ({delim!r}).",
            "Pase miembros del enum Token directamente (ej. Token.LPAREN, Token.RPAREN).",
        ).raise_error()
    return delim


class Enclosed(Combinator):
    """
    Combinator that evaluates inner content enclosed between arbitrary opening
    and closing `Token` delimiters while optionally enabling bracket-aware
    whitespace skipping.
    """

    header_class: bool = True
    combinator_kind: ClassVar[CombinatorKind] = CombinatorKind.ENCLOSED

    def __init__(
        self,
        open: Token,
        content: Combinator,
        close: Token,
        skip_whitespace: bool = True,
        allow_empty: bool = True,
    ) -> None:
        """
        Initialize the `Enclosed` combinator with arbitrary `Token` delimiters.

        Args:
            open (Token): Opening delimiter token (e.g., `Token.LPAREN`, `Token.WALRUS`).
            content (Combinator): Inner combinator evaluated between the delimiters.
            close (Token): Closing delimiter token (e.g., `Token.RPAREN`, `Token.HLINE`).
            skip_whitespace (bool): If True, enables bracket-aware mode to skip
                `NEWLINE`, `INDENT`, and `DEDENT` tokens inside the delimiters.
            allow_empty (bool): If True, allows empty delimiter pairs with no inner content.
        """
        super().__init__()
        self.open_token: Token = _validate_token(open, "apertura")
        self.close_token: Token = _validate_token(close, "cierre")
        self.content: Combinator = content
        self.skip_whitespace: bool = skip_whitespace
        self.allow_empty: bool = allow_empty

    def parse(self, analyzer: ASTAnalyzer) -> Any:
        """
        Evaluate the opening token, inner content combinator, and closing token.

        Args:
            analyzer (ASTAnalyzer): Active AST analyzer instance.

        Returns:
            Any: Result of `self.content` (`[]` if empty and allowed), or `None` on failure.
        """
        parser = analyzer.parser
        father = parser.node(
            "ProcessingEnclosed", "Procesando delimitadores", set_target=True
        )
        checkpoint = parser.savepoint("ENCLOSED-Analysis")

        try:
            # 1. Validate opening delimiter token
            if parser.empty() or (parser.is_eof() and self.open_token != Token.EOF):
                analyzer.report_error(
                    errors.ParserError(
                        "UnexpectedEOFBeforeOpenDelimiter",
                        errors.PARSER_EARLY_EOF,
                        f"Se esperaba el delimitador de apertura '{self.open_token.name}', pero se alcanzó EOF.",
                        "Asegúrese de abrir el bloque o expresión delimitada.",
                    ),
                    pos=parser.pos,
                )
                return None

            open_tok = parser.peek()
            if open_tok is None or open_tok.token != self.open_token:
                if open_tok is not None:
                    analyzer.report_error(
                        errors.ParserError(
                            "OpeningDelimiterMismatch",
                            errors.PARSER_UNEXPECTED_TOKEN,
                            f"Se esperaba el delimitador de apertura '{self.open_token.name}', pero se recibió "
                            f"'{open_tok.token.name}' ({open_tok.value!r}) en línea {open_tok.line}, columna {open_tok.col}.",
                            f"Inicie el bloque con '{self.open_token.name}'.",
                        ),
                        pos=parser.pos,
                    )
                parser.restore(checkpoint)
                return None

            parser.consume()
            analyzer.discard_staged_failure(min_weight=parser.pos)
            father.note(
                f"Enclosed: apertura '{self.open_token.name}' aceptada", "normal"
            )

            # 2. Evaluate inner content under bracket-aware mode
            if self.skip_whitespace:
                parser.enter_delimiter()
                parser.skip_whitespace()

            try:
                content_start_pos = parser.pos
                current = parser.peek() if not parser.empty() else None

                if current is not None and current.token == self.close_token:
                    if not self.allow_empty:
                        failed_pos = parser.pos
                        parser.restore(checkpoint)
                        analyzer.report_error(
                            errors.GrammarError(
                                "EmptyEnclosedContent",
                                errors.GRAMMAR_COMBINATOR_FAILED,
                                f"El contenido dentro de '{self.open_token.name}...{self.close_token.name}' "
                                f"no puede estar vacío (línea {current.line}, columna {current.col}).",
                                "Proporcione una expresión válida dentro de los delimitadores.",
                            ),
                            pos=failed_pos,
                        )
                        return None
                    result: Any = []
                else:
                    with analyzer.safe_mode():
                        result = analyzer.visitor(self.content)

                    if result is None:
                        failed_pos = parser.pos
                        parser.restore(checkpoint)
                        fallback = errors.GrammarError(
                            "EnclosedContentMismatch",
                            errors.GRAMMAR_COMBINATOR_FAILED,
                            f"El contenido dentro de '{self.open_token.name}...{self.close_token.name}' no coincidió.",
                            "Revise la sintaxis de los elementos internos entre los delimitadores.",
                        )
                        if analyzer.in_failure_context:
                            analyzer.report_error(fallback, pos=failed_pos)
                        else:
                            analyzer.flush_failure(fallback=fallback)
                        return None

                    if not self.allow_empty and parser.pos == content_start_pos:
                        failed_pos = parser.pos
                        parser.restore(checkpoint)
                        analyzer.report_error(
                            errors.GrammarError(
                                "EmptyEnclosedContent",
                                errors.GRAMMAR_COMBINATOR_FAILED,
                                f"El contenido dentro de '{self.open_token.name}...{self.close_token.name}' "
                                f"no consumió ningún elemento (línea {open_tok.line}, columna {open_tok.col}).",
                                "Proporcione al menos un elemento válido dentro de los delimitadores.",
                            ),
                            pos=failed_pos,
                        )
                        return None

                if self.skip_whitespace:
                    parser.skip_whitespace()

                # 3. Validate closing delimiter token
                if parser.empty() or (parser.is_eof() and self.close_token != Token.EOF):
                    failed_pos = parser.pos
                    parser.restore(checkpoint)
                    eof_err = errors.ParserError(
                        "UnclosedDelimiterEOF",
                        errors.PARSER_EARLY_EOF,
                        f"Se esperaba el delimitador de cierre '{self.close_token.name}' "
                        f"(abierto en línea {open_tok.line}, columna {open_tok.col}), pero se alcanzó EOF.",
                        f"Cierre el bloque abierto con '{self.close_token.name}'.",
                    )
                    if analyzer.in_failure_context:
                        analyzer.report_error(eof_err, pos=failed_pos)
                    else:
                        analyzer.stage_failure(eof_err, weight=failed_pos)
                        analyzer.flush_failure(fallback=eof_err)
                    return None

                close_tok = parser.peek()
                if close_tok is None or close_tok.token != self.close_token:
                    failed_pos = parser.pos
                    parser.restore(checkpoint)
                    if close_tok is not None:
                        mismatch_err = errors.ParserError(
                            "ClosingDelimiterMismatch",
                            errors.PARSER_UNEXPECTED_TOKEN,
                            f"Se esperaba el delimitador de cierre '{self.close_token.name}', pero se recibió "
                            f"'{close_tok.token.name}' ({close_tok.value!r}) en línea {close_tok.line}, columna {close_tok.col}.",
                            f"Asegúrese de cerrar correctamente con '{self.close_token.name}'.",
                        )
                    if analyzer.in_failure_context:
                        analyzer.report_error(mismatch_err, pos=failed_pos)
                    else:
                        analyzer.stage_failure(mismatch_err, weight=failed_pos)
                        analyzer.flush_failure(fallback=mismatch_err)
                    return None

                parser.consume()
                analyzer.discard_staged_failure(min_weight=parser.pos)
                father.note(
                    f"Enclosed: cierre '{self.close_token.name}' aceptado", "success"
                )
                return result
            finally:
                if self.skip_whitespace:
                    parser.exit_delimiter()
        finally:
            parser.down()

    def __repr__(self) -> str:
        return (
            f"Enclosed(Token.{self.open_token.name}, "
            f"{self.content!r}, "
            f"Token.{self.close_token.name})"
        )



__all__ = [
    "Enclosed",
]
