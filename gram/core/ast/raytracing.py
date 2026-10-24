"""
AST RayTracing Telemetry Engine (`gram.core.ast.raytracing`).
============================================================
Tracks combinator evaluation flows, branch generation, and execution paths
across AST visitor passes, integrating with parser backtracking checkpoints.
"""
from __future__ import annotations

from typing import Any

from gram.core.combinators import Combinator, Ref


class Trace:
    """
    Represents an isolated sequence of combinators evaluated along an AST branch.
    """

    def __init__(self) -> None:
        self.values: list[Combinator] = []
        self.levels: list[int] = []

    def add(self, combinator: Combinator, level: int = 1) -> None:
        """Append a combinator and its nesting depth level to the active trace."""
        self.values.append(combinator)
        self.levels.append(level)

    def stringify(self) -> str:
        """
        Render the trace into a hierarchically indented string representation.
        """
        if not self.values:
            return "PROGRAM\n    (empty)"

        lines = ["PROGRAM"]
        effective_levels = self.levels if len(self.levels) == len(self.values) else [1] * len(self.values)

        for c, level in zip(self.values, effective_levels):
            indent = "    " * max(1, level)
            if isinstance(c, Ref):
                lines.append(f"{indent}->{c.type()}({c.rule_name})")
            else:
                lines.append(f"{indent}->{c.type()}")
        return "\n".join(lines)

    def copy(self) -> Trace:
        """Create a deep copy of the trace data preserving combinator references."""
        t = Trace()
        t.values = list(self.values)
        t.levels = list(self.levels)
        return t

    def clear(self) -> None:
        """Reset the trace entries."""
        self.values.clear()
        self.levels.clear()


class TraceRecord:
    """
    Detailed evaluation record of a single combinator: nesting depth, the
    cursor span it covered and how it finished.
    """

    __slots__ = ("combinator", "depth", "start", "end", "outcome", "exception_type")

    def __init__(self, combinator: Combinator, depth: int, start: int) -> None:
        self.combinator = combinator
        self.depth = depth
        self.start = start
        self.end: int | None = None
        self.outcome: str = "PENDING"
        self.exception_type: str | None = None

    def format(self) -> str:
        """Return a single indented line describing this record."""
        indent = "    " * max(1, self.depth)
        name = (
            f"{self.combinator.type()}({self.combinator.rule_name})"
            if isinstance(self.combinator, Ref)
            else self.combinator.type()
        )
        extra = f" {self.exception_type}" if self.exception_type else ""
        return f"{indent}->{name} [{self.start}:{self.end}] {self.outcome}{extra}"


class RayTracing:
    """
    Syntactic raytracer recording execution paths, alternative branches,
    and state rollbacks triggered during parser backtracking.
    """

    def __init__(self, mode: str = "basic") -> None:
        self.mode = mode
        self.trace: Trace = Trace()
        self.paths: list[str] = []
        self._checkpoints: dict[int, tuple[Trace, list[str]]] = {}
        self._trace_stack: list[Trace] = []
        self._path_stack: list[list[str]] = []
        self.branches: list[Trace] = []
        self.records: list[TraceRecord] = []
        self.backtracks: list[int] = []
        self.furthest: int | None = None

    @property
    def branchs(self) -> list[Trace]:
        """Backward-compatible alias for `branches`."""
        return self.branches

    def generate_branch(self) -> None:
        """Begin a new branch trace or record the initial active trace."""
        if not self.branches:
            self.branches.append(self.trace)
        else:
            self.trace = Trace()
            self.branches.append(self.trace)

    def stringify(self) -> str:
        """Format all recorded branch traces into formatted text blocks."""
        return "\n\n".join(b.stringify() for b in self.branches)

    def add(self, combinator: Combinator, level: int = 1) -> None:
        """Record an evaluated combinator into the active branch trace."""
        self.trace.add(combinator, level=level)

    def lift(self, checkpoint: Any = None) -> None:
        """
        Save a snapshot of the current trace and paths upon a parser savepoint.
        """
        saved_trace = self.trace.copy()
        saved_paths = list(self.paths)

        if checkpoint is not None:
            self._checkpoints[id(checkpoint)] = (saved_trace, saved_paths)

        self._trace_stack.append(saved_trace)
        self._path_stack.append(saved_paths)

    def unreach(self, checkpoint: Any = None) -> None:
        """
        Restore trace and paths to the saved snapshot upon a parser restore/backtrack.
        """
        if checkpoint is not None and id(checkpoint) in self._checkpoints:
            saved_trace, saved_paths = self._checkpoints[id(checkpoint)]
            self.trace = saved_trace.copy()
            self.paths = list(saved_paths)
            return

        if self._trace_stack:
            self.trace = self._trace_stack.pop()
        if self._path_stack:
            self.paths = self._path_stack.pop()

    def addpath(self, p: str) -> None:
        """Append a rule name to the sequential execution path."""
        self.paths.append(p)

    def path_tracing(self) -> str:
        """Return the formatted arrow-delimited path sequence."""
        return "->".join(self.paths)

    # ------------------------------------------------------------------
    # Detailed mode
    # ------------------------------------------------------------------
    def begin(
        self, combinator: Combinator, depth: int = 1, position: int = 0
    ) -> TraceRecord:
        """
        Open a detailed record for `combinator` and mirror it in the active
        trace so that `stringify()` stays consistent with basic mode.
        """
        self.trace.add(combinator, level=depth)
        record = TraceRecord(combinator, depth, position)
        self.records.append(record)
        return record

    def end(
        self,
        record: TraceRecord,
        position: int | None = None,
        outcome: str = "SUCCESS",
        exception_type: str | None = None,
    ) -> None:
        """Close `record` with the final cursor position and its outcome."""
        record.end = position
        record.outcome = outcome
        record.exception_type = exception_type

    def observe_position(self, pos: Any = None) -> None:
        """
        Register the furthest cursor position abandoned by a parser rollback.
        """
        if not isinstance(pos, int):
            return
        self.backtracks.append(pos)
        if self.furthest is None or pos > self.furthest:
            self.furthest = pos

    def detailed(self) -> str:
        """Render every recorded combinator with its span and outcome."""
        if not self.records:
            return "PROGRAM\n    (empty)"
        lines = ["PROGRAM"]
        for rec in self.records:
            lines.append(rec.format())
        if self.backtracks:
            lines.append(
                f"backtracks={len(self.backtracks)} furthest={self.furthest}"
            )
        return "\n".join(lines)

    def close(self) -> None:
        """
        Release parser snapshots taken for rollback, preserving traces,
        records and branches so results stay readable after analysis.
        """
        self._checkpoints.clear()
        self._trace_stack.clear()
        self._path_stack.clear()


__all__ = ["Trace", "TraceRecord", "RayTracing"]