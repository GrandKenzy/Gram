"""
Reglas Sintácticas de Alto Nivel de GLANG (`gram.glang.rules.decl_rules`).
==========================================================================
Define las declaraciones maestras de sintaxis en GLang:
- `INCLUDE`: Directiva para incluir gramáticas y plugins cargados.
- `CLN_DEFINE`: Declaración de una regla con nombre y código.
- `CLN_DECLARATION`: Definición del cuerpo gramatical de una regla.
- `CLN_KEYWORD`: Definición de palabras clave reservadas.
- `CLN_PROGRAM`: Punto de entrada principal ([0]:).
"""
from __future__ import annotations

from typing import Any

from gram.core.combinators import (
    Alt,
    MatchGroup,
    MatchKeyword,
    MatchToken,
    Opt,
    Ref,
    RuleItem,
    Seq,
    Some,
)
from gram.glang.rules.decl_combinators import CLN_REFERENCE
from gram.native.rules import (
    BLOCK,
    DOCSTRING,
    ENDLINE,
    HEXADECIMAL,
)


def _get_plugin_suggestions() -> list[tuple[str, str]]:
    """Obtiene los plugins disponibles para sugerencias en include."""
    known: dict[str, str] = {
        "GRAM_ESSENCIAL_PACK": "Pack de utilidades esenciales de Gram",
    }
    try:
        from gram.plugins.registry import all_plugins
        for p in all_plugins():
            known[p.name] = f"Plugin '{p.name}' disponible en Gram"
    except Exception:
        pass
    return [(k, v) for k, v in sorted(known.items())]


class INCLUDE(RuleItem):
    name: str = 'INCLUDE'
    code: int = 50
    description: str = 'Directiva para incluir y fusionar gramáticas de plugins instalados (ej. include "mi_plugin").'
    grammar = Seq(
        MatchKeyword('include'),
        MatchToken('STRING'),
        Ref(ENDLINE),
    )
    colors: dict[int, str] = {1: "#88FF00"}
    suggestions: dict[int, Any] = {1: _get_plugin_suggestions}
    suggestions_autocomplete: bool = True


class CLN_DEFINE(RuleItem):
    name: str = 'DEFINE'
    code: int = 51
    description: str = 'Declara una regla sintáctica con su nombre y código numérico único (ej. define MY_RULE 1000).'
    grammar = Seq(
        MatchKeyword('define'),
        MatchToken('IDENT'),
        MatchToken('NUMBER'),
        Ref(ENDLINE),
        Opt(Ref(DOCSTRING)),
    )
    colors: dict[int, str] = {1: '#9CDCFE', 2: '#B5CEA8'}
    suggestions: dict[int, Any] = {
        1: [('MY_RULE', 'Nombre de regla sintáctica')],
        2: [('1000', 'Código numérico único recomendado (100 a 100000)')],
    }
    suggestions_autocomplete: bool = True


class CLN_DECLARATION(RuleItem):
    name: str = 'DECLARATION'
    code = 54
    description = 'Define el cuerpo gramatical de una regla con un combinador principal (ej. MY_RULE Seq:).'
    grammar = Seq(
        MatchToken('IDENT'),
        MatchGroup('CLN_COMBINATOR_MAIN'),
        MatchToken('COLON'),
        Ref(ENDLINE),
        Ref(BLOCK),
    )
    colors: dict[int, str] = {0: '#4EC9B0', 2: '#D4D4D4'}
    suggestions: dict[int, Any] = {
        1: [
            ('Seq', 'Combinador de secuencia estricta'),
            ('Alt', 'Combinador de alternativa'),
            ('Many', 'Cero o más repeticiones (*)'),
            ('Some', 'Una o más repeticiones (+)'),
        ]
    }
    suggestions_autocomplete: bool = True


class CLN_KEYWORD(RuleItem):
    name: str = 'KEYWORD'
    code: int = 52
    description = 'Bloque declarativo para registrar una nueva palabra clave reservada con color, descripción y grupo.'
    grammar = Seq(
        MatchKeyword('Keyword'),
        MatchToken('STRING'),
        MatchToken('COLON'),
        Ref(ENDLINE),
        MatchToken('INDENT'),
        Some(
            Alt(
                # color
                Seq(
                    MatchKeyword('color'),
                    MatchToken('COLON'),
                    Ref(HEXADECIMAL),
                    Ref(ENDLINE),
                ),
                # description
                Seq(
                    MatchKeyword('description'),
                    MatchToken('COLON'),
                    Alt(
                        MatchToken('STRING'),
                        MatchToken('DOCSTRING'),
                    ),
                    Ref(ENDLINE),
                ),
                # group
                Seq(
                    MatchKeyword('group'),
                    MatchToken('COLON'),
                    MatchToken('STRING'),
                    Ref(ENDLINE),
                ),
            )
        ),
        MatchToken('DEDENT'),
    )
    colors: dict[int, str] = {1: '#CE9178', 2: '#D4D4D4'}
    suggestions: dict[int, Any] = {0: [('Keyword', 'Definición de palabra clave')]}
    suggestions_autocomplete: bool = True


class CLN_PROGRAM(RuleItem):
    name: str = 'PROGRAM'
    code = 30
    description = 'Declaración del punto de entrada principal del programa DSL (ej. [0]:).'
    grammar = Seq(
        MatchToken('LBRACKET'),
        MatchToken('NUMBER'),
        MatchToken('RBRACKET'),
        MatchToken('COLON'),
        Ref(ENDLINE),
        MatchToken('INDENT'),
        Ref(CLN_REFERENCE),
        Alt(
            MatchToken('DEDENT'),
            MatchToken('EOF'),
        ),
    )
    colors: dict[int, str] = {1: '#B5CEA8', 3: '#D4D4D4'}
    suggestions_autocomplete: bool = True


__all__ = [
    'INCLUDE',
    'CLN_DEFINE',
    'CLN_DECLARATION',
    'CLN_KEYWORD',
    'CLN_PROGRAM',
]
