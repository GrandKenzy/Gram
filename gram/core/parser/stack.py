"""
EN:
    Parser Telemetry and Diagnostics Stack (`gram.core.parser.stack`).
    ==================================================================
    Provides the dedicated `StackInfo` instance for collecting telemetry notes,
    nodes, and error records during syntax parsing execution.

ES:
    Pila de Telemetría y Errores para el Analizador Sintáctico (`gram.core.parser.stack`).
    ==================================================================================
    Proporciona la instancia `StackInfo` dedicada a recolectar notas, nodos y registros
    de errores durante el proceso de análisis sintáctico (parsing).
"""
from __future__ import annotations

from gram.utilities.info.stack import StackInfo

# Instancia global dedicada a la trazabilidad y telemetría del parser
stack: StackInfo = StackInfo(
    'parser-log',
    'PARSER',
    'Registro y diagnóstico del analizador sintáctico',
    expose_nodes=True,
)

__all__ = ['stack']
