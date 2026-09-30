"""
Sistema de Caché Centralizado de Gram (`gram.cachesystem.core`).
================================================================
Proporciona indexación, verificación de integridad y almacenamiento de metadatos
para plugins y componentes de Gram mediante hashes criptográficos SHA-256.

Permite:
- Calcular hashes deterministas del árbol de archivos de un plugin (tree_hash).
- Inspeccionar y resolver plugins SIN ejecutar su ciclo de vida (sin llamar a load()).
- Evitar reanálisis estáticos y verificaciones redundantes en instalaciones y actualizaciones.
- Detección precisa de archivos añadidos, modificados o eliminados.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from gram import config
from gram.plugins.validator import ValidationReport, should_ignore, validate_plugin


def get_cache_base_dir() -> Path:
    """
    Resuelve el directorio base del sistema de caché de Gram.

    Prioridad:
    1. config.CACHE_DIR
    2. Variable de entorno GRAM_CACHE
    3. Directorio por defecto: ~/.gram/cache
    """
    if getattr(config, "CACHE_DIR", None):
        p = Path(config.CACHE_DIR).expanduser().resolve()
    elif "GRAM_CACHE" in os.environ:
        p = Path(os.environ["GRAM_CACHE"]).expanduser().resolve()
    else:
        p = Path.home() / ".gram" / "cache"

    p.mkdir(parents=True, exist_ok=True)
    return p


def get_plugin_cache_dir() -> Path:
    """Retorna el subdirectorio de caché para plugins (~/.gram/cache/plugins)."""
    p = get_cache_base_dir() / "plugins"
    p.mkdir(parents=True, exist_ok=True)
    return p


def compute_file_hash(path: Path | str) -> str:
    """Calcula el hash SHA-256 de un archivo individual."""
    p = Path(path)
    if not p.exists() or not p.is_file():
        return ""

    sha = hashlib.sha256()
    try:
        with p.open("rb") as f:
            while chunk := f.read(65536):
                sha.update(chunk)
        return sha.hexdigest()
    except OSError:
        return ""


def compute_plugin_tree_hash(plugin_dir: Path | str) -> tuple[str, dict[str, str]]:
    """
    Calcula el hash determinista de todos los archivos del plugin,
    ignorando archivos temporales, binarios y artefactos volátiles.

    Returns:
        Tupla (tree_hash_sha256, diccionario {ruta_relativa_posix: sha256}).
    """
    root = Path(plugin_dir).resolve()
    if not root.exists() or not root.is_dir():
        return "", {}

    files_hashes: dict[str, str] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not should_ignore(d)]

        for f in filenames:
            if should_ignore(f):
                continue
            full_path = Path(dirpath) / f
            rel_path = full_path.relative_to(root).as_posix()
            f_hash = compute_file_hash(full_path)
            if f_hash:
                files_hashes[rel_path] = f_hash

    combined_sha = hashlib.sha256()
    for rel_p in sorted(files_hashes.keys()):
        combined_sha.update(rel_p.encode("utf-8"))
        combined_sha.update(b":")
        combined_sha.update(files_hashes[rel_p].encode("utf-8"))
        combined_sha.update(b"\n")

    return combined_sha.hexdigest(), files_hashes


@dataclass
class PluginCacheEntry:
    """Entrada persistente en el caché para un plugin validado e inspeccionado."""
    plugin_name: str
    uuid: str
    version: str
    tree_hash: str
    manifest_hash: str
    files_hashes: dict[str, str]
    inspected_at: float
    is_valid: bool
    dependencies_resolved: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PluginCacheEntry:
        return cls(
            plugin_name=data.get("plugin_name", ""),
            uuid=data.get("uuid", ""),
            version=data.get("version", ""),
            tree_hash=data.get("tree_hash", ""),
            manifest_hash=data.get("manifest_hash", ""),
            files_hashes=data.get("files_hashes", {}),
            inspected_at=data.get("inspected_at", 0.0),
            is_valid=data.get("is_valid", False),
            dependencies_resolved=data.get("dependencies_resolved", []),
        )

    def is_up_to_date(self, plugin_dir: Path | str) -> bool:
        """Verifica si los archivos del plugin coinciden exactamente con el caché."""
        curr_hash, _ = compute_plugin_tree_hash(plugin_dir)
        return bool(curr_hash and curr_hash == self.tree_hash)

    def diff_files(self, plugin_dir: Path | str) -> dict[str, list[str]]:
        """
        Compara los archivos actuales del plugin contra los registrados en el caché.

        Returns:
            Diccionario con listas: 'added', 'modified', 'deleted', 'unchanged'.
        """
        _, current_files = compute_plugin_tree_hash(plugin_dir)
        cached_files = self.files_hashes

        added = [f for f in current_files if f not in cached_files]
        deleted = [f for f in cached_files if f not in current_files]
        modified = [
            f for f in current_files
            if f in cached_files and current_files[f] != cached_files[f]
        ]
        unchanged = [
            f for f in current_files
            if f in cached_files and current_files[f] == cached_files[f]
        ]

        return {
            "added": sorted(added),
            "deleted": sorted(deleted),
            "modified": sorted(modified),
            "unchanged": sorted(unchanged),
        }


def save_plugin_cache(entry: PluginCacheEntry) -> Path:
    """Guarda la entrada de caché en el subdirectorio de caché de plugins."""
    cache_dir = get_plugin_cache_dir()
    identifier = f"{entry.plugin_name}_{entry.uuid}.json" if entry.uuid else f"{entry.plugin_name}.json"
    cache_file = cache_dir / identifier
    cache_file.write_text(json.dumps(entry.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return cache_file


def get_plugin_cache(plugin_name: str, uuid: str | None = None) -> PluginCacheEntry | None:
    """Obtiene una entrada de caché existente por nombre y/o UUID."""
    cache_dir = get_plugin_cache_dir()

    candidates: list[Path] = []
    if uuid:
        candidates.append(cache_dir / f"{plugin_name}_{uuid}.json")
    candidates.append(cache_dir / f"{plugin_name}.json")

    for cand in candidates:
        if cand.exists() and cand.is_file():
            try:
                data = json.loads(cand.read_text(encoding="utf-8"))
                return PluginCacheEntry.from_dict(data)
            except Exception:
                continue

    prefix = f"{plugin_name}_"
    for cand in cache_dir.glob(f"{prefix}*.json"):
        try:
            data = json.loads(cand.read_text(encoding="utf-8"))
            if not uuid or data.get("uuid") == uuid:
                return PluginCacheEntry.from_dict(data)
        except Exception:
            continue

    return None


def invalidate_plugin_cache(plugin_name: str, uuid: str | None = None) -> bool:
    """Elimina la entrada de caché asociada a un plugin."""
    cache_dir = get_plugin_cache_dir()
    removed = False

    targets = [cache_dir / f"{plugin_name}.json"]
    if uuid:
        targets.append(cache_dir / f"{plugin_name}_{uuid}.json")

    for cand in cache_dir.glob(f"{plugin_name}_*.json"):
        targets.append(cand)

    for target in targets:
        if target.exists():
            try:
                target.unlink()
                removed = True
            except OSError:
                pass

    return removed


def inspect_and_resolve_plugin(
    plugin_dir: Path | str,
    target_name: str | None = None,
    installed_plugins_dir: Path | None = None,
    use_cache: bool = True,
) -> tuple[ValidationReport, PluginCacheEntry | None]:
    """
    Inspecciona y resuelve estáticamente un plugin SIN ejecutar su ciclo de vida (no llama a load()).
    """
    path = Path(plugin_dir).resolve()
    tree_hash, files_hashes = compute_plugin_tree_hash(path)

    manifest_file = path / "manifest.json"
    manifest_hash = compute_file_hash(manifest_file) if manifest_file.exists() else ""

    if use_cache and tree_hash:
        cand_name = target_name or path.name
        if manifest_file.exists():
            try:
                raw_m = json.loads(manifest_file.read_text(encoding="utf-8"))
                cand_name = raw_m.get("plugin_name", cand_name)
                cand_uuid = raw_m.get("uuid", "")
            except Exception:
                cand_uuid = ""
        else:
            cand_uuid = ""

        cached = get_plugin_cache(cand_name, cand_uuid)
        if cached and cached.tree_hash == tree_hash and cached.is_valid:
            cached_report = ValidationReport(
                plugin_name=cached.plugin_name,
                source_dir=path,
                uuid=cached.uuid,
                incoming_version=cached.version,
                target_folder=target_name or path.name,
            )
            return cached_report, cached

    report = validate_plugin(path, target_name=target_name, installed_plugins_dir=installed_plugins_dir)

    if not report.is_valid:
        return report, None

    resolved_deps: list[str] = []
    if report.manifest and report.manifest.requests:
        for req in report.manifest.requests:
            c_name = req.canonical_name()
            local_dep = path / "versions" / c_name
            if local_dep.exists() and local_dep.is_dir():
                resolved_deps.append(f"{c_name} (local versions/)")
            elif installed_plugins_dir and (installed_plugins_dir / c_name).exists():
                resolved_deps.append(f"{c_name} (instalado en catálogo)")
            else:
                resolved_deps.append(f"{c_name} (pendiente)")

    entry = PluginCacheEntry(
        plugin_name=report.plugin_name,
        uuid=report.uuid,
        version=report.incoming_version or "1.0.0",
        tree_hash=tree_hash,
        manifest_hash=manifest_hash,
        files_hashes=files_hashes,
        inspected_at=time.time(),
        is_valid=True,
        dependencies_resolved=resolved_deps,
    )
    save_plugin_cache(entry)

    return report, entry


__all__ = [
    "PluginCacheEntry",
    "compute_file_hash",
    "compute_plugin_tree_hash",
    "get_cache_base_dir",
    "get_plugin_cache_dir",
    "get_plugin_cache",
    "save_plugin_cache",
    "invalidate_plugin_cache",
    "inspect_and_resolve_plugin",
]
