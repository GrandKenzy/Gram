"""
Pruebas Unitarias del Catálogo Centralizado de Errores (gram.errors).
=====================================================================
Valida la integridad del estándar OSGDC, la completitud del catálogo,
la seguridad de los códigos generados y las funciones de consulta.
"""
from __future__ import annotations

import unittest
from gram import errors
from gram.utilities import error


class TestGramErrors(unittest.TestCase):
    """Suite de pruebas para el catálogo oficial de errores de Gram."""

    def test_all_errors_integrity(self) -> None:
        """Verifica que todos los errores registrados cumplan con el estándar OSGDC."""
        all_errs = errors.all_errors()
        self.assertGreaterEqual(len(all_errs), 52, "El catálogo debe contener al menos los 52 errores base.")

        for err in all_errs:
            with self.subTest(error_name=err.name):
                self.assertIsInstance(err, error.codes.CodeError)
                self.assertEqual(len(err.code_string), 5, f"{err.name} debe tener 5 dígitos OSGDC.")
                self.assertTrue(err.code_string.isdigit(), f"{err.code_string} debe ser numérico.")
                self.assertTrue(err.safe, f"El error {err.name} ({err.code_string}) debe estar dentro de los límites seguros.")
                self.assertEqual(err.type, "S", f"El tipo del error {err.name} debe ser Standard ('S').")
                self.assertTrue(err.name.startswith("Gram."), f"El nombre canónico {err.name} debe iniciar con 'Gram.'.")

    def test_lookup_by_code(self) -> None:
        """Verifica la resolución de errores por código en múltiples formatos."""
        # Búsqueda por entero
        err_int = errors.get_error_by_code(11010)
        self.assertIsNotNone(err_int)
        self.assertEqual(err_int.name, "Gram.Lexer.EmptyKeywords")

        # Búsqueda por tupla
        err_tuple = errors.get_error_by_code((1, 2, 4, 1, 1))
        self.assertIsNotNone(err_tuple)
        self.assertEqual(err_tuple.name, "Gram.Parser.UnexpectedToken")

        # Búsqueda por cadena de dígitos
        err_str = errors.get_error_by_code("12411")
        self.assertIsNotNone(err_str)
        self.assertEqual(err_str.name, "Gram.Parser.UnexpectedToken")

        # Búsqueda por cadena formateada 'S-XXXXX'
        err_formatted = errors.get_error_by_code("S-23411")
        self.assertIsNotNone(err_formatted)
        self.assertEqual(err_formatted.name, "Gram.Plugin.ManifestNotFound")

        # Búsqueda de ANY_NOT_IMPLEMENTED (código 13102 con SHOULD_REPAIR)
        err_any = errors.get_error_by_code(13102)
        self.assertIsNotNone(err_any)
        self.assertEqual(err_any.name, "Gram.Combinator.NotImplemented")

        # Búsqueda de código inexistente
        self.assertIsNone(errors.get_error_by_code(99999))

    def test_lookup_by_name(self) -> None:
        """Verifica la resolución de errores por nombre exacto y corto."""
        # Nombre exacto
        err_exact = errors.get_error_by_name("Gram.Parser.EarlyEOF")
        self.assertIsNotNone(err_exact)
        self.assertEqual(err_exact.code_string, "12411")

        # Nombre insensible a mayúsculas
        err_case = errors.get_error_by_name("gram.parser.earlyeof")
        self.assertIsNotNone(err_case)
        self.assertEqual(err_case, errors.PARSER_EARLY_EOF)

        # Sufijo / Nombre corto
        err_short = errors.get_error_by_name("EarlyEOF")
        self.assertIsNotNone(err_short)
        self.assertEqual(err_short, errors.PARSER_EARLY_EOF)

        # Nombre inexistente
        self.assertIsNone(errors.get_error_by_name("NonExistentErrorName"))

    def test_lookup_by_scope(self) -> None:
        """Verifica el filtrado de errores por ámbito/subsistema."""
        lexer_errs = errors.get_errors_by_scope(errors.LEXER_ERROR)
        self.assertEqual(len(lexer_errs), 12)
        for err in lexer_errs:
            self.assertEqual(err.code_string[1], "1")

        parser_errs = errors.get_errors_by_scope("parser")
        self.assertEqual(len(parser_errs), 3)
        for err in parser_errs:
            self.assertEqual(err.code_string[1], "2")

        grammar_errs = errors.get_errors_by_scope(errors.GRAMMAR_ERROR)
        self.assertGreaterEqual(len(grammar_errs), 12)

        semantic_errs = errors.get_errors_by_scope(errors.SEMANTIC_ERROR)
        self.assertEqual(len(semantic_errs), 6)
        for err in semantic_errs:
            self.assertEqual(err.code_string[1], "4")

        compilation_errs = errors.get_errors_by_scope("compilation")
        self.assertEqual(len(compilation_errs), 4)
        for err in compilation_errs:
            self.assertEqual(err.code_string[1], "5")

    def test_lookup_by_origin(self) -> None:
        """Verifica el filtrado por origen del componente emisor."""
        native_errs = errors.get_errors_by_origin(errors.NATIVE_ERROR)
        plugin_errs = errors.get_errors_by_origin("plugin")

        self.assertGreater(len(native_errs), 30)
        self.assertEqual(len(plugin_errs), 21)

        for err in plugin_errs:
            self.assertEqual(err.code_string[0], "2")

    def test_no_legacy_aliases(self) -> None:
        """Verifica que las variables viejas y alias redundantes hayan sido eliminados."""
        self.assertFalse(hasattr(errors, "FATAL_ERROR"), "FATAL_ERROR no debe existir; usar FATAL.")
        self.assertFalse(hasattr(errors, "INTERNAL_ERROR"), "INTERNAL_ERROR no debe existir; usar INTERNAL.")
        self.assertFalse(hasattr(errors, "DONT_REQUIRE_REPAIR_AND_NOT_USABLE"), "Variable antigua eliminada.")
        self.assertFalse(hasattr(errors, "REQUIRES_REPAIR_BUT_USABLE"), "Variable antigua eliminada.")
        self.assertFalse(hasattr(errors, "NOT_USABLE"), "NOT_USABLE fue omitido por redundancia.")

        # Verificar que solo existan los tres códigos de condición
        self.assertTrue(hasattr(errors, "USABLE"))
        self.assertTrue(hasattr(errors, "REQUIRES_REPAIR"))
        self.assertTrue(hasattr(errors, "SHOULD_REPAIR"))

        # Verificar que solo existan INTERNAL y FATAL
        self.assertTrue(hasattr(errors, "INTERNAL"))
        self.assertTrue(hasattr(errors, "FATAL"))

    def test_error_class_integration(self) -> None:
        """Verifica que los objetos CodeError se integren con la clase base Error."""
        err = error.Error(
            "Prueba de Error Léxico",
            errors.LEXER_UNEXPECTED_CHARACTER,
            "Línea 10: carácter '§' no soportado."
        )
        self.assertEqual(err.code, errors.LEXER_UNEXPECTED_CHARACTER)
        output = err.stringify(ansi=False)
        self.assertIn("S-11411", output)
        self.assertIn("Gram.Lexer.UnexpectedCharacter", output)
        self.assertIn("Prueba de Error Léxico", output)


if __name__ == "__main__":
    unittest.main()
