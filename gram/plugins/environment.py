"""
Gestión del Entorno de Ejecución Aislado para Plugins de Gram.
==============================================================
Proporciona:
  1. Entorno virtual (venv) dedicado a Gram, sin contaminar el Python global.
  2. Instalación de dependencias Python requeridas por plugins, con validación
     de lista blanca aprobada por el usuario final.
  3. Directorios de datos, temporales y caché privados por plugin.
  4. API de lista blanca de librerías: solo el usuario final puede modificarla.
"""
from __future__ import annotations

import importlib
import json
import os
import shutil
import subprocess
import sys
import venv
from pathlib import Path
from typing import TYPE_CHECKING, Any

from gram import config

if TYPE_CHECKING:
    from gram.plugins.manifest import PluginManifest


# ---------------------------------------------------------------------------
# Helpers de rutas del venv
# ---------------------------------------------------------------------------

def get_path() -> Path:
    """
    Ruta absoluta al directorio del entorno virtual dedicado de Gram.

    Prioridad:
      1. ``config.ENVIRONMENT_DIR`` (si está configurado).
      2. Variable de entorno ``GRAM_ENV``.
      3. ``~/.gram/env`` por defecto.
    """
    env_dir = getattr(config, "ENVIRONMENT_DIR", None)
    if env_dir:
        return Path(env_dir).resolve()

    env_var = os.environ.get("GRAM_ENV")
    if env_var:
        return Path(env_var).resolve()

    return (Path.home() / ".gram" / "env").resolve()


def get_python_executable() -> Path:
    """Binario ``python`` dentro del venv de Gram."""
    env_dir = get_path()
    if sys.platform == "win32":
        return env_dir / "Scripts" / "python.exe"
    return env_dir / "bin" / "python"


def get_pip_executable() -> Path:
    """Binario ``pip`` dentro del venv de Gram."""
    env_dir = get_path()
    if sys.platform == "win32":
        return env_dir / "Scripts" / "pip.exe"
    return env_dir / "bin" / "pip"


def get_site_packages() -> Path | None:
    """Ruta al directorio ``site-packages`` del venv de Gram."""
    env_dir = get_path()
    if sys.platform == "win32":
        sp = env_dir / "Lib" / "site-packages"
        return sp if sp.exists() else None
    lib_dir = env_dir / "lib"
    if lib_dir.exists():
        for child in lib_dir.iterdir():
            if child.is_dir() and child.name.startswith("python"):
                sp = child / "site-packages"
                if sp.exists():
                    return sp
    return None


# ---------------------------------------------------------------------------
# Ciclo de vida del venv
# ---------------------------------------------------------------------------

def is_created() -> bool:
    """Retorna True si el venv de Gram ya existe con un Python válido."""
    py = get_python_executable()
    return py.exists() and py.is_file()


def is_active() -> bool:
    """Retorna True si el proceso actual corre dentro del venv de Gram."""
    try:
        return Path(sys.prefix).resolve() == get_path()
    except Exception:
        return False


def create(force: bool = False, with_pip: bool = True) -> Path:
    """
    Crea el venv dedicado de Gram.

    Args:
        force: Si True, borra y recrea cualquier venv previo.
        with_pip: Asegura la presencia de ``pip``.

    Returns:
        Ruta al directorio del venv creado.
    """
    env_dir = get_path()
    env_dir.parent.mkdir(parents=True, exist_ok=True)

    if force and env_dir.exists():
        try:
            shutil.rmtree(env_dir)
        except OSError:
            pass

    venv.EnvBuilder(
        system_site_packages=False,
        clear=force,
        symlinks=False,
        with_pip=with_pip,
    ).create(str(env_dir))

    return env_dir


def ensure() -> Path:
    """Garantiza que el venv exista, creándolo si es necesario."""
    if not is_created():
        return create(force=False, with_pip=True)
    return get_path()


