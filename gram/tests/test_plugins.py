"""
Pruebas Unitarias del Subsistema de Plugins (`gram.tests.test_plugins`).
========================================================================
Valida exhaustivamente:
  1. Manifest: parsing, SemVer, generación de UUID.
  2. Colores: definiciones, conversiones, rechazo de canal alfa (OSGDC).
  3. Registro en memoria: ciclo de vida, colisiones, errores.
  4. Seguridad estática (AST): importaciones no autorizadas, dunders, eval/exec.
  5. Permisos: aprobación, revocación, persistencia.
  6. Entorno: lista blanca de librerías, protección de escritura desde plugins.
  7. Extensiones de procesamiento de Gram:
     - Registro dinámico de Keywords y WordGroups en el Lexer.
     - Registro de Custom Combinators.
     - Inyección de reglas en DECLARATION (apply_to_grammar).
     - Pipeline de transformación y validación de AST.
  8. Validación estática previa (validate_plugin) con auditoría real.
"""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from gram import config, errors
from gram.core.ast.nodes import ASTNode, ASTProgram
from gram.core.combinators import Alt, Many, MatchKeyword, MatchToken, Ref, RuleItem, Seq
from gram.core.combinators.mods import is_custom_mod
from gram.core.lexer import Token, TokenType, words
from gram.plugins import (
    ColorDefinition,
    Plugin,
    PluginBase,
    PluginColors,
    PluginManifest,
    PluginPermissions,
    Plugins,
    SecurityIssue,
    audit_python_code,
    format_version,
    generate_uuid,
    get_plugins_dir,
    match_semver,
    parse_colors,
    parse_manifest,
    parse_semver,
    parse_version_tuple,
    registry,
    validate_plugin,
)
from gram.plugins.environment import (
    allow_add,
    allow_list,
    allow_remove,
    is_library_allowed,
    reset_allowed_libraries,
)
from gram.plugins.permissions import PluginNotApprovedError, require_approval
from gram.native.rules import DECLARATION, PROGRAM
from gram.utilities.error import GrammarError, PluginError


# ---------------------------------------------------------------------------
# Caso base con aislamiento
# ---------------------------------------------------------------------------

class BasePluginTestCase(unittest.TestCase):
    """Caso base con aislamiento de registro, configuración y permisos."""

    def setUp(self) -> None:
        self.old_hide_console = config.ERROR_HIDE_CONSOLE
        self.old_exit_on_error = config.ERROR_EXIT_ON_ERROR
        config.ERROR_HIDE_CONSOLE = True
        config.ERROR_EXIT_ON_ERROR = False

        # Modo permisivo: los plugins no requieren aprobación interactiva en tests
        self.old_allow_all = getattr(config, "PLUGINS_ALLOW_ALL_PLUGINS", False)
        config.PLUGINS_ALLOW_ALL_PLUGINS = True

        self.temp_dir = tempfile.mkdtemp()
        self.old_data_dir = getattr(config, "DATA_DIR", None)
        config.DATA_DIR = self.temp_dir

        words.clear_all()
        registry.clear()
        Plugins.registry.clear()
        reset_allowed_libraries()

    def tearDown(self) -> None:
        config.ERROR_HIDE_CONSOLE = self.old_hide_console
        config.ERROR_EXIT_ON_ERROR = self.old_exit_on_error
        config.PLUGINS_ALLOW_ALL_PLUGINS = self.old_allow_all
        config.DATA_DIR = self.old_data_dir

        words.clear_all()
        registry.clear()
        Plugins.registry.clear()
        reset_allowed_libraries()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def create_mock_plugin(
        self,
        folder_name: str,
        manifest_data: dict[str, Any],
        main_py_code: str,
        init_py_code: str = "",
        colors_data: dict[str, Any] | None = None,
    ) -> Path:
        """Crea un plugin temporal en disco para pruebas aisladas."""
        plugin_path = Path(self.temp_dir) / folder_name
        plugin_path.mkdir(parents=True, exist_ok=True)

        (plugin_path / "manifest.json").write_text(
            json.dumps(manifest_data, indent=2), encoding="utf-8"
        )
        (plugin_path / "main.py").write_text(main_py_code, encoding="utf-8")
        (plugin_path / "__init__.py").write_text(init_py_code, encoding="utf-8")

        if colors_data is not None:
            (plugin_path / "colors.json").write_text(
                json.dumps(colors_data, indent=2), encoding="utf-8"
            )

        return plugin_path


