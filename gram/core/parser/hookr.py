"""
Parser Hook Registry (`gram.core.parser.hookr`).
================================================
Provides a lightweight event dispatcher (`Hookr`) enabling external observers
like `RayTracing` to react to parser events (such as savepoint and restore).
"""
from __future__ import annotations

from typing import Any, Callable


class Hookr:
    """
    Lightweight observer manager for parser lifecycle events.
    """

    def __init__(self) -> None:
        self.callables: list[Callable[..., Any]] = []

    def ran(self, *args: Any, **kwargs: Any) -> None:
        """
        Execute all registered subscriber callbacks with the given arguments.
        """
        for call in list(self.callables):
            call(*args, **kwargs)

    def trigger(self, *args: Any, **kwargs: Any) -> None:
        """Alias for `ran` following standard event dispatcher conventions."""
        self.ran(*args, **kwargs)

    def add(self, call: Callable[..., Any]) -> None:
        """Register a new callback handler if not already present."""
        if call not in self.callables:
            self.callables.append(call)

    def remove(self, call: Callable[..., Any]) -> None:
        """Unregister an existing callback handler."""
        if call in self.callables:
            self.callables.remove(call)

    def clear(self) -> None:
        """Remove all registered callback handlers."""
        self.callables.clear()


__all__ = ['Hookr']