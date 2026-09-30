"""
Pruebas Unitarias Exhaustivas del Analizador Léxico de Gram (`gram.tests.test_lexer`).
======================================================================================
Valida todos los componentes del subsistema léxico:
  1. Catálogo de tokens y tipos léxicos (Token, CustomToken, TokenType, MAP_SYMBOLS).
  2. Motor de palabras clave y grupos semánticos (Keyword, WordGroup, words, word).
  3. Visitante de números (enteros, hexadecimal, binario, octal, punto flotante, exponentes, guiones bajos, errores).
  4. Visitante de cadenas y docstrings (comillas simples/dobles, multilínea, secuencias de escape estándar y Unicode, errores).
  5. Visitante de símbolos y operadores (coincidencia máxima / maximal munch, operadores compuestos, Unicode, errores).
  6. Visitante de palabras (booleanos true/false, literales null, keywords registradas, identificadores).
  7. Motor Lexer (flujo completo, gestión de indentación INDENT/DEDENT, comentarios, líneas vacías, check_state, errores).
  8. Flujo de tokens TokenStream (navegación, lookahead, consumo condicional, match, check, slice, filtros).
"""
from __future__ import annotations

import unittest

from gram import config, errors
from gram.core.lexer import (
    CustomToken,
    Keyword,
    Lexer,
    MAP_SYMBOLS,
    Token,
    TokenStream,
    TokenType,
    WordGroup,
    WordGroupManager,
    add_group,
    add_keyword,
    all_group_names,
    all_groups,
    all_keyword_names,
    all_keywords,
    check_state,
    clear_all,
    count_keywords,
    create_group,
    exists_in_group,
    get_group,
    get_keyword,
    get_sorted_symbols,
    get_tokens,
    group_exists,
    groups,
    is_empty,
    keyword_exists,
    remove_group,
    remove_keyword,
    tokenize,
    tokenize_stream,
    word,
    words,
)
from gram.utilities.error import LexerError


class BaseLexerTestCase(unittest.TestCase):
    """Caso base con configuración silenciosa y aislamiento de estado."""

    def setUp(self) -> None:
        self.old_hide_console = config.ERROR_HIDE_CONSOLE
        self.old_exit_on_error = config.ERROR_EXIT_ON_ERROR
        config.ERROR_HIDE_CONSOLE = True
        config.ERROR_EXIT_ON_ERROR = False
        clear_all()
        # Registrar keywords base para que check_state() no falle por defecto
        add_keyword('def', '#FF5555', description='Definición de función')
        add_keyword('if', '#55FF55', description='Condicional if')
        add_keyword('else', '#55FF55', description='Rama alternativa')
        add_keyword('return', '#5555FF', description='Retorno')

    def tearDown(self) -> None:
        clear_all()
        config.ERROR_HIDE_CONSOLE = self.old_hide_console
        config.ERROR_EXIT_ON_ERROR = self.old_exit_on_error


# ==============================================================================
# 1. PRUEBAS DE TOKENS Y TOKENTYPE
# ==============================================================================

