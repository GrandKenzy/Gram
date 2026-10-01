"""
Extensión GLANG para el Plugin Storage (`storage.glang.py`).
============================================================
Añade soporte sintáctico en GLANG para combinadores de memoria de tokens:
Save, Load y Tag.
"""
from __future__ import annotations

from gram.core.lexer.words import add_group, add_keyword


def setup_glang() -> None:
    """Registra palabras clave de storage en la sintaxis de GLANG."""
    add_group("STORAGE_OPS", color_group="#C586C0", allow_override=True)
    add_keyword("Save", "#C586C0", group="STORAGE_OPS", description="Almacena el token procesado en el registro interno.", allow_override=True)
    add_keyword("Load", "#C586C0", group="STORAGE_OPS", description="Compara y consume contra un token previamente guardado.", allow_override=True)
    add_keyword("Tag", "#CE9178", group="STORAGE_OPS", description="Etiqueta el nodo sintáctico en el AST.", allow_override=True)
