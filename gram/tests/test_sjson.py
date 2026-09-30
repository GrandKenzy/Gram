"""
Pruebas Unitarias del Subsistema SJSON (`gram.tests.test_sjson`).
================================================================
Valida exhaustivamente los 4 requisitos clave de SJSON:
  1. Variables numéricas y strings exclusivamente (con validación de tipos).
  2. Cálculos y expresiones aritméticas (+, -, *, /, %, unary, paréntesis, concatenación).
  3. Comentarios con '//' en cualquier posición del documento.
  4. Importación y herencia de otros JSON mediante '{ extend: "ruta" }'.
  5. Compilación determinista a JSON común y corriente (RFC 8259).
"""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from gram import config
from gram.sjson import (
    SJSONCalculationError,
    SJSONCompiler,
    SJSONError,
    SJSONExtendError,
    SJSONVariableError,
    compile as sjson_compile,
    compile_file,
    parse as sjson_parse,
)


class TestSJSONSystem(unittest.TestCase):
    """Suite de pruebas unitarias para SJSON."""

    def setUp(self) -> None:
        self.old_hide_console = config.ERROR_HIDE_CONSOLE
        self.old_exit_on_error = config.ERROR_EXIT_ON_ERROR
        config.ERROR_HIDE_CONSOLE = True
        config.ERROR_EXIT_ON_ERROR = False
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self) -> None:
        config.ERROR_HIDE_CONSOLE = self.old_hide_console
        config.ERROR_EXIT_ON_ERROR = self.old_exit_on_error
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        from gram.core.lexer import words
        for kw in ("let", "var", "extend", "true", "false", "null"):
            if words.keyword_exists(kw):
                words.remove_keyword(kw)

    # =========================================================================
    # 1. PRUEBAS DE VARIABLES (NUMÉRICAS Y STRINGS SOLAMENTE)
    # =========================================================================

    def test_numeric_and_string_variables(self) -> None:
        src = """
        let port = 8080
        let host = "127.0.0.1"
        let factor = 1.5
        var timeout = 30
        {
            "host": host,
            "port": port,
            "factor": factor,
            "timeout": timeout
        }
        """
        data = sjson_parse(src)
        self.assertEqual(data["host"], "127.0.0.1")
        self.assertEqual(data["port"], 8080)
        self.assertEqual(data["factor"], 1.5)
        self.assertEqual(data["timeout"], 30)

    def test_variable_reusing_other_variables(self) -> None:
        src = """
        let base = 100
        let double_base = base * 2
        let prefix = "api_"
        let full_name = prefix + "service"
        {
            "double": double_base,
            "name": full_name
        }
        """
        data = sjson_parse(src)
        self.assertEqual(data["double"], 200)
        self.assertEqual(data["name"], "api_service")

    def test_reject_boolean_variables(self) -> None:
        src = """
        let is_active = true
        {
            "active": is_active
        }
        """
        with self.assertRaises(SJSONVariableError) as ctx:
            sjson_parse(src)
        self.assertIn("Solo se permiten variables numéricas", str(ctx.exception))

    def test_reject_object_variables(self) -> None:
        src = """
        let my_obj = { "k": 1 }
        {
            "sub": my_obj
        }
        """
        with self.assertRaises(SJSONVariableError) as ctx:
            sjson_parse(src)
        self.assertIn("Solo se permiten variables numéricas", str(ctx.exception))

    def test_reject_array_variables(self) -> None:
        src = """
        let my_list = [1, 2, 3]
        {
            "list": my_list
        }
        """
        with self.assertRaises(SJSONVariableError) as ctx:
            sjson_parse(src)
        self.assertIn("Solo se permiten variables numéricas", str(ctx.exception))

    def test_reject_undefined_variable(self) -> None:
        src = """
        {
            "val": undefined_variable_name
        }
        """
        with self.assertRaises(SJSONVariableError) as ctx:
            sjson_parse(src)
        self.assertIn("no definida", str(ctx.exception))

    # =========================================================================
    # 2. PRUEBAS DE CÁLCULOS
    # =========================================================================

    def test_arithmetic_calculations(self) -> None:
        src = """
        let x = 10
        let y = 20
        {
            "sum": 5 + 15,
            "diff": 50 - 20,
            "prod": 6 * 7,
            "div_exact": 100 / 4,
            "div_float": 7 / 2,
            "mod": 10 % 3,
            "unary_neg": -x,
            "unary_pos": +y,
            "precedence": 2 + 3 * 4,
            "parentheses": (2 + 3) * 4
        }
        """
        data = sjson_parse(src)
        self.assertEqual(data["sum"], 20)
        self.assertEqual(data["diff"], 30)
        self.assertEqual(data["prod"], 42)
        self.assertEqual(data["div_exact"], 25)
        self.assertEqual(data["div_float"], 3.5)
        self.assertEqual(data["mod"], 1)
        self.assertEqual(data["unary_neg"], -10)
        self.assertEqual(data["unary_pos"], 20)
        self.assertEqual(data["precedence"], 14)
        self.assertEqual(data["parentheses"], 20)

    def test_string_concatenation_calculations(self) -> None:
        src = """
        let domain = "example.com"
        let port = 8080
        {
            "greeting": "Hello " + "World",
            "url": "http://" + domain + ":" + port,
            "message": "Puerto asignado: " + (port + 1)
        }
        """
        data = sjson_parse(src)
        self.assertEqual(data["greeting"], "Hello World")
        self.assertEqual(data["url"], "http://example.com:8080")
        self.assertEqual(data["message"], "Puerto asignado: 8081")

    def test_division_by_zero_error(self) -> None:
        src = """
        {
            "fail": 100 / 0
        }
        """
        with self.assertRaises(SJSONCalculationError) as ctx:
            sjson_parse(src)
        self.assertIn("División por cero", str(ctx.exception))

    # =========================================================================
    # 3. PRUEBAS DE COMENTARIOS CON '//'
    # =========================================================================

    def test_comments_with_double_slash(self) -> None:
        src = """
        // Comentario en cabecera
        // Segunda línea de comentario
        let a = 10 // Comentario después de variable
        
        // Comentario antes del objeto
        {
            // Comentario dentro del objeto
            "key1": "value1", // Comentario en par clave: valor
            // Comentario intermedio
            "key2": 42,
            "list": [
                // Comentario dentro de array
                1, // Comentario tras elemento
                2,
                3 // Trailing comment
            ]
        }
        // Comentario al final del archivo
        """
        data = sjson_parse(src)
        self.assertEqual(data["key1"], "value1")
        self.assertEqual(data["key2"], 42)
        self.assertEqual(data["list"], [1, 2, 3])

    # =========================================================================
    # 4. PRUEBAS DE EXTEND (IMPORTAR OTROS JSON)
    # =========================================================================

    def test_extend_json_inheritance(self) -> None:
        base_file = self.temp_dir / "base.json"
        base_file.write_text(json.dumps({
            "app": "BaseApp",
            "version": 1.0,
            "timeout": 30,
            "network": {
                "host": "localhost",
                "port": 80
            }
        }))

        sjson_src = f"""
        let port_offset = 8000
        {{
            extend: "{base_file.name}",
            "version": 2.0,
            "network": {{
                "port": port_offset + 80
            }},
            "author": "Kentucky"
        }}
        """

        compiler = SJSONCompiler(sjson_src, base_dir=self.temp_dir)
        data = compiler.compile()

        # Debe conservar las claves heredadas
        self.assertEqual(data["app"], "BaseApp")
        self.assertEqual(data["timeout"], 30)
        self.assertEqual(data["network"]["host"], "localhost")
        # Debe sobrescribir las claves modificadas
        self.assertEqual(data["version"], 2.0)
        self.assertEqual(data["network"]["port"], 8080)
        self.assertEqual(data["author"], "Kentucky")
        # La clave 'extend' no debe figurar en el resultado
        self.assertNotIn("extend", data)

    def test_extend_chained_sjson(self) -> None:
        root_file = self.temp_dir / "root.json"
        root_file.write_text(json.dumps({"env": "staging", "debug": True}))

        mid_file = self.temp_dir / "middle.sjson"
        mid_file.write_text(f"""
        let factor = 10
        {{
            extend: "{root_file.name}",
            "limit": 5 * factor
        }}
        """)

        leaf_src = f"""
        {{
            extend: "{mid_file.name}",
            "env": "production"
        }}
        """

        data = sjson_parse(leaf_src, base_dir=self.temp_dir)
        self.assertEqual(data["env"], "production")
        self.assertEqual(data["debug"], True)
        self.assertEqual(data["limit"], 50)
        self.assertNotIn("extend", data)

    def test_extend_circular_dependency_detected(self) -> None:
        file_a = self.temp_dir / "a.sjson"
        file_b = self.temp_dir / "b.sjson"

        file_a.write_text('{\n extend: "b.sjson"\n}')
        file_b.write_text('{\n extend: "a.sjson"\n}')

        with self.assertRaises(SJSONExtendError) as ctx:
            sjson_parse(file_a.read_text(), base_dir=self.temp_dir)
        self.assertIn("Dependencia circular", str(ctx.exception))

    def test_extend_missing_file_raises_error(self) -> None:
        src = '{\n extend: "archivo_inexistente.json"\n}'
        with self.assertRaises(SJSONExtendError) as ctx:
            sjson_parse(src, base_dir=self.temp_dir)
        self.assertIn("No se encontró el archivo referenciado en extend", str(ctx.exception))

    # =========================================================================
    # 5. PRUEBAS DE COMPILACIÓN A JSON ESTÁNDAR
    # =========================================================================

    def test_compile_returns_valid_standard_json_string(self) -> None:
        src = """
        // Configuración SJSON
        let base = 500
        {
            "name": "Gram App",
            "capacity": base * 2,
            "is_ready": true,
            "deleted": null
        }
        """
        json_output = sjson_compile(src, indent=2)
        self.assertIsInstance(json_output, str)

        # Debe parsearse sin errores con el módulo json estándar de Python (RFC 8259)
        parsed = json.loads(json_output)
        self.assertEqual(parsed["name"], "Gram App")
        self.assertEqual(parsed["capacity"], 1000)
        self.assertEqual(parsed["is_ready"], True)
        self.assertIsNone(parsed["deleted"])

    def test_compile_file_end_to_end(self) -> None:
        base_json = self.temp_dir / "base.json"
        base_json.write_text(json.dumps({"org": "Gram Community", "tier": "free"}))

        sjson_file = self.temp_dir / "service.sjson"
        sjson_file.write_text(f"""
        // Comentarios permitidos
        let port = 9000
        let service = "auth"
        {{
            extend: "{base_json.name}",
            "service_name": service + "-srv",
            "port": port + 1,
            "tier": "enterprise"
        }}
        """)

        out_path = compile_file(sjson_file)
        self.assertTrue(out_path.exists())
        self.assertEqual(out_path.suffix, ".json")

        content = json.loads(out_path.read_text(encoding="utf-8"))
        self.assertEqual(content["org"], "Gram Community")
        self.assertEqual(content["tier"], "enterprise")
        self.assertEqual(content["service_name"], "auth-srv")
        self.assertEqual(content["port"], 9001)
        self.assertNotIn("extend", content)


if __name__ == "__main__":
    unittest.main()
