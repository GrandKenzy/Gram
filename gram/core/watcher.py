"""
Syntactic Watcher and Execution Monitor (`gram.core.watcher`).
=============================================================
EN:
    Supervises syntactic execution in real time, recording the active combinator
    stack, in-progress sequences, current ordinal step, and positioned tokens,
    enabling precise error diagnostics and telemetry inspection.
    Includes filesystem watchers (`FileWatcher` and `PluginWatcher`) for hot-reloading support.

ES:
    Supervisa en tiempo real el progreso de la ejecución sintáctica, registrando
    la pila de combinadores activos, secuencias en curso, paso actual y token
    posicionado, permitiendo diagnósticos precisos ante fallos o depuración.
    Incluye además vigilantes de sistema de archivos (`FileWatcher` y `PluginWatcher`)
    para soporte de recarga en caliente (hot-reload).
"""
from __future__ import annotations

import hashlib
import os
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from gram.core.combinators.base import Combinator
    from gram.core.lexer.tokens import TokenType


class Watcher:
    """
    EN:
        Internal execution watcher and telemetry monitor for Parser and ASTAnalyzer.
        Monitors active combinator stacks, ordered sequences, and tokens under the cursor
        in real time, enabling detailed telemetry, snapshots, and error diagnostics.

    ES:
        Vigilante interno del motor de análisis sintáctico (Parser y ASTAnalyzer).
        Supervisa en tiempo real la pila de combinadores activos, secuencias ordenadas
        y tokens bajo el cursor, posibilitando telemetría detallada, inspección y snapshots.
    """

    def __init__(self) -> None:
        """
        EN: Initializes the execution monitor with empty combinator and sequence stacks.
        ES: Inicializa el monitor con pilas vacías de combinadores y secuencias.
        """
        self._token: TokenType | None = None
        self._combinator_stack: list[Combinator] = []
        self._sequence_stack: list[dict[str, Any]] = []
        self._errors: list[Exception] = []

    # =========================================================================
    # SEGUIMIENTO DE ESTADO (PARSER & ANALYZER) / STATE TRACKING
    # =========================================================================

    def update_token(self, token: TokenType | None) -> None:
        """
        EN: Updates the active lexical token currently under inspection.
        ES: Actualiza el token léxico que se encuentra bajo análisis en este momento.

        Args:
            token (TokenType | None): Active token or None.
        """
        self._token = token

    def enter_combinator(self, combinator: Combinator, token: TokenType | None = None) -> None:
        """
        EN: Pushes a combinator onto the active evaluation stack.
        ES: Registra la entrada a la evaluación de un combinador.

        Args:
            combinator (Combinator): Syntactic combinator entering evaluation.
            token (TokenType | None, optional): Current token under the cursor.
        """
        self._combinator_stack.append(combinator)
        if token is not None:
            self._token = token

    def exit_combinator(self) -> None:
        """
        EN: Pops the topmost combinator from the evaluation stack upon completion.
        ES: Registra la finalización de la evaluación del combinador actual.
        """
        if self._combinator_stack:
            self._combinator_stack.pop()

    def enter_sequence(self, sequence: Combinator, total_steps: int) -> None:
        """
        EN: Registers the entry into an ordered multi-step sequence (e.g., Seq).
        ES: Registra el inicio de una secuencia ordenada de pasos (ej. Seq).

        Args:
            sequence (Combinator): Sequence combinator entering execution.
            total_steps (int): Total number of sequential steps.
        """
        self._sequence_stack.append({
            "sequence": sequence,
            "total_steps": total_steps,
            "current_step": 0,
        })

    def step_sequence(self, step_index: int = 1) -> None:
        """
        EN: Updates the current ordinal step within the active sequence.
        ES: Actualiza el paso actual dentro de la secuencia activa.

        Args:
            step_index (int, optional): 1-based ordinal index of the current step. Defaults to 1.
        """
        if self._sequence_stack:
            self._sequence_stack[-1]["current_step"] = step_index

    def exit_sequence(self) -> None:
        """
        EN: Pops the topmost sequence from the sequence stack upon completion.
        ES: Registra la salida o finalización de la secuencia actual.
        """
        if self._sequence_stack:
            self._sequence_stack.pop()

    def reset(self) -> None:
        """
        EN: Resets the entire watcher state, clearing all stacks and error logs.
        ES: Restablece el estado completo del vigilante, limpiando pilas y registros.
        """
        self._token = None
        self._combinator_stack.clear()
        self._sequence_stack.clear()
        self._errors.clear()

    # =========================================================================
    # GESTIÓN DE ERRORES Y TELEMETRÍA / ERROR RECORDING & TELEMETRY
    # =========================================================================

    def record_error(self, error: Exception) -> None:
        """
        EN: Records an exception raised during syntactic analysis for telemetry inspection.
        ES: Registra una excepción producida durante la evaluación sintáctica.

        Args:
            error (Exception): Exception to record.
        """
        self._errors.append(error)

    @property
    def has_errors(self) -> bool:
        """
        EN: True if one or more exceptions were captured during monitoring.
        ES: Indica si se han registrado errores durante la inspección.
        """
        return bool(self._errors)

    @property
    def errors(self) -> list[Exception]:
        """
        EN: Returns a copy of the list of captured exceptions.
        ES: Lista de excepciones capturadas.
        """
        return list(self._errors)

    def clear_errors(self) -> None:
        """
        EN: Clears all accumulated error records.
        ES: Limpia el registro de errores acumulados.
        """
        self._errors.clear()

    # =========================================================================
    # CONSULTAS Y DIAGNÓSTICO / QUERIES & DIAGNOSTICS
    # =========================================================================

    @property
    def depth(self) -> int:
        """
        EN: Current depth of the active combinator evaluation stack.
        ES: Profundidad actual de la pila de combinadores en evaluación.
        """
        return len(self._combinator_stack)

    @property
    def sequence_step(self) -> int:
        """
        EN: Current step of the nearest active sequence (0 if no sequence active).
        ES: Paso actual de la secuencia activa más cercana (0 si no hay secuencia).
        """
        seq = self.current_sequence
        return seq["current_step"] if seq else 0

    def active_path(self) -> list[str]:
        """
        EN: Returns the hierarchical path of active combinator types from root to top.
        ES: Retorna la ruta jerárquica de tipos de combinadores actualmente activos.

        Returns:
            list[str]: Combinator type names in bottom-to-top order.
        """
        return [
            c.type() if hasattr(c, "type") else getattr(c, "name", str(c))
            for c in self._combinator_stack
        ]

    @property
    def current_token(self) -> TokenType | None:
        """
        EN: Lexical token currently being analyzed under the cursor.
        ES: Token léxico que se está analizando actualmente bajo el cursor.
        """
        return self._token

    @property
    def current_combinator(self) -> Combinator | None:
        """
        EN: Active combinator at the top of the evaluation stack.
        ES: Combinador activo en la cima de la pila de evaluación.
        """
        return self._combinator_stack[-1] if self._combinator_stack else None

    @property
    def current_sequence(self) -> dict[str, Any] | None:
        """
        EN: Information dictionary of the nearest active sequence.
        ES: Información de la secuencia activa más cercana.
        """
        return self._sequence_stack[-1] if self._sequence_stack else None

    def snapshot(self) -> dict[str, Any]:
        """
        EN: Captures a comprehensive structured snapshot of the engine position and context.
        ES: Captura un estado estructurado de la posición y contexto actual del motor.

        Returns:
            dict[str, Any]: Dictionary detailing sequence, step, combinator, depth, and token.
        """
        seq_info = self.current_sequence
        seq_repr = None
        step = None
        total = None

        if seq_info:
            seq_repr = repr(seq_info["sequence"])
            step = seq_info["current_step"]
            total = seq_info["total_steps"]

        comb = self.current_combinator
        comb_repr = repr(comb) if comb else None

        tok = self.current_token
        tok_repr = repr(tok) if tok else None

        return {
            "sequence": seq_repr,
            "sequence_step": step,
            "sequence_total": total,
            "combinator": comb_repr,
            "depth": len(self._combinator_stack),
            "combinator_depth": len(self._combinator_stack),
            "token": tok_repr,
            "token_type": getattr(getattr(tok, "token", None), "name", None) if tok else None,
            "token_value": getattr(tok, "value", None) if tok else None,
            "token_line": getattr(tok, "line", None) if tok else None,
            "token_col": getattr(tok, "col", None) if tok else None,
        }

    def where_am_i(self) -> str:
        """
        EN: Returns a human-readable diagnostic trace string indicating the active position.
        ES: Retorna una cadena descriptiva y legible que indica la posición actual del motor.

        Returns:
            str: Diagnostic execution trace string.
        """
        snap = self.snapshot()
        seq_str = (
            f"Secuencia: {snap['sequence']} (Paso {snap['sequence_step']}/{snap['sequence_total']})"
            if snap["sequence"]
            else "Secuencia: Ninguna"
        )
        comb_str = f"Combinador: {snap['combinator'] or 'Ninguno'}"

        if snap["token"]:
            tok_str = f"Token: {snap['token_type']}({snap['token_value']!r}) en L{snap['token_line']}:C{snap['token_col']}"
        else:
            tok_str = "Token: Ninguno"

        return f"[{seq_str}] -> [{comb_str}] -> [{tok_str}]"

    def __repr__(self) -> str:
        return f"<Watcher: {self.where_am_i()}>"


