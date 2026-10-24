"""
Negative Lookahead Combinator (`gram.core.combinators.negation`).
=================================================================
Provides the zero-width negative lookahead combinator (`Not`), which succeeds
if and only if its child combinator fails to match at the current cursor
position, without consuming any tokens.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from gram import errors
from gram.core.combinators.base import Combinator

if TYPE_CHECKING:
    from gram.core.ast import ASTAnalyzer


class Not(Combinator):
    """
    Zero-width negative lookahead combinator (`!e` in PEG notation).

    Succeeds and returns `[]` if `self.combinator` fails to match at the
    current cursor position, always restoring the parser state to its savepoint.
    """

    def __init__(self, combinator: Combinator) -> None:
        """
        Initialize the negative lookahead combinator.

        Args:
            combinator (Combinator): Child combinator that must NOT match.
        """
        super().__init__()
        self.combinator: Combinator = combinator

    def parse(self, analyzer: ASTAnalyzer) -> list[Any] | None:
        """
        Verify that `self.combinator` does not match at the current cursor
        position and restore the parser checkpoint.
        """
        parser = analyzer.parser
        father = parser.node(
            "ProcessingNot", "Procesando lookahead negativo Not", set_target=True
        )
        checkpoint = parser.savepoint("NOT-Analysis")
        try:
            try:
                with analyzer.failure_scope():
                    res = analyzer.visitor(self.combinator)
            finally:
                parser.restore(checkpoint)

            if res is None:
                father.note(
                    f"Not({self.combinator!r}) confirmado (no hubo coincidencia).",
                    "success",
                )
                return []

            father.note(
                f"Not({self.combinator!r}) rechazado: se detectó coincidencia prohibida.",
                "error",
            )
            curr_tok = parser.peek() if not parser.empty() else None
            tok_info = (
                f" en línea {curr_tok.line}, columna {curr_tok.col} ({curr_tok.value!r})"
                if curr_tok is not None
                else ""
            )
            analyzer.report_error(
                errors.GrammarError(
                    "NegativeLookaheadMatched",
                    errors.GRAMMAR_COMBINATOR_FAILED,
                    f"El combinador Not({self.combinator!r}) detectó una coincidencia prohibida{tok_info}.",
                    "El patrón indicado dentro de Not(...) no está permitido en esta posición.",
                ),
                pos=checkpoint.pos,
            )
            return None
        finally:
            parser.down()

    def __repr__(self) -> str:
        return f"Not({self.combinator!r})"


__all__ = ["Not"]