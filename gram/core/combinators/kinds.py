"""
Formal Semantic Kinds and Verification for Syntactic Combinators
(`gram.core.combinators.kinds`).
================================================================
Defines `CombinatorKind`, establishing the closed semantic signatures that Gram
recognizes for declarative grammar analysis and Ahead-Of-Time (AOT) C compilation,
while rejecting unrecognized or arbitrary black-box combinators.
"""
from __future__ import annotations

from enum import Enum
from typing import Any


class CombinatorKind(Enum):
    """
    Formal algebraic category for a syntactic combinator.

    Combinators signed with a `CombinatorKind` expose precise, declarative
    semantics to the predictability analyzer and the AOT C compiler.
    """

    # Terminals
    TERMINAL_TOKEN = "terminal_token"
    TERMINAL_KEYWORD = "terminal_keyword"
    TERMINAL_GROUP = "terminal_group"
    TERMINAL_SYMBOL = "terminal_symbol"
    TERMINAL_LITERAL = "terminal_literal"

    # Structural
    SEQUENCE = "sequence"
    ALTERNATIVE = "alternative"
    OPTIONAL = "optional"
    MANY = "many"
    SOME = "some"
    REFERENCE = "reference"
    ENCLOSED = "enclosed"
    ITEM = "item"

    # Lookahead & syntactic predicates
    LOOKAHEAD_POS = "lookahead_pos"
    LOOKAHEAD_NEG = "lookahead_neg"
    SAME_LINE = "same_line"

    # Expressions (Pratt precedence climbing)
    EXPR_DUAL = "expr_dual"
    EXPR_ARITHMETIC = "expr_arithmetic"
    EXPR_CONDITIONAL = "expr_conditional"

    # Modifiers & specialized handlers
    CONVERT = "convert"
    SEPARATOR = "separator"
    UNTIL = "until"
    UNTIL_INDENT = "until_indent"
    CAPTURE_RAW = "capture_raw"
    IF = "if"
    ERROR = "error"
    PREPROCESS = "preprocess"
    EXPECTED = "expected"
    SKIP = "skip"
    TAG = "tag"
    LOAD = "load"
    SAVE = "save"
    REQ = "req"
    TOKENIZE = "tokenize"


COMPILABLE_COMBINATOR_KINDS: frozenset[CombinatorKind] = frozenset(
    {
        CombinatorKind.TERMINAL_TOKEN,
        CombinatorKind.TERMINAL_KEYWORD,
        CombinatorKind.TERMINAL_GROUP,
        CombinatorKind.TERMINAL_SYMBOL,
        CombinatorKind.TERMINAL_LITERAL,
        CombinatorKind.SEQUENCE,
        CombinatorKind.ALTERNATIVE,
        CombinatorKind.OPTIONAL,
        CombinatorKind.MANY,
        CombinatorKind.SOME,
        CombinatorKind.REFERENCE,
        CombinatorKind.ENCLOSED,
        CombinatorKind.ITEM,
        CombinatorKind.LOOKAHEAD_POS,
        CombinatorKind.LOOKAHEAD_NEG,
        CombinatorKind.SAME_LINE,
        CombinatorKind.EXPR_DUAL,
        CombinatorKind.EXPR_ARITHMETIC,
        CombinatorKind.EXPR_CONDITIONAL,
        CombinatorKind.SEPARATOR,
        CombinatorKind.UNTIL,
        CombinatorKind.CAPTURE_RAW,
    }
)


def get_combinator_kind(combinator: Any) -> CombinatorKind | None:
    """Return the formal semantic kind of `combinator`, or None if external/unrecognized."""
    return getattr(combinator, "combinator_kind", None)


def is_semantic_combinator(combinator: Any) -> bool:
    """Return True if `combinator` possesses a recognized formal semantic signature."""
    return isinstance(get_combinator_kind(combinator), CombinatorKind)


def is_compilable_combinator(combinator: Any) -> bool:
    """Return True if `combinator` can be compiled Ahead-Of-Time into native C code."""
    kind = get_combinator_kind(combinator)
    return kind in COMPILABLE_COMBINATOR_KINDS


__all__ = [
    "COMPILABLE_COMBINATOR_KINDS",
    "CombinatorKind",
    "get_combinator_kind",
    "is_compilable_combinator",
    "is_semantic_combinator",
]
