"""
Módulo de ejemplo SJSON (Super JSON con Gram Framework).
========================================================
Provee las utilidades de parseo y compilación de Super JSON a JSON estándar.
"""
from __future__ import annotations

from gram.sjson import (
    SJSONCalculationError,
    SJSONCompiler,
    SJSONError,
    SJSONExtendError,
    SJSONVariableError,
    compile,
    compile_file,
    parse,
)

__all__ = [
    "compile",
    "compile_file",
    "parse",
    "SJSONCompiler",
    "SJSONError",
    "SJSONVariableError",
    "SJSONCalculationError",
    "SJSONExtendError",
]
