"""
Definición de reglas gramaticales de expresiones para Gram Framework.
======================================================================
Expone las reglas sintácticas y el diccionario de gramática para el plugin expressions.
Utiliza ChainL y ChainR para asociatividad izquierda y derecha modular.
"""
from __future__ import annotations

from typing import Any
from gram.core.combinators import (
    Alt,
    DECLARATION,
    Many,
    MatchToken,
    PROGRAM,
    Ref,
    RuleItem,
    Seq,
)
from gram.core.lexer.tokens import Token
from gram.plugins.source.expressions.combinators import (
    ArithmeticExpr,
    ChainL,
    ChainR,
    ConditionalExpr,
    ExpressionBuilder,
    IsDigit,
    MathBinaryOp,
    MathGroup,
    MathUnaryOp,
)


# ============================================================================
# Reglas Gramaticales (RuleItem)
# ============================================================================

class CONDITIONAL_EXPR(RuleItem):
    code = 7050
    name = "CONDITIONAL_EXPR"
    description = "Expresión condicional con operadores relacionales (==, !=, <, <=, >, >=), lógicos (&&, ||, !) y booleanos."
    docs = "docs/conditional_expr.md"
    grammar = ConditionalExpr()
    colors = {0: "#4EC9B0"}
    suggestions = {0: [("cond", "Expresión condicional (ej. a > 10 && b == 0)")]}
    suggestions_autocomplete = True


class COMP_OP(RuleItem):
    code = 7051
    name = "COMP_OP"
    description = "Operador relacional de comparación: ==, !=, <, <=, >, >="
    grammar = Alt(
        MatchToken(Token.EQUAL),
        MatchToken(Token.NOT_EQUAL),
        MatchToken(Token.LESS_EQUAL),
        MatchToken(Token.GREATER_EQUAL),
        MatchToken(Token.LESS),
        MatchToken(Token.GREATER),
    )
    colors = {0: "#D4D4D4"}


class LOGIC_OP(RuleItem):
    code = 7052
    name = "LOGIC_OP"
    description = "Operador lógico: &&, ||"
    grammar = Alt(
        MatchToken(Token.LOGIC_AND),
        MatchToken(Token.AND_LOGIC),
        MatchToken(Token.LOGIC_OR),
        MatchToken(Token.OR_LOGIC),
    )
    colors = {0: "#D4D4D4"}

class ARITHMETIC_EXPR(RuleItem):
    code = 7001
    name = "ARITHMETIC_EXPR"
    description = "Expresión aritmética completa con soporte para +, -, *, /, //, %, **, unarios y paréntesis anidados."
    docs = "docs/arithmetic_expr.md"
    grammar = ArithmeticExpr()
    colors = {0: "#4EC9B0"}
    suggestions = {0: [("expr", "Expresión aritmética (ej. 2 + 3 * 4)")]}
    suggestions_autocomplete = True


class MATH_SUM(RuleItem):
    code = 7002
    name = "MATH_SUM"
    description = "Operación de adición asociativa por la izquierda: a + b + c -> ((a + b) + c)"
    grammar = ChainL(MatchToken(Token.NUMBER), MatchToken(Token.PLUS))
    colors = {0: "#569CD6"}


class MATH_SUB(RuleItem):
    code = 7003
    name = "MATH_SUB"
    description = "Operación de sustracción asociativa por la izquierda: a - b - c -> ((a - b) - c)"
    grammar = ChainL(MatchToken(Token.NUMBER), MatchToken(Token.MINUS))
    colors = {0: "#569CD6"}


class MATH_MULT(RuleItem):
    code = 7004
    name = "MATH_MULT"
    description = "Operación de multiplicación asociativa por la izquierda: a * b * c -> ((a * b) * c)"
    grammar = ChainL(MatchToken(Token.NUMBER), MatchToken(Token.STAR))
    colors = {0: "#569CD6"}


class MATH_DIV(RuleItem):
    code = 7005
    name = "MATH_DIV"
    description = "Operación de división asociativa por la izquierda: a / b / c -> ((a / b) / c)"
    grammar = ChainL(MatchToken(Token.NUMBER), MatchToken(Token.SLASH))
    colors = {0: "#569CD6"}


class MATH_FLOOR_DIV(RuleItem):
    code = 7006
    name = "MATH_FLOOR_DIV"
    description = "Operación de división entera: a // b // c"
    grammar = ChainL(MatchToken(Token.NUMBER), MatchToken(Token.FLOOR_DIV))
    colors = {0: "#569CD6"}


