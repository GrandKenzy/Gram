"""
Tests for Lookahead and Control Combinators (Peek, Not, Skip, Tag, Tokenize, ErrorCombinator).
"""
from __future__ import annotations

from gram import errors
from gram.core.combinators.error_combinator import ErrorCombinator
from gram.core.combinators.match import MatchKeyword, MatchToken
from gram.core.combinators.negation import Not
from gram.core.combinators.peek import Peek
from gram.core.combinators.signals import SkipFlowSignal
from gram.core.combinators.skip import Skip
from gram.core.combinators.tag import Tag
from gram.core.combinators.tokenize import Tokenize
from gram.core.lexer.tokens import CustomToken, Token, TokenType
from tests.combinators.base import CombinatorTestCase


class TestLookaheadAndControl(CombinatorTestCase):
    """
    Validates result shape, operational variants, and errors for:
    - Peek (positive lookahead)
    - Not (negative lookahead)
    - Skip (control flow signal)
    - Tag (semantic metadata)
    - Tokenize (composite lexical grouping)
    - ErrorCombinator (error capture and recovery)
    """

    # =========================================================================
    # 1. Peek (Positive Lookahead)
    # =========================================================================

    def test_peek_shape_and_variants(self) -> None:
        """1. Result shape: returns [] without consuming tokens."""
        peek_kw = Peek(MatchKeyword("int"))

        # Variant A: Lookahead matches -> returns [], pos stays 0
        res, a1 = self.parse_with_analyzer(peek_kw, "int my_var")
        self.assertIsInstance(res, list)
        self.assertEqual(len(res), 0)
        self.assertEqual(a1.parser.pos, 0)

        # Variant B: Lookahead mismatch -> returns None, pos stays 0
        res_fail, a2 = self.parse_with_analyzer(peek_kw, "str my_var")
        self.assertIsNone(res_fail)
        self.assertEqual(a2.parser.pos, 0)

    # =========================================================================
    # 2. Not (Negative Lookahead)
    # =========================================================================

    def test_not_shape_and_variants(self) -> None:
        """1. Result shape: returns [] when sub-combinator does NOT match."""
        not_int = Not(MatchKeyword("int"))

        # Variant A: Sub-combinator fails -> Not succeeds, returns [], pos stays 0
        res_succeed, a1 = self.parse_with_analyzer(not_int, "str my_var")
        self.assertIsInstance(res_succeed, list)
        self.assertEqual(len(res_succeed), 0)
        self.assertEqual(a1.parser.pos, 0)

        # Variant B: Sub-combinator matches -> Not fails, returns None, pos stays 0
        res_fail, a2 = self.parse_with_analyzer(not_int, "int my_var")
        self.assertIsNone(res_fail)
        self.assertEqual(a2.parser.pos, 0)

    # =========================================================================
    # 3. Skip (Flow Control Signal)
    # =========================================================================

    def test_skip_shape_and_variants(self) -> None:
        """1. Result shape & Variants: raises the specified ControlFlowSignal."""
        skip = Skip(SkipFlowSignal)
        analyzer = self.create_analyzer("int x")
        with self.assertRaises(SkipFlowSignal):
            analyzer.visitor(skip)

    # =========================================================================
    # 4. Tag (Token Semantic Tagging)
    # =========================================================================

    def test_tag_shape_and_variants(self) -> None:
        """1. Result shape: returns current TokenType without consuming it."""
        # Variant A: Add tag
        tag_add = Tag.add("statement_start")
        res, a1 = self.parse_with_analyzer(tag_add, "int x")
        self.assertIsInstance(res, TokenType)
        self.assertIn("statement_start", a1.parser.tk_tags.get(0, frozenset()))
        self.assertEqual(a1.parser.pos, 0)  # zero-width

        # Variant B: Assert tag exists
        tag_check = Tag.exists("statement_start")
        res_check = a1.visitor(tag_check)
        self.assertIsNotNone(res_check)

        # Variant C: Assert tag not exists
        tag_missing = Tag.not_exists("unknown_tag")
        res_un = a1.visitor(tag_missing)
        self.assertIsNotNone(res_un)

        # Variant D: Remove tag
        tag_rm = Tag.remove("statement_start")
        a1.visitor(tag_rm)
        self.assertNotIn("statement_start", a1.parser.tk_tags.get(0, frozenset()))

    def test_tag_errors(self) -> None:
        """3. Errors: Tag.exists on untagged token reports RequiredTagMissing."""
        tag_check = Tag.exists("missing_tag")
        res, a = self.parse_with_analyzer(tag_check, "int x")
        self.assertIsNone(res)
        self.assertTrue(any(e.name == "RequiredTagMissing" for e in a._errors))

    # =========================================================================
    # 5. Tokenize (Composite Lexical Fusing)
    # =========================================================================

    def test_tokenize_shape_and_variants(self) -> None:
        """1. Result shape: returns a single TokenType backed by a CustomToken."""
        # Fuses 2 identifier tokens into a single composite token
        tok_comb = Tokenize(
            MatchToken(Token.IDENT),
            MatchToken(Token.IDENT),
            name="DOUBLE_IDENT",
            join_char="_",
        )
        res, a1 = self.parse_with_analyzer(tok_comb, "first second")
        self.assertIsInstance(res, TokenType)
        self.assertIsInstance(res.token, CustomToken)
        self.assertEqual(res.token.name, "DOUBLE_IDENT")
        self.assertEqual(res.value, "first_second")
        self.assertEqual(a1.parser.pos, 2)

    def test_tokenize_errors(self) -> None:
        """3. Errors: EmptyTokenizeCombinators raised on empty initialization."""
        with self.assertRaises(errors.GrammarError) as ctx:
            Tokenize()
        self.assertEqual(ctx.exception.name, "EmptyTokenizeCombinators")

    # =========================================================================
    # 6. ErrorCombinator
    # =========================================================================

    def test_error_combinator_shape_and_variants(self) -> None:
        """1. Result shape: list[errors.Error] capturing errors from the stack."""
        err_comb = ErrorCombinator(length=0)  # capture all

        # Simulate a parse failure that stages an error
        analyzer = self.create_analyzer("str")
        analyzer.visitor(MatchKeyword("int"))  # reports UnexpectedNonKeywordToken / TokenMismatch
        self.assertTrue(len(analyzer._errors) > 0)

        # Capture errors using ErrorCombinator
        caught = analyzer.visitor(err_comb)
        self.assertIsInstance(caught, list)
        self.assertTrue(len(caught) > 0)
        self.assertIsInstance(caught[0], errors.Error)

    def test_error_combinator_errors(self) -> None:
        """3. Errors: NoErrorsToCatch reported when error stack is empty."""
        err_comb = ErrorCombinator(length=1)
        res, analyzer = self.parse_with_analyzer(err_comb, "int")
        self.assertIsNone(res)
        self.assertTrue(any(e.name == "NoErrorsToCatch" for e in analyzer._errors))
