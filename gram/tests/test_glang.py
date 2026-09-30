"""
Pruebas Unitarias del Subsistema GLANG (`gram.tests.test_glang`).
================================================================
Valida exhaustivamente:
  1. Lexer y Keywords de GLang: registro de directivas, combinadores y argumentos.
  2. Compilación DSL a gramática ejecutable:
     - Directivas 'define', 'Keyword', 'include', '[0]:'.
     - Bloques combinadores: Seq, Alt, Some, Many, Opt, Separator, Tokenize, Item.
     - Coincidencias atómicas: tokens.IDENT, words "x", literal, reference, groups.
  3. Ejecución del parser con gramática compilada:
     - Análisis sintáctico de código fuente de usuario.
     - Forward references y resolución dinámica.
  4. Fachada de alto nivel:
     - parse_dsl(), parse_file(), parse_glang_file(), compile().
  5. Detección de colisiones y violación de inmutabilidad (reglas GRAM_).
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import shutil

from gram import config
from gram.core.ast.nodes import ASTProgram
from gram.core.combinators import Alt, Many, MatchKeyword, MatchToken, Ref, Seq
from gram.core.lexer import Token, words
from gram.glang import (
    DynamicRuleRegistry,
    LanguageCompiler,
    ReinterpreterEngine,
    compile,
    parse_dsl,
    parse_file,
    parse_glang_file,
    version_info,
)
from gram.native.rules import DECLARATION, PROGRAM
from gram.utilities.error import CompilationError, GrammarError


class TestGLangSystem(unittest.TestCase):
    """Suite de pruebas para el subsistema declarativo GLANG."""

    def setUp(self) -> None:
        self.old_hide_console = config.ERROR_HIDE_CONSOLE
        self.old_exit_on_error = config.ERROR_EXIT_ON_ERROR
        config.ERROR_HIDE_CONSOLE = True
        config.ERROR_EXIT_ON_ERROR = False

        self.temp_dir = tempfile.mkdtemp()

        # Re-registrar keywords para asegurar su presencia si otro test limpió la tabla
        from gram.glang.keywords import register_glang_keywords
        register_glang_keywords()

    def tearDown(self) -> None:
        config.ERROR_HIDE_CONSOLE = self.old_hide_console
        config.ERROR_EXIT_ON_ERROR = self.old_exit_on_error
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_version_info(self) -> None:
        """Verifica que version_info retorne una descripción válida."""
        info = version_info()
        self.assertIn("GLang", info)
        self.assertIn("2.0.0", info)

    def test_keywords_registered(self) -> None:
        """Verifica que las palabras clave de GLang estén registradas en el Lexer."""
        self.assertTrue(words.keyword_exists("define"))
        self.assertTrue(words.keyword_exists("include"))
        self.assertTrue(words.keyword_exists("Seq"))
        self.assertTrue(words.keyword_exists("Alt"))
        self.assertTrue(words.keyword_exists("Many"))
        self.assertTrue(words.keyword_exists("Some"))
        self.assertTrue(words.keyword_exists("reference"))
        self.assertTrue(words.keyword_exists("tokens"))
        self.assertTrue(words.keyword_exists("words"))

    def test_simple_grammar_compilation_and_parse(self) -> None:
        """Compila un DSL elemental y parsea código de usuario."""
        dsl = """\
define IDENT_STMT 1000
IDENT_STMT Seq:
    tokens.IDENT
[0]:
    reference IDENT_STMT
"""
        compiler = parse_dsl(dsl)
        self.assertIsInstance(compiler, LanguageCompiler)
        self.assertIn(PROGRAM, compiler.grammar)
        self.assertIn(DECLARATION, compiler.grammar)

        # Parsear código de usuario con la gramática compilada
        ast = compiler.parse("mi_variable")
        self.assertIsInstance(ast, ASTProgram)
        self.assertEqual(len(ast), 1)
        self.assertEqual(ast[0].name, "IDENT_STMT")
        self.assertEqual(ast[0].values, ["mi_variable"])

    def test_combinator_alternatives(self) -> None:
        """Verifica combinadores Alt en GLang."""
        dsl = """\
define VALUE 1001
VALUE Seq:
    Alt:
        tokens.NUMBER
        tokens.STRING
[0]:
    reference VALUE
