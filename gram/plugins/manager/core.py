"""
Gestor de Ciclo de Vida y Procesamiento de Plugins para Gram.
=============================================================
Orquesta la inicialización, seguridad, resolución de dependencias y ejecución
de plugins bajo el contrato formal ``PluginBase``:

  - Aprobación del usuario antes de cualquier ejecución de código de plugin.
  - Auditoría estática AST antes de importar el módulo.
  - Instalación del hook de auditoría de CPython al primer uso.
  - Registro automático de keywords, WordGroups y tokens en el Lexer.
  - Registro de combinadores (Custom Mods) y reglas gramaticales.
  - Inyección dinámica de reglas en ``DECLARATION`` (``apply_to_grammar``).
  - Transformaciones y validaciones de AST en pipeline.

Contrato único: los plugins DEBEN subclasificar ``PluginBase`` en ``main.py``.
No se soportan módulos de funciones sueltas.
"""
from __future__ import annotations

import importlib
import importlib.util
import json
import shutil
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, ClassVar

import gram
from gram import config, errors
from gram.core.combinators.alternative import Alt
from gram.core.combinators.base import Combinator, RuleItem
from gram.core.combinators.mods import register_custom_mod
from gram.core.combinators.reference import Ref
from gram.core.lexer import words
from gram.native.rules import DECLARATION
from gram.plugins import registry
from gram.plugins.base import PluginBase
from gram.plugins.colors import PluginColors
from gram.plugins.environment import install_plugin_requirements
from gram.plugins.manager.manifest_processor import ManifestProcessor
from gram.plugins.manifest import PluginManifest, match_semver, parse_manifest
from gram.plugins.permissions import PluginNotApprovedError, PluginPermissions, require_approval
from gram.plugins.security import audit_plugin_directory, install_audit_hook
from gram.utilities import error


def get_plugins_dir() -> Path:
    """
    Ruta absoluta al directorio base de plugins de Gram.

    Prioridad:
      1. ``config.PLUGINS_DIR`` (si está configurado).
      2. ``gram/plugins/source/`` por defecto.
    """
    if hasattr(config, "PLUGINS_DIR") and getattr(config, "PLUGINS_DIR"):
        p = Path(getattr(config, "PLUGINS_DIR")).resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p

    gram_dir = Path(gram.__file__).resolve().parent
    source_dir = gram_dir / "plugins" / "source"
    source_dir.mkdir(parents=True, exist_ok=True)
    return source_dir


