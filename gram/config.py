"""
Configuración Global del Framework Gram.
=========================================
Las variables de este módulo controlan el comportamiento del lexer, parser,
AST, reporte de errores, telemetría (info/logs), reglas y entorno de plugins.

IMPORTANTE:
Las variables de este módulo solo pueden ser modificadas por el usuario
desde su punto de entrada (__main__) o scripts principales.
Los plugins tienen estrictamente prohibido modificar config directamente.
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path
from types import ModuleType
from typing import Any


# ==============================================================================
# VALORES POR DEFECTO (CONSTANTES INMUTABLES DE REFERENCIA)
# ==============================================================================
_DEFAULTS: dict[str, Any] = {
    # Lexer
    'LEXER_COMMENT_TOKEN': '#',
    'LEXER_IGNORE_EMPTY_LINES': True,
    'LEXER_IGNORE_NEWLINES': True,
    'LEXER_SAVE_COMMENTS': True,
    'LEXER_SUPPORT_DOCSTRINGS': True,
    'LEXER_ADD_INFO': True,
    'LEXER_ADD_ERROR': True,
    # Parser
    'PARSER_ADD_INFO': True,
    'PARSER_ADD_ERROR': True,
    # AST
    'AST_ADD_INFO': True,
    'AST_ADD_ERROR': True,
    # Error Handling
    'ERROR_EXIT_ON_ERROR': False,
    'ERROR_GENERATE_LOGFILE': False,
    'ERROR_HIDE_CONSOLE': False,
    # Info & Logging
    'INFO_INIT': False,
    'INFO_GENERATE_LOGFILE': False,
    'INFO_SHOW_TYPES': ['Advice', 'Error', 'Normal', 'Success', 'Warn'],
    'INFO_SHOW_PRIORITY': 3,
    'INFO_FLATTEN_OUTPUT': True,
    'LOG_HIDE_CONSOLE': True,
    # Rules
    'RULE_SET_WORK_INT': 10000,
    # Plugins & Security
    'PLUGINS_ALLOW_ALL_PLUGINS': False,
    'PLUGIN_ALLOW_INSTALL_DEPENDENCIES': False,
    'PLUGIN_DEFINE_COMMANDS': True,
    'PLUGIN_ALLOW_PYTHON_INSTALL_LIBS': False,
    'DATA_DIR': Path('./data'),
    'TEMP_DIR': Path('./data/temp'),
    'CACHE_DIR': Path('./data/.cache'),
    # Environment
    'ENVIRONMENT_DIR': Path('./environment/env'),
    'ENVIRONMENT_AUTO_CREATE': True,
    'ENVIRONMENT_BASE_REQUIREMENTS': ["setuptools", "wheel"],
}

# ==============================================================================
# 1. ANALIZADOR LÉXICO (LEXER)
# ==============================================================================
LEXER_COMMENT_TOKEN: str = '#'
LEXER_IGNORE_EMPTY_LINES: bool = True
LEXER_IGNORE_NEWLINES: bool = True
LEXER_SAVE_COMMENTS: bool = True
LEXER_SUPPORT_DOCSTRINGS: bool = True
LEXER_ADD_INFO: bool = True
LEXER_ADD_ERROR: bool = True

# ==============================================================================
# 2. MOTOR DEL PARSER
# ==============================================================================
PARSER_ADD_INFO: bool = True
PARSER_ADD_ERROR: bool = True

# ==============================================================================
# 3. ÁRBOL DE SINTAXIS ABSTRACTA (AST)
# ==============================================================================
AST_ADD_INFO: bool = True
AST_ADD_ERROR: bool = True

# ==============================================================================
# 4. GESTIÓN DE ERRORES
# ==============================================================================
ERROR_EXIT_ON_ERROR: bool = True
ERROR_GENERATE_LOGFILE: bool = False
ERROR_HIDE_CONSOLE: bool = False
ERROR_SUPPORT_ANSI: bool = False

# ==============================================================================
# 5. TELEMETRÍA, INFORMACIÓN Y LOGS
# ==============================================================================
INFO_INIT: bool = False
INFO_GENERATE_LOGFILE: bool = False
INFO_GENERATE_LOGFILE_ON_ERROR: bool = False
INFO_FLATTEN_OUTPUT: bool = True
INFO_SUPPORT_ANSI: bool = False
LOG_HIDE_CONSOLE: bool = True

# ==============================================================================
# 6. REGLAS Y TRABAJO INTERNO
# ==============================================================================
RULE_SET_WORK_INT: int = 10000

# ==============================================================================
# 7. PLUGINS Y SEGURIDAD
# ==============================================================================
PLUGINS_ALLOW_ALL_PLUGINS: bool = False
PLUGIN_ALLOW_INSTALL_DEPENDENCIES: bool = False
PLUGIN_DEFINE_COMMANDS: bool = True
PLUGIN_ALLOW_PYTHON_INSTALL_LIBS: bool = False
DATA_DIR: Path | str | None = Path('./data')
TEMP_DIR: Path | str | None = Path('./data/temp')
CACHE_DIR: Path | str | None = Path('./data/.cache')

# ==============================================================================
# 8. ENTORNO VIRTUAL (VENV)
# ==============================================================================
ENVIRONMENT_DIR: Path | str | None = Path('./environment/env')
ENVIRONMENT_AUTO_CREATE: bool = True
ENVIRONMENT_BASE_REQUIREMENTS: list[str] = ["setuptools", "wheel"]


def _is_caller_plugin() -> tuple[bool, str]:
    """
    Inspecciona la procedencia de la llamada para determinar si proviene de un plugin.

    Returns:
        Tupla (es_plugin: bool, nombre_del_plugin: str).
    """
    # 1. Comprobación mediante registro de plugin activo
    for pkg_name in ('gram.plugins.manager',):
        try:
            mod = sys.modules.get(f'{pkg_name}.registry')
            if mod is not None and hasattr(mod, 'get_current_loading'):
                active = mod.get_current_loading()
                if active is not None and active != 'GRAM_ESSENCIAL_PACK':
                    return True, active
        except Exception:
            pass

    # 2. Inspección del stack de frames
    plugins_root: Path | None = None
    for pkg_name in ('gram.plugins.manager.core',):
        try:
            mod = sys.modules.get(pkg_name)
            if mod is not None and hasattr(mod, 'get_plugins_dir'):
                plugins_root = mod.get_plugins_dir().resolve()
                break
        except Exception:
            pass

    stack = inspect.stack()
    for frame_info in stack[1:]:
        filename = frame_info.filename
        if not filename or filename.startswith('<'):
            continue

        mod_name = frame_info.frame.f_globals.get('__name__', '')
        # Verificar módulos bajo gram.plugins o Gram.plugins (excepto builtins)
        for prefix in ('gram.plugins.',):
            if mod_name.startswith(prefix) and not mod_name.startswith(f'{prefix}GRAM_ESSENCIAL_PACK'):
                parts = mod_name.split('.')
                p_name = parts[2] if len(parts) > 2 else mod_name
                return True, p_name

        if plugins_root is not None:
            try:
                p = Path(filename).resolve()
                rel = p.relative_to(plugins_root)
                if rel.parts and rel.parts[0] != 'GRAM_ESSENCIAL_PACK':
                    return True, rel.parts[0]
            except (ValueError, OSError):
                pass

    return False, ''


def reset_to_defaults() -> None:
    """
    Restablece todas las variables de configuración a sus valores por defecto.
    Útil en suites de pruebas para aislar efectos secundarios entre tests.
    """
    current_module = sys.modules[__name__]
    for key, value in _DEFAULTS.items():
        if isinstance(value, list):
            setattr(current_module, key, list(value))
        else:
            setattr(current_module, key, value)


def to_dict() -> dict[str, Any]:
    """
    Retorna un diccionario con todas las variables de configuración activas y sus valores.
    """
    current_module = sys.modules[__name__]
    return {
        key: getattr(current_module, key)
        for key in _DEFAULTS
    }


class _ConfigModule(ModuleType):
    """
    Módulo de configuración con protección de escritura contra modificaciones de plugins
    y variables oficiales de configuración.
    """

    def __init__(self, name: str, doc: str | None = None) -> None:
        super().__init__(name, doc)
        self.__dict__['_initialized'] = False

    def __setattr__(self, name: str, value: Any) -> None:
        if not getattr(self, '_initialized', False) or name.startswith('_'):
            super().__setattr__(name, value)
            return

        is_plugin, plugin_name = _is_caller_plugin()
        if is_plugin:
            p_label = f"'{plugin_name}'" if plugin_name else "desconocido"
            # Intento de reporte mediante el sistema de errores de Gram si está disponible
            for err_pkg in ('gram',):
                try:
                    err_mod = sys.modules.get(f'{err_pkg}.utilities.error')
                    codes_mod = sys.modules.get(f'{err_pkg}.errors')
                    if err_mod and hasattr(err_mod, 'PluginError'):
                        err_code = getattr(codes_mod, 'PLUGIN_CONFIG_MUTATION_DENIED', 20111) if codes_mod else 20111
                        err_mod.PluginError(
                            "Modificación de configuración denegada",
                            err_code,
                            f"El plugin {p_label} intentó modificar la variable de configuración '{name}'.",
                            "Los plugins no tienen permisos para modificar config.py. "
                            "Declare las configuraciones requeridas en 'required_config' de su manifest.json.",
                        ).raise_error()
                except Exception:
                    pass

            raise PermissionError(
                f"El plugin {p_label} no tiene permisos para modificar la variable de configuración '{name}'."
            )

        super().__setattr__(name, value)


# Inicializar wrapper y registrar en sys.modules
_current = sys.modules[__name__]
_wrapper = _ConfigModule(__name__, __doc__)
for _k, _v in list(_current.__dict__.items()):
    setattr(_wrapper, _k, _v)
_wrapper._initialized = True
sys.modules[__name__] = _wrapper

__all__ = [
    # Lexer
    "LEXER_COMMENT_TOKEN",
    "LEXER_IGNORE_EMPTY_LINES",
    "LEXER_IGNORE_NEWLINES",
    "LEXER_SAVE_COMMENTS",
    "LEXER_SUPPORT_DOCSTRINGS",
    "LEXER_ADD_INFO",
    "LEXER_ADD_ERROR",
    # Parser
    "PARSER_ADD_INFO",
    "PARSER_ADD_ERROR",
    # AST
    "AST_ADD_INFO",
    "AST_ADD_ERROR",
    # Errores
    "ERROR_EXIT_ON_ERROR",
    "ERROR_GENERATE_LOGFILE",
    "ERROR_HIDE_CONSOLE",
    "ERROR_SUPPORT_ANSI",
    # Info & Logs
    "INFO_INIT",
    "INFO_GENERATE_LOGFILE",
    "INFO_FLATTEN_OUTPUT",
    "INFO_SUPPORT_ANSI",
    "LOG_HIDE_CONSOLE",
    # Reglas
    "RULE_SET_WORK_INT",
    # Plugins & Seguridad
    "PLUGINS_ALLOW_ALL_PLUGINS",
    "PLUGIN_ALLOW_INSTALL_DEPENDENCIES",
    "PLUGIN_DEFINE_COMMANDS",
    "PLUGIN_ALLOW_PYTHON_INSTALL_LIBS",
    "DATA_DIR",
    "TEMP_DIR",
    "CACHE_DIR",
    # Entorno
    "ENVIRONMENT_DIR",
    "ENVIRONMENT_AUTO_CREATE",
    "ENVIRONMENT_BASE_REQUIREMENTS",
    # Funciones de utilidad
    "reset_to_defaults",
    "to_dict",
]
