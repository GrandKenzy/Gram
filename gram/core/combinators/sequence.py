"""
Sequence Combinator (`gram.core.combinators.sequence`).
=======================================================
Concatenates multiple syntactic combinators in strict sequential order.
All child combinators must match for the sequence to succeed; if any element
fails, the parser state is atomically restored to the initial savepoint while
preserving the deepest atomic failure position.
"""
from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

from gram import errors
from gram.core.combinators.base import Combinator
from gram.core.combinators.signals import ControlFlowSignal

if TYPE_CHECKING:
    from gram.core.ast import ASTAnalyzer


class Seq(Combinator):
    """
    Strict ordered sequence combinator.

    Evaluates a tuple of child combinators in sequential order against the
    token stream. If any child combinator fails to match, the parser cursor
    and diagnostic target stack are atomically restored to the initial savepoint.
    """

    header_class: bool = True

    def __init__(self, *combinators: Combinator) -> None:
        """
        Initialize the sequence combinator with one or more child combinators.

        Args:
            *combinators (Combinator): Combinators to evaluate in strict order.
        """
        super().__init__()
        if not combinators:
            errors.GrammarError(
                "EmptySequence",
                errors.GRAMMAR_COMBINATOR_FAILED,
                "La secuencia Seq() requiere al menos un combinador.",
                "Proporcione uno o más combinadores dentro de Seq(...).",
            ).raise_error()

        self.combinators: tuple[Combinator, ...] = tuple(combinators)

    def parse(self, analyzer: ASTAnalyzer) -> list[Any] | None:
        """
        Parse the token stream by evaluating each child combinator in succession.

        Args:
            analyzer (ASTAnalyzer): Active AST analyzer instance.

        Returns:
            list[Any] | None: List of results from each child combinator on success,
            or `None` if any element in the sequence fails to match.
        """
        parser = analyzer.parser
        father = parser.node(
            "ProcessingSequence",
            "Procesando secuencia de combinadores",
            set_target=True,
        )
        father.note(
            f"Procesando SEQ con {len(self.combinators)} combinadores", "normal"
        )
        checkpoint = parser.savepoint("SEQ-Analysis")
        results: list[Any] = []

        try:
            for index, combinator in enumerate(self.combinators, start=1):
                father.note(
                    f"Procesando combinador No. {index}: {combinator.type()}",
                    "normal",
                )
                try:
                    response = analyzer.visitor(combinator)
                except ControlFlowSignal:
                    father.note(
                        f"Señal de corte temprano recibida en el elemento {index} de SEQ.",
                        "advice",
                    )
                    break

                if response is None:
                    failed_pos = parser.pos
                    curr_tok = parser.peek() if not parser.empty() else None
                    tok_info = (
                        f" en línea {curr_tok.line}, columna {curr_tok.col} ({curr_tok.token.name})"
                        if curr_tok is not None
                        else ""
                    )
                    father.note(
                        f"Abortado: el elemento {index} ({combinator!r}) no coincidió",
                        "advice",
                    )
                    parser.restore(checkpoint)

                    fallback = errors.GrammarError(
                        "SequenceElementMismatch",
                        errors.GRAMMAR_COMBINATOR_FAILED,
                        f"Secuencia sintáctica incompleta{tok_info}.",
                        f"El elemento No. {index} ({combinator!r}) no coincidió con la secuencia esperada.",
                    )
                    if analyzer.safe_flag:
                        analyzer.report_error(fallback, pos=failed_pos)
                    else:
                        analyzer.flush_failure(fallback=fallback)
                    return None

                if response != []:
                    results.append(response)
                analyzer.discard_staged_failure(min_weight=parser.pos)

            father.note("Secuencia completada correctamente.", "success")
            return results
        finally:
            parser.down()

    def items(self) -> tuple[Combinator, ...]:
        """Return the tuple of child combinators comprising this sequence."""
        return self.combinators

    def __iter__(self) -> Iterator[Combinator]:
        return iter(self.combinators)

    def __len__(self) -> int:
        return len(self.combinators)

    def __repr__(self) -> str:
        items = ", ".join(repr(c) for c in self.combinators)
        return f"Seq({items})"


Sequence = Seq

__all__ = ["Seq", "Sequence"]