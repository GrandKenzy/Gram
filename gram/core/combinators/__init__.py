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
    convert,
    enclosed,
    error_combinator,
    expected,
    expressions,
    item,
    load,
    many,
    match,
    negation,
    optional,
    peek,
    preprocess,
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
    until_indent,
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
from .convert import Convert
from .enclosed import Enclosed
from .error_combinator import ErrorCombinator
from .expected import Expected
from .expressions import (
    ArithmeticExpr,
    ConditionalExpr,
    DualExpr,
    bind_left,
    bind_right,
)
from .item import Item, ItemNode, Literal, LiteralNode
from .load import Load
from .many import Many
from .match import (
    MatchGroup,
    MatchKeyword,
    MatchSeqSymbol,
    MatchToken,
    generador_expr,
)
from .negation import Not
from .optional import Opt
from .peek import Peek
from .preprocess import Preprocess
from .reference import Ref
from .req import Req
from .save import Save
from .separator import ArrayNode, Separator
from .sequence import Seq
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
from .until_indent import UntilIndent

GrammarType = dict[RuleType, Combinator]

__all__ = [
    # Flow Control Signals
    "AbortFlowSignal",
    # Core Structural & Repetition Combinators
    "Alt",
    "ArithmeticExpr",
    "ArrayNode",
    # Base Classes & Metadata
    "AutoCode",
    "BacktrackSignal",
    "BreakFlowSignal",
    "Combinator",
    "ConditionalExpr",
    "ControlFlowSignal",
    "CutFlowSignal",
    "Convert",
    "DualExpr",
    "bind_left",
    "bind_right",
    "Enclosed",
    # Advanced Control, Lookahead & Validation Combinators
    "ErrorCombinator",
    "Expected",
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
    "MatchToken",
    "Not",
    "Opt",
    "Peek",
    "Preprocess",
    "Ref",
    "Req",
    "RuleItem",
    "RuleMeta",
    "RuleType",
    "Save",
    "Separator",
    "Seq",
    "SetCode",
    "Skip",
    "SkipFlowSignal",
    "Some",
    "Tag",
    "Tokenize",
    "Until",
    "UntilIndent",
    # Submodules
    "alternative",
    "base",
    "conditional",
    "convert",
    "enclosed",
    "error_combinator",
    "expected",
    "expressions",
    "generador_expr",
    "item",
    "load",
    "many",
    "match",
    "negation",
    "optional",
    "peek",
    "preprocess",
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
    "until_indent",
]
