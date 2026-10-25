"""Regression tests for diagnostic isolation during speculative parsing."""
from __future__ import annotations

from gram import errors
from gram.core.combinators.alternative import Alt
from gram.core.combinators.base import Combinator
from gram.core.combinators.match import MatchKeyword, MatchToken
from gram.core.combinators.negation import Not
from gram.core.combinators.optional import Opt
from gram.core.combinators.peek import Peek
from gram.core.combinators.sequence import Seq
from gram.core.combinators.signals import (
    AbortFlowSignal,
    BacktrackSignal,
    CutFlowSignal,
)
from gram.core.combinators.some import Some
from gram.core.lexer.tokens import Token
from gram.utilities import Diagnostics
from tests.combinators.base import CombinatorTestCase


class CandidateProbe(Combinator):
    def __init__(
        self, *, result=None, candidate=None, weight=0, steps=0, exception=None
    ) -> None:
        super().__init__()
        self.result = result
        self.candidate = candidate
        self.weight = weight
        self.steps = steps
        self.exception = exception
        self.calls = 0

    def parse(self, analyzer):
        self.calls += 1
        for _ in range(self.steps):
            analyzer.parser.consume()
        if self.candidate is not None:
            analyzer.report_error(self.candidate, pos=self.weight)
        if self.exception is not None:
            raise self.exception
        return self.result


