"""
Combinadores de GRAM_ESSENCIAL_PACK.
====================================
Exporta los combinadores oficiales del pack esencial de Gram:
- Req: Combinador fluido de validación y transformación de tokens.
- Skip: Señal de terminación exitosa de secuencias Seq.
- ErrorCombinator: Captura de errores acumulados en StackError.
- If: Afirmación condicional, bifurcación ok/fail y modo lookahead.
- Peek: Lookahead positivo de ancho cero.
- Not: Lookahead negativo de ancho cero.
- Until: Consumo hasta combinador objetivo.
- SimpleCombinator: Clase base simplificada para validación booleana de tokens.
"""
from __future__ import annotations

from typing import Any
from ..advanced_combinators import (
    ErrorCombinator,
    If,
    Not,
    Peek,
    Req,
    Skip,
    Until,
)
from ..combinator_base import SimpleCombinator


def get_combinators() -> list[Any]:
    """Retorna los combinadores oficiales expuestos por GRAM_ESSENCIAL_PACK."""
    return [
        Req,
        Skip,
        ErrorCombinator,
        If,
        Peek,
        Not,
        Until,
        SimpleCombinator,
    ]


__all__ = [
    "Req",
    "Skip",
    "ErrorCombinator",
    "If",
    "Peek",
    "Not",
    "Until",
    "SimpleCombinator",
    "get_combinators",
]
