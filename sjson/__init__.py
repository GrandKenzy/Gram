"""
Paquete SJSON — Super JSON.
===========================
Proporciona la API pública directa para compilar y analizar documentos SJSON.
"""
from __future__ import annotations

from sjson.compiler import (
    SJSONCompiler,
    compile,
    compile_file,
    deep_merge,
    parse,
)
from sjson.errors import (
    SJSONCalculationError,
    SJSONError,
    SJSONExtendError,
    SJSONVariableError,
)
from sjson.grammar import (
    get_sjson_grammar,
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
    "get_sjson_grammar",
]
