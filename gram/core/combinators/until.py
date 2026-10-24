"""
Until Delimiter Combinator (`gram.core.combinators.until`).
===========================================================
Provides the `Until` combinator, which sequentially consumes tokens until a
target stopping combinator matches on the stream.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from gram import errors
from gram.core.combinators.base import Combinator

if TYPE_CHECKING:
    from gram.core.ast import ASTAnalyzer


class Until(Combinator):
    """
    Combinator that consumes tokens one by one until `self.target` matches.

    - If `consume_target=False` (default): stops immediately before `self.target`,
      leaving the target tokens unconsumed in the stream.
    - If `consume_target=True`: consumes `self.target` and appends its result
      to the returned list.
    """

    header_class: bool = True

    def __init__(
        self,
        target: Combinator,
        *,
        consume_target: bool = False,
        max_tokens: int | None = None,
    ) -> None:
        """
        Initialize the `Until` combinator.

        Args:
            target (Combinator): Stopping combinator condition.
            consume_target (bool): Whether to consume and include `target` when matched.
            max_tokens (int | None): Optional cap on the number of tokens consumed before `target`.
        """
        super().__init__()
        self.target: Combinator = target
        self.consume_target: bool = consume_target
        self.max_tokens: int | None = max_tokens

    def parse(self, analyzer: ASTAnalyzer) -> list[Any] | None:
        """
        Consume tokens sequentially until `self.target` matches or `EOF` is reached.
        """
        parser = analyzer.parser
        father = parser.node(
            "ProcessingUntil", "Procesando consumo Until", set_target=True
        )
        initial_checkpoint = parser.savepoint("UNTIL-Analysis")
        collected: list[Any] = []

        try:
            while not parser.is_eof():
                chk = parser.savepoint("UNTIL-Step")
                try:
                    with analyzer.failure_scope() as target_scope:
                        target_res = analyzer.visitor(self.target)
                except BaseException:
                    parser.restore(chk)
                    raise

                if target_res is not None:
                    if self.consume_target:
                        candidate = target_scope.candidate
                        if candidate is not None and candidate[0] > parser.pos:
                            analyzer.stage_failure(candidate[1], weight=candidate[0])
                        if isinstance(target_res, list):
                            collected.extend(target_res)
                        else:
                            collected.append(target_res)
                    else:
                        parser.restore(chk)

                    father.note(
                        f"Until({self.target!r}) encontró el objetivo tras {len(collected)} elementos.",
                        "success",
                    )
                    return collected

                # Target did not match at current position: rewind target probe and consume 1 token
                parser.restore(chk)

                if self.max_tokens is not None and len(collected) >= self.max_tokens:
                    break

                tok = parser.consume()
                if tok is None:
                    break
                node = analyzer.delegate_return_node(tok)
                if node is not None:
                    collected.append(node)

            # Reached EOF or max_tokens without matching target
            failed_pos = parser.pos
            parser.restore(initial_checkpoint)
            father.note(
                f"Until({self.target!r}) alcanzó el límite o EOF sin encontrar el objetivo.",
                "error",
            )
            analyzer.report_error(
                errors.GrammarError(
                    "UntilTargetNotFound",
                    errors.GRAMMAR_COMBINATOR_FAILED,
                    f"Until({self.target!r}) alcanzó el final sin encontrar el combinador objetivo.",
                    "Asegúrese de incluir el delimitador o patrón de cierre esperado por Until.",
                ),
                pos=failed_pos,
            )
            return None
        finally:
            parser.down()

    def __repr__(self) -> str:
        return (
            f"Until({self.target!r}, "
            f"consume_target={self.consume_target}, max_tokens={self.max_tokens})"
        )


__all__ = ["Until"]
