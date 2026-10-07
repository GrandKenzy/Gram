"""
Pruebas Unitarias del Catálogo de Combinadores (`gram.tests.test_combinators`).
==============================================================================
Valida exhaustivamente todos los componentes de `gram.core.combinators`:
  1. Matchers atómicos: MatchToken, MatchKeyword, MatchGroup, MatchSymbol/MatchSeqSymbol, generador_expr.
  2. Item & Literal: ItemResult, secuencia atómica Item, validación de primitivos con Literal.
  3. Secuencia (Seq): consumo ordenado, backtracking atómico completo, operador `+`.
  4. Alternativas (Alt): selección priorizada, backtracking entre ramas, operador `|`, CutFlowSignal.
  5. Opcional (Opt): OptResult, desempaquetado (unwrap), preservación de cursor si no coincide.
  6. Repeticiones (Many & Some): 0..n y 1..n, tolerancia a fallos, señales de ruptura (BreakFlowSignal).
  7. Separator (Sep): secuencias delimitadas, trailing separators, restricciones min/max, SeparatorResult.
  8. Enclosed (Bracketed): delimitadores emparejados, integración con bracket_context (supresión de saltos).
  9. Reference (Ref): resolución dinámica de reglas por nombre y clase, gramáticas recursivas.
  10. Tokenize: síntesis de secuencias de tokens en un único CustomToken.
  11. Mods & AdditionalStack: clasificación hardcoded vs custom, registro dinámico y despacho.
"""
from __future__ import annotations

import unittest

from gram import config, errors
from gram.core.combinators import (
    Alt,
    AnyGrammar,
    Bracketed,
    CombinatorAdditionalStack,
    ControlFlowSignal,
    CutFlowSignal,
    Enclosed,
    Item,
    ItemResult,
    Literal,
    Many,
    MatchGroup,
    MatchKeyword,
    MatchSeqSymbol,
    MatchSymbol,
    MatchToken,
    Opt,
    OptResult,
    Ref,
    RuleItem,
    Sep,
    Separator,
    SeparatorResult,
    Seq,
    Some,
    Tokenize,
    custom_mod,
    generador_expr,
    is_custom_mod,
    is_hardcoded_mod,
    register_custom_mod,
)
from gram.core.lexer import Token, TokenType, words
from gram.core.parser import Parser
from gram.utilities.error import GrammarError, ParserError


class BaseCombinatorTestCase(unittest.TestCase):
    """Caso base para pruebas de combinadores con configuración aislada."""

    def setUp(self) -> None:
        self.old_hide_console = config.ERROR_HIDE_CONSOLE
        self.old_exit_on_error = config.ERROR_EXIT_ON_ERROR
        config.ERROR_HIDE_CONSOLE = True
        config.ERROR_EXIT_ON_ERROR = False
        words.clear_all()
        CombinatorAdditionalStack.clear()

    def tearDown(self) -> None:
        config.ERROR_HIDE_CONSOLE = self.old_hide_console
        config.ERROR_EXIT_ON_ERROR = self.old_exit_on_error
        words.clear_all()
        CombinatorAdditionalStack.clear()

    def make_token(
        self,
        token: Token | str,
        value: Any = "",
        line: int = 1,
        col: int = 0,
    ) -> TokenType:
        """Crea una instancia concreta de TokenType."""
        tok_type = token if isinstance(token, Token) else Token.from_string(token) or Token.IDENT
        return TokenType(token=tok_type, value=value, line=line, col=col)

    def make_parser(self, *tokens: TokenType) -> Parser:
        """Crea un Parser con los tokens dados."""
        return Parser(tokens=list(tokens))


