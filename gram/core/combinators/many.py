"""
Zero-or-More Repetition Combinator (`gram.core.combinators.many`).
==================================================================
Defines the Kleene star repetition combinator (`0..n`). Repeatedly evaluates
its inner child combinator while matches succeed and tokens advance, surfacing
partial deep syntax errors if an iteration fails mid-branch.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from gram.core.combinators.base import Combinator
from gram.core.combinators.signals import BreakFlowSignal, SkipFlowSignal

if TYPE_CHECKING:
    from gram.core.ast import ASTAnalyzer


class Many(Combinator):
    """
    Zero-or-more repetition combinator (`0..n` / Kleene star).

    Accepts any number of consecutive occurrences of the inner combinator
    and returns a list of all matched results. If an iteration fails after
    partially consuming tokens (`staged_weight > checkpoint.pos`) and is not
    protected by an outer speculative context, flushes the deep error.
    """

    header_class: bool = True

    def __init__(self, combinator: Combinator) -> None:
        """
        Initialize the zero-or-more repetition combinator.

        Args:
            combinator (Combinator): Child syntactic combinator to repeat.
        """
        super().__init__()
        self.combinator: Combinator = combinator

    def parse(self, analyzer: ASTAnalyzer) -> list[Any]:
        """
        Repeatedly evaluate `self.combinator` until the stream is exhausted
        or a speculative iteration fails.

        Args:
            analyzer (ASTAnalyzer): Active AST analyzer instance.

        Returns:
            list[Any]: Accumulated match results (`[]` if zero matches occurred).
        """
        parser = analyzer.parser
        father = parser.node(
            "ProcessingMany", "Procesando secuencia Many", set_target=True
        )
        father.note(f"Many inicializado con {self.combinator!r}", "normal")
        results: list[Any] = []

        try:
            while not parser.empty():
                checkpoint = parser.savepoint("MANY-Iteration")
                had_prior_staged = analyzer.staged_failure is not None

                try:
                    with analyzer.safe_mode():
                        res = analyzer.visitor(self.combinator)
                except SkipFlowSignal:
                    if parser.pos == checkpoint.pos:
                        parser.restore(checkpoint)
                        break
                    continue
                except BreakFlowSignal:
                    parser.restore(checkpoint)
                    break

                if res is not None:
                    results.append(res)
                    analyzer.discard_staged_failure(min_weight=parser.pos)
                    if parser.pos == checkpoint.pos:
                        break
                else:
                    parser.restore(checkpoint)
                    # If the iteration advanced into a branch before failing,
                    # surface the deep error unless an outer safe_mode is active.
                    if analyzer.staged_weight > checkpoint.pos:
                        if not analyzer.safe_flag:
                            analyzer.flush_failure()
                    elif not had_prior_staged and analyzer.staged_weight == checkpoint.pos:
                        analyzer.discard_staged_failure()
                    break

            father.note(
                f"MANY finalizado: {len(results)} coincidencias acumuladas",
                "success",
            )
            return results
        finally:
            parser.down()

    def __repr__(self) -> str:
        return f"Many({self.combinator!r})"


__all__ = ["Many"]