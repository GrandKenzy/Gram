"""
Pruebas Unitarias del Subsistema VSIX y Editor (`gram.tests.test_vsix`).
========================================================================
Valida exhaustivamente:
  1. Extracción de metadatos sintácticos (extract_metadata, RuleMetadata, KeywordMetadata, SyntaxMetadata).
  2. Generación de artefactos VS Code:
     - Gramática TextMate (generate_textmate_grammar)
     - Tema cromático (generate_theme)
     - Configuración de lenguaje (generate_language_configuration)
     - Fragmentos / Snippets (generate_snippets)
     - Cliente LSP JavaScript (generate_lsp_client_js)
     - Icono PNG incrustado (generate_icon_png)
     - Manifiesto package.json (generate_package_json)
  3. Empaquetado OPC / VSIX (build_extension_directory, package_vsix).
  4. Gestor de ciclo de vida (VsixManager, compile, clear, ID universal gram.gram-language-support).
  5. Servidor Language Server Protocol (LSP) nativo JSON-RPC (GramLanguageServer):
     - initialize / initialized
     - textDocument/didOpen & publishDiagnostics (código válido y código con errores)
     - textDocument/completion (tokens, keywords, reglas)
     - textDocument/hover (documentación markdown)
     - shutdown / exit
  6. Subcomandos CLI (gram vsix compile, info, list).
"""
from __future__ import annotations

import io
import json
import os
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import gram
from gram import config
from gram.cli.core import build_parser, main
from gram.core.combinators.base import RuleItem
from gram.glang.keywords import register_glang_keywords
from gram.vsix import (
    GRAM_EXTENSION_NAME,
    GRAM_FULL_ID,
    GRAM_PUBLISHER,
    GramLanguageServer,
    KeywordMetadata,
    RuleMetadata,
    SyntaxMetadata,
    VsixManager,
    build_extension_directory,
    clear,
    compile as vsix_compile,
    extract_metadata,
    generate_icon_png,
    generate_language_configuration,
    generate_lsp_client_js,
    generate_package_json,
    generate_snippets,
    generate_textmate_grammar,
    generate_theme,
    get_active_vsix,
    is_installed,
    list_installed,
    package_vsix,
    register_user_grammar,
    register_user_keyword,
    uninstall,
)


