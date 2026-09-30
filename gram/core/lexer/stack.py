"""
Pila de Telemetría para el Analizador Léxico (`gram.core.lexer.stack`).
======================================================================
Proporciona la instancia `StackInfo` dedicada a recolectar notas, nodos
de visitantes y diagnósticos jerárquicos durante el proceso de tokenización.
"""
from __future__ import annotations

from gram.utilities.info.stack import StackInfo

# Instancia global dedicada a la trazabilidad y telemetría del lexer
stack: StackInfo = StackInfo(
    'lexer-log',
    'LEXER',
    'Registro y diagnóstico del analizador léxico',
    expose_nodes=True,
)

__all__ = ['stack']
