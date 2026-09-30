"""Combinadores de almacenamiento (Save, Load, Tag)."""
from __future__ import annotations

from .load import Load
from .save import Save, StorageStacK
from .tag import Tag

__all__ = [
    "Save",
    "StorageStacK",
    "Load",
    "Tag",
]
