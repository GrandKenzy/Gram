"""
Combinador Load (`gram.plugins.source.storage.combinators.load`).
================================================================
Permite recuperar un token almacenado previamente en StorageStacK.
"""
from __future__ import annotations

from typing import Any

from gram.core.combinators.additional_stack import CombinatorAdditionalStack
from gram.core.combinators.base import Combinator
from gram.core.lexer.tokens import TokenType
from .save import StorageStacK


class Load(Combinator):
    """
    Combinador y auxiliar que recupera un token almacenado en StorageStacK.
    Al usarse en una secuencia no consume tokens.
    """
    code: int = 5002
    name: str = "Load"
    description: str = "Recupera un token almacenado previamente en StorageStacK sin consumirlo."
    docs: str = "docs/load.md"
    colors: dict[int, str] = {0: "#CE9178"}
    suggestions: dict[int, Any] = {0: [("nombre_var", "Nombre de la variable a cargar de StorageStacK", "Clave previamente guardada")]}
    suggestions_autocomplete: bool = True

    def __init__(self, name: str) -> None:
        super().__init__()
        self.name = name

    def get(self) -> TokenType | None:
        """Obtiene la instancia TokenType almacenada bajo la clave de este combinador."""
        return StorageStacK.get(self.name)

    def __call__(self) -> TokenType | None:
        return self.get()

    @property
    def token(self) -> Any | None:
        tok = self.get()
        return tok.token if tok is not None else None

    @property
    def value(self) -> Any | None:
        tok = self.get()
        return tok.value if tok is not None else None

    @property
    def line(self) -> int:
        tok = self.get()
        return tok.line if tok is not None else 0

    @property
    def col(self) -> int:
        tok = self.get()
        return tok.col if tok is not None else 0

    def parse(
        self,
        analyzer: Any,
        current: TokenType,
        ignore_errors: bool = False,
    ) -> TokenType | None:
        """
        Retorna el token almacenado y restaura la posición del parser
        para actuar como combinador de ancho cero.
        """
        saved_token = self.get()

        if hasattr(analyzer, "parser") and hasattr(analyzer.parser, "restore"):
            analyzer.parser.restore(analyzer.parser.pos - 1)

        return saved_token

    def __eq__(self, other: Any) -> bool:
        tok = self.get()
        if tok is None:
            return False
        if isinstance(other, str):
            curr_name = getattr(tok.token, "name", str(tok.token))
            return curr_name == other or tok.value == other
        if hasattr(other, "name"):
            return tok.token == other
        return tok == other

    def __repr__(self) -> str:
        return f"Load({self.name!r})"


CombinatorAdditionalStack.register(Load)
