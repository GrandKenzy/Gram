"""
Gramática del Lenguaje C para Gram (`examples.CExample.grammar`).
================================================================
Define las palabras clave, reglas sintácticas y combinadores de Gram
necesarios para parsear un subconjunto expresivo del lenguaje C:
- Tipos de datos primitivos y modificadores: int, char, float, double, void, short, long, unsigned.
- Declaración e inicialización de variables escalares y punteros (*).
- Definición y prototipos de funciones con listas de parámetros.
- Sentencias de control de flujo: if / else, while, for, return, break, continue.
- Expresiones aritméticas, relacionales, lógicas, unarias y llamadas a funciones.
- Bloques de código delimitados por llaves { ... }.
"""
from __future__ import annotations

from typing import Any
from gram.core.ast.analyzer import ASTAnalyzer
from gram.core.combinators import (
    Alt,
    DECLARATION,
    Many,
    MatchKeyword,
    MatchToken,
    Opt,
    PROGRAM,
    Ref,
    RuleItem,
    Sep,
    Seq,
)
from gram.core.lexer import Token, words


def setup_c_keywords() -> None:
    """Registra las palabras clave del lenguaje C en el motor léxico de Gram."""
    c_keywords = {
        # Tipos primitivos y calificadores
        "int": "#4EC9B0",
        "char": "#4EC9B0",
        "float": "#4EC9B0",
        "double": "#4EC9B0",
        "void": "#4EC9B0",
        "short": "#4EC9B0",
        "long": "#4EC9B0",
        "unsigned": "#4EC9B0",
        "signed": "#4EC9B0",
        "const": "#569CD6",
        # Control de flujo
        "if": "#C586C0",
        "else": "#C586C0",
        "while": "#C586C0",
        "for": "#C586C0",
        "return": "#C586C0",
        "break": "#C586C0",
        "continue": "#C586C0",
        # Estructuras
        "struct": "#4EC9B0",
        "typedef": "#569CD6",
        "enum": "#4EC9B0",
    }
    for kw, color in c_keywords.items():
        if not words.keyword_exists(kw):
            words.add_keyword(kw, hex_color=color, allow_override=True)


# ============================================================================
# Reglas Sintácticas (RuleItem) de C
# ============================================================================

class C_TYPE(RuleItem):
    code = 9101
    name = "C_TYPE"
    description = "Tipo de dato nativo en C."
    colors = {0: "#4EC9B0"}
    grammar = Alt(
        Seq(MatchKeyword("const"), MatchKeyword("char")),
        Seq(MatchKeyword("const"), MatchKeyword("int")),
        Seq(MatchKeyword("const"), MatchKeyword("void")),
        MatchKeyword("int"),
        MatchKeyword("char"),
        MatchKeyword("float"),
        MatchKeyword("double"),
        MatchKeyword("void"),
        MatchKeyword("short"),
        MatchKeyword("long"),
        MatchKeyword("unsigned"),
        MatchKeyword("signed"),
    )


class C_POINTER(RuleItem):
    code = 9102
    name = "C_POINTER"
    description = "Modificador de puntero (*)."
    colors = {0: "#D4D4D4"}
    grammar = Many(MatchToken(Token.STAR))


class C_ATOM(RuleItem):
    code = 9103
    name = "C_ATOM"
    description = "Átomo o término primario de expresión en C."
    grammar = Alt(
        MatchToken(Token.NUMBER),
        MatchToken(Token.STRING),
        MatchToken(Token.IDENT),
    )


class C_CALL_ARGS(RuleItem):
    code = 9104
    name = "C_CALL_ARGS"
    description = "Argumentos de llamada a función separados por comas."
    grammar = Sep(Ref("C_EXPR"), MatchToken(Token.COMMA))


