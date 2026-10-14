"""
Parsing Combinators Subsystem (`gram.core.combinators`).
========================================================
Exposes atomic, composable, and modular building blocks for formal grammar
design and syntactic token stream analysis.
"""
from __future__ import annotations

from . import (
    alternative,
    base,
    conditional,
    enclosed,
    error_combinator,
    item,
    many,
    match,
    negation,
    optional,
    peek,
    reference,
    req,
    separator,
    sequence,
    signals,
    skip,
    some,
    tokenize,
    until,
)
from .alternative import Alt
from .base import (
    AutoCode,
    Combinator,
    RuleItem,
    RuleMeta,
    RuleType,
    SetCode,
)
from .conditional import If
from .enclosed import Bracketed, Enclosed
from .error_combinator import ErrorCombinator
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
from .negation import Not
from .optional import Opt
from .peek import Peek
from .reference import Ref
from .req import Req
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
from .skip import Skip
from .some import Some
from .tokenize import Tokenize
from .until import Until

GrammarType = dict[RuleType, Combinator]

__all__ = [
    # Flow Control Signals
    "AbortFlowSignal",
    # Core Structural & Repetition Combinators
    "Alt",
    # Base Classes & Metadata
    "AutoCode",
    "BacktrackSignal",
    "Bracketed",
    "BreakFlowSignal",
    "Combinator",
    "ControlFlowSignal",
    "CutFlowSignal",
    "Enclosed",
    # Advanced Control, Lookahead & Validation Combinators
    "ErrorCombinator",
    "GrammarType",
    "If",
    "Item",
    "ItemNode",
    "Literal",
    "LiteralNode",
    "Many",
    # Token Matchers
    "MatchGroup",
    "MatchKeyword",
    "MatchSeqSymbol",
    "MatchSymbol",
    "MatchToken",
    "Not",
    "Opt",
    "Peek",
    "Ref",
    "Req",
    "RuleItem",
    "RuleMeta",
    "RuleType",
    "Sep",
    "Separator",
    "SeparatorResult",
    "Seq",
    "Sequence",
    "SetCode",
    "Skip",
    "SkipFlowSignal",
    "Some",
    "Tokenize",
    "Until",
    # Submodules
    "alternative",
    "base",
    "conditional",
    "enclosed",
    "error_combinator",
    "generador_expr",
    "item",
    "many",
    "match",
    "negation",
    "optional",
    "peek",
    "reference",
    "req",
    "separator",
    "sequence",
    "signals",
    "skip",
    "some",
    "tokenize",
    "until",
]