class TestVsixMetadataAndGeneration(unittest.TestCase):
    """Pruebas de extracción de metadatos y generación de componentes de la extensión."""

    def setUp(self) -> None:
        self.old_hide_console = config.ERROR_HIDE_CONSOLE
        self.old_exit_on_error = config.ERROR_EXIT_ON_ERROR
        config.ERROR_HIDE_CONSOLE = True
        config.ERROR_EXIT_ON_ERROR = False
        self.temp_dir = Path(tempfile.mkdtemp())
        register_glang_keywords()

    def tearDown(self) -> None:
        config.ERROR_HIDE_CONSOLE = self.old_hide_console
        config.ERROR_EXIT_ON_ERROR = self.old_exit_on_error
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_extract_native_metadata(self) -> None:
        meta = extract_metadata(include_native=True)
        self.assertIsInstance(meta, SyntaxMetadata)
        self.assertGreater(len(meta.rules), 0)
        self.assertIn(".gram", meta.file_extensions)
        self.assertIn(".glang", meta.file_extensions)

        # Reglas nativas conocidas deben estar presentes
        rule_names = list(meta.rules.keys())
        self.assertTrue(any("PROGRAM" in r or "DECLARATION" in r or "STATEMENT" in r for r in rule_names))

    def test_syntax_metadata_merge(self) -> None:
        meta1 = SyntaxMetadata(file_extensions=[".gram"])
        meta1.keywords["let"] = KeywordMetadata(name="let", hex_color="#FF0000", group="keywords")
        meta1.rules["RULE_A"] = RuleMetadata(name="RULE_A", code=101)

        meta2 = SyntaxMetadata(file_extensions=[".glang", ".gram"])
        meta2.keywords["fn"] = KeywordMetadata(name="fn", hex_color="#00FF00", group="keywords")
        meta2.rules["RULE_B"] = RuleMetadata(name="RULE_B", code=102)

        meta1.merge(meta2)
        self.assertIn("let", meta1.keywords)
        self.assertIn("fn", meta1.keywords)
        self.assertIn("RULE_A", meta1.rules)
        self.assertIn("RULE_B", meta1.rules)
        self.assertEqual(meta1.file_extensions, [".gram", ".glang"])

    def test_generate_textmate_grammar(self) -> None:
        meta = SyntaxMetadata()
        meta.keywords["func"] = KeywordMetadata(name="func", hex_color="#FF5555", group="keywords")
        meta.rules["RULE_TEST"] = RuleMetadata(name="RULE_TEST", code=200, scope="entity.name.type.gram")

        tm = generate_textmate_grammar(meta)
        self.assertEqual(tm["name"], "Gram")
        self.assertEqual(tm["scopeName"], "source.gram")
        self.assertIn("patterns", tm)

        pattern_names = [p.get("name", "") for p in tm["patterns"] if "name" in p]
        self.assertTrue(any("RULE_TEST" in n or "rule" in n for n in pattern_names))
        self.assertTrue(any("func" in n for n in pattern_names))

    def test_generate_theme(self) -> None:
        meta = SyntaxMetadata()
        meta.keywords["return"] = KeywordMetadata(name="return", hex_color="#CC7832")
        meta.rules["RULE_CUSTOM"] = RuleMetadata(name="RULE_CUSTOM", code=201, color="#6897BB")

        theme = generate_theme(meta, theme_name="Gram Theme")
        self.assertEqual(theme["name"], "Gram Theme")
        self.assertEqual(theme["type"], "dark")
        self.assertIn("tokenColors", theme)
        self.assertTrue(len(theme["tokenColors"]) > 0)

        theme_colors = [tc["settings"]["foreground"] for tc in theme["tokenColors"] if "foreground" in tc.get("settings", {})]
        self.assertIn("#CC7832", theme_colors)
        self.assertIn("#6897BB", theme_colors)

    def test_generate_language_configuration(self) -> None:
        cfg = generate_language_configuration()
        self.assertIn("comments", cfg)
        self.assertEqual(cfg["comments"]["lineComment"], "#")
        self.assertIn("brackets", cfg)
        self.assertIn("autoClosingPairs", cfg)

    def test_generate_snippets(self) -> None:
        meta = SyntaxMetadata()
        meta.rules["IF_STMT"] = RuleMetadata(
            name="IF_STMT",
            code=300,
            description="Sentencia if",
            suggestions={"if_block": {"prefix": "if", "body": "if ${1:cond} {\n\t$0\n}", "description": "Bloque if"}},
        )

        snippets = generate_snippets(meta)
        self.assertIn("if_block", snippets)
        self.assertEqual(snippets["if_block"]["prefix"], "if")
        self.assertIn("body", snippets["if_block"])

    def test_generate_lsp_client_js(self) -> None:
        js_code = generate_lsp_client_js()
        self.assertIn("vscode-languageclient", js_code)
        self.assertIn("LanguageClient", js_code)
        self.assertIn("compiler.path", js_code)
        self.assertIn("compiler.args", js_code)
        self.assertIn("getConfiguration('gram')", js_code)

    def test_generate_icon_png(self) -> None:
        target_icon = self.temp_dir / "test_icon.png"
        res = generate_icon_png(target_icon)
        self.assertEqual(res, target_icon)
        self.assertTrue(target_icon.exists())
        png_bytes = target_icon.read_bytes()
        self.assertTrue(png_bytes.startswith(b"\x89PNG\r\n\x1a\n"))

    def test_generate_package_json(self) -> None:
        meta = SyntaxMetadata(file_extensions=[".gram", ".glang", ".g"])
        pkg = generate_package_json(
            metadata=meta,
            ext_id="gram-language-support",
            ext_name="Gram Language Support",
            publisher="gram",
            version="1.0.0",
            compiler_path="gramc",
            compiler_args=["--emit-ast"],
        )
        self.assertEqual(pkg["name"], "gram-language-support")
        self.assertEqual(pkg["publisher"], "gram")
        self.assertEqual(pkg["version"], "1.0.0")
        self.assertIn("contributes", pkg)
        self.assertIn("languages", pkg["contributes"])
        self.assertIn("configuration", pkg["contributes"])

        # Verificar configuración de compilador
        props = pkg["contributes"]["configuration"]["properties"]
        self.assertIn("gram.compiler.path", props)
        self.assertEqual(props["gram.compiler.path"]["default"], "gramc")
        self.assertIn("gram.compiler.args", props)
        self.assertEqual(props["gram.compiler.args"]["default"], ["--emit-ast"])


