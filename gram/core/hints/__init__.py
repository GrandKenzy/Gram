"""
Subsistema de Pistas Virtuales e Inlay Hints (`gram.core.hints`).
================================================================
Permite la definición, gestión y materialización de pistas visuales virtuales
(Inlay Hints de tipos, parámetros y metadatos) en reglas gramaticales RuleItem
y en el servidor de lenguaje LSP de Gram Framework.
"""
from __future__ import annotations

from gram.core.hints.definition import Hints, InlayHintKind, VirtualHint
from gram.core.hints.manager import VirtualHintManager

__all__ = [
    "Hints",
    "InlayHintKind",
    "VirtualHint",
    "VirtualHintManager",
]