class C_CALL(RuleItem):
    code = 9105
    name = "C_CALL"
    description = "Llamada a función en C: identificador(args)."
    colors = {0: "#DCDCAA"}
    grammar = Seq(
        MatchToken(Token.IDENT),
        MatchToken(Token.LPAREN),
        Opt(Ref(C_CALL_ARGS)),
        MatchToken(Token.RPAREN),
    )


class C_PAREN_EXPR(RuleItem):
    code = 9106
    name = "C_PAREN_EXPR"
    description = "Expresión entre paréntesis: ( expr )."
    grammar = Seq(
        MatchToken(Token.LPAREN),
        Ref("C_EXPR"),
        MatchToken(Token.RPAREN),
    )


class C_PRIMARY(RuleItem):
    code = 9107
    name = "C_PRIMARY"
    description = "Término primario (llamada, paréntesis o átomo)."
    grammar = Alt(
        Ref(C_CALL),
        Ref(C_PAREN_EXPR),
        Ref(C_ATOM),
    )


class C_UNARY_OP(RuleItem):
    code = 9108
    name = "C_UNARY_OP"
    description = "Operadores unarios en C (+, -, !, *, &)."
    grammar = Alt(
        MatchToken(Token.PLUS),
        MatchToken(Token.MINUS),
        MatchToken(Token.EXCLAMATION),
        MatchToken(Token.STAR),
        MatchToken(Token.AND),
    )


class C_UNARY(RuleItem):
    code = 9109
    name = "C_UNARY"
    description = "Expresión unaria en C."
    grammar = Alt(
        Seq(Ref(C_UNARY_OP), Ref(C_PRIMARY)),
        Ref(C_PRIMARY),
    )


class C_BIN_OP(RuleItem):
    code = 9110
    name = "C_BIN_OP"
    description = "Operador binario aritmético, relacional, lógico o de asignación."
    grammar = Alt(
        # Aritméticos
        MatchToken(Token.PLUS),
        MatchToken(Token.MINUS),
        MatchToken(Token.STAR),
        MatchToken(Token.SLASH),
        MatchToken(Token.PERCENT),
        # Comparación / Relacionales
        MatchToken(Token.EQUAL),
        MatchToken(Token.NOT_EQUAL),
        MatchToken(Token.LESS_EQUAL),
        MatchToken(Token.GREATER_EQUAL),
        MatchToken(Token.LESS),
        MatchToken(Token.GREATER),
        # Lógicos y bits
        MatchToken(Token.LOGIC_AND),
        MatchToken(Token.LOGIC_OR),
        MatchToken(Token.AND),
        MatchToken(Token.OR),
        MatchToken(Token.XOR),
        # Asignación
        MatchToken(Token.ASSIGN),
    )


class C_EXPR(RuleItem):
    code = 9111
    name = "C_EXPR"
    description = "Expresión general en C con operadores encadenados."
    grammar = Seq(
        Ref(C_UNARY),
        Many(Seq(Ref(C_BIN_OP), Ref(C_UNARY))),
    )


class C_VAR_DECL(RuleItem):
    code = 9112
    name = "C_VAR_DECL"
    description = "Declaración de variable con o sin inicializador: tipo [*] id [= expr]? ;"
    colors = {0: "#4EC9B0", 1: "#9CDCFE"}
    grammar = Seq(
        Ref(C_TYPE),
        Opt(Ref(C_POINTER)),
        MatchToken(Token.IDENT),
        Opt(Seq(MatchToken(Token.ASSIGN), Ref(C_EXPR))),
        MatchToken(Token.SEMICOLON),
    )


class C_PARAM(RuleItem):
    code = 9113
    name = "C_PARAM"
    description = "Parámetro individual de función: tipo [*] id."
    grammar = Seq(
        Ref(C_TYPE),
        Opt(Ref(C_POINTER)),
        Opt(MatchToken(Token.IDENT)),
    )


class C_PARAMS(RuleItem):
    code = 9114
    name = "C_PARAMS"
    description = "Lista de parámetros de función."
    grammar = Sep(Ref(C_PARAM), MatchToken(Token.COMMA))


