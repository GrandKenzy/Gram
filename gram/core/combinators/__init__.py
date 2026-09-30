"""
EN:
    Parsing Combinators Subsystem (`gram.core.combinators`).
    ========================================================
    Defines atomic, composable, and modular building blocks for formal grammar
    design and syntactic token stream analysis.

ES:
    Subpaquete de Combinadores Sintácticos (`gram.core.combinators`).
    ================================================================
    Define bloques de construcción atómicos, combinables y modulares
    para el diseño de gramáticas formales y análisis sintáctico.
"""
from __future__ import annotations

from gram.core.combinators import (
    additional_stack,
    alternative,
    any_grammar,
    base,
    defaults,
    enclosed,
    item,
    many,
    match,
    mods,
    optional,
    reference,
    separator,
    sequence,
    signals,
    some,
    tokenize,
)
from gram.core.combinators.additional_stack import CombinatorAdditionalStack
from gram.core.combinators.alternative import Alt, Alternative
from gram.core.combinators.any_grammar import AnyGrammar
from gram.core.combinators.base import (
    Combinator,
    RuleItem,
    RuleMeta,
    RuleType,
)
from gram.core.combinators.defaults import (
    BLOCK,
    DECLARATION,
    DOCSTRING,
    ENDLINE,
    HEXADECIMAL,
    INDENT_BLOCK,
    PASS,
    PROGRAM,
    create_rule,
)
from gram.core.combinators.enclosed import Bracketed, Enclosed
from gram.core.combinators.item import Item, ItemResult, Literal
from gram.core.combinators.many import Many
from gram.core.combinators.match import (
    MatchGroup,
    MatchKeyword,
    MatchSeqSymbol,
    MatchSymbol,
    MatchToken,
    generador_expr,
)
from gram.core.combinators.mods import (
    HARDCODED_MODS,
    custom_mod,
    get_custom_mods,
    get_hardcoded_mods,
    is_custom_mod,
    is_hardcoded_mod,
    register_custom_mod,
)
from gram.core.combinators.optional import Opt, OptResult, Optional
from gram.core.combinators.reference import Ref, Reference
from gram.core.combinators.separator import Sep, Separator, SeparatorResult
from gram.core.combinators.sequence import Seq, Sequence
from gram.core.combinators.signals import (
    AbortFlowSignal,
    BacktrackSignal,
    BreakFlowSignal,
    ControlFlowSignal,
    CutFlowSignal,
    SkipFlowSignal,
)
from gram.core.combinators.some import Some
from gram.core.combinators.tokenize import Tokenize

__all__ = [
    # Módulos
    "additional_stack",
    "alternative",
    "any_grammar",
    "base",
    "defaults",
    "enclosed",
    "item",
    "many",
    "match",
    "mods",
    "optional",
    "reference",
    "separator",
    "sequence",
    "signals",
    "some",
    "tokenize",
    # Clases Base y Metadatos
    "Combinator",
    "RuleItem",
    "RuleMeta",
    "RuleType",
    # Combinadores de Control y Estructura
    "Alt",
    "Alternative",
    "AnyGrammar",
    "Bracketed",
    "Enclosed",
    "Item",
    "ItemResult",
    "Literal",
    "Many",
    "Some",
    "Opt",
    "Optional",
    "OptResult",
    "Ref",
    "Reference",
    "Sep",
    "Separator",
    "SeparatorResult",
    "Seq",
    "Sequence",
    "Tokenize",
    # Matchers
    "MatchToken",
    "MatchKeyword",
    "MatchGroup",
    "MatchSeqSymbol",
    "MatchSymbol",
    "generador_expr",
    # Señales de Control de Flujo
    "ControlFlowSignal",
    "SkipFlowSignal",
    "BreakFlowSignal",
    "CutFlowSignal",
    "BacktrackSignal",
    "AbortFlowSignal",
    # Integración y Mods
    "CombinatorAdditionalStack",
    "HARDCODED_MODS",
    "is_hardcoded_mod",
    "get_hardcoded_mods",
    "register_custom_mod",
    "custom_mod",
    "is_custom_mod",
    "get_custom_mods",
    # Reglas predefinidas y constructores
    "create_rule",
    "PROGRAM",
    "DECLARATION",
    "ENDLINE",
    "BLOCK",
    "INDENT_BLOCK",
    "DOCSTRING",
    "HEXADECIMAL",
    "PASS",
]
