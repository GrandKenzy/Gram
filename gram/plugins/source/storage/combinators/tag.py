"""
Combinador Tag (`gram.plugins.source.storage.combinators.tag`).
==============================================================
Añade una etiqueta semántica al AST sin consumir tokens del código fuente.
"""
from __future__ import annotations

from typing import Any

from gram.core.combinators.additional_stack import CombinatorAdditionalStack
from gram.core.combinators.base import Combinator
from gram.core.lexer.tokens import Token, TokenType


class Tag(Combinator):
    """
    Añade una etiqueta semántica identificadora ('tag.<nombre>') al AST
    sin consumir tokens del flujo de entrada.
    """
    code: int = 5003
    name: str = "Tag"
    description: str = "Añade una etiqueta semántica ('tag.<nombre>') al AST sin consumir tokens."
    docs: str = "docs/tag.md"
    colors: dict[int, str] = {0: "#569CD6"}
    suggestions: dict[int, Any] = {0: [("etiqueta", "Nombre de la etiqueta semántica ('tag.<nombre>')", "Valor inyectado en AST values")]}
    suggestions_autocomplete: bool = True

    def __init__(self, name: str) -> None:
        super().__init__()
        self.name = name

    def parse(
        self,
        analyzer: Any,
        current: TokenType,
        ignore_errors: bool = False,
    ) -> TokenType:
        tag_token = TokenType(
            Token.IDENT,
            f"tag.{self.name}",
            line=getattr(current, "line", 1) - 1 if hasattr(current, "line") else 0,
            col=getattr(current, "col", 0),
        )

        if hasattr(analyzer, "parser") and hasattr(analyzer.parser, "restore"):
            analyzer.parser.restore(analyzer.parser.pos - 1)

        return tag_token

    def __repr__(self) -> str:
        return f"Tag({self.name!r})"


CombinatorAdditionalStack.register(Tag)
