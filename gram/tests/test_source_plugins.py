"""
Pruebas Unitarias para los Plugins Oficiales en gram/plugins/source:
1. storage
2. expressions
3. GRAM_ESSENCIAL_PACK
"""
from __future__ import annotations

import unittest
from pathlib import Path

from gram.core.lexer import Lexer, Token, TokenType
from gram.core.parser.core import Parser
from gram.plugins.validator import validate_plugin
import gram.plugins.source.storage as storage
import gram.plugins.source.expressions as expressions
import gram.plugins.source.GRAM_ESSENCIAL_PACK as gep


class TestStoragePlugin(unittest.TestCase):
    """Pruebas del plugin storage."""

    def setUp(self):
        storage.StorageStacK.clear()

    def test_manifest_validation(self):
        plugin_dir = Path(storage.__file__).parent
        report = validate_plugin(plugin_dir)
        self.assertTrue(report.is_valid, f"Errores en storage manifest/auditoría: {report.errors}")
        self.assertEqual(report.plugin_name, "storage")

    def test_plugin_class_and_exports(self):
        p = storage.StoragePlugin()
        self.assertTrue(p.on_load())
        self.assertEqual(len(p.get_combinators()), 3)
        self.assertEqual(len(p.get_rules()), 3)
        self.assertIn("Save", [c.__name__ for c in storage.get_combinators()])
        self.assertIn("Load", [c.__name__ for c in storage.get_combinators()])
        self.assertIn("Tag", [c.__name__ for c in storage.get_combinators()])

    def test_storage_stack_operations(self):
        tok = TokenType(token=Token.IDENT, value="my_var", line=1, col=1)
        storage.StorageStacK.save("key1", tok)
        self.assertEqual(storage.StorageStacK.get("key1"), tok)
        self.assertIsNone(storage.StorageStacK.get("nonexistent"))
        storage.StorageStacK.clear()
        self.assertIsNone(storage.StorageStacK.get("key1"))

    def test_save_and_load_combinators(self):
        code = "test_var"
        tokens = Lexer(code).process()
        parser = Parser(tokens)
        tok = parser.consume()

        # Save combinator
        save_comb = storage.Save("x")
        res = save_comb.parse(parser, tok)
        self.assertEqual(res, tok)
        self.assertEqual(storage.StorageStacK.get("x"), tok)

        # Load combinator
        load_comb = storage.Load("x")
        loaded = load_comb.parse(parser, tok)
        self.assertEqual(loaded, tok)

    def test_tag_combinator(self):
        code = "x"
        tokens = Lexer(code).process()
        parser = Parser(tokens)
        tok = parser.consume()
        tag_comb = storage.Tag("my_tag")
        tagged = tag_comb.parse(parser, tok)
        self.assertIsNotNone(tagged)
        self.assertEqual(tagged.value, "tag.my_tag")


