"""
Gram Framework Parsing Subsystem (`gram.core.parser`).
======================================================
Exports the core syntactic analysis classes and state management infrastructure:
  - `Checkpoint`: Immutable cursor, bracket depth, and target stack snapshot.
  - `ParseState`: Controller for token navigation, backtracking, lookahead, and telemetry.
  - `Parser`: High-level token consumption engine and AST analysis orchestrator.
"""
from __future__ import annotations

from gram.core.parser.checkpoint import Checkpoint
from gram.core.parser.conversions import ConversionState
from gram.core.parser.control import ParseState
from gram.core.parser.core import Parser

__all__ = [
    'Checkpoint',
    'ConversionState',
    'ParseState',
    'Parser',
]
