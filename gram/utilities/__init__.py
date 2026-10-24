"""
Diagnostic Telemetry and Failure Tracking Primitives (`Devutool` / `utilities`).
================================================================================
Provides the standalone `Diagnostics` base class for hierarchical telemetry
node management, reentrant failure-suppression contexts (`failure_context`),
and weighted candidate failure staging.

Completely decoupled from any host framework or global configuration.
"""
from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import ClassVar

from . import Format, ansi_colors, error, info

ErrorHook = Callable[['Diagnostics', error.Error], str | None]


class ErrorAction:
    """Action directives returned by error hooks to dictate error handling."""

    STORE = "store"
    OMIT = "omit"
    RAISE = "raise"
    SUPPRESS_RAISE = "suppress"


class _FailureScope:
    """Local candidate captured when an isolated failure scope exits."""

    __slots__ = ('candidate',)

    def __init__(self) -> None:
        self.candidate: tuple[int, error.Error] | None = None


class Diagnostics:
    """
    Framework-agnostic controller for hierarchical telemetry trees, reentrant
    failure contexts, weighted candidate error staging, and error hooks.
    """

    _global_hooks: ClassVar[list[ErrorHook]] = []

    def __init__(
        self,
        file: str,
        name: str,
        description: str,
        expose_nodes: bool = False,
        generate_log_file: bool = False,
        generate_on_error: bool = False,
    ) -> None:
        self.stack = info.StackInfo(
            file,
            name,
            description,
            expose_nodes,
            generate_on_error,
            generate_log_file,
        )
        self._targets: list[info.Node] = []
        self._errors: list[error.Error] = []
        self._context_depth: int = 0
        self._staged_failure: tuple[int, error.Error] | None = None
        self._hooks: list[ErrorHook] = []

    @classmethod
    def register_global_hook(cls, hook: ErrorHook) -> None:
        """Register a framework-wide error interceptor hook."""
        if hook not in cls._global_hooks:
            cls._global_hooks.append(hook)

    @classmethod
    def unregister_global_hook(cls, hook: ErrorHook) -> None:
        """Remove a previously registered framework-wide error hook."""
        if hook in cls._global_hooks:
            cls._global_hooks.remove(hook)

    @classmethod
    @contextmanager
    def hook_errors(cls, hook: ErrorHook) -> Iterator[None]:
        """Context manager to intercept errors across all Diagnostics instances."""
        cls.register_global_hook(hook)
        try:
            yield
        finally:
            cls.unregister_global_hook(hook)

    def add_hook(self, hook: ErrorHook) -> None:
        """Register an instance-level error hook."""
        if hook not in self._hooks:
            self._hooks.append(hook)

    def remove_hook(self, hook: ErrorHook) -> None:
        """Remove an instance-level error hook."""
        if hook in self._hooks:
            self._hooks.remove(hook)

    # ==========================================================================
    # TELEMETRY TARGET STACK
    # ==========================================================================

    @property
    def _target(self) -> info.Node | None:
        """Return the active telemetry node at the top of the stack, or `None`."""
        return self._targets[-1] if self._targets else None

    def node(
        self,
        name: str,
        description: str = "",
        set_target: bool = False,
        from_target: bool = True,
    ) -> info.Node:
        """Create a telemetry node and optionally push it onto the active target stack."""
        parent = (
            self._target
            if (from_target and self._target is not None)
            else self.stack
        )
        n = parent.node(name, description=description, priority=0)
        if set_target:
            self._targets.append(n)
        return n

    def down(self, get: bool = False) -> info.Node | None:
        """Pop the top telemetry node from the active target stack."""
        if not self._targets:
            return None
        n = self._targets.pop()
        return n if get else None

    def insert(self, node: info.Node) -> None:
        """Append an external telemetry `node` to the active target or main stack."""
        if self._target is not None:
            self._target.stack.append(node)
        else:
            self.stack.main.stack.append(node)

    def migrate(self, node: info.Node) -> None:
        """Replace the active target's internal stack with `node.stack`."""
        if self._target is not None:
            self._target.stack = node.stack
        else:
            raise RuntimeError("No active _target defined for migration.")

    def current(self) -> info.Node | info.StackInfo:
        """Return the active target node if present, or the root `StackInfo`."""
        return self._target or self.stack

    # ==========================================================================
    # LOGGING PRIMITIVES
    # ==========================================================================

    def sender(self, msg: str, t: Format.LogType) -> None:
        """Emit a formatted note to the current telemetry target."""
        self.current().note(msg, t)

    def debug(self, note: str) -> None:
        self.sender(note, "normal")

    def warn(self, note: str) -> None:
        self.sender(note, "warn")

    def advice(self, note: str) -> None:
        self.sender(note, "advice")

    def success(self, note: str) -> None:
        self.sender(note, "success")

    def error(self, note: str) -> None:
        self.sender(note, "error")

    # ==========================================================================
    # FAILURE CONTEXT & WEIGHTED STAGING PRIMITIVES
    # ==========================================================================

    @property
    def in_failure_context(self) -> bool:
        """Return True if currently inside a `failure_context` block."""
        return self._context_depth > 0

    @contextmanager
    def failure_context(self) -> Iterator[None]:
        """
        Reentrant context manager tracking nested speculative/protected execution depth.
        """
        self._context_depth += 1
        try:
            yield
        finally:
            self._context_depth = max(0, self._context_depth - 1)

    @contextmanager
    def failure_scope(self) -> Iterator[_FailureScope]:
        """Isolate speculative failures, restoring the incoming candidate on exit.

        The returned scope retains only its local candidate. Callers explicitly
        stage or publish that candidate when their parse result requires it.
        Signals and exceptions restore the incoming candidate without merging.
        """
        scope = _FailureScope()
        saved = self._staged_failure
        self._staged_failure = None
        try:
            with self.failure_context():
                yield scope
        finally:
            scope.candidate = self._staged_failure
            self._staged_failure = saved



    @property
    def staged_failure(self) -> error.Error | None:
        """Return the highest-weight staged `Error` candidate, or `None`."""
        return self._staged_failure[1] if self._staged_failure is not None else None

    @property
    def staged_weight(self) -> int:
        """Return the weight/offset of the current staged failure, or `-1` if none."""
        return self._staged_failure[0] if self._staged_failure is not None else -1

    def stage_failure(self, err: error.Error, weight: int = 0) -> error.Error:
        """
        Stage a candidate error if no candidate exists yet or if `weight` is
        strictly greater than the current candidate's weight (`weight > staged_weight`).
        """
        if self._staged_failure is None or weight > self._staged_failure[0]:
            self._staged_failure = (weight, err)
        return err

    def discard_staged_failure(self, min_weight: int | None = None) -> None:
        """
        Discard the staged candidate error unconditionally (if `min_weight` is `None`)
        or only if `min_weight > staged_weight`.
        """
        if min_weight is None or (
            self._staged_failure is not None and min_weight >= self._staged_failure[0]
        ):
            self._staged_failure = None

    def promote_staged_failure(
        self, fallback: error.Error | None = None
    ) -> error.Error | None:
        """
        Move the staged candidate (or `fallback`) into the permanent `_errors` list
        and return it, clearing the staging slot.
        """
        staged = self._staged_failure
        self._staged_failure = None
        target = staged[1] if staged is not None else fallback
        if target is not None:
            self.record_failure(target)
        return target

    @classmethod
    def dispatch_error_hooks(cls, sender: Any, err: error.Error) -> str:
        """
        Evaluate globally registered error hooks and return the resulting ErrorAction.
        """
        action = ErrorAction.STORE
        for hook in cls._global_hooks:
            decision = hook(sender, err)
            if decision is not None:
                action = decision
                if action == ErrorAction.OMIT:
                    break

        if action == ErrorAction.SUPPRESS_RAISE:
            setattr(err, "_suppress_raise", True)

        return action

    def record_failure(self, err: error.Error) -> error.Error | None:
        """
        Evaluate registered error hooks and record or suppress the failure.
        """
        all_hooks = list(self._global_hooks) + list(self._hooks)
        action = ErrorAction.STORE
        for hook in all_hooks:
            decision = hook(self, err)
            if decision is not None:
                action = decision
                if action == ErrorAction.OMIT:
                    return None

        if action == ErrorAction.OMIT:
            return None

        if action == ErrorAction.SUPPRESS_RAISE:
            setattr(err, "_suppress_raise", True)

        if not self._errors or self._errors[-1] is not err:
            self._errors.append(err)

        if action == ErrorAction.RAISE:
            err.raise_error()

        return err

    def clear_failures(self) -> None:
        """Clear all recorded errors and any staged candidate."""
        self._errors.clear()
        self._staged_failure = None

    def fail(
        self,
        err: error.Error | None = None,
        *,
        exit: bool | None = None,
    ) -> None:
        """
        Promote and raise err unless suppressed by an active error hook.
        """
        target = (
            err
            or self.promote_staged_failure()
            or (self._errors[-1] if self._errors else None)
        )
        if target is None:
            return

        res = self.record_failure(target)
        if res is None or getattr(target, "_suppress_raise", False):
            return

        target.raise_error(exit=exit)


__all__ = ["Diagnostics", "ErrorAction", "ErrorHook", "ansi_colors", "error", "info"]