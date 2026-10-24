"""Bounded, seeded adversarial checks for speculative diagnostic contracts.

Four seeds cover 160 scope programs (1,600 scopes and 4,800 local reports),
plus 1,120 generated wrapper cases. Expected causes come from declared leaf
events and grammatical outcomes, independently of the staged parser state.
"""
from __future__ import annotations

import random

from gram import errors
from gram.core.combinators import Alt, Combinator, Not, Opt, Peek
from gram.core.combinators.signals import (
    AbortFlowSignal, BacktrackSignal, CutFlowSignal,
)
from gram.core.lexer import Token, TokenType
from gram.utilities import Diagnostics
from tests.combinators.base import CombinatorTestCase


SEEDS = (7, 29, 101, 4099)


class DiagnosticLeaf(Combinator):
    """A declared parse outcome with explicit diagnostic events."""

    def __init__(self, events=(), *, succeeds=False, steps=0, interruption=None):
        super().__init__()
        self.events = events
        self.succeeds = succeeds
        self.steps = steps
        self.interruption = interruption
        self.calls = 0

    def parse(self, analyzer):
        self.calls += 1
        for _ in range(self.steps):
            analyzer.parser.consume()
        for weight, error in self.events:
            analyzer.report_error(error, pos=weight)
        if self.interruption is not None:
            raise self.interruption
        return [] if self.succeeds else None


