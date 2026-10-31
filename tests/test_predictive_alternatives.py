"""Regression tests for audited alternatives and predictive planning."""
from __future__ import annotations

import unittest

from gram.core.ast.analyzer import ASTAnalyzer
from gram.core.combinators import (
    Alt,
    Combinator,
    MatchKeyword,
    MatchToken,
    Ref,
    RuleItem,
    Seq,
    audit_alternatives,
)
from gram.core.lexer import Token
from gram.core.parser import Parser
from tests.combinators.base import CombinatorTestCase


class ShortPredictiveRule(RuleItem):
    entrypoint = Seq(MatchKeyword("short"), MatchToken(Token.IDENT))


class LongPredictiveRule(RuleItem):
    entrypoint = Seq(
        MatchKeyword("long"),
        MatchToken(Token.IDENT),
        MatchToken(Token.ASSIGN),
        MatchToken(Token.NUMBER),
        MatchToken(Token.SEMICOLON),
    )


class OpaquePredictiveBranch(Combinator):
    """Unknown branch used to verify that audit plans preserve barriers."""

    def parse(self, analyzer):
        return None


class TestPredictiveAlternatives(CombinatorTestCase):
    def setUp(self) -> None:
        super().setUp()
        from gram import lexer

        lexer.add_keyword("short")
        lexer.add_keyword("long")

    def alternatives(self, *, audit: bool) -> Alt:
        return Alt(
            Ref(ShortPredictiveRule),
            Ref(LongPredictiveRule),
            audit=audit,
        )

    def test_audit_orders_exact_fixed_branches_and_caches_plan(self) -> None:
        alternative = self.alternatives(audit=True)

        plan = alternative.get_predictive_plan()

        self.assertEqual(plan.order, (1, 0))
        self.assertIs(alternative.get_predictive_plan(), plan)
        self.assertEqual(
            alternative.combinators,
            (alternative.combinators[0], alternative.combinators[1]),
        )
        self.assertTrue(plan.profiles[0].reorderable)
        self.assertTrue(plan.profiles[1].reorderable)

    def test_audit_keeps_declared_order_public_but_uses_planned_order(self) -> None:
        alternative = self.alternatives(audit=True)
        parser = Parser(self.tokenize("long value = 1;"))
        analyzer = ASTAnalyzer(parser, type("Entry", (RuleItem,), {"entrypoint": alternative}), trace="detailed")

        result = analyzer.visitor(alternative)

        self.assertIsNotNone(result)
        self.assertEqual(parser.pos, 5)
        self.assertEqual(analyzer.raytracing.alternative_records[0].branch_index, 1)
        self.assertEqual(analyzer.raytracing.alternative_records[0].outcome, "SUCCESS")
        self.assertEqual(analyzer.raytracing.alternative_records[0].consumed, 5)
        self.assertEqual(alternative.items()[0].rule_name, "ShortPredictiveRule")

    def test_audit_false_preserves_declared_attempt_order(self) -> None:
        alternative = self.alternatives(audit=False)
        parser = Parser(self.tokenize("long value = 1;"))
        analyzer = ASTAnalyzer(parser, type("Entry", (RuleItem,), {"entrypoint": alternative}), trace="detailed")

        analyzer.visitor(alternative)

        records = analyzer.raytracing.alternative_records
        self.assertGreaterEqual(len(records), 2)
        self.assertEqual(records[0].branch_index, 0)
        self.assertEqual(records[1].branch_index, 1)

    def test_opaque_branch_is_a_reordering_barrier(self) -> None:
        alternative = Alt(
            Ref(ShortPredictiveRule),
            OpaquePredictiveBranch(),
            Ref(LongPredictiveRule),
            audit=True,
        )

        plan = audit_alternatives(alternative)

        self.assertEqual(plan.order, (0, 1, 2))
        self.assertTrue(any("kept in declaration order" in warning for warning in plan.warnings))

    def test_recursive_reference_is_reported_as_unknown_without_recursing(self) -> None:
        recursive_rule = type("RecursivePredictiveRule", (RuleItem,), {})
        recursive_ref = Ref(recursive_rule)
        recursive_rule.entrypoint = recursive_ref

        plan = audit_alternatives(Alt(recursive_ref, audit=True))

        self.assertEqual(plan.profiles[0].certainty, "unknown")
        self.assertIn("recursive", plan.profiles[0].reasons[0])
        self.assertEqual(plan.order, (0,))

    def test_operator_composition_preserves_audit_opt_in(self) -> None:
        alternative = self.alternatives(audit=True)

        combined = alternative | MatchKeyword("short")

        self.assertTrue(combined.audit)
        self.assertEqual(len(combined), 3)


if __name__ == "__main__":
    unittest.main()
