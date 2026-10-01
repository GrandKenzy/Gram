"""
Módulo de Soporte VSIX y Carga de Extensiones para GLANG (`gram.glang.vsix`).
=============================================================================
Gestiona la generación, instalación y desinstalación de extensiones VS Code
específicas para GLANG (.glang).

Soporta la extensión dinámica mediante archivos `*.glang.py` o `.glang.py`
alojados en plugins de Gram. Cualquier error en un plugin es capturado de
forma segura y el plugin es ignorado para evitar bloqueos o fallos de compilación.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from typing import Any

from gram.plugins.manager.core import get_plugins_dir
from gram.glang.keywords import register_glang_keywords
import gram.vsix as vsix


def discover_glang_plugin_files() -> list[tuple[str, Path]]:
    """
    Busca archivos de extensión `*.glang.py` o `.glang.py` en:
      1. Directorio de plugins fuente oficiales (`gram/plugins/source/`).
      2. Directorio de plugins instalados en el sistema (`get_plugins_dir()`).
      3. Directorio de datos locales (`data/.cache/plugins/`).
    """
    found_files: list[tuple[str, Path]] = []
    seen_paths: set[Path] = set()

    search_dirs: list[Path] = []

    # 1. Plugins fuente oficiales empaquetados con Gram
    source_plugins_dir = Path(__file__).resolve().parent.parent / "plugins" / "source"
    if source_plugins_dir.is_dir():
        search_dirs.append(source_plugins_dir)

    # 2. Plugins instalados en el catálogo de Gram
    try:
        catalog_dir = get_plugins_dir()
        if catalog_dir.is_dir():
            search_dirs.append(catalog_dir)
    except Exception:
        pass

    # 3. Directorio de caché local data/.cache/plugins
    cwd_data = Path.cwd() / "data" / ".cache" / "plugins"
    if cwd_data.is_dir() and cwd_data not in search_dirs:
        search_dirs.append(cwd_data)

    for base_dir in search_dirs:
        if not base_dir.exists():
            continue

        # Cada subdirectorio es un plugin
        for plugin_item in base_dir.iterdir():
            if not plugin_item.is_dir():
                continue
            plugin_name = plugin_item.name

            # Buscar archivos *.glang.py y .glang.py recursivamente en el plugin
            for entry in plugin_item.rglob("*.py"):
                name = entry.name
                if name.endswith(".glang.py") or name == ".glang.py" or name == "glang.py":
                    resolved = entry.resolve()
                    if resolved not in seen_paths:
                        seen_paths.add(resolved)
                        found_files.append((plugin_name, resolved))

    return found_files


def load_glang_extension_file(plugin_name: str, file_path: Path) -> dict[str, Any]:
    """
    Carga de forma aislada y segura un archivo de extensión `*.glang.py`.
    Si ocurre cualquier error (sintáctico, de importación o de ejecución),
    captura la excepción e ignora el plugin para no congelar ni romper el generador.
    """
    result: dict[str, Any] = {
        "plugin": plugin_name,
        "file": str(file_path),
        "loaded": False,
        "error": None,
        "keywords_added": 0,
    }

    try:
        # Generar un nombre único de módulo para evitar colisiones
        module_name = f"gram_glang_ext_{plugin_name}_{file_path.stem.replace('.', '_')}"
        spec = importlib.util.spec_from_file_location(module_name, str(file_path))
        if spec is None or spec.loader is None:
            result["error"] = "No se pudo crear el cargador de módulo"
            print(f"[AVISO GLANG] Plugin '{plugin_name}': cargador no válido para '{file_path.name}'. Ignorado.")
            return result

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module

        # Ejecutar el módulo
        spec.loader.exec_module(module)

        # Si el módulo define funciones de inicialización conocidas, invocarlas
        for hook_name in ("setup_glang", "register_glang", "setup", "register"):
            hook = getattr(module, hook_name, None)
            if callable(hook):
                try:
                    hook()
                except Exception as hook_exc:
                    print(f"[AVISO GLANG] Plugin '{plugin_name}': error en hook '{hook_name}': {hook_exc}. Continuando.")

        # Registrar palabras clave explícitas si el módulo las expone
        explicit_kws = getattr(module, "GLANG_KEYWORDS", None)
        if isinstance(explicit_kws, dict):
            from gram.core.lexer.words import add_keyword
            for kw, color in explicit_kws.items():
                try:
                    add_keyword(kw, hex_color=color if isinstance(color, str) else "#FFFFFF", allow_override=True)
                    result["keywords_added"] += 1
                except Exception:
                    pass

        result["loaded"] = True
        return result

    except Exception as exc:
        result["error"] = str(exc)
        print(f"[AVISO GLANG] Plugin '{plugin_name}': error al implementar '{file_path.name}': {exc}. Plugin ignorado.")
        return result


def load_all_glang_extensions() -> list[dict[str, Any]]:
    """
    Descubre y carga todas las extensiones `*.glang.py` disponibles en plugins.
    """
    found = discover_glang_plugin_files()
    reports: list[dict[str, Any]] = []

    for plugin_name, file_path in found:
        report = load_glang_extension_file(plugin_name, file_path)
        reports.append(report)

    return reports


def generate_glang_vsix(
    output_path: str | Path | None = None,
    force: bool = True,
    install_after: bool = False,
    compiler_path: str = "",
    compiler_args: list[str] | None = None,
) -> Path:
    """
    Genera el paquete VSIX de VS Code configurado para GLANG (.glang).
    Carga de forma resiliente todas las extensiones `*.glang.py` de plugins.
    """
    # 1. Registrar palabras clave base de GLang
    register_glang_keywords()

    # 2. Cargar extensiones de plugins (*.glang.py) con tolerancia total a fallos
    ext_reports = load_all_glang_extensions()
    loaded_count = sum(1 for r in ext_reports if r["loaded"])
    ignored_count = len(ext_reports) - loaded_count

    print(f"[INFO GLANG] Extensiones .glang.py detectadas: {len(ext_reports)} (Cargadas: {loaded_count}, Ignoradas: {ignored_count})")

    # 3. Compilar el paquete VSIX con soporte de extensión .glang
    target_vsix = vsix.compile(
        output_path=output_path,
        force=force,
        custom_extensions=[".glang", ".g"],
        compiler_path=compiler_path,
        compiler_args=compiler_args,
    )

    # 4. Si se solicitó instalación inmediata
    if install_after:
        ok, msg = vsix.install(target_vsix)
        if ok:
            print(f"[OK GLANG] Extensión VSIX instalada en VS Code: {msg}")
        else:
            print(f"[ERROR GLANG] Falló la instalación en VS Code: {msg}")

    return target_vsix


def install_glang_vsix(vsix_file: str | Path | None = None) -> tuple[bool, str]:
    """
    Instala la extensión VSIX de GLANG en Visual Studio Code.
    Si no existe un archivo compilado, lo genera primero.
    """
    if vsix_file is None:
        active = vsix.get_active_vsix()
        if active and Path(active).is_file():
            target_file = Path(active)
        else:
            print("[INFO GLANG] Generando extensión VSIX antes de instalar...")
            target_file = generate_glang_vsix(force=True)
    else:
        target_file = Path(vsix_file).resolve()
        if not target_file.is_file():
            print(f"[INFO GLANG] Archivo '{target_file}' no encontrado. Compilando extensión...")
            target_file = generate_glang_vsix(output_path=target_file, force=True)

    return vsix.install(target_file)


def uninstall_glang_vsix() -> tuple[bool, str]:
    """
    Desinstala la extensión de GLANG de Visual Studio Code.
    """
    return vsix.uninstall()


__all__ = [
    "discover_glang_plugin_files",
    "load_glang_extension_file",
    "load_all_glang_extensions",
    "generate_glang_vsix",
    "install_glang_vsix",
    "uninstall_glang_vsix",
]
