"""
Módulo de Validación Previa y Análisis de Seguridad de Plugins de Gram.
========================================================================
Inspecciona exhaustivamente el directorio de un plugin antes de su instalación,
carga o almacenamiento en caché:
- Valida la sintaxis e integridad de manifest.json mediante PluginManifest.
- Comprueba la compatibilidad SemVer con la versión del motor Gram.
- Ejecuta auditoría de seguridad completa (importaciones, dunders, eval/exec)
  mediante ``gram.plugins.security``.
- Verifica que main.py defina una subclase de PluginBase.
- Valida capacidades declaradas en el manifest frente a métodos implementados.
- Comprueba si el plugin ya está instalado o si hay discrepancia de versión.
"""
from __future__ import annotations

import ast
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import gram
from gram import errors
from gram.plugins.manager.manifest_processor import ManifestProcessor
from gram.plugins.manifest import PluginManifest, match_semver, parse_semver


def should_ignore(name: str) -> bool:
    """Filtra archivos temporales, binarios y cachés innecesarios."""
    ignored = {
        "__pycache__",
        ".git",
        ".pytest_cache",
        ".venv",
        ".idea",
        ".vscode",
        ".mypy_cache",
        ".ruff_cache",
        ".tox",
    }
    return name in ignored or name.endswith((".pyc", ".pyo"))


@dataclass
class ValidationIssue:
    """Representa una advertencia, error o información de validación de un plugin."""
    level: str  # "ERROR" | "WARNING" | "DUPLICATE" | "INFO"
    code: Any = None
    message: str = ""
    file: str | None = None
    line: int | None = None

    def format_line(self) -> str:
        """Formatea la incidencia con ubicación de archivo y línea si están disponibles."""
        loc = f" ({self.file}:{self.line})" if self.file and self.line else (f" ({self.file})" if self.file else "")
        return f"{self.message}{loc}"


@dataclass
class ValidationReport:
    """Informe detallado del resultado de la validación previa."""
    plugin_name: str
    source_dir: Path
    manifest: PluginManifest | None = None
    issues: list[ValidationIssue] = field(default_factory=list)
    uuid: str = ""
    installed_version: str | None = None
    incoming_version: str | None = None
    is_installed: bool = False
    is_protected: bool = False
    version_mismatch: bool = False
    target_folder: str = ""

    @property
    def is_valid(self) -> bool:
        """Indica si el plugin no contiene errores fatales que impidan su instalación o uso."""
        return not any(i.level == "ERROR" for i in self.issues)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.level == "ERROR"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.level == "WARNING"]

    @property
    def duplicates(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.level == "DUPLICATE"]

    @property
    def infos(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.level == "INFO"]


