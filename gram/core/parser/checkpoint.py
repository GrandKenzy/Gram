"""
Immutable Parser State Snapshot (`gram.core.parser.checkpoint`).
================================================================
Defines the immutable data structure storing physical and virtual cursor positions,
bracket delimiter nesting depth, and the active diagnostic target stack, enabling
atomic syntax transactions and side-effect-free backtracking.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from gram.utilities.info import Node


@dataclass(frozen=True, slots=True)
class Checkpoint:
    """
    Represents an immutable snapshot of the parser's internal state.

    Stores physical and virtual cursor positions, bracket delimiter depth,
    and an immutable copy of the active diagnostic target stack to support
    safe state restoration during backtracking operations.

    Attributes:
        pos (int): Physical cursor position at the time of the snapshot.
        vpos (int): Virtual cursor position for speculative lookahead.
        bracket_depth (int): Open bracket delimiter nesting depth.
        targets (tuple[Node, ...]): Snapshot of the active diagnostic node stack.
        name (str): Descriptive identifier for the checkpoint.
    """
    pos: int
    vpos: int
    bracket_depth: int = 0
    targets: tuple[Node, ...] = ()
    storage: tuple[tuple[str, Any], ...] = ()
    tk_tags: tuple[tuple[int, frozenset[str]], ...] = ()
    token_overrides: tuple[tuple[int, Any], ...] = ()
    name: str = 'checkpoint'

    @property
    def target(self) -> Node | None:
        """Return the top diagnostic node from the saved stack, if any."""
        return self.targets[-1] if self.targets else None

    def __repr__(self) -> str:
        node_label = f", target={self.target}" if self.target is not None else ""
        return (
            f"Checkpoint(name={self.name!r}, pos={self.pos}, "
            f"virtual={self.vpos}, bracket={self.bracket_depth}{node_label})"
        )


__all__ = ['Checkpoint']