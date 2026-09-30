"""
GLANG: Lenguaje Declarativo de Gramáticas de Gram Framework (`gram.glang`).
==========================================================================
Permite definir gramáticas completas en archivos `.glang` usando una sintaxis concisa,
legible y expresiva basada en combinadores sintácticos.
"""
from __future__ import annotations

from gram.glang.grammar import grammar
from gram.glang.main import LanguageCompiler, compile, parse_dsl, parse_file, parse_glang_file
from gram.glang.reinterpreter import (
    CombinatorBuilderRegistry,
    DynamicRuleRegistry,
    ReinterpreterEngine,
    combinator_builders,
)


def version_info() -> str:
    """Retorna la información de versión y soporte de GLang."""
    return """\
GLang v2.0.0
=============
Lenguaje declarativo de gramáticas de Gram Framework v2.0.0.
Soporta definición de reglas, combinadores estructurales, atómicos y referencias.
"""


def show_version_info(get: bool = False) -> str | None:
    """Muestra o retorna la información de versión de GLang."""
    info = version_info()
    if get:
        return info
    print(info)
    return None


__all__ = [
    'grammar',
    'parse_dsl',
    'parse_file',
    'parse_glang_file',
    'compile',
    'LanguageCompiler',
    'ReinterpreterEngine',
    'DynamicRuleRegistry',
    'CombinatorBuilderRegistry',
    'combinator_builders',
    'version_info',
    'show_version_info',
]