class TestTokensAndTokenType(BaseLexerTestCase):
    """Pruebas para Token, CustomToken, TokenType y mapas de símbolos."""

    def test_token_enum_completeness(self) -> None:
        """Verifica que Token enum tenga categorías básicas y método get_tokens."""
        all_toks = get_tokens()
        self.assertIn(Token.EOF, all_toks)
        self.assertIn(Token.IDENT, all_toks)
        self.assertIn(Token.NUMBER, all_toks)
        self.assertIn(Token.STRING, all_toks)
        self.assertIn(Token.DOCSTRING, all_toks)
        self.assertIn(Token.BOOL, all_toks)
        self.assertIn(Token.NULL, all_toks)
        self.assertIn(Token.INDENT, all_toks)
        self.assertIn(Token.DEDENT, all_toks)

    def test_custom_token(self) -> None:
        """Verifica creación, igualdad y hashing de CustomToken."""
        ct1 = CustomToken("SQL_SELECT", description="Token de SQL")
        ct2 = CustomToken("SQL_SELECT")
        self.assertEqual(ct1, ct2)
        self.assertEqual(ct1.name, "SQL_SELECT")
        self.assertEqual(str(ct1), "SQL_SELECT")
        self.assertEqual(hash(ct1), hash(ct2))

    def test_tokentype_properties_and_equality(self) -> None:
        """Verifica atributos, igualdad y formato de TokenType."""
        t1 = TokenType(Token.IDENT, "mi_variable", line=2, col=5)
        t2 = TokenType(Token.IDENT, "mi_variable", line=2, col=5)
        self.assertEqual(t1, t2)
        self.assertEqual(t1.token, Token.IDENT)
        self.assertEqual(t1.value, "mi_variable")
        self.assertEqual(t1.line, 2)
        self.assertEqual(t1.col, 5)

        # Formatter de mensajes
        formatted = t1.formatter("Error en $name ($value) en línea $line:$col")
        self.assertIn("IDENT", formatted)
        self.assertIn("mi_variable", formatted)
        self.assertIn("2:5", formatted)

    def test_sorted_symbols_maximal_munch_order(self) -> None:
        """Garantiza que get_sorted_symbols() ordene por longitud descendente."""
        symbols_list = get_sorted_symbols()
        self.assertGreater(len(symbols_list), 30)
        # Símbolos de 3 caracteres antes de 2 y 1
        idx_shl_assign = symbols_list.index("<<=")
        idx_shl = symbols_list.index("<<")
        idx_less = symbols_list.index("<")
        self.assertLess(idx_shl_assign, idx_shl)
        self.assertLess(idx_shl, idx_less)


# ==============================================================================
# 2. PRUEBAS DE PALABRAS CLAVE Y GRUPOS (WORDS Y WORD PROXY)
# ==============================================================================

class TestKeywordAndGroupManager(BaseLexerTestCase):
    """Pruebas para Keyword, WordGroup, words y el alias de compatibilidad word."""

    def test_keyword_lifecycle(self) -> None:
        """Verifica registro, consulta, existencia y eliminación de keywords."""
        kw = add_keyword("async", "#AA00FF", description="Función asíncrona")
        self.assertIsInstance(kw, Keyword)
        self.assertEqual(kw.name, "async")
        self.assertTrue(keyword_exists("async"))
        self.assertEqual(get_keyword("async"), kw)
        self.assertEqual(str(kw), "async")

        # Eliminación
        removed = remove_keyword("async")
        self.assertEqual(removed, kw)
        self.assertFalse(keyword_exists("async"))
        self.assertIsNone(get_keyword("async"))

    def test_keyword_invalid_name_error(self) -> None:
        """Verifica error al registrar una keyword con nombre vacío o blanco."""
        with self.assertRaises(LexerError):
            add_keyword("")
        with self.assertRaises(LexerError):
            add_keyword("   ")

    def test_keyword_already_exists_error(self) -> None:
        """Verifica error al intentar registrar una keyword duplicada sin allow_override."""
        with self.assertRaises(LexerError):
            add_keyword("def", allow_override=False)

        # Con allow_override=True no debe fallar
        overridden = add_keyword("def", "#000000", allow_override=True)
        self.assertEqual(overridden.hex_color, "#000000")

    def test_word_proxy_identity(self) -> None:
        """Verifica que el módulo word sea un proxy idéntico al módulo words."""
        self.assertIs(word.add_keyword, words.add_keyword)
        self.assertIs(word.get_keyword, words.get_keyword)
        self.assertIs(word.groups, words.groups)

    def test_word_group_lifecycle(self) -> None:
        """Verifica creación de grupos, inclusión de palabras y pertenencia."""
        add_keyword("i32", "#112233")
        add_keyword("i64", "#112233")

        grp = create_group("NumericTypes", ["i32", "i64"], "#FFAA00", "Enteros")
        self.assertIsInstance(grp, WordGroup)
        self.assertEqual(grp.count(), 2)
        self.assertIn("i32", grp)
        self.assertIn("i64", grp)
        self.assertTrue(exists_in_group("i32", "NumericTypes"))
        self.assertFalse(exists_in_group("str", "NumericTypes"))

        # Eliminar grupo
        removed = remove_group("NumericTypes")
        self.assertEqual(removed, grp)
        self.assertFalse(group_exists("NumericTypes"))

    def test_word_group_unregistered_keyword_error(self) -> None:
        """Verifica error al intentar agregar una palabra no registrada al grupo."""
        with self.assertRaises(LexerError):
            add_group("BadGroup", ["keyword_inexistente_123"])

    def test_word_group_duplicate_error(self) -> None:
        """Verifica error al crear grupo con nombre duplicado."""
        add_group("MyGroup")
        with self.assertRaises(LexerError):
            add_group("MyGroup", allow_override=False)


