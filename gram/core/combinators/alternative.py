"""
Alternative Combinator (`gram.core.combinators.alternative`).
=============================================================
Defines the syntactic branching combinator (`Alt`). Evaluates candidate
combinators in priority order inside a reentrant `safe_mode` context and
surfaces the deepest atomic failure if all candidate branches are rejected.
"""
from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

from gram import errors
from gram.core.combinators.base import Combinator
from gram.core.combinators.signals import BacktrackSignal, CutFlowSignal

if TYPE_CHECKING:
    from gram.core.ast import ASTAnalyzer


class Alt(Combinator):
    """
    Alternative combinator (logical OR branch).

    Evaluates candidate combinators sequentially until the first match succeeds.
    If all candidates fail, promotes or stages the deepest candidate error
    recorded across the attempted branches.
    """

    header_class: bool = True

    def __init__(self, *combinators: Combinator) -> None:
        """
        Initialize the alternative combinator with one or more candidate branches.

        Args:
            *combinators (Combinator): Candidate combinator branches to evaluate in order.
        """
        super().__init__()
        if not combinators:
            errors.GrammarError(
                "EmptyAlternatives",
                errors.GRAMMAR_COMBINATOR_FAILED,
                "El combinador Alt() requiere al menos una alternativa.",
                "Proporcione uno o más combinadores candidatos dentro de Alt(...).",
            ).raise_error()

        self.combinators: tuple[Combinator, ...] = tuple(combinators)

    def parse(self, analyzer: ASTAnalyzer) -> Any:
        """
        Evaluate candidate branches sequentially until one matches.

        Args:
            analyzer (ASTAnalyzer): Active AST analyzer instance.

        Returns:
            Any: Result of the first matching branch, or `None` if all branches fail.
        """
        parser = analyzer.parser
        father = parser.node(
            "ProcessingAlt", "Procesando combinador de Alternativas", set_target=True
        )
        analyzer.debug(f"Procesando ALT con {len(self.combinators)} alternativas")

        checkpoint = parser.savepoint("ALT-Analysis")

        try:
            for index, combinator in enumerate(self.combinators, start=1):
                father.note(
                    f"Probando alternativa No. {index}: {combinator.type()}",
                    "normal",
                )
                try:
                    with analyzer.safe_mode():
                        res = analyzer.visitor(combinator)
                except BacktrackSignal:
                    res = None
                except CutFlowSignal:
                    parser.restore(checkpoint)
                    father.note(
                        f"Corte (CutFlowSignal) activado en alternativa No. {index}; abortando backtracking.",
                        "warn",
                    )
                    break

                if res is None:
                    father.note(f"Alternativa No. {index} rechazada", "normal")
                    parser.restore(checkpoint)
                    continue

                father.note(f"Alternativa No. {index} aceptada", "success")
                analyzer.discard_staged_failure(min_weight=parser.pos)
                return res

            father.note("Todas las alternativas fueron rechazadas", "error")
            curr_tok = parser.peek() if not parser.empty() else None
            tok_info = (
                f" en línea {curr_tok.line}, columna {curr_tok.col} ({curr_tok.token.name})"
                if curr_tok is not None
                else ""
            )
            fallback = errors.GrammarError(
                "NoAlternativeMatched",
                errors.GRAMMAR_COMBINATOR_FAILED,
                f"Ninguna de las {len(self.combinators)} alternativas coincidió{tok_info}.",
                "Verifique que la expresión coincida con alguna de las reglas permitidas.",
            )

            if analyzer.safe_flag:
                analyzer.stage_failure(fallback, weight=checkpoint.pos)
            else:
                analyzer.flush_failure(fallback=fallback)

            return None
        finally:
            parser.down()

    def items(self) -> tuple[Combinator, ...]:
        """Return the tuple of candidate combinators in this alternative."""
        return self.combinators

    def __iter__(self) -> Iterator[Combinator]:
        return iter(self.combinators)

    def __len__(self) -> int:
        return len(self.combinators)

    def __repr__(self) -> str:
        items = ", ".join(repr(c) for c in self.combinators)
        return f"Alt({items})"


__all__ = ["Alt"]