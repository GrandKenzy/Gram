"""
Punto de Entrada y Fachada Pública de GLANG (`gram.glang.main`).
==============================================================
Proporciona las funciones principales para compilar gramáticas declarativas GLang
a partir de código fuente, archivos o contexto de plugin activo.
"""
from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any

from gram import errors
from gram.glang.reinterpreter import LanguageCompiler
from gram.utilities import error


def _find_plugin_context() -> tuple[Any, Path | None]:
    """
    Inspecciona el stack de llamadas una única vez y devuelve (plugin, cand_dir).
    plugin puede ser None si no se detecta contexto de plugin activo.
    cand_dir apunta al directorio que contiene algún archivo .glang, o None.
    """
    from gram.plugins.manager import Plugins
    from gram.plugins import registry as _registry

    # Primero intentar por nombre de plugin activo en carga
    current_name = _registry.get_current_loading()
    if current_name:
        plugin = Plugins.find(current_name)
        if plugin and plugin.plugin_path:
            return plugin, plugin.plugin_path

    # Inspeccionar el stack de llamadas una sola vez
    plugin = None
    cand_dir: Path | None = None

    caller = inspect.currentframe()
    try:
        while caller:
            caller = caller.f_back
            if caller is None:
                break
            fname = caller.f_code.co_filename
            if not fname or fname.startswith('<') or not Path(fname).exists():
                continue

            frame_dir = Path(fname).resolve().parent

            # ¿Es un directorio de plugin ya registrado?
            if plugin is None:
                for p in Plugins.registry.values():
                    if p.plugin_path and p.plugin_path.resolve() == frame_dir:
                        plugin = p
                        cand_dir = frame_dir
                        break
                if plugin is None and (
                    (frame_dir / "manifest.json").exists()
                    or (frame_dir / "main.py").exists()
                ):
                    plugin = Plugins.find(frame_dir.name)
                    if plugin is None:
                        for p in Plugins.registry.values():
                            if p.plugin_path and p.plugin_path.resolve() == frame_dir:
                                plugin = p
                                break

            # ¿Hay archivos .glang?
            if cand_dir is None and list(frame_dir.glob("*.glang")):
                cand_dir = frame_dir

            # Si encontramos ambos, parar
            if plugin and cand_dir:
                break
    finally:
        del caller

    return plugin, cand_dir


def parse_dsl(dsl_source: str) -> LanguageCompiler:
    """Parsea una cadena de texto en sintaxis GLang y retorna un LanguageCompiler."""
    compiler = LanguageCompiler.from_dsl(dsl_source)
    try:
        from gram import vsix
        vsix.register_user_grammar(compiler.grammar)
    except Exception:
        pass
    return compiler


def parse_glang_file(glang_path: str | Path) -> LanguageCompiler:
    """
    Compila un archivo de especificación `.glang` y devuelve el LanguageCompiler.
    Use `compiler.parse(source)` o `compiler.parse_file(path)` para parsear código fuente.
    """
    compiler = LanguageCompiler.from_file(glang_path)
    try:
        from gram import vsix
        vsix.register_user_grammar(compiler.grammar)
    except Exception:
        pass
    return compiler


def parse_file(glang_path: str | Path, source_path: str | Path | None = None) -> Any:
    """
    Compila un archivo `.glang` y opcionalmente analiza un archivo fuente con él.

    Args:
        glang_path: Ruta al archivo `.glang` con la especificación de gramática.
        source_path: Ruta opcional al archivo fuente a parsear con esa gramática.
                     Si se omite, devuelve el LanguageCompiler para uso manual.

    Returns:
        ASTProgram si se proporcionó source_path, LanguageCompiler en caso contrario.
    """
    compiler = parse_glang_file(glang_path)
    if source_path is not None:
        return compiler.parse_file(source_path)
    return compiler


def compile(source_or_file: str | Path | None = None) -> dict[Any, Any]:
    """
    Compila un archivo o código fuente GLang (.glang) en un diccionario de gramática ejecutable.

    Si se invoca sin argumentos desde dentro de `load()` de un plugin,
    detecta automáticamente el archivo .glang del plugin.

    Returns:
        Diccionario {RuleItem: Combinator} de la gramática compilada.
    """
    from gram.plugins.manager import Plugins
    from gram.plugins import registry as _registry

    # 1. Sin argumentos: detectar contexto de plugin o directorio con .glang
    if source_or_file is None:
        plugin, cand_dir = _find_plugin_context()

        if plugin is not None:
            return plugin.compile_glang()

        if cand_dir is not None:
            glang_files = sorted(cand_dir.glob("*.glang"))
            if glang_files:
                compiler = LanguageCompiler.from_file(glang_files[0])
                return compiler.grammar

        error.GrammarError(
            "Archivo .glang no encontrado",
            errors.PLUGIN_MANIFEST_INVALID,
            "No se especificó un archivo .glang y no se pudo determinar el plugin en carga.",
            "Invoque glang.compile() dentro de la función load() de su plugin o pase la ruta del archivo.",
        ).raise_error()

    # 2. Ruta a un archivo .glang
    if isinstance(source_or_file, Path) or (
        isinstance(source_or_file, str)
        and (Path(source_or_file).is_file() or str(source_or_file).endswith(".glang"))
    ):
        file_path = Path(source_or_file)
        if not file_path.is_file():
            current_name = _registry.get_current_loading()
            plugin_ctx = Plugins.find(current_name) if current_name else None
            if plugin_ctx and plugin_ctx.plugin_path and (plugin_ctx.plugin_path / file_path).is_file():
                file_path = plugin_ctx.plugin_path / file_path
            else:
                error.GrammarError(
                    "Archivo .glang no encontrado",
                    errors.PLUGIN_MANIFEST_INVALID,
                    f"No se encontró el archivo .glang especificado: {file_path}",
                    "Verifique la ruta del archivo .glang proporcionada.",
                ).raise_error()

        compiler = LanguageCompiler.from_file(file_path)
        current_name = _registry.get_current_loading()
        plugin_ctx = Plugins.find(current_name) if current_name else None
        if plugin_ctx:
            plugin_ctx._compiled_grammar = compiler.grammar
            plugin_ctx._compiler = compiler
            plugin_ctx._glang_file = file_path
        return compiler.grammar

    # 3. Código DSL inline como string
    compiler = LanguageCompiler.from_dsl(str(source_or_file))
    current_name = _registry.get_current_loading()
    plugin_ctx = Plugins.find(current_name) if current_name else None
    if plugin_ctx:
        plugin_ctx._compiled_grammar = compiler.grammar
        plugin_ctx._compiler = compiler
    return compiler.grammar


__all__ = ['parse_dsl', 'parse_file', 'parse_glang_file', 'compile', 'LanguageCompiler']
