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
    expressions,
    item,
    load,
    many,
    match,
    negation,
    optional,
    peek,
    reference,
    req,
    save,
    separator,
    sequence,
    signals,
    skip,
    some,
    tag,
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
from .enclosed import Enclosed
from .error_combinator import ErrorCombinator
from .expressions import ArithmeticExpr, ConditionalExpr, DualExpr
from .item import Item, ItemNode, Literal, LiteralNode
from .load import Load
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
from .save import Save
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
from .tag import Tag
from .tokenize import Tokenize
from .until import Until

GrammarType = dict[RuleType, Combinator]

__all__ = [
    # Flow Control Signals
    "AbortFlowSignal",
    # Core Structural & Repetition Combinators
    "Alt",
    "ArithmeticExpr",
    # Base Classes & Metadata
    "AutoCode",
    "BacktrackSignal",
    "BreakFlowSignal",
    "Combinator",
    "ConditionalExpr",
    "ControlFlowSignal",
    "CutFlowSignal",
    "DualExpr",
    "Enclosed",
    # Advanced Control, Lookahead & Validation Combinators
    "ErrorCombinator",
    "GrammarType",
    "If",
    "Item",
    "ItemNode",
    "Literal",
    "LiteralNode",
    "Load",
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
    "Save",
    "Sep",
    "Separator",
    "SeparatorResult",
    "Seq",
    "Sequence",
    "SetCode",
    "Skip",
    "SkipFlowSignal",
    "Some",
    "Tag",
    "Tokenize",
    "Until",
    # Submodules
    "alternative",
    "base",
    "conditional",
    "enclosed",
    "error_combinator",
    "expressions",
    "generador_expr",
    "item",
    "load",
    "many",
    "match",
    "negation",
    "optional",
    "peek",
    "reference",
    "req",
    "save",
    "separator",
    "sequence",
    "signals",
    "skip",
    "some",
    "tag",
    "tokenize",
    "until",
]