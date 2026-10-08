"""
Submódulo de Reglas y Códigos Sintácticos (`gram.core.rules`).
=============================================================
EN:
    Exports automatic rule coding utilities (`AutoCode`, `SetCode`, `CodeManager`).
ES:
    Exporta utilidades de codificación automática de reglas (`AutoCode`, `SetCode`, `CodeManager`).
"""
from __future__ import annotations

from gram.core.rules.codes import (
    AutoCode,
    CodeManager,
    SetCode,
    code_manager,
)

__all__ = [
    "AutoCode",
    "CodeManager",
    "SetCode",
    "code_manager",
]
