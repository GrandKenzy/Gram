"""
Paquete CJSON / SJSON — JSON con estilo C potenciado por Gram.
"""
from __future__ import annotations

from gram.sjson import (
    SJSONCalculationError as CJSONCalculationError,
    SJSONCompiler as CJSONCompiler,
    SJSONError as CJSONError,
    SJSONExtendError as CJSONExtendError,
    SJSONVariableError as CJSONVariableError,
    compile,
    compile_file,
    deep_merge,
    parse,
)

__all__ = [
    "compile",
    "compile_file",
    "parse",
    "CJSONCompiler",
    "deep_merge",
    "CJSONError",
    "CJSONVariableError",
    "CJSONCalculationError",
    "CJSONExtendError",
]
