"""Diagnostics from conditional, scanning and expression probes stay local."""
from gram import errors
from gram.core.combinators import (
    ArithmeticExpr, If, MatchKeyword, MatchToken, Not, Ref, RuleItem, Seq, Until,
)
from gram.core.lexer import Token
from tests.combinators.base import CombinatorTestCase


class LongOperand(RuleItem):
    name = 'LongOperand'
    nodeable = True
    entrypoint = Seq(
        MatchToken(Token.NUMBER), MatchToken(Token.IDENT), MatchToken(Token.STRING),
    )


class TestProbeDiagnostics(CombinatorTestCase):
    def prior_failure(self, analyzer, weight=0):
        prior = errors.ParserError('PriorFailure', errors.PARSER_UNEXPECTED_TOKEN)
        analyzer.stage_failure(prior, weight=weight)
        return prior

    def test_if_fallback_discards_failed_condition_only(self):
        analyzer = self.create_analyzer('int name')
        prior = self.prior_failure(analyzer)
        condition = Seq(
            MatchKeyword('int'), MatchToken(Token.IDENT), MatchKeyword('return'),
        )
        result = analyzer.visitor(If(condition, fail=Not(MatchToken(Token.NUMBER))))
        self.assertEqual(result, [])
        self.assertIs(analyzer.staged_failure, prior)
        self.assertEqual(analyzer.staged_weight, 0)
        self.assertEqual(analyzer._errors, [])

    def test_if_without_fallback_reports_its_own_deep_failure(self):
        analyzer = self.create_analyzer('int name')
        prior = self.prior_failure(analyzer, weight=99)
        condition = Seq(
            MatchKeyword('int'), MatchToken(Token.IDENT), MatchKeyword('return'),
        )
        self.assertIsNone(analyzer.visitor(If(condition)))
        self.assertEqual(len(analyzer._errors), 1)
        self.assertIsNot(analyzer._errors[0], prior)
        self.assertEqual(analyzer._errors[0].name, 'KeywordTypeMismatch')
        self.assertIn("'return'", analyzer._errors[0].caution[0])

    def test_if_restored_condition_preserves_incoming_candidate(self):
        analyzer = self.create_analyzer('int')
        prior = self.prior_failure(analyzer)
        self.assertIsNotNone(analyzer.visitor(If(MatchKeyword('int'), restore=True)))
        self.assertEqual(analyzer.parser.pos, 0)
        self.assertIs(analyzer.staged_failure, prior)

    def test_until_missing_target_discards_intermediate_probe_errors(self):
        analyzer = self.create_analyzer('int name')
        self.prior_failure(analyzer)
        target = Seq(
            MatchKeyword('int'), MatchToken(Token.IDENT), MatchKeyword('return'),
        )
        with analyzer.safe_mode():
            self.assertIsNone(analyzer.visitor(Until(target)))
        self.assertEqual(analyzer.staged_failure.name, 'UntilTargetNotFound')
        self.assertEqual(analyzer.staged_weight, 2)
        self.assertEqual(analyzer._errors, [])

    def test_expression_native_atom_discards_rejected_reference_error(self):
        analyzer = self.create_analyzer('1 name')
        expression = ArithmeticExpr(Ref(LongOperand), Token.NUMBER)
        result = analyzer.visitor(expression)
        self.assertIsNotNone(result)
        self.assertEqual(result.token.value, 1)
        self.assertEqual(analyzer.parser.pos, 1)
        self.assertIsNone(analyzer.staged_failure)
        self.assertEqual(analyzer._errors, [])

    def test_expression_keeps_deep_reference_failure_when_no_atom_matches(self):
        analyzer = self.create_analyzer('1 name')
        with analyzer.safe_mode():
            self.assertIsNone(analyzer.visitor(ArithmeticExpr(Ref(LongOperand))))
        self.assertEqual(analyzer.staged_failure.name, 'EOFReached')
        self.assertEqual(analyzer.staged_weight, 2)
        self.assertEqual(analyzer.parser.pos, 0)
