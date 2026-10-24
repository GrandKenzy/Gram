"""Generated integration corpora and an observer-on/off equivalence check."""
from __future__ import annotations

import random

from gram.core.ast.analyzer import ASTAnalyzer
from gram.core.combinators import (
    Alt, ArithmeticExpr, MatchKeyword, MatchToken, Ref, RuleItem, Seq,
)
from gram.core.combinators.expressions import ASTBinaryOp
from gram.core.lexer import Lexer, Token, words
from gram.core.parser import Parser
from tests.combinators.base import CombinatorTestCase


class StressDeclaration(RuleItem):
    entrypoint = Seq(
        MatchKeyword('let'), MatchToken(Token.IDENT), MatchToken(Token.ASSIGN),
        ArithmeticExpr(Token.NUMBER), MatchToken(Token.SEMICOLON),
    )


class StressProgram(RuleItem):
    entrypoint = Alt(Ref(StressDeclaration))


class SilentTracing:
    """Disable only observation, leaving the production visitor unchanged."""
    def ignore(self, *args, **kwargs):
        pass

    add = addpath = generate_branch = lift = unreach = ignore


def evaluate(node):
    if isinstance(node, ASTBinaryOp):
        left, right = evaluate(node.left), evaluate(node.right)
        if node.operator.token == Token.PLUS:
            return left + right
        if node.operator.token == Token.STAR:
            return left * right
        raise AssertionError(f'Unexpected generated operator: {node.operator.token}')
    return node.token.value


class TestParserStress(CombinatorTestCase):
    def setUp(self):
        super().setUp()
        words.add_keyword('let')

    def corpus(self, seed, count):
        rng = random.Random(seed)
        source, expected = [], []
        for index in range(count):
            a, b, c = (rng.randrange(1, 100) for _ in range(3))
            if rng.randrange(2):
                expression, value = f'({a} + {b}) * {c}', (a + b) * c
            else:
                expression, value = f'{a} + {b} * {c}', a + b * c
            source.append(f'let v{index} = {expression};')
            expected.append((f'v{index}', value))
        return '\n'.join(source), expected

    def analyze(self, source, tracing):
        lexer = Lexer(source)
        parser = Parser(lexer.process())
        analyzer = ASTAnalyzer(parser, StressProgram)
        if not tracing:
            parser.hookr.remove(analyzer.dispatch_raytracing_process)
            analyzer.raytracing = SilentTracing()
        try:
            roots = analyzer.process()
            values = [(node.nodes[1].token.value, evaluate(node.nodes[3])) for node in roots]
            diagnostics = [(err.name, str(err.code), err.caution) for err in analyzer._errors]
            return values, diagnostics, parser.pos, parser.is_eof()
        finally:
            # The stress corpus must not leave its telemetry in the global registry.
            for owner in (lexer, parser, analyzer):
                owner.stack.clean()

    def test_generated_programs_match_oracle_with_and_without_tracing(self):
        for seed in (0, 7, 42, 20261023):
            for count in (1, 8, 32):
                with self.subTest(seed=seed, count=count):
                    source, expected = self.corpus(seed, count)
                    observed = self.analyze(source, tracing=True)
                    silent = self.analyze(source, tracing=False)
                    self.assertEqual(observed, silent)
                    self.assertEqual(observed[0], expected)
                    self.assertEqual(observed[1], [])
                    self.assertTrue(observed[3])

    def test_incomplete_programs_have_identical_prefix_and_errors_with_tracing(self):
        for seed in (0, 7, 42, 20261023):
            source, expected = self.corpus(seed, 8)
            for suffix in ('let broken =', 'let broken = 1 +', 'let broken = (1 + 2;'):
                with self.subTest(seed=seed, suffix=suffix):
                    invalid = source + '\n' + suffix
                    observed = self.analyze(invalid, tracing=True)
                    self.assertEqual(observed, self.analyze(invalid, tracing=False))
                    self.assertEqual(observed[0], expected)
                    self.assertTrue(observed[1])
                    self.assertFalse(observed[3])

    def test_thousand_declarations_without_tracing_match_arithmetic_oracle(self):
        source, expected = self.corpus(20261023, 1000)
        values, diagnostics, _, at_eof = self.analyze(source, tracing=False)
        self.assertEqual(values, expected)
        self.assertEqual(diagnostics, [])
        self.assertTrue(at_eof)
