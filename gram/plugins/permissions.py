"""
Sistema de Permisos y Aprobación de Plugins de Gram (`gram.plugins.permissions`).
==================================================================================
Gestiona qué plugins han sido explícitamente aprobados por el usuario final para
su ejecución. Ningún plugin puede cargarse sin aprobación previa, a menos que el
usuario haya habilitado ``config.PLUGINS_ALLOW_ALL_PLUGINS = True`` (modo de
desarrollo/depuración — no recomendado en producción).

Diseño:
  - Las aprobaciones se almacenan en un archivo JSON persistente
    (``~/.gram/approved_plugins.json`` por defecto).
  - La aprobación incluye el nombre del plugin, su UUID y su versión,
    garantizando que una actualización del plugin requiera re-aprobación.
  - La aprobación interactiva (``request_approval()``) muestra un resumen
    del plugin al usuario en consola y solicita confirmación explícita.
  - Los plugins pueden ser revocados individualmente o en bloque.
  - Todo el subsistema es accesible únicamente por el usuario final;
    los plugins tienen prohibido invocar funciones de aprobación.
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from gram import config

if TYPE_CHECKING:
    from gram.plugins.manifest import PluginManifest


# ---------------------------------------------------------------------------
# Estructuras de datos
# ---------------------------------------------------------------------------

@dataclass
class ApprovalRecord:
    """Registro de aprobación de un plugin por el usuario final."""
    name: str
    uuid: str
    version: str
    approved_at: str        # ISO-8601
    capabilities: list[str]

    def matches(self, manifest: PluginManifest) -> bool:
        """
        Comprueba si este registro corresponde al manifest dado.

        Un plugin se considera previamente aprobado solo si el UUID **y**
        la versión coinciden exactamente. Cualquier cambio de versión invalida
        la aprobación anterior.
        """
        return (
            self.uuid == manifest.uuid
            and self.version == manifest.version_str
        )


class PluginNotApprovedError(Exception):
    """
    Excepción lanzada cuando se intenta cargar un plugin que no ha sido
    aprobado explícitamente por el usuario final.
    """
    def __init__(self, plugin_name: str, uuid: str, version: str) -> None:
        self.plugin_name = plugin_name
        self.uuid = uuid
        self.version = version
        super().__init__(
            f"El plugin '{plugin_name}' (v{version}, UUID: {uuid}) "
            "no ha sido aprobado por el usuario. "
            "Use PluginPermissions.request_approval() o apruébelo antes de cargarlo."
        )


# ---------------------------------------------------------------------------
# Almacenamiento persistente
# ---------------------------------------------------------------------------

def _get_approvals_file() -> Path:
    """Ruta al archivo JSON de aprobaciones de plugins."""
    base = Path(getattr(config, "DATA_DIR", None) or (Path.home() / ".gram")).resolve()
    base.mkdir(parents=True, exist_ok=True)
    return base / "approved_plugins.json"


def _load_approvals() -> dict[str, ApprovalRecord]:
    """Carga las aprobaciones persistidas desde disco."""
    path = _get_approvals_file()
    if not path.exists():
        return {}

    try:
        raw: list[dict] = json.loads(path.read_text(encoding="utf-8"))
        records: dict[str, ApprovalRecord] = {}
        for item in raw:
            rec = ApprovalRecord(
                name=item["name"],
                uuid=item["uuid"],
                version=item["version"],
                approved_at=item.get("approved_at", ""),
                capabilities=item.get("capabilities", []),
            )
            records[rec.uuid] = rec
        return records
    except Exception:
        return {}


def _save_approvals(records: dict[str, ApprovalRecord]) -> None:
    """Persiste el estado de aprobaciones en disco."""
    path = _get_approvals_file()
    try:
        data = [asdict(rec) for rec in records.values()]
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


# ---------------------------------------------------------------------------
# API pública de permisos
# ---------------------------------------------------------------------------

class PluginPermissions:
    """
    Gestor estático de permisos de plugins de Gram.

    Todas las operaciones de escritura (aprobación, revocación) solo pueden
    ser realizadas por el usuario final. Los plugins tienen terminantemente
    prohibido llamar ``approve()`` o ``revoke()``.
    """

    @staticmethod
    def _active_records() -> dict[str, ApprovalRecord]:
        return _load_approvals()

    @staticmethod
    def _assert_not_plugin_caller() -> None:
        """Lanza PluginError si la llamada ocurre dentro de la carga de un plugin."""
        from gram import errors
        from gram.plugins import registry as _registry
        from gram.utilities import error

        active_plugin = _registry.get_current_loading()
        if active_plugin is not None:
            error.PluginError(
                "Modificación de permisos denegada",
                errors.PLUGIN_CONFIG_MUTATION_DENIED,
                f"El plugin '{active_plugin}' intentó modificar el sistema de permisos.",
                "Solo el usuario final puede aprobar o revocar plugins.",
            ).raise_error()

    # --- Consultas ---

    @staticmethod
    def is_approved(manifest: PluginManifest) -> bool:
        """
        Retorna True si el plugin representado por *manifest* ha sido
        previamente aprobado con la misma versión y UUID.
        """
        # Modo permisivo de desarrollo: todos los plugins pasan
        if getattr(config, "PLUGINS_ALLOW_ALL_PLUGINS", False):
            return True

        records = _load_approvals()
        rec = records.get(manifest.uuid)
        return rec is not None and rec.matches(manifest)

    @staticmethod
    def list_approved() -> list[ApprovalRecord]:
        """Retorna la lista de plugins actualmente aprobados."""
        return list(_load_approvals().values())

    # --- Aprobación programática (solo usuario final) ---

    @staticmethod
    def approve(manifest: PluginManifest) -> ApprovalRecord:
        """
        Aprueba programáticamente un plugin sin interacción de consola.

        Uso típico:
          ``PluginPermissions.approve(plugin.manifest)`` desde ``__main__``.

        Raises:
            PermissionError: Si la llamada proviene de código de un plugin.
        """
        PluginPermissions._assert_not_plugin_caller()

        import datetime
        caps = _capabilities_list(manifest)
        records = _load_approvals()
        rec = ApprovalRecord(
            name=manifest.plugin_name,
            uuid=manifest.uuid,
            version=manifest.version_str,
            approved_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            capabilities=caps,
        )
        records[manifest.uuid] = rec
        _save_approvals(records)
        return rec

    # --- Aprobación interactiva (consola) ---

    @staticmethod
    def request_approval(
        manifest: PluginManifest,
        security_issues: list | None = None,
    ) -> bool:
        """
        Solicita al usuario la aprobación interactiva del plugin en consola.

        Muestra un resumen del plugin (nombre, versión, autor, capacidades,
        dependencias y posibles problemas de seguridad detectados) y aguarda
        confirmación explícita (``s``/``n``).

        Args:
            manifest: Manifiesto del plugin a aprobar.
            security_issues: Hallazgos de auditoría estática (opcional).

        Returns:
            True si el usuario aprueba el plugin, False en caso contrario.
        """
        # Si ya está aprobado para esta versión, no se vuelve a preguntar
        if PluginPermissions.is_approved(manifest):
            return True

        _print_approval_prompt(manifest, security_issues or [])

        try:
            answer = input("¿Aprobar plugin? [s/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nAprobación cancelada.")
            return False

        if answer in ("s", "si", "sí", "y", "yes"):
            PluginPermissions.approve(manifest)
            print(f"✔  Plugin '{manifest.plugin_name}' aprobado.\n")
            return True

        print(f"✗  Plugin '{manifest.plugin_name}' rechazado. No se cargará.\n")
        return False

    # --- Revocación ---

    @staticmethod
    def revoke(plugin_uuid: str) -> bool:
        """
        Revoca la aprobación de un plugin por su UUID.

        Raises:
            PermissionError: Si la llamada proviene de un plugin.

        Returns:
            True si se revocó una aprobación existente.
        """
        PluginPermissions._assert_not_plugin_caller()

        records = _load_approvals()
        if plugin_uuid in records:
            del records[plugin_uuid]
            _save_approvals(records)
            return True
        return False

    @staticmethod
    def revoke_all() -> int:
        """
        Revoca todas las aprobaciones de plugins.

        Raises:
            PermissionError: Si la llamada proviene de un plugin.

        Returns:
            Número de aprobaciones revocadas.
        """
        PluginPermissions._assert_not_plugin_caller()

        records = _load_approvals()
        count = len(records)
        _save_approvals({})
        return count


# ---------------------------------------------------------------------------
# Función de guardado de permisos (para uso del gestor de plugins)
# ---------------------------------------------------------------------------

def require_approval(
    manifest: PluginManifest,
    security_issues: list | None = None,
    interactive: bool = True,
) -> None:
    """
    Punto de control de permisos invocado por el gestor de plugins antes de
    ejecutar cualquier código de un plugin.

    Si el plugin ya fue aprobado para la versión exacta actual, retorna
    inmediatamente. Si no, y ``interactive=True``, abre el diálogo de
    aprobación en consola. Si el usuario rechaza o ``interactive=False``,
    lanza :class:`PluginNotApprovedError`.

    Args:
        manifest: Manifiesto del plugin que solicita ejecución.
        security_issues: Hallazgos de seguridad a mostrar al usuario.
        interactive: Si False, lanza la excepción directamente sin preguntar.

    Raises:
        PluginNotApprovedError: Si el plugin no está aprobado.
    """
    if PluginPermissions.is_approved(manifest):
        return

    if interactive:
        approved = PluginPermissions.request_approval(manifest, security_issues)
        if not approved:
            raise PluginNotApprovedError(manifest.plugin_name, manifest.uuid, manifest.version_str)
    else:
        raise PluginNotApprovedError(manifest.plugin_name, manifest.uuid, manifest.version_str)


# ---------------------------------------------------------------------------
# Helpers internos de presentación
# ---------------------------------------------------------------------------

def _capabilities_list(manifest: PluginManifest) -> list[str]:
    """Construye la lista de capacidades activas de un manifest."""
    caps = manifest.capabilities
    active: list[str] = []
    if caps.load:
        active.append("load")
    if caps.process:
        active.append("process")
    if caps.cli:
        active.append("cli")
    return active


def _print_approval_prompt(manifest: PluginManifest, security_issues: list) -> None:
    """Imprime el resumen de aprobación de un plugin en consola."""
    sep = "─" * 60
    print(f"\n{sep}")
    print("  SOLICITUD DE APROBACIÓN DE PLUGIN")
    print(sep)
    print(f"  Nombre    : {manifest.plugin_name}")
    print(f"  Versión   : {manifest.version_str}")
    if manifest.description:
        print(f"  Descripción: {manifest.description}")
    if hasattr(manifest, "author") and manifest.author:
        print(f"  Autor     : {manifest.author}")
    print(f"  UUID      : {manifest.uuid}")

    caps = _capabilities_list(manifest)
    if caps:
        print(f"  Capacidades: {', '.join(caps)}")

    if manifest.requests:
        deps = ", ".join(req.name for req in manifest.requests)
        print(f"  Dependencias de plugins: {deps}")

    if manifest.python_lib_requests:
        libs = ", ".join(manifest.python_lib_requests.keys())
        print(f"  Librerías Python requeridas: {libs}")

    if security_issues:
        errors_count = sum(1 for i in security_issues if getattr(i, "level", "") == "ERROR")
        warnings_count = sum(1 for i in security_issues if getattr(i, "level", "") == "WARNING")
        print(f"\n  ⚠  AUDITORÍA DE SEGURIDAD: {errors_count} error(es), {warnings_count} advertencia(s)")
        for issue in security_issues[:5]:
            if hasattr(issue, "format_line"):
                print(f"     • {issue.format_line()}")
            else:
                print(f"     • {issue}")
        if len(security_issues) > 5:
            print(f"     ... y {len(security_issues) - 5} problema(s) más.")
    else:
        print("\n  ✔  Sin problemas de seguridad detectados en el análisis estático.")

    print(sep)
    print("  ADVERTENCIA: Solo apruebe plugins de fuentes de confianza.")
    print(sep)


__all__ = [
    "ApprovalRecord",
    "PluginNotApprovedError",
    "PluginPermissions",
    "require_approval",
]