class MATH_MOD(RuleItem):
    code = 7007
    name = "MATH_MOD"
    description = "Operación de residuo/módulo: a % b"
    grammar = ChainL(MatchToken(Token.NUMBER), MatchToken(Token.PERCENT))
    colors = {0: "#569CD6"}


class MATH_POW(RuleItem):
    code = 7008
    name = "MATH_POW"
    description = "Operación de potenciación asociativa por la derecha: a ** b ** c -> (a ** (b ** c))"
    grammar = ChainR(MatchToken(Token.NUMBER), MatchToken(Token.POW))
    colors = {0: "#569CD6"}


class MATH_UNARY(RuleItem):
    code = 7009
    name = "MATH_UNARY"
    description = "Operación aritmética unaria: (+ o -) <número>"
    grammar = Seq(
        Alt(MatchToken(Token.PLUS), MatchToken(Token.MINUS)),
        MatchToken(Token.NUMBER),
    )
    colors = {1: "#569CD6"}


class MATH_PAREN(RuleItem):
    code = 7010
    name = "MATH_PAREN"
    description = "Expresión aritmética agrupada en paréntesis: ( <expr> )"
    grammar = Seq(
        MatchToken(Token.LPAREN),
        ArithmeticExpr(),
        MatchToken(Token.RPAREN),
    )


class IS_DIGIT(RuleItem):
    code = 7011
    name = "IS_DIGIT"
    description = "Regla de validación de dígito numérico."
    grammar = Seq(IsDigit())


# ============================================================================
# Diccionario de Gramática para Gram Framework
# ============================================================================

grammar: dict[Any, Any] = {
    PROGRAM: Many(Ref(DECLARATION)),
    DECLARATION: Alt(
        Ref(ARITHMETIC_EXPR),
        Ref(CONDITIONAL_EXPR),
        Ref(MATH_SUM),
        Ref(MATH_SUB),
        Ref(MATH_MULT),
        Ref(MATH_DIV),
        Ref(MATH_FLOOR_DIV),
        Ref(MATH_MOD),
        Ref(MATH_POW),
        Ref(MATH_UNARY),
        Ref(MATH_PAREN),
        Ref(IS_DIGIT),
    ),
    ARITHMETIC_EXPR: ARITHMETIC_EXPR.grammar,
    CONDITIONAL_EXPR: CONDITIONAL_EXPR.grammar,
    COMP_OP: COMP_OP.grammar,
    LOGIC_OP: LOGIC_OP.grammar,
    MATH_SUM: MATH_SUM.grammar,
    MATH_SUB: MATH_SUB.grammar,
    MATH_MULT: MATH_MULT.grammar,
    MATH_DIV: MATH_DIV.grammar,
    MATH_FLOOR_DIV: MATH_FLOOR_DIV.grammar,
    MATH_MOD: MATH_MOD.grammar,
    MATH_POW: MATH_POW.grammar,
    MATH_UNARY: MATH_UNARY.grammar,
    MATH_PAREN: MATH_PAREN.grammar,
    IS_DIGIT: IS_DIGIT.grammar,
}


def get_rules() -> list[type[RuleItem]]:
    """Retorna las clases RuleItem expuestas por el plugin expressions."""
    return [
        ARITHMETIC_EXPR,
        CONDITIONAL_EXPR,
        COMP_OP,
        LOGIC_OP,
        MATH_SUM,
        MATH_SUB,
        MATH_MULT,
        MATH_DIV,
        MATH_FLOOR_DIV,
        MATH_MOD,
        MATH_POW,
        MATH_UNARY,
        MATH_PAREN,
        IS_DIGIT,
    ]


def get_grammar() -> dict[Any, Any]:
    """Retorna la gramática física expuesta por el plugin expressions."""
    return grammar


__all__ = [
    "ARITHMETIC_EXPR",
    "CONDITIONAL_EXPR",
    "COMP_OP",
    "LOGIC_OP",
    "MATH_SUM",
    "MATH_SUB",
    "MATH_MULT",
    "MATH_DIV",
    "MATH_FLOOR_DIV",
    "MATH_MOD",
    "MATH_POW",
    "MATH_UNARY",
    "MATH_PAREN",
    "IS_DIGIT",
    "grammar",
    "get_grammar",
    "get_rules",
]
