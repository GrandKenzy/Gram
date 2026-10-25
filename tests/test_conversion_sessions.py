"""Isolation and explicit transfer tests for parser conversions."""
from __future__ import annotations

import unittest

from gram import config
from gram.core.combinators import Alt, Convert, MatchToken, Ref, RuleItem, Seq
from gram.core.lexer import Token, TokenType
from gram.core.parser import ConversionState, Parser
from gram.sessions import Session


class ScopedConversionItem(RuleItem):
    entrypoint = Seq(
        Convert("Bunga", Token.DOT, scope=True),
        MatchToken(Token.DOT),
    )


class ScopedConversionProgram(RuleItem):
    entrypoint = Alt(Ref(ScopedConversionItem))


class DotItem(RuleItem):
    entrypoint = MatchToken(Token.DOT)


class DotProgram(RuleItem):
    entrypoint = Alt(Ref(DotItem))


class TestConversionState(unittest.TestCase):
    def setUp(self) -> None:
        self.previous_exit = config.ERROR_EXIT_ON_ERROR
        self.previous_hide = config.ERROR_HIDE_CONSOLE
        config.ERROR_EXIT_ON_ERROR = False
        config.ERROR_HIDE_CONSOLE = True

    def tearDown(self) -> None:
        config.ERROR_EXIT_ON_ERROR = self.previous_exit
        config.ERROR_HIDE_CONSOLE = self.previous_hide

    def tokens(self, source: str):
        return [
            TokenType(Token.IDENT, source, 0, 0),
            TokenType(Token.EOF, None, 1, 0),
        ]

    def test_parser_can_export_and_import_detached_conversions(self) -> None:
        source = Parser(self.tokens("Bunga"))
        source.register_conversion("Bunga", Token.DOT)
        exported = source.export_conversions()

        target = Parser(self.tokens("Bunga"))
        target.import_conversions(exported)
        self.assertEqual(target.export_conversions(), {"Bunga": Token.DOT})

        # The exported dictionary is detached from the source parser.
        exported.clear()
        self.assertEqual(source.export_conversions(), {"Bunga": Token.DOT})

    def test_session_state_can_carry_one_file_addition_into_another(self) -> None:
        session = Session("C-like", "Many")
        state = ConversionState()

        first = session.parse(
            self.tokens("Bunga"),
            "first.c",
            ScopedConversionProgram,
            conversion_state=state,
        )
        self.assertTrue(first)
        self.assertEqual(state.export(), {"Bunga": Token.DOT})

        second = session.parse(
            self.tokens("Bunga"),
            "second.c",
            DotProgram,
            conversion_state=state,
        )
        self.assertTrue(second)

    def test_session_without_shared_state_does_not_inherit_file_conversion(self) -> None:
        session = Session("isolated", "Many")
        state = ConversionState()
        session.parse(
            self.tokens("Bunga"),
            "first.c",
            ScopedConversionProgram,
            conversion_state=state,
        )

        isolated = session.parse(
            self.tokens("Bunga"),
            "other.c",
            DotProgram,
        )
        self.assertEqual(isolated, [])

    def test_failed_parse_does_not_update_external_state(self) -> None:
        session = Session("transactional", "Many")
        state = ConversionState()

        result = session.parse(
            self.tokens("Bunga"),
            "broken.c",
            ScopedConversionProgram,
            conversion_state=state,
        )
        self.assertTrue(result)

        # A conflicting second definition fails before it can escape.
        class ConflictingItem(RuleItem):
            entrypoint = Seq(
                Convert("Bunga", Token.COMMA, scope=True),
                MatchToken(Token.COMMA),
            )

        class ConflictingProgram(RuleItem):
            entrypoint = Alt(Ref(ConflictingItem))

        result = session.parse(
            self.tokens("Bunga"),
            "conflict.c",
            ConflictingProgram,
            conversion_state=state,
        )
        self.assertEqual(result, [])
        self.assertEqual(state.export(), {"Bunga": Token.DOT})

    def test_conversion_state_clone_and_reset(self) -> None:
        state = ConversionState({"Bunga": Token.DOT})
        clone = state.clone()
        clone.register("Other", Token.COMMA)

        self.assertEqual(state.export(), {"Bunga": Token.DOT})
        self.assertEqual(
            clone.export(),
            {"Bunga": Token.DOT, "Other": Token.COMMA},
        )

        clone.clear()
        self.assertEqual(clone.export(), {})
        self.assertEqual(state.export(), {"Bunga": Token.DOT})


if __name__ == "__main__":
    unittest.main()
