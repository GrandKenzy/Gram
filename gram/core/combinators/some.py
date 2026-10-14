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
        parser = analyzer.parser
        father = parser.node(
            "ProcessingSome", "Procesando secuencia Some", set_target=True
        )
        father.note(f"SOME iniciado con {self.combinator!r}", "normal")

        initial_checkpoint = parser.savepoint("SOME-Analysis")
        results: list[Any] = []

        try:
            while not parser.empty():
                checkpoint = parser.savepoint("SOME-Iteration")
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

                if res is None:
                    parser.restore(checkpoint)
                    if results:
                        if analyzer.staged_weight > checkpoint.pos:
                            if not analyzer.safe_flag:
                                analyzer.flush_failure()
                        elif not had_prior_staged and analyzer.staged_weight == checkpoint.pos:
                            analyzer.discard_staged_failure()
                    break

                results.append(res)
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

                if analyzer.safe_flag:
                    analyzer.stage_failure(fallback, weight=initial_checkpoint.pos)
                else:
                    analyzer.flush_failure(fallback=fallback)

                return None

            father.note(f"SOME completado: {len(results)} coincidencias", "success")
            return results
        finally:
            parser.down()

    def __repr__(self) -> str:
        return f"Some({self.combinator!r})"


__all__ = ["Some"]