# ---------------------------------------------------------------------------
# 1. Manifest y SemVer
# ---------------------------------------------------------------------------

class TestPluginManifestAndVersions(BasePluginTestCase):
    """Pruebas para el procesador de manifiestos y utilidades SemVer."""

    def test_version_parsing_and_formatting(self) -> None:
        self.assertEqual(parse_version_tuple([1, 20, 3]), (1, 20, 3))
        self.assertEqual(parse_version_tuple((2, 0)), (2, 0))
        self.assertEqual(parse_version_tuple(10), (10,))
        self.assertEqual(parse_version_tuple("v2.1.0"), (2, 1, 0))
        self.assertEqual(parse_version_tuple("1.5"), (1, 5))
        self.assertEqual(format_version((1, 2, 3)), "1.2.3")
        self.assertEqual(format_version("v1.0.0"), "1.0.0")

    def test_semver_matching(self) -> None:
        self.assertTrue(match_semver("1.2.3", "1.2.3"))
        self.assertTrue(match_semver("1.2.0", "1.2.x"))
        self.assertTrue(match_semver("1.2.5", "*"))
        self.assertTrue(match_semver("2.0.0", ">=1.0.0"))
        self.assertFalse(match_semver("0.9.0", ">=1.0.0"))
        self.assertFalse(match_semver("1.2.0", "1.3.x"))

    def test_generate_uuid(self) -> None:
        u1 = generate_uuid()
        u2 = generate_uuid()
        self.assertEqual(len(u1), 36)
        self.assertNotEqual(u1, u2)

        det1 = generate_uuid("plugin_sample")
        det2 = generate_uuid("plugin_sample")
        self.assertEqual(det1, det2)

    def test_parse_manifest_valid(self) -> None:
        path = self.create_mock_plugin(
            "valid_plugin",
            {
                "plugin_name": "valid_plugin",
                "version": [1, 2, 0],
                "author": "Test Author",
                "description": "A test plugin",
                "capabilities": {"load": True, "process": True},
            },
            "from gram.plugins.base import PluginBase\nclass P(PluginBase): pass\n",
        )
        manifest = parse_manifest(path / "manifest.json")
        self.assertEqual(manifest.plugin_name, "valid_plugin")
        self.assertEqual(manifest.version, (1, 2, 0))
        self.assertEqual(manifest.version_str, "1.2.0")
        self.assertEqual(manifest.author, "Test Author")
        self.assertTrue(manifest.capabilities.load)
        self.assertTrue(manifest.capabilities.process)

    def test_parse_manifest_missing_name_raises(self) -> None:
        p = Path(self.temp_dir) / "invalid_manifest.json"
        p.write_text('{"version": "1.0.0"}', encoding="utf-8")
        with self.assertRaises(GrammarError):
            parse_manifest(p)


# ---------------------------------------------------------------------------
# 2. Colores
# ---------------------------------------------------------------------------

class TestPluginColors(BasePluginTestCase):
    """Pruebas para el subsistema de colores y esquemas de resaltado."""

    def test_color_definition_and_conversions(self) -> None:
        color = ColorDefinition("KEYWORD", 255, 128, 0)
        self.assertEqual(color.name, "KEYWORD")
        self.assertEqual(color.rgb, (255, 128, 0))
        self.assertEqual(color.hex, "#FF8000")
        self.assertIn("255;128;0", color.to_ansi())
        self.assertIn("test", color.colorize("test"))
        tm = color.to_textmate()
        self.assertEqual(tm["settings"]["foreground"], "#FF8000")

    def test_parse_colors_from_dict(self) -> None:
        palette = {
            "KEYWORD": "#00FF00",
            "IDENT": [50, 100, 150],
            "STRING": "#E06C75",
        }
        colors = parse_colors(palette)
        self.assertEqual(len(colors), 3)
        self.assertEqual(colors["KEYWORD"].hex, "#00FF00")
        self.assertEqual(colors["IDENT"].rgb, (50, 100, 150))
        self.assertEqual(colors["STRING"].hex, "#E06C75")

    def test_parse_colors_rejects_alpha_channel(self) -> None:
        with self.assertRaises(GrammarError):
            parse_colors({"INVALID": [255, 0, 0, 128]})
        with self.assertRaises(GrammarError):
            parse_colors({"INVALID": "#FF000080"})


