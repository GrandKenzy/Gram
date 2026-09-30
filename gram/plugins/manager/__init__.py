"""
Módulo de Gestión y Carga de Plugins para Gram (`gram.plugins.manager`).
========================================================================
"""
from __future__ import annotations

from gram.plugins.manager.core import Plugin, Plugins, get_plugins_dir
from gram.plugins.manager.manifest_processor import ManifestProcessor, ManifestProcessResult

__all__ = [
    "Plugin",
    "Plugins",
    "get_plugins_dir",
    "ManifestProcessor",
    "ManifestProcessResult",
]
