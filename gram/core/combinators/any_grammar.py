"""
Combinador AnyGrammar (`gram.core.combinators.any_grammar`).
===========================================================
Combinador experimental para validación de comodines sintácticos.
En la arquitectura de Gram v1.0.0, este combinador levanta formalmente
un `GrammarError` con código `ANY_NOT_IMPLEMENTED` aconsejando el uso
de alternativas explícitas como `Alt()` o `MatchGroup()`.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from gram import errors
from gram.core.combinators.base import Combinator
from gram.utilities import error

if TYPE_CHECKING:
    from gram.core.ast import ASTAnalyzer
    from gram.core.lexer.tokens import TokenType
    from gram.core.parser.core import Parser


class AnyGrammar(Combinator):
    """
    ES:
        Combinador experimental AnyGrammar.
        En Gram Framework este combinador levanta formalmente un GrammarError
        para evitar conflictos de espacio de nombres con `typing.Any` e inducir
        especificaciones gramaticales deterministas.

    EN:
        Experimental wildcard combinator raising ANY_NOT_IMPLEMENTED by design.
    """
    header_class: bool = True

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self.header_class: bool = True
        self.args: tuple[Any, ...] = args
        self.kwargs: dict[str, Any] = kwargs

    def parse(
        self,
        analyzer: ASTAnalyzer | Parser | Any,
        current: TokenType | None = None,
        ignore_errors: bool = False,
    ) -> Any:
        """
        Levanta GrammarError indicando que Any no está implementado directamente.

        Raises:
            GrammarError: Con código ANY_NOT_IMPLEMENTED.
        """
        err = error.GrammarError(
            "Combinador no implementado",
            errors.ANY_NOT_IMPLEMENTED,
            "El combinador 'Any' / 'AnyGrammar' no está implementado en Gram.",
            "Considere estructurar su regla gramatical mediante combinadores explícitos como Alt() o MatchGroup().",
        )
        target_node = self._get_node(analyzer)
        if target_node is not None:
            target_node.note(f"Error gramatical: {err.name} ({err.code})", "Error")
        err.raise_error()

    def __repr__(self) -> str:
        return "AnyGrammar()"


# Alias interno para evitar colisión con typing.Any
_Any = AnyGrammar


__all__ = [
    "AnyGrammar",
]