# ==============================================================================
# 3. PRUEBAS DEL VISITANTE DE NÚMEROS (NUMBERS VISITOR)
# ==============================================================================

class TestNumbersVisitor(BaseLexerTestCase):
    """Pruebas de enteros, bases (0x, 0b, 0o), flotantes, exponentes y errores."""

    def test_decimal_integers_and_underscores(self) -> None:
        """Verifica análisis de números enteros estándar y con guion bajo."""
        tokens_list = tokenize("100 1_000_000 0 42")
        numbers = [t for t in tokens_list if t.token == Token.NUMBER]
        self.assertEqual([t.value for t in numbers], [100, 1000000, 0, 42])

    def test_hexadecimal_numbers(self) -> None:
        """Verifica análisis de números en base hexadecimal (0x...)."""
        tokens_list = tokenize("0x10 0xFF 0xDEAD_BEEF 0X1A")
        numbers = [t for t in tokens_list if t.token == Token.NUMBER]
        self.assertEqual([t.value for t in numbers], [16, 255, 0xDEADBEEF, 26])

    def test_binary_numbers(self) -> None:
        """Verifica análisis de números en base binaria (0b...)."""
        tokens_list = tokenize("0b1010 0b1111_0000 0B1")
        numbers = [t for t in tokens_list if t.token == Token.NUMBER]
        self.assertEqual([t.value for t in numbers], [10, 240, 1])

    def test_octal_numbers(self) -> None:
        """Verifica análisis de números en base octal (0o...)."""
        tokens_list = tokenize("0o10 0o77 0o123_456 0O7")
        numbers = [t for t in tokens_list if t.token == Token.NUMBER]
        self.assertEqual([t.value for t in numbers], [8, 63, 0o123456, 7])

    def test_floating_point_numbers(self) -> None:
        """Verifica números con parte decimal."""
        tokens_list = tokenize("3.14 0.001 100.5_5")
        numbers = [t for t in tokens_list if t.token == Token.NUMBER]
        self.assertAlmostEqual(numbers[0].value, 3.14)
        self.assertAlmostEqual(numbers[1].value, 0.001)
        self.assertAlmostEqual(numbers[2].value, 100.55)

    def test_scientific_notation(self) -> None:
        """Verifica notación científica con exponente (1e5, 2.5E-3, 3e+2)."""
        tokens_list = tokenize("1e5 2.5E-3 3e+2")
        numbers = [t for t in tokens_list if t.token == Token.NUMBER]
        self.assertEqual(numbers[0].value, 100000.0)
        self.assertAlmostEqual(numbers[1].value, 0.0025)
        self.assertEqual(numbers[2].value, 300.0)

    def test_incomplete_hex_prefix_error(self) -> None:
        """Verifica error al encontrar '0x' sin dígitos hexadecimales posteriores."""
        with self.assertRaises(LexerError):
            tokenize("0x")

    def test_incomplete_binary_prefix_error(self) -> None:
        """Verifica error al encontrar '0b' sin dígitos binarios posteriores."""
        with self.assertRaises(LexerError):
            tokenize("0b")

    def test_incomplete_octal_prefix_error(self) -> None:
        """Verifica error al encontrar '0o' sin dígitos octales posteriores."""
        with self.assertRaises(LexerError):
            tokenize("0o")

    def test_invalid_exponent_error(self) -> None:
        """Verifica error al encontrar '1e+' sin dígitos de exponente."""
        with self.assertRaises(LexerError):
            tokenize("1e+")