class TestMatchers(BaseCombinatorTestCase):
    """Pruebas para combinadores de coincidencia directa (match)."""

    def test_match_token_success(self) -> None:
        tok = self.make_token(Token.IDENT, "foo")
        parser = self.make_parser(tok)
        matcher = MatchToken(Token.IDENT)

        result = matcher.parse(parser)
        self.assertIs(result, tok)
        self.assertEqual(parser.pos, 1)

    def test_match_token_by_string(self) -> None:
        tok = self.make_token(Token.NUMBER, 42)
        parser = self.make_parser(tok)
        matcher = MatchToken("NUMBER")

        result = matcher.parse(parser)
        self.assertEqual(result.value, 42)
        self.assertEqual(parser.pos, 1)

    def test_match_token_mismatch_backtracks(self) -> None:
        tok = self.make_token(Token.STRING, "hello")
        parser = self.make_parser(tok)
        matcher = MatchToken(Token.NUMBER)

        # Con ignore_errors=True
        result = matcher.parse(parser, ignore_errors=True)
        self.assertIsNone(result)
        self.assertEqual(parser.pos, 0)

        # Con ignore_errors=False lanza ParserError
        with self.assertRaises(ParserError) as ctx:
            matcher.parse(parser, ignore_errors=False)
        self.assertEqual(ctx.exception.code, errors.PARSER_UNEXPECTED_TOKEN)
        self.assertEqual(parser.pos, 0)

    def test_match_keyword_success(self) -> None:
        words.add_keyword("function")
        tok = self.make_token(Token.KEYWORD, "function")
        parser = self.make_parser(tok)
        matcher = MatchKeyword("function")

        result = matcher.parse(parser)
        self.assertIs(result, tok)
        self.assertEqual(parser.pos, 1)

    def test_match_keyword_unregistered_fails(self) -> None:
        tok = self.make_token(Token.KEYWORD, "unregistered")
        parser = self.make_parser(tok)
        matcher = MatchKeyword("unregistered")

        with self.assertRaises(ParserError) as ctx:
            matcher.parse(parser)
        self.assertEqual(ctx.exception.code, errors.KEYWORD_NOT_FOUND)
        self.assertEqual(parser.pos, 0)

    def test_match_group_success_and_filtering(self) -> None:
        words.add_keyword("int")
        words.add_keyword("float")
        words.add_keyword("void")
        grp = words.add_group("TYPES", ["int", "float", "void"])

        # Coincidencia estándar
        tok_int = self.make_token(Token.KEYWORD, "int")
        parser = self.make_parser(tok_int)
        matcher = MatchGroup("TYPES")
        self.assertIsNotNone(matcher.parse(parser))

        # Filtro exclude
        tok_void = self.make_token(Token.KEYWORD, "void")
        p2 = self.make_parser(tok_void)
        matcher_no_void = MatchGroup("TYPES", exclude=["void"])
        self.assertIsNone(matcher_no_void.parse(p2, ignore_errors=True))
        self.assertEqual(p2.pos, 0)

        # Filtro only
        tok_float = self.make_token(Token.KEYWORD, "float")
        p3 = self.make_parser(tok_float)
        matcher_only_int = MatchGroup("TYPES", only=["int"])
        self.assertIsNone(matcher_only_int.parse(p3, ignore_errors=True))

    def test_match_symbol_and_generador_expr(self) -> None:
        expr = generador_expr("#", ["A", "F"], [0, 9])
        self.assertEqual(expr, r"\#[A-F0-9]")

        matcher = MatchSeqSymbol(regex=r"==|!=")
        tok_eq = self.make_token(Token.EQUAL, "==")
        p = self.make_parser(tok_eq)
        res = matcher.parse(p)
        self.assertIsNotNone(res)
        self.assertEqual(p.pos, 1)

        # Reetiquetado a CustomToken
        matcher_tagged = MatchSeqSymbol(pattern="->", custom_token_name="ARROW")
        tok_arrow = self.make_token(Token.IDENT, "->")
        p2 = self.make_parser(tok_arrow)
        res2 = matcher_tagged.parse(p2)
        self.assertEqual(res2.token.name, "ARROW")