class TestDiagnosticFuzz(CombinatorTestCase):
    def setUp(self):
        super().setUp()
        self.tokens = [
            TokenType(Token.IDENT, f'name{i}', 0, i * 6) for i in range(9)
        ] + [TokenType(Token.EOF, None, 0, 54)]
        self.errors = [
            errors.ParserError(f'Cause{i}', errors.PARSER_UNEXPECTED_TOKEN)
            for i in range(24)
        ]

    def analyzer_with_prior(self, rng):
        analyzer = self.create_analyzer(self.tokens)
        analyzer.stage_failure(rng.choice(self.errors), weight=rng.choice((0, 1, 4, 99)))
        return analyzer, analyzer._staged_failure

    def test_seeded_nested_scopes_restore_exact_parent_and_keep_local_events(self):
        scopes = reports = 0
        published = []
        for seed in SEEDS:
            rng = random.Random(seed)
            for program in range(40):
                analyzer, prior = self.analyzer_with_prior(rng)
                plans = []
                for _ in range(10):
                    events = [
                        (rng.choice((0, 0, 1, 2, 4)), rng.choice(self.errors))
                        for _ in range(3)
                    ]
                    interruption = rng.choice((
                        None, CutFlowSignal(), BacktrackSignal(), AbortFlowSignal(),
                        RuntimeError('scope interruption'),
                    ))
                    plans.append((events, rng.randrange(4), interruption))

                def exercise(level):
                    nonlocal scopes, reports
                    events, child_position, interruption = plans[level]
                    incoming = analyzer._staged_failure
                    # Stable maximum specifies the first cause when offsets tie.
                    expected = max(events, key=lambda event: event[0])
                    try:
                        with analyzer.failure_scope() as scope:
                            self.assertIsNone(analyzer.staged_failure)
                            self.assertTrue(analyzer.safe_flag)
                            for position in range(4):
                                if position == child_position and level + 1 < len(plans):
                                    exercise(level + 1)
                                if position < len(events):
                                    weight, error = events[position]
                                    analyzer.report_error(error, pos=weight)
                                    reports += 1
                            if interruption is not None:
                                raise interruption
                    except (CutFlowSignal, BacktrackSignal, AbortFlowSignal, RuntimeError) as caught:
                        self.assertIs(caught, interruption)
                    self.assertEqual(scope.candidate, expected, (seed, program, level))
                    self.assertIs(analyzer._staged_failure, incoming)
                    scopes += 1

                with Diagnostics.hook_errors(lambda sender, error: published.append(error)):
                    exercise(0)
                self.assertIs(analyzer._staged_failure, prior)
                self.assertFalse(analyzer.safe_flag)
                self.assertEqual(analyzer._errors, [])
                self.assertEqual(published, [])

        self.assertEqual(scopes, 1600)
        self.assertEqual(reports, 4800)

    def test_seeded_successful_assertions_and_alternatives_discard_rejected_causes(self):
        cases = 0
        published = []
        with Diagnostics.hook_errors(lambda sender, error: published.append(error)):
            for seed in SEEDS:
                rng = random.Random(seed)
                for iteration in range(60):
                    analyzer, prior = self.analyzer_with_prior(rng)
                    rejected = DiagnosticLeaf(
                        ((rng.randint(2, 8), rng.choice(self.errors)),),
                        steps=rng.randint(1, 4),
                    )
                    accepted = rng.choice((
                        Opt(DiagnosticLeaf(((1, rng.choice(self.errors)),), succeeds=True, steps=1)),
                        Peek(DiagnosticLeaf(((8, rng.choice(self.errors)),), succeeds=True, steps=4)),
                        Not(DiagnosticLeaf(((8, rng.choice(self.errors)),), steps=4)),
                        Alt(DiagnosticLeaf(((0, rng.choice(self.errors)),), succeeds=True)),
                    ))
                    for _ in range(rng.randint(1, 8)):
                        accepted = Peek(accepted)

                    self.assertEqual(analyzer.visitor(Alt(rejected, accepted)), [], (seed, iteration))
                    self.assertIs(analyzer._staged_failure, prior)
                    self.assertEqual(analyzer.parser.pos, 0)
                    self.assertEqual(analyzer._errors, [])
                    self.assertEqual(published, [])
                    cases += 1

        self.assertEqual(cases, 240)

    def test_seeded_failed_alternatives_publish_one_deepest_local_cause(self):
        cases = 0
        for seed in SEEDS:
            rng = random.Random(seed)
            for iteration in range(60):
                analyzer, _ = self.analyzer_with_prior(rng)
                branches = []
                events = []
                for _ in range(rng.randint(2, 5)):
                    branch_events = [
                        (rng.randint(1, 8), rng.choice(self.errors))
                        for _ in range(rng.randint(1, 3))
                    ]
                    events.extend(branch_events)
                    branches.append(DiagnosticLeaf(branch_events, steps=rng.randint(0, 4)))
                expected = max(events, key=lambda event: event[0])[1]
                combinator = Alt(*branches)
                for _ in range(rng.randint(0, 8)):
                    combinator = rng.choice((Opt, Peek))(combinator)
                published = []
                with Diagnostics.hook_errors(lambda sender, error: published.append(error)):
                    self.assertIsNone(analyzer.visitor(combinator), (seed, iteration))

                self.assertEqual(analyzer._errors, [expected], (seed, iteration))
                self.assertEqual(published, [expected])
                self.assertIsNone(analyzer.staged_failure)
                self.assertEqual(analyzer.parser.pos, 0)
                self.assertFalse(analyzer.safe_flag)
                self.assertEqual(analyzer.parser._targets, [])
                cases += 1

        self.assertEqual(cases, 240)

    def test_seeded_nested_signals_commit_backtrack_or_escape_without_pollution(self):
        cases = 0
        signal_types = (CutFlowSignal, BacktrackSignal, AbortFlowSignal, RuntimeError)
        for seed in SEEDS:
            rng = random.Random(seed)
            for iteration in range(40):
                for signal_type in signal_types:
                    analyzer, prior = self.analyzer_with_prior(rng)
                    committed = rng.choice(self.errors)
                    signal = signal_type('generated interruption')
                    child = DiagnosticLeaf(
                        ((rng.randint(1, 3), committed),), steps=1,
                        interruption=signal,
                    )
                    for _ in range(rng.randint(1, 8)):
                        child = rng.choice((Opt, Peek, Not))(child)
                    rejected = DiagnosticLeaf(((8, rng.choice(self.errors)),))
                    fallback = DiagnosticLeaf(succeeds=True)
                    combinator = Alt(rejected, child, fallback)
                    published = []

                    with Diagnostics.hook_errors(lambda sender, error: published.append(error)):
                        if signal_type in (AbortFlowSignal, RuntimeError):
                            with self.assertRaises(signal_type) as caught:
                                analyzer.visitor(combinator)
                            self.assertIs(caught.exception, signal)
                        else:
                            result = analyzer.visitor(combinator)
                            if signal_type is CutFlowSignal:
                                self.assertIsNone(result)
                            else:
                                self.assertEqual(result, [])

                    label = (seed, iteration, signal_type.__name__)
                    if signal_type is CutFlowSignal:
                        self.assertEqual(analyzer._errors, [committed], label)
                        self.assertEqual(published, [committed], label)
                        self.assertIsNone(analyzer.staged_failure)
                    else:
                        self.assertIs(analyzer._staged_failure, prior, label)
                        self.assertEqual(analyzer._errors, [], label)
                        self.assertEqual(published, [], label)
                    self.assertEqual(fallback.calls, int(signal_type is BacktrackSignal), label)
                    self.assertFalse(analyzer.safe_flag, label)
                    self.assertEqual(analyzer.parser._targets, [], label)
                    cases += 1

        self.assertEqual(cases, 640)
