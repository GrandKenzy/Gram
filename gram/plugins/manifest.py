"""
Módulo de Especificación y Validación de Manifest para Plugins de Gram.
========================================================================
Define la estructura tipada PluginManifest, la resolución semántica de versiones
(soporte para listas [major, minor, patch] y cadenas semver), verificación de
dependencias de plugins y bibliotecas de Python, y reglas de compatibilidad OSGDC.
"""
from __future__ import annotations

import json
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from gram import config, errors
from gram.utilities import error


def generate_uuid(name: str | None = None) -> str:
    """
    Genera un identificador único global (UUID v4 o v5 determinista si se proporciona un nombre).

    Args:
        name: Nombre opcional para generar un UUID v5 reproducible.

    Returns:
        Cadena con el UUID formateado.
    """
    if name:
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, name))
    return str(uuid.uuid4())


def parse_version_tuple(value: Any) -> tuple[int, ...]:
    """
    Normaliza una representación de versión (lista, tupla, entero o cadena) a una tupla de enteros.

    Ejemplos:
        [1, 20, 3] -> (1, 20, 3)
        "1.20.3"   -> (1, 20, 3)
        "v2.1"     -> (2, 1)
        [3, 10]    -> (3, 10)
    """
    if isinstance(value, (list, tuple)):
        return tuple(int(x) for x in value if str(x).isdigit())

    if isinstance(value, int):
        return (value,)

    if isinstance(value, str):
        clean = value.strip().lstrip("vV")
        if not clean:
            return (0, 0, 0)
        parts = clean.split(".")
        result: list[int] = []
        for part in parts:
            digits = ""
            for ch in part:
                if ch.isdigit():
                    digits += ch
                else:
                    break
            result.append(int(digits) if digits else 0)
        return tuple(result) if result else (0, 0, 0)

    return (0, 0, 0)


def format_version(version: tuple[int, ...] | list[int] | str) -> str:
    """Convierte una versión en formato de tupla/lista a cadena separada por puntos."""
    if isinstance(version, str):
        return version.strip().lstrip("vV")
    if isinstance(version, (tuple, list)):
        return ".".join(str(x) for x in version)
    return str(version)


def parse_semver(version_str: str) -> tuple[int, int, int]:
    """Convierte una cadena de versión x.y.z en tupla de tres enteros (major, minor, patch)."""
    tup = parse_version_tuple(version_str)
    major = tup[0] if len(tup) > 0 else 0
    minor = tup[1] if len(tup) > 1 else 0
    patch = tup[2] if len(tup) > 2 else 0
    return major, minor, patch


def match_semver(target: str | tuple[int, ...], pattern: str | tuple[int, ...]) -> bool:
    """
    Comprueba si target satisface el patrón semver indicado.
    Soporta comodines 'x' o '*' (ej. '1.x.x', '1.2.x', '*'), operadores >=, y tuplas de versión.
    """
    target_str = format_version(target)
    pattern_str = format_version(pattern)

    target_clean = target_str.strip().lstrip("vV")
    pattern_clean = pattern_str.strip().lstrip("vV")

    # Comparación de operador >=
    if pattern_clean.startswith(">="):
        min_v = parse_semver(pattern_clean[2:])
        tgt_v = parse_semver(target_clean)
        return tgt_v >= min_v

    # Patrón wildcard global: cualquier versión es válida
    if pattern_clean in ("*", "x", ""):
        return True

    t_parts = target_clean.split(".")
    p_parts = pattern_clean.split(".")

    for i in range(max(len(t_parts), len(p_parts))):
        p_val = p_parts[i] if i < len(p_parts) else "0"
        t_val = t_parts[i] if i < len(t_parts) else "0"

        if p_val.lower() in ("x", "*"):
            continue

        try:
            if int(p_val) != int(t_val):
                return False
        except ValueError:
            if p_val != t_val:
                return False

    return True


@dataclass
class PluginCapabilities:
    """Capacidades declaradas y habilitadas por el plugin."""
    load: bool = True
    process: bool = True
    cli: bool = False
    replaceable: bool = True
    protect: int = 0  # 0: total, 1: id, 2: id+rules, 3: id+rules+comb, 4: all


