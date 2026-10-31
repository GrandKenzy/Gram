"""
Gram Framework Lexical Analyzer Subsystem (`gram.core.lexer`).
==============================================================
Exports the lexical analysis engine (`Lexer`, `LexerState`), token types
(`Token`, `TokenType`, `CustomToken`, `MAP_SYMBOLS`), token navigation
wrapper (`TokenStream`), and keyword/group management utilities.
"""
from __future__ import annotations

from gram.core.lexer import control, core, flags, items, multiline, tokens, visitors, words
from gram.core.lexer.control import LexerState
from gram.core.lexer.core import Lexer, check_state
from gram.core.lexer.items import TokenStream
from gram.core.lexer.flags import CHAR, NONE, SIMPLE_QUOTE, TokenFlags
from gram.core.lexer.multiline import (
    MULTLINE,
    add_multline,
    list_multline,
    remove_multline,
)
from gram.core.lexer.tokens import (
    MAP_SYMBOLS,
    CustomToken,
    Token,
    TokenType,
    get_sorted_symbols,
    get_tokens,
)
from gram.core.lexer.words import (
    Keyword,
    WordGroup,
    WordGroupManager,
    add_group,
    add_keyword,
    all_group_names,
    all_groups,
    all_keyword_names,
    all_keywords,
    clear_all,
    count_keywords,
    exists_in_group,
    get_group,
    get_keyword,
    group_exists,
    groups,
    is_empty,
    keyword_exists,
    remove_group,
    remove_keyword,
)


def Version() -> str:
    """Return the version string of the Gram lexer subsystem."""
    return "3.0.0"


__all__ = [
    "MAP_SYMBOLS",
    "MULTLINE",
    "CHAR",
    "NONE",
    "SIMPLE_QUOTE",
    "TokenFlags",
    # Tokens & Symbols
    "CustomToken",
    # Keywords & WordGroups
    "Keyword",
    # Core Lexer Engine & State
    "Lexer",
    "LexerState",
    "Token",
    "TokenStream",
    "TokenType",
    "Version",
    "WordGroup",
    "WordGroupManager",
    "add_group",
    "add_keyword",
    "all_group_names",
    "all_groups",
    "all_keyword_names",
    "all_keywords",
    "check_state",
    "clear_all",
    # Submodules
    "control",
    "core",
    "count_keywords",
    "exists_in_group",
    "get_group",
    "get_keyword",
    "get_sorted_symbols",
    "get_tokens",
    "group_exists",
    "groups",
    "is_empty",
    "items",
    "flags",
    "multiline",
    "add_multline",
    "list_multline",
    "remove_multline",
    "keyword_exists",
    "remove_group",
    "remove_keyword",
    "tokens",
    "visitors",
    "words",
]
