"""
Framework Gram — Framework de Meta-Interpretación y Diseño de DSLs.
====================================================================
Versión limpia, modular y fuertemente tipada.

Exporta los componentes esenciales del framework para acceso directo:
- Léxico: Lexer, Token, TokenType, CustomToken, words, Keyword
- Parser y AST: Parser, Checkpoint, ParseControl, ASTAnalyzer, ASTProgram, ASTNode, Watcher
- Combinadores: Seq, Alt, Many, Some, Opt, Sep, Enclosed, MatchToken, MatchKeyword,
                MatchSymbol, MatchGroup, Ref, RuleItem, Combinator, Tokenize, Query
- Gramáticas por defecto: PROGRAM, DECLARATION, BLOCK, INDENT_BLOCK, PASS, ENDLINE
- DSL: parse_dsl, parse_glang_file, LanguageCompiler
"""
from __future__ import annotations

# Submódulos del sistema
from gram import config, errors, utilities, vsix
from gram.core import ast, combinators, lexer, parser, rules
from gram.core.process import (
    process,
)

__version__ = "2.0.0b0"
__version_info__ = (2, 0, 0, "beta")


def version() -> str:
    """Retorna la versión actual del Framework Gram."""
    return __version__


__all__ = [
    # Metadatos
    "__version__",
    "__version_info__",
    "ast",
    "combinators",
    "config",
    "errors",
    "lexer",
    "parser",
    "process",
    "rules",
    "utilities",
    "version",
    "vsix",
]