# ==============================================================================
# 4. PRUEBAS DEL VISITANTE DE CADENAS (STRINGS Y DOCSTRINGS)
# ==============================================================================

class TestStringsVisitor(BaseLexerTestCase):
    """Pruebas de cadenas simples, dobles, multilínea (docstrings), escapes y errores."""

    def test_simple_and_double_quoted_strings(self) -> None:
        """Verifica cadenas con comillas simples y dobles."""
        tokens_list = tokenize("'hola' \"mundo\"")
        strings_toks = [t for t in tokens_list if t.token == Token.STRING]
        self.assertEqual(len(strings_toks), 2)
        self.assertEqual(strings_toks[0].value, "hola")
        self.assertEqual(strings_toks[1].value, "mundo")

    def test_escape_sequences(self) -> None:
        """Verifica secuencias de escape estándar (\\n, \\t, \\r, etc.)."""
        tokens_list = tokenize(r'"linea1\nlinea2\ttab"')
        str_tok = next(t for t in tokens_list if t.token == Token.STRING)
        self.assertEqual(str_tok.value, "linea1\nlinea2\ttab")

    def test_unicode_escape_sequence(self) -> None:
        """Verifica secuencias de escape Unicode \\uXXXX."""
        tokens_list = tokenize(r'"\u0041\u0042\u0043"')
        str_tok = next(t for t in tokens_list if t.token == Token.STRING)
        self.assertEqual(str_tok.value, "ABC")

    def test_triple_quoted_docstrings(self) -> None:
        """Verifica docstrings multilínea delimitados por triple comilla."""
        code = '"""Primera linea\nSegunda linea"""'
        tokens_list = tokenize(code)
        doc_tok = next(t for t in tokens_list if t.token == Token.DOCSTRING)
        self.assertEqual(doc_tok.value, "Primera linea\nSegunda linea")

    def test_unclosed_single_line_string_error(self) -> None:
        """Verifica error cuando una cadena no tiene comilla de cierre antes del fin de línea."""
        with self.assertRaises(LexerError):
            tokenize('"cadena sin cerrar')

    def test_unclosed_docstring_error(self) -> None:
        """Verifica error cuando un docstring no se cierra antes de EOF."""
        with self.assertRaises(LexerError):
            tokenize('"""docstring infinito sin cerrar')


# ==============================================================================
# 5. PRUEBAS DEL VISITANTE DE SÍMBOLOS (SYMBOLS VISITOR)
# ==============================================================================