# ---------------------------------------------------------------------------
# 3. Registro
# ---------------------------------------------------------------------------

class TestPluginRegistry(BasePluginTestCase):
    """Pruebas para el registro central de plugins en tiempo de ejecución."""

    def test_registry_tracking_and_order(self) -> None:
        registry.set_current_loading("plugin_a")
        self.assertEqual(registry.get_current_loading(), "plugin_a")

        registry.record_load_order("plugin_a")
        registry.record_load_order("plugin_b")
        registry.record_load_order("plugin_a")  # No duplicados

        self.assertEqual(registry.get_load_order(), ["plugin_a", "plugin_b"])

        registry.record_collision("keyword", "test_kw", "plugin_a", "plugin_b", "plugin_b")
        collisions = registry.get_collisions()
        self.assertEqual(len(collisions), 1)
        self.assertEqual(collisions[0].identifier, "test_kw")

        registry.record_error("plugin_c", "Error al inicializar")
        self.assertEqual(registry.get_errors().get("plugin_c"), "Error al inicializar")


# ---------------------------------------------------------------------------
# 4. Seguridad estática (AST)
# ---------------------------------------------------------------------------

class TestPluginSecurityAudit(BasePluginTestCase):
    """Pruebas de la auditoría estática de código Python de plugins."""

    def test_clean_code_passes(self) -> None:
        """Código limpio no debe generar ninguna SecurityIssue."""
        code = """
from gram.plugins.base import PluginBase
import math

class MyPlugin(PluginBase):
    def process(self, x):
        return math.sqrt(x)
"""
        issues = audit_python_code(code, filename="main.py")
        errors_found = [i for i in issues if i.level == "ERROR"]
        self.assertEqual(len(errors_found), 0)

    def test_blocked_eval_call(self) -> None:
        """eval() debe ser detectado como ERROR."""
        code = "result = eval('1 + 1')\n"
        issues = audit_python_code(code, filename="main.py")
        self.assertTrue(any(i.level == "ERROR" and "eval" in i.message for i in issues))

    def test_blocked_exec_call(self) -> None:
        """exec() debe ser detectado como ERROR."""
        code = "exec('import os')\n"
        issues = audit_python_code(code, filename="main.py")
        self.assertTrue(any(i.level == "ERROR" and "exec" in i.message for i in issues))

    def test_blocked_dunder_attribute_access(self) -> None:
        """Acceso a __subclasses__ debe ser detectado como ERROR."""
        code = "subclasses = object.__subclasses__()\n"
        issues = audit_python_code(code, filename="main.py")
        self.assertTrue(
            any(i.level == "ERROR" and "__subclasses__" in i.message for i in issues)
        )

    def test_blocked_unauthorized_import(self) -> None:
        """Importar 'requests' (no en lista blanca) debe ser un ERROR."""
        code = "import requests\n"
        issues = audit_python_code(code, filename="main.py")
        self.assertTrue(
            any(i.level == "ERROR" and "requests" in i.message for i in issues)
        )

    def test_allowed_import_gram(self) -> None:
        """Importar desde gram siempre debe estar permitido."""
        code = "from gram.plugins.base import PluginBase\n"
        issues = audit_python_code(code, filename="main.py")
        errors_found = [i for i in issues if i.level == "ERROR"]
        self.assertEqual(len(errors_found), 0)

    def test_allowed_import_from_whitelist(self) -> None:
        """Importar 'math' (en lista blanca por defecto) debe pasar."""
        code = "import math\nresult = math.pi\n"
        issues = audit_python_code(code, filename="main.py")
        errors_found = [i for i in issues if i.level == "ERROR"]
        self.assertEqual(len(errors_found), 0)

    def test_getattr_with_banned_dunder(self) -> None:
        """getattr(obj, '__globals__') debe ser detectado como ERROR."""
        code = "x = getattr(some_obj, '__globals__')\n"
        issues = audit_python_code(code, filename="main.py")
        self.assertTrue(
            any(i.level == "ERROR" and "__globals__" in i.message for i in issues)
        )


