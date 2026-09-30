"""
Subsistema de Seguridad para Plugins de Gram (`gram.plugins.security`).
=======================================================================
Implementa dos capas de defensa independientes y complementarias:

**Capa 1 — Análisis Estático (en tiempo de validación/instalación):**
  Audita el código fuente ``.py`` de un plugin *antes* de ejecutarlo,
  bloqueando patrones de evasión de sandbox conocidos en CPython:
    - Importaciones de módulos no autorizados (contra la lista blanca de
      ``gram.plugins.environment``).
    - Acceso a atributos ``dunder`` de introspección peligrosa
      (``__subclasses__``, ``__globals__``, ``__builtins__``, etc.).
    - Llamadas a funciones de ejecución dinámica (``eval``, ``exec``,
      ``compile``, ``__import__``).
    - Uso de ``getattr()`` con atributos ``dunder`` restringidos.

**Capa 2 — Gancho de Auditoría de CPython (en tiempo de ejecución):**
  Registra un hook permanente e irrevocable en el intérprete mediante
  ``sys.addaudithook()`` (PEP 578). Intercepta y bloquea en runtime
  intentos de subprocesos (``subprocess.Popen``), sockets y llamadas
  al sistema cuando se originan desde el código de un plugin.
"""
from __future__ import annotations

import ast
import inspect
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from gram import config, errors


# ===========================================================================
# Constantes de políticas de seguridad
# ===========================================================================

#: Atributos ``dunder`` de bajo nivel cuyo acceso está prohibido en plugins.
BANNED_DUNDER_ATTRIBUTES: frozenset[str] = frozenset({
    "__subclasses__",
    "__bases__",
    "__base__",
    "__globals__",
    "__builtins__",
    "__code__",
    "__closure__",
})

#: Funciones nativas de metaprogramación dinámica prohibidas en plugins.
BANNED_BUILTIN_CALLS: frozenset[str] = frozenset({
    "eval",
    "exec",
    "compile",
    "__import__",
})

#: Eventos de CPython audit que los plugins tienen terminantemente prohibidos.
RESTRICTED_AUDIT_EVENTS: frozenset[str] = frozenset({
    "subprocess.Popen",
    "os.system",
    "os.spawn",
    "os.posix_spawn",
    "socket.connect",
    "socket.bind",
})

#: Submódulos de infraestructura de Gram que *no* se tratan como código de plugin.
_GRAM_INFRA_PREFIXES: tuple[str, ...] = (
    "gram.plugins.manager",
    "gram.plugins.security",
    "gram.plugins.validator",
    "gram.plugins.manifest",
    "gram.plugins.colors",
    "gram.plugins.registry",
    "gram.plugins.environment",
    "gram.plugins.permissions",
)


# ===========================================================================
# Capa 1: Auditoría Estática AST
# ===========================================================================

@dataclass
class SecurityIssue:
    """Hallazgo de seguridad detectado durante la auditoría estática de un plugin."""
    level: str          # ``'ERROR'`` | ``'WARNING'``
    code: Any           # ``errors.CodeError``
    message: str
    file: str | None = None
    line: int | None = None

    def format_line(self) -> str:
        """Formatea el hallazgo para presentación en consola o logs."""
        loc = ""
        if self.file:
            loc = f" [{self.file}"
            if self.line:
                loc += f":L{self.line}"
            loc += "]"
        code_str = f" ({self.code.name})" if hasattr(self.code, "name") else f" ({self.code})"
        return f"{self.message}{loc}{code_str}"


