"""
Token Matching Combinators Subpackage (`gram.core.combinators.match`).
======================================================================
Provides atomic combinators specialized in validating and filtering tokens:
- `MatchToken`: Matches by token type (`Token` enum, `CustomToken`, or name).
- `MatchKeyword`: Matches a specific registered keyword in the lexer.
- `MatchGroup`: Matches membership within a semantic `WordGroup`.
- `MatchSymbol` / `MatchSeqSymbol`: Matches token text via regex or symbol list.
- `generador_expr`: Helper builder for regular expression patterns.
"""
from __future__ import annotations

from gram.core.combinators.match.match_group import MatchGroup
from gram.core.combinators.match.match_keyword import MatchKeyword
from gram.core.combinators.match.match_symbol import (
    MatchSeqSymbol,
    MatchSymbol,
    generador_expr,
)
from gram.core.combinators.match.match_token import MatchToken

__all__ = [
    "MatchGroup",
    "MatchKeyword",
    "MatchSeqSymbol",
    "MatchSymbol",
    "MatchToken",
    "generador_expr",
]