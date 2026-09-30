"""
GRAM_ESSENCIAL_PACK — Punto de Entrada Principal (main.py)
==========================================================
Punto de entrada oficial de GRAM_ESSENCIAL_PACK conforme al protocolo
de plugins de Gram (PluginBase).
"""
from __future__ import annotations

from typing import Any

from gram.plugins.base import PluginBase
from .combinators import (
    ErrorCombinator,
    If,
    Not,
    Peek,
    Req,
    SimpleCombinator,
    Skip,
    Until,
    get_combinators as _get_combinators,
)


class GramEssentialPackPlugin(PluginBase):
    """Plugin oficial del pack esencial de desarrollo y abstracción para Gram."""

    def on_load(self) -> bool:
        """Inicializa los combinadores y compila VSIX si está disponible."""
        from gram.core.combinators.mods import register_custom_mod
        for comb in self.get_combinators():
            register_custom_mod(comb)

        try:
            from gram import vsix
            vsix.compile_from(__file__)
        except Exception:
            pass

        return True

    def get_combinators(self) -> list[Any]:
        """Retorna los combinadores oficiales expuestos por GRAM_ESSENCIAL_PACK."""
        return _get_combinators()

    def process(self, *args: Any, **kwargs: Any) -> Any:
        """Función de procesamiento del plugin."""
        return True


def get_combinators() -> list[Any]:
    """Retorna los combinadores (Custom Mods) expuestos por GRAM_ESSENCIAL_PACK."""
    return _get_combinators()


def load() -> bool:
    """Función de carga de conveniencia."""
    plugin = GramEssentialPackPlugin()
    return plugin.on_load()


def process(*args: Any, **kwargs: Any) -> Any:
    """Función de procesamiento de conveniencia."""
    return True


__all__ = [
    "GramEssentialPackPlugin",
    "load",
    "process",
    "get_combinators",
    "SimpleCombinator",
    "If",
    "ErrorCombinator",
    "Req",
    "Skip",
    "Peek",
    "Not",
    "Until",
]