class TestVsixPackagingAndManager(unittest.TestCase):
    """Pruebas de construcción de directorio VSIX, empaquetado OPC ZIP y VsixManager."""

    def setUp(self) -> None:
        self.old_hide_console = config.ERROR_HIDE_CONSOLE
        self.old_exit_on_error = config.ERROR_EXIT_ON_ERROR
        config.ERROR_HIDE_CONSOLE = True
        config.ERROR_EXIT_ON_ERROR = False
        self.temp_dir = Path(tempfile.mkdtemp())
        self.mgr = VsixManager()
        self.mgr._temp_dir = self.temp_dir
        register_glang_keywords()

    def tearDown(self) -> None:
        config.ERROR_HIDE_CONSOLE = self.old_hide_console
        config.ERROR_EXIT_ON_ERROR = self.old_exit_on_error
        self.mgr.clear()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_build_extension_directory_structure(self) -> None:
        out_dir = self.temp_dir / "build_ext"
        meta = extract_metadata(include_native=True)

        build_extension_directory(
            output_dir=out_dir,
            metadata=meta,
            ext_id=GRAM_EXTENSION_NAME,
            ext_name="Gram Language Support",
            publisher=GRAM_PUBLISHER,
            version="1.0.0",
        )

        self.assertTrue((out_dir / "package.json").is_file())
        self.assertTrue((out_dir / "icon.png").is_file())
        self.assertTrue((out_dir / "language-configuration.json").is_file())
        self.assertTrue((out_dir / "syntaxes" / "gram.tmLanguage.json").is_file())
        self.assertTrue((out_dir / "themes" / "gram-theme.json").is_file())
        self.assertTrue((out_dir / "snippets" / "snippets.json").is_file())
        self.assertTrue((out_dir / "client" / "extension.js").is_file())

    def test_package_vsix_creates_valid_opc_zip(self) -> None:
        build_dir = self.temp_dir / "build_ext"
        meta = extract_metadata(include_native=True)
        build_extension_directory(
            output_dir=build_dir,
            metadata=meta,
            ext_id=GRAM_EXTENSION_NAME,
            ext_name="Gram Language Support",
            publisher=GRAM_PUBLISHER,
            version="1.0.0",
        )

        vsix_file = self.temp_dir / "test.vsix"
        packaged_path = package_vsix(build_dir, output_vsix=vsix_file)
        self.assertEqual(packaged_path, vsix_file)
        self.assertTrue(vsix_file.exists())
        self.assertGreater(vsix_file.stat().st_size, 0)

        # Validar estructura OPC ZIP
        with zipfile.ZipFile(vsix_file, "r") as zf:
            namelist = zf.namelist()
            self.assertIn("[Content_Types].xml", namelist)
            self.assertIn("extension.vsixmanifest", namelist)
            self.assertIn("extension/package.json", namelist)
            self.assertIn("extension/icon.png", namelist)
            self.assertIn("extension/syntaxes/gram.tmLanguage.json", namelist)

            manifest_content = zf.read("extension.vsixmanifest").decode("utf-8")
            self.assertIn(f'Id="{GRAM_EXTENSION_NAME}"', manifest_content)
            self.assertIn(f'Publisher="{GRAM_PUBLISHER}"', manifest_content)

    def test_manager_compile_and_clear(self) -> None:
        target_path = self.temp_dir / "output.vsix"
        res = self.mgr.compile(output_path=target_path, force=True)
        self.assertEqual(res, target_path)
        self.assertTrue(target_path.exists())
        self.assertEqual(self.mgr.active_vsix, target_path)

        self.mgr.clear()
        self.assertIsNone(self.mgr.active_vsix)
        self.assertFalse(target_path.exists())

    def test_constant_gram_identifiers(self) -> None:
        self.assertEqual(GRAM_PUBLISHER, "gram")
        self.assertEqual(GRAM_EXTENSION_NAME, "gram-language-support")
        self.assertEqual(GRAM_FULL_ID, "gram.gram-language-support")
        self.assertEqual(self.mgr.FULL_ID, "gram.gram-language-support")

    def test_register_user_keyword(self) -> None:
        self.mgr.register_user_keyword("my_custom_kw", hex_color="#ABCDEF", description="Custom keyword")
        self.assertIn("my_custom_kw", self.mgr._user_metadata.keywords)
        kw = self.mgr._user_metadata.keywords["my_custom_kw"]
        self.assertEqual(kw.hex_color, "#ABCDEF")
        self.assertEqual(kw.description, "Custom keyword")

    def test_register_user_grammar(self) -> None:
        class FakeRule(RuleItem):
            code = 999
            name = "FAKE_RULE"
            description = "Fake rule for test"
            @classmethod
            def compile(cls):
                return {"code": 999, "name": "FAKE_RULE", "description": "Fake rule for test"}

        self.mgr.register_user_grammar({FakeRule: None})
        self.assertIn("FAKE_RULE", self.mgr._user_metadata.rules)
        self.assertEqual(self.mgr._user_metadata.rules["FAKE_RULE"].code, 999)

    @patch("subprocess.run")
    @patch("gram.vsix.core.find_vscode_executable")
    def test_install_and_uninstall_invocations(self, mock_find, mock_run) -> None:
        mock_find.return_value = "code"
        mock_run.return_value = MagicMock(returncode=0, stdout="Success", stderr="")

        dummy_vsix = self.temp_dir / "dummy.vsix"
        dummy_vsix.write_text("dummy")

        ok, msg = self.mgr.install(dummy_vsix)
        self.assertTrue(ok)
        mock_run.assert_called_with(["code", "--install-extension", str(dummy_vsix), "--force"], capture_output=True, text=True, check=False)

        ok_un, msg_un = self.mgr.uninstall()
        self.assertTrue(ok_un)
        mock_run.assert_called_with(["code", "--uninstall-extension", GRAM_FULL_ID], capture_output=True, text=True, check=False)


