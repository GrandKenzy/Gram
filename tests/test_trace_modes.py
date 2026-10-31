"""Coverage for the ASTAnalyzer tracing modes: off, basic and detailed."""
from __future__ import annotations

from gram import parser
from gram.core.ast.analyzer import ASTAnalyzer
from gram.core.ast.raytracing import RayTracing, TraceRecord
from gram.core.combinators import Alt, MatchKeyword, MatchToken, Ref, RuleItem, Seq
from gram.core.combinators.signals import CutFlowSignal
from gram.core.combinators.skip import Skip
from gram.core.lexer.tokens import Token
from tests.combinators.base import CombinatorTestCase, DummyEntrypoint


class TraceEntryRule(RuleItem):
    entrypoint = MatchKeyword("int")


class TraceEntryPoint(RuleItem):
    entrypoint = Alt(Ref(TraceEntryRule))


class TestTraceModes(CombinatorTestCase):
    def analyzer(self, code: str, trace: str) -> ASTAnalyzer:
        p = parser.Parser(self.tokenize(code))
        return ASTAnalyzer(p, DummyEntrypoint, trace=trace)

    def test_unknown_mode_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.analyzer("int", "verbose")

    def test_off_registers_no_hook_and_records_nothing(self) -> None:
        analyzer = self.analyzer("int value", "off")
        self.assertNotIn(
            analyzer.dispatch_raytracing_process, analyzer.parser.hookr.callables
        )

        result = analyzer.visitor(Seq(MatchKeyword("int"), MatchToken(Token.IDENT)))

        self.assertEqual(len(result), 2)
        self.assertEqual(analyzer.raytracing.trace.values, [])
        self.assertEqual(analyzer.raytracing.records, [])

    def test_basic_records_trace_but_no_detailed_records(self) -> None:
        analyzer = self.analyzer("int value", "basic")

        analyzer.visitor(Seq(MatchKeyword("int"), MatchToken(Token.IDENT)))

        self.assertGreaterEqual(len(analyzer.raytracing.trace.values), 3)
        self.assertEqual(analyzer.raytracing.records, [])

    def test_detailed_records_span_and_outcome(self) -> None:
        analyzer = self.analyzer("int value", "detailed")

        analyzer.visitor(Seq(MatchKeyword("int"), MatchToken(Token.IDENT)))

        records = analyzer.raytracing.records
        self.assertTrue(all(isinstance(r, TraceRecord) for r in records))
        self.assertEqual(records[0].depth, 1)
        self.assertEqual((records[0].start, records[0].end), (0, 2))
        self.assertEqual(records[0].outcome, "SUCCESS")
        self.assertEqual(len(analyzer.raytracing.trace.values), len(records))

    def test_detailed_marks_failed_alternative_and_observes_backtrack(self) -> None:
        analyzer = self.analyzer("int value", "detailed")
        alt = Alt(
            Seq(MatchKeyword("int"), MatchKeyword("str")),
            Seq(MatchKeyword("int"), MatchToken(Token.IDENT)),
        )

        result = analyzer.visitor(alt)

        self.assertEqual(len(result), 2)
        raytracing = analyzer.raytracing
        self.assertIn("FAILED", [r.outcome for r in raytracing.records])
        self.assertTrue(raytracing.backtracks)
        self.assertGreaterEqual(raytracing.furthest, 1)
        self.assertIn("backtracks=", raytracing.detailed())

    def test_detailed_marks_control_signals(self) -> None:
        analyzer = self.analyzer("int value", "detailed")

        with self.assertRaises(CutFlowSignal):
            analyzer.visitor(Seq(MatchKeyword("int"), Skip(CutFlowSignal)))

        outcomes = {r.outcome: r.exception_type for r in analyzer.raytracing.records}
        self.assertEqual(outcomes.get("CONTROL"), "CutFlowSignal")
        control = next(r for r in analyzer.raytracing.records if r.outcome == "CONTROL")
        self.assertEqual(control.flow_kind, "commit_alternative")

    def test_parser_reports_abandoned_position_on_restore(self) -> None:
        p = parser.Parser(self.tokenize("int value"))
        checkpoint = p.savepoint("probe")
        p.consume()
        p.consume()

        p.restore(checkpoint)

        self.assertEqual(p._restore_from_pos, 2)
        self.assertEqual(p.pos, 0)

    def test_close_releases_snapshots_but_keeps_results(self) -> None:
        analyzer = self.analyzer("int value", "detailed")
        analyzer.visitor(Seq(MatchKeyword("int"), MatchToken(Token.IDENT)))
        raytracing = analyzer.raytracing

        analyzer.close()

        self.assertFalse(raytracing._checkpoints)
        self.assertFalse(raytracing._trace_stack)
        self.assertTrue(raytracing.records)
        self.assertNotIn(
            analyzer.dispatch_raytracing_process, analyzer.parser.hookr.callables
        )

    def test_entrypoint_trace_flags_are_restored_after_process(self) -> None:
        root = TraceEntryPoint.entrypoint
        child = root.combinators[0]
        before = (root.ignore, child.branchable)

        analyzer = self.analyzer("int", "off")
        analyzer.entrypoint = TraceEntryPoint
        analyzer.process()

        self.assertEqual((root.ignore, child.branchable), before)

    def test_empty_detailed_report(self) -> None:
        self.assertEqual(RayTracing(mode="detailed").detailed(), "PROGRAM\n    (empty)")
