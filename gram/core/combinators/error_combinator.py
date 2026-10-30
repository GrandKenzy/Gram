"""
Error Inspection and Recovery Combinator (`gram.core.combinators.error_combinator`).
====================================================================================
Provides `ErrorCombinator` to inspect, capture, and clear recorded errors from
the active diagnostic stacks (`ASTAnalyzer`, `Parser`, or `StackError`).
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from gram import errors
from gram.core.combinators.base import Combinator
from gram.utilities.error.stack import StackError

if TYPE_CHECKING:
    from gram.core.ast import ASTAnalyzer


class ErrorCombinator(Combinator):
    """
    Captures previously recorded errors during syntactic analysis.

    - `length=0`: Captures and clears all currently recorded errors.
    - `length=N`: Captures and removes up to the `N` most recent errors.
    """

    def __init__(self, length: int = 1) -> None:
        """
        Initialize the error recovery combinator.

        Args:
            length (int): Number of recent errors to capture (`0` for all).
        """
        super().__init__()
        self.length: int = max(0, length)

    def parse(self, analyzer: ASTAnalyzer) -> list[errors.Error] | None:
        """
        Extract up to `self.length` errors from the diagnostic error registries.
        """
        parser = analyzer.parser
        father = parser.node(
            "ProcessingErrorCombinator",
            "Inspeccionando pila de errores",
            set_target=True,
        )

        try:
            # Combine recorded errors from analyzer, parser, and global StackError
            source_list: list[errors.Error]
            global_stack = False
            if analyzer._errors:
                source_list = analyzer._errors
            elif parser._errors:
                source_list = parser._errors
            else:
                source_list = StackError.__err__
                global_stack = True

            total_errors = len(source_list)
            if total_errors == 0:
                father.note("No se encontraron errores para capturar.", "warn")
                analyzer.report_error(
                    errors.GrammarError(
                        "NoErrorsToCatch",
                        errors.GRAMMAR_COMBINATOR_FAILED,
                        "El combinador ErrorCombinator no encontró ningún fallo registrado para atrapar.",
                        "Verifique que exista un error previo en la pila de diagnósticos.",
                    ),
                    pos=parser.pos,
                )
                return None

            to_catch = (
                total_errors
                if self.length == 0
                else min(self.length, total_errors)
            )
            if global_stack:
                caught_errors = StackError._pop_recent(to_catch)
            else:
                caught_errors = list(source_list[-to_catch:])
                del source_list[-to_catch:]

            caught_errors.reverse()
            father.note(
                f"ErrorCombinator atrapó {len(caught_errors)} error(es).",
                "success",
            )
            return caught_errors
        finally:
            parser.down()

    def __repr__(self) -> str:
        return f"ErrorCombinator(length={self.length})"


__all__ = ["ErrorCombinator"]
