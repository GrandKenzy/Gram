"""
GRAM_ESSENCIAL_PACK
===================
Plugin estándar de abstracción y desarrollo de extensiones para Gram.
Facilita la creación de nuevos plugins ocultando la complejidad del motor
subyacente y proveyendo combinadores esenciales:
- SimpleCombinator: Creación intuitiva de combinadores basados en predicados sobre tokens.
- If: Lógica condicional, bifurcación ok/fail y lookahead seguro.
- ErrorCombinator: Captura estructurada de errores.
- Req, Skip, Peek, Not, Until: Primitivas avanzadas de parsing.
"""
from __future__ import annotations

# Tipos y definiciones
from . import types
from .types import (
    ASTAType,
    ASTAnalyzer,
    ASTNode,
    ASTProgram,
    Combinator,
    GrammarType,
    Lexer,
    Parser,
    PluginLoadFn,
    PluginProcessFn,
    RuleItem,
    RuleMeta,
    RuleType,
    Token,
    TokenList,
    TokenType,
    Watcher,
)

# Combinadores nativos de Gram re-exportados para desarrollo fluido
from gram.core.combinators import (
    Alt,
    Bracketed,
    Enclosed,
    Item,
    Literal,
    Many,
    MatchGroup,
    MatchKeyword,
    MatchSeqSymbol,
    MatchToken,
    Opt,
    Ref,
    Separator,
    Seq,
    Some,
    Tokenize,
)

# Reglas nativas
from gram.core.combinators.defaults import (
    BLOCK,
    CUSTOM_RULES,
    DECLARATION,
    DEFAULT_RULES,
    DOCSTRING,
    ENDLINE,
    HEXADECIMAL,
    INDENT_BLOCK,
    PROGRAM,
    PROTECTED_MAX_ID,
    PROTECTED_MIN_ID,
    RECOMMENDED_MAX_PLUGIN_ID,
    RECOMMENDED_MIN_PLUGIN_ID,
    RULE_PRIORITIES,
    RULES_BY_ID,
    RULES_BY_NAME,
    add_rule,
    create_rule,
    get_rule_by_id,
    get_rule_by_name,
    is_protected_id,
)

# Combinadores del pack
from .advanced_combinators import (
    ErrorCombinator,
    If,
    Not,
    Peek,
    Req,
    Skip,
    Until,
)
from .combinator_base import SimpleCombinator
from .combinators import get_combinators
from .api import (
    HARDCODED_MODS,
    custom_mod,
    get_custom_mods,
    get_hardcoded_mods,
    is_custom_mod,
    is_hardcoded_mod,
    register_combinator,
    register_custom_mod,
    register_error,
    register_group,
    register_keyword,
    register_rule,
)

# Plugin principal
from .main import (
    GramEssentialPackPlugin,
    load,
    process,
)

__all__ = [
    # Plugin
    "GramEssentialPackPlugin",
    "load",
    "process",
    "get_combinators",
    # Tipos
    "types",
    "ASTAType",
    "ASTAnalyzer",
    "GrammarType",
    "Token",
    "TokenType",
    "TokenList",
    "PluginLoadFn",
    "PluginProcessFn",
    "Combinator",
    "RuleItem",
    "RuleMeta",
    "RuleType",
    "Lexer",
    "ASTNode",
    "ASTProgram",
    "Parser",
    "Watcher",
    # Combinadores de Gram
    "Seq",
    "Alt",
    "Bracketed",
    "Enclosed",
    "Opt",
    "Many",
    "Some",
    "Ref",
    "MatchKeyword",
    "MatchToken",
    "MatchSeqSymbol",
    "MatchGroup",
    "Separator",
    "Tokenize",
    "Item",
    "Literal",
    # Reglas nativas
    "PROGRAM",
    "DECLARATION",
    "ENDLINE",
    "BLOCK",
    "INDENT_BLOCK",
    "DOCSTRING",
    "HEXADECIMAL",
    "DEFAULT_RULES",
    "CUSTOM_RULES",
    "RULES_BY_ID",
    "RULES_BY_NAME",
    "RULE_PRIORITIES",
    "PROTECTED_MIN_ID",
    "PROTECTED_MAX_ID",
    "RECOMMENDED_MIN_PLUGIN_ID",
    "RECOMMENDED_MAX_PLUGIN_ID",
    "is_protected_id",
    "get_rule_by_id",
    "get_rule_by_name",
    "add_rule",
    "create_rule",
    # Combinadores avanzados del pack
    "SimpleCombinator",
    "If",
    "ErrorCombinator",
    "Req",
    "Skip",
    "Peek",
    "Not",
    "Until",
    # API de registro
    "register_keyword",
    "register_rule",
    "register_group",
    "register_error",
    "register_combinator",
    "register_custom_mod",
    "custom_mod",
    "is_custom_mod",
    "is_hardcoded_mod",
    "get_custom_mods",
    "get_hardcoded_mods",
    "HARDCODED_MODS",
]
