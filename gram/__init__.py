"""
Framework Gram — Framework de Meta-Interpretación y Diseño de DSLs.
====================================================================
Versión limpia, modular y fuertemente tipada.
"""
from __future__ import annotations

from gram import cachesystem, cli, config, core, environment, errors, glang, native, plugins, sjson, utilities, vsix

__version__ = "1.0.0"
__version_info__ = (1, 0, 0)


def version() -> str:
    """Retorna la versión actual del Framework Gram."""
    return __version__


__all__ = [
    "cachesystem",
    "cli",
    "config",
    "core",
    "environment",
    "errors",
    "glang",
    "native",
    "plugins",
    "sjson",
    "utilities",
    "vsix",
    "__version__",
    "__version_info__",
    "version",
]
