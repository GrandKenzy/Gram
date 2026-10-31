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
from gram.core.lexer import TokenType
from gram.core.parser import Parser
from gram.sessions import Session
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

    def test_nested_combinator_mutation_rebuilds_the_plan(self) -> None:
        branch = Seq(MatchKeyword("short"))
        alternative = Alt(branch, audit=True)

        first = alternative.get_predictive_plan()
        branch.combinators = (MatchKeyword("short"), MatchToken(Token.IDENT))
        second = alternative.get_predictive_plan()

        self.assertIsNot(first, second)
        self.assertEqual(second.profiles[0].min_tokens, 2)

    def test_rule_entrypoint_mutation_rebuilds_the_plan(self) -> None:
        rule = type(
            "MutablePredictiveRule",
            (RuleItem,),
            {"entrypoint": MatchKeyword("short")},
        )
        alternative = Alt(Ref(rule), audit=True)
        first = alternative.get_predictive_plan()
        rule.entrypoint = Seq(MatchKeyword("short"), MatchToken(Token.IDENT))

        second = alternative.get_predictive_plan()

        self.assertIsNot(first, second)
        self.assertEqual(second.profiles[0].min_tokens, 2)

    def test_session_mutation_rebuilds_contextual_plan(self) -> None:
        session = Session("predictive-cache", "Many")
        parser = Parser(self.tokenize("short"), session=session)
        alternative = Alt(MatchKeyword("short"), audit=True)

        first = alternative.get_predictive_plan(parser)
        session.add_group("cache_group")
        session.add_keyword("cache_revision", group="cache_group")
        second = alternative.get_predictive_plan(parser)

        self.assertIsNot(first, second)

    def test_conversion_changes_are_read_without_stale_dispatch(self) -> None:
        alternative = Alt(
            MatchToken(Token.NUMBER),
            MatchToken(Token.STRING),
            audit=True,
        )

        number_parser = Parser(
            [TokenType(Token.IDENT, "value")],
            conversions={"value": Token.NUMBER},
        )
        number_analyzer = ASTAnalyzer(
            number_parser,
            type("Entry", (RuleItem,), {"entrypoint": alternative}),
            trace="detailed",
        )
        self.assertIsNotNone(number_analyzer.visitor(alternative))
        self.assertEqual(
            [record.branch_index for record in number_analyzer.raytracing.alternative_records],
            [0],
        )

        string_parser = Parser(
            [TokenType(Token.IDENT, "value")],
            conversions={"value": Token.STRING},
        )
        string_analyzer = ASTAnalyzer(
            string_parser,
            type("Entry", (RuleItem,), {"entrypoint": alternative}),
            trace="detailed",
        )
        self.assertIsNotNone(string_analyzer.visitor(alternative))
        self.assertEqual(
            [record.branch_index for record in string_analyzer.raytracing.alternative_records],
            [1],
        )

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

    def test_first_set_dispatch_skips_impossible_exact_branches(self) -> None:
        alternative = Alt(
            MatchKeyword("short"),
            MatchKeyword("long"),
            audit=True,
        )
        parser = Parser(self.tokenize("long"))
        analyzer = ASTAnalyzer(
            parser,
            type("Entry", (RuleItem,), {"entrypoint": alternative}),
            trace="detailed",
        )

        self.assertIsNotNone(analyzer.visitor(alternative))

        records = analyzer.raytracing.alternative_records
        self.assertEqual([record.branch_index for record in records], [1])

    def test_first_set_dispatch_preserves_opaque_barriers(self) -> None:
        alternative = Alt(
            MatchKeyword("short"),
            OpaquePredictiveBranch(),
            MatchKeyword("long"),
            audit=True,
        )
        parser = Parser(self.tokenize("long"))
        analyzer = ASTAnalyzer(
            parser,
            type("Entry", (RuleItem,), {"entrypoint": alternative}),
            trace="detailed",
        )

        self.assertIsNotNone(analyzer.visitor(alternative))
        records = analyzer.raytracing.alternative_records
        self.assertEqual([record.branch_index for record in records], [1, 2])

    def test_first_set_dispatch_falls_back_when_no_branch_predicts(self) -> None:
        alternative = self.alternatives(audit=True)
        parser = Parser(self.tokenize("unknown"))
        analyzer = ASTAnalyzer(
            parser,
            type("Entry", (RuleItem,), {"entrypoint": alternative}),
            trace="detailed",
        )

        self.assertIsNone(analyzer.visitor(alternative))
        records = analyzer.raytracing.alternative_records
        self.assertEqual([record.branch_index for record in records], [1, 0])

    def test_audit_false_and_true_preserve_parse_observables(self) -> None:
        def run(audit: bool, source: str) -> tuple[object, int, bool, list[tuple[str, str]]]:
            analyzer = self.create_analyzer(source)
            result = analyzer.visitor(self.alternatives(audit=audit))
            errors = [(item.name, str(item.code)) for item in analyzer._errors]
            return repr(result), analyzer.parser.pos, analyzer.parser.is_eof(), errors

        for source in ("long value = 1;", "long value ="):
            with self.subTest(source=source):
                self.assertEqual(run(False, source), run(True, source))

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