class TestItemAndLiteral(BaseCombinatorTestCase):
    """Pruebas para los combinadores Item, ItemResult y Literal."""

    def test_item_result_properties(self) -> None:
        res = ItemResult([10, [20, 30]])
        self.assertEqual(res.first, 10)
        self.assertEqual(res.last, [20, 30])
        self.assertTrue(res.is_match)
        self.assertTrue(bool(res))
        self.assertEqual(res.to_list(), [10, [20, 30]])

    def test_item_atomic_success(self) -> None:
        t1 = self.make_token(Token.IDENT, "var")
        t2 = self.make_token(Token.COLON, ":")
        parser = self.make_parser(t1, t2)

        item_comb = Item(MatchToken(Token.IDENT), MatchToken(Token.COLON))
        res = item_comb.parse(parser)

        self.assertIsInstance(res, ItemResult)
        self.assertEqual(len(res), 2)
        self.assertEqual(parser.pos, 2)

    def test_item_atomic_failure_rolls_back(self) -> None:
        t1 = self.make_token(Token.IDENT, "var")
        t2 = self.make_token(Token.ASSIGN, "=")  # Se esperaba COLON
        parser = self.make_parser(t1, t2)

        item_comb = Item(MatchToken(Token.IDENT), MatchToken(Token.COLON))
        res = item_comb.parse(parser, ignore_errors=True)

        self.assertIsNone(res)
        self.assertEqual(parser.pos, 0)  # Rollback atómico completo

    def test_literal_validation(self) -> None:
        t_num = self.make_token(Token.NUMBER, 100)
        p1 = self.make_parser(t_num)
        self.assertIsNotNone(Literal(100).parse(p1))

        # Discrepancia de valor
        p2 = self.make_parser(t_num)
        self.assertIsNone(Literal(200).parse(p2, ignore_errors=True))
        self.assertEqual(p2.pos, 0)

        # Rechazo de palabras clave
        words.add_keyword("class")
        t_kw = self.make_token(Token.KEYWORD, "class")
        p3 = self.make_parser(t_kw)
        self.assertIsNone(Literal("class").parse(p3, ignore_errors=True))
        self.assertEqual(p3.pos, 0)


class TestSequenceAndAlternative(BaseCombinatorTestCase):
    """Pruebas para Secuencia (Seq) y Alternativas (Alt)."""

    def test_seq_success(self) -> None:
        t1 = self.make_token(Token.IDENT, "x")
        t2 = self.make_token(Token.ASSIGN, "=")
        t3 = self.make_token(Token.NUMBER, 10)
        parser = self.make_parser(t1, t2, t3)

        seq = Seq(MatchToken(Token.IDENT), MatchToken(Token.ASSIGN), MatchToken(Token.NUMBER))
        res = seq.parse(parser)

        self.assertIsInstance(res, list)
        self.assertEqual(len(res), 3)
        self.assertEqual(parser.pos, 3)

    def test_seq_backtracking_on_intermediate_failure(self) -> None:
        t1 = self.make_token(Token.IDENT, "x")
        t2 = self.make_token(Token.COLON, ":")  # Se esperaba ASSIGN
        t3 = self.make_token(Token.NUMBER, 10)
        parser = self.make_parser(t1, t2, t3)

        seq = Seq(MatchToken(Token.IDENT), MatchToken(Token.ASSIGN), MatchToken(Token.NUMBER))
        res = seq.parse(parser, ignore_errors=True)

        self.assertIsNone(res)
        self.assertEqual(parser.pos, 0)  # Retorno a 0 exacto

    def test_seq_operator_add(self) -> None:
        s1 = MatchToken(Token.IDENT) + MatchToken(Token.ASSIGN)
        self.assertIsInstance(s1, Seq)
        self.assertEqual(len(s1.combinators), 2)

        s2 = s1 + MatchToken(Token.NUMBER)
        self.assertEqual(len(s2.combinators), 3)

    def test_alt_success_first_branch(self) -> None:
        tok = self.make_token(Token.NUMBER, 42)
        parser = self.make_parser(tok)

        alt = Alt(MatchToken(Token.NUMBER), MatchToken(Token.STRING))
        res = alt.parse(parser)

        self.assertEqual(res.value, 42)
        self.assertEqual(parser.pos, 1)

    def test_alt_success_second_branch_with_backtrack(self) -> None:
        tok = self.make_token(Token.STRING, "hello")
        parser = self.make_parser(tok)

        alt = Alt(MatchToken(Token.NUMBER), MatchToken(Token.STRING))
        res = alt.parse(parser)

        self.assertEqual(res.value, "hello")
        self.assertEqual(parser.pos, 1)

    def test_alt_all_fail_restores_cursor(self) -> None:
        tok = self.make_token(Token.IDENT, "var")
        parser = self.make_parser(tok)

        alt = Alt(MatchToken(Token.NUMBER), MatchToken(Token.STRING))
        res = alt.parse(parser, ignore_errors=True)

        self.assertIsNone(res)
        self.assertEqual(parser.pos, 0)

    def test_alt_operator_or(self) -> None:
        a1 = MatchToken(Token.NUMBER) | MatchToken(Token.STRING)
        self.assertIsInstance(a1, Alt)
        self.assertEqual(len(a1.combinators), 2)

        a2 = a1 | MatchToken(Token.IDENT)
        self.assertEqual(len(a2.combinators), 3)

    def test_alt_cut_flow_signal_stops_backtracking(self) -> None:
        class CutCombinator(MatchToken):
            def parse(self, analyzer, current=None, ignore_errors=False):
                super().parse(analyzer, current, ignore_errors=ignore_errors)
                raise CutFlowSignal("Cut triggered")

        tok = self.make_token(Token.IDENT, "cut_me")
        parser = self.make_parser(tok)

        alt = Alt(CutCombinator(Token.IDENT), MatchToken(Token.IDENT))
        res = alt.parse(parser, ignore_errors=True)

        self.assertIsNone(res)
        self.assertEqual(parser.pos, 0)


