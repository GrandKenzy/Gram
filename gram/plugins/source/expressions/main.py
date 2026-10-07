"""
Plugin expressions — Punto de Entrada Principal (main.py)
=========================================================
Provee soporte completo para expresiones en Gram Framework:
- Combinadores de asociatividad: ChainL (izquierda) y ChainR (derecha)
- Constructor declarativo de precedencias: ExpressionBuilder
- Aritmética: Suma (+), Resta (-), Multiplicación (*), División (/), División entera (//), Módulo (%), Potencia (**)
- Operaciones a nivel de bits: &, |, ^, <<, >>
- Operaciones de comparación: ==, !=, <, <=, >, >=
- Asignación: = (asociatividad derecha)
- Operadores unarios (+, -, ~) con encadenamiento
- Funciones matemáticas en entorno (sqrt, abs, min, max, sin, cos, tan, round, floor, ceil, log, exp, pow)
- Paréntesis y anidamiento arbitrario
- Compatible con VSIX y GLang.
"""
from __future__ import annotations

from typing import Any

from gram.core.combinators.base import RuleItem
from gram.plugins.base import PluginBase
from .combinators import (
    ArithmeticExpr,
    ChainL,
    ChainR,
    ConditionalExpr,
    ConditionalSyntaxError,
    ExpressionBuilder,
    IsDigit,
    MathBinaryOp,
    MathGroup,
    MathUnaryOp,
    get_combinators as _get_combinators,
)
from .evaluator import (
    ArithmeticNode,
    ArithmeticSyntaxError,
    BinaryOpNode,
    BooleanNode,
    DEFAULT_ENV,
    FunctionCallNode,
    GroupNode,
    NumberNode,
    UnaryOpNode,
    VariableNode,
    evaluate,
)
from .grammar import (
    ARITHMETIC_EXPR,
    COMP_OP,
    CONDITIONAL_EXPR,
    IS_DIGIT,
    LOGIC_OP,
    MATH_DIV,
    MATH_FLOOR_DIV,
    MATH_MOD,
    MATH_MULT,
    MATH_PAREN,
    MATH_POW,
    MATH_SUB,
    MATH_SUM,
    MATH_UNARY,
    get_grammar as _get_grammar,
    get_rules as _get_rules,
    grammar,
)


class ExpressionsPlugin(PluginBase):
    """Plugin oficial de expresiones matemáticas, operadores y evaluador para Gram."""

    def on_load(self) -> bool:
        """Inicializa los combinadores y compila VSIX si está disponible."""
        from gram.core.combinators.mods import register_custom_mod
        register_custom_mod(ChainL)
        register_custom_mod(ChainR)
        register_custom_mod(ConditionalExpr)

        try:
            from gram import vsix
            vsix.compile_from(__file__)
        except Exception:
            pass

        return True

    def get_combinators(self) -> list[Any]:
        """Retorna los combinadores expuestos por el plugin expressions."""
        return _get_combinators()

    def get_rules(self) -> list[type[RuleItem]]:
        """Retorna las clases RuleItem expuestas por el plugin."""
        return _get_rules()

    def get_grammar(self) -> dict[Any, Any]:
        """Retorna el diccionario de reglas gramaticales físicas expuestas por el plugin."""
        return _get_grammar()

    def process(self, *args: Any, **kwargs: Any) -> Any:
        """
        Función de procesamiento del plugin.
        Si se invoca con una expresión (string, tokens o AST), la evalúa.
        """
        if args:
            first = args[0]
            if isinstance(first, (str, list)) or hasattr(first, "tokens") or hasattr(first, "value"):
                env = kwargs.get("env", args[1] if len(args) > 1 and isinstance(args[1], dict) else None)
                return evaluate(first, env=env)
            return True
        return True


def get_combinators() -> list[Any]:
    """Retorna los combinadores expuestos por el plugin expressions."""
    return _get_combinators()


def get_grammar() -> dict[Any, Any]:
    """Retorna el diccionario de reglas gramaticales físicas expuestas por el plugin."""
    return _get_grammar()


__all__ = [
    # Plugin Base
    "ExpressionsPlugin",
    "get_combinators",
    "get_grammar",
    "evaluate",
    # Evaluador y Nodos
    "ArithmeticNode",
    "BooleanNode",
    "BinaryOpNode",
    "NumberNode",
    "VariableNode",
    "UnaryOpNode",
    "GroupNode",
    "FunctionCallNode",
    "ArithmeticSyntaxError",
    "DEFAULT_ENV",
    # Combinadores
    "ChainL",
    "ChainR",
    "ExpressionBuilder",
    "ArithmeticExpr",
    "ConditionalExpr",
    "ConditionalSyntaxError",
    "IsDigit",
    "MathBinaryOp",
    "MathUnaryOp",
    "MathGroup",
    # Reglas RuleItem
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
]