class Plugin:
    """
    Instancia activa de un plugin cargado en el runtime de Gram.

    Gestiona su ciclo de vida completo:
      1. Localización y parsing del manifest.
      2. Auditoría estática de seguridad (AST).
      3. Aprobación del usuario final.
      4. Instalación de dependencias Python (si las hay).
      5. Importación del módulo y vinculación de la subclase de ``PluginBase``.
      6. Auto-registro en el Lexer, Combinators y Gramática de Gram.
    """

    def __init__(
        self,
        target: str | Path,
        auto_load: bool = True,
        interactive: bool = True,
    ) -> None:
        self.name: str = ""
        self.uuid: str = ""
        self.plugin_path: Path = Path()
        self.manifest: PluginManifest | None = None
        self.colors: PluginColors | None = None
        self.module: ModuleType | None = None
        self.instance: PluginBase | None = None
        self.dependencies: dict[str, Plugin] = {}
        self.is_loaded: bool = False
        self.load_result: Any = None
        self._interactive: bool = interactive

        # Instalar hook de auditoría de CPython al primer uso del sistema
        install_audit_hook()

        self._resolve(target)
        if auto_load:
            self.load()

    # -------------------------------------------------------------------------
    # Resolución física
    # -------------------------------------------------------------------------

    def _resolve(self, target: str | Path) -> None:
        """Localiza el directorio del plugin y parsea su manifest."""
        plugins_base = get_plugins_dir()

        direct_path = Path(target) if isinstance(target, (Path, str)) else None
        if direct_path and (direct_path.exists() or "/" in str(target) or "\\" in str(target)):
            path = direct_path.resolve()
        else:
            name = str(target).strip()
            if name.startswith("plugins."):
                name = name[len("plugins."):]

            candidate = (plugins_base / name).resolve()
            if candidate.exists() and candidate.is_dir():
                path = candidate
            else:
                found_path: Path | None = None
                if plugins_base.exists():
                    for item in plugins_base.iterdir():
                        if item.is_dir() and (item / "manifest.json").exists():
                            try:
                                m_data = json.loads(
                                    (item / "manifest.json").read_text(encoding="utf-8")
                                )
                                if m_data.get("plugin_name") == name or m_data.get("uuid") == name:
                                    found_path = item
                                    break
                            except Exception:
                                pass

                if found_path is not None:
                    path = found_path
                else:
                    error.GrammarError(
                        "Plugin no encontrado",
                        errors.PLUGIN_NOT_FOUND,
                        f"No se encontró el directorio del plugin: {candidate}",
                        f"Verifique que el plugin '{target}' exista en {plugins_base}.",
                    ).raise_error()

        manifest_file = path / "manifest.json"
        res = ManifestProcessor.process(manifest_file, require_main=True, load_colors=True)
        self.manifest = res.manifest
        self.name = self.manifest.plugin_name
        self.uuid = self.manifest.uuid
        self.plugin_path = path
        self.colors = res.colors

    # -------------------------------------------------------------------------
    # Dependencias
    # -------------------------------------------------------------------------

    def load_dependencies(self) -> None:
        """
        Carga recursivamente las dependencias declaradas en el manifest.

        Verifica compatibilidad SemVer y previene ciclos de carga.
        """
        if not self.manifest or not self.manifest.requests:
            return

        if registry.is_loading(self.name):
            return

        registry.enter_loading(self.name)
        try:
            for req in self.manifest.requests:
                canonical = req.canonical_name()

                local_ver = self.plugin_path / "versions" / canonical
                if local_ver.exists() and local_ver.is_dir():
                    dep = Plugin(local_ver, auto_load=True, interactive=self._interactive)
                elif registry.has_plugin(canonical):
                    dep = registry.get_plugin(canonical)  # type: ignore[assignment]
                else:
                    dep = Plugin(canonical, auto_load=True, interactive=self._interactive)

                if dep and dep.manifest:
                    if not match_semver(dep.manifest.version, req.min_version):
                        registry.record_error(self.name, f"Versión incompatible de '{req.name}'")
                        error.PluginError(
                            "Versión de requerimiento incompatible",
                            errors.PLUGIN_DEPENDENCY_VERSION_MISMATCH,
                            f"Versión incompatible de '{req.name}' en '{self.name}'. "
                            f"Se requiere '{req.min_version_str}', se encontró '{dep.manifest.version_str}'.",
                        ).raise_error()

                self.dependencies[canonical] = dep  # type: ignore[assignment]
        finally:
            registry.exit_loading(self.name)

    # -------------------------------------------------------------------------
    # Carga principal
    # -------------------------------------------------------------------------

    def load(self) -> Any:
        """
        Ejecuta el ciclo de carga completo del plugin:

        1. Carga dependencias recursivas.
        2. Audita estáticamente el código fuente (AST).
        3. Solicita aprobación del usuario final.
        4. Instala dependencias Python declaradas en el manifest.
        5. Importa ``main.py`` y vincula la subclase de ``PluginBase``.
        6. Valida capacidades declaradas.
        7. Invoca ``on_load()``.
        8. Auto-registra extensiones (keywords, grupos, combinadores).
        """
        if self.is_loaded:
            return self.load_result

        # 1. Dependencias
        self.load_dependencies()

        # 2. Auditoría estática de seguridad
        security_issues = audit_plugin_directory(self.plugin_path)
        has_errors = any(
            getattr(issue, "level", "") == "ERROR" for issue in security_issues
        )
        allow_all = getattr(config, "PLUGINS_ALLOW_ALL_PLUGINS", False)

        if has_errors and not allow_all:
            formatted = "\n  ".join(
                issue.format_line() if hasattr(issue, "format_line") else str(issue)
                for issue in security_issues
                if getattr(issue, "level", "") == "ERROR"
            )
            error.PluginError(
                "Auditoría de seguridad fallida",
                errors.PLUGIN_PROTECTED_VIOLATION,
                f"El plugin '{self.name}' no superó la auditoría de seguridad:\n  {formatted}",
                "Corrija los problemas indicados o contacte al autor del plugin.",
            ).raise_error()

        # 3. Aprobación del usuario final
        if self.manifest:
            try:
                require_approval(
                    self.manifest,
                    security_issues=security_issues,
                    interactive=self._interactive,
                )
            except PluginNotApprovedError as exc:
                error.PluginError(
                    "Plugin no aprobado",
                    errors.PLUGIN_CONFIG_MUTATION_DENIED,
                    str(exc),
                    "Use PluginPermissions.approve(manifest) o apruébelo interactivamente.",
                ).raise_error()

        # Registrar en estado de carga
        registry.set_current_loading(self.name)
        registry.register_plugin(self)
        Plugins.registry[self.name] = self

        # 4. Instalar dependencias Python declaradas
        if self.manifest and self.manifest.python_lib_requests:
            try:
                install_plugin_requirements(self.manifest)
            except Exception as exc:
                registry.unregister_plugin(self.name)
                Plugins.registry.pop(self.name, None)
                registry.set_current_loading(None)
                raise exc

        # 5. Importar main.py
        folder_alias = self.plugin_path.name
        pkg_name = f"gram.plugins.{folder_alias}"

        # Registrar el paquete en sys.modules para imports relativos
        if pkg_name not in sys.modules:
            init_path = self.plugin_path / "__init__.py"
            pkg_spec = importlib.util.spec_from_file_location(
                pkg_name,
                str(init_path) if init_path.exists() else None,
                submodule_search_locations=[str(self.plugin_path)],
            )
            if pkg_spec and pkg_spec.loader:
                pkg_mod = importlib.util.module_from_spec(pkg_spec)
                sys.modules[pkg_name] = pkg_mod
                try:
                    pkg_spec.loader.exec_module(pkg_mod)
                except Exception:
                    pass
            elif pkg_spec:
                pkg_mod = importlib.util.module_from_spec(pkg_spec)
                sys.modules[pkg_name] = pkg_mod

        main_file = self.plugin_path / "main.py"
        if not main_file.exists():
            registry.unregister_plugin(self.name)
            Plugins.registry.pop(self.name, None)
            registry.set_current_loading(None)
            error.GrammarError(
                "Punto de entrada no encontrado",
                errors.PLUGIN_MAIN_NOT_FOUND,
                f"El plugin '{self.name}' no contiene 'main.py' en: {main_file}",
            ).raise_error()

        mod_name = f"{pkg_name}.main"
        if mod_name in sys.modules:
            module = sys.modules[mod_name]
        else:
            spec = importlib.util.spec_from_file_location(mod_name, str(main_file))
            if spec is None or spec.loader is None:
                registry.unregister_plugin(self.name)
                Plugins.registry.pop(self.name, None)
                registry.set_current_loading(None)
                error.GrammarError(
                    "Cargador de plugin inválido",
                    errors.PLUGIN_MANIFEST_INVALID,
                    f"No se pudo crear el cargador para '{self.name}'.",
                ).raise_error()

            module = importlib.util.module_from_spec(spec)
            sys.modules[mod_name] = module
            try:
                spec.loader.exec_module(module)
            except Exception as exc:
                sys.modules.pop(mod_name, None)
                registry.unregister_plugin(self.name)
                Plugins.registry.pop(self.name, None)
                registry.set_current_loading(None)
                registry.record_error(self.name, str(exc))
                raise exc

        self.module = module

        # 5b. Localizar subclase de PluginBase
        plugin_instance: PluginBase | None = None
        for attr_name in dir(module):
            val = getattr(module, attr_name, None)
            if isinstance(val, type) and issubclass(val, PluginBase) and val is not PluginBase:
                plugin_instance = val(manifest=self.manifest, plugin_path=self.plugin_path)
                break
            elif isinstance(val, PluginBase):
                plugin_instance = val
                break

        if plugin_instance is None:
            registry.unregister_plugin(self.name)
            Plugins.registry.pop(self.name, None)
            registry.set_current_loading(None)
            error.GrammarError(
                "Clase de plugin no encontrada",
                errors.PLUGIN_MAIN_NOT_FOUND,
                f"El plugin '{self.name}' no define una subclase de PluginBase en main.py.",
                "Crea una clase que herede de PluginBase y defínela en main.py.",
            ).raise_error()

        self.instance = plugin_instance

        # 6. Validar capacidades declaradas
        if self.manifest:
            caps = self.manifest.capabilities
            if caps.load and not hasattr(self.instance, "on_load"):
                registry.set_current_loading(None)
                error.GrammarError(
                    "Capacidad load() no implementada",
                    errors.PLUGIN_CAPABILITY_MISSING,
                    f"El plugin '{self.name}' declara 'load: true' pero no implementa on_load().",
                ).raise_error()

            if caps.process and not hasattr(self.instance, "process"):
                registry.set_current_loading(None)
                error.GrammarError(
                    "Capacidad process() no implementada",
                    errors.PLUGIN_CAPABILITY_MISSING,
                    f"El plugin '{self.name}' declara 'process: true' pero no implementa process().",
                ).raise_error()

        # 7. Invocar on_load()
        result: Any = None
        if self.manifest and self.manifest.capabilities.load:
            try:
                result = self.instance.on_load()  # type: ignore[union-attr]
            except error.Error:
                registry.set_current_loading(None)
                raise
            except Exception as exc:
                registry.set_current_loading(None)
                registry.record_error(self.name, str(exc))
                error.GrammarError(
                    "Fallo en carga de plugin",
                    errors.PLUGIN_LOADED_ERROR,
                    f"Error durante on_load() en '{self.name}': {exc}",
                ).raise_error()

            if result is False:
                registry.set_current_loading(None)
                registry.record_error(self.name, "on_load() retornó False")
                error.GrammarError(
                    "Fallo en carga de plugin",
                    errors.PLUGIN_LOADED_ERROR,
                    f"on_load() del plugin '{self.name}' retornó False.",
                ).raise_error()

        # 8. Auto-registro en Gram
        self._register_extensions()

        self.is_loaded = True
        self.load_result = result
        registry.register_plugin(self)
        registry.record_load_order(self.name)
        registry.set_current_loading(None)

        return result

    # -------------------------------------------------------------------------
    # Auto-registro de extensiones léxicas y sintácticas
    # -------------------------------------------------------------------------

    def _register_extensions(self) -> None:
        """Registra combinadores, keywords y grupos en los catálogos de Gram."""
        if self.instance is None:
            return

        # Combinadores custom
        for comb in self.instance.get_combinators():
            if isinstance(comb, type) or hasattr(comb, "parse"):
                register_custom_mod(comb)

        # Keywords
        for kw_item in self.instance.get_keywords():
            try:
                if hasattr(kw_item, "name"):
                    words.add_keyword(
                        name=kw_item.name,
                        hex_color=getattr(kw_item, "hex_color", None),
                        group=getattr(kw_item, "group", None),
                        description=getattr(kw_item, "description", None),
                    )
                elif isinstance(kw_item, str):
                    words.add_keyword(kw_item)
                elif isinstance(kw_item, tuple):
                    k_name = kw_item[0]
                    k_color = kw_item[1] if len(kw_item) > 1 else None
                    k_group = kw_item[2] if len(kw_item) > 2 else None
                    words.add_keyword(k_name, hex_color=k_color, group=k_group)
            except Exception:
                pass

        # Word groups
        for grp_name, grp_words in self.instance.get_word_groups().items():
            try:
                words.add_group(grp_name, grp_words)
            except Exception:
                pass

    # -------------------------------------------------------------------------
    # Puntos de extensión (solo desde la instancia de PluginBase)
    # -------------------------------------------------------------------------

    def get_keywords(self) -> list[Any]:
        """Palabras clave expuestas por el plugin."""
        return self.instance.get_keywords() if self.instance else []

    def get_word_groups(self) -> dict[str, list[str]]:
        """Grupos de palabras expuestos por el plugin."""
        return self.instance.get_word_groups() if self.instance else {}

    def get_tokens(self) -> list[Any]:
        """Tokens personalizados expuestos por el plugin."""
        return self.instance.get_tokens() if self.instance else []

    def get_combinators(self) -> list[Any]:
        """Combinadores expuestos por el plugin."""
        return self.instance.get_combinators() if self.instance else []

    def get_rules(self) -> list[Any]:
        """Reglas sintácticas expuestas por el plugin."""
        return self.instance.get_rules() if self.instance else []

    def compile_glang(self, filepath: str | Path | None = None) -> dict[Any, Any]:
        """
        Compila el archivo .glang del plugin (o un archivo específico) a combinadores ejecutables.
        Almacena la gramática resultante en self._compiled_grammar y self._compiler.
        """
        import gram.glang
        if filepath is not None:
            fpath = Path(filepath)
            if not fpath.is_file() and self.plugin_path:
                cand = self.plugin_path / fpath
                if cand.is_file():
                    fpath = cand
            compiler = gram.glang.LanguageCompiler.from_file(fpath)
            self._compiled_grammar = compiler.grammar
            self._compiler = compiler
            self._glang_file = fpath
            return self._compiled_grammar

        glang_files = list(self.plugin_path.glob("*.glang")) if self.plugin_path else []
        if not glang_files:
            error.GrammarError(
                "Archivo .glang no encontrado",
                errors.PLUGIN_MANIFEST_INVALID,
                f"No se encontró ningún archivo .glang en el directorio del plugin '{self.name}'.",
            ).raise_error()

        compiler = gram.glang.LanguageCompiler.from_file(glang_files[0])
        self._compiled_grammar = compiler.grammar
        self._compiler = compiler
        self._glang_file = glang_files[0]
        return self._compiled_grammar

    def get_grammar(self) -> dict[Any, Any]:
        """
        Retorna la gramática formal expuesta por el plugin:
        - Si existe self._compiled_grammar, la retorna.
        - Si self.instance implementa get_grammar() y retorna dict no vacío, lo retorna.
        - Si existe un archivo .glang en el directorio del plugin, intenta compilarlo con compile_glang().
        """
        if hasattr(self, "_compiled_grammar") and self._compiled_grammar is not None:
            return self._compiled_grammar

        if self.instance:
            g = self.instance.get_grammar()
            if g:
                return g

        if self.plugin_path and self.plugin_path.exists():
            glang_files = list(self.plugin_path.glob("*.glang"))
            if glang_files:
                try:
                    return self.compile_glang(glang_files[0])
                except Exception:
                    pass

        return {}

    def extend_declarations(self) -> list[Any]:
        """Reglas a inyectar en ``DECLARATION``."""
        if self.instance:
            explicit = self.instance.extend_declarations()
            if explicit:
                return list(explicit)
        return []

    def extend_grammar(self, base_grammar: dict[Any, Any]) -> dict[Any, Any]:
        """
        Enriquece un diccionario de gramática base con las reglas del plugin.

        1. Incorpora todas las reglas de ``get_grammar()``.
        2. Agrega ``RuleItem`` con gramática propia.
        3. Inyecta las declaraciones en ``DECLARATION``.
        """
        new_grammar = dict(base_grammar)

        for rule_key, rule_val in self.get_grammar().items():
            new_grammar[rule_key] = rule_val

        for r in self.get_rules():
            if isinstance(r, type) and issubclass(r, RuleItem):
                if getattr(r, "grammar", None) is not None:
                    new_grammar[r] = r.grammar

        extensions = self.extend_declarations()
        if extensions and DECLARATION in new_grammar:
            current_decl = new_grammar[DECLARATION]
            if isinstance(current_decl, Alt):
                existing_args = list(current_decl.combinators)
                for item in extensions:
                    ref_item = Ref(item) if not isinstance(item, Combinator) else item
                    if ref_item not in existing_args:
                        existing_args.append(ref_item)
                new_grammar[DECLARATION] = Alt(*existing_args)

        return new_grammar

    def transform_ast(self, ast: Any) -> Any:
        """Aplica la transformación de AST del plugin."""
        return self.instance.transform_ast(ast) if self.instance else ast

    def validate_ast(self, ast: Any) -> list[Any]:
        """Ejecuta validaciones de AST del plugin."""
        return self.instance.validate_ast(ast) if self.instance else []

    def process(self, *args: Any, **kwargs: Any) -> Any:
        """Ejecuta el procesamiento del plugin."""
        if not self.is_loaded:
            self.load()

        if self.instance is None:
            error.GrammarError(
                "Plugin no inicializado",
                errors.PLUGIN_CAPABILITY_MISSING,
                f"El plugin '{self.name}' no tiene una instancia activa de PluginBase.",
            ).raise_error()

        try:
            return self.instance.process(*args, **kwargs)  # type: ignore[union-attr]
        except error.Error:
            raise
        except Exception as exc:
            error.GrammarError(
                "Fallo en procesamiento de plugin",
                errors.PLUGIN_PROCESSED_ERROR,
                f"Error durante process() en '{self.name}': {exc}",
            ).raise_error()

    def cli(self, *args: Any, **kwargs: Any) -> Any:
        """Ejecuta la interfaz CLI del plugin."""
        if not self.is_loaded:
            self.load()
        return self.instance.cli(*args, **kwargs) if self.instance else None

    def get_colors(self) -> PluginColors | None:
        """Paleta de colores declarada por el plugin."""
        return self.colors

    def unload(self) -> None:
        """Descarga el plugin liberando sus módulos e invocando ``on_unload()``."""
        if self.instance:
            try:
                self.instance.on_unload()
            except Exception:
                pass

        registry.unregister_plugin(self.name)
        Plugins.registry.pop(self.name, None)

        if self.plugin_path:
            folder_alias = self.plugin_path.name
            sys.modules.pop(f"gram.plugins.{folder_alias}.main", None)
            sys.modules.pop(f"gram.plugins.{folder_alias}", None)
            pycache_dir = self.plugin_path / "__pycache__"
            if pycache_dir.exists():
                shutil.rmtree(pycache_dir, ignore_errors=True)
            importlib.invalidate_caches()

        self.is_loaded = False
        self.load_result = None
        self.instance = None