class TestExpressionsPlugin(unittest.TestCase):
    """Pruebas del plugin expressions."""

    def test_manifest_validation(self):
        plugin_dir = Path(expressions.__file__).parent
        report = validate_plugin(plugin_dir)
        self.assertTrue(report.is_valid, f"Errores en expressions manifest/auditoría: {report.errors}")
        self.assertEqual(report.plugin_name, "expressions")

    def test_plugin_class_and_exports(self):
        p = expressions.ExpressionsPlugin()
        self.assertTrue(p.on_load())
        combs = [c.__name__ for c in p.get_combinators()]
        self.assertIn("ChainL", combs)
        self.assertIn("ChainR", combs)
        self.assertIn("ExpressionBuilder", combs)
        self.assertIn("ArithmeticExpr", combs)
        self.assertIn("ConditionalExpr", combs)

        rules = [r.__name__ for r in p.get_rules()]
        self.assertIn("CONDITIONAL_EXPR", rules)
        self.assertIn("COMP_OP", rules)
        self.assertIn("LOGIC_OP", rules)

    def test_conditional_expr_combinator(self):
        class DummyAnalyzer:
            node = None
            def __init__(self, parser):
                self.parser = parser

        cond_comb = expressions.ConditionalExpr(allow_ident_boolean=True)

        # 1. Comparación aritmética válida: 10 + 20 > 5
        toks = Lexer("10 + 20 > 5").process()
        p = Parser(toks)
        t = p.consume()
        res = cond_comb.parse(DummyAnalyzer(p), t, ignore_errors=True)
        self.assertIsNotNone(res)
        self.assertEqual([x.value for x in res], [10, "+", 20, ">", 5])

        # 2. Expresión puramente aritmética: 10 + 20 (debe ser RECHAZADA)
        toks = Lexer("10 + 20").process()
        p = Parser(toks)
        t = p.consume()
        res = cond_comb.parse(DummyAnalyzer(p), t, ignore_errors=True)
        self.assertIsNone(res, "10 + 20 no debe ser aceptado como condición")

        # 3. Número solo: 42 (debe ser RECHAZADO)
        toks = Lexer("42").process()
        p = Parser(toks)
        t = p.consume()
        res = cond_comb.parse(DummyAnalyzer(p), t, ignore_errors=True)
        self.assertIsNone(res, "42 no debe ser aceptado como condición")

        # 4. Identificador como bandera booleana: activo (aceptado)
        toks = Lexer("activo").process()
        p = Parser(toks)
        t = p.consume()
        res = cond_comb.parse(DummyAnalyzer(p), t, ignore_errors=True)
        self.assertIsNotNone(res)
        self.assertEqual([x.value for x in res], ["activo"])

        # 5. Aritmética con identificador: activo + 1 (debe ser RECHAZADA)
        toks = Lexer("activo + 1").process()
        p = Parser(toks)
        t = p.consume()
        res = cond_comb.parse(DummyAnalyzer(p), t, ignore_errors=True)
        self.assertIsNone(res, "activo + 1 no debe ser aceptado como condición")

        # 6. Negación lógica: !activo
        toks = Lexer("!activo").process()
        p = Parser(toks)
        t = p.consume()
        res = cond_comb.parse(DummyAnalyzer(p), t, ignore_errors=True)
        self.assertIsNotNone(res)
        self.assertEqual([x.value for x in res], ["!", "activo"])

        # 7. Negación con agrupación: !(10 + 20 > 5)
        toks = Lexer("!(10 + 20 > 5)").process()
        p = Parser(toks)
        t = p.consume()
        res = cond_comb.parse(DummyAnalyzer(p), t, ignore_errors=True)
        self.assertIsNotNone(res)
        self.assertEqual([x.value for x in res], ["!", "(", 10, "+", 20, ">", 5, ")"])

        # 8. Negación con aritmética inválida: !(10 + 20) (debe ser RECHAZADA)
        toks = Lexer("!(10 + 20)").process()
        p = Parser(toks)
        t = p.consume()
        res = cond_comb.parse(DummyAnalyzer(p), t, ignore_errors=True)
        self.assertIsNone(res)

        # 9. Conectores lógicos: 10 + 20 > 5 && activo == 1
        toks = Lexer("10 + 20 > 5 && activo == 1").process()
        p = Parser(toks)
        t = p.consume()
        res = cond_comb.parse(DummyAnalyzer(p), t, ignore_errors=True)
        self.assertIsNotNone(res)
        self.assertEqual([x.value for x in res], [10, "+", 20, ">", 5, "&&", "activo", "==", 1])

        # 10. Conector con condición inválida a la derecha: 10 + 20 > 5 && 42 (debe ser RECHAZADA)
        toks = Lexer("10 + 20 > 5 && 42").process()
        p = Parser(toks)
        t = p.consume()
        res = cond_comb.parse(DummyAnalyzer(p), t, ignore_errors=True)
        self.assertIsNone(res)

        # 11. Literales booleanos: true && false
        toks = Lexer("true && false").process()
        p = Parser(toks)
        t = p.consume()
        res = cond_comb.parse(DummyAnalyzer(p), t, ignore_errors=True)
        self.assertIsNotNone(res)
        self.assertEqual(len(res), 3)

    def test_evaluator_conditionals_and_logic(self):
        # Comparaciones simples
        self.assertEqual(expressions.evaluate("10 + 20 > 5"), 1)
        self.assertEqual(expressions.evaluate("10 + 20 < 5"), 0)
        self.assertEqual(expressions.evaluate("10 == 10"), 1)
        self.assertEqual(expressions.evaluate("10 != 10"), 0)

        # Conectores lógicos && y ||
        self.assertEqual(expressions.evaluate("10 > 5 && 2 < 4"), 1)
        self.assertEqual(expressions.evaluate("10 > 5 && 2 > 4"), 0)
        self.assertEqual(expressions.evaluate("10 < 5 || 2 < 4"), 1)
        self.assertEqual(expressions.evaluate("10 < 5 || 2 > 4"), 0)

        # Negación lógica !
        self.assertEqual(expressions.evaluate("!0"), 1)
        self.assertEqual(expressions.evaluate("!1"), 0)
        self.assertEqual(expressions.evaluate("!(10 > 20)"), 1)

        # Booleanos y variables de entorno
        env = {"x": 8, "y": 10, "activo": 1}
        self.assertEqual(expressions.evaluate("x > 5 && y == 10", env=env), 1)
        self.assertEqual(expressions.evaluate("x < 5 && y == 10", env=env), 0)
        self.assertEqual(expressions.evaluate("activo && x == 8", env=env), 1)

    def test_evaluator_basic_arithmetic(self):
        self.assertEqual(expressions.evaluate("2 + 3 * 4"), 14)
        self.assertEqual(expressions.evaluate("(2 + 3) * 4"), 20)
        self.assertEqual(expressions.evaluate("10 / 2 + 5"), 10.0)
        self.assertEqual(expressions.evaluate("15 // 4"), 3)
        self.assertEqual(expressions.evaluate("17 % 5"), 2)
        self.assertEqual(expressions.evaluate("2 ** 3"), 8)

    def test_evaluator_unary_and_nesting(self):
        self.assertEqual(expressions.evaluate("-5 + 10"), 5)
        self.assertEqual(expressions.evaluate("+(-3)"), -3)
        self.assertEqual(expressions.evaluate("-(2 + 3)"), -5)

    def test_evaluator_with_variables(self):
        env = {"x": 10, "y": 20}
        self.assertEqual(expressions.evaluate("x + y * 2", env=env), 50)
        self.assertEqual(expressions.evaluate("(x + y) / 2", env=env), 15.0)

    def test_evaluator_math_functions(self):
        self.assertEqual(expressions.evaluate("sqrt(16)"), 4.0)
        self.assertEqual(expressions.evaluate("abs(-42)"), 42)
        self.assertEqual(expressions.evaluate("min(5, 10)"), 5)
        self.assertEqual(expressions.evaluate("max(5, 10)"), 10)

    def test_plugin_process(self):
        p = expressions.ExpressionsPlugin()
        self.assertEqual(p.process("3 * 3 + 1"), 10)
        self.assertTrue(p.process())


