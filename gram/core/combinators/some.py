"""
One-or-More Repetition Combinator (`gram.core.combinators.some`).
=================================================================
Defines the non-empty repetition combinator (`1..n` or Kleene plus `+`).
Requires at least one mandatory match of the inner combinator to succeed;
otherwise restores the initial checkpoint and promotes the deepest failure.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from gram import errors
from gram.core.combinators.base import Combinator
from gram.core.combinators.signals import BreakFlowSignal, SkipFlowSignal

if TYPE_CHECKING:
    from gram.core.ast import ASTAnalyzer


class Some(Combinator):
    """
    One-or-more repetition combinator (`1..n` / Kleene plus).

    Requires at least one match of the inner combinator and accumulates
    subsequent consecutive matches until the stream ends or matching fails.
    """

    header_class: bool = True

    def __init__(self, combinator: Combinator) -> None:
        """
        Initialize the one-or-more repetition combinator.

        Args:
            combinator (Combinator): Child syntactic combinator to repeat.
        """
        super().__init__()
        self.combinator: Combinator = combinator

    def parse(self, analyzer: ASTAnalyzer) -> list[Any] | None:
        """
        Evaluate `self.combinator` requiring at least one successful match.

        Args:
            analyzer (ASTAnalyzer): Active AST analyzer instance.

        Returns:
            list[Any] | None: Non-empty list of matched results, or `None` on failure.
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

    def _parse_iterations(self, analyzer: ASTAnalyzer) -> tuple[list[Any] | None, bool]:
        """Collect iterations without using a surrounding branch's failure candidate."""
        parser = analyzer.parser
        father = parser.node(
            "ProcessingSome", "Procesando secuencia Some", set_target=True
        )
        father.note(f"SOME iniciado con {self.combinator!r}", "normal")

        initial_checkpoint = parser.savepoint("SOME-Analysis")
        results: list[Any] = []
        publish_failure = False

        try:
            while not parser.empty():
                checkpoint = parser.savepoint("SOME-Iteration")
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

                if res is None:
                    parser.restore(checkpoint)
                    if attempt.candidate is not None:
                        weight, err = attempt.candidate
                        if not results or weight > checkpoint.pos:
                            analyzer.stage_failure(err, weight=weight)
                            publish_failure = bool(results)
                    break

                results.append(res)
                if attempt.candidate is not None and attempt.candidate[0] > parser.pos:
                    weight, err = attempt.candidate
                    analyzer.stage_failure(err, weight=weight)
                analyzer.discard_staged_failure(min_weight=parser.pos)
                if parser.pos == checkpoint.pos:
                    break

            if not results:
                parser.restore(initial_checkpoint)
                father.note(
                    f"SOME rechazado: se requería al menos 1 coincidencia para {self.combinator!r}",
                    "warn",
                )

                curr_tok = parser.peek() if not parser.empty() else None
                tok_info = (
                    f" en línea {curr_tok.line}, columna {curr_tok.col} ({curr_tok.token.name})"
                    if curr_tok is not None
                    else ""
                )
                fallback = errors.GrammarError(
                    "MinimumOccurrenceNotMet",
                    errors.GRAMMAR_COMBINATOR_FAILED,
                    f"Se esperaba al menos una ocurrencia de {self.combinator!r}{tok_info}.",
                    "Verifique que la expresión cumpla con al menos una repetición válida.",
                )

                analyzer.stage_failure(fallback, weight=initial_checkpoint.pos)

                return None, True

            father.note(f"SOME completado: {len(results)} coincidencias", "success")
            # A prior accepted iteration may own a deeper partial failure even
            # when the final iteration is a clean mismatch at its starting token.
            return results, publish_failure or analyzer.staged_weight > parser.pos
        finally:
            parser.down()

    def __repr__(self) -> str:
        return f"Some({self.combinator!r})"


__all__ = ["Some"]
