"""Exhaustive C-define-style coverage for logical token conversions."""
from __future__ import annotations

import unittest

from gram import config, errors, lexer
from gram.core.combinators import Alt, Combinator, Convert, MatchToken, Ref, RuleItem, Seq
from gram.core.lexer import MAP_SYMBOLS, Token, TokenType
from gram.core.parser import ConversionState
from gram.sessions import Session
from tests.combinators.base import CombinatorTestCase


class CDefine(Combinator):
    """Small test-only parser for ``#define NAME REPLACEMENT`` directives."""

    def parse(self, analyzer):
        parser = analyzer.parser
        checkpoint = parser.savepoint("C-DEFINE")

        hash_token = parser.peek()
        if hash_token is None or hash_token.token != Token.HASH:
            parser.restore(checkpoint)
            return None
        parser.consume()

        define_token = parser.peek()
        if (
            define_token is None
            or define_token.token != Token.KEYWORD
            or define_token.value != "define"
        ):
            parser.restore(checkpoint)
            return None
        parser.consume()

        name_token = parser.peek()
        if name_token is None or name_token.token != Token.IDENT:
            parser.restore(checkpoint)
            return None
        parser.consume()

        replacement = parser.peek()
        if replacement is None:
            parser.restore(checkpoint)
            return None

        target = MAP_SYMBOLS.get(str(replacement.value))
        if target is None and replacement.token == Token.IDENT:
            target = Token.from_string(str(replacement.value))
        if target is None:
            parser.restore(checkpoint)
            return None
        parser.consume()

        try:
            parser.register_conversion(str(name_token.value), target)
        except ValueError as exc:
            parser.restore(checkpoint)
            analyzer.report_error(
                errors.GrammarError(
                    "CDefineConversionConflict",
                    errors.GRAMMAR_COMBINATOR_FAILED,
                    str(exc),
                    "No redefina una macro con otro token dentro de la misma unidad.",
                ),
                pos=checkpoint.pos,
            )
            return None
        return []

    def __repr__(self) -> str:
        return "CDefine()"


class CDefineRule(RuleItem):
    entrypoint = CDefine()


class CTokenUseRule(RuleItem):
    entrypoint = Alt(
        MatchToken(Token.STAR),
        MatchToken(Token.DOT),
        MatchToken(Token.COMMA),
        MatchToken(Token.LPAREN),
        MatchToken(Token.RPAREN),
    )


class CProgram(RuleItem):
    entrypoint = Alt(Ref(CDefineRule), Ref(CTokenUseRule))


class BrokenDefineItem(RuleItem):
    entrypoint = Seq(CDefine(), MatchToken(Token.DOT))


class BrokenDefineProgram(RuleItem):
    entrypoint = Alt(Ref(BrokenDefineItem))