class TestOptionalAndRepetition(BaseCombinatorTestCase):
    """Pruebas para Opt, Many y Some."""

    def test_opt_matching(self) -> None:
        tok = self.make_token(Token.PLUS, "+")
        parser = self.make_parser(tok)

        opt = Opt(MatchToken(Token.PLUS))
        res = opt.parse(parser)

        self.assertIsInstance(res, OptResult)
        self.assertTrue(res.matched)
        self.assertEqual(res.unwrap(), tok)
        self.assertEqual(parser.pos, 1)

    def test_opt_not_matching(self) -> None:
        tok = self.make_token(Token.MINUS, "-")
        parser = self.make_parser(tok)

        opt = Opt(MatchToken(Token.PLUS))
        res = opt.parse(parser)

        self.assertIsInstance(res, OptResult)
        self.assertFalse(res.matched)
        self.assertIsNone(res.unwrap())
        self.assertEqual(res.unwrap(default="default"), "default")
        self.assertEqual(parser.pos, 0)  # No consume nada

    def test_many_zero_occurrences(self) -> None:
        tok = self.make_token(Token.IDENT, "foo")
        parser = self.make_parser(tok)

        many = Many(MatchToken(Token.NUMBER))
        res = many.parse(parser)

        self.assertEqual(res, [])
        self.assertEqual(parser.pos, 0)

    def test_many_multiple_occurrences(self) -> None:
        t1 = self.make_token(Token.NUMBER, 1)
        t2 = self.make_token(Token.NUMBER, 2)
        t3 = self.make_token(Token.IDENT, "end")
        parser = self.make_parser(t1, t2, t3)

        many = Many(MatchToken(Token.NUMBER))
        res = many.parse(parser)

        self.assertEqual(len(res), 2)
        self.assertEqual(parser.pos, 2)
        self.assertEqual(parser.current().value, "end")

    def test_some_at_least_one(self) -> None:
        t1 = self.make_token(Token.NUMBER, 1)
        t2 = self.make_token(Token.IDENT, "end")
        parser = self.make_parser(t1, t2)

        some = Some(MatchToken(Token.NUMBER))
        res = some.parse(parser)

        self.assertEqual(len(res), 1)
        self.assertEqual(parser.pos, 1)

    def test_some_zero_fails(self) -> None:
        tok = self.make_token(Token.IDENT, "foo")
        parser = self.make_parser(tok)

        some = Some(MatchToken(Token.NUMBER))
        res = some.parse(parser, ignore_errors=True)

        self.assertIsNone(res)
        self.assertEqual(parser.pos, 0)

        with self.assertRaises(ParserError) as ctx:
            some.parse(parser, ignore_errors=False)
        self.assertEqual(ctx.exception.code, errors.COMBINATOR_FAILED)