def activate() -> bool:
    """
    Inyecta ``site-packages`` del venv en ``sys.path`` del proceso actual,
    permitiendo que los plugins importen sus dependencias instaladas.

    Returns:
        True si el path fue añadido exitosamente.
    """
    sp = get_site_packages()
    if sp is None:
        ensure()
        sp = get_site_packages()

    if sp is not None and sp.exists():
        sp_str = str(sp.resolve())
        if sp_str not in sys.path:
            sys.path.insert(0, sp_str)
        importlib.invalidate_caches()
        return True
    return False


def reset(install_base: bool = True) -> bool:
    """
    Reinicia el venv de Gram a su estado limpio inicial.

    Args:
        install_base: Si True, instala ``setuptools`` y ``wheel`` tras recrear.

    Returns:
        True si el proceso concluyó sin errores.
    """
    create(force=True, with_pip=True)
    pip_exe = get_pip_executable()
    if not pip_exe.exists():
        return False

    if install_base:
        base_pkgs = list(getattr(config, "ENVIRONMENT_BASE_REQUIREMENTS", ["setuptools", "wheel"]))
        if base_pkgs:
            subprocess.run(
                [str(pip_exe), "install", "--upgrade"] + base_pkgs,
                capture_output=True,
                text=True,
            )

    activate()
    return True


# ---------------------------------------------------------------------------
# Instalación y gestión de paquetes
# ---------------------------------------------------------------------------

def install(
    *packages: str,
    requirements_file: str | Path | None = None,
    upgrade: bool = False,
) -> bool:
    """
    Instala paquetes dentro del venv de Gram.

    Args:
        packages: Especificaciones de paquetes (p.ej. ``'numpy>=1.20'``).
        requirements_file: Ruta opcional a un ``requirements.txt``.
        upgrade: Si True, añade ``--upgrade`` al comando pip.

    Returns:
        True si la instalación fue exitosa.
    """
    ensure()
    pip_exe = get_pip_executable()
    if not pip_exe.exists():
        return False

    cmd: list[str] = [str(pip_exe), "install"]
    if upgrade:
        cmd.append("--upgrade")

    if requirements_file:
        rf = Path(requirements_file).resolve()
        if not rf.exists():
            return False
        cmd.extend(["-r", str(rf)])

    if packages:
        cmd.extend(list(packages))

    if len(cmd) == 2:
        return True

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        activate()
        return True
    return False


