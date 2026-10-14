"""
Combinadores expuestos por el plugin Expressions.
"""
from __future__ import annotations

from typing import Any
from .is_digit import IsDigit
from .arithmetic_expr import ArithmeticExpr
from .math_ops import MathBinaryOp, MathUnaryOp, MathGroup
from .chain import ChainL, ChainR
from .builder import ExpressionBuilder
from .conditional_expr import ConditionalExpr, ConditionalSyntaxError


def get_combinators() -> list[Any]:
    """Retorna los combinadores expuestos por el plugin expressions para Gram y GLang."""
    return [
        ChainL,
        ChainR,
        ExpressionBuilder,
        ArithmeticExpr,
        ConditionalExpr,
        IsDigit,
        MathBinaryOp,
        MathUnaryOp,
        MathGroup,
    ]


__all__ = [
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
    "get_combinators",
]