class TestGramEssentialPackPlugin(unittest.TestCase):
    """Pruebas de GRAM_ESSENCIAL_PACK."""

    def test_manifest_validation(self):
        plugin_dir = Path(gep.__file__).parent
        report = validate_plugin(plugin_dir)
        self.assertTrue(report.is_valid, f"Errores en GEP manifest/auditoría: {report.errors}")
        self.assertEqual(report.plugin_name, "GRAM_ESSENCIAL_PACK")

    def test_plugin_class_and_exports(self):
        p = gep.GramEssentialPackPlugin()
        self.assertTrue(p.on_load())
        combs = [c.__name__ for c in p.get_combinators()]
        self.assertIn("SimpleCombinator", combs)
        self.assertIn("If", combs)
        self.assertIn("ErrorCombinator", combs)
        self.assertIn("Req", combs)
        self.assertIn("Skip", combs)
        self.assertIn("Peek", combs)
        self.assertIn("Not", combs)
        self.assertIn("Until", combs)

    def test_simple_combinator(self):
        class EvenNumberCombinator(gep.SimpleCombinator):
            def evaluate(self, current: TokenType) -> bool:
                if current.token != Token.NUMBER:
                    return False
                try:
                    return int(current.value) % 2 == 0
                except (ValueError, TypeError):
                    return False

        even_comb = EvenNumberCombinator()
        tokens = Lexer("4 5").process()
        parser = Parser(tokens)
        tok1 = parser.consume()
        res1 = even_comb.parse(parser, tok1)
        self.assertEqual(res1, tok1)

        tok2 = parser.consume()
        res2 = even_comb.parse(parser, tok2, ignore_errors=True)
        self.assertIsNone(res2)

    def test_req_combinator(self):
        req = gep.Req("IDENT").is_lower().length(5)
        tokens = Lexer("hello WORLD").process()
        parser = Parser(tokens)
        tok1 = parser.consume()
        res1 = req.parse(parser, tok1)
        self.assertIsNotNone(res1)
        self.assertEqual(res1.value, "hello")

        # Fails on uppercase
        tok2 = parser.consume()
        res2 = req.parse(parser, tok2, ignore_errors=True)
        self.assertIsNone(res2)

    def test_if_combinator(self):
        if_comb = gep.If(
            conditions=[gep.MatchToken(Token.NUMBER)],
            ok=gep.MatchToken(Token.PLUS),
        )
        tokens = Lexer("123 +").process()
        parser = Parser(tokens)
        tok1 = parser.consume()
        res = if_comb.parse(parser, tok1)
        self.assertIsNotNone(res)

    def test_peek_and_not_combinators(self):
        tokens = Lexer("42 abc").process()
        parser = Parser(tokens)
        tok = parser.consume()

        # Peek positive
        peek_comb = gep.Peek(gep.MatchToken(Token.NUMBER))
        self.assertEqual(peek_comb.parse(parser, tok), [])

        # Peek negative (should fail on NUMBER)
        not_comb = gep.Not(gep.MatchToken(Token.NUMBER))
        self.assertIsNone(not_comb.parse(parser, tok, ignore_errors=True))

    def test_helper_api(self):
        # register_error
        err = gep.register_error((2, 1, 1, 0, 1), "TestError")
        self.assertEqual(err.name, "TestError")

        # register_keyword
        kw = gep.register_keyword("my_custom_kw", color="#123456", allow_override=True)
        self.assertEqual(kw.name, "my_custom_kw")


if __name__ == "__main__":
    unittest.main()
