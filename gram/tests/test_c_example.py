"""
Pruebas Unitarias del Motor CExample (`gram.tests.test_c_example`).
===================================================================
Valida el funcionamiento del analizador sintáctico para C basado en Gram:
  1. Registro de palabras clave de C en el Lexer.
  2. Declaraciones de variables escalares, punteros e inicializadores.
  3. Prototipos y definiciones completas de funciones.
  4. Sentencias de control de flujo (if/else, while, for, return).
  5. Expresiones aritméticas, relacionales y llamadas anidadas.
  6. Manejo de preprocesador (#include) y comentarios (// y /* ... */).
  7. Extracción de símbolos y formateo jerárquico del AST.
  8. Análisis end-to-end del archivo sample.c.
"""
from __future__ import annotations

import unittest
from pathlib import Path

from examples.CExample.c_parser import CParser, parse_c, parse_c_file
from examples.CExample.grammar import (
    C_BLOCK,
    C_FUNC_DECL,
    C_FUNC_DEF,
    C_IF_STMT,
    C_RETURN_STMT,
    C_VAR_DECL,
    C_WHILE_STMT,
    get_c_grammar,
    setup_c_keywords,
)
from gram.core.lexer import words


class TestCExample(unittest.TestCase):
    """Suite de pruebas unitarias para el motor CExample de Gram."""

    @classmethod
    def setUpClass(cls) -> None:
        setup_c_keywords()
        cls.parser = CParser()

    def test_c_keywords_registered(self) -> None:
        """Verifica que las palabras clave esenciales de C estén en el Lexer."""
        for kw in ("int", "char", "void", "if", "else", "while", "for", "return", "const"):
            self.assertTrue(words.keyword_exists(kw), f"Palabra clave de C '{kw}' no registrada.")

    def test_variable_declarations(self) -> None:
        """Verifica declaraciones de variables simples, punteros y con inicialización."""
        code = """
        int x;
        float y = 3.14;
        char* message = "hola mundo";
        """
        ast = self.parser.parse(code)
        self.assertEqual(len(ast.body), 3)
        for node in ast.body:
            self.assertEqual(node.name, "C_VAR_DECL")

        symbols = self.parser.extract_symbols(ast)
        var_names = [v["name"] for v in symbols["variables"]]
        self.assertIn("x", var_names)
        self.assertIn("y", var_names)
        self.assertIn("message", var_names)

    def test_function_prototype(self) -> None:
        """Verifica la detección y parseo de prototipos de función (C_FUNC_DECL)."""
        code = "int calculate_sum(int a, int b);"
        ast = self.parser.parse(code)
        self.assertEqual(len(ast.body), 1)
        self.assertEqual(ast.body[0].name, "C_FUNC_DECL")

        symbols = self.parser.extract_symbols(ast)
        self.assertEqual(len(symbols["functions"]), 1)
        fn = symbols["functions"][0]
        self.assertEqual(fn["name"], "calculate_sum")
        self.assertEqual(fn["return_type"], "int")
        self.assertFalse(fn["is_definition"])

    def test_function_definition(self) -> None:
        """Verifica la definición completa de una función con cuerpo (C_FUNC_DEF)."""
        code = """
        int multiply(int x, int y) {
            return x * y;
        }
        """
        ast = self.parser.parse(code)
        self.assertEqual(len(ast.body), 1)
        self.assertEqual(ast.body[0].name, "C_FUNC_DEF")

        symbols = self.parser.extract_symbols(ast)
        self.assertEqual(len(symbols["functions"]), 1)
        fn = symbols["functions"][0]
        self.assertEqual(fn["name"], "multiply")
        self.assertTrue(fn["is_definition"])

    def test_control_flow_statements(self) -> None:
        """Verifica sentencias if-else, while y for dentro de funciones."""
        code = """
        void process(int n) {
            if (n > 0) {
                return 1;
            } else {
                return 0;
            }
            while (n < 10) {
                n = n + 1;
            }
        }
        """
        ast = self.parser.parse(code)
        self.assertEqual(len(ast.body), 1)
        self.assertEqual(ast.body[0].name, "C_FUNC_DEF")

        # Inspeccionar nodos hijos del bloque
        func_def = ast.body[0]
        block_node = None
        for child in func_def.children:
            if child.name == "C_BLOCK":
                block_node = child
                break
        self.assertIsNotNone(block_node)
        stmt_names = [child.name for child in block_node.children]
        self.assertIn("C_IF_STMT", stmt_names)
        self.assertIn("C_WHILE_STMT", stmt_names)

    def test_preprocessor_includes_and_comments(self) -> None:
        """Verifica extracción de #include y eliminación de comentarios de bloque /* */."""
        code = """
        /* Comentario de encabezado multilínea
           que abarca varias líneas */
        #include <stdlib.h>
        #include "custom.h"

        // Comentario de una línea
        int status = 0;
        """
        ast = self.parser.parse(code)
        self.assertEqual(len(ast.body), 1)
        self.assertEqual(ast.body[0].name, "C_VAR_DECL")

        includes = getattr(ast, "includes", [])
        self.assertEqual(len(includes), 2)
        self.assertEqual(includes[0], "<stdlib.h>")
        self.assertEqual(includes[1], '"custom.h"')

    def test_sample_c_full_program(self) -> None:
        """Verifica la compilación y análisis completo del archivo de muestra sample.c."""
        sample_file = Path(__file__).resolve().parent.parent.parent / "examples" / "CExample" / "sample.c"
        self.assertTrue(sample_file.exists(), f"sample.c no encontrado en {sample_file}")

        ast = self.parser.parse_file(sample_file)
        self.assertEqual(len(ast.body), 6, "sample.c debe contener exactamente 6 declaraciones raíz")

        symbols = self.parser.extract_symbols(ast)
        self.assertIn("<stdio.h>", symbols["includes"])
        self.assertEqual(len(symbols["variables"]), 1)
        self.assertEqual(symbols["variables"][0]["name"], "g_max_iterations")

        func_names = [f["name"] for f in symbols["functions"]]
        self.assertIn("add", func_names)
        self.assertIn("factorial", func_names)
        self.assertIn("sum_to_n", func_names)
        self.assertIn("main", func_names)

    def test_format_tree_ascii(self) -> None:
        """Verifica que el formateo de árbol ASCII funcione de manera limpia y sin errores."""
        code = "int a = 10;"
        ast = self.parser.parse(code)
        tree = self.parser.format_tree(ast, ascii_only=True)
        self.assertIn("ASTProgram", tree)
        self.assertIn("C_VAR_DECL", tree)
        self.assertIn("+--", tree)


if __name__ == "__main__":
    unittest.main()
