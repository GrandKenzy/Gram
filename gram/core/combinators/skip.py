"""
Skip Flow Combinator (`gram.core.combinators.skip`).
====================================================
Provides the `Skip` combinator, which raises `SkipFlowSignal` to immediately
complete the enclosing sequence (`Seq`) or repetition loop (`Many`, `Some`)
with syntactic success.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from gram.core.combinators.base import Combinator
from gram.core.combinators.signals import *

if TYPE_CHECKING:
    from gram.core.ast import ASTAnalyzer


class Skip(Combinator):
    """
    Flow-control combinator that cleanly interrupts the current sequence (`Seq`)
    or repetition loop and marks the enclosing evaluation as successful.
    """
    
    def __init__(self, signal: type[ControlFlowSignal]) -> None:
        self.signal = signal

    def parse(self, analyzer: ASTAnalyzer) -> Any:
        """
        Log the skip directive in the parser's diagnostic stack and raise
        `SkipFlowSignal`.
        """
        analyzer.parser.advice(
            "Skip() alcanzado: interrumpiendo flujo de secuencia con éxito."
        )
        raise self.signal()

    def __repr__(self) -> str:
        return "Skip()"


__all__ = ["Skip"]