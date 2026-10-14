"""
Optional Combinator (`gram.core.combinators.optional`).
=======================================================
Provides the `Opt` combinator for rules or subtrees with optional cardinality
(`0..1`). Evaluates the inner combinator inside a reentrant `safe_mode` context;
if it fails to match at the starting token, restores the checkpoint and returns `None`.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from gram import errors
from gram.core.combinators.base import Combinator
from gram.core.combinators.signals import ControlFlowSignal

if TYPE_CHECKING:
    from gram.core.ast import ASTAnalyzer


class Opt(Combinator):
    """
    Optional combinator (`0..1` occurrence).

    Evaluates its inner child combinator within `analyzer.safe_mode()`. On
    mismatch, rewinds the parser state to its initial checkpoint and returns `None`.
    """

    header_class: bool = True

    def __init__(self, combinator: Combinator) -> None:
        """
        Initialize the optional combinator with a target child combinator.

        Args:
            combinator (Combinator): Child combinator to evaluate optionally.
        """
        super().__init__()
        if not isinstance(combinator, Combinator):
            errors.GrammarError(
                "InvalidOptionalTarget",
                errors.GRAMMAR_COMBINATOR_UNSUPPORTED,
                f"Opt esperaba una instancia de Combinator, pero recibió: {type(combinator).__name__}.",
                "Pase un combinador sintáctico válido a Opt(...).",
            ).raise_error()

        self.combinator: Combinator = combinator

    def parse(self, analyzer: ASTAnalyzer) -> Any | None:
        """
        Evaluate `self.combinator` optionally against `analyzer`.

        Args:
            analyzer (ASTAnalyzer): Active AST analyzer managing the parser and visitor.

        Returns:
            Any | None: The matched result from `self.combinator`, or `None` if omitted.
        """
        parser = analyzer.parser
        father = parser.node(
            "ProcessingOptional", "Procesando secuencia opcional", set_target=True
        )
        father.note(f"Iniciando evaluación opcional para: {self.combinator!r}", "normal")

        checkpoint = parser.savepoint(name="OptCheckpoint")
        had_prior_staged = analyzer.staged_failure is not None

        try:
            with analyzer.safe_mode():
                response = analyzer.visitor(self.combinator)

            if response is None:
                father.note(
                    f"El combinador opcional {self.combinator!r} no coincidió (retornó None).",
                    "warn",
                )
                parser.restore(checkpoint)
                if analyzer.staged_weight > checkpoint.pos:
                    if not analyzer.safe_flag:
                        analyzer.flush_failure()
                elif not had_prior_staged and analyzer.staged_weight == checkpoint.pos:
                    analyzer.discard_staged_failure()
                return None

            father.note(
                f"Secuencia opcional {self.combinator!r} evaluada exitosamente.",
                "success",
            )
            analyzer.discard_staged_failure(min_weight=parser.pos)
            return response

        except ControlFlowSignal:
            raise
        except Exception as exc:
            father.note(
                f"Excepción capturada durante evaluación opcional ({type(exc).__name__}): {exc}",
                "error",
            )
            parser.restore(checkpoint)
            return None
        finally:
            parser.down()

    def __repr__(self) -> str:
        return f"Opt({self.combinator!r})"


__all__ = ["Opt"]