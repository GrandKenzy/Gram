"""
Reglas Nativas y Predefinidas de Gram Framework (`gram.native.rules`).
=====================================================================
Define las reglas sintácticas fundamentales (PROGRAM, DECLARATION, ENDLINE,
BLOCK, INDENT_BLOCK, DOCSTRING, HEXADECIMAL, PASS), así como los catálogos
globales de protección de identificadores numéricos y prioridades.
"""
from __future__ import annotations

from typing import Any

from gram import errors
from gram.core.combinators.alternative import Alt
from gram.core.combinators.base import Combinator, RuleItem, RuleType
from gram.core.combinators.match import MatchKeyword, MatchToken
from gram.core.combinators.optional import Opt
from gram.core.combinators.reference import Ref
from gram.core.combinators.sequence import Seq
from gram.utilities import error


class PROGRAM(RuleItem):
    """Regla raíz por defecto de un programa sintáctico."""
    code: int = 0
    name: str = "PROGRAM"
    description: str = "Regla raíz de programa sintáctico"
    grammar: Combinator | None = None
    suggestions: dict[int, Any] = {0: [("DECLARATION", "Declaración sintáctica general"), ("PASS", "Instrucción vacía")]}
    suggestions_autocomplete: bool = True


class DECLARATION(RuleItem):
    """Regla abstracta para declaraciones de alto nivel."""
    code: int = 1
    name: str = "DECLARATION"
    description: str = "Declaración sintáctica general de nivel superior"
    grammar: Combinator | None = None
    suggestions: dict[int, Any] = {}
    suggestions_autocomplete: bool = True


class ENDLINE(RuleItem):
    """Regla estructural de fin de línea con soporte de comentarios."""
    code: int = 2
    name: str = "ENDLINE"
    description: str = "Fin de línea (NEWLINE) o fin de archivo (EOF) con soporte de comentarios opcionales"
    is_structural: bool = True
    grammar: Combinator | None = Seq(
        Opt(MatchToken("COMMENT")),
        Alt(
            MatchToken("NEWLINE"),
            MatchToken("EOF"),
        ),
    )
    colors: dict[int, str] = {0: "#6A9955"}


class BLOCK(RuleItem):
    """Regla contenedora abstracta para bloques de instrucciones."""
    code: int = 3
    name: str = "BLOCK"
    description: str = "Bloque estructurado contenedor de instrucciones de código"
    is_structural: bool = True
    grammar: Combinator | None = None


class INDENT_BLOCK(RuleItem):
    """Regla estructural para bloques delimitados por indentación (INDENT ... DEDENT/EOF)."""
    code: int = 4
    name: str = "INDENT_BLOCK"
    description: str = "Bloque estructurado delimitado por indentación (INDENT ... DEDENT/EOF)"
    is_structural: bool = True
    grammar: Combinator | None = Seq(
        MatchToken("INDENT"),
        Ref(BLOCK),
        Alt(
            MatchToken("DEDENT"),
            MatchToken("EOF"),
        ),
    )


class DOCSTRING(RuleItem):
    """Regla para cadenas de documentación de bloque con fin de línea posterior."""
    code: int = 5
    name: str = "DOCSTRING"
    description: str = "Cadena de documentación multilínea de bloque finalizada por fin de línea"
    grammar: Combinator | None = Seq(
        MatchToken("DOCSTRING"),
        Ref(ENDLINE),
    )
    colors: dict[int, str] = {0: "#6A9955"}
    suggestions_autocomplete: bool = True


class HEXADECIMAL(RuleItem):
    """Regla predeterminada para valores hexadecimales."""
    code: int = 6
    name: str = "HEXADECIMAL"
    description: str = "Constante o literal hexadecimal"
    grammar: Combinator | None = Alt(
        MatchToken("STRING"),
        Seq(
            MatchToken("HASH"),
            Alt(
                MatchToken("IDENT"),
                MatchToken("NUMBER"),
            ),
        ),
    )
    colors: dict[int, str] = {0: "#B5CEA8"}


class PASS(RuleItem):
    """Instrucción nula o vacía."""
    code: int = 30
    name: str = "PASS"
    description: str = "Instrucción nula o vacía (no-op)"
    grammar: Combinator | None = Seq(
        MatchKeyword("pass"),
        Ref(ENDLINE),
    )
    suggestions: dict[int, Any] = {0: [("pass", "Instrucción nula o vacía")]}
    suggestions_autocomplete: bool = True


