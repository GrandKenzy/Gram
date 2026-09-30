"""
Core Subpackage of the Gram Framework (`gram.core`).
===================================================
EN:
    Contains the central compilation engine of the framework:
      - lexer: Lexical analyzer, stream tokenization, and AST visitors.
      - combinators: Modular syntactic combinators and native grammar rules.
      - parser: Syntactic parser with backtracking, virtual cursor, and transactions.
      - ast: Abstract Syntax Tree, semantic analyzer, and tree visualization.
      - watcher: Real-time execution monitor, combinator stack tracker, and file watcher.

ES:
    Contiene el motor central de compilación del framework:
      - lexer: Analizador léxico, tokenización de flujo y visitantes.
      - combinators: Combinadores sintácticos modulares y reglas gramaticales nativas.
      - parser: Analizador sintáctico con backtracking, cursor virtual y transacciones.
      - ast: Árbol de sintaxis abstracta, analizador semántico y visualización.
      - watcher: Monitor de ejecución en tiempo real, pila de combinadores y vigilante de archivos.
"""
from __future__ import annotations

from gram.core import ast, combinators, lexer, parser
from gram.core.parser import Checkpoint, ParseControl, Parser
from gram.core.watcher import FileWatcher, PluginWatcher, Watcher

__all__ = [
    "Checkpoint",
    "FileWatcher",
    "ParseControl",
    "Parser",
    "PluginWatcher",
    "Watcher",
    "ast",
    "combinators",
    "lexer",
    "parser",
]
