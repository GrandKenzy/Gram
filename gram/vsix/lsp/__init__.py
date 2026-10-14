"""
Language Server Protocol Subsystem (`gram.vsix.lsp`).
=====================================================
Exports language server protocol state management, isolated document sessions,
and non-invasive telemetry bridges for editor tooling.
"""
from __future__ import annotations

from gram.vsix.lsp.server import JSONRPCProtocol, LSPServer, start_server
from gram.vsix.lsp.state import DocumentSession, LSPState

__all__ = [
    "DocumentSession",
    "JSONRPCProtocol",
    "LSPServer",
    "LSPState",
    "start_server",
]
