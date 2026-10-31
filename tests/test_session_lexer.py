"""Session-owned lexer registry regression tests."""
from __future__ import annotations

import unittest

from gram import config
from gram import combinators as cmb
from gram.core.lexer import Token, WordGroupManager, tokens, words
from gram.sessions import Session


class SessionDeclaration(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.MatchKeyword("let"),
        cmb.MatchToken(Token.IDENT),
    )


class SessionProgram(cmb.RuleItem):
    entrypoint = cmb.Alt(cmb.Ref(SessionDeclaration))


class SessionGroupDeclaration(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.MatchGroup("types"),
        cmb.MatchToken(Token.IDENT),
    )


class SessionGroupProgram(cmb.RuleItem):
    entrypoint = cmb.Alt(cmb.Ref(SessionGroupDeclaration))


class SessionLexerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config_snapshot = config.save()
        self.keywords_snapshot = tuple(words.MAP_KEYWORDS.items())
        self.groups_snapshot = tuple(words._GLOBAL_GROUPS.items())
        self.symbols_snapshot = tuple(tokens.MAP_SYMBOLS.items())
        words.unbind_session()
        words.clear_all()
        self.addCleanup(self._restore)

    def _restore(self) -> None:
        words.unbind_session()
        words.MAP_KEYWORDS.clear()
        words.MAP_KEYWORDS.update(self.keywords_snapshot)
        words._GLOBAL_GROUPS.clear()
        words._GLOBAL_GROUPS.update(self.groups_snapshot)
        tokens.MAP_SYMBOLS.clear()
        tokens.MAP_SYMBOLS.update(self.symbols_snapshot)
        tokens._sync_symbol_indexes()
        config.load(self.config_snapshot)

    def test_loose_registration_routes_to_session_during_init(self) -> None:
        session = Session("session-lexer", "Many")
        session.init()
        words.add_group("types")
        words.add_keyword("integer", group="types")
        session.migrate()

        self.assertIn("integer", session.keywords)
        self.assertIn("types", session.groups)
        self.assertNotIn("integer", words.MAP_KEYWORDS)
        result = session.tokenize("integer value", "session.gram")
        self.assertEqual([item.token for item in result[:2]], [Token.KEYWORD, Token.IDENT])

    def test_two_sessions_keep_lexicons_isolated(self) -> None:
        first = Session("first", "Many")
        first.init()
        first.add_keyword("alpha")
        first.migrate()

        second = Session("second", "Many")
        second.init()
        second.add_keyword("beta")
        second.migrate()

        first_tokens = first.tokenize("alpha beta", "first.gram")
        second_tokens = second.tokenize("alpha beta", "second.gram")
        self.assertEqual([item.token for item in first_tokens[:2]], [Token.KEYWORD, Token.IDENT])
        self.assertEqual([item.token for item in second_tokens[:2]], [Token.IDENT, Token.KEYWORD])

    def test_lexer_reads_configuration_from_session(self) -> None:
        session = Session("configured", "Many")
        session.init()
        session.add_keyword("if")
        config.LEXER_SUPPORT_PREFIXED_STRINGS = False
        session.migrate()

        config.LEXER_SUPPORT_PREFIXED_STRINGS = True
        result = session.tokenize('L"value"', "configured.gram")
        self.assertEqual(
            [(item.token, item.value) for item in result],
            [(Token.IDENT, "L"), (Token.STRING, "value"), (Token.EOF, None)],
        )

    def test_lexer_reads_symbols_from_session(self) -> None:
        session = Session("symbols", "Many")
        session.init()
        tokens.MAP_SYMBOLS["@@"] = Token.AT
        tokens._sync_symbol_indexes()
        session.add_keyword("value")
        session.migrate()

        result = session.tokenize("value @@", "symbols.gram")
        self.assertEqual(
            [(item.token, item.value) for item in result],
            [(Token.KEYWORD, "value"), (Token.AT, "@@"), (Token.EOF, None)],
        )

    def test_load_exposes_session_catalog_to_legacy_readers(self) -> None:
        session = Session("loadable", "Many")
        session.init()
        session.add_keyword("loaded")
        session.migrate()
        session.load()

        self.assertIsNotNone(words.get_keyword("loaded"))

    def test_direct_session_registration_stays_visible_after_load(self) -> None:
        session = Session("loaded-mutation", "Many")
        session.init()
        session.add_keyword("before")
        session.migrate()
        session.load()

        session.add_keyword("after")
        self.assertIsNotNone(words.get_keyword("after"))
        result = session.tokenize("before after", "loaded-mutation.gram")
        self.assertEqual(
            [item.token for item in result[:2]],
            [Token.KEYWORD, Token.KEYWORD],
        )

    def test_parser_and_ast_analyzer_keep_the_session_view(self) -> None:
        session = Session("parser-session", "Many", SessionProgram)
        session.init()
        session.add_keyword("let")
        session.migrate()
        session.config["PARSER_ADD_INFO"] = False
        session.config["AST_ADD_INFO"] = False

        tokens_result = session.tokenize("let value", "parser-session.gram")
        parser_identity = id(session.parser)
        result = session.parse(tokens_result, "parser-session.gram", trace="off")

        self.assertEqual(len(result), 1)
        self.assertEqual(id(session.parser), parser_identity)
        self.assertIs(session.parser.session, session)
        self.assertIs(session.parser.analyzer_ast_instance.session, session)
        self.assertIs(session.parser.analyzer_ast_instance.parser, session.parser)
        self.assertFalse(session.parser.get_config("PARSER_ADD_INFO"))
        self.assertFalse(session.parser.analyzer_ast_instance.get_config("AST_ADD_INFO"))

    def test_match_group_resolves_the_parser_session(self) -> None:
        first = Session("group-first", "Many", SessionGroupProgram)
        first.init()
        first.add_group("types")
        first.add_keyword("alpha", group="types")
        first.migrate()

        second = Session("group-second", "Many", SessionGroupProgram)
        second.init()
        second.add_group("types")
        second.add_keyword("beta", group="types")
        second.migrate()

        first_result = first.parse(
            first.tokenize("alpha value", "group-first.gram"),
            "group-first.gram",
            trace="off",
        )
        second_result = second.parse(
            second.tokenize("beta value", "group-second.gram"),
            "group-second.gram",
            trace="off",
        )

        self.assertEqual(len(first_result), 1)
        self.assertEqual(len(second_result), 1)

    def test_word_group_manager_is_obsolete(self) -> None:
        with self.assertRaises(RuntimeError):
            WordGroupManager()


if __name__ == "__main__":
    unittest.main()