class C_RETURN_STMT(RuleItem):
    code = 9115
    name = "C_RETURN_STMT"
    description = "Sentencia return: return [expr]? ;"
    colors = {0: "#C586C0"}
    grammar = Seq(
        MatchKeyword("return"),
        Opt(Ref(C_EXPR)),
        MatchToken(Token.SEMICOLON),
    )


class C_EXPR_STMT(RuleItem):
    code = 9116
    name = "C_EXPR_STMT"
    description = "Sentencia de expresión terminada en punto y coma: expr ;"
    grammar = Seq(
        Ref(C_EXPR),
        MatchToken(Token.SEMICOLON),
    )


class C_BREAK_STMT(RuleItem):
    code = 9117
    name = "C_BREAK_STMT"
    description = "Sentencia break ;"
    colors = {0: "#C586C0"}
    grammar = Seq(MatchKeyword("break"), MatchToken(Token.SEMICOLON))


class C_CONTINUE_STMT(RuleItem):
    code = 9118
    name = "C_CONTINUE_STMT"
    description = "Sentencia continue ;"
    colors = {0: "#C586C0"}
    grammar = Seq(MatchKeyword("continue"), MatchToken(Token.SEMICOLON))


class C_BLOCK(RuleItem):
    code = 9119
    name = "C_BLOCK"
    description = "Bloque de código delimitado por llaves { ... }."
    grammar = Seq(
        MatchToken(Token.LBRACE),
        Many(Ref("C_STMT")),
        MatchToken(Token.RBRACE),
    )


class C_IF_STMT(RuleItem):
    code = 9120
    name = "C_IF_STMT"
    description = "Sentencia condicional: if (expr) { ... } [else { ... }]?"
    colors = {0: "#C586C0"}
    grammar = Seq(
        MatchKeyword("if"),
        MatchToken(Token.LPAREN),
        Ref(C_EXPR),
        MatchToken(Token.RPAREN),
        Alt(Ref(C_BLOCK), Ref("C_STMT")),
        Opt(Seq(MatchKeyword("else"), Alt(Ref(C_BLOCK), Ref("C_STMT")))),
    )


class C_WHILE_STMT(RuleItem):
    code = 9121
    name = "C_WHILE_STMT"
    description = "Bucle while: while (expr) { ... }"
    colors = {0: "#C586C0"}
    grammar = Seq(
        MatchKeyword("while"),
        MatchToken(Token.LPAREN),
        Ref(C_EXPR),
        MatchToken(Token.RPAREN),
        Alt(Ref(C_BLOCK), Ref("C_STMT")),
    )


class C_FOR_INIT(RuleItem):
    code = 9122
    name = "C_FOR_INIT"
    description = "Cláusula de inicialización de bucle for."
    grammar = Alt(
        Ref(C_VAR_DECL),
        Ref(C_EXPR_STMT),
        MatchToken(Token.SEMICOLON),
    )


class C_FOR_STMT(RuleItem):
    code = 9123
    name = "C_FOR_STMT"
    description = "Bucle for: for (init; cond; step) { ... }"
    colors = {0: "#C586C0"}
    grammar = Seq(
        MatchKeyword("for"),
        MatchToken(Token.LPAREN),
        Ref(C_FOR_INIT),
        Opt(Ref(C_EXPR)),
        MatchToken(Token.SEMICOLON),
        Opt(Ref(C_EXPR)),
        MatchToken(Token.RPAREN),
        Alt(Ref(C_BLOCK), Ref("C_STMT")),
    )


class C_STMT(RuleItem):
    code = 9124
    name = "C_STMT"
    description = "Sentencia general en C (bloque, return, if, while, for, decl o expr)."
    grammar = Alt(
        Ref(C_BLOCK),
        Ref(C_RETURN_STMT),
        Ref(C_IF_STMT),
        Ref(C_WHILE_STMT),
        Ref(C_FOR_STMT),
        Ref(C_BREAK_STMT),
        Ref(C_CONTINUE_STMT),
        Ref(C_VAR_DECL),
        Ref(C_EXPR_STMT),
        MatchToken(Token.SEMICOLON),
    )