class TestSeparatorAndEnclosed(BaseCombinatorTestCase):
    """Pruebas para Separator (Sep) y Enclosed (Bracketed)."""

    def test_separator_standard(self) -> None:
        # a, b, c
        t1 = self.make_token(Token.IDENT, "a")
        t2 = self.make_token(Token.COMMA, ",")
        t3 = self.make_token(Token.IDENT, "b")
        t4 = self.make_token(Token.COMMA, ",")
        t5 = self.make_token(Token.IDENT, "c")
        parser = self.make_parser(t1, t2, t3, t4, t5)

        sep = Sep(MatchToken(Token.IDENT), sep=Token.COMMA)
        res = sep.parse(parser)

        self.assertIsInstance(res, SeparatorResult)
        self.assertEqual(len(res), 3)
        self.assertEqual([t.value for t in res], ["a", "b", "c"])
        self.assertFalse(res.trailing_separator)
        self.assertEqual(parser.pos, 5)

    def test_separator_trailing_allowed(self) -> None:
        # a, b,
        t1 = self.make_token(Token.IDENT, "a")
        t2 = self.make_token(Token.COMMA, ",")
        t3 = self.make_token(Token.IDENT, "b")
        t4 = self.make_token(Token.COMMA, ",")
        parser = self.make_parser(t1, t2, t3, t4)

        sep = Sep(MatchToken(Token.IDENT), sep=Token.COMMA, allow_trailing=True)
        res = sep.parse(parser)

        self.assertEqual(len(res), 2)
        self.assertTrue(res.trailing_separator)
        self.assertEqual(parser.pos, 4)

    def test_separator_trailing_not_allowed_rolls_back(self) -> None:
        # a, b,
        t1 = self.make_token(Token.IDENT, "a")
        t2 = self.make_token(Token.COMMA, ",")
        t3 = self.make_token(Token.IDENT, "b")
        t4 = self.make_token(Token.COMMA, ",")
        parser = self.make_parser(t1, t2, t3, t4)

        sep = Sep(MatchToken(Token.IDENT), sep=Token.COMMA, allow_trailing=False)
        res = sep.parse(parser, ignore_errors=True)

        # El separador final no coincide como trailing; consume hasta 'b' y deja la coma
        self.assertEqual(len(res), 2)
        self.assertEqual(parser.pos, 3)  # La coma final fue restaurada

    def test_enclosed_success_with_whitespace_suppression(self) -> None:
        # ( \n x \n )
        t_open = self.make_token(Token.LPAREN, "(")
        t_nl1 = self.make_token(Token.NEWLINE, "\n")
        t_val = self.make_token(Token.IDENT, "x")
        t_nl2 = self.make_token(Token.NEWLINE, "\n")
        t_close = self.make_token(Token.RPAREN, ")")
        parser = self.make_parser(t_open, t_nl1, t_val, t_nl2, t_close)

        enclosed = Enclosed("(", MatchToken(Token.IDENT), ")")
        res = enclosed.parse(parser)

        self.assertEqual(res.value, "x")
        self.assertEqual(parser.pos, 5)

    def test_enclosed_mismatched_open(self) -> None:
        t_open = self.make_token(Token.LBRACKET, "[")
        parser = self.make_parser(t_open)

        enclosed = Enclosed("(", MatchToken(Token.IDENT), ")")
        res = enclosed.parse(parser, ignore_errors=True)

        self.assertIsNone(res)
        self.assertEqual(parser.pos, 0)

    def test_enclosed_empty_content_allowed_by_default(self) -> None:
        parser = self.make_parser(
            self.make_token(Token.LPAREN, "("),
            self.make_token(Token.RPAREN, ")"),
        )

        res = Enclosed("(", MatchToken(Token.IDENT), ")").parse(parser)

        self.assertEqual(res, [])
        self.assertEqual(parser.pos, 2)

    def test_enclosed_empty_content_can_be_rejected(self) -> None:
        parser = self.make_parser(
            self.make_token(Token.LPAREN, "("),
            self.make_token(Token.RPAREN, ")"),
        )

        res = Enclosed(
            "(", MatchToken(Token.IDENT), ")", allow_empty=False
        ).parse(parser, ignore_errors=True)

        self.assertIsNone(res)
        self.assertEqual(parser.pos, 0)


