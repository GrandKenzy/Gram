"""
Tests for Reference (Ref), Item, Literal, Save, and Load Combinators.
"""
from __future__ import annotations

from gram import errors
from gram.core.ast.nodes import ASTNode, ASTRef, Identifier
from gram.core.combinators.base import RuleItem
from gram.core.combinators.item import Item, ItemNode, Literal, LiteralNode
from gram.core.combinators.load import Load
from gram.core.combinators.match import MatchToken
from gram.core.combinators.reference import Ref
from gram.core.combinators.save import Save
from gram.core.lexer.tokens import Token, TokenType
from tests.combinators.base import CombinatorTestCase


class SimpleNamedRule(RuleItem):
    """Rule with explicit nodeable=True."""
    nodeable = True
    entrypoint = MatchToken(Token.IDENT)


class AnonymousRule(RuleItem):
    """Rule without nodeable (returns raw AST node)."""
    nodeable = False
    entrypoint = MatchToken(Token.IDENT)


class EmptyGrammarRule(RuleItem):
    """Rule with no entrypoint defined."""
    entrypoint = None


class TestReferenceAndItems(CombinatorTestCase):
    """
    Validates result shape, operational variants, and errors for:
    - Ref (Rule referencing)
    - Item & Literal (Atomic token groups & literals)
    - Save & Load (Parser storage operations)
    """

    # =========================================================================
    # 1. Ref (Reference)
    # =========================================================================

    def test_ref_shape_and_variants(self) -> None:
        """1. Result shape: ASTRef when named/nodeable, raw node when anonymous."""
        # Variant A: Nodeable rule produces ASTRef
        ref_nodeable = Ref(SimpleNamedRule)
        res_ref, a1 = self.parse_with_analyzer(ref_nodeable, "my_identifier")
        self.assertIsInstance(res_ref, ASTRef)
        self.assertEqual(res_ref.name, "SimpleNamedRule")
        self.assertEqual(len(res_ref.nodes), 1)
        self.assertIsInstance(res_ref.nodes[0], Identifier)
        self.assertEqual(a1.parser.pos, 1)

        # Variant B: Explicit alias name overrides rule name
        ref_alias = Ref(SimpleNamedRule, name="CustomAlias")
        res_alias, a2 = self.parse_with_analyzer(ref_alias, "other_var")
        self.assertIsInstance(res_alias, ASTRef)
        self.assertEqual(res_alias.name, "CustomAlias")

        # Variant C: Anonymous rule produces raw inner node
        ref_anon = Ref(AnonymousRule)
        res_raw, a3 = self.parse_with_analyzer(ref_anon, "raw_var")
        self.assertIsInstance(res_raw, Identifier)
        self.assertEqual(res_raw.token.value, "raw_var")

    def test_ref_errors(self) -> None:
        """3. Errors: EmptyRuleReference reported when rule entrypoint is None."""
        ref_empty = Ref(EmptyGrammarRule)
        res, analyzer = self.parse_with_analyzer(ref_empty, "int x")
        self.assertIsNone(res)
        self.assertTrue(any(e.name == "EmptyRuleReference" for e in analyzer._errors))

    # =========================================================================
    # 2. Item & Literal
    # =========================================================================

    def test_item_shape_and_variants(self) -> None:
        """1. Result shape: ItemNode (subclass of list[TokenType])."""
        item_comb = Item(MatchToken(Token.IDENT), MatchToken("ASSIGN"))
        res, a1 = self.parse_with_analyzer(item_comb, "foo = 10")
        self.assertIsInstance(res, ItemNode)
        self.assertEqual(len(res), 2)
        self.assertEqual(a1.parser.pos, 2)

        # Partial failure rolls back
        res_fail, a2 = self.parse_with_analyzer(item_comb, "foo + 10")
        self.assertIsNone(res_fail)
        self.assertEqual(a2.parser.pos, 0)

    def test_literal_shape_and_variants(self) -> None:
        """1. Result shape: LiteralNode (subclass of list[TokenType])."""
        # Match specific literal value
        lit = Literal("custom_word")
        res, a1 = self.parse_with_analyzer(lit, "custom_word 99")
        self.assertIsInstance(res, LiteralNode)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0].value, "custom_word")
        self.assertEqual(a1.parser.pos, 1)

        # Mismatch returns None
        res_fail, a2 = self.parse_with_analyzer(lit, "different_word")
        self.assertIsNone(res_fail)
        self.assertEqual(a2.parser.pos, 0)

    # =========================================================================
    # 3. Save & Load
    # =========================================================================

    def test_save_and_load_shape_and_variants(self) -> None:
        """1. Result shape & 2. Variants: storage across Save and Load."""
        # Save current identifier under key 'my_saved_var'
        save_comb = Save("my_saved_var", MatchToken(Token.IDENT))
        res_save, analyzer = self.parse_with_analyzer(save_comb, "alpha alpha beta")
        self.assertIsInstance(res_save, Identifier)
        self.assertIn("my_saved_var", analyzer.parser.storage)
        self.assertEqual(analyzer.parser.storage["my_saved_var"].value, "alpha")

        # Load with mode='get': returns saved TokenType without moving cursor
        load_get = Load("my_saved_var", mode="get")
        res_get = analyzer.visitor(load_get)
        self.assertIsInstance(res_get, TokenType)
        self.assertEqual(res_get.value, "alpha")
        self.assertEqual(analyzer.parser.pos, 1)

        # Load with mode='match': asserts next token matches saved token and consumes it
        load_match = Load("my_saved_var", mode="match", matcher=MatchToken(Token.IDENT))
        res_match = analyzer.visitor(load_match)
        self.assertIsNotNone(res_match)
        self.assertEqual(analyzer.parser.pos, 2)

        # Load with mode='unmatch': asserts next token ('beta') differs from saved ('alpha')
        load_unmatch = Load("my_saved_var", mode="unmatch")
        res_unmatch = analyzer.visitor(load_unmatch)
        self.assertIsNotNone(res_unmatch)

    def test_load_errors(self) -> None:
        """3. Errors: StorageKeyNotFound reported when key is not in storage."""
        load_missing = Load("NON_EXISTENT_KEY")
        res, analyzer = self.parse_with_analyzer(load_missing, "test")
        self.assertIsNone(res)
        self.assertTrue(any(e.name == "StorageKeyNotFound" for e in analyzer._errors))
