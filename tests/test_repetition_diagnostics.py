"""Regression coverage for failure ownership in repetition and separated lists."""
from __future__ import annotations

import unittest

from gram import errors
from gram.core.combinators.alternative import Alt
from gram.core.combinators.base import Combinator
from gram.core.combinators.many import Many
from gram.core.combinators.match import MatchKeyword, MatchToken
from gram.core.combinators.optional import Opt
from gram.core.combinators.separator import Separator
from gram.core.combinators.sequence import Seq
from gram.core.combinators.signals import AbortFlowSignal, BreakFlowSignal, SkipFlowSignal
from gram.core.combinators.some import Some
from gram.core.lexer.tokens import Token
from tests.combinators.base import CombinatorTestCase


class StageThenRaise(Combinator):
    def __init__(self, failure, exception):
        super().__init__()
        self.failure = failure
        self.exception = exception

    def parse(self, analyzer):
        analyzer.stage_failure(self.failure, weight=analyzer.parser.pos + 5)
        raise self.exception


class TestRepetitionDiagnostics(CombinatorTestCase):
    @staticmethod
    def prior_error():
        return errors.ParserError(
            'UnrelatedPriorFailure', errors.PARSER_UNEXPECTED_TOKEN, 'An earlier branch failed.'
        )

    @staticmethod
    def declaration():
        return Seq(MatchKeyword('int'), MatchToken(Token.IDENT))

    def test_clean_repetitions_preserve_incoming_candidate_without_publishing(self):
        cases = (
            (Many(MatchKeyword('int')), 'str', 0),
            (Many(MatchToken(Token.NUMBER)), '1 str', 1),
            (Some(MatchToken(Token.NUMBER)), '1 str', 1),
            (Separator(Token.NUMBER), 'str', 0),
            (Separator(Token.NUMBER), '1 str', 1),
        )
        for combinator, source, end_pos in cases:
            for prior_weight in (0, 20):
                with self.subTest(combinator=combinator, prior_weight=prior_weight):
                    analyzer = self.create_analyzer(source)
                    previous = self.prior_error()
                    analyzer.stage_failure(previous, weight=prior_weight)
                    incoming = analyzer._staged_failure

                    self.assertIsNotNone(analyzer.visitor(combinator))

                    self.assertEqual(analyzer.parser.pos, end_pos)
                    self.assertIs(analyzer._staged_failure, incoming)
                    self.assertEqual(analyzer._errors, [])

    def test_partial_repetition_publishes_own_error_instead_of_deeper_incoming_error(self):
        for repetition in (Many, Some):
            with self.subTest(repetition=repetition.__name__):
                analyzer = self.create_analyzer('int a int')
                previous = self.prior_error()
                analyzer.stage_failure(previous, weight=20)
                incoming = analyzer._staged_failure

                result = analyzer.visitor(repetition(self.declaration()))

                self.assertEqual(len(result), 1)
                self.assertEqual(analyzer.parser.pos, 2)
                self.assertIs(analyzer._staged_failure, incoming)
                self.assertEqual(len(analyzer._errors), 1)
                self.assertIsNot(analyzer._errors[0], previous)
                self.assertIn('IDENT', ' '.join(analyzer._errors[0].caution))

    def test_partial_repetition_remains_deep_through_successful_wrappers(self):
        wrappers = (
            lambda child: child,
            lambda child: Alt(child, MatchToken(Token.NUMBER)),
            Opt,
        )
        for repetition in (Many, Some):
            for wrapper in wrappers:
                with self.subTest(repetition=repetition.__name__, wrapper=wrapper):
                    analyzer = self.create_analyzer('int a int')
                    with analyzer.safe_mode():
                        result = analyzer.visitor(wrapper(repetition(self.declaration())))

                    self.assertEqual(len(result), 1)
                    self.assertEqual(analyzer.parser.pos, 2)
                    self.assertEqual(analyzer.staged_weight, 3)
                    self.assertIn('IDENT', ' '.join(analyzer.staged_failure.caution))
                    self.assertEqual(analyzer._errors, [])

    def test_nested_repetition_publishes_deep_failure_after_clean_final_attempt(self):
        for repetition in (Many, Some):
            with self.subTest(repetition=repetition.__name__):
                combinator = repetition(
                    Seq(
                        MatchToken(Token.NUMBER),
                        Many(Seq(MatchToken(Token.COMMA), MatchToken(Token.NUMBER))),
                    )
                )
                result, analyzer = self.parse_with_analyzer(combinator, '1, x')

                self.assertEqual(len(result), 1)
                self.assertEqual(analyzer.parser.pos, 1)
                self.assertEqual([err.name for err in analyzer._errors], ['TokenMismatch'])
                self.assertIsNone(analyzer.staged_failure)

    def test_required_first_item_reports_local_error_with_deeper_incoming_candidate(self):
        for combinator in (Some(MatchToken(Token.NUMBER)), Separator(Token.NUMBER, min=1)):
            with self.subTest(combinator=combinator):
                analyzer = self.create_analyzer('str')
                previous = self.prior_error()
                analyzer.stage_failure(previous, weight=20)
                incoming = analyzer._staged_failure

                self.assertIsNone(analyzer.visitor(combinator))

                self.assertIs(analyzer._staged_failure, incoming)
                self.assertEqual(len(analyzer._errors), 1)
                self.assertIsNot(analyzer._errors[0], previous)
                self.assertIn('NUMBER', ' '.join(analyzer._errors[0].caution))

    def test_separator_keeps_deep_failure_owned_by_successful_value(self):
        analyzer = self.create_analyzer('int a int')
        with analyzer.safe_mode():
            result = analyzer.visitor(Separator(Some(self.declaration()), max=1))

        self.assertEqual(len(result), 1)
        self.assertEqual(analyzer.parser.pos, 2)
        self.assertEqual(analyzer.staged_weight, 3)
        self.assertIn('IDENT', ' '.join(analyzer.staged_failure.caution))
        self.assertEqual(analyzer._errors, [])

    def test_separator_discards_rejected_long_value_when_short_value_matches(self):
        combinator = Separator(
            [
                Seq(MatchKeyword('int'), MatchToken(Token.IDENT), MatchKeyword('return')),
                MatchKeyword('int'),
            ],
            max=1,
        )
        result, analyzer = self.parse_with_analyzer(combinator, 'int value')

        self.assertEqual(len(result), 1)
        self.assertEqual(analyzer.parser.pos, 1)
        self.assertIsNone(analyzer.staged_failure)
        self.assertEqual(analyzer._errors, [])

    def test_clean_separator_ending_does_not_override_following_expected_keyword(self):
        analyzer = self.create_analyzer('1 name')
        with analyzer.safe_mode():
            result = analyzer.visitor(
                Seq(Separator(Token.NUMBER), MatchKeyword('int'))
            )

        self.assertIsNone(result)
        self.assertEqual(analyzer.staged_weight, 1)
        self.assertEqual(analyzer.staged_failure.name, 'KeywordTypeMismatch')
        self.assertIn('int', ' '.join(analyzer.staged_failure.caution))

    def test_separator_minimum_failure_does_not_promote_incoming_candidate(self):
        analyzer = self.create_analyzer('int value')
        previous = self.prior_error()
        analyzer.stage_failure(previous, weight=20)
        incoming = analyzer._staged_failure
        combinator = Separator(
            [
                Seq(MatchKeyword('int'), MatchToken(Token.IDENT), MatchKeyword('return')),
                Seq(MatchKeyword('int'), MatchToken(Token.NUMBER)),
            ],
            min=1,
        )

        self.assertIsNone(analyzer.visitor(combinator))

        self.assertEqual(analyzer.parser.pos, 0)
        self.assertIs(analyzer._staged_failure, incoming)
        self.assertEqual(len(analyzer._errors), 1)
        self.assertIsNot(analyzer._errors[0], previous)
        self.assertIn('return', ' '.join(analyzer._errors[0].caution))

    def test_separator_partial_next_value_keeps_deep_error_and_trailing_policy(self):
        for trailing, end_pos in ((True, 3), (False, 2)):
            with self.subTest(trailing=trailing):
                analyzer = self.create_analyzer('int a, int')
                with analyzer.safe_mode():
                    result = analyzer.visitor(
                        Separator(self.declaration(), allow_trailing=trailing)
                    )

                self.assertEqual(len(result), 1)
                self.assertEqual(result.trailing, trailing)
                self.assertEqual(analyzer.parser.pos, end_pos)
                self.assertEqual(analyzer.staged_weight, 4)
                self.assertIn('IDENT', ' '.join(analyzer.staged_failure.caution))
                self.assertEqual(analyzer._errors, [])

    def test_handled_loop_signals_discard_their_local_failures(self):
        for repetition in (Many, Some):
            for signal in (SkipFlowSignal, BreakFlowSignal):
                with self.subTest(repetition=repetition.__name__, signal=signal.__name__):
                    analyzer = self.create_analyzer('1')
                    previous = self.prior_error()
                    analyzer.stage_failure(previous, weight=1)
                    incoming = analyzer._staged_failure
                    discarded = self.prior_error()

                    analyzer.visitor(repetition(StageThenRaise(discarded, signal())))

                    self.assertIs(analyzer._staged_failure, incoming)
                    self.assertNotIn(discarded, analyzer._errors)
                    self.assertEqual(analyzer.parser.pos, 0)

    def test_exception_and_abort_restore_parent_candidate_and_scope_depth(self):
        for owner in (Many, Some, Separator):
            for exception in (RuntimeError('stop'), AbortFlowSignal()):
                with self.subTest(owner=owner.__name__, exception=type(exception).__name__):
                    analyzer = self.create_analyzer('1')
                    previous = self.prior_error()
                    analyzer.stage_failure(previous, weight=1)
                    incoming = analyzer._staged_failure

                    with self.assertRaises(type(exception)):
                        analyzer.visitor(owner(StageThenRaise(self.prior_error(), exception)))

                    self.assertIs(analyzer._staged_failure, incoming)
                    self.assertFalse(analyzer.safe_flag)
                    self.assertEqual(analyzer._errors, [])

    def test_separator_delimiter_break_discards_local_failure(self):
        analyzer = self.create_analyzer('1,')
        previous = self.prior_error()
        analyzer.stage_failure(previous, weight=1)
        incoming = analyzer._staged_failure
        discarded = self.prior_error()

        result = analyzer.visitor(
            Separator(Token.NUMBER, sep=StageThenRaise(discarded, BreakFlowSignal()))
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(analyzer.parser.pos, 1)
        self.assertIs(analyzer._staged_failure, incoming)
        self.assertNotIn(discarded, analyzer._errors)


if __name__ == '__main__':
    unittest.main()