class TestReferenceAndTokenize(BaseCombinatorTestCase):
    """Pruebas para Ref (Reference), Tokenize y AnyGrammar."""

    def test_reference_to_rule_class(self) -> None:
        class NumberRule(RuleItem):
            code = 101
            name = "NumberRule"
            grammar = MatchToken(Token.NUMBER)

        tok = self.make_token(Token.NUMBER, 123)
        parser = self.make_parser(tok)

        ref = Ref(NumberRule)
        res = ref.parse(parser)

        self.assertEqual(res.value, 123)
        self.assertEqual(parser.pos, 1)

    def test_reference_to_named_grammar_in_analyzer(self) -> None:
        class DummyAnalyzer:
            def __init__(self, parser: Parser):
                self.parser = parser
                self.grammar = {"expr": MatchToken(Token.IDENT)}

        tok = self.make_token(Token.IDENT, "my_var")
        parser = self.make_parser(tok)
        analyzer = DummyAnalyzer(parser)

        ref = Ref("expr")
        res = ref.parse(analyzer)

        self.assertEqual(res.value, "my_var")
        self.assertEqual(parser.pos, 1)

    def test_tokenize_fuses_tokens(self) -> None:
        t1 = self.make_token(Token.IDENT, "0x")
        t2 = self.make_token(Token.NUMBER, 1)
        t3 = self.make_token(Token.IDENT, "A")
        parser = self.make_parser(t1, t2, t3)

        tok_comb = Tokenize(
            MatchToken(Token.IDENT),
            MatchToken(Token.NUMBER),
            MatchToken(Token.IDENT),
            token_name="HEX_LITERAL",
        )
        res = tok_comb.parse(parser)

        self.assertIsInstance(res, TokenType)
        self.assertEqual(res.value, "0x1A")
        self.assertEqual(res.token.name, "HEX_LITERAL")
        self.assertEqual(parser.pos, 3)

    def test_any_grammar_raises_any_not_implemented(self) -> None:
        parser = self.make_parser(self.make_token(Token.IDENT, "x"))
        any_g = AnyGrammar()

        with self.assertRaises(GrammarError) as ctx:
            any_g.parse(parser)
        self.assertEqual(ctx.exception.code, errors.ANY_NOT_IMPLEMENTED)


class TestModsAndAdditionalStack(BaseCombinatorTestCase):
    """Pruebas para clasificación de combinadores y la pila adicional (mods)."""

    def test_hardcoded_mods_classification(self) -> None:
        self.assertTrue(is_hardcoded_mod(Seq))
        self.assertTrue(is_hardcoded_mod(Alt))
        self.assertTrue(is_hardcoded_mod(MatchToken(Token.IDENT)))
        self.assertFalse(is_hardcoded_mod(object))

    def test_custom_mod_registration_and_dispatch(self) -> None:
        @custom_mod("MY_CUSTOM_COMBINATOR")
        class MyCustom(Seq):
            pass

        self.assertTrue(is_custom_mod(MyCustom))
        self.assertTrue(CombinatorAdditionalStack.has(MyCustom))

        # Registro manual con handler
        handler_called = []

        def my_handler(comb, analyzer, current, ignore_errors):
            handler_called.append(True)
            return "HANDLER_OK"

        register_custom_mod(MyCustom, handler=my_handler)
        parser = self.make_parser()
        res = CombinatorAdditionalStack.process(MyCustom(MatchToken(Token.IDENT)), parser)

        self.assertEqual(res, "HANDLER_OK")
        self.assertTrue(handler_called[0])