@dataclass
class PluginDependency:
    """Requisito de dependencia entre plugins de Gram."""
    name: str
    min_version: tuple[int, ...] = (1, 0, 0)
    min_version_str: str = "1.0.0"
    install: bool = False

    def canonical_name(self) -> str:
        """Resuelve el nombre canónico del plugin requerido."""
        if self.name in ("ESSENCIAL_PACK", "GRAM_ESSENCIAL_PACK"):
            return "GRAM_ESSENCIAL_PACK"
        if self.name.startswith("plugins."):
            return self.name[len("plugins."):]
        return self.name


@dataclass
class PluginManifest:
    """
    Estructura tipada y validada de la especificación manifest.json para plugins de Gram.
    """
    plugin_name: str
    version: tuple[int, ...]
    version_str: str
    min_engine: tuple[int, ...]
    min_engine_str: str
    min_python_version: tuple[int, ...]
    author: str = ""
    description: str = ""
    short: str = ""
    license: str | None = None
    license_file: str | None = None
    main: str = "main.py"
    colors: str | None = None
    capabilities: PluginCapabilities = field(default_factory=PluginCapabilities)
    config_requests: dict[str, Any] = field(default_factory=dict)
    python_lib_requests: dict[str, tuple[int, ...]] = field(default_factory=dict)
    requests: list[PluginDependency] = field(default_factory=list)
    controls: dict[str, list[str]] = field(default_factory=dict)
    sites: dict[str, str] = field(default_factory=dict)
    type: str = "extendable"
    use_venv: bool = True
    version_state: str = "Stable"
    uuid: str = ""
    icon: str | None = None
    tags: list[str] = field(default_factory=list)
    schema: str | None = None
    manifest_path: Path | None = None


