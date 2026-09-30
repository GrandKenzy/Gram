"""
Subsistema SJSON — JSON con Variables, Cálculos y Herencia (`gram.sjson`).
========================================================================
Proporciona soporte completo para:
  1. Variables numéricas y strings (`let <nombre> = <valor>`).
  2. Cálculos y expresiones aritméticas (`+`, `-`, `*`, `/`, `%`) y concatenación de texto.
  3. Comentarios de una línea con `//`.
  4. Importación y herencia de otros JSON mediante `{ extend: "ruta" }`.
  5. Compilación a JSON común y corriente (RFC 8259).
"""
from __future__ import annotations

from gram.sjson.compiler import (
    SJSONCompiler,
    compile,
    compile_file,
    deep_merge,
    parse,
)
from gram.sjson.errors import (
    SJSONCalculationError,
    SJSONError,
    SJSONExtendError,
    SJSONVariableError,
)
from gram.sjson.grammar import (
    SJSON_ARRAY,
    SJSON_EXPR,
    SJSON_OBJECT,
    SJSON_PAIR,
    SJSON_VALUE,
    SJSON_VAR_DECL,
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
    "SJSON_VALUE",
    "SJSON_PAIR",
    "SJSON_OBJECT",
    "SJSON_ARRAY",
    "SJSON_VAR_DECL",
    "SJSON_EXPR",
]
