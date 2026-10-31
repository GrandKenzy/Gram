"""
Gram Binary IR (GIR) Subsystem (`gram.ir`).
===========================================
Provides fast, zero-dependency deserialization, tree traversal, inspection, and
querying for Gram Binary IR (`.gir`) files and byte buffers.
"""
from __future__ import annotations

from gram.ir.reader import (
    GIR_MAGIC,
    GIR_NODE_ARRAY,
    GIR_NODE_EXPR,
    GIR_NODE_RAW,
    GIR_NODE_RULE,
    GIR_NODE_TERMINAL,
    GIR_VERSION_MAJOR,
    GIR_VERSION_MINOR,
    GirHeader,
    GirNode,
    GirView,
    load,
    load_gir,
)

__all__ = [
    "GIR_MAGIC",
    "GIR_NODE_ARRAY",
    "GIR_NODE_EXPR",
    "GIR_NODE_RAW",
    "GIR_NODE_RULE",
    "GIR_NODE_TERMINAL",
    "GIR_VERSION_MAJOR",
    "GIR_VERSION_MINOR",
    "GirHeader",
    "GirNode",
    "GirView",
    "load",
    "load_gir",
]
