"""
EN:
    Immutable Parser State Snapshot (`gram.core.parser.checkpoint`).
    ================================================================
    Defines the immutable data structure storing physical and virtual cursor positions,
    bracket delimiter nesting depth, and the active telemetry node, enabling atomic
    syntax transactions and side-effect-free backtracking.

ES:
    Instantánea Inmutable del Estado del Parser (`gram.core.parser.checkpoint`).
    ============================================================================
    Define la estructura de datos inmutable que almacena las posiciones de los
    cursores físico y virtual, profundidad de delimitadores y nodo de telemetría activo,
    posibilitando transacciones sintácticas atómicas y backtracking sin efectos colaterales.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gram.utilities.info import Node


@dataclass(frozen=True, slots=True)
class Checkpoint:
    """
    EN:
        Represents an immutable snapshot of the parser's internal state.
        Allows saving and restoring physical and virtual cursor positions
        and bracket delimiter depth during backtracking operations.

    ES:
        Representa una instantánea inmutable del estado interno del parser.
        Permite guardar y restaurar posiciones de cursores (físico y virtual)
        y la profundidad de delimitadores durante operaciones de backtracking.

    Attributes:
        pos (int): Real physical cursor position at the time of snapshot.
                   Posición del cursor físico real en el momento del guardado.
        virtual_pos (int): Virtual cursor position for speculative lookahead.
                           Posición del cursor virtual para exploración previa.
        bracket_depth (int): Bracket delimiter nesting depth (bracket-aware mode).
                             Profundidad de delimitadores abiertos (bracket-aware mode).
        target_node (Node | None): Active telemetry node at the time of snapshot.
                                   Nodo de telemetría activo en el momento del guardado.
    """
    pos: int
    virtual_pos: int
    bracket_depth: int = 0
    target_node: Node | None = None

    def __repr__(self) -> str:
        node_label = f", node={self.target_node.name!r}" if self.target_node is not None else ""
        return f"Checkpoint(pos={self.pos}, virtual={self.virtual_pos}, bracket={self.bracket_depth}{node_label})"


__all__ = ['Checkpoint']
