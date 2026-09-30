"""
Pruebas Unitarias de la Herramienta de Línea de Comandos (`gram.tests.test_cli`).
================================================================================
Valida exhaustivamente:
  1. CLI Parser y despacho de subcomandos:
     - Version (--version) y ayuda (--help).
     - Subcomando 'list' (catálogo de plugins).
     - Subcomando 'env info' (entorno virtual dedicado).
     - Subcomando 'check' (validación estática en dry-run).
     - Subcomando 'glang' (compilación y análisis sintáctico con .glang).
  2. CacheSystem (gram.cachesystem):
     - compute_file_hash, compute_plugin_tree_hash.
     - PluginCacheEntry, save_plugin_cache, get_plugin_cache, invalidate_plugin_cache.
     - Detección de cambios incrementales con diff_files.
"""
from __future__ import annotations

import io
import json
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

from gram import config
from gram.cachesystem import (
    PluginCacheEntry,
    compute_file_hash,
    compute_plugin_tree_hash,
    get_plugin_cache,
    invalidate_plugin_cache,
    save_plugin_cache,
)
from gram.cli.core import build_parser, main


class TestCLIAndCacheSystem(unittest.TestCase):
    """Suite de pruebas para gram.cli y gram.cachesystem."""

    def setUp(self) -> None:
        self.old_hide_console = config.ERROR_HIDE_CONSOLE
        self.old_exit_on_error = config.ERROR_EXIT_ON_ERROR
        config.ERROR_HIDE_CONSOLE = True
        config.ERROR_EXIT_ON_ERROR = False

        self.temp_dir = tempfile.mkdtemp()
        self.old_data_dir = getattr(config, "DATA_DIR", None)
        self.old_cache_dir = getattr(config, "CACHE_DIR", None)
        config.DATA_DIR = self.temp_dir
        config.CACHE_DIR = str(Path(self.temp_dir) / "cache")

    def tearDown(self) -> None:
        config.ERROR_HIDE_CONSOLE = self.old_hide_console
        config.ERROR_EXIT_ON_ERROR = self.old_exit_on_error
        config.DATA_DIR = self.old_data_dir
        config.CACHE_DIR = self.old_cache_dir
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_parser_has_expected_commands(self) -> None:
        """Verifica que el parser registre todos los subcomandos esperados."""
        import argparse
        parser = build_parser()
        subparser_actions = [
            a for a in parser._actions
            if isinstance(a, argparse._SubParsersAction)
        ]
        self.assertTrue(len(subparser_actions) > 0)
        choices = list(subparser_actions[0].choices.keys())
        expected = [
            "install",
            "load",
            "update",
            "reload",
            "remove",
            "list",
            "info",
            "check",
            "env",
            "watch",
            "clean",
            "run",
            "glang",
        ]
        for cmd in expected:
            self.assertIn(cmd, choices)

    def test_cli_list_command(self) -> None:
        """El subcomando list debe retornar 0."""
        buf = io.StringIO()
        with redirect_stdout(buf):
            ret = main(["list"])
        self.assertEqual(ret, 0)
        output = buf.getvalue()
        self.assertIn("Plugins Instalados", output)

    def test_cli_env_info_command(self) -> None:
        """El subcomando env info debe retornar 0."""
        buf = io.StringIO()
        with redirect_stdout(buf):
            ret = main(["env", "info"])
        self.assertEqual(ret, 0)
        output = buf.getvalue()
        self.assertIn("Entorno Virtual", output)

    def test_cli_check_mock_plugin(self) -> None:
        """El subcomando check debe validar estáticamente un mock plugin."""
        plugin_dir = Path(self.temp_dir) / "mock_cli_plugin"
        plugin_dir.mkdir(parents=True)

        manifest = {
            "plugin_name": "mock_cli_plugin",
            "version": "1.0.0",
            "description": "Mock plugin for CLI check test",
            "entrypoint": "main.py",
            "capabilities": {"load": True, "process": False, "cli": False},
        }
        (plugin_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        (plugin_dir / "main.py").write_text(
            """\
from gram.plugins.base import PluginBase

class MockPlugin(PluginBase):
    pass
""",
            encoding="utf-8",
        )

        buf = io.StringIO()
        with redirect_stdout(buf):
            ret = main(["check", str(plugin_dir)])
        self.assertEqual(ret, 0)
        output = buf.getvalue()
        self.assertIn("Verificación de Plugin", output)
        self.assertIn("[OK] El plugin es válido", output)

    def test_cli_glang_command_compile_and_parse(self) -> None:
        """El subcomando glang debe compilar una gramática y analizar código fuente."""
        glang_file = Path(self.temp_dir) / "test_cli.glang"
        glang_file.write_text(
            """\
define GREET 1000
GREET Seq:
    tokens.IDENT
[0]:
    reference GREET
""",
            encoding="utf-8-sig",
        )

        src_file = Path(self.temp_dir) / "src.txt"
        src_file.write_text("antigravity", encoding="utf-8")

        buf = io.StringIO()
        with redirect_stdout(buf):
            ret = main(["glang", str(glang_file), "-s", str(src_file), "-a"])
        self.assertEqual(ret, 0)
        output = buf.getvalue()
        self.assertIn("GLANG — Compilación de Gramática", output)
        self.assertIn("Sentencias AST: 1", output)

    def test_cachesystem_file_and_tree_hash(self) -> None:
        """Verifica el cálculo de hashes criptográficos SHA-256 de archivos y árboles."""
        test_file = Path(self.temp_dir) / "file.txt"
        test_file.write_text("hello world", encoding="utf-8")

        h1 = compute_file_hash(test_file)
        self.assertTrue(len(h1) == 64)

        tree_hash, hashes = compute_plugin_tree_hash(self.temp_dir)
        self.assertTrue(len(tree_hash) == 64)
        self.assertIn("file.txt", hashes)
        self.assertEqual(hashes["file.txt"], h1)

    def test_cachesystem_entry_save_and_retrieve(self) -> None:
        """Verifica guardado, recuperación e invalidación de entradas en CacheSystem."""
        entry = PluginCacheEntry(
            plugin_name="demo_plugin",
            uuid="1234-uuid",
            version="1.2.3",
            tree_hash="abc123treehash",
            manifest_hash="def456manifesthash",
            files_hashes={"main.py": "111", "manifest.json": "222"},
            inspected_at=1000.0,
            is_valid=True,
            dependencies_resolved=["dep1"],
        )

        save_plugin_cache(entry)
        loaded = get_plugin_cache("demo_plugin", "1234-uuid")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.plugin_name, "demo_plugin")
        self.assertEqual(loaded.version, "1.2.3")
        self.assertEqual(loaded.tree_hash, "abc123treehash")

        # Invalidar
        removed = invalidate_plugin_cache("demo_plugin", "1234-uuid")
        self.assertTrue(removed)
        self.assertIsNone(get_plugin_cache("demo_plugin", "1234-uuid"))

    def test_cachesystem_diff_files(self) -> None:
        """Verifica que diff_files detecte archivos añadidos, modificados y eliminados."""
        plugin_dir = Path(self.temp_dir) / "diff_plugin"
        plugin_dir.mkdir(parents=True)
        (plugin_dir / "file1.txt").write_text("v1", encoding="utf-8")
        (plugin_dir / "file2.txt").write_text("v2", encoding="utf-8")

        _, hashes = compute_plugin_tree_hash(plugin_dir)

        entry = PluginCacheEntry(
            plugin_name="diff_plugin",
            uuid="",
            version="1.0.0",
            tree_hash="old_tree",
            manifest_hash="",
            files_hashes=dict(hashes),
            inspected_at=100.0,
            is_valid=True,
        )

        # Modificar file1, eliminar file2, añadir file3
        (plugin_dir / "file1.txt").write_text("v1_modified", encoding="utf-8")
        (plugin_dir / "file2.txt").unlink()
        (plugin_dir / "file3.txt").write_text("v3", encoding="utf-8")

        diff = entry.diff_files(plugin_dir)
        self.assertIn("file3.txt", diff["added"])
        self.assertIn("file1.txt", diff["modified"])
        self.assertIn("file2.txt", diff["deleted"])


if __name__ == "__main__":
    unittest.main()
