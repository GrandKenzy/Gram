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
from itertools import chain
from typing import Any, ClassVar
from weakref import WeakSet

from . import Format, ansi_colors, error, info

ErrorHook = Callable[['Diagnostics', error.Error], str | None]


class ErrorAction:
    """String directives returned by error hooks."""

    STORE = "store"
    OMIT = "omit"
    RAISE = "raise"
    SUPPRESS_RAISE = "suppress"


class _FailureScope:
    """Failure candidate captured when an isolated scope exits."""

    __slots__ = ('candidate',)

    def __init__(self) -> None:
        self.candidate: tuple[int, error.Error] | None = None


class Diagnostics:
    """
    Framework-agnostic controller for telemetry and staged error handling.

    The class is intentionally subclass-friendly: consumers may add state and
    may continue to inspect the compatibility attributes ``_targets``,
    ``_errors`` and ``_staged_failure``.
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
        """Initialize telemetry and failure-tracking state.

        Args:
            file: Logical log file name.
            name: Root telemetry node name.
            description: Root telemetry node description.
            expose_nodes: Whether child nodes are included when rendered.
            generate_log_file: Whether to register the log file immediately.
            generate_on_error: Whether to write the stack at process exit.
        """
        self.stack = info.StackInfo(
            file,
            name,
            description,
            expose_nodes,
            generate_on_error,
            generate_log_file,
        )
        self._recorded_errors: WeakSet[error.Error] = WeakSet()
        self._errors: list[error.Error] = []
        self._context_depth: int = 0
        self._staged_failure: tuple[int, error.Error] | None = None
        self._hooks: list[ErrorHook] = []

    @classmethod
    def register_global_hook(cls, hook: ErrorHook) -> None:
        """Register a global hook once, preserving registration order.

        Complexity: O(H), where H is the number of registered global hooks.
        """
        if hook not in cls._global_hooks:
            cls._global_hooks.append(hook)

    @classmethod
    def unregister_global_hook(cls, hook: ErrorHook) -> None:
        """Remove a previously registered global hook if present.

        Complexity: O(H), where H is the number of registered global hooks.
        """
        if hook in cls._global_hooks:
            cls._global_hooks.remove(hook)

    @classmethod
    @contextmanager
    def hook_errors(cls, hook: ErrorHook) -> Iterator[None]:
        """Temporarily register a global hook for all diagnostics instances.

        The hook is removed even when the context exits with an exception.
        """
        cls.register_global_hook(hook)
        try:
            yield
        finally:
            cls.unregister_global_hook(hook)

    def add_hook(self, hook: ErrorHook) -> None:
        """Register an instance hook once, preserving registration order."""
        if hook not in self._hooks:
            self._hooks.append(hook)

    def remove_hook(self, hook: ErrorHook) -> None:
        """Remove a previously registered instance hook if present."""
        if hook in self._hooks:
            self._hooks.remove(hook)

    # ==========================================================================
    # TELEMETRY TARGET STACK
    # ==========================================================================

    @property
    def _target(self) -> info.Node | None:
        """Return the active target node, or ``None`` when none is active."""
        return self.stack.target

    @property
    def _targets(self) -> list[info.Node]:
        """Return the mutable target-list view owned by :class:`StackInfo`."""
        return self.stack.targets

    @_targets.setter
    def _targets(self, targets: list[info.Node]) -> None:
        self.stack.replace_targets(targets)

    def node(
        self,
        name: str,
        description: str = "",
        set_target: bool = False,
        from_target: bool = True,
    ) -> info.Node:
        """Create a telemetry node and optionally activate it as a target.

        Args:
            name: Child node name.
            description: Child node description.
            set_target: Push the new node onto the target stack when true.
            from_target: Use the active target as parent when true.

        Returns:
            The newly created node.
        """
        return self.stack.node(
            name,
            description,
            set_target=set_target,
            from_target=from_target,
        )

    def down(self, get: bool = False) -> info.Node | None:
        """Pop the active target and optionally return it."""
        return self.stack.down(get=get)

    def insert(self, node: info.Node) -> None:
        """Append an external node to the active target or root node."""
        self.stack.insert(node)

    def migrate(self, node: info.Node) -> None:
        """Replace the active target contents with ``node.stack``.

        Raises:
            RuntimeError: If no target is active.
        """
        self.stack.migrate(node)

    def current(self) -> info.Node:
        """Return the active target node or the root telemetry node."""
        return self.stack.current()

    # ==========================================================================
    # LOGGING PRIMITIVES
    # ==========================================================================

    def sender(self, msg: str, t: Format.LogType) -> None:
        """Emit a typed note on the current telemetry node."""
        self.current().emit(msg, t)

    def debug(self, note: str) -> None:
        """Emit a normal diagnostic note."""
        self.sender(note, "normal")

    def warn(self, note: str) -> None:
        """Emit a warning diagnostic note."""
        self.sender(note, "warn")

    def advice(self, note: str) -> None:
        """Emit an advice diagnostic note."""
        self.sender(note, "advice")

    def success(self, note: str) -> None:
        """Emit a success diagnostic note."""
        self.sender(note, "success")

    def error(self, note: str) -> None:
        """Emit an error diagnostic note."""
        self.sender(note, "error")

    def fatal(self, note: str) -> None:
        """Emit a fatal diagnostic note."""
        self.sender(note, "fatal")

    # ==========================================================================
    # FAILURE CONTEXT & WEIGHTED STAGING PRIMITIVES
    # ==========================================================================

    @property
    def in_failure_context(self) -> bool:
        """Return whether execution is inside at least one failure context."""
        return self._context_depth > 0

    @contextmanager
    def failure_context(self) -> Iterator[None]:
        """Track re-entrant speculative or protected execution depth."""
        self._context_depth += 1
        try:
            yield
        finally:
            self._context_depth = max(0, self._context_depth - 1)

    @contextmanager
    def failure_scope(self) -> Iterator[_FailureScope]:
        """Isolate speculative failures and restore the incoming candidate.

        The yielded scope retains only its local candidate. Callers decide
        whether to publish it after the scope exits. Exceptions and control-flow
        signals restore the incoming candidate without merging.
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
        """Return the current staged error candidate, or ``None``."""
        return self._staged_failure[1] if self._staged_failure is not None else None

    @property
    def staged_weight(self) -> int:
        """Return the current candidate weight, or ``-1`` when unset."""
        return self._staged_failure[0] if self._staged_failure is not None else -1

    def stage_failure(self, err: error.Error, weight: int = 0) -> error.Error:
        """Stage ``err`` when it is deeper than the current candidate.

        Args:
            err: Candidate error to stage.
            weight: Cursor position or other comparable failure depth.

        Returns:
            The supplied error.

        Complexity: O(1).
        """
        if self._staged_failure is None or weight > self._staged_failure[0]:
            self._staged_failure = (weight, err)
        return err

    def discard_staged_failure(self, min_weight: int | None = None) -> None:
        """Discard the staged candidate when the supplied threshold permits it.

        ``None`` always discards. Otherwise the candidate is discarded when
        ``min_weight >= staged_weight``.
        """
        if min_weight is None or (
            self._staged_failure is not None and min_weight >= self._staged_failure[0]
        ):
            self._staged_failure = None

    def promote_staged_failure(
        self,
        fallback: error.Error | None = None,
        *,
        record: bool = True,
    ) -> error.Error | None:
        """Clear and return the staged candidate or fallback error.

        Args:
            fallback: Error to use when no candidate is staged.
            record: Record the selected error before returning it.

        Returns:
            The selected error, or ``None`` when neither source is available.
        """
        staged = self._staged_failure
        self._staged_failure = None
        target = staged[1] if staged is not None else fallback
        if target is not None and record:
            self.record_failure(target)
        return target

    @staticmethod
    def _resolve_hook_action(
        sender: Any,
        err: error.Error,
        hooks: Iterator[ErrorHook],
    ) -> str:
        """Evaluate a hook stream and return its final action."""
        action = ErrorAction.STORE
        for hook in hooks:
            decision = hook(sender, err)
            if decision is not None:
                action = decision
                if action == ErrorAction.OMIT:
                    break

        if action == ErrorAction.SUPPRESS_RAISE:
            setattr(err, "_suppress_raise", True)

        return action

    @classmethod
    def dispatch_error_hooks(cls, sender: Any, err: error.Error) -> str:
        """Evaluate global hooks and return the resulting ``ErrorAction``."""
        return cls._resolve_hook_action(sender, err, iter(cls._global_hooks))

    def record_failure(self, err: error.Error) -> error.Error | None:
        """Evaluate hooks and record, suppress, omit, or raise ``err``.

        Global hooks run before instance hooks. The same error instance is
        processed at most once by this ``Diagnostics`` instance.

        Complexity: O(H), where H is the number of applicable hooks.
        """
        if err in self._recorded_errors:
            return err

        hooks = chain(tuple(self._global_hooks), tuple(self._hooks))
        action = self._resolve_hook_action(self, err, hooks)
        self._recorded_errors.add(err)
        if action == ErrorAction.OMIT:
            return None

        setattr(err, "_error_hooks_dispatched", True)

        if not self._errors or self._errors[-1] is not err:
            self._errors.append(err)

        if action == ErrorAction.RAISE:
            err.raise_error(dispatch=False)

        return err

    def clear_failures(self) -> None:
        """Clear recorded errors, deduplication state, and staged candidates."""
        self._errors.clear()
        self._staged_failure = None
        self._recorded_errors.clear()

    def fail(
        self,
        err: error.Error | None = None,
        *,
        exit: bool | None = None,
    ) -> None:
        """Record and raise the selected error unless a hook suppresses it.

        Args:
            err: Explicit error to record and raise.
            exit: Optional override for the host exit policy.
        """
        target = err
        if target is None:
            target = self.promote_staged_failure(record=False)
        if target is None and self._errors:
            target = self._errors[-1]
        if target is None:
            return

        res = self.record_failure(target)
        if res is None or getattr(target, "_suppress_raise", False):
            return

        target.raise_error(exit=exit)


__all__ = ["Diagnostics", "ErrorAction", "ErrorHook", "ansi_colors", "error", "info"]
