"""
Aggressive stress tests and adversarial fuzzing for the Gram Lexer.
===================================================================
Tests scale, deep indentation hierarchies, malformed literal recovery,
operator maximal-munch collision, non-crashing fuzzing, and telemetry isolation.
"""
from __future__ import annotations

import random
import unittest
from unittest.mock import patch

from gram import config, errors
from gram.core.lexer import (
    Lexer,
    LexerState,
    Token,
    TokenType,
    flags,
    tokens as lexer_tokens,
    words,
)
from gram.core.lexer.tokens import disabled_symbol, insert_symbol


class TestLexerStress(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = patch.dict(
            config.__dict__,
            {
                "LEXER_COMMENT_TOKEN": "#",
                "LEXER_BLOCK_COMMENT_TOKEN": "/*",
                "LEXER_SUPPORT_BLOCK_COMMENTS": True,
                "LEXER_SUPPORT_DOCSTRINGS": True,
                "LEXER_SUPPORT_PREFIXED_STRINGS": True,
                "LEXER_SUPPORT_LEADING_DOT_NUMBERS": True,
                "LEXER_TAB_WIDTH": 4,
                "LEXER_INDENT_STYLE": "spaces",
                "TOKEN_BOOL_TRUE": "true",
                "TOKEN_BOOL_FALSE": "false",
                "TOKEN_NULL": "null",
                "SUPPORT_INDENT": True,
                "SUPPORT_TRIPLE_DOT": True,
                "LEXER_IGNORE_EMPTY_LINES": True,
                "LEXER_IGNORE_NEWLINES": True,
                "LEXER_SAVE_COMMENTS": True,
                "LEXER_ADD_INFO": False,
                "INFO_GENERATE_LOGFILE": False,
                "INFO_GENERATE_LOGFILE_ON_ERROR": False,
                "ERROR_EXIT_ON_ERROR": False,
                "ERROR_HIDE_CONSOLE": True,
            },
        )
        self.keywords = patch.dict(words.MAP_KEYWORDS, clear=True)
        self.groups = patch.dict(words._GLOBAL_GROUPS, clear=True)
        self.active_lexer = patch.object(LexerState, "_active_instance", None)
        for patcher in (self.settings, self.keywords, self.groups, self.active_lexer):
            patcher.start()
            self.addCleanup(patcher.stop)

        # Baseline keywords
        words.add_keyword("let")
        words.add_keyword("fn")
        words.add_keyword("if")
        words.add_keyword("else")
        words.add_keyword("return")

    # ==========================================================================
    # 1. MASSIVE CORPORA & SCALE STRESS
    # ==========================================================================

    def test_massive_mixed_corpus_scale(self) -> None:
        """Tokenize thousands of lines with heterogeneous syntax without leaks."""
        rng = random.Random(42)
        lines: list[str] = []
        expected_token_types: list[Token] = []

        for i in range(1000):
            var_name = f"var_{i}"
            num_val = i * 3
            # Line format: let var_i = num; // comment
            line = f"let {var_name} = {num_val}; # comment {i}"
            lines.append(line)
            expected_token_types.extend(
                [Token.KEYWORD, Token.IDENT, Token.ASSIGN, Token.NUMBER, Token.SEMICOLON]
            )

        source = "\n".join(lines)
        lexer = Lexer(source)
        result = lexer.process()

        # Last token is always EOF
        self.assertEqual(result[-1].token, Token.EOF)
        emitted_types = [t.token for t in result[:-1]]
        self.assertEqual(len(emitted_types), len(expected_token_types))
        self.assertEqual(emitted_types, expected_token_types)
        self.assertEqual(len(lexer.comments), 1000)

    def test_giant_single_line_many_tokens(self) -> None:
        """Process a single line with thousands of tokens without recursion limit."""
        token_count = 5000
        source = " ".join(f"x{i} + {i} *" for i in range(token_count))
        lexer = Lexer(source)
        result = lexer.process()

        # Each iteration produces: IDENT, PLUS, NUMBER, STAR
        expected_count = token_count * 4 + 1  # plus EOF
        self.assertEqual(len(result), expected_count)
        self.assertEqual(result[-1].token, Token.EOF)

        # Verify coordinates strictly increment on the same line
        prev_col = -1
        for tok in result[:-1]:
            self.assertEqual(tok.line, 1)
            self.assertGreater(tok.col, prev_col)
            prev_col = tok.col

    def test_giant_single_string_literal(self) -> None:
        """Scan a very large string literal (50,000 characters) with escapes."""
        inner_content = "abcdefghij\\n\\t\\\"'12345!@#$%^" * 2000
        source = f'"{inner_content}"'
        lexer = Lexer(source)
        result = lexer.process()

        self.assertEqual(len(result), 2)  # STRING + EOF
        self.assertEqual(result[0].token, Token.STRING)
        self.assertTrue(result[0].flags & flags.SIMPLE_QUOTE)
        self.assertIn("\n", result[0].value)
        self.assertIn("\t", result[0].value)

    # ==========================================================================
    # 2. EXTREME INDENTATION & DEEP NESTING
    # ==========================================================================

    def test_deep_indentation_pyramid(self) -> None:
        """Nest indentation 100 levels deep, then suddenly dedent to zero."""
        depth = 100
        lines = []
        for i in range(depth):
            indent_str = "    " * i
            lines.append(f"{indent_str}let x{i} = {i}")
        # Final line with 0 indentation
        lines.append("return")

        source = "\n".join(lines)
        lexer = Lexer(source)
        result = lexer.process()

        indents_emitted = sum(1 for t in result if t.token == Token.INDENT)
        dedents_emitted = sum(1 for t in result if t.token == Token.DEDENT)

        self.assertEqual(indents_emitted, depth - 1)
        self.assertEqual(dedents_emitted, depth - 1)
        self.assertEqual(lexer.indents, [0])

    def test_ragged_dedent_jumps(self) -> None:
        """Dedent across arbitrary levels (e.g. 50 -> 30 -> 10 -> 0)."""
        source = (
            "let x = 0\n"
            "    let x = 1\n"
            "        let x = 2\n"
            "            let x = 3\n"
            "                let x = 4\n"
            "        let x = 5\n"       # Dedents from level 4 to level 2 (2 DEDENTs)
            "    let x = 6\n"           # Dedents from level 2 to level 1 (1 DEDENT)
            "let x = 7"                 # Dedents from level 1 to level 0 (1 DEDENT)
        )
        lexer = Lexer(source)
        result = lexer.process()

        tokens_kinds = [t.token for t in result]
        indents_count = tokens_kinds.count(Token.INDENT)
        dedents_count = tokens_kinds.count(Token.DEDENT)

        self.assertEqual(indents_count, 4)
        self.assertEqual(dedents_count, 4)
        self.assertEqual(lexer.indents, [0])

    def test_mixed_indentation_policy_tab_stops(self) -> None:
        """Verify 'mixed' indentation aligns tab stops correctly."""
        config.LEXER_INDENT_STYLE = "mixed"
        config.LEXER_TAB_WIDTH = 4

        # Line 0: level 0
        # Line 1: ' \t' -> 1 space + tab to next multiple of 4 = 4 columns (1 INDENT)
        # Line 2: '   \t' -> 3 spaces + tab to next multiple of 4 = 4 columns (SAME LEVEL, 0 INDENT)
        # Line 3: '\t\t' -> 8 columns (1 INDENT)
        source = (
            "let a = 0\n"
            " \tlet b = 1\n"
            "   \tlet c = 2\n"
            "\t\tlet d = 3"
        )
        lexer = Lexer(source)
        result = lexer.process()

        indents = [t.value for t in result if t.token == Token.INDENT]
        self.assertEqual(indents, [4, 8])

    def test_invalid_dedent_reports_diagnostics_without_crashing(self) -> None:
        """Dedent that does not match any previous level reports error cleanly."""
        source = (
            "let a = 0\n"
            "        let b = 1\n"    # level 8
            "    let c = 2\n"        # level 4 -> VALID dedent
            "   let d = 3"           # level 3 -> MISMATCH (does not match 0, 4, 8)
        )
        lexer = Lexer(source)
        result = lexer.process()

        self.assertTrue(any(f.code == errors.LEXER_INDENTATION_MISMATCH for f in lexer._errors))
        self.assertEqual(result[-1].token, Token.EOF)

    # ==========================================================================
    # 3. ADVERSARIAL INPUTS & FUZZING RECOVERY
    # ==========================================================================

    def test_unterminated_strings_recovery(self) -> None:
        """Verify all varieties of unterminated strings recover cleanly to Token.ERROR."""
        cases = [
            '"unterminated at EOL',
            "'unterminated single quote at EOL",
            '"""unterminated docstring at EOF',
            "'''unterminated docstring at EOF",
            'L"unterminated prefixed string',
            'u8"unterminated utf8 string',
            '"escaped backslash at EOL\\',
        ]
        for idx, case in enumerate(cases):
            with self.subTest(case=case):
                lexer = Lexer(case)
                result = lexer.process()
                self.assertTrue(
                    any(t.token == Token.ERROR for t in result),
                    f"Case {idx} did not emit Token.ERROR: {case}",
                )
                self.assertEqual(result[-1].token, Token.EOF)
                self.assertTrue(len(lexer._errors) > 0)

    def test_malformed_numeric_literals_recovery(self) -> None:
        """Adversarial numeric literals recover to Token.ERROR without infinite loop."""
        malformed = [
            "123_456_",      # Trailing underscore
            "1__2",          # Consecutive underscores
            "0x_12",         # Underscore after radix prefix
            "0b",            # Radix prefix with no digits
            "0o",            # Octal prefix with no digits
            "0x",            # Hex prefix with no digits
            "0b10201",       # Invalid binary digit (2)
            "0o789",         # Invalid octal digit (8, 9)
            "1.2.3",         # Multiple dots
            "1e",            # Exponent with no digits
            "1e+",           # Exponent with only sign
            "0x1.2p",        # Hex float without exponent digits
            "0x1.2p+",       # Hex float with sign but no digits
            "123xyz",        # Malformed alphanumeric suffix
        ]
        for lit in malformed:
            with self.subTest(lit=lit):
                source = f"let x = {lit};"
                lexer = Lexer(source)
                result = lexer.process()

                self.assertTrue(
                    any(t.token == Token.ERROR for t in result),
                    f"Literal {lit!r} should produce Token.ERROR",
                )
                self.assertEqual(result[-1].token, Token.EOF)

    def test_unterminated_block_comment_does_not_hang(self) -> None:
        """Unterminated block comment /* consumes to EOF and terminates."""
        source = "let x = 10; /* unclosed block comment started here"
        lexer = Lexer(source)
        result = lexer.process()

        self.assertEqual(result[-1].token, Token.EOF)
        # Block comments are stored in lexer.comments; unclosed comment reports error
        self.assertTrue(any(t.token == Token.ERROR for t in lexer.comments))
        self.assertTrue(any(e.code == errors.LEXER_UNCLOSED_STRING for e in lexer._errors))

    def test_exotic_unicode_characters(self) -> None:
        """Test Unicode operators, mathematical symbols, and non-ASCII characters."""
        source = "√ x ∧ y ∨ ¬ z ∞ ° § • ... ·"
        lexer = Lexer(source)
        result = lexer.process()

        tokens_kinds = [t.token for t in result]
        expected = [
            Token.SQRT,
            Token.IDENT,
            Token.LOGIC_AND,
            Token.IDENT,
            Token.LOGIC_OR,
            Token.LOGIC_NOT,
            Token.IDENT,
            Token.INFINITY,
            Token.DEGREE,
            Token.SECTION,
            Token.BULLET,
            Token.THREE_DOTS,
            Token.MIDDLE_DOT,
            Token.EOF,
        ]
        self.assertEqual(tokens_kinds, expected)

    # ==========================================================================
    # 4. OPERATOR MAXIMAL-MUNCH & COMBINATORIAL STRESS
    # ==========================================================================

    def test_dense_operator_chains(self) -> None:
        """Verify maximal munch decomposes dense operator chains deterministically."""
        # '+++++' -> '++' (INCREMENT), '++' (INCREMENT), '+' (PLUS)
        # '==='   -> '==' (EQUAL), '=' (ASSIGN)
        # '**='   -> '**=' (POW_ASSIGN)
        # '->->'  -> '->' (ARROW), '->' (ARROW)
        # ':=:='  -> ':=' (WALRUS), ':=' (WALRUS)
        # '<<=<<' -> '<<=' (SHL_ASSIGN), '<<' (SHL)
        source = "+++++ === **= ->-> :=:= <<=<<"
        lexer = Lexer(source)
        result = lexer.process()

        tokens_kinds = [t.token for t in result[:-1]]
        expected = [
            Token.INCREMENT, Token.INCREMENT, Token.PLUS,
            Token.EQUAL, Token.ASSIGN,
            Token.POW_ASSIGN,
            Token.ARROW, Token.ARROW,
            Token.WALRUS, Token.WALRUS,
            Token.SHL_ASSIGN, Token.SHL,
        ]
        self.assertEqual(tokens_kinds, expected)

    def test_dynamic_symbol_churn(self) -> None:
        """Insert and remove dozens of custom symbols under rapid churn."""
        original_symbols = list(lexer_tokens.get_sorted_symbols())
        custom_symbols = [f"?{i}?" for i in range(50)]

        try:
            # Register all 50 custom symbols
            for sym in custom_symbols:
                insert_symbol(sym, Token.QUESTION)

            # Test scanning a stream using the custom symbols
            source = " ".join(custom_symbols)
            lexer = Lexer(source)
            result = lexer.process()

            self.assertEqual(len(result), 51)  # 50 QUESTION + 1 EOF
            self.assertTrue(all(t.token == Token.QUESTION for t in result[:-1]))

        finally:
            # Clean up all custom symbols
            for sym in custom_symbols:
                disabled_symbol(sym)

            # Check that symbols list reverted to exact original length
            self.assertEqual(lexer_tokens.get_sorted_symbols(), original_symbols)

    # ==========================================================================
    # 5. PRECEDENCE & CASE DISCRIMINATION
    # ==========================================================================

    def test_word_classification_precedence(self) -> None:
        """Verify BOOL -> NULL -> KEYWORD -> IDENT precedence under all casings."""
        words.add_keyword("TRUE", allow_override=True)
        words.add_keyword("NULL", allow_override=True)
        words.add_keyword("match", allow_override=True)

        # "true" (BOOL True)
        # "True" (BOOL True)
        # "TRUE" (BOOL True - boolean takes precedence over registered keyword "TRUE")
        # "true_val" (IDENT)
        # "null" (NULL None)
        # "Null" (NULL None)
        # "NULL" (NULL None - null takes precedence over registered keyword "NULL")
        # "nullptr" (IDENT)
        # "match" (KEYWORD)
        # "Match" (IDENT - keywords are case-sensitive)
        source = "true True TRUE true_val null Null NULL nullptr match Match"
        lexer = Lexer(source)
        result = lexer.process()

        expected = [
            (Token.BOOL, True),
            (Token.BOOL, True),
            (Token.BOOL, True),
            (Token.IDENT, "true_val"),
            (Token.NULL, None),
            (Token.NULL, None),
            (Token.NULL, None),
            (Token.IDENT, "nullptr"),
            (Token.KEYWORD, "match"),
            (Token.IDENT, "Match"),
            (Token.EOF, None),
        ]
        self.assertEqual([(t.token, t.value) for t in result], expected)

    # ==========================================================================
    # 6. ADVERSARIAL RANDOM FUZZING & EXTREME BOUNDS
    # ==========================================================================

    def test_random_character_fuzzing_terminates_safely(self) -> None:
        """Fuzz with pseudo-random sequences of characters; must never loop or raise unhandled exceptions."""
        rng = random.Random(1337)
        # Alphabet includes quotes, escapes, operators, letters, numbers, unicode, whitespace
        alphabet = "abcdef1230._+-*/%&|^=!:;~@#$?()[]{} \t\n\r\"'\\«»§•°√∞∧∨¬"
        
        for trial in range(50):
            length = rng.randint(20, 150)
            fuzzed_source = "".join(rng.choice(alphabet) for _ in range(length))
            lexer = Lexer(fuzzed_source)
            result = lexer.process()
            
            # Must always finish at EOF without infinite loop
            self.assertTrue(len(result) >= 1)
            self.assertEqual(result[-1].token, Token.EOF)

    def test_extreme_number_digit_sizes(self) -> None:
        """Verify 500-digit integers and subnormal floats tokenize without precision overflow crash."""
        huge_int_str = "9" * 500
        tiny_float_str = "1.0e-300"
        hex_float_str = "0x1.0p-100"
        source = f"{huge_int_str} {tiny_float_str} {hex_float_str}"

        lexer = Lexer(source)
        result = lexer.process()

        self.assertEqual(len(result), 4)  # 3 numbers + 1 EOF
        self.assertEqual(result[0].token, Token.NUMBER)
        self.assertEqual(result[0].value, int(huge_int_str))
        self.assertEqual(result[1].token, Token.DECIMAL)
        self.assertAlmostEqual(result[1].value, 1.0e-300)
        self.assertEqual(result[2].token, Token.DECIMAL)

    def test_token_stream_cursor_stress(self) -> None:
        """Rapid traversal, peeking, and selective consumption across 5000 tokens."""
        count = 5000
        source = " ".join(f"item_{i} = {i};" for i in range(count))
        stream = Lexer(source).stream()

        # Check total tokens (4 per statement + 1 EOF = 20001)
        self.assertEqual(len(stream), count * 4 + 1)
        
        # Advance 1000 tokens
        for _ in range(1000):
            tok = stream.advance()
            self.assertIsNotNone(tok)
        
        self.assertEqual(stream.position, 1000)
        
        # Rewind 500
        stream.rewind(500)
        self.assertEqual(stream.position, 500)
        
        # Match pattern
        matched = stream.check(Token.IDENT, Token.KEYWORD)
        self.assertTrue(matched)
        
        # Reset
        stream.reset()
        self.assertEqual(stream.position, 0)
        self.assertEqual(stream.current().value, "item_0")
        
        # Filter stream
        filtered = stream.filter_tokens(Token.SEMICOLON, Token.ASSIGN)
        # Should now only have IDENT and NUMBER + EOF
        self.assertEqual(len(filtered), count * 2 + 1)


if __name__ == "__main__":
    unittest.main()