class TestSymbolsVisitor(BaseLexerTestCase):
    """Pruebas de operadores simples, compuestos, maximal munch y Unicode."""

    def test_basic_operators_and_delimiters(self) -> None:
        """Verifica reconocimiento de operadores matemáticos y delimitadores."""
        code = "+ - * / % ( ) [ ] { } , : ;"
        tokens_list = tokenize(code)
        types = [t.token for t in tokens_list if t.token not in (Token.NEWLINE, Token.EOF)]
        expected = [
            Token.PLUS, Token.MINUS, Token.STAR, Token.SLASH, Token.PERCENT,
            Token.LPAREN, Token.RPAREN, Token.LBRACKET, Token.RBRACKET,
            Token.LBRACE, Token.RBRACE, Token.COMMA, Token.COLON, Token.SEMICOLON,
        ]
        self.assertEqual(types, expected)

    def test_maximal_munch_compound_operators(self) -> None:
        """Verifica que operadores compuestos no sean fragmentados (ej. '<<=' vs '<<' vs '<')."""
        code = "<<= >> = == != <= >= += -= *= /= **="
        tokens_list = tokenize(code)
        types = [t.token for t in tokens_list if t.token not in (Token.NEWLINE, Token.EOF)]
        expected = [
            Token.SHL_ASSIGN, Token.SHR, Token.ASSIGN, Token.EQUAL,
            Token.NOT_EQUAL, Token.LESS_EQUAL, Token.GREATER_EQUAL,
            Token.PLUS_ASSIGN, Token.MINUS_ASSIGN, Token.STAR_ASSIGN,
            Token.SLASH_ASSIGN, Token.POW_ASSIGN,
        ]
        self.assertEqual(types, expected)

    def test_arrows_and_special_symbols(self) -> None:
        """Verifica flechas (->, =>, <-, <->) y tres puntos (...)."""
        code = "-> => <- <-> ..."
        tokens_list = tokenize(code)
        types = [t.token for t in tokens_list if t.token not in (Token.NEWLINE, Token.EOF)]
        expected = [Token.ARROW, Token.FAT_ARROW, Token.LEFT_ARROW, Token.DOUBLE_ARROW, Token.THREE_DOTS]
        self.assertEqual(types, expected)

    def test_unicode_math_and_logic_symbols(self) -> None:
        """Verifica símbolos matemáticos y lógicos Unicode (∧, ∨, ¬, √, ∞, °)."""
        code = "∧ ∨ ¬ √ ∞ °"
        tokens_list = tokenize(code)
        types = [t.token for t in tokens_list if t.token not in (Token.NEWLINE, Token.EOF)]
        expected = [Token.LOGIC_AND, Token.LOGIC_OR, Token.LOGIC_NOT, Token.SQRT, Token.INFINITY, Token.DEGREE]
        self.assertEqual(types, expected)

    def test_unexpected_character_error(self) -> None:
        """Verifica error al encontrar un carácter no reconocido en el catálogo léxico."""
        with self.assertRaises(LexerError):
            tokenize("¿")


# ==============================================================================
# 6. PRUEBAS DEL VISITANTE DE PALABRAS (WORDS VISITOR)
# ==============================================================================

class TestWordsVisitor(BaseLexerTestCase):
    """Pruebas de identificadores, booleanos (true/false), nulos (null) y keywords."""

    def test_boolean_and_null_literals(self) -> None:
        """Verifica reconocimiento de true, false y null."""
        tokens_list = tokenize("true false null")
        toks = [t for t in tokens_list if t.token not in (Token.NEWLINE, Token.EOF)]

        self.assertEqual(toks[0].token, Token.BOOL)
        self.assertEqual(toks[0].value, True)

        self.assertEqual(toks[1].token, Token.BOOL)
        self.assertEqual(toks[1].value, False)

        self.assertEqual(toks[2].token, Token.NULL)
        self.assertIsNone(toks[2].value)

    def test_registered_keywords(self) -> None:
        """Verifica que las palabras registradas en el catálogo emitan Token.KEYWORD."""
        tokens_list = tokenize("def if else return")
        kw_toks = [t for t in tokens_list if t.token not in (Token.NEWLINE, Token.EOF)]
        for t in kw_toks:
            self.assertEqual(t.token, Token.KEYWORD)
        self.assertEqual([t.value for t in kw_toks], ["def", "if", "else", "return"])

    def test_generic_identifiers(self) -> None:
        """Verifica que palabras no reservadas emitan Token.IDENT."""
        tokens_list = tokenize("mi_variable _contador x123 CamelCase")
        idents = [t for t in tokens_list if t.token not in (Token.NEWLINE, Token.EOF)]
        for t in idents:
            self.assertEqual(t.token, Token.IDENT)
        self.assertEqual([t.value for t in idents], ["mi_variable", "_contador", "x123", "CamelCase"])