class TestHeaderClassAttribute(BaseCombinatorTestCase):
    """Valida el atributo header_class en la clase base Combinator y sus subclases."""

    def test_combinator_base_defaults_to_false(self) -> None:
        from gram.core.combinators.base import Combinator
        self.assertFalse(Combinator.header_class)
        base_inst = Combinator()
        self.assertFalse(base_inst.header_class)

    def test_unconfigured_subclass_defaults_to_false(self) -> None:
        from gram.core.combinators.base import Combinator

        class CustomLeafCombinator(Combinator):
            pass

        self.assertFalse(CustomLeafCombinator.header_class)
        inst = CustomLeafCombinator()
        self.assertFalse(inst.header_class)

    def test_header_combinators_have_header_class_true(self) -> None:
        """Los combinadores que actúan como cabeceras de regla deben tener header_class = True."""
        header_classes = [
            Alt,
            Seq,
            Many,
            Some,
            Opt,
            Separator,
            Sep,
            Enclosed,
            Bracketed,
            Tokenize,
            AnyGrammar,
        ]
        for cls in header_classes:
            self.assertTrue(
                cls.header_class,
                f"El combinador de cabecera {cls.__name__} debe tener header_class = True a nivel de clase."
            )

        # Probar instancias
        dummy = MatchToken(Token.IDENT)
        self.assertTrue(Alt(dummy).header_class)
        self.assertTrue(Seq(dummy).header_class)
        self.assertTrue(Many(dummy).header_class)
        self.assertTrue(Some(dummy).header_class)
        self.assertTrue(Opt(dummy).header_class)
        self.assertTrue(Sep(dummy).header_class)
        self.assertTrue(Enclosed("(", dummy, ")").header_class)
        self.assertTrue(Tokenize(dummy).header_class)
        self.assertTrue(AnyGrammar().header_class)

    def test_non_header_combinators_have_header_class_false(self) -> None:
        """Los combinadores atómicos u hoja deben tener header_class = False."""
        self.assertFalse(MatchToken.header_class)
        self.assertFalse(MatchToken(Token.IDENT).header_class)
        self.assertFalse(MatchKeyword.header_class)
        self.assertFalse(MatchKeyword("test").header_class)
        self.assertFalse(MatchGroup.header_class)
        self.assertFalse(MatchGroup("TEST_GROUP").header_class)
        self.assertFalse(MatchSeqSymbol.header_class)
        self.assertFalse(Ref.header_class)
        self.assertFalse(Ref("regla").header_class)
        self.assertFalse(Item.header_class)
        self.assertFalse(Item(MatchToken(Token.IDENT)).header_class)
        self.assertFalse(Literal.header_class)
        self.assertFalse(Literal("valor").header_class)

    def test_plugin_header_combinators(self) -> None:
        """Verifica header_class en combinadores de plugins conocidos."""
        from gram.plugins.source.expressions.combinators.chain import ChainL, ChainR
        from gram.plugins.source.GRAM_ESSENCIAL_PACK.advanced_combinators import If

        dummy = MatchToken(Token.IDENT)
        self.assertTrue(ChainL.header_class)
        self.assertTrue(ChainL(dummy, dummy).header_class)
        self.assertTrue(ChainR.header_class)
        self.assertTrue(ChainR(dummy, dummy).header_class)
        self.assertTrue(If.header_class)
        self.assertTrue(If(dummy).header_class)


if __name__ == "__main__":
    unittest.main()