# ---------------------------------------------------------------------------
# 5. Permisos de usuario
# ---------------------------------------------------------------------------

class TestPluginPermissions(BasePluginTestCase):
    """Pruebas para el sistema de aprobación de plugins."""

    def _make_manifest(self, name: str = "test_plugin") -> PluginManifest:
        """Crea un manifest en memoria para pruebas de permisos."""
        path = self.create_mock_plugin(
            name,
            {
                "plugin_name": name,
                "version": [1, 0, 0],
                "capabilities": {},
            },
            "from gram.plugins.base import PluginBase\nclass P(PluginBase): pass\n",
        )
        return parse_manifest(path / "manifest.json")

    def test_approve_and_check(self) -> None:
        """Un plugin aprobado debe retornar True en is_approved()."""
        # Desactivar modo permisivo para probar el flujo real
        config.PLUGINS_ALLOW_ALL_PLUGINS = False

        manifest = self._make_manifest("perm_plugin_1")
        self.assertFalse(PluginPermissions.is_approved(manifest))

        PluginPermissions.approve(manifest)
        self.assertTrue(PluginPermissions.is_approved(manifest))

    def test_revoke_removes_approval(self) -> None:
        """Una aprobación revocada debe retornar False en is_approved()."""
        config.PLUGINS_ALLOW_ALL_PLUGINS = False

        manifest = self._make_manifest("perm_plugin_2")
        PluginPermissions.approve(manifest)
        self.assertTrue(PluginPermissions.is_approved(manifest))

        PluginPermissions.revoke(manifest.uuid)
        self.assertFalse(PluginPermissions.is_approved(manifest))

    def test_allow_all_bypasses_approval(self) -> None:
        """PLUGINS_ALLOW_ALL_PLUGINS=True hace que is_approved() retorne True sin aprobar."""
        config.PLUGINS_ALLOW_ALL_PLUGINS = True
        manifest = self._make_manifest("perm_plugin_3")
        self.assertTrue(PluginPermissions.is_approved(manifest))

    def test_require_approval_raises_when_not_approved(self) -> None:
        """require_approval con interactive=False debe lanzar PluginNotApprovedError."""
        config.PLUGINS_ALLOW_ALL_PLUGINS = False
        manifest = self._make_manifest("perm_plugin_4")
        with self.assertRaises(PluginNotApprovedError):
            require_approval(manifest, interactive=False)

    def test_require_approval_passes_when_approved(self) -> None:
        """require_approval debe pasar sin excepción si el plugin ya está aprobado."""
        config.PLUGINS_ALLOW_ALL_PLUGINS = False
        manifest = self._make_manifest("perm_plugin_5")
        PluginPermissions.approve(manifest)
        # No debe lanzar ninguna excepción
        require_approval(manifest, interactive=False)

    def test_version_change_invalidates_approval(self) -> None:
        """Cambiar la versión del plugin invalida la aprobación previa."""
        config.PLUGINS_ALLOW_ALL_PLUGINS = False
        path = self.create_mock_plugin(
            "versioned_plugin",
            {"plugin_name": "versioned_plugin", "version": [1, 0, 0], "capabilities": {}},
            "from gram.plugins.base import PluginBase\nclass P(PluginBase): pass\n",
        )
        manifest_v1 = parse_manifest(path / "manifest.json")
        PluginPermissions.approve(manifest_v1)

        # Actualizar versión
        (path / "manifest.json").write_text(
            json.dumps({"plugin_name": "versioned_plugin", "version": [2, 0, 0],
                        "uuid": manifest_v1.uuid, "capabilities": {}}),
            encoding="utf-8",
        )
        manifest_v2 = parse_manifest(path / "manifest.json")
        # La aprobación de v1 no debe servir para v2
        self.assertFalse(PluginPermissions.is_approved(manifest_v2))


