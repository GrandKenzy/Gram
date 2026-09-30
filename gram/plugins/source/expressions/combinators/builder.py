"""
Constructor declarativo de expresiones (ExpressionBuilder).
==========================================================
Permite construir cascadas de precedencia y asociatividad utilizando
ChainL, ChainR y prefijos de forma limpia, componible y declarativa.
"""
from __future__ import annotations

from typing import Any, Callable
from gram.core.combinators.base import Combinator
from gram.core.combinators.alternative import Alt
from gram.plugins.source.expressions.combinators.chain import ChainL, ChainR


class ExpressionBuilder:
    """
    Constructor fluido para gramáticas de expresiones sintácticas y matemáticas.

    Ejemplo:
        builder = ExpressionBuilder(primary=Alt(MatchToken(Token.NUMBER), MatchToken(Token.IDENT)))
        builder.right(MatchToken(Token.POW))
        builder.left(Alt(MatchToken(Token.STAR), MatchToken(Token.SLASH)))
        builder.left(Alt(MatchToken(Token.PLUS), MatchToken(Token.MINUS)))
        expr_combinator = builder.build()
    """
    def __init__(self, primary: Combinator):
        self._current: Combinator = primary

    def left(
        self,
        operator: Any,
        reducer: Callable[[Any, Any, Any], Any] | None = None,
    ) -> ExpressionBuilder:
        """Añade un nivel de operadores con asociatividad izquierda (ChainL)."""
        self._current = ChainL(self._current, operator, reducer=reducer)
        return self

    def right(
        self,
        operator: Any,
        reducer: Callable[[Any, Any, Any], Any] | None = None,
    ) -> ExpressionBuilder:
        """Añade un nivel de operadores con asociatividad derecha (ChainR)."""
        self._current = ChainR(self._current, operator, reducer=reducer)
        return self

    def build(self) -> Combinator:
        """Retorna el combinador de expresión resultante listo para usarse en reglas sintácticas."""
        return self._current


__all__ = ["ExpressionBuilder"]
