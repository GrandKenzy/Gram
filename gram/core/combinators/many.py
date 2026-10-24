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
        with analyzer.failure_scope() as scope:
            results, publish_failure = self._parse_iterations(analyzer)

        if scope.candidate is not None:
            weight, err = scope.candidate
            if publish_failure and not analyzer.safe_flag:
                with analyzer.failure_scope():
                    analyzer.stage_failure(err, weight=weight)
                    analyzer.flush_failure()
            else:
                analyzer.stage_failure(err, weight=weight)
        return results

    def _parse_iterations(self, analyzer: ASTAnalyzer) -> tuple[list[Any], bool]:
        """Collect iterations and retain only failures owned by this repetition."""
        parser = analyzer.parser
        father = parser.node(
            "ProcessingMany", "Procesando secuencia Many", set_target=True
        )
        father.note(f"Many inicializado con {self.combinator!r}", "normal")
        results: list[Any] = []
        publish_failure = False

        try:
            while not parser.empty():
                checkpoint = parser.savepoint("MANY-Iteration")
                try:
                    with analyzer.failure_scope() as attempt:
                        res = analyzer.visitor(self.combinator)
                except SkipFlowSignal:
                    if parser.pos == checkpoint.pos:
                        parser.restore(checkpoint)
                        break
                    analyzer.discard_staged_failure(min_weight=parser.pos)
                    continue
                except BreakFlowSignal:
                    parser.restore(checkpoint)
                    break

                if res is not None:
                    results.append(res)
                    if attempt.candidate is not None and attempt.candidate[0] > parser.pos:
                        weight, err = attempt.candidate
                        analyzer.stage_failure(err, weight=weight)
                    analyzer.discard_staged_failure(min_weight=parser.pos)
                    if parser.pos == checkpoint.pos:
                        break
                else:
                    parser.restore(checkpoint)
                    # If the iteration advanced into a branch before failing,
                    # surface the deep error unless an outer safe_mode is active.
                    if attempt.candidate is not None and attempt.candidate[0] > checkpoint.pos:
                        weight, err = attempt.candidate
                        analyzer.stage_failure(err, weight=weight)
                        publish_failure = True
                    break

            father.note(
                f"MANY finalizado: {len(results)} coincidencias acumuladas",
                "success",
            )
            # An accepted child can retain a partial failure beyond its prefix;
            # a later clean mismatch must not leave that local error unpublished.
            return results, publish_failure or analyzer.staged_weight > parser.pos
        finally:
            parser.down()

    def __repr__(self) -> str:
        return f"Many({self.combinator!r})"


__all__ = ["Many"]