class TestCDefineConversions(CombinatorTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.previous_comment = config.LEXER_COMMENT_TOKEN
        config.LEXER_COMMENT_TOKEN = "//"
        lexer.add_keyword("define")

    def tearDown(self) -> None:
        config.LEXER_COMMENT_TOKEN = self.previous_comment
        super().tearDown()

    def lex(self, source: str) -> list[TokenType]:
        return lexer.Lexer(source).process()

    def test_define_pointer_macro_changes_future_use(self) -> None:
        result, analyzer = self.parse_with_analyzer(
            Seq(
                CDefine(),
                MatchToken(Token.STAR),
            ),
            "#define PTR * PTR",
        )

        self.assertIsNotNone(result)
        self.assertEqual(analyzer.parser.export_conversions(), {"PTR": Token.STAR})
        self.assertEqual(analyzer.parser.pos, 5)

    def test_define_can_build_structural_syntax(self) -> None:
        grammar = Seq(
            CDefine(),
            CDefine(),
            CDefine(),
            MatchToken(Token.LPAREN),
            MatchToken(Token.IDENT),
            MatchToken(Token.COMMA),
            MatchToken(Token.IDENT),
            MatchToken(Token.RPAREN),
        )
        result, analyzer = self.parse_with_analyzer(
            grammar,
            "#define OPEN ( #define SEP , #define CLOSE ) OPEN left SEP right CLOSE",
        )

        self.assertIsNotNone(result)
        self.assertEqual(
            analyzer.parser.export_conversions(),
            {"OPEN": Token.LPAREN, "SEP": Token.COMMA, "CLOSE": Token.RPAREN},
        )

    def test_define_is_exact_and_case_sensitive(self) -> None:
        result, analyzer = self.parse_with_analyzer(
            Seq(
                CDefine(),
                MatchToken(Token.STAR),
                MatchToken(Token.IDENT),
            ),
            "#define PTR * PTR ptr",
        )

        self.assertIsNotNone(result)
        self.assertEqual(analyzer.parser.export_conversions(), {"PTR": Token.STAR})

    def test_local_convert_does_not_escape_like_a_define(self) -> None:
        result, analyzer = self.parse_with_analyzer(
            Seq(
                Convert("PTR", Token.STAR),
                MatchToken(Token.STAR),
                MatchToken(Token.IDENT),
            ),
            "PTR PTR",
        )

        self.assertIsNotNone(result)
        self.assertEqual(analyzer.parser.export_conversions(), {})

    def test_export_import_carries_macros_to_another_file(self) -> None:
        first = self.create_analyzer(self.lex("#define PTR *"))
        self.assertIsNotNone(first.visitor(CDefine()))
        exported = first.parser.export_conversions()

        second = self.create_analyzer(self.lex("PTR"))
        second.parser.import_conversions(exported)
        result = second.visitor(MatchToken(Token.STAR))

        self.assertIsNotNone(result)
        self.assertEqual(exported, {"PTR": Token.STAR})

    def test_import_is_detached_and_does_not_mutate_source_state(self) -> None:
        source = self.create_analyzer(self.lex("#define PTR *"))
        source.visitor(CDefine())
        exported = source.parser.export_conversions()

        exported["PTR"] = Token.DOT
        self.assertEqual(source.parser.export_conversions(), {"PTR": Token.STAR})

        target = self.create_analyzer(self.lex("PTR"))
        target.parser.import_conversions(source.parser.export_conversions())
        target.parser.conversions["OTHER"] = Token.COMMA
        self.assertEqual(source.parser.export_conversions(), {"PTR": Token.STAR})

    def test_shared_state_accumulates_defines_across_files(self) -> None:
        state = ConversionState()
        session = Session("C", "Many")

        first = session.parse(
            self.lex("#define PTR *"),
            "pointer.h",
            CProgram,
            conversion_state=state,
        )
        second = session.parse(
            self.lex("#define OPEN ("),
            "syntax.h",
            CProgram,
            conversion_state=state,
        )
        third = session.parse(
            self.lex("PTR OPEN"),
            "main.c",
            CProgram,
            conversion_state=state,
        )

        self.assertTrue(first)
        self.assertTrue(second)
        self.assertTrue(third)
        self.assertEqual(
            state.export(),
            {"PTR": Token.STAR, "OPEN": Token.LPAREN},
        )

    def test_separate_files_do_not_inherit_defines_without_state(self) -> None:
        session = Session("C", "Many")
        first = session.parse(self.lex("#define PTR *"), "header.h", CProgram)
        second = session.parse(self.lex("PTR"), "other.c", CProgram)

        self.assertTrue(first)
        self.assertEqual(second, [])

    def test_two_language_states_can_interpret_same_macro_differently(self) -> None:
        c_state = ConversionState({"VALUE": Token.STAR})
        script_state = ConversionState({"VALUE": Token.STRING})

        c_analyzer = self.create_analyzer(self.lex("VALUE"))
        c_analyzer.parser.import_conversions(c_state.export())

        script_analyzer = self.create_analyzer(self.lex("VALUE"))
        script_analyzer.parser.import_conversions(script_state.export())

        self.assertIsNotNone(c_analyzer.visitor(MatchToken(Token.STAR)))
        self.assertIsNone(script_analyzer.visitor(MatchToken(Token.STAR)))
        self.assertEqual(script_analyzer.parser.pos, 0)
        self.assertEqual(c_analyzer.parser.export_conversions(), {"VALUE": Token.STAR})

    def test_failed_file_does_not_export_partial_define(self) -> None:
        state = ConversionState()
        session = Session("C", "Many")

        # The definition succeeds locally, but the required following token fails.
        result = session.parse(
            self.lex("#define PTR * MISSING"),
            "broken.c",
            BrokenDefineProgram,
            conversion_state=state,
        )

        self.assertEqual(result, [])
        self.assertEqual(state.export(), {})

    def test_conflicting_define_does_not_replace_existing_macro(self) -> None:
        state = ConversionState({"PTR": Token.STAR})
        session = Session("C", "Many")

        result = session.parse(
            self.lex("#define PTR ."),
            "redefine.c",
            CProgram,
            conversion_state=state,
        )

        self.assertEqual(result, [])
        self.assertEqual(state.export(), {"PTR": Token.STAR})

    def test_backtracking_removes_speculative_define(self) -> None:
        analyzer = self.create_analyzer(self.lex("#define PTR * PTR"))
        result = analyzer.visitor(
            Alt(
                Seq(CDefine(), MatchToken(Token.NUMBER)),
                MatchToken(Token.HASH),
            )
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.token.value, "#")
        self.assertEqual(analyzer.parser.export_conversions(), {})
        self.assertEqual(analyzer.parser.pos, 1)

    def test_conversion_state_clone_is_safe_for_include_variants(self) -> None:
        parent = ConversionState({"PTR": Token.STAR})
        header_a = parent.clone()
        header_b = parent.clone()
        header_a.register("OPEN", Token.LPAREN)
        header_b.register("CLOSE", Token.RPAREN)

        self.assertEqual(parent.export(), {"PTR": Token.STAR})
        self.assertEqual(
            header_a.export(),
            {"PTR": Token.STAR, "OPEN": Token.LPAREN},
        )
        self.assertEqual(
            header_b.export(),
            {"PTR": Token.STAR, "CLOSE": Token.RPAREN},
        )


if __name__ == "__main__":
    unittest.main()