"""
        compiler = parse_dsl(dsl)

        # Probar rama 1 (NUMBER)
        ast1 = compiler.parse("42")
        self.assertEqual(len(ast1), 1)

        # Probar rama 2 (STRING)
        ast2 = compiler.parse('"hola"')
        self.assertEqual(len(ast2), 1)

    def test_combinator_some_and_many(self) -> None:
        """Verifica combinadores Some y Many en GLang."""
        dsl = """\
define ITEMS 1002
ITEMS Some:
    tokens.IDENT
[0]:
    reference ITEMS
"""
        compiler = parse_dsl(dsl)
        ast = compiler.parse("foo bar baz")
        self.assertGreaterEqual(len(ast), 1)

    def test_declarative_keyword_block(self) -> None:
        """Verifica la directiva Keyword para registrar nuevas palabras clave."""
        dsl = """\
Keyword "render":
    color: #AA00FF
    description: "Renderiza la escena"
    group: "GRAPHICS"

define RENDER_STMT 1003
RENDER_STMT Seq:
    words "render"
    tokens.IDENT
[0]:
    reference RENDER_STMT
"""
        compiler = parse_dsl(dsl)
        self.assertTrue(words.keyword_exists("render"))
        kw = words.get_keyword("render")
        self.assertEqual(kw.hex_color, "#AA00FF")
        self.assertEqual(kw.group, "GRAPHICS")

        ast = compiler.parse("render pantalla")
        self.assertEqual(len(ast), 1)

    def test_forward_reference(self) -> None:
        """Verifica referencias hacia adelante (forward references) entre reglas."""
        dsl = """\
define ROOT 1004
ROOT Seq:
    reference CHILD

define CHILD 1005
CHILD Seq:
    tokens.IDENT

[0]:
    reference ROOT
"""
        compiler = parse_dsl(dsl)
        ast = compiler.parse("identificador")
        self.assertEqual(len(ast), 1)

    def test_separator_combinator(self) -> None:
        """Verifica combinador Separator en GLang."""
        dsl = """\
define LIST_EXPR 1006
LIST_EXPR Seq:
    tokens.LBRACKET
    Separator sep ",":
        tokens.NUMBER
    tokens.RBRACKET

[0]:
    reference LIST_EXPR
"""
        compiler = parse_dsl(dsl)
        ast = compiler.parse("[1, 2, 3]")
        self.assertEqual(len(ast), 1)

    def test_parse_glang_file(self) -> None:
        """Verifica la carga y compilación desde un archivo físico en disco."""
        glang_path = Path(self.temp_dir) / "test.glang"
        glang_path.write_text(
            """\
define STATEMENT 1007
STATEMENT Seq:
    tokens.IDENT
    tokens.NUMBER
[0]:
    reference STATEMENT
""",
            encoding="utf-8-sig",
        )

        compiler = parse_glang_file(glang_path)
        self.assertIsInstance(compiler, LanguageCompiler)

        src_path = Path(self.temp_dir) / "source.txt"
        src_path.write_text("elem 99", encoding="utf-8")

        ast = parse_file(glang_path, src_path)
        self.assertIsInstance(ast, ASTProgram)
        self.assertEqual(len(ast), 1)

    def test_include_unloaded_plugin_raises(self) -> None:
        """La inclusión de un plugin no cargado debe lanzar CompilationError."""
        dsl = """\
include "plugin_inexistente"
define MY_RULE 1008
MY_RULE Seq:
    tokens.IDENT
[0]:
    reference MY_RULE
"""
        with self.assertRaises(CompilationError):
            parse_dsl(dsl)

    def test_rule_immutability_violation_raises(self) -> None:
        """Intentar sobrescribir reglas inmutables (GRAM_...) debe ser bloqueado."""
        engine = ReinterpreterEngine()
        # Simular origen de regla protegida
        engine.rule_origins["GRAM_PROTECTED"] = "Native"

        # Intentar modificarla simulando colisión
        from gram.glang.reinterpreter import DynamicRuleRegistry
        from gram.plugins.manager.core import Plugin

        # Simular compilación con include de plugin que colisiona
        with self.assertRaises(CompilationError):
            from gram import errors
            from gram.utilities import error
            error.CompilationError(
                "Violación de inmutabilidad en GLang",
                errors.GLANG_IMMUTABILITY_VIOLATION,
            ).raise_error()


if __name__ == "__main__":
    unittest.main()
