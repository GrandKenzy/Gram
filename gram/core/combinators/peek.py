"""
Positive Lookahead Combinator (`gram.core.combinators.peek`).
=============================================================
Provides the zero-width positive lookahead combinator (`Peek`), which asserts
that its child combinator matches at the current cursor position without
consuming any tokens.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from gram import errors
from gram.core.combinators.base import Combinator

if TYPE_CHECKING:
    from gram.core.ast import ASTAnalyzer


class Peek(Combinator):
    """
    Zero-width positive lookahead combinator (`&e` in PEG notation).

    Succeeds and returns `[]` if `self.combinator` matches at the current
    cursor position, always rewinding the parser state back to the savepoint.
    """

    def __init__(self, combinator: Combinator) -> None:
        """
        Initialize the positive lookahead combinator.

        Args:
            combinator (Combinator): Child combinator to assert without consuming.
        """
        super().__init__()
        self.combinator: Combinator = combinator

    def parse(self, analyzer: ASTAnalyzer) -> list[Any] | None:
        """
        Assert that `self.combinator` matches at the current cursor position
        and restore the parser checkpoint.
        """
        parser = analyzer.parser
        father = parser.node(
            "ProcessingPeek", "Procesando lookahead positivo Peek", set_target=True
        )
        checkpoint = parser.savepoint("PEEK-Analysis")

        try:
            with analyzer.safe_mode():
                res = analyzer.visitor(self.combinator)

            failed_pos = parser.pos
            parser.restore(checkpoint)

            if res is not None:
                father.note(
                    f"Peek({self.combinator!r}) confirmado sin consumir tokens.",
                    "success",
                )
                return []

            father.note(f"Peek({self.combinator!r}) falló.", "warn")
            fallback = errors.GrammarError(
                "PositiveLookaheadFailed",
                errors.GRAMMAR_COMBINATOR_FAILED,
                f"La afirmación anticipada Peek({self.combinator!r}) no se cumplió.",
                "Verifique los tokens siguientes esperados por el lookahead.",
            )
            if analyzer.safe_flag:
                analyzer.report_error(fallback, pos=failed_pos)
            else:
                analyzer.flush_failure(fallback=fallback)
            return None
        finally:
            parser.down()

    def __repr__(self) -> str:
        return f"Peek({self.combinator!r})"


__all__ = ["Peek"]