"""
Motor Central y Administrador del Subsistema VSIX (`gram.vsix.core`).
=====================================================================
Permite la generación incremental, modular y combinada de paquetes VSIX
para VS Code, con gestión directa de ciclo de vida (`compile`, `install`, `uninstall`).

Características:
  - Identificador universal fijo de Gram: ``gram.gram-language-support``.
  - Generación de TextMate, temas cromáticos, snippets, LSP y configuración de compilador.
  - Instalación y desinstalación automática en Visual Studio Code mediante la CLI ``code``.
  - Soporte para compilación modular por plugin (`compile_from`) y consolidación automática.
"""
from __future__ import annotations

import inspect
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from gram import config
from gram.core.combinators.base import RuleItem
from gram.plugins.colors import ColorDefinition, PluginColors
from gram.vsix.extract import (
    KeywordMetadata,
    RuleMetadata,
    SyntaxMetadata,
    extract_metadata,
)
from gram.vsix.generate import (
    GRAM_EXTENSION_NAME,
    GRAM_FULL_ID,
    GRAM_PUBLISHER,
    build_extension_directory,
    package_vsix,
)


def find_vscode_executable() -> str | None:
    """
    Localiza el ejecutable de la CLI de VS Code ('code') en el sistema.
    Busca en PATH y en ubicaciones de instalación comunes de Windows, macOS y Linux.
    """
    code_in_path = shutil.which("code") or shutil.which("code.cmd")
    if code_in_path:
        return code_in_path

    # Rutas típicas en Windows
    if os.name == "nt":
        local_app = os.environ.get("LOCALAPPDATA", "")
        prog_files = os.environ.get("ProgramFiles", "")
        prog_files_x86 = os.environ.get("ProgramFiles(x86)", "")

        candidates = [
            Path(local_app) / "Programs" / "Microsoft VS Code" / "bin" / "code.cmd",
            Path(local_app) / "Programs" / "Microsoft VS Code" / "Code.exe",
            Path(prog_files) / "Microsoft VS Code" / "bin" / "code.cmd",
            Path(prog_files_x86) / "Microsoft VS Code" / "bin" / "code.cmd",
        ]
        for c in candidates:
            if c.exists():
                return str(c)
    else:
        # Linux / macOS
        candidates_unix = [
            Path("/usr/bin/code"),
            Path("/usr/local/bin/code"),
            Path("/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code"),
        ]
        for c in candidates_unix:
            if c.exists():
                return str(c)

    return None


