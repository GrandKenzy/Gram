"""
Abstract Syntax Tree Subpackage (`gram.core.ast`).
==================================================
EN:
    Provides core components for construction, semantic inspection, hierarchical
    traversal, and formatted serialization of the Gram Abstract Syntax Tree (AST).

ES:
    Proporciona los componentes para la construcción, inspección semántica,
    recorrido jerárquico y serialización formateada del Árbol de Sintaxis Abstracta (AST) de Gram.
"""
from __future__ import annotations

from gram.core.ast.analyzer import ASTAnalyzer
from gram.core.ast.nodes import (
    ASTNode,
    ASTProgram,
    generate_file_tree,
)

__all__ = [
    "ASTAnalyzer",
    "ASTNode",
    "ASTProgram",
    "generate_file_tree",
]
