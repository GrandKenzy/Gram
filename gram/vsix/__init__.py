"""
Subsistema de Extensión y Resaltado VS Code / VSIX (`gram.vsix`).
================================================================
Permite extraer metadatos de sintaxis, autocompletado y esquemas de color de Gram y sus plugins,
generando gramáticas TextMate (.tmLanguage.json), temas cromáticos (.json),
configuraciones de lenguaje, fragmentos (snippets), servidor de lenguaje (LSP) y paquetes .vsix.

Puntos de Entrada:
  - `compile()`: Genera el paquete VSIX consolidado con LSP y compilador.
  - `install()`: Compila e instala la extensión en Visual Studio Code mediante la CLI `code`.
  - `uninstall()`: Desinstala la extensión de Gram en Visual Studio Code por su ID universal.
  - `is_installed()` / `list_installed()`: Consulta el estado de instalación en VS Code.
  - `compile_from()`: Compilación modular en plugins.
"""
from __future__ import annotations

from gram.vsix.core import (
    VsixManager,
    find_vscode_executable,
    manager,
)
from gram.vsix.extract import (
    KeywordMetadata,
    RuleMetadata,
    SyntaxMetadata,
    extract_metadata,
)
from gram.vsix.generate import (
    GRAM_EXTENSION_NAME,
    GRAM_FULL_ID,
    GRAM_PUBLISHER,
    build_extension_directory,
    generate_icon_png,
    generate_language_configuration,
    generate_lsp_client_js,
    generate_package_json,
    generate_snippets,
    generate_textmate_grammar,
    generate_theme,
    package_vsix,
)
from gram.vsix.lsp import (
    GramLanguageServer,
    start_lsp_server,
)

# Fachada pública directa a nivel de módulo
compile = manager.compile
install = manager.install
uninstall = manager.uninstall
is_installed = manager.is_installed
list_installed = manager.list_installed
reload = manager.reload
clear = manager.clear
compile_from = manager.compile_from
get_active_vsix = manager.get_active_vsix
register_user_grammar = manager.register_user_grammar
register_user_keyword = manager.register_user_keyword

__all__ = [
    # Identificadores universales
    "GRAM_PUBLISHER",
    "GRAM_EXTENSION_NAME",
    "GRAM_FULL_ID",
    # Gestor y fachada de ciclo de vida
    "VsixManager",
    "manager",
    "compile",
    "install",
    "uninstall",
    "is_installed",
    "list_installed",
    "reload",
    "clear",
    "compile_from",
    "get_active_vsix",
    "register_user_grammar",
    "register_user_keyword",
    "find_vscode_executable",
    # Extracción de metadatos
    "KeywordMetadata",
    "RuleMetadata",
    "SyntaxMetadata",
    "extract_metadata",
    # Generadores
    "build_extension_directory",
    "generate_language_configuration",
    "generate_package_json",
    "generate_textmate_grammar",
    "generate_theme",
    "generate_snippets",
    "generate_lsp_client_js",
    "generate_icon_png",
    "package_vsix",
    # Language Server Protocol (LSP)
    "GramLanguageServer",
    "start_lsp_server",
]
