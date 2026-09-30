"""
Registro Central de Estado del Subsistema de Plugins de Gram.
=============================================================
Mantiene el estado compartido en tiempo de ejecución: plugins cargados,
orden de carga efectiva, detección de colisiones de identificadores y errores.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from gram.plugins.manager.core import Plugin


@dataclass
class CollisionInfo:
    """Describe una colisión de identificador entre dos plugins de Gram."""
    kind: str
    """Categoría: 'keyword' | 'rule_name' | 'rule_id' | 'combinator' | 'error'."""
    identifier: str
    """Nombre o código numérico del identificador en conflicto."""
    from_plugin: str
    """Plugin que registró el identificador primero (propietario original)."""
    to_plugin: str
    """Plugin que intentó reemplazar o duplicar el identificador."""
    resolved_by: str
    """Plugin cuyo registro quedó vigente tras resolver la colisión."""


# ---------------------------------------------------------------------------
# Estado global en memoria (un único ejemplar por proceso)
# ---------------------------------------------------------------------------
_registry: dict[str, Plugin] = {}
_load_order: list[str] = []
_loading_stack: set[str] = set()
_collisions: list[CollisionInfo] = []
_errors: dict[str, str] = {}
_current_loading_plugin: str | None = None


def set_current_loading(plugin_name: str | None) -> None:
    """Establece el nombre del plugin que está siendo cargado actualmente."""
    global _current_loading_plugin
    _current_loading_plugin = plugin_name


def get_current_loading() -> str | None:
    """Retorna el nombre del plugin que está siendo cargado en este momento."""
    return _current_loading_plugin


def record_load_order(plugin_name: str) -> None:
    """Registra un plugin como cargado exitosamente preservando el orden de carga."""
    if plugin_name not in _load_order:
        _load_order.append(plugin_name)


def get_load_order() -> list[str]:
    """Retorna una copia de la lista ordenada de plugins cargados."""
    return list(_load_order)


def record_collision(
    kind: str,
    identifier: str,
    from_plugin: str,
    to_plugin: str,
    resolved_by: str,
) -> None:
    """Registra una colisión de identificador entre dos plugins."""
    _collisions.append(
        CollisionInfo(
            kind=kind,
            identifier=identifier,
            from_plugin=from_plugin,
            to_plugin=to_plugin,
            resolved_by=resolved_by,
        )
    )


record_glang_collision = record_collision


def get_collisions() -> list[CollisionInfo]:
    """Retorna la lista de todas las colisiones detectadas."""
    return list(_collisions)


def record_error(plugin_name: str, message: str) -> None:
    """Registra un error de carga o inicialización asociado a un plugin."""
    _errors[plugin_name] = message


def get_errors() -> dict[str, str]:
    """Retorna el mapa de errores registrados por plugin."""
    return dict(_errors)


def register_plugin(plugin: Plugin) -> None:
    """
    Registra una instancia de Plugin en el catálogo central bajo sus identificadores:
    nombre, UUID y nombre de carpeta.
    """
    if plugin.name:
        _registry[plugin.name] = plugin
    if plugin.uuid:
        _registry[plugin.uuid] = plugin
    if plugin.plugin_path and plugin.plugin_path.name:
        _registry[plugin.plugin_path.name] = plugin


def unregister_plugin(name_or_uuid: str) -> None:
    """Elimina un plugin del registro activo."""
    plugin = _registry.pop(name_or_uuid, None)
    if plugin:
        if plugin.name in _registry:
            _registry.pop(plugin.name, None)
        if plugin.uuid in _registry:
            _registry.pop(plugin.uuid, None)
        if plugin.plugin_path and plugin.plugin_path.name in _registry:
            _registry.pop(plugin.plugin_path.name, None)
        if plugin.name in _load_order:
            _load_order.remove(plugin.name)


def get_plugin(name_or_uuid: str) -> Plugin | None:
    """Obtiene un plugin cargado desde el registro por su nombre o UUID."""
    return _registry.get(name_or_uuid)


def has_plugin(name_or_uuid: str) -> bool:
    """Verifica si un plugin está registrado y disponible."""
    return name_or_uuid in _registry


def all_plugins() -> list[Plugin]:
    """Retorna una lista con todas las instancias de Plugin registradas (sin duplicados)."""
    seen: set[str] = set()
    result: list[Plugin] = []
    for plugin in _registry.values():
        if plugin.name not in seen:
            seen.add(plugin.name)
            result.append(plugin)
    return result


def is_loading(plugin_name: str) -> bool:
    """Indica si un plugin se encuentra actualmente en proceso de resolución/carga."""
    return plugin_name in _loading_stack


def enter_loading(plugin_name: str) -> None:
    """Registra el inicio del ciclo de carga de un plugin para detección de ciclos."""
    _loading_stack.add(plugin_name)


def exit_loading(plugin_name: str) -> None:
    """Finaliza el ciclo de carga de un plugin liberando la pila de resolución."""
    _loading_stack.discard(plugin_name)


def clear() -> None:
    """
    Limpia completamente el estado de todos los plugins registrados.
    Útil en pruebas unitarias para garantizar aislamiento entre tests.
    """
    global _current_loading_plugin
    _registry.clear()
    _load_order.clear()
    _loading_stack.clear()
    _collisions.clear()
    _errors.clear()
    _current_loading_plugin = None


__all__ = [
    "CollisionInfo",
    "set_current_loading",
    "get_current_loading",
    "record_load_order",
    "get_load_order",
    "record_collision",
    "record_glang_collision",
    "get_collisions",
    "record_error",
    "get_errors",
    "register_plugin",
    "unregister_plugin",
    "get_plugin",
    "has_plugin",
    "all_plugins",
    "is_loading",
    "enter_loading",
    "exit_loading",
    "clear",
]
