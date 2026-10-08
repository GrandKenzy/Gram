"""
Pruebas Unitarias para AutoCode y SetCode (`gram.tests.test_codes`).
====================================================================
EN:
    Unit tests validating automatic code generation, manual base setting (SetCode),
    collision avoidance, step increments, and declarative RuleItem integration.
ES:
    Pruebas unitarias que validan la generación automática de códigos, configuración
    manual de base (SetCode), evasión de colisiones, incrementos de paso e integración
    declarativa con RuleItem.
"""
from __future__ import annotations

import unittest
import warnings

import gram
from gram.core.rules.codes import AutoCode, CodeManager, SetCode, code_manager


class TestAutoCodeAndSetCode(unittest.TestCase):
    """Suite de pruebas para AutoCode y SetCode."""

    def setUp(self) -> None:
        # Reiniciar el gestor de códigos con base limpia para pruebas aisladas
        code_manager.reset(code=50000, clear_used=True)

    def test_set_code_and_autocode_sequential(self) -> None:
        """Verifica que SetCode establece la base y AutoCode incrementa secuencialmente."""
        gram.SetCode(20000)
        c1 = gram.AutoCode()
        c2 = gram.AutoCode()
        c3 = gram.AutoCode()

        self.assertEqual(c1, 20000)
        self.assertEqual(c2, 20001)
        self.assertEqual(c3, 20002)
        self.assertIsInstance(c1, int)
        self.assertIsInstance(c1, AutoCode)

    def test_collision_avoidance_with_manual_codes(self) -> None:
        """Verifica que AutoCode detecta códigos manuales y los omite sin colisionar."""
        gram.SetCode(30000)
        c1 = gram.AutoCode()  # 30000

        # Simular una regla manual o código registrado intermedio (30001)
        AutoCode.register(30001)

        c2 = gram.AutoCode()  # Debe omitir 30001 y entregar 30002
        self.assertEqual(c1, 30000)
        self.assertEqual(c2, 30002)

    def test_autocode_peek_does_not_consume(self) -> None:
        """Verifica que peek previsualiza el siguiente código sin reservarlo."""
        gram.SetCode(40000)
        next_code = AutoCode.peek()
        self.assertEqual(next_code, 40000)

        # La primera llamada real debe obtener el mismo código
        actual = gram.AutoCode()
        self.assertEqual(actual, 40000)

        # Ahora el peek debe avanzar a 40001
        self.assertEqual(AutoCode.peek(), 40001)

    def test_autocode_with_custom_step(self) -> None:
        """Verifica incremento personalizado de paso en AutoCode y SetCode."""
        gram.SetCode(50000, step=10)
        c1 = gram.AutoCode()
        c2 = gram.AutoCode()
        c3 = gram.AutoCode()

        self.assertEqual(c1, 50000)
        self.assertEqual(c2, 50010)
        self.assertEqual(c3, 50020)

    def test_autocode_is_used_and_used_codes(self) -> None:
        """Verifica comprobación de códigos registrados y consulta del conjunto."""
        gram.SetCode(60000)
        c = gram.AutoCode()
        self.assertTrue(AutoCode.is_used(60000))
        self.assertFalse(AutoCode.is_used(60001))
        self.assertIn(60000, AutoCode.used_codes())

    def test_rule_item_integration_with_autocode_call(self) -> None:
        """Verifica uso explícito de gram.AutoCode() dentro de un RuleItem."""
        gram.SetCode(70000)

        class RuleA(gram.RuleItem):
            name = "rule_a"
            code = gram.AutoCode()

        class RuleB(gram.RuleItem):
            name = "rule_b"
            code = gram.AutoCode()

        self.assertEqual(RuleA.code, 70000)
        self.assertEqual(RuleB.code, 70001)

    def test_rule_item_integration_with_autocode_class_reference(self) -> None:
        """Verifica uso de gram.AutoCode sin paréntesis dentro de RuleItem."""
        gram.SetCode(75000)

        class RuleNoParens(gram.RuleItem):
            name = "rule_no_parens"
            code = gram.AutoCode

        self.assertEqual(RuleNoParens.code, 75000)
        self.assertIsInstance(RuleNoParens.code, int)

    def test_rule_item_auto_assignment_when_code_omitted(self) -> None:
        """Verifica asignación automática de código cuando una subclase de RuleItem omite code."""
        gram.SetCode(80000)

        class RuleOmitted(gram.RuleItem):
            name = "rule_omitted"

        self.assertEqual(RuleOmitted.code, 80000)
        self.assertIsInstance(RuleOmitted.code, int)

    def test_rule_item_manual_code_registered_and_skipped(self) -> None:
        """Verifica que un RuleItem con código manual se registra y es omitido por AutoCode."""
        gram.SetCode(85000)

        class RuleAuto1(gram.RuleItem):
            name = "rule_auto_1"
            code = gram.AutoCode()  # 85000

        class RuleManual(gram.RuleItem):
            name = "rule_manual"
            code = 85001  # Código manual

        class RuleAuto2(gram.RuleItem):
            name = "rule_auto_2"
            code = gram.AutoCode()  # Debe saltar 85001 y dar 85002

        self.assertEqual(RuleAuto1.code, 85000)
        self.assertEqual(RuleManual.code, 85001)
        self.assertEqual(RuleAuto2.code, 85002)

    def test_rule_item_explicit_zero_code_preserved(self) -> None:
        """Verifica que una regla que explícitamente declare code = 0 no sea sobrescrita."""
        class RuleZero(gram.RuleItem):
            name = "rule_zero"
            code = 0

        self.assertEqual(RuleZero.code, 0)

    def test_set_code_validation_and_warnings(self) -> None:
        """Verifica validación de tipos y advertencias en SetCode."""
        with self.assertRaises(TypeError):
            gram.SetCode("invalido")  # type: ignore

        with self.assertRaises(ValueError):
            gram.SetCode(-1)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            gram.SetCode(15)  # Rango protegido (0-20)
            self.assertTrue(any(issubclass(item.category, UserWarning) for item in w))


if __name__ == "__main__":
    unittest.main()