# ==============================================================================
# 7. PRUEBAS DEL MOTOR LEXER (ESTRUCTURA, INDENTACIÓN, COMENTARIOS)
# ==============================================================================

class TestLexerEngine(BaseLexerTestCase):
    """Pruebas del motor de análisis léxico, indentación, comentarios y check_state."""

    def test_check_state_empty_keywords_error(self) -> None:
        """Verifica que check_state() lance LexerError si no hay keywords registradas."""
        clear_all()
        self.assertTrue(is_empty())
        with self.assertRaises(LexerError):
            check_state()

        with self.assertRaises(LexerError):
            Lexer("x = 1").process()

    def test_indentation_and_dedentation_block(self) -> None:
        """Verifica generación de tokens INDENT y DEDENT para bloques jerárquicos."""
        code = [
            "if condition:",
            "    x = 10",
            "    y = 20",
            "z = 30",
        ]
        tokens_list = tokenize(code)
        types = [t.token for t in tokens_list]

        self.assertIn(Token.INDENT, types)
        self.assertIn(Token.DEDENT, types)

        indent_idx = types.index(Token.INDENT)
        dedent_idx = types.index(Token.DEDENT)
        self.assertLess(indent_idx, dedent_idx)

        # z debe emitirse tras el DEDENT
        z_idx = next(i for i, t in enumerate(tokens_list) if t.token == Token.IDENT and t.value == "z")
        self.assertGreater(z_idx, dedent_idx)

    def test_automatic_dedents_at_eof(self) -> None:
        """Verifica que bloques indentados se cierren con DEDENT antes de EOF."""
        code = [
            "if condition:",
            "    x = 10",
        ]
        tokens_list = tokenize(code)
        types = [t.token for t in tokens_list]
        self.assertIn(Token.INDENT, types)
        self.assertIn(Token.DEDENT, types)
        self.assertEqual(types[-2], Token.DEDENT)
        self.assertEqual(types[-1], Token.EOF)

    def test_indentation_mismatch_error(self) -> None:
        """Verifica que una desindentación no coincidente lance error."""
        code = [
            "def foo():",
            "    x = 1",
            "  y = 2",
        ]
        with self.assertRaises(LexerError):
            tokenize(code)

    def test_comments_handling(self) -> None:
        """Verifica omisión o conservación de comentarios de línea."""
        code = "a = 1 # Este es un comentario\nb = 2"

        # Con save_comments=False
        no_comm = tokenize(code, save_comments=False)
        self.assertNotIn(Token.COMMENT, [t.token for t in no_comm])

        # Con save_comments=True
        with_comm = tokenize(code, save_comments=True)
        comm_toks = [t for t in with_comm if t.token == Token.COMMENT]
        self.assertEqual(len(comm_toks), 1)
        self.assertIn("Este es un comentario", comm_toks[0].value)

    def test_custom_comment_delimiter(self) -> None:
        """Verifica uso de un delimitador de comentarios personalizado (ej. ';')."""
        code = "x = 42 ; comentario con punto y coma"
        tokens_list = tokenize(code, comment_token=";", save_comments=True)
        comm_tok = next(t for t in tokens_list if t.token == Token.COMMENT)
        self.assertIn("comentario con punto y coma", comm_tok.value)


# ==============================================================================
# 8. PRUEBAS DEL FLUJO DE TOKENS (TOKENSTREAM)
# ==============================================================================

