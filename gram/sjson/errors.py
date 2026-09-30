"""
Excepciones y Errores del Subsistema SJSON (`gram.sjson.errors`).
================================================================
Define los tipos de error especializados para el análisis, evaluación
y compilación de documentos SJSON con soporte para línea y columna.
"""
from __future__ import annotations

from typing import Any


class SJSONError(Exception):
    """Error base de compilación o sintaxis en documentos SJSON."""

    def __init__(
        self,
        message: str,
        line: int | None = None,
        col: int | None = None,
        source_file: str | None = None,
    ) -> None:
        self.message = message
        self.line = line
        self.col = col
        self.source_file = source_file

        loc_str = ""
        if source_file:
            loc_str += f" en '{source_file}'"
        if line is not None:
            loc_str += f" (línea {line}"
            if col is not None:
                loc_str += f", col {col}"
            loc_str += ")"

        full_msg = f"[Error SJSON]{loc_str}: {message}"
        super().__init__(full_msg)


class SJSONVariableError(SJSONError):
    """Error cuando una variable no existe o viola el tipo permitido (solo números y strings)."""
    pass


class SJSONCalculationError(SJSONError):
    """Error durante la evaluación de una expresión o cálculo aritmético/string."""
    pass


class SJSONExtendError(SJSONError):
    """Error durante la resolución de herencia o importación de archivos mediante extend."""
    pass