class TestGramLanguageServerProtocol(unittest.TestCase):
    """Pruebas del servidor Language Server Protocol (LSP) nativo JSON-RPC."""

    def setUp(self) -> None:
        self.old_hide_console = config.ERROR_HIDE_CONSOLE
        self.old_exit_on_error = config.ERROR_EXIT_ON_ERROR
        config.ERROR_HIDE_CONSOLE = True
        config.ERROR_EXIT_ON_ERROR = False
        register_glang_keywords()

    def tearDown(self) -> None:
        config.ERROR_HIDE_CONSOLE = self.old_hide_console
        config.ERROR_EXIT_ON_ERROR = self.old_exit_on_error

    def _rpc_request(self, method: str, params: dict | None = None, req_id: int | str = 1) -> str:
        body = json.dumps({"jsonrpc": "2.0", "id": req_id, "method": method, "params": params or {}})
        return f"Content-Length: {len(body)}\r\n\r\n{body}"

    def _rpc_notification(self, method: str, params: dict | None = None) -> str:
        body = json.dumps({"jsonrpc": "2.0", "method": method, "params": params or {}})
        return f"Content-Length: {len(body)}\r\n\r\n{body}"

    def _parse_responses(self, output_str: str) -> list[dict]:
        responses = []
        for part in output_str.split("Content-Length:"):
            part = part.strip()
            if not part:
                continue
            lines = part.split("\r\n\r\n", 1)
            if len(lines) == 2:
                try:
                    responses.append(json.loads(lines[1]))
                except Exception:
                    pass
        return responses

    def test_lsp_initialize_and_shutdown(self) -> None:
        stream_in = io.StringIO(
            self._rpc_request("initialize", {"capabilities": {}}, req_id=1)
            + self._rpc_notification("initialized")
            + self._rpc_request("shutdown", req_id=2)
            + self._rpc_notification("exit")
        )
        stream_out = io.StringIO()

        server = GramLanguageServer(stream_in=stream_in, stream_out=stream_out)
        server.run()

        responses = self._parse_responses(stream_out.getvalue())
        self.assertTrue(len(responses) >= 2)

        # Respuesta de initialize
        init_resp = next(r for r in responses if r.get("id") == 1)
        self.assertIn("capabilities", init_resp["result"])
        caps = init_resp["result"]["capabilities"]
        self.assertIn("textDocumentSync", caps)
        self.assertIn("completionProvider", caps)
        self.assertIn("hoverProvider", caps)

        # Respuesta de shutdown
        shutdown_resp = next(r for r in responses if r.get("id") == 2)
        self.assertIsNone(shutdown_resp["result"])

    def test_lsp_diagnostics_on_open(self) -> None:
        doc_uri = "file:///sample.glang"
        valid_code = """\
define IDENT_STMT 1000
IDENT_STMT Seq:
    tokens.IDENT
[0]:
    reference IDENT_STMT
"""

        stream_in = io.StringIO(
            self._rpc_notification("textDocument/didOpen", {
                "textDocument": {
                    "uri": doc_uri,
                    "languageId": "glang",
                    "version": 1,
                    "text": valid_code,
                }
            })
            + self._rpc_request("shutdown", req_id=9)
            + self._rpc_notification("exit")
        )
        stream_out = io.StringIO()

        server = GramLanguageServer(stream_in=stream_in, stream_out=stream_out)
        server.run()

        responses = self._parse_responses(stream_out.getvalue())
        diag_notif = next((r for r in responses if r.get("method") == "textDocument/publishDiagnostics"), None)
        self.assertIsNotNone(diag_notif)
        self.assertEqual(diag_notif["params"]["uri"], doc_uri)
        # Código válido: sin errores críticos
        self.assertEqual(len(diag_notif["params"]["diagnostics"]), 0)

    def test_lsp_diagnostics_on_invalid_syntax(self) -> None:
        doc_uri = "file:///invalid.gram"
        invalid_code = "??? $$$ invalid @@ 999 888"

        stream_in = io.StringIO(
            self._rpc_notification("textDocument/didOpen", {
                "textDocument": {
                    "uri": doc_uri,
                    "languageId": "gram",
                    "version": 1,
                    "text": invalid_code,
                }
            })
            + self._rpc_request("shutdown", req_id=9)
            + self._rpc_notification("exit")
        )
        stream_out = io.StringIO()

        server = GramLanguageServer(stream_in=stream_in, stream_out=stream_out)
        server.run()

        responses = self._parse_responses(stream_out.getvalue())
        diag_notif = next((r for r in responses if r.get("method") == "textDocument/publishDiagnostics"), None)
        self.assertIsNotNone(diag_notif)
        # Debe haber detectado errores de sintaxis o tokenización
        self.assertGreater(len(diag_notif["params"]["diagnostics"]), 0)
        d = diag_notif["params"]["diagnostics"][0]
        self.assertIn("range", d)
        self.assertIn("message", d)

    def test_lsp_completions(self) -> None:
        doc_uri = "file:///test.glang"
        meta = SyntaxMetadata()
        meta.keywords["token"] = KeywordMetadata(name="token", hex_color="#FF0000", description="Define un token")
        meta.rules["RULE_DECL"] = RuleMetadata(name="RULE_DECL", code=10, description="Declaración")

        stream_in = io.StringIO(
            self._rpc_notification("textDocument/didOpen", {
                "textDocument": {"uri": doc_uri, "languageId": "glang", "version": 1, "text": "tok"}
            })
            + self._rpc_request("textDocument/completion", {
                "textDocument": {"uri": doc_uri},
                "position": {"line": 0, "character": 3},
            }, req_id=10)
            + self._rpc_request("shutdown", req_id=11)
            + self._rpc_notification("exit")
        )
        stream_out = io.StringIO()

        server = GramLanguageServer(stream_in=stream_in, stream_out=stream_out, metadata=meta)
        server.run()

        responses = self._parse_responses(stream_out.getvalue())
        comp_resp = next(r for r in responses if r.get("id") == 10)
        items = comp_resp["result"]["items"]
        labels = [item["label"] for item in items]
        self.assertIn("token", labels)
        self.assertIn("RULE_DECL", labels)

    def test_lsp_hover(self) -> None:
        doc_uri = "file:///hover.glang"
        meta = SyntaxMetadata()
        meta.keywords["keyword_doc"] = KeywordMetadata(name="keyword_doc", hex_color="#123456", description="Doc de prueba")

        stream_in = io.StringIO(
            self._rpc_notification("textDocument/didOpen", {
                "textDocument": {"uri": doc_uri, "languageId": "glang", "version": 1, "text": "keyword_doc"}
            })
            + self._rpc_request("textDocument/hover", {
                "textDocument": {"uri": doc_uri},
                "position": {"line": 0, "character": 4},
            }, req_id=20)
            + self._rpc_request("shutdown", req_id=21)
            + self._rpc_notification("exit")
        )
        stream_out = io.StringIO()

        server = GramLanguageServer(stream_in=stream_in, stream_out=stream_out, metadata=meta)
        server.run()

        responses = self._parse_responses(stream_out.getvalue())
        hover_resp = next(r for r in responses if r.get("id") == 20)
        self.assertIsNotNone(hover_resp["result"])
        self.assertIn("Doc de prueba", hover_resp["result"]["contents"]["value"])


