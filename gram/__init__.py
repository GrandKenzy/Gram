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
- DSL & SJSON: parse_dsl, parse_glang_file, LanguageCompiler, SJSONCompiler
"""
from __future__ import annotations

# Submódulos del sistema
from gram import cachesystem, cli, config, core, environment, errors, glang, native, plugins, sjson, utilities, vsix

# Subpaquetes principales de core
from gram.core import ast, combinators, lexer, parser

# Motor Léxico
from gram.core.lexer import (
    CustomToken,
    Keyword,
    Lexer,
    Token,
    TokenType,
    words,
)

# Motor de Parsing
from gram.core.parser import (
    Checkpoint,
    ParseControl,
    Parser,
)

# Árbol de Sintaxis Abstracta (AST) y Telemetría
from gram.core.ast import (
    ASTAnalyzer,
    ASTNode,
    ASTProgram,
    generate_file_tree,
)
from gram.core.watcher import Watcher

# Combinadores Sintácticos y Reglas
from gram.core.combinators import (
    BLOCK,
    DECLARATION,
    DOCSTRING,
    ENDLINE,
    HEXADECIMAL,
    INDENT_BLOCK,
    PASS,
    PROGRAM,
    AbortFlowSignal,
    Alt,
    Alternative,
    AnyGrammar,
    BacktrackSignal,
    Bracketed,
    BreakFlowSignal,
    Combinator,
    ControlFlowSignal,
    CutFlowSignal,
    Enclosed,
    Item,
    Literal,
    Many,
    MatchGroup,
    MatchKeyword,
    MatchSeqSymbol,
    MatchSymbol,
    MatchToken,
    Opt,
    Optional,
    Query,
    Ref,
    Reference,
    RuleItem,
    RuleMeta,
    RuleType,
    Sep,
    Separator,
    Seq,
    Sequence,
    SkipFlowSignal,
    Some,
    Tokenize,
    create_rule,
    query,
)

# Compilador y Parser de GLANG
from gram.glang import (
    LanguageCompiler,
    parse_dsl,
    parse_file,
    parse_glang_file,
)

# Compilador SJSON
from gram.sjson import (
    SJSONCompiler,
)

# Orquestación de Alto Nivel
from gram.core.process import (
    process,
    get_stack
)

__version__ = "1.0.0"
__version_info__ = (1, 0, 0)


def version() -> str:
    """Retorna la versión actual del Framework Gram."""
    return __version__


__all__ = [
    # Metadatos
    "__version__",
    "__version_info__",
    "version",
    # Módulos y submódulos
    "cachesystem",
    "cli",
    "config",
    "core",
    "environment",
    "errors",
    "glang",
    "native",
    "plugins",
    "sjson",
    "utilities",
    "vsix",
    "ast",
    "combinators",
    "lexer",
    "parser",
    # Léxico
    "Lexer",
    "Token",
    "TokenType",
    "CustomToken",
    "words",
    "Keyword",
    # Parsing
    "Parser",
    "Checkpoint",
    "ParseControl",
    # AST
    "ASTAnalyzer",
    "ASTNode",
    "ASTProgram",
    "generate_file_tree",
    "Watcher",
    # Combinadores y Reglas
    "RuleItem",
    "RuleMeta",
    "RuleType",
    "Combinator",
    "Seq",
    "Sequence",
    "Alt",
    "Alternative",
    "Many",
    "Some",
    "Opt",
    "Optional",
    "Sep",
    "Separator",
    "Enclosed",
    "Bracketed",
    "Item",
    "Literal",
    "MatchToken",
    "MatchKeyword",
    "MatchSymbol",
    "MatchGroup",
    "MatchSeqSymbol",
    "Ref",
    "Reference",
    "Tokenize",
    "Query",
    "query",
    "AnyGrammar",
    # Gramáticas por defecto
    "PROGRAM",
    "DECLARATION",
    "BLOCK",
    "INDENT_BLOCK",
    "PASS",
    "ENDLINE",
    "HEXADECIMAL",
    "DOCSTRING",
    "create_rule",
    # Señales de flujo
    "ControlFlowSignal",
    "BacktrackSignal",
    "CutFlowSignal",
    "SkipFlowSignal",
    "BreakFlowSignal",
    "AbortFlowSignal",
    # GLANG DSL
    "LanguageCompiler",
    "parse_dsl",
    "parse_file",
    "parse_glang_file",
    # SJSON
    "SJSONCompiler",
    # Orquestación de Alto Nivel
    "process",
]
