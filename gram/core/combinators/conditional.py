"""
Conditional Branching Combinator (`gram.core.combinators.conditional`).
=======================================================================
Provides the `If` combinator, which evaluates one or more condition combinators
and branches into either `ok` (optionally rewinding the condition tokens if
`restore=True`) or `fail`.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import ClassVar, TYPE_CHECKING, Any

from gram import errors
from gram.core.combinators.base import Combinator
from gram.core.combinators.kinds import CombinatorKind
from gram.core.combinators.sequence import Seq

if TYPE_CHECKING:
    from gram.core.ast import ASTAnalyzer


def _coerce_branch(branch: Any) -> Combinator | None:
    if branch is None:
        return None
    if isinstance(branch, (list, tuple)):
        return Seq(*branch)
    return branch


class If(Combinator):
    combinator_kind: ClassVar[CombinatorKind] = CombinatorKind.IF
    """
    Conditional combinator that asserts a sequence of `conditions` and branches
    between `ok` and `fail`.

    - If all `conditions` match:
      - If `restore=False`: keeps condition tokens consumed and evaluates `ok`.
      - If `restore=True`: restores the cursor to the start (lookahead mode)
        and evaluates `ok`.
    - If any condition fails:
      - Restores the cursor to the initial checkpoint and evaluates `fail` (if
        defined), or reports a failure.
    """

    header_class: bool = True

    def __init__(
        self,
        conditions: Sequence[Combinator] | Combinator,
        ok: Sequence[Combinator] | Combinator | None = None,
        fail: Sequence[Combinator] | Combinator | None = None,
        *,
        restore: bool = False,
    ) -> None:
        """
        Initialize the conditional combinator.

        Args:
            conditions (Sequence[Combinator] | Combinator): Condition(s) to test.
            ok (Sequence[Combinator] | Combinator | None): Branch evaluated when
                all conditions succeed.
            fail (Sequence[Combinator] | Combinator | None): Branch evaluated when
                any condition fails.
            restore (bool): If True, rewinds the cursor before evaluating `ok`.
        """
        super().__init__()
        if isinstance(conditions, (list, tuple)):
            self.conditions: tuple[Combinator, ...] = tuple(conditions)
        else:
            self.conditions = (conditions,)

        if not self.conditions:
            errors.GrammarError(
                "EmptyIfConditions",
                errors.GRAMMAR_COMBINATOR_FAILED,
                "El combinador If() requiere al menos una condición.",
                "Proporcione uno o más combinadores de condición en If(...).",
            ).raise_error()

        self.ok: Combinator | None = _coerce_branch(ok)
        self.fail: Combinator | None = _coerce_branch(fail)
        self.restore: bool = restore

    def parse(self, analyzer: ASTAnalyzer) -> Any:
        """
        Evaluate `self.conditions` and dispatch either `self.ok` or `self.fail`.
        """
        parser = analyzer.parser
        father = parser.node(
            "ProcessingIf", "Procesando condicional If", set_target=True
        )
        checkpoint = parser.savepoint("IF-Analysis")

        try:
            # 1. Evaluate condition sequence speculatively
            conditions_passed = True
            cond_results: list[Any] = []

            try:
                with analyzer.failure_scope() as condition_scope:
                    for cond in self.conditions:
                        res = analyzer.visitor(cond)
                        if res is None:
                            conditions_passed = False
                            break
                        cond_results.append(res)
            except BaseException:
                parser.restore(checkpoint)
                raise

            # 2. Condition failed -> execute fail branch or report error
            if not conditions_passed:
                failed_pos = parser.pos
                parser.restore(checkpoint)

                if self.fail is not None:
                    father.note(
                        "Condición de If() no cumplida; evaluando rama 'fail'.",
                        "advice",
                    )
                    return analyzer.visitor(self.fail)

                curr_tok = parser.peek() if not parser.empty() else None
                tok_info = (
                    f" en '{curr_tok.value}' (línea {curr_tok.line}, columna {curr_tok.col})"
                    if curr_tok is not None
                    else ""
                )
                fallback = errors.GrammarError(
                    "IfConditionNotMet",
                    errors.GRAMMAR_COMBINATOR_FAILED,
                    f"Condición de If() no cumplida{tok_info}.",
                    "Verifique la expresión condicional o defina una rama 'fail'.",
                )
                candidate = condition_scope.candidate
                if candidate is not None:
                    analyzer.report_error(candidate[1], pos=candidate[0])
                else:
                    analyzer.report_error(fallback, pos=failed_pos)
                return None

            # 3. Conditions succeeded -> execute ok branch
            father.note("Condiciones de If() cumplidas.", "success")
            if self.restore:
                parser.restore(checkpoint)
                if self.ok is not None:
                    return analyzer.visitor(self.ok)
                return cond_results

            candidate = condition_scope.candidate
            if candidate is not None and candidate[0] > parser.pos:
                analyzer.stage_failure(candidate[1], weight=candidate[0])
            analyzer.discard_staged_failure(min_weight=parser.pos)
            if self.ok is not None:
                ok_res = analyzer.visitor(self.ok)
                if ok_res is None:
                    parser.restore(checkpoint)
                    return None
                return [*cond_results, ok_res]

            return cond_results
        finally:
            parser.down()

    def __repr__(self) -> str:
        return (
            f"If(conditions={self.conditions!r}, "
            f"ok={self.ok!r}, fail={self.fail!r}, restore={self.restore})"
        )


__all__ = ["If"]
