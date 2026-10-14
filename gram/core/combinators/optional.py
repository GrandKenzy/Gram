"""
Optional Combinator (`gram.core.combinators.optional`).
=======================================================
Provides the `Opt` combinator for rules or subtrees with optional cardinality
(`0..1`). Evaluates the inner combinator inside a reentrant `safe_mode` context:
- If omitted at the starting token, restores the checkpoint and returns `[]`.
- If partially matched before failing (`staged_weight > checkpoint.pos`),
  propagates the deep syntax failure and returns `None`.
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

    Evaluates its inner child combinator within `analyzer.safe_mode()`.
    Returns `[]` when cleanly omitted so enclosing `Seq` combinators succeed,
    or `None` if the optional branch consumed tokens and failed mid-way.
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

    def parse(self, analyzer: ASTAnalyzer) -> Any:
        """
        Evaluate `self.combinator` optionally against `analyzer`.

        Args:
            analyzer (ASTAnalyzer): Active AST analyzer managing the parser and visitor.

        Returns:
            Any:
            - The matched result from `self.combinator` if present.
            - `[]` if cleanly omitted at `checkpoint.pos`.
            - `None` if the optional branch partially matched and failed deep inside.
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
                parser.restore(checkpoint)

                # Deep partial failure inside Opt (e.g., `int a = ` missing value after `=`)
                if analyzer.staged_weight > checkpoint.pos:
                    father.note(
                        f"Fallo parcial profundo dentro de Opt({self.combinator!r}) "
                        f"en pos={analyzer.staged_weight}.",
                        "error",
                    )
                    if not analyzer.safe_flag:
                        analyzer.flush_failure()
                    return None

                # Clean omission at starting position (0 tokens consumed)
                father.note(
                    f"El combinador opcional {self.combinator!r} fue omitido limpiamente.",
                    "advice",
                )
                if not had_prior_staged and analyzer.staged_weight == checkpoint.pos:
                    analyzer.discard_staged_failure()
                return []

            father.note(
                f"Secuencia opcional {self.combinator!r} evaluada exitosamente.",
                "success",
            )
            analyzer.discard_staged_failure(min_weight=parser.pos)
            return response

        except ControlFlowSignal:
            raise
        except errors.Error as err:
            father.note(
                f"Error de Gram capturado durante evaluación opcional ({err.name}): {err}",
                "error",
            )
            failed_pos = parser.pos
            parser.restore(checkpoint)
            analyzer.report_error(err, pos=failed_pos)
            if failed_pos > checkpoint.pos:
                if not analyzer.safe_flag:
                    analyzer.flush_failure()
                return None
            return []
        finally:
            parser.down()

    def __repr__(self) -> str:
        return f"Opt({self.combinator!r})"


__all__ = ["Opt"]