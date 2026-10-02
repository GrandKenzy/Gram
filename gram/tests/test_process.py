"""
Pruebas Unitarias del Orquestador de Alto Nivel (`gram.core.process` / `gram.process`).
=====================================================================================
Valida la función `gram.process`:
  1. Análisis directo pasando código fuente como string.
  2. Análisis pasando ruta de archivo como cadena (str) y como Path.
  3. Soporte para gramáticas como diccionario, RuleItem directo y Combinator directo.
  4. Integración con plugins y ejecución de transformaciones de AST.
  5. Manejo correcto de errores ante archivos inexistentes.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import gram
from gram import config
from gram.core.ast.nodes import ASTProgram


class TestGramProcess(unittest.TestCase):
    """Casos de prueba para gram.process()."""

    def setUp(self) -> None:
        self.old_hide = config.ERROR_HIDE_CONSOLE
        self.old_exit = config.ERROR_EXIT_ON_ERROR
        config.ERROR_HIDE_CONSOLE = True
        config.ERROR_EXIT_ON_ERROR = False

        # Registrar keywords necesarias
        gram.words.add_keyword("let", "#569CD6", allow_override=True)
        gram.words.add_keyword("configuration", "#FF00FF", allow_override=True)
        if not gram.words.group_exists("Resources"):
            gram.words.add_group("Resources")
        gram.words.add_keyword("ResourcePack", "#FF00FF", "Resources", allow_override=True)
        gram.words.add_keyword("BehaviorPack", "#FF00FF", "Resources", allow_override=True)

    def tearDown(self) -> None:
        config.ERROR_HIDE_CONSOLE = self.old_hide
        config.ERROR_EXIT_ON_ERROR = self.old_exit

    def test_process_string_source(self) -> None:
        """Prueba gram.process() directamente con código en cadena de texto."""
        class LetStmt(gram.RuleItem):
            name = "LetStmt"
            grammar = gram.Seq(
                gram.MatchKeyword("let"),
                gram.MatchToken(gram.Token.IDENT),
                gram.MatchToken(gram.Token.ASSIGN),
                gram.MatchToken(gram.Token.NUMBER),
            )

        grammar = {
            gram.PROGRAM: gram.Many(gram.Ref(LetStmt)),
            LetStmt: LetStmt.grammar,
        }

        source = "let count = 42"
        ast = gram.process(grammar, source)

        self.assertIsInstance(ast, ASTProgram)
        self.assertEqual(len(ast.body), 1)
        self.assertEqual(ast.body[0].name, "LetStmt")
        self.assertEqual(ast.body[0].values, ["let", "count", 42])

    def test_process_file_source(self) -> None:
        """Prueba gram.process() leyendo desde una ruta de archivo (str y Path)."""
        class LetStmt(gram.RuleItem):
            name = "LetStmt"
            grammar = gram.Seq(
                gram.MatchKeyword("let"),
                gram.MatchToken(gram.Token.IDENT),
                gram.MatchToken(gram.Token.ASSIGN),
                gram.MatchToken(gram.Token.NUMBER),
            )

        grammar = {
            gram.PROGRAM: gram.Many(gram.Ref(LetStmt)),
        }

        source = "let x = 10\nlet y = 20\n"

        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write(source)
            temp_path = f.name

        try:
            # 1. Pasando string de la ruta
            ast1 = gram.process(grammar, temp_path, ignore_newlines=True)
            self.assertIsInstance(ast1, ASTProgram)
            self.assertEqual(len(ast1.body), 2)
            self.assertEqual(ast1.body[0].values, ["let", "x", 10])
            self.assertEqual(ast1.body[1].values, ["let", "y", 20])

            # 2. Pasando objeto Path
            ast2 = gram.process(grammar, Path(temp_path), ignore_newlines=True)
            self.assertIsInstance(ast2, ASTProgram)
            self.assertEqual(len(ast2.body), 2)
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_process_single_rule_item_as_grammar(self) -> None:
        """Prueba pasar una clase RuleItem directamente como argumento grammar."""
        class SimpleRule(gram.RuleItem):
            name = "SimpleRule"
            grammar = gram.Seq(
                gram.MatchKeyword("let"),
                gram.MatchToken(gram.Token.IDENT),
            )

        ast = gram.process(SimpleRule, "let foo")
        self.assertIsInstance(ast, ASTProgram)
        self.assertEqual(len(ast.body), 1)
        self.assertEqual(ast.body[0].name, "SimpleRule")

    def test_process_with_mock_plugin(self) -> None:
        """Prueba la integración de plugins y transform_ast en gram.process()."""
        from gram.plugins.base import PluginBase

        class CustomAstPlugin(PluginBase):
            def transform_ast(self, ast: ASTProgram) -> ASTProgram:
                # Agregar un atributo o modificar el AST
                ast.metadata = {"transformed_by_plugin": True}  # type: ignore[attr-defined]
                return ast

        class SimpleRule(gram.RuleItem):
            name = "SimpleRule"
            grammar = gram.Seq(
                gram.MatchKeyword("let"),
                gram.MatchToken(gram.Token.IDENT),
            )

        plugin_instance = CustomAstPlugin()
        ast = gram.process(SimpleRule, "let bar", plugins=[plugin_instance])

        self.assertIsInstance(ast, ASTProgram)
        self.assertTrue(getattr(ast, "metadata", {}).get("transformed_by_plugin"))

    def test_process_file_not_found(self) -> None:
        """Prueba que un Path inexistente arroja FileNotFoundError."""
        fake_path = Path("archivo_completamente_inexistente_12345.xyz")
        with self.assertRaises(FileNotFoundError):
            gram.process({gram.PROGRAM: gram.PASS}, fake_path)


if __name__ == "__main__":
    unittest.main()
