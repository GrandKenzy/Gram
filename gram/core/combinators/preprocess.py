"""Zero-width user-defined token preprocessing."""
from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from gram import errors
from gram.core.combinators.base import Combinator
from gram.core.lexer.tokens import TokenType

if TYPE_CHECKING:
    from gram.core.ast import ASTAnalyzer


class Preprocess(Combinator):
    """Run a user predicate against the current effective token.

    Truthy callback results allow parsing to continue without restoring the
    entry checkpoint. Falsy results and callback failures restore that
    checkpoint and publish a shallow diagnostic at the entry position.
    """

    def __init__(self, func: Callable[[ASTAnalyzer, TokenType], object]) -> None:
        super().__init__()
        if not callable(func):
            errors.GrammarError(
                "InvalidPreprocessFunction",
                errors.GRAMMAR_COMBINATOR_UNSUPPORTED,
                "Preprocess requiere una función invocable.",
                "Pase una función con firma (analyzer, token) -> object.",
            ).raise_error()
        self.func = func

    def parse(self, analyzer: ASTAnalyzer) -> Any:
        parser = analyzer.parser
        checkpoint = parser.savepoint("PREPROCESS-Analysis")
        current = parser.peek_effective()
        if current is None:
            parser.restore(checkpoint)
            analyzer.report_error(
                errors.ParserError(
                    "PreprocessUnexpectedEOF",
                    errors.PARSER_EARLY_EOF,
                    "Preprocess no encontró un token actual.",
                    "Asegúrese de ejecutar el combinador antes de EOF.",
                ),
                pos=checkpoint.pos,
            )
            return None

        start = parser.pos
        try:
            result = self.func(analyzer, current)
        except Exception as exc:
            parser.restore(checkpoint)
            analyzer.report_error(
                errors.GrammarError(
                    "PreprocessCallbackError",
                    errors.GRAMMAR_COMBINATOR_FAILED,
                    f"La función de Preprocess lanzó {type(exc).__name__}: {exc}.",
                    "Corrija la función personalizada para que devuelva un valor truthy o falsy válido.",
                ),
                pos=start,
            )
            return None

        if parser.pos != start:
            parser.restore(checkpoint)
            analyzer.report_error(
                errors.GrammarError(
                    "PreprocessConsumedTokens",
                    errors.GRAMMAR_COMBINATOR_FAILED,
                    "Preprocess no puede consumir tokens.",
                    "Use el callback únicamente para inspeccionar o validar el token.",
                ),
                pos=start,
            )
            return None

        if not result:
            parser.restore(checkpoint)
            analyzer.report_error(
                errors.GrammarError(
                    "PreprocessRejected",
                    errors.GRAMMAR_COMBINATOR_FAILED,
                    f"Preprocess rechazó el token {current.token.name} ({current.value!r}).",
                    "La función debe devolver un valor verdadero para permitir continuar.",
                ),
                pos=start,
            )
            return None

        return []

    def __repr__(self) -> str:
        return f"Preprocess({getattr(self.func, '__name__', self.func)!r})"


__all__ = ["Preprocess"]