def update(*packages: str) -> bool:
    """
    Actualiza paquetes específicos en el venv de Gram (o los paquetes base si no se especifica ninguno).

    Returns:
        True si la actualización fue exitosa.
    """
    ensure()
    pip_exe = get_pip_executable()
    if not pip_exe.exists():
        return False

    targets = (
        list(packages)
        if packages
        else ["pip"] + list(getattr(config, "ENVIRONMENT_BASE_REQUIREMENTS", ["setuptools", "wheel"]))
    )

    result = subprocess.run(
        [str(pip_exe), "install", "--upgrade"] + targets,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        activate()
        return True
    return False


def reinstall(*packages: str) -> bool:
    """
    Reinstala paquetes en el venv forzando reconstrucción sin caché.
    Si no se especifican paquetes, reinicia completamente el venv.

    Returns:
        True si la operación fue exitosa.
    """
    if not packages:
        return reset(install_base=True)

    ensure()
    pip_exe = get_pip_executable()
    if not pip_exe.exists():
        return False

    result = subprocess.run(
        [str(pip_exe), "install", "--force-reinstall", "--no-cache-dir"] + list(packages),
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        activate()
        return True
    return False


def uninstall(*packages: str, yes: bool = True) -> bool:
    """
    Desinstala paquetes del venv de Gram.

    Args:
        packages: Nombres de paquetes a desinstalar.
        yes: Si True, omite la confirmación interactiva.

    Returns:
        True si la desinstalación fue exitosa.
    """
    if not is_created() or not packages:
        return False

    pip_exe = get_pip_executable()
    if not pip_exe.exists():
        return False

    cmd = [str(pip_exe), "uninstall"]
    if yes:
        cmd.append("-y")
    cmd.extend(list(packages))

    result = subprocess.run(cmd, capture_output=True, text=True)
    importlib.invalidate_caches()
    return result.returncode == 0


def run(
    command_or_args: list[str] | str,
    capture_output: bool = True,
    **kwargs: Any,
) -> subprocess.CompletedProcess[str]:
    """
    Ejecuta código o scripts dentro del venv de Gram.

    Args:
        command_or_args: Código Python (cadena, ejecutado con ``-c``) o lista de argumentos.
        capture_output: Si True, captura stdout y stderr.

    Returns:
        ``subprocess.CompletedProcess`` con los resultados.
    """
    ensure()
    py_exe = get_python_executable()

    if isinstance(command_or_args, str):
        cmd = [str(py_exe), "-c", command_or_args]
    else:
        cmd = [str(py_exe)] + list(command_or_args)

    return subprocess.run(cmd, capture_output=capture_output, text=True, **kwargs)


def list_packages() -> dict[str, str]:
    """
    Retorna un mapeo ``{nombre: versión}`` de los paquetes instalados en el venv.
    """
    if not is_created():
        return {}

    pip_exe = get_pip_executable()
    if not pip_exe.exists():
        return {}

    result = subprocess.run(
        [str(pip_exe), "list", "--format=json"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return {}

    try:
        data = json.loads(result.stdout)
        return {item["name"]: item["version"] for item in data}
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Lista blanca de librerías permitidas para plugins
# ---------------------------------------------------------------------------

_DEFAULT_ALLOWED_LIBRARIES: frozenset[str] = frozenset({
    # Módulos estándar de uso común y seguro
    "math",
    "typing",
    "pathlib",
    "copy",
    "json",
    "wave",
    "mmap",
    # Librerías de terceros populares explícitamente permitidas por defecto
    "pillow",
    "pil",
})

_allowed_libraries: set[str] = set(_DEFAULT_ALLOWED_LIBRARIES)


def allow_list() -> list[str]:
    """Retorna la lista ordenada de librerías permitidas para plugins."""
    return sorted(_allowed_libraries)


def allow_add(*names: str) -> None:
    """
    Añade librerías a la lista blanca de plugins.

    Solo puede ser invocado por el usuario final (``__main__`` o scripts
    principales). Los plugins tienen terminantemente prohibido llamar esta función.

    Raises:
        PluginError: Si un plugin activo intenta modificar la lista blanca.
    """
    from gram import errors
    from gram.plugins import registry as _registry
    from gram.utilities import error

    active_plugin = _registry.get_current_loading()
    if active_plugin is not None:
        error.PluginError(
            "Modificación de lista blanca denegada",
            errors.PLUGIN_CONFIG_MUTATION_DENIED,
            f"El plugin '{active_plugin}' intentó modificar la lista de librerías permitidas con allow_add().",
            "Solo el usuario final puede modificar la lista blanca de librerías.",
        ).raise_error()

    for name in names:
        clean = name.strip().lower()
        if clean:
            _allowed_libraries.add(clean)
            # Alias automáticos
            if clean == "pillow":
                _allowed_libraries.add("pil")
            elif clean == "wave":
                _allowed_libraries.add("wav")


def allow_remove(*names: str) -> None:
    """
    Remueve librerías de la lista blanca de plugins.

    Solo puede ser invocado por el usuario final.

    Raises:
        PluginError: Si un plugin activo intenta modificar la lista blanca.
    """
    from gram import errors
    from gram.plugins import registry as _registry
    from gram.utilities import error

    active_plugin = _registry.get_current_loading()
    if active_plugin is not None:
        error.PluginError(
            "Modificación de lista blanca denegada",
            errors.PLUGIN_CONFIG_MUTATION_DENIED,
            f"El plugin '{active_plugin}' intentó modificar la lista de librerías permitidas con allow_remove().",
            "Solo el usuario final puede modificar la lista blanca de librerías.",
        ).raise_error()

    for name in names:
        clean = name.strip().lower()
        _allowed_libraries.discard(clean)
        if clean == "pillow":
            _allowed_libraries.discard("pil")
        elif clean == "wave":
            _allowed_libraries.discard("wav")


def is_library_allowed(name: str) -> bool:
    """
    Comprueba si una librería está en la lista blanca.

    ``gram`` y ``__future__`` siempre están permitidos.
    La comprobación se realiza contra el nombre raíz del módulo
    (p.ej. ``'numpy.linalg'`` → ``'numpy'``).
    """
    root = name.strip().lower().split(".")[0]
    if root in ("gram", "__future__"):
        return True
    return root in _allowed_libraries


def reset_allowed_libraries() -> None:
    """Restaura la lista blanca a sus valores por defecto."""
    _allowed_libraries.clear()
    _allowed_libraries.update(_DEFAULT_ALLOWED_LIBRARIES)


# ---------------------------------------------------------------------------
# Directorios de almacenamiento por plugin
# ---------------------------------------------------------------------------

def get_data_base_dir() -> Path:
    """Directorio base de almacenamiento persistente de plugins."""
    p = Path(getattr(config, "DATA_DIR", None) or (Path.home() / ".gram" / "data")).resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_temp_base_dir() -> Path:
    """Directorio base de archivos temporales de plugins."""
    p = Path(getattr(config, "TEMP_DIR", None) or (Path.home() / ".gram" / "temp")).resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_plugin_data_dir(plugin_name: str, plugin_uuid: str = "") -> Path:
    """
    Retorna (y crea si no existe) el directorio de datos persistentes de un plugin.

    El directorio es privado para ``plugin_name`` + ``plugin_uuid``.
    """
    folder = f"{plugin_name}_{plugin_uuid}".strip("_")
    p = get_data_base_dir() / folder
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_plugin_temp_dir(plugin_name: str, plugin_uuid: str = "") -> Path:
    """
    Retorna (y crea si no existe) el directorio temporal de un plugin.
    """
    folder = f"{plugin_name}_{plugin_uuid}".strip("_")
    p = get_temp_base_dir() / folder
    p.mkdir(parents=True, exist_ok=True)
    return p


def clean_temp(plugin_name: str | None = None) -> int:
    """
    Elimina archivos temporales de plugins.

    Args:
        plugin_name: Si se especifica, solo limpia los temporales de ese plugin.

    Returns:
        Número de entradas eliminadas.
    """
    base = get_temp_base_dir()
    if not base.exists():
        return 0

    count = 0
    for item in list(base.iterdir()):
        if plugin_name is not None and not item.name.startswith(plugin_name):
            continue
        try:
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
            count += 1
        except OSError:
            pass

    return count


def clean_cache(plugin_name: str | None = None) -> int:
    """
    Elimina entradas de caché de plugins.

    Args:
        plugin_name: Si se especifica, solo limpia la caché de ese plugin.

    Returns:
        Número de archivos de caché eliminados.
    """
    cache_dir = Path(
        getattr(config, "CACHE_DIR", None) or (Path.home() / ".gram" / "cache" / "plugins")
    ).resolve()

    if not cache_dir.exists():
        return 0

    count = 0
    for item in list(cache_dir.glob("*.json")):
        if plugin_name is not None and not item.stem.startswith(plugin_name):
            continue
        try:
            item.unlink()
            count += 1
        except OSError:
            pass

    return count


def clean_data(plugin_name: str) -> bool:
    """
    Elimina el directorio de datos persistentes de un plugin.

    Returns:
        True si se eliminó al menos un directorio de datos.
    """
    if not plugin_name:
        return False

    base = get_data_base_dir()
    if not base.exists():
        return False

    removed = False
    for item in list(base.iterdir()):
        if item.is_dir() and item.name.startswith(plugin_name):
            try:
                shutil.rmtree(item)
                removed = True
            except OSError:
                pass

    return removed


# ---------------------------------------------------------------------------
# Instalación de dependencias declaradas en manifests
# ---------------------------------------------------------------------------

def install_plugin_requirements(manifest: PluginManifest) -> bool:
    """
    Instala en el venv de Gram las dependencias Python declaradas en un
    ``PluginManifest``, respetando la política de lista blanca y el flag
    ``config.PLUGIN_ALLOW_PYTHON_INSTALL_LIBS``.

    Args:
        manifest: Manifiesto del plugin a procesar.

    Returns:
        True si todas las dependencias fueron instaladas correctamente.

    Raises:
        PluginError: Si alguna librería no está en la lista blanca o la
                     instalación de librerías está deshabilitada en config.
    """
    from gram import errors
    from gram.utilities import error

    ensure()
    activate()

    specs: list[str] = []

    # 1. Auditar y preparar python_lib_requests del manifest
    for lib_name, ver_tuple in manifest.python_lib_requests.items():
        root = lib_name.strip().lower().split(".")[0]

        # Stdlib segura: no requiere instalación pip
        _safe_stdlib = {
            "sys", "os", "math", "json", "pathlib", "copy",
            "typing", "dataclasses", "collections", "itertools",
            "functools", "abc", "enum", "re",
        }
        if root in _safe_stdlib:
            continue

        if not is_library_allowed(root):
            error.PluginError(
                "Librería no permitida",
                errors.PLUGIN_PROTECTED_VIOLATION,
                f"El plugin '{manifest.plugin_name}' requiere '{lib_name}', que no está en la lista blanca.",
                f"Librerías permitidas: {allow_list()}.",
            ).raise_error()

        if ver_tuple:
            ver_str = ".".join(str(x) for x in ver_tuple)
            specs.append(f"{lib_name}>={ver_str}")
        else:
            specs.append(lib_name)

    # 2. Procesar requirements.txt junto al manifest.json
    req_file: Path | None = None
    if manifest.manifest_path:
        candidate = manifest.manifest_path.parent / "requirements.txt"
        if candidate.exists() and candidate.is_file():
            req_file = candidate

    if not specs and req_file is None:
        return True

    # 3. Verificar política de instalación
    allow_install = getattr(config, "PLUGIN_ALLOW_PYTHON_INSTALL_LIBS", False) or getattr(
        config, "PLUGINS_ALLOW_ALL_PLUGINS", False
    )
    if not allow_install:
        error.PluginError(
            "Instalación de librerías Python denegada",
            errors.PLUGIN_CONFIG_MUTATION_DENIED,
            f"El plugin '{manifest.plugin_name}' requiere instalar {specs}, "
            f"pero 'config.PLUGIN_ALLOW_PYTHON_INSTALL_LIBS' está en False.",
            "Active 'config.PLUGIN_ALLOW_PYTHON_INSTALL_LIBS = True' para permitirlo.",
        ).raise_error()

    return install(*specs, requirements_file=req_file)


__all__ = [
    # Rutas del venv
    "get_path",
    "get_python_executable",
    "get_pip_executable",
    "get_site_packages",
    # Estado del venv
    "is_created",
    "is_active",
    # Ciclo de vida
    "create",
    "ensure",
    "activate",
    "reset",
    # Paquetes
    "install",
    "update",
    "reinstall",
    "uninstall",
    "run",
    "list_packages",
    # Lista blanca
    "allow_list",
    "allow_add",
    "allow_remove",
    "is_library_allowed",
    "reset_allowed_libraries",
    # Directorios por plugin
    "get_data_base_dir",
    "get_temp_base_dir",
    "get_plugin_data_dir",
    "get_plugin_temp_dir",
    "clean_temp",
    "clean_cache",
    "clean_data",
    # Dependencias de manifests
    "install_plugin_requirements",
]