class VsixManager:
    """
    Gestor centralizado del subsistema de extensiones VSIX y soporte de editor de Gram.
    Controla compilación, empaquetado, instalación e integración con el Language Server.
    """

    PUBLISHER: str = GRAM_PUBLISHER
    EXTENSION_NAME: str = GRAM_EXTENSION_NAME
    FULL_ID: str = GRAM_FULL_ID
    DEFAULT_VERSION: str = "1.0.0"

    def __init__(self) -> None:
        self._fragments: dict[str, SyntaxMetadata] = {}
        self._plugin_vsix_cache: dict[str, Path] = {}
        self._user_metadata: SyntaxMetadata = SyntaxMetadata()
        self._active_vsix: Path | None = None
        self._temp_dir: Path | None = None

    def _get_temp_dir(self) -> Path:
        if self._temp_dir is None or not self._temp_dir.exists():
            base = Path(tempfile.gettempdir()) / "gram_vsix_runtime"
            base.mkdir(parents=True, exist_ok=True)
            self._temp_dir = base
        return self._temp_dir

    @property
    def active_vsix(self) -> Path | None:
        """Ruta al paquete VSIX activo generado, o None si no se ha compilado."""
        if self._active_vsix and self._active_vsix.exists():
            return self._active_vsix
        return None

    def get_active_vsix(self) -> Path | None:
        """Retorna el paquete VSIX activo actual si existe."""
        return self.active_vsix

    def register_user_grammar(self, grammar: dict[Any, Any], source: str = "user_dsl") -> None:
        """Registra reglas sintácticas compiladas por el usuario para su inclusión en el VSIX."""
        if not isinstance(grammar, dict):
            return

        for r_item in grammar.keys():
            if inspect.isclass(r_item) and issubclass(r_item, RuleItem):
                try:
                    compiled = r_item.compile()
                    name = compiled.get("name") or getattr(r_item, "name", r_item.__name__)
                    self._user_metadata.rules[name] = RuleMetadata(
                        name=name,
                        code=compiled.get("code", getattr(r_item, "code", 0)),
                        description=compiled.get("description", getattr(r_item, "description", "")),
                        docs=compiled.get("docs", getattr(r_item, "docs", "")),
                        colors=compiled.get("colors", getattr(r_item, "colors", {})),
                        color=compiled.get("color", getattr(r_item, "color", "#FFFFFF")),
                        scope=compiled.get("scope", getattr(r_item, "scope", "")),
                        is_structural=compiled.get("is_structural", getattr(r_item, "is_structural", False)),
                        suggestions=compiled.get("suggestions", getattr(r_item, "suggestions", {})),
                        suggestions_autocomplete=compiled.get("suggestions_autocomplete", True),
                        source_plugin=source,
                    )
                except Exception:
                    name = getattr(r_item, "name", r_item.__name__)
                    self._user_metadata.rules[name] = RuleMetadata(
                        name=name,
                        code=getattr(r_item, "code", 0),
                        description=getattr(r_item, "description", ""),
                        source_plugin=source,
                    )

    def register_user_keyword(
        self,
        name: str,
        hex_color: str = "#FFFFFF",
        group: str | None = None,
        description: str = "",
        source: str = "user_dsl",
    ) -> None:
        """Registra una palabra clave de usuario para su inclusión en el VSIX."""
        self._user_metadata.keywords[name] = KeywordMetadata(
            name=name,
            hex_color=hex_color,
            group=group,
            description=description,
            source_plugin=source,
        )

    def compile(
        self,
        output_path: str | Path | None = None,
        force: bool = False,
        custom_extensions: list[str] | None = None,
        compiler_path: str = "",
        compiler_args: list[str] | None = None,
    ) -> Path:
        """
        Compila el paquete VSIX consolidado y unificado con soporte de LSP y compilador.

        Combina:
          1. Reglas nativas y sintaxis de Gram y GLang.
          2. Fragmentos cacheados de plugins cargados (compile_from).
          3. Metadatos de plugins activos en Plugins.registry.
          4. Reglas dinámicas y palabras clave del usuario.

        Returns:
            Path al archivo .vsix compilado.
        """
        if self._active_vsix and self._active_vsix.exists() and not force and output_path is None:
            return self._active_vsix

        unified_meta = extract_metadata(include_native=True)

        for fragment in self._fragments.values():
            unified_meta.merge(fragment)

        from gram.plugins.manager import Plugins
        active_plugins = list(Plugins.registry.values())
        if active_plugins:
            runtime_meta = extract_metadata(plugins=active_plugins, include_native=False)
            unified_meta.merge(runtime_meta)

        unified_meta.merge(self._user_metadata)

        if custom_extensions:
            for ext in custom_extensions:
                clean_ext = ext if ext.startswith(".") else f".{ext}"
                if clean_ext not in unified_meta.file_extensions:
                    unified_meta.file_extensions.append(clean_ext)

        if compiler_path:
            unified_meta.compiler_path = compiler_path
        if compiler_args:
            unified_meta.compiler_args = list(compiler_args)

        if output_path is not None:
            target_vsix = Path(output_path).resolve()
        else:
            target_vsix = self._get_temp_dir() / f"{self.EXTENSION_NAME}-{self.DEFAULT_VERSION}.vsix"

        build_dir = self._get_temp_dir() / "unified_extension_build"
        if build_dir.exists():
            shutil.rmtree(build_dir, ignore_errors=True)

        build_extension_directory(
            output_dir=build_dir,
            metadata=unified_meta,
            ext_id=self.EXTENSION_NAME,
            ext_name="Gram Language Support",
            publisher=self.PUBLISHER,
            version=self.DEFAULT_VERSION,
            compiler_path=unified_meta.compiler_path,
            compiler_args=unified_meta.compiler_args,
        )

        package_vsix(build_dir, output_vsix=target_vsix)
        self._active_vsix = target_vsix
        return target_vsix

    def install(self, vsix_path: str | Path | None = None) -> tuple[bool, str]:
        """
        Instala el paquete VSIX en Visual Studio Code mediante 'code --install-extension'.

        Args:
            vsix_path: Ruta al archivo .vsix. Si es None, compila automáticamente el actual.

        Returns:
            Tupla (éxito: bool, mensaje: str).
        """
        code_bin = find_vscode_executable()
        if not code_bin:
            return False, "Ejecutable de Visual Studio Code ('code') no encontrado en el sistema o PATH."

        target_file = Path(vsix_path).resolve() if vsix_path else self.compile()
        if not target_file.exists():
            return False, f"El archivo .vsix a instalar no existe: {target_file}"

        try:
            res = subprocess.run(
                [code_bin, "--install-extension", str(target_file), "--force"],
                capture_output=True,
                text=True,
                check=False,
            )
            if res.returncode == 0:
                return True, f"Extensión '{self.FULL_ID}' instalada exitosamente en VS Code desde {target_file.name}."
            else:
                err_msg = res.stderr.strip() or res.stdout.strip()
                return False, f"Fallo al instalar extensión en VS Code: {err_msg}"
        except Exception as exc:
            return False, f"Error durante la ejecución del instalador de VS Code: {exc}"

    def uninstall(self) -> tuple[bool, str]:
        """
        Desinstala la extensión de Gram en Visual Studio Code mediante 'code --uninstall-extension'.
        Utiliza el identificador universal constante 'gram.gram-language-support'.

        Returns:
            Tupla (éxito: bool, mensaje: str).
        """
        code_bin = find_vscode_executable()
        if not code_bin:
            return False, "Ejecutable de Visual Studio Code ('code') no encontrado en el sistema o PATH."

        try:
            res = subprocess.run(
                [code_bin, "--uninstall-extension", self.FULL_ID],
                capture_output=True,
                text=True,
                check=False,
            )
            if res.returncode == 0:
                return True, f"Extensión '{self.FULL_ID}' desinstalada exitosamente de VS Code."
            else:
                out_msg = res.stderr.strip() or res.stdout.strip()
                return False, f"Fallo al desinstalar extensión '{self.FULL_ID}': {out_msg}"
        except Exception as exc:
            return False, f"Error durante la desinstalación: {exc}"

    def is_installed(self) -> bool:
        """Verifica si la extensión oficial de Gram está instalada en Visual Studio Code."""
        code_bin = find_vscode_executable()
        if not code_bin:
            return False

        try:
            res = subprocess.run(
                [code_bin, "--list-extensions"],
                capture_output=True,
                text=True,
                check=False,
            )
            if res.returncode == 0:
                installed_ids = [line.strip().lower() for line in res.stdout.splitlines() if line.strip()]
                return self.FULL_ID.lower() in installed_ids
        except Exception:
            pass

        return False

    def list_installed(self) -> list[str]:
        """Retorna la lista de extensiones instaladas en VS Code que pertenezcan a Gram."""
        code_bin = find_vscode_executable()
        if not code_bin:
            return []

        gram_exts = []
        try:
            res = subprocess.run(
                [code_bin, "--list-extensions"],
                capture_output=True,
                text=True,
                check=False,
            )
            if res.returncode == 0:
                for line in res.stdout.splitlines():
                    name = line.strip()
                    if name.lower().startswith("gram.") or name.lower().startswith("gram-"):
                        gram_exts.append(name)
        except Exception:
            pass

        return gram_exts

    def compile_from(
        self,
        caller_file_or_path: str | Path | None = None,
        cache_dir: Path | str | None = None,
    ) -> Path:
        """
        Compila y cachea un paquete VSIX modular exclusivo para un plugin concreto.
        Se invoca típicamente en el `load()` del plugin:
            vsix.compile_from(__file__)
        """
        if caller_file_or_path is None:
            frame = inspect.currentframe()
            try:
                caller = frame.f_back if frame else None
                caller_file_or_path = caller.f_code.co_filename if caller else None
            finally:
                del frame

        if not caller_file_or_path:
            raise ValueError("No se pudo determinar el archivo de origen para compile_from().")

        raw_path = Path(caller_file_or_path).resolve()
        plugin_dir = raw_path if raw_path.is_dir() else raw_path.parent

        manifest_file = plugin_dir / "manifest.json"
        manifest_data: dict[str, Any] = {}
        if manifest_file.exists():
            try:
                manifest_data = json.loads(manifest_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        plugin_name = manifest_data.get("plugin_name") or plugin_dir.name
        version = manifest_data.get("version", "1.0.0")

        plugin_meta = SyntaxMetadata()

        from gram.plugins.manager import Plugins
        plugin_inst = Plugins.find(plugin_name)
        if plugin_inst:
            p_colors = getattr(plugin_inst, "colors", None)
            if isinstance(p_colors, PluginColors):
                for c_name, c_def in p_colors._colors.items():
                    plugin_meta.colors[c_name] = c_def
            try:
                p_grammar = plugin_inst.get_grammar()
                if isinstance(p_grammar, dict):
                    for r_item in p_grammar.keys():
                        if inspect.isclass(r_item) and issubclass(r_item, RuleItem):
                            comp = r_item.compile()
                            r_name = comp["name"]
                            plugin_meta.rules[r_name] = RuleMetadata(
                                name=r_name,
                                code=comp["code"],
                                description=comp["description"],
                                docs=comp["docs"],
                                colors=comp["colors"],
                                color=comp["color"],
                                scope=comp["scope"],
                                is_structural=comp["is_structural"],
                                suggestions=comp["suggestions"],
                                suggestions_autocomplete=comp.get("suggestions_autocomplete", True),
                                source_plugin=plugin_name,
                            )
            except Exception:
                pass

        if not plugin_meta.rules:
            glang_files = list(plugin_dir.glob("*.glang"))
            for gf in glang_files:
                try:
                    from gram.glang.reinterpreter import LanguageCompiler
                    compiler = LanguageCompiler.from_file(gf)
                    for r_item in compiler.grammar.keys():
                        if inspect.isclass(r_item) and issubclass(r_item, RuleItem):
                            comp = r_item.compile()
                            r_name = comp["name"]
                            plugin_meta.rules[r_name] = RuleMetadata(
                                name=r_name,
                                code=comp["code"],
                                description=comp["description"],
                                docs=comp["docs"],
                                colors=comp["colors"],
                                color=comp["color"],
                                scope=comp["scope"],
                                is_structural=comp["is_structural"],
                                suggestions=comp["suggestions"],
                                suggestions_autocomplete=comp.get("suggestions_autocomplete", True),
                                source_plugin=plugin_name,
                            )
                except Exception:
                    pass

        from gram.core.lexer.words import MAP_KEYWORDS
        for kw_name, kw_obj in MAP_KEYWORDS.items():
            if getattr(kw_obj, "_source_plugin", None) == plugin_name:
                plugin_meta.keywords[kw_name] = KeywordMetadata(
                    name=kw_name,
                    hex_color=getattr(kw_obj, "hex_color", "#FFFFFF") or "#FFFFFF",
                    group=getattr(kw_obj, "group", None),
                    description=getattr(kw_obj, "description", ""),
                    source_plugin=plugin_name,
                )

        self._fragments[plugin_name] = plugin_meta

        if cache_dir is not None:
            effective_cache_dir = Path(cache_dir).resolve()
        else:
            try:
                effective_cache_dir = plugin_dir / ".vsix_cache"
                effective_cache_dir.mkdir(parents=True, exist_ok=True)
            except OSError:
                effective_cache_dir = self._get_temp_dir() / "plugin_cache" / plugin_name
                effective_cache_dir.mkdir(parents=True, exist_ok=True)

        build_dir = effective_cache_dir / "build"
        target_vsix = effective_cache_dir / f"{plugin_name}-{version}.vsix"

        build_extension_directory(
            output_dir=build_dir,
            metadata=plugin_meta,
            ext_id=f"gram-plugin-{plugin_name}",
            ext_name=f"Gram Plugin: {plugin_name}",
            publisher="gram-plugin",
            version=version,
        )

        package_vsix(build_dir, output_vsix=target_vsix)
        self._plugin_vsix_cache[plugin_name] = target_vsix
        self._active_vsix = None

        return target_vsix

    def reload(self, output_path: str | Path | None = None) -> Path:
        """Recarga y recompila forzosamente el paquete VSIX unificado."""
        return self.compile(output_path=output_path, force=True)

    def clear(self) -> None:
        """Limpia el estado interno y elimina archivos temporales generados."""
        self._fragments.clear()
        self._plugin_vsix_cache.clear()
        self._user_metadata = SyntaxMetadata()

        if self._active_vsix and self._active_vsix.exists():
            try:
                self._active_vsix.unlink()
            except OSError:
                pass
        self._active_vsix = None

        if self._temp_dir and self._temp_dir.exists():
            shutil.rmtree(self._temp_dir, ignore_errors=True)
            self._temp_dir = None


manager = VsixManager()

__all__ = [
    "VsixManager",
    "manager",
    "find_vscode_executable",
]
