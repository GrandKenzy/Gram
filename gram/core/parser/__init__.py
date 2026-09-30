"""
EN:
    Gram Framework Parsing Subsystem (`gram.core.parser`).
    ======================================================
    Exports core syntax analysis classes and infrastructure:
      - Checkpoint: Immutable cursor and bracket state snapshot for backtracking.
      - ParseControl: Controller for navigation, backtracking, lookahead, and telemetry.
      - Parser: Clean consumption engine and syntax orchestrator.
      - stack: Dedicated diagnostic stack for the parser.

ES:
    Subsistema de Análisis Sintáctico de Gram Framework (`gram.core.parser`).
    ========================================================================
    Exporta las clases centrales del análisis sintáctico e infraestructura:
      - Checkpoint: Instantánea inmutable del estado de cursores para backtracking.
      - ParseControl: Controlador de navegación, backtracking, lookahead y telemetría.
      - Parser: Motor de consumo limpio y orquestador sintáctico.
      - stack: Pila de diagnóstico dedicada del parser.
"""
from __future__ import annotations

from gram.core.parser import stack
from gram.core.parser.checkpoint import Checkpoint
from gram.core.parser.control import ParseControl
from gram.core.parser.core import Parser

__all__ = [
    'Checkpoint',
    'ParseControl',
    'Parser',
    'stack',
]
