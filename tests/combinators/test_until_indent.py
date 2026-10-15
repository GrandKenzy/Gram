"""
Unit Tests for UntilIndent Combinator (`tests.combinators.test_until_indent`).
=============================================================================
Validates operational variants, relative and absolute modes, target consumption,
and error conditions for `UntilIndent`.
"""
import unittest

from gram import errors
from gram.core.combinators.match import MatchKeyword, MatchToken
from gram.core.combinators.sequence import Seq
from gram.core.combinators.until_indent import UntilIndent
from gram.core.lexer import Token
from tests.combinators.base import CombinatorTestCase


class TestUntilIndent(CombinatorTestCase):
    """
    Validates result shape, operational variants, and errors for:
    - UntilIndent("back")  (Relative dedentation)
    - UntilIndent("front") (Relative indentation)
    - UntilIndent(N)       (Absolute indentation level)
    """

    # =========================================================================
    # 1. UntilIndent("back")
    # =========================================================================

    def test_until_indent_back_leave_target(self) -> None:
        """Stops before DEDENT when consume_target=False (default)."""
        code = (
            "block:\n"
            "    int a = 10\n"
            "    return a\n"
            "int x = 20"
        )
        # Parse block header and INDENT first
        header = Seq(
            MatchKeyword("block"),
            MatchToken("COLON"),
            MatchToken("INDENT"),
        )
        _, analyzer = self.parse_with_analyzer(header, code)
        self.assertEqual(analyzer.parser.pos, 3)

        # Now UntilIndent('back') should consume all statements inside the block
        # and stop right before DEDENT (without consuming it)
        until_back = UntilIndent("back", consume_target=False)
        collected = analyzer.visitor(until_back)

        self.assertIsInstance(collected, list)
        self.assertGreater(len(collected), 0)
        # Next token in stream must still be DEDENT
        next_tok = analyzer.parser.peek()
        self.assertIsNotNone(next_tok)
        self.assertEqual(next_tok.token, Token.DEDENT)

    def test_until_indent_back_consume_target(self) -> None:
        """Consumes DEDENT when consume_target=True."""
        code = (
            "block:\n"
            "    int a = 10\n"
            "int x = 20"
        )
        header = Seq(
            MatchKeyword("block"),
            MatchToken("COLON"),
            MatchToken("INDENT"),
        )
        _, analyzer = self.parse_with_analyzer(header, code)

        until_back = UntilIndent("back", consume_target=True)
        collected = analyzer.visitor(until_back)

        self.assertIsInstance(collected, list)
        # Cursor should now be past DEDENT, pointing to 'int' at level 0
        next_tok = analyzer.parser.peek()
        self.assertIsNotNone(next_tok)
        self.assertEqual(next_tok.token, Token.KEYWORD)
        self.assertEqual(next_tok.value, "int")

    def test_until_indent_back_immediate_dedent(self) -> None:
        """Returns empty list immediately if already positioned before DEDENT."""
        code = (
            "block:\n"
            "    int a = 10\n"
            "int x = 20"
        )
        header = Seq(
            MatchKeyword("block"),
            MatchToken("COLON"),
            MatchToken("INDENT"),
            UntilIndent("back", consume_target=False),
        )
        _, analyzer = self.parse_with_analyzer(header, code)

        # Now cursor is directly before DEDENT
        self.assertEqual(analyzer.parser.peek().token, Token.DEDENT)
        # Calling UntilIndent('back') again should return [] without consuming DEDENT
        second_call = analyzer.visitor(UntilIndent("back", consume_target=False))
        self.assertEqual(second_call, [])
        self.assertEqual(analyzer.parser.peek().token, Token.DEDENT)

    def test_until_indent_nested_dedent(self) -> None:
        """Does not stop at inner DEDENT if level does not drop below initial level."""
        code = (
            "block:\n"
            "    if true:\n"
            "        int inner = 1\n"
            "    int outer = 2\n"
            "int x = 3"
        )
        header = Seq(
            MatchKeyword("block"),
            MatchToken("COLON"),
            MatchToken("INDENT"),
        )
        _, analyzer = self.parse_with_analyzer(header, code)

        # initial_level is 4. Inner block goes to 8 then dedents to 4.
        # UntilIndent('back') should consume the inner block and outer stmt,
        # only stopping when dedenting below 4 (to level 0).
        until_back = UntilIndent("back", consume_target=False)
        collected = analyzer.visitor(until_back)

        self.assertIsInstance(collected, list)
        self.assertEqual(analyzer.parser.peek().token, Token.DEDENT)
        self.assertEqual(analyzer.parser.peek().value, 0)

    # =========================================================================
    # 2. UntilIndent("front")
    # =========================================================================

    def test_until_indent_front(self) -> None:
        """Consumes tokens until encountering an INDENT token."""
        code = (
            "block:\n"
            "    int a = 10\n"
        )
        analyzer = self.create_analyzer(code)
        # From pos 0 (level 0), consume until indentation ('front')
        until_front = UntilIndent("front", consume_target=False)
        collected = analyzer.visitor(until_front)

        self.assertIsInstance(collected, list)
        # Should have consumed 'block' and ':'
        self.assertEqual(len(collected), 2)
        # Next unconsumed token should be INDENT
        self.assertEqual(analyzer.parser.peek().token, Token.INDENT)

    # =========================================================================
    # 3. UntilIndent(level: int)
    # =========================================================================

    def test_until_indent_level_zero(self) -> None:
        """Consumes until level 0 is reached."""
        code = (
            "block:\n"
            "    return 10\n"
            "int x = 20"
        )
        header = Seq(
            MatchKeyword("block"),
            MatchToken("COLON"),
            MatchToken("INDENT"),
        )
        _, analyzer = self.parse_with_analyzer(header, code)

        until_zero = UntilIndent(0, consume_target=False)
        collected = analyzer.visitor(until_zero)

        self.assertIsInstance(collected, list)
        self.assertEqual(analyzer.parser.peek().token, Token.DEDENT)
        self.assertEqual(analyzer.parser.peek().value, 0)

    # =========================================================================
    # 4. allow_eof and max_tokens
    # =========================================================================

    def test_until_indent_allow_eof(self) -> None:
        """Succeeds at EOF when allow_eof=True."""
        code = "int a = 10"
        analyzer = self.create_analyzer(code)

        until_front = UntilIndent("front", allow_eof=True)
        res = analyzer.visitor(until_front)
        self.assertIsInstance(res, list)
        self.assertEqual(len(res), 4)

    def test_until_indent_not_found_error(self) -> None:
        """Reports UntilIndentTargetNotFound when target is not reached."""
        code = "int a = 10"
        analyzer = self.create_analyzer(code)

        until_front = UntilIndent("front", allow_eof=False)
        res = analyzer.visitor(until_front)
        self.assertIsNone(res)
        self.assertTrue(
            any(e.name == "UntilIndentTargetNotFound" for e in analyzer._errors)
        )

    # =========================================================================
    # 5. Constructor Validation Errors
    # =========================================================================

    def test_invalid_target_errors(self) -> None:
        """Raises GrammarError on invalid target specifications."""
        with self.assertRaises(errors.GrammarError) as ctx1:
            UntilIndent("sideways")
        self.assertEqual(ctx1.exception.name, "InvalidUntilIndentTarget")

        with self.assertRaises(errors.GrammarError) as ctx2:
            UntilIndent(-5)
        self.assertEqual(ctx2.exception.name, "InvalidUntilIndentTarget")

        with self.assertRaises(errors.GrammarError) as ctx3:
            UntilIndent([0])  # type: ignore
        self.assertEqual(ctx3.exception.name, "InvalidUntilIndentTarget")


if __name__ == "__main__":
    unittest.main()