class ASTSecurityVisitor(ast.NodeVisitor):
    """
    Recorre el AST de un archivo Python y detecta patrones de riesgo de
    seguridad que contravienen las políticas del sandbox de Gram.
    """

    def __init__(
        self,
        filename: str,
        allowed_locals: set[str] | None = None,
        check_imports: bool = True,
    ) -> None:
        self.filename = filename
        self.allowed_locals: set[str] = allowed_locals or set()
        self.check_imports = check_imports
        self.issues: list[SecurityIssue] = []

    # --- Importaciones ---

    def visit_Import(self, node: ast.Import) -> None:
        if self.check_imports:
            for alias in node.names:
                self._audit_module(alias.name, node.lineno)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if self.check_imports:
            # Importaciones relativas dentro del paquete del plugin: siempre válidas.
            if node.level and node.level > 0:
                self.generic_visit(node)
                return
            if node.module:
                self._audit_module(node.module, node.lineno)
        self.generic_visit(node)

    def _audit_module(self, raw_name: str, lineno: int) -> None:
        from gram.plugins.environment import allow_list, is_library_allowed

        root = raw_name.split(".")[0]
        if root in self.allowed_locals:
            return
        if raw_name.startswith(("gram", "Gram", "__future__")):
            return
        if not is_library_allowed(root):
            self.issues.append(
                SecurityIssue(
                    level="ERROR",
                    code=errors.PLUGIN_PROTECTED_VIOLATION,
                    message=(
                        f"Importación no autorizada de '{raw_name}'. "
                        f"El módulo no figura en la lista blanca: {allow_list()}."
                    ),
                    file=self.filename,
                    line=lineno,
                )
            )

    # --- Atributos dunder prohibidos ---

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr in BANNED_DUNDER_ATTRIBUTES:
            self.issues.append(
                SecurityIssue(
                    level="ERROR",
                    code=errors.PLUGIN_PROTECTED_VIOLATION,
                    message=(
                        f"Acceso prohibido al atributo especial '{node.attr}'. "
                        "La introspección de bajo nivel no está permitida en plugins de Gram."
                    ),
                    file=self.filename,
                    line=node.lineno,
                )
            )
        self.generic_visit(node)

    # --- Llamadas a funciones peligrosas ---

    def visit_Call(self, node: ast.Call) -> None:
        func_name: str | None = None

        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            if func_name in BANNED_BUILTIN_CALLS:
                self.issues.append(
                    SecurityIssue(
                        level="ERROR",
                        code=errors.PLUGIN_PROTECTED_VIOLATION,
                        message=(
                            f"Llamada prohibida a '{func_name}()'. "
                            "La ejecución dinámica de código está restringida en plugins de Gram."
                        ),
                        file=self.filename,
                        line=node.lineno,
                    )
                )

        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr
            is_builtins_access = (
                isinstance(node.func.value, ast.Name)
                and node.func.value.id in ("builtins", "__builtins__")
            )
            if (is_builtins_access and func_name in BANNED_BUILTIN_CALLS) or func_name in (
                "eval",
                "exec",
                "__import__",
            ):
                self.issues.append(
                    SecurityIssue(
                        level="ERROR",
                        code=errors.PLUGIN_PROTECTED_VIOLATION,
                        message=(
                            f"Llamada prohibida al método '{func_name}()'. "
                            "La ejecución dinámica de código está restringida en plugins de Gram."
                        ),
                        file=self.filename,
                        line=node.lineno,
                    )
                )

        # getattr() con atributos dunder restringidos como string literal
        if func_name == "getattr" and len(node.args) >= 2:
            target_arg = node.args[1]
            if isinstance(target_arg, ast.Constant) and isinstance(target_arg.value, str):
                if target_arg.value in BANNED_DUNDER_ATTRIBUTES:
                    self.issues.append(
                        SecurityIssue(
                            level="ERROR",
                            code=errors.PLUGIN_PROTECTED_VIOLATION,
                            message=(
                                f"Llamada a getattr() solicitando '{target_arg.value}'. "
                                "La inspección de atributos especiales está restringida."
                            ),
                            file=self.filename,
                            line=node.lineno,
                        )
                    )

        self.generic_visit(node)


def audit_python_code(
    code_or_tree: str | ast.AST,
    filename: str = "<plugin_code>",
    allowed_locals: set[str] | None = None,
    check_imports: bool = True,
) -> list[SecurityIssue]:
    """
    Audita una cadena de código Python o un árbol AST contra las políticas
    de seguridad de Gram.

    Args:
        code_or_tree: Código fuente (str) o AST ya parseado.
        filename: Nombre de archivo para mensajes de error.
        allowed_locals: Nombres de módulos locales del plugin considerados válidos.
        check_imports: Si False, omite la validación de importaciones.

    Returns:
        Lista de :class:`SecurityIssue` encontrados. Lista vacía = limpio.
    """
    if isinstance(code_or_tree, str):
        try:
            tree = ast.parse(code_or_tree, filename=filename)
        except SyntaxError as syn_err:
            return [
                SecurityIssue(
                    level="ERROR",
                    code=errors.PLUGIN_SYNTAX_ERROR,
                    message=f"Error sintáctico: {syn_err.msg}",
                    file=filename,
                    line=syn_err.lineno,
                )
            ]
        except Exception as exc:
            return [
                SecurityIssue(
                    level="ERROR",
                    code=errors.PLUGIN_SYNTAX_ERROR,
                    message=f"Error al analizar el código: {exc}",
                    file=filename,
                )
            ]
    else:
        tree = code_or_tree

    visitor = ASTSecurityVisitor(
        filename=filename,
        allowed_locals=allowed_locals,
        check_imports=check_imports,
    )
    visitor.visit(tree)
    return visitor.issues