# =============================================================================
# 2. VIGILANTE DE ARCHIVOS Y RECARGA EN CALIENTE (FILEWATCHER & PLUGINWATCHER)
# =============================================================================

def should_ignore(name: str) -> bool:
    """
    EN: Filters out temporary files, binaries, build directories, and unnecessary caches.
    ES: Filtra archivos temporales, binarios y cachés innecesarios.

    Args:
        name (str): File or directory base name.

    Returns:
        bool: True if the file should be ignored.
    """
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


def compute_file_hash(path: Path | str) -> str:
    """
    EN: Computes the SHA-256 cryptographic hash of a file for change verification.
    ES: Calcula el hash SHA-256 de un archivo para verificación de cambios.

    Args:
        path (Path | str): Target file path.

    Returns:
        str: Hexadecimal SHA-256 digest, or empty string on error/non-file.
    """
    p = Path(path)
    if not p.is_file():
        return ""
    try:
        return hashlib.sha256(p.read_bytes()).hexdigest()
    except OSError:
        return ""


class FileWatcher:
    """
    EN:
        Filesystem watcher monitoring changes across files and directories.
        Detects additions, modifications, and deletions by inspecting
        timestamps (mtime), sizes, and SHA-256 hashes.

    ES:
        Vigilante de sistema de archivos para monitoreo de cambios en tiempo real.
        Detecta adiciones, modificaciones y eliminaciones mediante inspección
        de timestamps (mtime), tamaños y hashes SHA-256.
    """

    def __init__(
        self,
        paths: list[Path | str] | Path | str | None = None,
        recursive: bool = True,
        debounce_seconds: float = 0.3,
        on_change: Callable[[dict[str, list[Path]]], None] | None = None,
        file_filter: Callable[[Path], bool] | None = None,
    ) -> None:
        """
        EN: Initializes the file watcher over one or more directories or files.
        ES: Inicializa el vigilante sobre una o varias rutas.

        Args:
            paths: Target path or list of paths to monitor (defaults to cwd if None).
            recursive (bool): If True, inspects subdirectories recursively.
            debounce_seconds (float): Stabilization delay before triggering callbacks.
            on_change: Callback invoked with detected changes dictionary.
            file_filter: Optional predicate to include or discard files.
        """
        if paths is None:
            self.paths: list[Path] = [Path.cwd().resolve()]
        elif isinstance(paths, (str, Path)):
            self.paths = [Path(paths).resolve()]
        else:
            self.paths = [Path(p).resolve() for p in paths]

        self.recursive: bool = recursive
        self.debounce_seconds: float = debounce_seconds
        self.on_change: Callable[[dict[str, list[Path]]], None] | None = on_change
        self.file_filter: Callable[[Path], bool] | None = file_filter

        self._snapshot: dict[Path, tuple[float, int, str]] = {}
        self._running: bool = False
        self._thread: threading.Thread | None = None
        self._lock: threading.Lock = threading.Lock()

        # Capture initial snapshot of watched files
        self._scan_initial()

    def _should_include(self, path: Path) -> bool:
        """
        EN: Determines if a file should be tracked based on filters and exclusions.
        ES: Determina si un archivo debe ser incluido según filtros y exclusiones.
        """
        if should_ignore(path.name):
            return False
        for parent in path.parents:
            if should_ignore(parent.name):
                return False
        if self.file_filter is not None and not self.file_filter(path):
            return False
        return True

    def _collect_files(self) -> list[Path]:
        """
        EN: Collects all eligible files under the configured paths.
        ES: Recolecta todos los archivos aplicables en las rutas configuradas.
        """
        collected: list[Path] = []
        for base in self.paths:
            if not base.exists():
                continue
            if base.is_file():
                if self._should_include(base):
                    collected.append(base)
                continue
            if self.recursive:
                for root, dirs, files in os.walk(base):
                    dirs[:] = [d for d in dirs if not should_ignore(d)]
                    for fname in files:
                        p = Path(root) / fname
                        if self._should_include(p):
                            collected.append(p)
            else:
                for entry in base.iterdir():
                    if entry.is_file() and self._should_include(entry):
                        collected.append(entry)
        return collected

    def _scan_initial(self) -> None:
        """
        EN: Captures initial state without triggering change notifications.
        ES: Captura el estado inicial sin disparar callbacks.
        """
        for f in self._collect_files():
            try:
                stat = f.stat()
                h = compute_file_hash(f)
                self._snapshot[f] = (stat.st_mtime, stat.st_size, h)
            except OSError:
                pass

    def poll_once(self) -> dict[str, list[Path]]:
        """
        EN: Executes a manual polling cycle and reports detected filesystem changes.
        ES: Ejecuta un ciclo de sondeo manual y reporta los cambios detectados.

        Returns:
            dict[str, list[Path]]: Dictionary with 'added', 'modified', 'deleted' file lists.
        """
        current_files = set(self._collect_files())
        previous_files = set(self._snapshot.keys())

        added: list[Path] = []
        modified: list[Path] = []
        deleted: list[Path] = []

        # Detect deletions
        for p in previous_files - current_files:
            deleted.append(p)
            self._snapshot.pop(p, None)

        # Detect additions and modifications
        for p in current_files:
            try:
                stat = p.stat()
                mtime = stat.st_mtime
                size = stat.st_size

                if p not in self._snapshot:
                    h = compute_file_hash(p)
                    self._snapshot[p] = (mtime, size, h)
                    added.append(p)
                else:
                    prev_mtime, prev_size, prev_hash = self._snapshot[p]
                    if prev_mtime != mtime or prev_size != size:
                        new_hash = compute_file_hash(p)
                        if new_hash != prev_hash:
                            self._snapshot[p] = (mtime, size, new_hash)
                            modified.append(p)
            except OSError:
                pass

        changes = {
            "added": added,
            "modified": modified,
            "deleted": deleted,
        }

        has_changes = bool(added or modified or deleted)
        if has_changes and self.on_change:
            time.sleep(self.debounce_seconds)
            self.on_change(changes)

        return changes

    def start_async(self, interval: float = 0.5) -> None:
        """
        EN: Starts background monitoring in a dedicated daemon thread.
        ES: Inicia el monitoreo en un hilo en segundo plano (daemon).

        Args:
            interval (float): Polling sleep interval in seconds. Defaults to 0.5.
        """
        with self._lock:
            if self._running:
                return
            self._running = True
            self._thread = threading.Thread(
                target=self._loop,
                args=(interval,),
                name="GramFileWatcherThread",
                daemon=True,
            )
            self._thread.start()

    def stop(self) -> None:
        """
        EN: Stops the asynchronous monitoring thread gracefully.
        ES: Detiene el hilo de monitoreo asíncrono de forma segura.
        """
        with self._lock:
            self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    @property
    def is_running(self) -> bool:
        """
        EN: Indicates whether the watcher thread is actively running.
        ES: Indica si el vigilante se encuentra activo.
        """
        return self._running

    def _loop(self, interval: float) -> None:
        while self._running:
            try:
                self.poll_once()
            except Exception:
                pass
            time.sleep(interval)

    def watch(self, interval: float = 1.0) -> None:
        """
        EN: Blocking synchronous loop for CLI monitoring, terminating on KeyboardInterrupt.
        ES: Bucle síncrono bloqueante para monitorizar desde consola (termina con KeyboardInterrupt).

        Args:
            interval (float): Polling interval in seconds. Defaults to 1.0.
        """
        self._running = True
        try:
            while self._running:
                self.poll_once()
                time.sleep(interval)
        except KeyboardInterrupt:
            self._running = False