# ---------------------------------------------------------------------------
# 6. Lista blanca de librerías (entorno)
# ---------------------------------------------------------------------------

class TestPluginEnvironmentAllowlist(BasePluginTestCase):
    """Pruebas para la lista blanca de librerías del entorno de plugins."""

    def test_default_allowed_libraries(self) -> None:
        """math, pathlib, json, copy, typing deben estar en la lista blanca por defecto."""
        for lib in ("math", "pathlib", "json", "copy", "typing"):
            self.assertTrue(is_library_allowed(lib), f"'{lib}' debería estar en la lista blanca")

    def test_gram_always_allowed(self) -> None:
        """'gram' y '__future__' siempre están permitidos."""
        self.assertTrue(is_library_allowed("gram"))
        self.assertTrue(is_library_allowed("gram.plugins.base"))
        self.assertTrue(is_library_allowed("__future__"))

    def test_add_and_remove_library(self) -> None:
        """allow_add y allow_remove modifican la lista blanca correctamente."""
        self.assertFalse(is_library_allowed("numpy"))
        allow_add("numpy")
        self.assertTrue(is_library_allowed("numpy"))
        allow_remove("numpy")
        self.assertFalse(is_library_allowed("numpy"))

    def test_reset_allowed_libraries(self) -> None:
        """reset_allowed_libraries restaura la lista a sus valores por defecto."""
        allow_add("somelib", "anotherlib")
        reset_allowed_libraries()
        self.assertFalse(is_library_allowed("somelib"))
        self.assertFalse(is_library_allowed("anotherlib"))
        self.assertTrue(is_library_allowed("math"))

    def test_root_module_check(self) -> None:
        """La comprobación se aplica al módulo raíz (numpy.linalg → numpy)."""
        allow_add("numpy")
        self.assertTrue(is_library_allowed("numpy.linalg"))
        allow_remove("numpy")
        self.assertFalse(is_library_allowed("numpy.linalg"))


# ---------------------------------------------------------------------------
# 7. Extensiones de procesamiento de Gram (PluginBase obligatorio)
# ---------------------------------------------------------------------------