class TestSpeculativeDiagnostics(CombinatorTestCase):
    def make_error(self, name):
        return errors.ParserError(name, errors.PARSER_UNEXPECTED_TOKEN, name)

    def analyzer_with_prior(self, weight=0):
        analyzer = self.create_analyzer('first second third')
        analyzer.stage_failure(self.make_error('PriorFailure'), weight=weight)
        return analyzer, analyzer._staged_failure

    def test_failure_scope_isolates_nested_candidates_and_restores_on_exception(self):
        analyzer, prior = self.analyzer_with_prior()
        outer_error = self.make_error('OuterFailure')
        inner_error = self.make_error('InnerFailure')

        with analyzer.failure_scope() as outer:
            self.assertIsNone(analyzer.staged_failure)
            self.assertTrue(analyzer.in_failure_context)
            analyzer.report_error(outer_error, pos=2)
            outer_candidate = analyzer._staged_failure
            with self.assertRaisesRegex(RuntimeError, 'scope failure'):
                with analyzer.failure_scope() as inner:
                    self.assertIsNone(analyzer.staged_failure)
                    analyzer.report_error(inner_error, pos=3)
                    raise RuntimeError('scope failure')
            self.assertIs(analyzer._staged_failure, outer_candidate)

        self.assertEqual(inner.candidate, (3, inner_error))
        self.assertEqual(outer.candidate, (2, outer_error))
        self.assertIs(analyzer._staged_failure, prior)
        self.assertFalse(analyzer.in_failure_context)
        self.assertEqual(analyzer._errors, [])

    def test_alt_short_success_preserves_prior_after_deeper_rejected_branch(self):
        analyzer, prior = self.analyzer_with_prior()
        combinator = Alt(
            Seq(MatchToken(Token.IDENT), MatchToken(Token.NUMBER)),
            MatchToken(Token.IDENT),
        )

        self.assertIsNotNone(analyzer.visitor(combinator))

        self.assertEqual(analyzer.parser.pos, 1)
        self.assertIs(analyzer._staged_failure, prior)
        self.assertEqual(analyzer._errors, [])

    def test_alt_discards_shallow_diagnostics_from_successful_branch(self):
        analyzer, prior = self.analyzer_with_prior()
        combinator = Alt(
            CandidateProbe(candidate=self.make_error('RejectedFailure'), weight=2),
            CandidateProbe(
                result=[], candidate=self.make_error('AcceptedNoise'), weight=0
            ),
        )

        self.assertEqual(analyzer.visitor(combinator), [])
        self.assertIs(analyzer._staged_failure, prior)

    def test_alt_publishes_deepest_local_failure_instead_of_prior(self):
        analyzer, _ = self.analyzer_with_prior(weight=10)
        shallow = self.make_error('ShallowFailure')
        deep = self.make_error('DeepFailure')

        result = analyzer.visitor(Alt(
            CandidateProbe(candidate=shallow, weight=1),
            CandidateProbe(candidate=deep, weight=2),
        ))

        self.assertIsNone(result)
        self.assertEqual(analyzer._errors, [deep])
        self.assertIsNone(analyzer.staged_failure)

    def test_alt_cut_reports_only_committed_branch(self):
        analyzer = self.create_analyzer('first second third')
        committed = self.make_error('CommittedFailure')
        unvisited = CandidateProbe(result=[])

        result = analyzer.visitor(Alt(
            CandidateProbe(candidate=self.make_error('RejectedFailure'), weight=3),
            CandidateProbe(
                candidate=committed, weight=1, exception=CutFlowSignal()
            ),
            unvisited,
        ))

        self.assertIsNone(result)
        self.assertEqual(analyzer._errors, [committed])
        self.assertEqual(unvisited.calls, 0)

    def test_alt_keeps_cut_cause_through_optional_and_assertion_scopes(self):
        wrappers = (
            Opt,
            Peek,
            Not,
            lambda child: Peek(Not(Opt(child))),
        )
        for wrapper in wrappers:
            with self.subTest(wrapper=wrapper.__name__):
                analyzer, _ = self.analyzer_with_prior(weight=99)
                committed = self.make_error('NestedCommittedFailure')
                unvisited = CandidateProbe(result=[])
                child = CandidateProbe(
                    candidate=committed, weight=2, steps=1,
                    exception=CutFlowSignal(),
                )

                result = analyzer.visitor(Alt(wrapper(child), unvisited))

                self.assertIsNone(result)
                self.assertEqual(analyzer._errors, [committed])
                self.assertEqual(unvisited.calls, 0)
                self.assertEqual(analyzer.parser.pos, 0)
                self.assertIsNone(analyzer.staged_failure)

    def test_escaping_cut_carries_cause_without_changing_incoming_candidate(self):
        analyzer, prior = self.analyzer_with_prior(weight=99)
        committed = self.make_error('NestedCommittedFailure')
        payload = object()
        signal = CutFlowSignal('nested cut', payload)
        child = CandidateProbe(
            candidate=committed, weight=2, steps=1, exception=signal,
        )

        with self.assertRaises(CutFlowSignal) as caught:
            analyzer.visitor(Peek(Opt(child)))

        self.assertIs(caught.exception, signal)
        self.assertIs(signal.payload, payload)
        self.assertEqual(signal._failure_candidate, (2, committed))
        self.assertIs(analyzer._staged_failure, prior)
        self.assertFalse(analyzer.in_failure_context)
        self.assertEqual(analyzer.parser.pos, 0)
        self.assertEqual(analyzer._errors, [])

    def test_cut_transport_keeps_deepest_local_cause_across_scopes(self):
        analyzer, prior = self.analyzer_with_prior(weight=99)
        deep = self.make_error('OuterDeepFailure')
        shallow = self.make_error('InnerShallowFailure')
        signal = CutFlowSignal()

        with self.assertRaises(CutFlowSignal):
            with analyzer.failure_scope():
                analyzer.report_error(deep, pos=3)
                with analyzer.failure_scope():
                    analyzer.report_error(shallow, pos=2)
                    raise signal

        self.assertEqual(signal._failure_candidate, (3, deep))
        self.assertIs(analyzer._staged_failure, prior)
        self.assertEqual(analyzer._errors, [])

    def test_alt_backtrack_then_success_preserves_prior(self):
        analyzer, prior = self.analyzer_with_prior()
        result = analyzer.visitor(Alt(
            CandidateProbe(
                candidate=self.make_error('RejectedFailure'), weight=3,
                steps=1, exception=BacktrackSignal(),
            ),
            CandidateProbe(result=[]),
        ))

        self.assertEqual(result, [])
        self.assertEqual(analyzer.parser.pos, 0)
        self.assertIs(analyzer._staged_failure, prior)

    def test_opt_omission_uses_local_failure_even_with_deeper_prior(self):
        analyzer, prior = self.analyzer_with_prior(weight=10)

        self.assertEqual(analyzer.visitor(Opt(MatchToken(Token.NUMBER))), [])

        self.assertIs(analyzer._staged_failure, prior)
        self.assertEqual(analyzer.parser.pos, 0)
        self.assertEqual(analyzer._errors, [])

    def test_opt_success_preserves_prior_and_discards_shallow_local_noise(self):
        for child in (
            MatchToken(Token.IDENT),
            CandidateProbe(
                result=[], candidate=self.make_error('AcceptedNoise'), weight=0
            ),
        ):
            with self.subTest(child=type(child).__name__):
                analyzer, prior = self.analyzer_with_prior()
                self.assertIsNotNone(analyzer.visitor(Opt(child)))
                self.assertIs(analyzer._staged_failure, prior)
                self.assertEqual(analyzer._errors, [])

    def test_opt_partial_failure_publishes_local_cause(self):
        analyzer, _ = self.analyzer_with_prior(weight=10)
        local_error = self.make_error('PartialFailure')

        result = analyzer.visitor(Opt(CandidateProbe(
            candidate=local_error, weight=2, steps=1,
        )))

        self.assertIsNone(result)
        self.assertEqual(analyzer._errors, [local_error])
        self.assertEqual(analyzer.parser.pos, 0)

    def test_alt_and_opt_preserve_deep_failure_after_successful_repetition(self):
        for wrapper in (Alt, Opt):
            with self.subTest(wrapper=wrapper.__name__):
                analyzer = self.create_analyzer('int a int')
                repeated = Some(Seq(
                    MatchKeyword('int'), MatchToken(Token.IDENT)
                ))

                result = analyzer.visitor(wrapper(repeated))

                self.assertIsNotNone(result)
                self.assertEqual(analyzer.parser.pos, 2)
                self.assertEqual(analyzer.staged_weight, 3)
                self.assertEqual(analyzer.staged_failure.name, 'EOFReached')
                self.assertEqual(analyzer._errors, [])

    def test_optional_raised_error_at_start_is_omitted_without_publication(self):
        analyzer, prior = self.analyzer_with_prior()
        published = []
        child = CandidateProbe(exception=self.make_error('OptionalMismatch'))
        with Diagnostics.hook_errors(lambda sender, err: published.append(err)):
            self.assertEqual(analyzer.visitor(Opt(child)), [])

        self.assertIs(analyzer._staged_failure, prior)
        self.assertEqual(analyzer._errors, [])
        self.assertEqual(published, [])

    def test_peek_success_discards_local_noise_and_preserves_prior(self):
        analyzer, prior = self.analyzer_with_prior()
        child = CandidateProbe(
            result=[], candidate=self.make_error('LookaheadNoise'), weight=3,
            steps=1,
        )

        self.assertEqual(analyzer.visitor(Peek(child)), [])
        self.assertIs(analyzer._staged_failure, prior)
        self.assertEqual(analyzer.parser.pos, 0)

    def test_peek_failure_publishes_local_cause_instead_of_prior(self):
        analyzer, _ = self.analyzer_with_prior(weight=10)
        local_error = self.make_error('LookaheadFailure')

        result = analyzer.visitor(Peek(CandidateProbe(
            candidate=local_error, weight=2,
        )))

        self.assertIsNone(result)
        self.assertEqual(analyzer._errors, [local_error])
        self.assertEqual(analyzer.parser.pos, 0)

    def test_not_success_restores_prior_exactly_without_publication(self):
        analyzer, prior = self.analyzer_with_prior()
        child = CandidateProbe(
            candidate=self.make_error('ExpectedMismatch'), weight=3, steps=1
        )
        published = []
        with Diagnostics.hook_errors(lambda sender, err: published.append(err)):
            self.assertEqual(analyzer.visitor(Not(child)), [])

        self.assertIs(analyzer._staged_failure, prior)
        self.assertEqual(analyzer.parser.pos, 0)
        self.assertEqual(analyzer._errors, [])
        self.assertEqual(published, [])

    def test_not_failure_uses_assertion_instead_of_child_noise(self):
        analyzer = self.create_analyzer('first second third')
        child = CandidateProbe(
            result=[], candidate=self.make_error('ChildNoise'), weight=3
        )
        with analyzer.safe_mode():
            self.assertIsNone(analyzer.visitor(Not(child)))

        self.assertEqual(analyzer.staged_failure.name, 'NegativeLookaheadMatched')
        self.assertEqual(analyzer.staged_weight, 0)
        self.assertEqual(analyzer._errors, [])

    def test_nested_successful_assertions_do_not_publish_child_failures(self):
        analyzer, prior = self.analyzer_with_prior()
        published = []
        child = CandidateProbe(candidate=self.make_error('NestedNoise'), weight=3)
        with Diagnostics.hook_errors(lambda sender, err: published.append(err)):
            self.assertEqual(analyzer.visitor(Peek(Not(child))), [])

        self.assertIs(analyzer._staged_failure, prior)
        self.assertEqual(published, [])
        self.assertEqual(analyzer._errors, [])

    def test_unhandled_signals_and_exceptions_restore_incoming_candidate(self):
        for wrapper in (Alt, Opt, Peek, Not):
            for exception in (AbortFlowSignal(), RuntimeError('unexpected failure')):
                with self.subTest(wrapper=wrapper.__name__, exception=type(exception).__name__):
                    analyzer, prior = self.analyzer_with_prior()
                    child = CandidateProbe(
                        candidate=self.make_error('InterruptedNoise'), weight=3,
                        steps=1, exception=exception,
                    )
                    with self.assertRaises(type(exception)):
                        analyzer.visitor(wrapper(child))
                    self.assertIs(analyzer._staged_failure, prior)
                    self.assertFalse(analyzer.in_failure_context)
                    self.assertEqual(analyzer._errors, [])
                    self.assertEqual(analyzer.parser._targets, [])
                    if wrapper in (Peek, Not):
                        self.assertEqual(analyzer.parser.pos, 0)
