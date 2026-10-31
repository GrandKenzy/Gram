"""
Same-Line Syntactic Continuity Combinator (`gram.core.combinators.same_line`).
==============================================================================
Provides the `SameLine` combinator, which asserts that its child combinator
begins on the same physical source line as the preceding parsed token.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from gram.core.combinators.base import Combinator
from gram.core.combinators.kinds import CombinatorKind

if TYPE_CHECKING:
    from gram.core.ast import ASTAnalyzer


class SameLine(Combinator):
    """
    Syntactic line-continuity predicate.

    Matches and delegates to `self.combinator` only if the next token starts
    on the exact same physical line as the previously consumed token. If the
    tokens are separated by a newline boundary, matching fails without consuming
    any tokens.
    """

    combinator_kind: ClassVar[CombinatorKind] = CombinatorKind.SAME_LINE

    def __init__(self, combinator: Combinator) -> None:
        super().__init__()
        self.combinator: Combinator = combinator

    def parse(self, analyzer: ASTAnalyzer) -> Any:
        parser = analyzer.parser
        if not parser.empty() and parser.pos > 0:
            current = parser.peek()
            previous = parser.tokens[parser.pos - 1]
            cur_line = getattr(current, "line", None)
            prev_line = getattr(previous, "line", None)
            if cur_line is not None and prev_line is not None and cur_line != prev_line:
                return None
        return analyzer.visitor(self.combinator)


__all__ = ["SameLine"]
