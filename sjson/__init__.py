"""
Paquete SJSON — Super JSON.
===========================
Proporciona la API pública directa para compilar y analizar documentos SJSON.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Garantizar que el paquete Gram local esté disponible en sys.path
_LOCAL_GRAM = Path(__file__).resolve().parent
if str(_LOCAL_GRAM) not in sys.path:
    sys.path.insert(0, str(_LOCAL_GRAM))

from gram.sjson import (
    SJSONCalculationError,
    SJSONCompiler,
    SJSONError,
    SJSONExtendError,
    SJSONVariableError,
    compile,
    compile_file,
    deep_merge,
    parse,
)

__all__ = [
    "compile",
    "compile_file",
    "parse",
    "SJSONCompiler",
    "deep_merge",
    "SJSONError",
    "SJSONVariableError",
    "SJSONCalculationError",
    "SJSONExtendError",
]