class PluginWatcher(FileWatcher):
    """
    EN:
        Specialized watcher for hot-reloading Gram plugins upon filesystem changes.
        Monitors plugin directories, locates manifest roots, and safely triggers reload events.

    ES:
        Vigilante especializado para recarga en caliente de plugins de Gram.
        Supervisa cambios en los directorios de plugins y notifica eventos de recarga.
    """

    def __init__(
        self,
        paths: list[Path | str] | Path | str | None = None,
        on_reload: Callable[[Any, Any, Any], None] | None = None,
        on_error: Callable[[str, list[Any]], None] | None = None,
        debounce_seconds: float = 0.3,
    ) -> None:
        """
        EN: Initializes the plugin watcher with reload and error callbacks.
        ES: Inicializa el vigilante de plugins con callbacks de recarga y error.

        Args:
            paths: Plugin directory path or list of paths.
            on_reload: Callback invoked upon successful reload (plugin, report, entry).
            on_error: Callback invoked when reload or validation fails.
            debounce_seconds (float): Debounce interval in seconds.
        """
        if paths is not None:
            target_paths = paths
        else:
            try:
                from gram.plugins.manager.core import get_plugins_dir
                target_paths = get_plugins_dir()
            except (ImportError, AttributeError):
                target_paths = [Path("./plugins").resolve()]

        super().__init__(
            paths=target_paths,
            recursive=True,
            debounce_seconds=debounce_seconds,
            on_change=self._handle_plugin_changes,
        )
        self.on_reload = on_reload
        self.on_error = on_error

    def _find_plugin_root(self, file_path: Path) -> Path | None:
        """
        EN: Identifies the root directory of the plugin containing a modified file.
        ES: Identifica la raíz del plugin contenedor de un archivo modificado.

        Args:
            file_path (Path): Path to the modified file.

        Returns:
            Path | None: Directory containing 'manifest.json', or None.
        """
        curr = file_path.parent if file_path.is_file() else file_path
        while curr and curr != curr.parent:
            if (curr / "manifest.json").exists():
                return curr
            curr = curr.parent
        return None

    def _handle_plugin_changes(self, changes: dict[str, list[Path]]) -> None:
        """
        EN: Processes changed files and safely reloads affected plugins.
        ES: Procesa archivos cambiados y recarga los plugins afectados de forma segura.
        """
        try:
            from gram.cachesystem import inspect_and_resolve_plugin
            from gram.plugins.manager.core import Plugins
        except (ImportError, AttributeError):
            return

        all_files = changes["added"] + changes["modified"] + changes["deleted"]
        affected_roots: set[Path] = set()

        for f in all_files:
            root = self._find_plugin_root(f)
            if root:
                affected_roots.add(root)

        for p_root in sorted(affected_roots):
            plugin_name = p_root.name
            try:
                report, entry = inspect_and_resolve_plugin(p_root, use_cache=False)
                if not getattr(report, "is_valid", True):
                    if self.on_error:
                        self.on_error(plugin_name, getattr(report, "errors", []))
                    continue

                reloaded_plugin = Plugins.reload(p_root)
                if self.on_reload:
                    self.on_reload(reloaded_plugin, report, entry)
            except Exception as exc:
                if self.on_error:
                    self.on_error(plugin_name, [str(exc)])


__all__ = [
    "Watcher",
    "FileWatcher",
    "PluginWatcher",
]