class TestPluginProcessingCapabilities(BasePluginTestCase):
    """Pruebas que validan la extensión de capacidades de procesamiento de Gram."""

    def test_plugin_extends_lexer_keywords_and_groups(self) -> None:
        """Verifica que un plugin registre automáticamente palabras clave y grupos en el Lexer."""
        p_path = self.create_mock_plugin(
            "dsl_keywords_plugin",
            {
                "plugin_name": "dsl_keywords_plugin",
                "version": [1, 0, 0],
                "capabilities": {"load": True, "process": True},
            },
            """\
from gram.plugins.base import PluginBase

class MyDSLPlugin(PluginBase):
    def get_keywords(self):
        return [("shader", "#FF00FF", "GRAPHICS"), "vertex"]

    def get_word_groups(self):
        return {"SHADERS": ["shader", "vertex"]}
""",
        )

        plugin = Plugins.load(p_path)
        self.assertTrue(plugin.is_loaded)

        self.assertTrue(words.keyword_exists("shader"))
        self.assertTrue(words.keyword_exists("vertex"))
        kw = words.get_keyword("shader")
        self.assertIsNotNone(kw)
        self.assertEqual(kw.hex_color, "#FF00FF")
        self.assertEqual(kw.group, "GRAPHICS")

        grp = words.get_group("SHADERS")
        self.assertIsNotNone(grp)
        self.assertIn("shader", grp.values)

    def test_plugin_requires_pluginbase_subclass(self) -> None:
        """Un plugin sin subclase de PluginBase en main.py debe fallar al cargar."""
        p_path = self.create_mock_plugin(
            "no_base_plugin",
            {
                "plugin_name": "no_base_plugin",
                "version": [1, 0, 0],
                "capabilities": {},
            },
            # main.py sin PluginBase
            "def process(): return 42\n",
        )
        with self.assertRaises(GrammarError):
            Plugins.load(p_path)

    def test_plugin_extends_combinators_custom_mods(self) -> None:
        """Verifica que los combinadores expuestos por el plugin se registren como Custom Mods."""
        p_path = self.create_mock_plugin(
            "custom_comb_plugin",
            {
                "plugin_name": "custom_comb_plugin",
                "version": [1, 0, 0],
                "capabilities": {},
            },
            """\
from gram.core.combinators.base import Combinator
from gram.plugins.base import PluginBase

class CustomClampCombinator(Combinator):
    def parse(self, analyzer, current=None, ignore_errors=False):
        return "clamped"

class CombPlugin(PluginBase):
    def get_combinators(self):
        return [CustomClampCombinator]
""",
        )

        plugin = Plugins.load(p_path)
        combs = plugin.get_combinators()
        self.assertEqual(len(combs), 1)
        self.assertEqual(combs[0].__name__, "CustomClampCombinator")
        self.assertTrue(is_custom_mod(combs[0]))

    def test_plugin_extends_grammar_and_declarations(self) -> None:
        """Verifica que el plugin inyecte reglas sintácticas directamente en DECLARATION."""
        p_path = self.create_mock_plugin(
            "custom_syntax_plugin",
            {
                "plugin_name": "custom_syntax_plugin",
                "version": [1, 0, 0],
                "capabilities": {},
            },
            """\
from gram.core.combinators.base import RuleItem
from gram.core.combinators.match import MatchKeyword, MatchToken
from gram.core.combinators.sequence import Seq
from gram.core.lexer import Token
from gram.plugins.base import PluginBase

class SHADER_DECL(RuleItem):
    code = 9001
    name = "SHADER_DECL"
    grammar = Seq(MatchKeyword("shader"), MatchToken(Token.IDENT))

class MySyntaxPlugin(PluginBase):
    def get_keywords(self):
        return ["shader"]

    def get_rules(self):
        return [SHADER_DECL]

    def extend_declarations(self):
        return [SHADER_DECL]
""",
        )

        plugin = Plugins.load(p_path)

        class BASE_STMT(RuleItem):
            code = 100
            name = "BASE_STMT"
            grammar = MatchToken(Token.IDENT)

        base_grammar = {
            PROGRAM: Many(Ref(DECLARATION)),
            DECLARATION: Alt(Ref(BASE_STMT)),
            BASE_STMT: BASE_STMT.grammar,
        }

        extended_grammar = Plugins.apply_to_grammar(base_grammar)
        decl_alt = extended_grammar[DECLARATION]
        decl_arg_names = [getattr(r.rule, "name", str(r.rule)) for r in decl_alt.combinators]
        self.assertIn("BASE_STMT", decl_arg_names)
        self.assertIn("SHADER_DECL", decl_arg_names)

        found_shader = any(
            getattr(k, "name", str(k)) == "SHADER_DECL" for k in extended_grammar
        )
        self.assertTrue(found_shader)

    def test_plugin_ast_transformation_pipeline(self) -> None:
        """Verifica que el plugin intercepte y transforme el AST generado."""
        p_path = self.create_mock_plugin(
            "ast_transform_plugin",
            {
                "plugin_name": "ast_transform_plugin",
                "version": [1, 0, 0],
                "capabilities": {},
            },
            """\
from gram.plugins.base import PluginBase

class ASTOptimizerPlugin(PluginBase):
    def transform_ast(self, ast):
        ast.metadata["optimized_by"] = "ASTOptimizerPlugin"
        return ast
""",
        )

        Plugins.load(p_path)

        ast_node = ASTProgram(body=[], comments=[])
        ast_node.metadata = {}

        transformed = Plugins.transform_ast(ast_node)
        self.assertEqual(transformed.metadata.get("optimized_by"), "ASTOptimizerPlugin")

    def test_plugin_process_execution(self) -> None:
        """Verifica el punto de procesamiento process() de un plugin."""
        p_path = self.create_mock_plugin(
            "calculator_plugin",
            {
                "plugin_name": "calculator_plugin",
                "version": [1, 0, 0],
                "capabilities": {"process": True},
            },
            """\
from gram.plugins.base import PluginBase

class CalcPlugin(PluginBase):
    def process(self, expr_str):
        parts = expr_str.split("+")
        return sum(int(p.strip()) for p in parts)
""",
        )

        Plugins.load(p_path)
        res = Plugins.process("calculator_plugin", "10 + 20 + 30")
        self.assertEqual(res, 60)

    def test_plugin_reload(self) -> None:
        """Verifica la recarga en caliente de un plugin."""
        p_path = self.create_mock_plugin(
            "reloadable_plugin",
            {
                "plugin_name": "reloadable_plugin",
                "version": [1, 0, 0],
                "capabilities": {"process": True},
            },
            """\
from gram.plugins.base import PluginBase

class ReloadPlugin(PluginBase):
    def process(self):
        return 1
""",
        )

        p1 = Plugins.load(p_path)
        self.assertEqual(p1.process(), 1)

        # Actualizar main.py en disco
        (p_path / "main.py").write_text(
            """\
from gram.plugins.base import PluginBase

class ReloadPlugin(PluginBase):
    def process(self):
        return 2
""",
            encoding="utf-8",
        )

        p2 = Plugins.reload(p_path)
        self.assertEqual(p2.process(), 2)