class C_FUNC_PARAMS(RuleItem):
    code = 9125
    name = "C_FUNC_PARAMS"
    description = "Sección de parámetros de cabecera de función: ( [params]? )"
    grammar = Seq(
        MatchToken(Token.LPAREN),
        Opt(Alt(MatchKeyword("void"), Ref(C_PARAMS))),
        MatchToken(Token.RPAREN),
    )


class C_FUNC_DEF(RuleItem):
    code = 9126
    name = "C_FUNC_DEF"
    description = "Definición completa de función con cuerpo: tipo [*] nombre(params) { ... }"
    colors = {0: "#4EC9B0", 1: "#DCDCAA"}
    grammar = Seq(
        Ref(C_TYPE),
        Opt(Ref(C_POINTER)),
        MatchToken(Token.IDENT),
        Ref(C_FUNC_PARAMS),
        Ref(C_BLOCK),
    )


class C_FUNC_DECL(RuleItem):
    code = 9127
    name = "C_FUNC_DECL"
    description = "Prototipo o declaración de función: tipo [*] nombre(params) ;"
    grammar = Seq(
        Ref(C_TYPE),
        Opt(Ref(C_POINTER)),
        MatchToken(Token.IDENT),
        Ref(C_FUNC_PARAMS),
        MatchToken(Token.SEMICOLON),
    )


# ============================================================================
# Diccionario Formal de Gramática para Gram Framework
# ============================================================================

c_grammar: dict[Any, Any] = {
    PROGRAM: Many(Ref(DECLARATION)),
    DECLARATION: Alt(
        Ref(C_FUNC_DEF),
        Ref(C_FUNC_DECL),
        Ref(C_VAR_DECL),
        Ref(C_STMT),
    ),
    C_TYPE: C_TYPE.grammar,
    C_POINTER: C_POINTER.grammar,
    C_ATOM: C_ATOM.grammar,
    C_CALL_ARGS: C_CALL_ARGS.grammar,
    C_CALL: C_CALL.grammar,
    C_PAREN_EXPR: C_PAREN_EXPR.grammar,
    C_PRIMARY: C_PRIMARY.grammar,
    C_UNARY_OP: C_UNARY_OP.grammar,
    C_UNARY: C_UNARY.grammar,
    C_BIN_OP: C_BIN_OP.grammar,
    C_EXPR: C_EXPR.grammar,
    C_VAR_DECL: C_VAR_DECL.grammar,
    C_PARAM: C_PARAM.grammar,
    C_PARAMS: C_PARAMS.grammar,
    C_RETURN_STMT: C_RETURN_STMT.grammar,
    C_EXPR_STMT: C_EXPR_STMT.grammar,
    C_BREAK_STMT: C_BREAK_STMT.grammar,
    C_CONTINUE_STMT: C_CONTINUE_STMT.grammar,
    C_BLOCK: C_BLOCK.grammar,
    C_IF_STMT: C_IF_STMT.grammar,
    C_WHILE_STMT: C_WHILE_STMT.grammar,
    C_FOR_INIT: C_FOR_INIT.grammar,
    C_FOR_STMT: C_FOR_STMT.grammar,
    C_STMT: C_STMT.grammar,
    C_FUNC_PARAMS: C_FUNC_PARAMS.grammar,
    C_FUNC_DEF: C_FUNC_DEF.grammar,
    C_FUNC_DECL: C_FUNC_DECL.grammar,
}


def get_c_grammar() -> dict[Any, Any]:
    """Retorna el diccionario de reglas sintácticas del lenguaje C."""
    setup_c_keywords()
    return c_grammar
