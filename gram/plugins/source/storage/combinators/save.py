"""
Combinador Save y Almacén StorageStacK (`gram.plugins.source.storage.combinators.save`).
========================================================================================
Provee almacenamiento estático en memoria para tokens encontrados durante el análisis
sintáctico sin consumir el flujo del parser.
"""
from __future__ import annotations

from typing import Any

from gram.core.combinators.additional_stack import CombinatorAdditionalStack
from gram.core.combinators.base import Combinator
from gram.core.lexer.tokens import TokenType
from gram.errors import codes
from gram.utilities import error


class StorageStacK:
    """Almacén estático para registrar y recuperar tokens por nombre de clave."""
    storage: dict[str, TokenType] = {}

    @classmethod
    def save(cls, name: str, value: TokenType) -> None:
        cls.storage[name] = value

    @classmethod
    def get(cls, name: str) -> TokenType | None:
        return cls.storage.get(name)

    @classmethod
    def has(cls, name: str) -> bool:
        return name in cls.storage

    @classmethod
    def clear(cls) -> None:
        cls.storage.clear()


class Save(Combinator):
    """
    Combinador que captura y almacena el token actual en StorageStacK SIN consumirlo.
    Permite que los combinadores subsecuentes procesen el token normalmente.
    """
    code: int = 5001
    name: str = "Save"
    description: str = "Captura y almacena el token actual en StorageStacK sin consumirlo."
    docs: str = "docs/save.md"
    colors: dict[int, str] = {0: "#4EC9B0"}
    suggestions: dict[int, Any] = {0: [("nombre_var", "Nombre bajo el cual almacenar el token", "Clave textual en StorageStacK")]}
    suggestions_autocomplete: bool = True

    def __init__(
        self,
        name: str,
        token_type: str = "",
        combinator: Any = None,
    ) -> None:
        super().__init__()
        self.name = name
        self.token_type = token_type
        self.combinator = combinator

    def _matches(self, current: TokenType) -> bool:
        """Verifica si el token actual satisface las condiciones opcionales del filtro."""
        if self.combinator is None:
            if not self.token_type or self.token_type == "*":
                return True
            curr_name = getattr(current.token, "name", str(current.token))
            return curr_name == self.token_type

        if hasattr(self.combinator, "keyword"):
            return current.value == self.combinator.keyword

        if hasattr(self.combinator, "token"):
            curr_name = getattr(current.token, "name", str(current.token))
            target = self.combinator.token
            target_name = getattr(target, "name", str(target))
            return (current.token == target) or (curr_name == target_name)

        if hasattr(self.combinator, "group_name"):
            val = str(current.value) if current.value is not None else ""
            tname = getattr(current.token, "name", str(current.token))
            if hasattr(self.combinator, "exclude") and (val in self.combinator.exclude or tname in self.combinator.exclude):
                return False
            if hasattr(self.combinator, "include") and (val in self.combinator.include or tname in self.combinator.include):
                return True

        return False

    def parse(
        self,
        analyzer: Any,
        current: TokenType,
        ignore_errors: bool = False,
    ) -> TokenType | None:
        target_node = self._get_node(analyzer)

        if not self._matches(current):
            if ignore_errors:
                return None
            err_code = codes.CodeError((2, 1, 1, 0, 1), "Storage.SaveTypeMismatch")
            error.ParserError(
                f"El token actual '{current.value}' no coincide con el criterio requerido por Save('{self.name}').",
                err_code,
                f"Línea {current.line}, Columna {current.col}",
            ).raise_error()

        StorageStacK.save(self.name, current)

        if target_node:
            target_node.note(f"Token '{current.value}' guardado en StorageStacK como '{self.name}'.", "Normal")

        # Restaurar la posición del parser para NO consumir el token
        if hasattr(analyzer, "parser") and hasattr(analyzer.parser, "restore"):
            analyzer.parser.restore(analyzer.parser.pos - 1)

        return current

    def __repr__(self) -> str:
        return f"Save({self.name!r})"


CombinatorAdditionalStack.register(Save)