def audit_plugin_directory(
    plugin_path: Path,
    allowed_locals: set[str] | None = None,
) -> list[SecurityIssue]:
    """
    Audita todos los archivos ``.py`` de un directorio de plugin.

    Los archivos en ``__pycache__`` y similares son ignorados.
    Un error sintáctico en cualquier archivo se registra como ``SecurityIssue``
    pero no interrumpe el análisis del resto de archivos.

    Args:
        plugin_path: Directorio raíz del plugin.
        allowed_locals: Módulos locales del plugin considerados válidos.

    Returns:
        Lista consolidada de :class:`SecurityIssue`.
    """
    _IGNORED_DIRS = {
        "__pycache__", ".git", ".pytest_cache", ".venv",
        ".idea", ".vscode", ".mypy_cache", ".ruff_cache", ".tox",
    }

    all_issues: list[SecurityIssue] = []

    for py_file in plugin_path.rglob("*.py"):
        if any(part in _IGNORED_DIRS for part in py_file.parts):
            continue
        if py_file.suffix in (".pyc", ".pyo"):
            continue

        try:
            source = py_file.read_text(encoding="utf-8")
        except OSError as exc:
            all_issues.append(
                SecurityIssue(
                    level="ERROR",
                    code=errors.PLUGIN_SYNTAX_ERROR,
                    message=f"No se pudo leer el archivo: {exc}",
                    file=str(py_file.name),
                )
            )
            continue

        issues = audit_python_code(
            source,
            filename=str(py_file.relative_to(plugin_path)),
            allowed_locals=allowed_locals,
        )
        all_issues.extend(issues)

    return all_issues


# ===========================================================================
# Capa 2: Gancho de Auditoría de CPython (runtime)
# ===========================================================================

_hook_installed: bool = False


def _is_frame_from_plugin(frame: Any) -> tuple[bool, str]:
    """
    Determina si un frame de la pila de ejecución pertenece al código
    de un plugin (y no a la infraestructura de Gram).

    Returns:
        ``(es_plugin, identificador)`` — el identificador puede ser el nombre
        del módulo o la ruta del archivo.
    """
    code_obj = getattr(frame, "f_code", None)
    if not code_obj:
        return False, ""

    filename: str = getattr(code_obj, "co_filename", "")
    mod_name: str = frame.f_globals.get("__name__", "")

    # 1. Comprobación por espacio de nombres
    if mod_name.startswith("gram.plugins."):
        if not any(mod_name.startswith(prefix) for prefix in _GRAM_INFRA_PREFIXES):
            return True, mod_name

    # 2. Comprobación por ruta de archivo
    norm = filename.replace("\\", "/").lower()
    if "/gram/plugins/" in norm or "/plugins/" in norm:
        infra_paths = [prefix.replace(".", "/") for prefix in _GRAM_INFRA_PREFIXES]
        if not any(infra in norm for infra in infra_paths):
            return True, filename

    return False, ""


def _gram_runtime_audit_hook(event: str, args: tuple[Any, ...]) -> None:
    """
    Hook de auditoría de CPython invocado ante eventos de bajo nivel.

    Intercepta y bloquea operaciones restringidas cuando se originan
    desde el código de un plugin.
    """
    # Modo permisivo total (solo para desarrollo/depuración)
    if getattr(config, "PLUGINS_ALLOW_ALL_PLUGINS", False):
        return

    if event not in RESTRICTED_AUDIT_EVENTS:
        return

    frame = inspect.currentframe()
    while frame is not None:
        is_plugin, plugin_id = _is_frame_from_plugin(frame)
        if is_plugin:
            raise PermissionError(
                f"Operación prohibida '{event}' bloqueada por el sandbox de Gram. "
                f"El plugin '{plugin_id}' no tiene permisos para realizar operaciones de sistema."
            )
        frame = frame.f_back


def install_audit_hook() -> bool:
    """
    Registra el hook de auditoría de CPython si aún no ha sido instalado.

    El hook es **permanente e irrevocable** para la vida del proceso actual,
    conforme a la especificación de ``sys.addaudithook()`` (PEP 578).
    Es idempotente: llamadas posteriores no tienen efecto.

    Returns:
        True si el hook fue instalado en esta llamada,
        False si ya estaba activo o el intérprete no lo soporta.
    """
    global _hook_installed
    if _hook_installed:
        return False

    if not hasattr(sys, "addaudithook"):
        return False

    try:
        sys.addaudithook(_gram_runtime_audit_hook)
        _hook_installed = True
        return True
    except Exception:
        return False


def is_audit_hook_installed() -> bool:
    """Retorna True si el gancho de auditoría de runtime está activo."""
    return _hook_installed


__all__ = [
    # Constantes
    "BANNED_DUNDER_ATTRIBUTES",
    "BANNED_BUILTIN_CALLS",
    "RESTRICTED_AUDIT_EVENTS",
    # Tipos
    "SecurityIssue",
    # Capa 1: análisis estático
    "ASTSecurityVisitor",
    "audit_python_code",
    "audit_plugin_directory",
    # Capa 2: runtime hook
    "install_audit_hook",
    "is_audit_hook_installed",
]
