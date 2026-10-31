"""
Syntactic Flow Control Signals (`gram.core.combinators.signals`).
=================================================================
Defines specialized control-flow exceptions used by combinators to coordinate
backtracking, early sequence completion, branch commitment (cut), loop
termination, and fatal parsing aborts.
"""
from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from gram.utilities.error import Error


class FlowKind(Enum):
    """Semantic directive carried by a control-flow signal."""

    CONTROL = "control"
    STOP_SEQUENCE = "stop_sequence"
    STOP_REPETITION = "stop_repetition"
    BACKTRACK_ALTERNATIVE = "backtrack_alternative"
    COMMIT_ALTERNATIVE = "commit_alternative"
    ABORT = "abort"


class ControlFlowSignal(Exception):
    """
    Base signal for internal combinator flow control.
    Represents an execution directive rather than a syntactic error.

    ``kind`` identifies the directive; the concrete subclasses remain public
    so existing ``except`` handlers continue to distinguish their semantics.
    """

    kind: ClassVar[FlowKind] = FlowKind.CONTROL

    def __init__(
        self, message: str = "Control flow signal", payload: Any = None
    ) -> None:
        super().__init__(message)
        self.message: str = message
        self.payload: Any = payload


class SkipFlowSignal(ControlFlowSignal):
    """
    Stop the current sequence successfully without creating a failure.

    In repetition combinators, zero-consumption skips stop the loop after a
    rollback; skips after consumption keep the consumed tokens and continue.
    """

    kind: ClassVar[FlowKind] = FlowKind.STOP_SEQUENCE

    def __init__(
        self, message: str = "Skip flow requested", payload: Any = None
    ) -> None:
        super().__init__(message, payload)


class BreakFlowSignal(ControlFlowSignal):
    """
    Stop the current repetition cleanly.

    The active iteration or separator checkpoint is restored before the loop
    exits; already accepted items remain accumulated.
    """

    kind: ClassVar[FlowKind] = FlowKind.STOP_REPETITION

    def __init__(
        self, message: str = "Break repetition loop requested", payload: Any = None
    ) -> None:
        super().__init__(message, payload)


class CutFlowSignal(ControlFlowSignal):
    """
    Commit the active alternative branch and inhibit later backtracking.

    ``Alt`` restores its own entry checkpoint, preserves the deepest failure
    candidate carried by this signal, and does not try subsequent branches.
    """

    kind: ClassVar[FlowKind] = FlowKind.COMMIT_ALTERNATIVE

    def __init__(
        self, message: str = "Commit branch / Cut backtracking", payload: Any = None
    ) -> None:
        super().__init__(message, payload)
        self._failure_candidate: tuple[int, Error] | None = None


class BacktrackSignal(ControlFlowSignal):
    """
    Reject the active alternative branch and request the next candidate.

    ``Alt`` restores its entry checkpoint and continues with the next branch.
    """

    kind: ClassVar[FlowKind] = FlowKind.BACKTRACK_ALTERNATIVE

    def __init__(
        self, message: str = "Backtrack requested", payload: Any = None
    ) -> None:
        super().__init__(message, payload)


class AbortFlowSignal(ControlFlowSignal):
    """
    Abort the entire syntactic analysis immediately.

    Structural combinators do not recover this signal or reinterpret it as a
    branch mismatch.
    """

    kind: ClassVar[FlowKind] = FlowKind.ABORT

    def __init__(
        self, message: str = "Abort parsing process", payload: Any = None
    ) -> None:
        super().__init__(message, payload)


__all__ = [
    "AbortFlowSignal",
    "BacktrackSignal",
    "BreakFlowSignal",
    "ControlFlowSignal",
    "CutFlowSignal",
    "FlowKind",
    "SkipFlowSignal",
]
