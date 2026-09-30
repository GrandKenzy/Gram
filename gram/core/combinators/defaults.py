"""
Reglas predefinidas del framework (`gram.core.combinators.defaults`).
=====================================================================
Re-exporta las reglas nativas centralizadas en `gram.native.rules` y proporciona
la función constructora dinámica `create_rule`.
"""
from __future__ import annotations

from typing import Any

from gram.native.rules import (
    BLOCK,
    CUSTOM_RULES,
    DECLARATION,
    DEFAULT_RULES,
    DOCSTRING,
    ENDLINE,
    HEXADECIMAL,
    INDENT_BLOCK,
    PASS,
    PROGRAM,
    PROTECTED_MAX_ID,
    PROTECTED_MIN_ID,
    RECOMMENDED_MAX_PLUGIN_ID,
    RECOMMENDED_MIN_PLUGIN_ID,
    RULE_PRIORITIES,
    RULES_BY_ID,
    RULES_BY_NAME,
    add_rule,
    get_rule_by_id,
    get_rule_by_name,
    is_protected_id,
    reset_rules,
)


def create_rule(
    name: str,
    code: int,
    grammar: Any,
    description: str = "",
    priority: int = 0,
) -> type[Any]:
    """
    Crea y registra dinámicamente una nueva regla sintáctica personalizada.

    Args:
        name: Nombre identificativo de la regla.
        code: Código numérico asignado a la regla.
        grammar: Combinador sintáctico que define la regla.
        description: Descripción textual opcional.
        priority: Prioridad numérica para resolución de colisiones.

    Returns:
        type[RuleItem]: Clase de regla recién creada y registrada.
    """
    from gram.core.combinators.base import RuleItem

    new_rule = type(name, (RuleItem,), {
        "name": name,
        "code": code,
        "description": description,
        "grammar": grammar,
    })
    add_rule(new_rule, priority=priority)
    return new_rule


__all__ = [
    "PROGRAM",
    "DECLARATION",
    "ENDLINE",
    "BLOCK",
    "INDENT_BLOCK",
    "DOCSTRING",
    "HEXADECIMAL",
    "PASS",
    "PROTECTED_MIN_ID",
    "PROTECTED_MAX_ID",
    "RECOMMENDED_MIN_PLUGIN_ID",
    "RECOMMENDED_MAX_PLUGIN_ID",
    "DEFAULT_RULES",
    "CUSTOM_RULES",
    "RULES_BY_ID",
    "RULES_BY_NAME",
    "RULE_PRIORITIES",
    "is_protected_id",
    "get_rule_by_id",
    "get_rule_by_name",
    "add_rule",
    "create_rule",
    "reset_rules",
]
