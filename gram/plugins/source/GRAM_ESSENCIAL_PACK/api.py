"""
API de ayuda para creación y registro simplificado de plugins en Gram.
"""
from __future__ import annotations

from typing import Any
from gram.core.combinators import defaults
from gram.core.combinators.base import RuleItem
from gram.core.combinators.mods import (
    HARDCODED_MODS,
    custom_mod,
    get_custom_mods,
    get_hardcoded_mods,
    is_custom_mod,
    is_hardcoded_mod,
    register_custom_mod,
)
from gram.core.lexer import word
from gram.utilities.error.codes import CodeError


def register_group(
    name: str,
    values: list[str | word.Keyword] | None = None,
    color_group: str = "#FFA500",
    description: str = "",
    *,
    allow_override: bool = False,
) -> word.WordGroup:
    """Registra un nuevo grupo léxico en el Lexer de Gram."""
    return word.add_group(name, values, color_group, description, allow_override=allow_override)


def register_keyword(
    name: str,
    color: str = "#FFFFFF",
    group: str | word.WordGroup | None = None,
    description: str = "",
    *,
    allow_override: bool = False,
) -> word.Keyword:
    """Registra una nueva palabra clave (keyword) en el Lexer de Gram."""
    group_name: str | None = None
    if group is not None:
        group_name = group.name if isinstance(group, word.WordGroup) else str(group)
        if not word.group_exists(group_name):
            word.add_group(
                name=group_name,
                values=[],
                color_group=color,
                description=f"Grupo autogenerado para {group_name}",
            )

    return word.add_keyword(
        name=name,
        hex_color=color,
        description=description,
        group=group_name,
        allow_override=allow_override,
    )


def register_rule(
    name: str,
    code: int,
    combinator: Any,
    description: str = "",
    priority: int = 0,
) -> type[RuleItem]:
    """Crea y registra una nueva regla sintáctica en Gram de forma automática."""
    nueva_regla = defaults.create_rule(
        name=name,
        code=code,
        grammar=combinator,
        description=description,
        priority=priority,
    )
    defaults.add_rule(nueva_regla, priority=priority)
    return nueva_regla


from gram.utilities.error.codes import CodeError, Codes


def register_error(
    code_tuple: tuple[int | Codes, ...],
    name: str,
) -> CodeError:
    """Crea un error formal compatible con el estándar OSGDC de Gram."""
    if all(isinstance(c, Codes) for c in code_tuple):
        return CodeError(tuple(code_tuple), name)
    groups = ["origin", "scope", "gravity", "documentation", "condition"]
    codes_objs = tuple(
        Codes(f"c_{val}", val, groups[i]) if not isinstance(val, Codes) else val
        for i, val in enumerate(code_tuple)
    )
    return CodeError(codes_objs, name)


register_combinator = register_custom_mod

__all__ = [
    "register_group",
    "register_keyword",
    "register_rule",
    "register_error",
    "register_combinator",
    "register_custom_mod",
    "custom_mod",
    "is_custom_mod",
    "is_hardcoded_mod",
    "get_custom_mods",
    "get_hardcoded_mods",
    "HARDCODED_MODS",
]
