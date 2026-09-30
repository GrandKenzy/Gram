"""
Sistema de Caché de Gram (`gram.cachesystem`).
==============================================
Exporta las utilidades principales para hash, validación en caché y gestión
de estados de plugins.
"""
from __future__ import annotations

from gram.cachesystem.core import (
    PluginCacheEntry,
    compute_file_hash,
    compute_plugin_tree_hash,
    get_cache_base_dir,
    get_plugin_cache,
    get_plugin_cache_dir,
    inspect_and_resolve_plugin,
    invalidate_plugin_cache,
    save_plugin_cache,
)

__all__ = [
    "PluginCacheEntry",
    "compute_file_hash",
    "compute_plugin_tree_hash",
    "get_cache_base_dir",
    "get_plugin_cache_dir",
    "get_plugin_cache",
    "save_plugin_cache",
    "invalidate_plugin_cache",
    "inspect_and_resolve_plugin",
]
