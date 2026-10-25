"""
Tests for Token, Keyword, Symbol, and Group Matching Combinators.
"""
from __future__ import annotations

from gram import errors
from gram.core.ast.nodes import (
    ASTKeyword,
    ASTNode,
    Identifier,
    LiteralNumber,
    LiteralString,
    LiteralSymbol,
)
from gram.core.combinators.match import (
    MatchGroup,
    MatchKeyword,
    MatchSeqSymbol,
    MatchToken,
    generador_expr,
)
from gram.core.lexer.tokens import Token
from tests.combinators.base import CombinatorTestCase


class TestMatchCombinators(CombinatorTestCase):
    """
    Validates result shapes, operational variants, and raised/reported errors
    for lexical matching combinators.
    """

    # =========================================================================
    # 1. MatchToken
    # =========================================================================

    def test_match_token_shape_and_variants(self) -> None:
        """1. Result shape: returns an ASTNode wrapping the matched token."""
        # Variant A: Using Token enum
        m_ident = MatchToken(Token.IDENT)
        res, analyzer = self.parse_with_analyzer(m_ident, "my_var 123")
        self.assertIsInstance(res, ASTNode)
        self.assertIsInstance(res, Identifier)
        self.assertEqual(res.token.value, "my_var")
        self.assertEqual(analyzer.parser.pos, 1)

        # Variant B: Using string name identifier
        m_num = MatchToken("NUMBER")
        res2, analyzer2 = self.parse_with_analyzer(m_num, "999")
        self.assertIsInstance(res2, LiteralNumber)
        self.assertEqual(res2.token.value, 999)

        # Variant C: Mismatch returns None and preserves cursor
        res_fail, analyzer3 = self.parse_with_analyzer(m_ident, "123")
        self.assertIsNone(res_fail)
        self.assertEqual(analyzer3.parser.pos, 0)

        # Variant D: Rejection of keywords (must use MatchKeyword instead)
        res_kw, analyzer4 = self.parse_with_analyzer(m_ident, "int x")
        self.assertIsNone(res_kw)
        self.assertEqual(analyzer4.parser.pos, 0)

    def test_match_token_errors(self) -> None:
        """3. Errors that it raises or reports."""
        # Error during construction with invalid token string name
        with self.assertRaises(errors.GrammarError) as ctx:
            MatchToken("NON_EXISTENT_TOKEN_XYZ")
        self.assertEqual(ctx.exception.name, "InvalidTokenReference")

        # Error reported on empty token stream
        m_ident = MatchToken(Token.IDENT)
        res, analyzer = self.parse_with_analyzer(m_ident, [])
        self.assertIsNone(res)
        self.assertTrue(any(e.name == "EmptyTokenStream" for e in analyzer._errors))

    # =========================================================================
    # 2. MatchKeyword
    # =========================================================================

    def test_match_keyword_shape_and_variants(self) -> None:
        """1. Result shape & 2. Variants: MatchKeyword."""
        m_kw = MatchKeyword("int")

        # Variant A: Correct keyword matched
        res, analyzer = self.parse_with_analyzer(m_kw, "int foo")
        self.assertIsInstance(res, ASTKeyword)
        self.assertEqual(res.token.value, "int")
        self.assertEqual(analyzer.parser.pos, 1)

        # Variant B: Keyword value mismatch returns None
        m_return = MatchKeyword("return")
        res_mismatch, analyzer2 = self.parse_with_analyzer(m_return, "int foo")
        self.assertIsNone(res_mismatch)
        self.assertEqual(analyzer2.parser.pos, 0)

        # Variant C: Non-keyword token under cursor returns None
        res_ident, analyzer3 = self.parse_with_analyzer(m_kw, "variable_name")
        self.assertIsNone(res_ident)
        self.assertEqual(analyzer3.parser.pos, 0)

    def test_match_keyword_errors(self) -> None:
        """3. Errors: Empty stream reporting."""
        m_kw = MatchKeyword("int")
        res, analyzer = self.parse_with_analyzer(m_kw, [])
        self.assertIsNone(res)
        self.assertTrue(any(e.name == "EmptyTokenStream" for e in analyzer._errors))

    # =========================================================================
    # 3. MatchGroup
    # =========================================================================

    def test_match_group_shape_and_variants(self) -> None:
        """1. Result shape & 2. Variants: MatchGroup."""
        # Variant A: Any keyword in group
        m_types = MatchGroup("types")
        res, analyzer = self.parse_with_analyzer(m_types, "int x")
        self.assertIsInstance(res, ASTKeyword)
        self.assertEqual(res.token.value, "int")

        res_str, _ = self.parse_with_analyzer(m_types, "str y")
        self.assertEqual(res_str.token.value, "str")

        # Variant B: Filter mode 'allow'
        m_allow = MatchGroup("types", values=["int"], behavior_values="allow")
        res_allowed, _ = self.parse_with_analyzer(m_allow, "int a")
        self.assertIsNotNone(res_allowed)

        res_denied_by_allow, _ = self.parse_with_analyzer(m_allow, "str b")
        self.assertIsNone(res_denied_by_allow)

        # Variant C: Filter mode 'deny'
        m_deny = MatchGroup("types", values=["bool"], behavior_values="deny")
        res_denied, _ = self.parse_with_analyzer(m_deny, "bool c")
        self.assertIsNone(res_denied)

    def test_match_group_errors(self) -> None:
        """3. Errors: Non-existent WordGroup reports WordGroupNotFound."""
        m_bad = MatchGroup("UNKNOWN_GROUP_NAME")
        res, analyzer = self.parse_with_analyzer(m_bad, "int x")
        self.assertIsNone(res)
        self.assertTrue(any(e.name == "WordGroupNotFound" for e in analyzer._errors))

    # =========================================================================
    # 4. MatchSeqSymbol and generador_expr
    # =========================================================================

    def test_match_symbol_shape_and_variants(self) -> None:
        """1. Result shape & 2. Variants: MatchSeqSymbol."""
        # Variant A: Exact regex pattern
        sym = MatchSeqSymbol(pattern=r":")
        res, analyzer = self.parse_with_analyzer(sym, ":")
        self.assertIsInstance(res, LiteralSymbol)
        self.assertEqual(res.token.value, ":")

        # Variant B: Relabeling with CustomToken
        sym_custom = MatchSeqSymbol(pattern=r"==", custom_token_name="EQ_OP")
        res2, _ = self.parse_with_analyzer(sym_custom, "==")
        self.assertIsInstance(res2, LiteralSymbol)
        self.assertEqual(res2.token.value, "==")

        # Variant C: generador_expr utility
        pat = generador_expr("#", ["A", "F"], [0, 9])
        self.assertTrue(pat.endswith("[A-F0-9]"))
        sym_gen = MatchSeqSymbol(pattern=pat)
        res3, _ = self.parse_with_analyzer(sym_gen, "#A0")
        self.assertIsNone(res3)

    def test_generador_expr_error(self) -> None:
        """3. Errors: Invalid part in generador_expr raises GrammarError."""
        with self.assertRaises(errors.GrammarError) as ctx:
            generador_expr(12345)
        self.assertEqual(ctx.exception.name, "InvalidRegexGeneratorPart")

    # =========================================================================
    # 5. MatchSeqSymbol
    # =========================================================================

    def test_match_seq_symbol_shape_and_variants(self) -> None:
        """1. Result shape & 2. Variants: MatchSeqSymbol."""
        # MatchSeqSymbol with symbols list
        seq_sym = MatchSeqSymbol(symbols=["+", "="])
        res, analyzer = self.parse_with_analyzer(seq_sym, "+")
        self.assertIsInstance(res, LiteralSymbol)
        self.assertEqual(res.token.value, "+")
        self.assertEqual(analyzer.parser.pos, 1)

        # Non-matching symbol
        res_fail, analyzer2 = self.parse_with_analyzer(seq_sym, "-")
        self.assertIsNone(res_fail)
        self.assertEqual(analyzer2.parser.pos, 0)