class TestTokenStream(BaseLexerTestCase):
    """Pruebas de navegación, lookahead y consumo condicional en TokenStream."""

    def test_stream_navigation(self) -> None:
        """Verifica advance, peek, current, has_next y is_eof."""
        stream = tokenize_stream("x = 42")
        self.assertEqual(stream.position, 0)
        self.assertTrue(stream.has_next())
        self.assertFalse(stream.is_eof())

        curr = stream.current()
        self.assertIsNotNone(curr)
        self.assertEqual(curr.value, "x")

        # Peek al siguiente
        peek1 = stream.peek(1)
        self.assertIsNotNone(peek1)
        self.assertEqual(peek1.token, Token.ASSIGN)

        # Avanzar
        adv = stream.advance()
        self.assertEqual(adv.value, "x")
        self.assertEqual(stream.position, 1)

    def test_stream_check_and_match(self) -> None:
        """Verifica check() sin avance y match() con consumo condicional."""
        stream = tokenize_stream("x = 42")
        # Check
        self.assertTrue(stream.check(Token.IDENT))
        self.assertTrue(stream.check("x"))
        self.assertFalse(stream.check(Token.NUMBER))
        self.assertEqual(stream.position, 0)

        # Match consume si coincide
        self.assertTrue(stream.match(Token.IDENT))
        self.assertEqual(stream.position, 1)
        self.assertTrue(stream.match("="))
        self.assertEqual(stream.position, 2)
        self.assertFalse(stream.match("="))
        self.assertEqual(stream.position, 2)

    def test_stream_consume_and_error(self) -> None:
        """Verifica consumo con aserción de tipo y error si no coincide."""
        stream = tokenize_stream("x = 42")
        consumed = stream.consume(Token.IDENT)
        self.assertEqual(consumed.value, "x")

        with self.assertRaises(LexerError):
            stream.consume(Token.STRING)

    def test_stream_rewind_reset_and_filter(self) -> None:
        """Verifica retroceso, reinicio y filtrado de tipos de token."""
        stream = tokenize_stream("x = 42")
        stream.advance()
        stream.advance()
        self.assertEqual(stream.position, 2)

        stream.rewind(1)
        self.assertEqual(stream.position, 1)

        stream.reset()
        self.assertEqual(stream.position, 0)

        # Filtrar saltos de línea y EOF
        filtered = stream.filter_tokens(Token.NEWLINE, Token.EOF)
        self.assertEqual(len(filtered), 3)
        self.assertEqual([t.token for t in filtered], [Token.IDENT, Token.ASSIGN, Token.NUMBER])


    def test_lexer_ignore_newlines_option(self) -> None:
        """Verifica el comportamiento de LEXER_IGNORE_NEWLINES tanto activado como desactivado."""
        code = "a = 1\nb = 2"

        # Con ignore_newlines=True (por defecto), no se emite NEWLINE
        tokens_ignored = tokenize(code, ignore_newlines=True)
        types_ignored = [t.token for t in tokens_ignored]
        self.assertNotIn(Token.NEWLINE, types_ignored)
        self.assertEqual(types_ignored, [Token.IDENT, Token.ASSIGN, Token.NUMBER, Token.IDENT, Token.ASSIGN, Token.NUMBER, Token.EOF])

        # Con ignore_newlines=False, se emiten los tokens NEWLINE
        tokens_preserved = tokenize(code, ignore_newlines=False)
        types_preserved = [t.token for t in tokens_preserved]
        self.assertIn(Token.NEWLINE, types_preserved)
        self.assertEqual(types_preserved.count(Token.NEWLINE), 2)

    def test_config_data_paths(self) -> None:
        """Verifica que las rutas de datos y entorno en config estén inicializadas como Path."""
        from pathlib import Path
        self.assertIsInstance(config.DATA_DIR, Path)
        self.assertIsInstance(config.TEMP_DIR, Path)
        self.assertIsInstance(config.CACHE_DIR, Path)
        self.assertIsInstance(config.ENVIRONMENT_DIR, Path)
        self.assertEqual(str(config.DATA_DIR).replace('\\', '/'), 'data')


if __name__ == "__main__":
    unittest.main()
