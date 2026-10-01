"""
Extensión GLANG para el Plugin Expressions (`expressions.glang.py`).
=====================================================================
Añade palabras clave y colores a GLANG para definir operadores asociativos
y constructores de expresiones directamente en archivos de gramática .glang.
"""
from __future__ import annotations

from gram.core.lexer.words import add_group, add_keyword


def setup_glang() -> None:
    """Registra palabras clave de expresiones en la sintaxis de GLANG."""
    add_group("EXPRESSION_OPS", color_group="#DCDCAA", allow_override=True)
    add_keyword("ChainL", "#DCDCAA", group="EXPRESSION_OPS", description="Combinador asociativo por izquierda (ChainL).", allow_override=True)
    add_keyword("ChainR", "#DCDCAA", group="EXPRESSION_OPS", description="Combinador asociativo por derecha (ChainR).", allow_override=True)
    add_keyword("ExprBuilder", "#4EC9B0", group="EXPRESSION_OPS", description="Constructor declarativo de precedencia de operadores.", allow_override=True)
