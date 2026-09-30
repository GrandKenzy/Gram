"""
CExample: Motor Mínimo de Parsing de Lenguaje C con Gram Framework.
===================================================================
Demuestra cómo utilizar las primitivas, combinadores y el ASTAnalyzer
de Gram para construir un parser completo y expresivo para un subconjunto
del lenguaje C (tipos, variables, punteros, funciones, sentencias if/while/for,
expresiones aritmético-lógicas y llamadas).
"""
from __future__ import annotations

from .grammar import (
    c_grammar,
    get_c_grammar,
    setup_c_keywords,
    C_TYPE,
    C_POINTER,
    C_ATOM,
    C_CALL,
    C_EXPR,
    C_VAR_DECL,
    C_PARAM,
    C_PARAMS,
    C_RETURN_STMT,
    C_EXPR_STMT,
    C_BREAK_STMT,
    C_CONTINUE_STMT,
    C_BLOCK,
    C_IF_STMT,
    C_WHILE_STMT,
    C_FOR_STMT,
    C_FUNC_DEF,
    C_FUNC_DECL,
)
from .c_parser import (
    CParser,
    parse_c,
    parse_c_file,
)

__all__ = [
    "CParser",
    "parse_c",
    "parse_c_file",
    "get_c_grammar",
    "setup_c_keywords",
    "c_grammar",
    "C_TYPE",
    "C_POINTER",
    "C_ATOM",
    "C_CALL",
    "C_EXPR",
    "C_VAR_DECL",
    "C_PARAM",
    "C_PARAMS",
    "C_RETURN_STMT",
    "C_EXPR_STMT",
    "C_BREAK_STMT",
    "C_CONTINUE_STMT",
    "C_BLOCK",
    "C_IF_STMT",
    "C_WHILE_STMT",
    "C_FOR_STMT",
    "C_FUNC_DEF",
    "C_FUNC_DECL",
]