# =============================================================================
# CONSTANTES DE PROTECCIÓN DE IDENTIFICADORES
# =============================================================================
PROTECTED_MIN_ID: int = 0
PROTECTED_MAX_ID: int = 20
RECOMMENDED_MIN_PLUGIN_ID: int = 100
RECOMMENDED_MAX_PLUGIN_ID: int = 100000

DEFAULT_RULES: tuple[RuleType, ...] = (
    PROGRAM,
    DECLARATION,
    ENDLINE,
    BLOCK,
    INDENT_BLOCK,
    DOCSTRING,
    HEXADECIMAL,
    PASS,
)

# Catálogos globales de reglas
CUSTOM_RULES: dict[RuleType, RuleType] = {}
RULES_BY_ID: dict[int, RuleType] = {r.code: r for r in DEFAULT_RULES}
RULES_BY_NAME: dict[str, RuleType] = {r.name: r for r in DEFAULT_RULES}
RULE_PRIORITIES: dict[int, int] = {r.code: 1000000 for r in DEFAULT_RULES}


def is_protected_id(code: int) -> bool:
    """Verifica si un identificador numérico pertenece al rango protegido (0-20)."""
    return PROTECTED_MIN_ID <= code <= PROTECTED_MAX_ID


def get_rule_by_id(code: int) -> RuleType | None:
    """Obtiene una regla sintáctica a partir de su identificador numérico único."""
    return RULES_BY_ID.get(code)


def get_rule_by_name(name: str) -> RuleType | None:
    """Obtiene una regla sintáctica a partir de su nombre canónico."""
    return RULES_BY_NAME.get(name)


def add_rule(rule: RuleType, priority: int = 0) -> None:
    """
    Registra una regla en el catálogo global de reglas.
    Los identificadores del 0 al 20 son nativos y están protegidos contra
    sobrescritura por plugins o reglas externas.

    Args:
        rule: Regla sintáctica (RuleItem).
        priority: Prioridad de resolución en caso de colisión.
    """
    rule_code = getattr(rule, "code", None)
    rule_name = getattr(rule, "name", str(rule))

    if rule_code is not None:
        if is_protected_id(rule_code) and rule not in DEFAULT_RULES:
            error.GrammarError(
                "Identificador de regla protegido",
                errors.RULE_PROTECTED_ID,
                f"El identificador de regla {rule_code} ('{rule_name}') está en el rango protegido ({PROTECTED_MIN_ID}-{PROTECTED_MAX_ID}) reservado para reglas nativas de Gram.",
                f"Use un identificador en el rango recomendado para plugins ({RECOMMENDED_MIN_PLUGIN_ID} a {RECOMMENDED_MAX_PLUGIN_ID}).",
            ).raise_error()

        current_priority = RULE_PRIORITIES.get(rule_code, -1)

        if rule_code in RULES_BY_ID:
            if priority > current_priority:
                RULES_BY_ID[rule_code] = rule
                RULES_BY_NAME[rule_name] = rule
                RULE_PRIORITIES[rule_code] = priority
            else:
                return
        else:
            RULES_BY_ID[rule_code] = rule
            RULES_BY_NAME[rule_name] = rule
            RULE_PRIORITIES[rule_code] = priority

    RULES_BY_NAME[rule_name] = rule


def reset_rules() -> None:
    """Restaura el catálogo de reglas a su estado inicial nativo."""
    global CUSTOM_RULES, RULES_BY_ID, RULES_BY_NAME, RULE_PRIORITIES
    CUSTOM_RULES = {}
    RULES_BY_ID = {r.code: r for r in DEFAULT_RULES}
    RULES_BY_NAME = {r.name: r for r in DEFAULT_RULES}
    RULE_PRIORITIES = {r.code: 1000000 for r in DEFAULT_RULES}


__all__ = [
    "PROGRAM",
    "DECLARATION",
    "ENDLINE",
    "BLOCK",
    "INDENT_BLOCK",
    "DOCSTRING",
    "HEXADECIMAL",
    "PASS",
    "DEFAULT_RULES",
    "PROTECTED_MIN_ID",
    "PROTECTED_MAX_ID",
    "RECOMMENDED_MIN_PLUGIN_ID",
    "RECOMMENDED_MAX_PLUGIN_ID",
    "CUSTOM_RULES",
    "RULES_BY_ID",
    "RULES_BY_NAME",
    "RULE_PRIORITIES",
    "is_protected_id",
    "get_rule_by_id",
    "get_rule_by_name",
    "add_rule",
    "reset_rules",
]
