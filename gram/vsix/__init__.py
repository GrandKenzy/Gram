"""
VSIX Language Server and Editor Tooling (`gram.vsix`).
======================================================
Provides metadata extraction and schema indexing for language tooling and editors.
"""
from __future__ import annotations

from gram.vsix.coloring import (
    ASTColorResolver,
    ColoredToken,
    TokenSelector,
    collect_node_tokens,
    preview_colored_source,
    resolve_ast_colors,
)
from gram.vsix.control import VSIXState
from gram.vsix.core import Supports, VSIXAnalyzer
from gram.vsix.generator import VSIXGenerator
from gram.vsix.info import (
    PackageInfo,
    declare_info,
    get_package_info,
    reset_package_info,
    set_author,
    set_language,
    set_meta,
    set_package,
    set_repository,
)
from gram.vsix.lsp import DocumentSession, LSPServer, LSPState
from gram.vsix.packer import (
    install_extension,
    launch_vscode,
    pack_vsix,
    up,
)

__all__ = [
    "ASTColorResolver",
    "ColoredToken",
    "DocumentSession",
    "LSPServer",
    "LSPState",
    "PackageInfo",
    "Supports",
    "TokenSelector",
    "VSIXAnalyzer",
    "VSIXGenerator",
    "VSIXState",
    "collect_node_tokens",
    "declare_info",
    "get_package_info",
    "install_extension",
    "launch_vscode",
    "pack_vsix",
    "preview_colored_source",
    "reset_package_info",
    "resolve_ast_colors",
    "set_author",
    "set_language",
    "set_meta",
    "set_package",
    "set_repository",
    "up",
]
