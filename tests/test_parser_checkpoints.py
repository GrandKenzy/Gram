"""Checkpoint rollback for repeated token replacements and speculative parsing."""
from __future__ import annotations

from gram.core.combinators.alternative import Alt
from gram.core.combinators.load import Load
from gram.core.combinators.match import MatchToken
from gram.core.combinators.peek import Peek
from gram.core.combinators.sequence import Seq
from gram.core.lexer.tokens import Token
from tests.combinators.base import CombinatorTestCase


class TestParserCheckpoints(CombinatorTestCase):
    def test_repeated_restore_and_reuse_of_nested_checkpoints(self) -> None:
        parser = self.create_analyzer("1 2 3").parser
        original, second, third = parser.tokens[:3]
        outer = parser.savepoint("original")
        parser.replace_token_at(0, second)
        inner = parser.savepoint("first-replacement")
        parser.replace_token_at(0, third)

        for _ in range(2):
            parser.restore(inner)
            self.assertIs(parser.tokens[0], second)
            self.assertEqual(parser._token_overrides, {0: original})

        for _ in range(2):
            parser.restore(outer)
            self.assertIs(parser.tokens[0], original)
            self.assertEqual(parser._token_overrides, {})
            parser.restore(inner)
            self.assertIs(parser.tokens[0], second)
            self.assertEqual(parser._token_overrides, {0: original})

    def test_restore_multiple_indices_and_other_parser_state(self) -> None:
        parser = self.create_analyzer("one two three four").parser
        original = tuple(parser.tokens)
        parser.replace_token_at(0, original[1])
        parser.replace_token_at(2, original[3])
        parser.pos, parser.vpos, parser.bracket_depth = 1, 2, 1
        parser.storage = {"kept": original[1]}
        parser.tk_tags = {0: frozenset({"kept"})}
        checkpoint = parser.savepoint("several-replacements")

        parser.replace_token_at(0, original[2])
        parser.replace_token_at(1, original[3])
        parser.replace_token_at(2, original[0])
        parser.pos, parser.vpos, parser.bracket_depth = 3, 0, 0
        parser.storage = {"discarded": original[0]}
        parser.tk_tags = {1: frozenset({"discarded"})}
        parser.node("Speculative", "Discard this target", set_target=True)
        parser.restore(checkpoint)

        for actual, expected in zip(
            parser.tokens, (original[1], original[1], original[3], *original[3:])
        ):
            self.assertIs(actual, expected)
        self.assertEqual(parser._token_overrides, {0: original[0], 2: original[2]})
        self.assertEqual(parser.snapshot(), {"pos": 1, "vpos": 2, "bracket_depth": 1})
        self.assertEqual(parser.storage, {"kept": original[1]})
        self.assertEqual(parser.tk_tags, {0: frozenset({"kept"})})
        self.assertEqual(tuple(parser._targets), checkpoint.targets)

    def test_savepoint_does_not_scan_the_token_stream(self) -> None:
        class IndexedOnlyTokens(list):
            def __iter__(self):
                raise AssertionError("Checkpoint must not copy the token stream")

            def __getitem__(self, index):
                if isinstance(index, slice):
                    raise AssertionError("Checkpoint must not slice the token stream")
                return super().__getitem__(index)

        parser = self.create_analyzer("1 2 3").parser
        original, replacement = parser.tokens[:2]
        parser.tokens = IndexedOnlyTokens(parser.tokens * 1000)
        parser.savepoint("unchanged-large-stream")
        parser.replace_token_at(0, replacement)
        checkpoint = parser.savepoint("one-replacement")
        parser.replace_token_at(0, original)
        parser.restore(checkpoint)
        self.assertIs(parser.tokens[0], replacement)

    def test_load_failed_matcher_restores_an_existing_replacement(self) -> None:
        analyzer = self.create_analyzer("1 2 3")
        parser = analyzer.parser
        original, second, third = parser.tokens[:3]
        parser.replace_token_at(0, second)
        parser.storage["saved"] = third

        with analyzer.safe_mode():
            result = analyzer.visitor(
                Load("saved", mode="replace", matcher=MatchToken(Token.STRING))
            )

        self.assertIsNone(result)
        self.assertIs(parser.tokens[0], second)
        self.assertEqual(parser._token_overrides, {0: original})
        self.assertEqual(parser.pos, 0)

    def test_peek_restores_replacement_and_swapped_storage(self) -> None:
        analyzer = self.create_analyzer("first second third")
        parser = analyzer.parser
        original, second, third = parser.tokens[:3]
        parser.replace_token_at(0, second)
        parser.storage["saved"] = third

        result = analyzer.visitor(
            Peek(Load("saved", mode="change", matcher=MatchToken(Token.IDENT)))
        )

        self.assertEqual(result, [])
        self.assertIs(parser.tokens[0], second)
        self.assertIs(parser.storage["saved"], third)
        self.assertEqual(parser._token_overrides, {0: original})
        self.assertEqual(parser.pos, 0)

    def test_alt_restores_existing_replacement_before_next_branch(self) -> None:
        analyzer = self.create_analyzer("1 2 3")
        parser = analyzer.parser
        original, second, third = parser.tokens[:3]
        parser.replace_token_at(0, second)
        parser.storage["saved"] = third

        result = analyzer.visitor(
            Alt(
                Seq(
                    Load("saved", mode="replace", matcher=MatchToken(Token.NUMBER)),
                    MatchToken(Token.STRING),
                ),
                MatchToken(Token.NUMBER),
            )
        )

        self.assertIs(result.token, second)
        self.assertIs(parser.tokens[0], second)
        self.assertEqual(parser._token_overrides, {0: original})
        self.assertEqual(parser.pos, 1)
