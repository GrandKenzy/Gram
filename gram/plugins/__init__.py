"""
Subsistema de Plugins y Extensiones de Gram (`gram.plugins`).
=============================================================
Proporciona el gestor de manifiestos tipados, auditoría de seguridad,
aprobación de plugins por el usuario final, entorno de ejecución aislado,
esquemas cromáticos de resaltado, validación de dependencias y la integración
completa en el pipeline de Gram (Lexer, Parser, Combinators y AST).
"""
from __future__ import annotations

from gram.core.watcher import FileWatcher, PluginWatcher
from gram.plugins import registry
from gram.plugins.base import PluginBase
from gram.plugins.colors import ColorDefinition, PluginColors, parse_colors
from gram.plugins.environment import (
    allow_add,
    allow_list,
    allow_remove,
    get_plugin_data_dir,
    get_plugin_temp_dir,
    install_plugin_requirements,
    is_library_allowed,
    reset_allowed_libraries,
)
from gram.plugins.manager import Plugin, Plugins, get_plugins_dir
from gram.plugins.manifest import (
    PluginCapabilities,
    PluginDependency,
    PluginManifest,
    format_version,
    generate_uuid,
    match_semver,
    parse_manifest,
    parse_semver,
    parse_version_tuple,
)
from gram.plugins.permissions import (
    ApprovalRecord,
    PluginNotApprovedError,
    PluginPermissions,
    require_approval,
)
from gram.plugins.security import (
    BANNED_BUILTIN_CALLS,
    BANNED_DUNDER_ATTRIBUTES,
    ASTSecurityVisitor,
    SecurityIssue,
    audit_plugin_directory,
    audit_python_code,
    install_audit_hook,
    is_audit_hook_installed,
)
from gram.plugins.validator import (
    ValidationIssue,
    ValidationReport,
    validate_plugin,
)


def get_plugins() -> list[str]:
    """Retorna la lista de identificadores de plugins actualmente registrados."""
    return registry.get_load_order()


__all__ = [
    # Gestor de plugins
    "Plugin",
    "Plugins",
    "PluginBase",
    # Observadores de archivos
    "PluginWatcher",
    "FileWatcher",
    # Manifest
    "PluginManifest",
    "PluginCapabilities",
    "PluginDependency",
    "parse_manifest",
    "parse_version_tuple",
    "format_version",
    "match_semver",
    "parse_semver",
    "generate_uuid",
    # Colores
    "ColorDefinition",
    "PluginColors",
    "parse_colors",
    # Directorio de plugins
    "get_plugins_dir",
    "get_plugins",
    # Registro
    "registry",
    # Validación previa
    "validate_plugin",
    "ValidationReport",
    "ValidationIssue",
    # Seguridad
    "SecurityIssue",
    "ASTSecurityVisitor",
    "audit_python_code",
    "audit_plugin_directory",
    "install_audit_hook",
    "is_audit_hook_installed",
    "BANNED_DUNDER_ATTRIBUTES",
    "BANNED_BUILTIN_CALLS",
    # Permisos de usuario
    "ApprovalRecord",
    "PluginNotApprovedError",
    "PluginPermissions",
    "require_approval",
    # Entorno de ejecución
    "allow_list",
    "allow_add",
    "allow_remove",
    "is_library_allowed",
    "reset_allowed_libraries",
    "get_plugin_data_dir",
    "get_plugin_temp_dir",
    "install_plugin_requirements",
]
