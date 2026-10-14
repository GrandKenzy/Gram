"""
Syntactic Flow Control Signals (`gram.core.combinators.signals`).
=================================================================
Defines specialized control-flow exceptions used by combinators to coordinate
backtracking, early sequence completion, branch commitment (cut), loop
termination, and fatal parsing aborts.
"""
from __future__ import annotations

from typing import Any


class ControlFlowSignal(Exception):
    """
    Base signal for internal combinator flow control.
    Represents an execution directive rather than a syntactic error.
    """

    def __init__(
        self, message: str = "Control flow signal", payload: Any = None
    ) -> None:
        super().__init__(message)
        self.message: str = message
        self.payload: Any = payload


class SkipFlowSignal(ControlFlowSignal):
    """
    Signal requesting early, successful completion of a sequence or parsing
    block without marking a cursor failure.
    """

    def __init__(
        self, message: str = "Skip flow requested", payload: Any = None
    ) -> None:
        super().__init__(message, payload)


class BreakFlowSignal(ControlFlowSignal):
    """
    Signal ordering immediate termination of a repetition loop (`Many`, `Some`,
    `Sep`) without rolling back already accumulated elements.
    """

    def __init__(
        self, message: str = "Break repetition loop requested", payload: Any = None
    ) -> None:
        super().__init__(message, payload)


class CutFlowSignal(ControlFlowSignal):
    """
    Cut/Commit signal that commits the active branch and inhibits subsequent
    backtracking in selection combinators (`Alt`).
    """

    def __init__(
        self, message: str = "Commit branch / Cut backtracking", payload: Any = None
    ) -> None:
        super().__init__(message, payload)


class BacktrackSignal(ControlFlowSignal):
    """
    Signal explicitly forcing a rollback of the active branch in favor of the
    next available candidate alternative.
    """

    def __init__(
        self, message: str = "Backtrack requested", payload: Any = None
    ) -> None:
        super().__init__(message, payload)


class AbortFlowSignal(ControlFlowSignal):
    """
    Signal for immediate, fatal termination of the entire syntactic analysis
    process upon unrecoverable conditions.
    """

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
    "SkipFlowSignal",
]