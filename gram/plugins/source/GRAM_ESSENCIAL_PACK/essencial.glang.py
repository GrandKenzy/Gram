"""
Extensión GLANG para GRAM_ESSENCIAL_PACK (`essencial.glang.py`).
===============================================================
Añade combinadores esenciales de control sintáctico a GLANG:
If, Error, Req, Peek y Until.
"""
from __future__ import annotations

from gram.core.lexer.words import add_group, add_keyword


def setup_glang() -> None:
    """Registra palabras clave de combinadores esenciales en GLANG."""
    add_group("ESSENCIAL_OPS", color_group="#4EC9B0", allow_override=True)
    add_keyword("If", "#C586C0", group="ESSENCIAL_OPS", description="Parseo condicional sintáctico en GLANG.", allow_override=True)
    add_keyword("Error", "#F44747", group="ESSENCIAL_OPS", description="Emisión declarativa de error sintáctico.", allow_override=True)
    add_keyword("Req", "#4EC9B0", group="ESSENCIAL_OPS", description="Asignación de requerimiento obligatorio.", allow_override=True)
    add_keyword("Peek", "#DCDCAA", group="ESSENCIAL_OPS", description="Inspección no destructiva de tokens en el parser.", allow_override=True)
    add_keyword("Until", "#C586C0", group="ESSENCIAL_OPS", description="Consumo de tokens hasta alcanzar el delimitador objetivo.", allow_override=True)