def validate_plugin(
    source_dir: Path | str,
    target_name: str | None = None,
    installed_plugins_dir: Path | None = None,
) -> ValidationReport:
    """
    Inspecciona y valida estáticamente un plugin en su directorio de origen.

    Args:
        source_dir: Ruta al directorio del plugin.
        target_name: Nombre objetivo opcional para sobrescribir o validar.
        installed_plugins_dir: Directorio del catálogo de plugins de Gram.

    Returns:
        ``ValidationReport`` con el estado, errores y metadatos del plugin.
    """
    source_path = Path(source_dir).resolve()
    effective_name = target_name or source_path.name

    report = ValidationReport(
        plugin_name=effective_name,
        source_dir=source_path,
        target_folder=target_name or source_path.name,
    )

    if not source_path.exists() or not source_path.is_dir():
        report.issues.append(
            ValidationIssue(
                level="ERROR",
                code=errors.PLUGIN_MANIFEST_NOT_FOUND,
                message=f"La ruta del plugin no existe o no es un directorio: {source_path}",
            )
        )
        return report

    # 1. Validar manifest.json
    manifest_file = source_path / "manifest.json"
    if not manifest_file.exists():
        report.issues.append(
            ValidationIssue(
                level="ERROR",
                code=errors.PLUGIN_MANIFEST_NOT_FOUND,
                message=f"Falta el archivo requerido 'manifest.json' en: {source_path}",
            )
        )
        return report

    try:
        proc_result = ManifestProcessor.process(manifest_file, require_main=False)
        manifest = proc_result.manifest
    except Exception as exc:
        report.issues.append(
            ValidationIssue(
                level="ERROR",
                code=errors.PLUGIN_MANIFEST_INVALID,
                message=f"Error en manifest.json: {exc}",
                file="manifest.json",
            )
        )
        return report

    report.manifest = manifest
    if manifest:
        report.plugin_name = manifest.plugin_name
        report.uuid = manifest.uuid
        report.incoming_version = manifest.version_str
        report.is_protected = (manifest.capabilities.protect >= 4) or (not manifest.capabilities.replaceable)

        # Validar compatibilidad SemVer con el motor Gram
        current_engine = getattr(gram, "__version_info__", (1, 0, 0))
        if not match_semver(current_engine, manifest.min_engine):
            report.issues.append(
                ValidationIssue(
                    level="ERROR",
                    code=errors.PLUGIN_INCOMPATIBLE_GRAM_VERSION,
                    message=(
                        f"Versión de Gram incompatible. El plugin requiere Gram >={manifest.min_engine_str}, "
                        f"pero la versión actual es {'.'.join(str(x) for x in current_engine)}."
                    ),
                    file="manifest.json",
                )
            )

    # 2. Validar presencia de main.py
    main_py = source_path / "main.py"
    if not main_py.exists():
        report.issues.append(
            ValidationIssue(
                level="ERROR",
                code=errors.PLUGIN_MAIN_NOT_FOUND,
                message=f"Falta el archivo de punto de entrada 'main.py' en: {source_path}",
            )
        )
    if not (source_path / "__init__.py").exists():
        report.issues.append(
            ValidationIssue(
                level="INFO",
                code=None,
                message="Se recomienda incluir '__init__.py' para tratar el plugin como un paquete Python estándar.",
            )
        )

    # 3. Auditoría de seguridad completa (importaciones, dunders, eval/exec)
    from gram.plugins.security import audit_plugin_directory
    security_issues = audit_plugin_directory(source_path)
    for sec_issue in security_issues:
        report.issues.append(
            ValidationIssue(
                level=sec_issue.level,
                code=sec_issue.code,
                message=sec_issue.message,
                file=sec_issue.file,
                line=sec_issue.line,
            )
        )

    # 4. Verificar que main.py define una subclase de PluginBase
    if main_py.exists() and not any(i.code == errors.PLUGIN_SYNTAX_ERROR for i in report.issues):
        try:
            content = main_py.read_text(encoding="utf-8")
            main_ast = ast.parse(content, filename=str(main_py))

            # Detectar herencia de PluginBase
            inherits_plugin_base = any(
                any(
                    (isinstance(base, ast.Name) and base.id == "PluginBase")
                    or (isinstance(base, ast.Attribute) and base.attr == "PluginBase")
                    for base in node.bases
                )
                for node in ast.walk(main_ast)
                if isinstance(node, ast.ClassDef)
            )
            defined_classes = {
                node.name for node in ast.walk(main_ast)
                if isinstance(node, ast.ClassDef)
            }

            if not defined_classes:
                report.issues.append(
                    ValidationIssue(
                        level="ERROR",
                        code=errors.PLUGIN_MAIN_NOT_FOUND,
                        message="main.py no define ninguna clase. El plugin debe subclasificar PluginBase.",
                        file="main.py",
                    )
                )
            elif not inherits_plugin_base:
                report.issues.append(
                    ValidationIssue(
                        level="WARNING",
                        code=errors.PLUGIN_CAPABILITY_MISSING,
                        message=(
                            f"Las clases {defined_classes} en main.py no parecen heredar de PluginBase. "
                            "El plugin no se cargará correctamente."
                        ),
                        file="main.py",
                    )
                )

            # Validar métodos de capacidades declaradas
            if manifest and inherits_plugin_base:
                defined_methods = {
                    node.name for node in ast.walk(main_ast)
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                }
                if manifest.capabilities.load and "on_load" not in defined_methods:
                    report.issues.append(
                        ValidationIssue(
                            level="INFO",
                            code=None,
                            message="Capacidad 'load' activa pero on_load() no está sobrescrito (se usará la implementación base).",
                            file="main.py",
                        )
                    )
                if manifest.capabilities.process and "process" not in defined_methods:
                    report.issues.append(
                        ValidationIssue(
                            level="ERROR",
                            code=errors.PLUGIN_CAPABILITY_MISSING,
                            message="Capacidad 'process' activa pero process() no está implementado.",
                            file="main.py",
                        )
                    )
                if manifest.capabilities.cli and "cli" not in defined_methods:
                    report.issues.append(
                        ValidationIssue(
                            level="ERROR",
                            code=errors.PLUGIN_CAPABILITY_MISSING,
                            message="Capacidad 'cli' activa pero cli() no está implementado.",
                            file="main.py",
                        )
                    )

        except SyntaxError as syn_err:
            report.issues.append(
                ValidationIssue(
                    level="ERROR",
                    code=errors.PLUGIN_SYNTAX_ERROR,
                    message=f"Error sintáctico en main.py: {syn_err.msg}",
                    file="main.py",
                    line=syn_err.lineno,
                )
            )

    # 5. Comprobar instalación previa y colisión de versiones
    if installed_plugins_dir and installed_plugins_dir.exists():
        candidate_dir = installed_plugins_dir / report.target_folder
        if candidate_dir.exists() and candidate_dir.is_dir():
            report.is_installed = True
            c_manifest = candidate_dir / "manifest.json"
            if c_manifest.exists():
                try:
                    c_data = json.loads(c_manifest.read_text(encoding="utf-8"))
                    c_ver = c_data.get("version")
                    if isinstance(c_ver, list):
                        report.installed_version = ".".join(str(x) for x in c_ver)
                    elif isinstance(c_ver, str):
                        report.installed_version = c_ver

                    if report.installed_version and report.incoming_version:
                        report.version_mismatch = (report.installed_version != report.incoming_version)
                except Exception:
                    pass

    return report


__all__ = [
    "ValidationIssue",
    "ValidationReport",
    "validate_plugin",
    "should_ignore",
]