# ---------------------------------------------------------------------------
# 8. Validación previa con auditoría real de seguridad
# ---------------------------------------------------------------------------

class TestPluginValidatorWithSecurity(BasePluginTestCase):
    """Pruebas del validador estático con auditoría de seguridad integrada."""

    def test_valid_plugin_passes_validation(self) -> None:
        """Un plugin limpio y bien formado debe pasar sin errores."""
        p_path = self.create_mock_plugin(
            "clean_plugin",
            {
                "plugin_name": "clean_plugin",
                "version": [1, 0, 0],
                "capabilities": {"process": True},
            },
            """\
from gram.plugins.base import PluginBase
import math

class CleanPlugin(PluginBase):
    def process(self, x):
        return math.sqrt(x)
""",
        )

        report = validate_plugin(p_path)
        self.assertTrue(report.is_valid)
        self.assertEqual(report.plugin_name, "clean_plugin")
        self.assertEqual(len(report.errors), 0)

    def test_plugin_with_eval_fails_validation(self) -> None:
        """Un plugin que usa eval() debe fallar la validación."""
        p_path = self.create_mock_plugin(
            "eval_plugin",
            {
                "plugin_name": "eval_plugin",
                "version": [1, 0, 0],
                "capabilities": {},
            },
            """\
from gram.plugins.base import PluginBase

class EvalPlugin(PluginBase):
    def process(self, code):
        return eval(code)
""",
        )

        report = validate_plugin(p_path)
        self.assertFalse(report.is_valid)
        self.assertTrue(any("eval" in i.message for i in report.errors))

    def test_plugin_without_pluginbase_warns(self) -> None:
        """Un plugin sin herencia de PluginBase debe generar al menos una advertencia o error."""
        p_path = self.create_mock_plugin(
            "no_base_validate",
            {
                "plugin_name": "no_base_validate",
                "version": [1, 0, 0],
                "capabilities": {},
            },
            "class SomeClass: pass\n",
        )

        report = validate_plugin(p_path)
        has_issue = len(report.warnings) > 0 or len(report.errors) > 0
        self.assertTrue(has_issue)

    def test_missing_manifest_fails_validation(self) -> None:
        """Un directorio sin manifest.json debe retornar error."""
        empty_dir = Path(self.temp_dir) / "empty_plugin"
        empty_dir.mkdir()

        report = validate_plugin(empty_dir)
        self.assertFalse(report.is_valid)
        self.assertTrue(any("manifest" in i.message.lower() for i in report.errors))

    def test_unauthorized_import_fails_validation(self) -> None:
        """Un plugin que importa 'requests' (no en lista blanca) debe fallar."""
        p_path = self.create_mock_plugin(
            "net_plugin",
            {
                "plugin_name": "net_plugin",
                "version": [1, 0, 0],
                "capabilities": {},
            },
            """\
import requests
from gram.plugins.base import PluginBase

class NetPlugin(PluginBase):
    def process(self):
        return requests.get("http://example.com")
""",
        )

        report = validate_plugin(p_path)
        self.assertFalse(report.is_valid)
        self.assertTrue(
            any("requests" in i.message for i in report.errors)
        )


if __name__ == "__main__":
    unittest.main()
