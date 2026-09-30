"""
Módulo de tipos y definiciones fundamentales para plugins en Gram.
==================================================================
Centraliza el acceso a tipos estructurales, clases base y reglas nativas del motor,
evitando la navegación profunda a través de módulos internos del analizador.
"""
from __future__ import annotations

from typing import Any, Callable

# Clases base de combinadores y reglas
from gram.core.combinators.base import (
    Combinator,
    RuleItem,
    RuleMeta,
    RuleType,
)

# Reglas nativas predeterminadas de Gram (defaults.py)
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

# Tipos de tokens y nodos del AST
from gram.core.lexer import Lexer
from gram.core.lexer.tokens import Token, TokenType
from gram.core.ast.analyzer import ASTAnalyzer
from gram.core.ast.nodes import ASTNode, ASTProgram
from gram.core.parser.core import Parser
from gram.core.watcher import Watcher

# Definiciones de tipos para desarrollo de plugins
ASTAType = ASTAnalyzer
GrammarType = dict[RuleType, Combinator]
TokenList = list[TokenType]
PluginLoadFn = Callable[[], bool]
PluginProcessFn = Callable[..., Any]

__all__ = [
    # Tipos estructurales y alias
    "ASTAType",
    "ASTAnalyzer",
    "GrammarType",
    "TokenList",
    "PluginLoadFn",
    "PluginProcessFn",
    # Clases base
    "Combinator",
    "RuleItem",
    "RuleMeta",
    "RuleType",
    # Reglas nativas
    "PROGRAM",
    "DECLARATION",
    "ENDLINE",
    "BLOCK",
    "INDENT_BLOCK",
    "DOCSTRING",
    "HEXADECIMAL",
    # Catálogos de reglas
    "DEFAULT_RULES",
    "CUSTOM_RULES",
    "RULES_BY_ID",
    "RULES_BY_NAME",
    "RULE_PRIORITIES",
    # Constantes de protección
    "PROTECTED_MIN_ID",
    "PROTECTED_MAX_ID",
    "RECOMMENDED_MIN_PLUGIN_ID",
    "RECOMMENDED_MAX_PLUGIN_ID",
    # Funciones de consulta y registro
    "is_protected_id",
    "get_rule_by_id",
    "get_rule_by_name",
    "add_rule",
    "create_rule",
    # Lexer, Parser y AST
    "Lexer",
    "Token",
    "TokenType",
    "ASTNode",
    "ASTProgram",
    "Parser",
    "Watcher",
]
