"""
Plugin storage — Punto de Entrada Principal (main.py).
======================================================
Provee los combinadores Save, Load y Tag para Gram Framework,
compatibles con VSIX y compilables hacia GLang.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from gram.core.combinators.base import RuleItem
from gram.core.combinators.match import MatchToken
from gram.core.combinators.sequence import Seq
from gram.core.lexer.tokens import Token
from gram.plugins.base import PluginBase
from .combinators import Load, Save, StorageStacK, Tag


# ===========================================================================
# Reglas Gramaticales con Metadatos para VSIX y GLang
# ===========================================================================

class STORAGE_SAVE(RuleItem):
    code = 5001
    name = "STORAGE_SAVE"
    description = "Regla de almacenamiento: captura y guarda el token en StorageStacK sin consumirlo."
    colors = {0: "#4EC9B0"}
    grammar = Seq(Save("ident"), MatchToken(Token.IDENT))
    suggestions = {0: [("ident", "Identificador a guardar en StorageStacK")]}
    suggestions_autocomplete = True


class STORAGE_LOAD(RuleItem):
    code = 5002
    name = "STORAGE_LOAD"
    description = "Regla de carga: recupera el token almacenado previamente en StorageStacK sin consumirlo."
    colors = {0: "#CE9178"}
    grammar = Seq(Load("ident"))
    suggestions = {0: [("ident", "Identificador a cargar de StorageStacK")]}
    suggestions_autocomplete = True


class STORAGE_TAG(RuleItem):
    code = 5003
    name = "STORAGE_TAG"
    description = "Regla de etiquetado: añade una etiqueta semántica ('tag.<nombre>') al AST sin consumir tokens."
    colors = {0: "#569CD6"}
    grammar = Seq(Tag("ident"), MatchToken(Token.IDENT))
    suggestions = {0: [("ident", "Identificador a etiquetar en el AST")]}
    suggestions_autocomplete = True


# ===========================================================================
# Clase Principal del Plugin (PluginBase)
# ===========================================================================

class StoragePlugin(PluginBase):
    """Plugin oficial de combinadores de almacenamiento y etiquetado para Gram."""

    def on_load(self) -> bool:
        """Inicializa los combinadores y compila VSIX."""
        from gram.core.combinators.mods import register_custom_mod
        for comb in (Save, Load, Tag):
            register_custom_mod(comb)

        try:
            from gram import vsix
            vsix.compile_from(__file__)
        except Exception:
            pass

        return True

    def get_combinators(self) -> list[Any]:
        """Retorna los combinadores expuestos por el plugin."""
        return [Save, Load, Tag]

    def get_rules(self) -> list[type[RuleItem]]:
        """Retorna las clases RuleItem del plugin."""
        return [STORAGE_SAVE, STORAGE_LOAD, STORAGE_TAG]

    def get_grammar(self) -> dict[Any, Any]:
        """Retorna las reglas gramaticales formales del plugin."""
        return {
            STORAGE_SAVE: STORAGE_SAVE.grammar,
            STORAGE_LOAD: STORAGE_LOAD.grammar,
            STORAGE_TAG: STORAGE_TAG.grammar,
        }

    def process(self, *args: Any, **kwargs: Any) -> bool:
        """Función de procesamiento del plugin."""
        return True


def get_combinators() -> list[Any]:
    """Retorna los combinadores expuestos por el plugin."""
    return [Save, Load, Tag]


def get_rules() -> list[type[RuleItem]]:
    """Retorna las clases RuleItem del plugin."""
    return [STORAGE_SAVE, STORAGE_LOAD, STORAGE_TAG]


def get_grammar() -> dict[Any, Any]:
    """Retorna las reglas gramaticales formales del plugin."""
    return {
        STORAGE_SAVE: STORAGE_SAVE.grammar,
        STORAGE_LOAD: STORAGE_LOAD.grammar,
        STORAGE_TAG: STORAGE_TAG.grammar,
    }


__all__ = [
    "StoragePlugin",
    "STORAGE_SAVE",
    "STORAGE_LOAD",
    "STORAGE_TAG",
    "get_combinators",
    "get_rules",
    "get_grammar",
]