class TestVsixCLICommands(unittest.TestCase):
    """Pruebas de los comandos CLI `gram vsix`."""

    def setUp(self) -> None:
        self.old_hide_console = config.ERROR_HIDE_CONSOLE
        self.old_exit_on_error = config.ERROR_EXIT_ON_ERROR
        config.ERROR_HIDE_CONSOLE = True
        config.ERROR_EXIT_ON_ERROR = False
        self.temp_dir = Path(tempfile.mkdtemp())
        register_glang_keywords()

    def tearDown(self) -> None:
        config.ERROR_HIDE_CONSOLE = self.old_hide_console
        config.ERROR_EXIT_ON_ERROR = self.old_exit_on_error
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_cli_vsix_info(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["vsix", "info"])
        self.assertEqual(args.func.__name__, "cmd_vsix")
        self.assertEqual(args.vsix_subcommand, "info")

        stdout_buf = io.StringIO()
        with patch("sys.stdout", stdout_buf):
            ret = main(["vsix", "info"])
        self.assertEqual(ret, 0)
        out = stdout_buf.getvalue()
        self.assertIn("ID Universal Gram", out)
        self.assertIn("gram.gram-language-support", out)

    def test_cli_vsix_compile(self) -> None:
        out_vsix = self.temp_dir / "cli_compiled.vsix"
        stdout_buf = io.StringIO()
        with patch("sys.stdout", stdout_buf):
            ret = main(["vsix", "compile", "-o", str(out_vsix), "--compiler", "gcc", "--ext", "c", "cpp"])
        self.assertEqual(ret, 0)
        self.assertTrue(out_vsix.exists())
        self.assertGreater(out_vsix.stat().st_size, 0)

        out = stdout_buf.getvalue()
        self.assertIn("VSIX — Compilación", out)
        self.assertIn("cli_compiled.vsix", out)

    def test_cli_vsix_list(self) -> None:
        stdout_buf = io.StringIO()
        with patch("sys.stdout", stdout_buf):
            ret = main(["vsix", "list"])
        self.assertEqual(ret, 0)
        out = stdout_buf.getvalue()
        self.assertIn("VSIX — Extensiones de Gram en VS Code", out)


if __name__ == "__main__":
    unittest.main()