# =============================================================================
# Fachada de alto nivel: Plugins
# =============================================================================

class Plugins:
    """
    Controlador principal y fachada de alto nivel del gestor de plugins de Gram.

    Todas las operaciones de carga respetan el flujo de seguridad completo:
    auditoría estática → aprobación de usuario → carga de módulo.
    """

    registry: ClassVar[dict[str, Plugin]] = {}

    @classmethod
    def load(
        cls,
        target: str | Path,
        auto_load: bool = True,
        interactive: bool = True,
    ) -> Plugin:
        """Carga o recupera un plugin por nombre o ruta."""
        if isinstance(target, str):
            existing = cls.find(target)
            if existing:
                return existing
        elif isinstance(target, Path):
            p_res = target.resolve()
            for p_inst in registry.all_plugins():
                if p_inst.plugin_path.resolve() == p_res:
                    return p_inst

        plugin = Plugin(target, auto_load=auto_load, interactive=interactive)
        cls.registry[plugin.name] = plugin
        return plugin

    @classmethod
    def get(cls, name_or_uuid: str) -> Plugin | None:
        """Obtiene un plugin cargado desde el registro."""
        return registry.get_plugin(name_or_uuid)

    @classmethod
    def find(cls, target: str) -> Plugin | None:
        """Busca un plugin por nombre, UUID o nombre de carpeta."""
        if registry.has_plugin(target):
            return registry.get_plugin(target)
        for p in registry.all_plugins():
            if p.name == target or p.uuid == target or (
                p.plugin_path and p.plugin_path.name == target
            ):
                return p
        return None

    @classmethod
    def all(cls) -> list[Plugin]:
        """Retorna todos los plugins registrados."""
        return registry.all_plugins()

    @classmethod
    def process(cls, target: str | Path, *args: Any, **kwargs: Any) -> Any:
        """Invoca ``process()`` del plugin especificado."""
        plugin = cls.find(str(target)) if isinstance(target, str) else None
        if plugin is None:
            plugin = cls.load(target, auto_load=True)
        return plugin.process(*args, **kwargs)

    @classmethod
    def cli(cls, plugin_name: str, *args: Any, **kwargs: Any) -> Any:
        """Invoca ``cli()`` del plugin especificado."""
        plugin = cls.load(plugin_name, auto_load=True)
        return plugin.cli(*args, **kwargs)

    @classmethod
    def discover(cls, dir_path: Path | None = None) -> list[PluginManifest]:
        """
        Descubre e inspecciona todos los plugins válidos en un directorio.

        Returns:
            Lista de ``PluginManifest`` encontrados.
        """
        base = dir_path if dir_path is not None else get_plugins_dir()
        manifests: list[PluginManifest] = []
        if base.exists() and base.is_dir():
            for item in base.iterdir():
                if item.is_dir() and (item / "manifest.json").exists():
                    try:
                        m = parse_manifest(item / "manifest.json")
                        manifests.append(m)
                    except Exception:
                        pass
        return manifests

    @classmethod
    def reload(
        cls,
        target: str | Path,
        interactive: bool = True,
    ) -> Plugin:
        """Recarga un plugin desde disco invalidando la caché de importación."""
        existing: Plugin | None = None
        if isinstance(target, str) and registry.has_plugin(target):
            existing = registry.get_plugin(target)
        elif isinstance(target, Path):
            p_res = target.resolve()
            for p_inst in registry.all_plugins():
                if p_inst.plugin_path.resolve() == p_res:
                    existing = p_inst
                    break

        if existing:
            target_path = existing.plugin_path
            existing.unload()
            target = target_path

        return cls.load(target, auto_load=True, interactive=interactive)

    @classmethod
    def unload(cls, target: str | Path) -> None:
        """Descarga un plugin del sistema."""
        plugin = cls.find(str(target)) if isinstance(target, str) else None
        if plugin:
            plugin.unload()

    # =========================================================================
    # Integración en el pipeline de Gram
    # =========================================================================

    @classmethod
    def apply_to_grammar(
        cls,
        grammar: dict[Any, Any],
        plugins: list[str | Plugin] | None = None,
    ) -> dict[Any, Any]:
        """
        Enriquece una gramática con las reglas y declaraciones de los plugins.

        Args:
            grammar: Diccionario de gramática base de Gram.
            plugins: Lista de plugins a usar. Si ``None``, usa todos los cargados.

        Returns:
            Nueva gramática extendida.
        """
        target_plugins: list[Plugin] = (
            registry.all_plugins()
            if plugins is None
            else [
                p if isinstance(p, Plugin) else cls.load(p, auto_load=True)
                for p in plugins
            ]
        )

        current = dict(grammar)
        for plug in target_plugins:
            current = plug.extend_grammar(current)
        return current

    @classmethod
    def transform_ast(
        cls,
        ast: Any,
        plugins: list[str | Plugin] | None = None,
    ) -> Any:
        """
        Ejecuta los transformadores de AST de todos los plugins activos en cadena.
        """
        target_plugins: list[Plugin] = (
            registry.all_plugins()
            if plugins is None
            else [
                p if isinstance(p, Plugin) else cls.load(p, auto_load=True)
                for p in plugins
            ]
        )

        current_ast = ast
        for plug in target_plugins:
            current_ast = plug.transform_ast(current_ast)
        return current_ast

    @classmethod
    def validate_ast(
        cls,
        ast: Any,
        plugins: list[str | Plugin] | None = None,
    ) -> dict[str, list[Any]]:
        """
        Ejecuta las validaciones de AST de todos los plugins activos.

        Returns:
            Diccionario ``{nombre_plugin: [diagnósticos]}``.
        """
        target_plugins: list[Plugin] = (
            registry.all_plugins()
            if plugins is None
            else [
                p if isinstance(p, Plugin) else cls.load(p, auto_load=True)
                for p in plugins
            ]
        )

        diagnostics: dict[str, list[Any]] = {}
        for plug in target_plugins:
            diags = plug.validate_ast(ast)
            if diags:
                diagnostics[plug.name] = diags
        return diagnostics


__all__ = [
    "Plugin",
    "Plugins",
    "get_plugins_dir",
]