def parse_manifest(
    manifest_path: Path | str,
    expected_folder_name: str | None = None,
) -> PluginManifest:
    """
    Lee, parsea y valida exhaustivamente un archivo manifest.json.
    Aplica las reglas de compatibilidad de Gram y políticas OSGDC.

    Args:
        manifest_path: Ruta al archivo manifest.json.
        expected_folder_name: Nombre esperado del directorio contenedor para validación.

    Returns:
        Instancia validada de PluginManifest.
    """
    path = Path(manifest_path).resolve()
    if not path.exists() or not path.is_file():
        error.GrammarError(
            "Manifiesto no encontrado",
            errors.PLUGIN_MANIFEST_NOT_FOUND,
            f"No se encontró el archivo de manifiesto en: {path}",
            "Cada plugin de Gram debe contar con un manifest.json al mismo nivel que su código.",
        ).raise_error()

    try:
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        error.GrammarError(
            "Sintaxis de manifiesto inválida",
            errors.PLUGIN_MANIFEST_INVALID,
            f"Error al analizar sintácticamente manifest.json: {exc}",
            "Verifique que el archivo manifest.json contenga una estructura JSON válida.",
        ).raise_error()

    if not isinstance(data, dict):
        error.GrammarError(
            "Estructura de manifiesto inválida",
            errors.PLUGIN_MANIFEST_INVALID,
            "El archivo manifest.json debe contener un objeto JSON en su raíz.",
        ).raise_error()

    # 1. plugin_name
    plugin_name = data.get("plugin_name")
    if not plugin_name or not isinstance(plugin_name, str) or not plugin_name.strip():
        error.GrammarError(
            "Nombre de plugin no especificado",
            errors.PLUGIN_MANIFEST_INVALID,
            "El manifest.json debe definir 'plugin_name' como una cadena de texto no vacía.",
            "Asegúrese de incluir 'plugin_name' en el JSON.",
        ).raise_error()
    plugin_name = plugin_name.strip()

    # 2. author, description, short
    author = str(data.get("author", "")).strip()
    description = str(data.get("description", "")).strip()
    short = str(data.get("short", "")).strip()

    # 3. version
    version_raw = data.get("version")
    if version_raw is None:
        error.GrammarError(
            "Versión de plugin no especificada",
            errors.PLUGIN_MANIFEST_INVALID,
            f"El manifest.json de '{plugin_name}' debe definir 'version'.",
            "Indique 'version' como una lista [major, minor, patch] o cadena 'x.y.z'.",
        ).raise_error()
    version = parse_version_tuple(version_raw)
    version_str = format_version(version_raw)

    # 4. min_engine
    min_engine_raw = data.get("min_engine", "1.0.0")
    min_engine = parse_version_tuple(min_engine_raw)
    min_engine_str = format_version(min_engine_raw)

    # 5. min_python_version
    min_python_raw = data.get("min_python_version", [3, 10])
    min_python = parse_version_tuple(min_python_raw)

    # 6. license y license_file
    license_val = data.get("license")
    license_file = data.get("license_file")

    # 7. main
    main_entry = str(data.get("main", "main.py")).strip()

    # 8. colors
    colors_file = data.get("colors")

    # 9. capabilities
    cap_data = data.get("capabilities", {})
    if not isinstance(cap_data, dict):
        cap_data = {}
    capabilities = PluginCapabilities(
        load=bool(cap_data.get("load", True)),
        process=bool(cap_data.get("process", True)),
        cli=bool(cap_data.get("cli", False)),
        replaceable=bool(cap_data.get("replaceable", True)),
        protect=int(cap_data.get("protect", 0)),
    )

    # 10. config_requests
    config_reqs = data.get("config_requests", {})
    if not isinstance(config_reqs, dict):
        config_reqs = {}

    # 11. python_lib_requests
    py_lib_reqs: dict[str, tuple[int, ...]] = {}
    raw_libs = data.get("python_lib_requests", {})
    if isinstance(raw_libs, dict):
        for lib_name, lib_ver in raw_libs.items():
            py_lib_reqs[str(lib_name)] = parse_version_tuple(lib_ver)

    # 12. requests (dependencias de plugins)
    plugin_reqs: list[PluginDependency] = []
    raw_reqs = data.get("requests", [])
    if isinstance(raw_reqs, list):
        for req_item in raw_reqs:
            if isinstance(req_item, dict):
                r_name = str(req_item.get("name", "")).strip()
                if r_name:
                    r_ver = req_item.get("min_version", "1.0.0")
                    plugin_reqs.append(
                        PluginDependency(
                            name=r_name,
                            min_version=parse_version_tuple(r_ver),
                            min_version_str=format_version(r_ver),
                            install=bool(req_item.get("install", False)),
                        )
                    )
            elif isinstance(req_item, str) and req_item.strip():
                plugin_reqs.append(
                    PluginDependency(
                        name=req_item.strip(),
                        min_version=(1, 0, 0),
                        min_version_str="1.0.0",
                    )
                )

    # 13. uuid
    plugin_uuid = data.get("uuid")
    if not plugin_uuid:
        plugin_uuid = generate_uuid(plugin_name)
    else:
        plugin_uuid = str(plugin_uuid).strip()

    # 14. tags
    tags = [str(t) for t in data.get("tags", []) if isinstance(t, (str, int))]

    manifest = PluginManifest(
        plugin_name=plugin_name,
        version=version,
        version_str=version_str,
        min_engine=min_engine,
        min_engine_str=min_engine_str,
        min_python_version=min_python,
        author=author,
        description=description,
        short=short,
        license=str(license_val) if license_val else None,
        license_file=str(license_file) if license_file else None,
        main=main_entry,
        colors=str(colors_file) if colors_file else None,
        capabilities=capabilities,
        config_requests=config_reqs,
        python_lib_requests=py_lib_reqs,
        requests=plugin_reqs,
        controls=data.get("controls", {}),
        sites=data.get("sites", {}),
        type=str(data.get("type", "extendable")),
        use_venv=bool(data.get("use_venv", True)),
        version_state=str(data.get("version_state", "Stable")),
        uuid=plugin_uuid,
        icon=data.get("icon"),
        tags=tags,
        schema=data.get("$schema"),
        manifest_path=path,
    )

    return manifest


__all__ = [
    "PluginCapabilities",
    "PluginDependency",
    "PluginManifest",
    "generate_uuid",
    "parse_version_tuple",
    "format_version",
    "parse_semver",
    "match_semver",
    "parse_manifest",
]
