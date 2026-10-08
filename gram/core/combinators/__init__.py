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

from . import (
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
    query,
    reference,
    separator,
    sequence,
    signals,
    some,
    tokenize,
)
from .additional_stack import CombinatorAdditionalStack
from .alternative import Alt, Alternative
from .any_grammar import AnyGrammar
from .base import (
    AutoCode,
    Combinator,
    RuleItem,
    RuleMeta,
    RuleType,
    SetCode,
)
from .query import Query, query
from gram.core.hints import (
    Hints,
    InlayHintKind,
    VirtualHint,
    VirtualHintManager,
)
from .defaults import (
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
from .enclosed import Bracketed, Enclosed
from .item import Item, ItemNode, Literal, LiteralNode
from .many import Many
from .match import (
    MatchGroup,
    MatchKeyword,
    MatchSeqSymbol,
    MatchSymbol,
    MatchToken,
    generador_expr,
)
from .mods import (
    HARDCODED_MODS,
    custom_mod,
    get_custom_mods,
    get_hardcoded_mods,
    is_custom_mod,
    is_hardcoded_mod,
    register_custom_mod,
)
from .optional import Opt, OptResult, Optional
from .reference import Ref, Reference
from .separator import Sep, Separator, SeparatorResult
from .sequence import Seq, Sequence
from .signals import (
    AbortFlowSignal,
    BacktrackSignal,
    BreakFlowSignal,
    ControlFlowSignal,
    CutFlowSignal,
    SkipFlowSignal,
)
from .some import Some
from .tokenize import Tokenize

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
    "query",
    "reference",
    "separator",
    "sequence",
    "signals",
    "some",
    "tokenize",
    # Clases Base y Metadatos
    "Combinator",
    "AutoCode",
    "RuleItem",
    "RuleMeta",
    "RuleType",
    "SetCode",
    "Query",
    "Hints",
    "InlayHintKind",
    "VirtualHint",
    "VirtualHintManager",
    # Combinadores de Control y Estructura
    "Alt",
    "Alternative",
    "AnyGrammar",
    "Bracketed",
    "Enclosed",
    "Item",
    "ItemNode",
    "Literal",
    "LiteralNode",
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
