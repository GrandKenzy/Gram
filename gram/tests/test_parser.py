"""
Pruebas Unitarias del Analizador Sintáctico de Gram (`gram.tests.test_parser`).
=============================================================================
Valida exhaustivamente todos los componentes de `gram.core.parser`:
  1. Parser: consumo físico de tokens, validación de tipos, errores PARSER_UNEXPECTED_TOKEN y PARSER_EARLY_EOF.
  2. ParseControl: cursores físico y virtual, lookahead no destructivo, matching y slicing.
  3. Checkpoints & Transacciones: instantáneas inmutables, backtracking y rollback atómico en fallos.
  4. Modo Bracket-Aware: supresión automática de NEWLINE/INDENT/DEDENT dentro de delimitadores y bracket_context.
  5. Exploración Virtual: future, peek_virtual, set_virtual_token, rollback y commit.
  6. Recuperación de errores: quit y synchronize.
  7. Telemetría y enrutamiento de errores: set_node, reset_node, scoped_node/use_node, note y fail.
  8. Interoperabilidad con TokenStream y Lexer.
"""
from __future__ import annotations

import unittest

from gram import config, errors
from gram.core.lexer import Token, TokenStream, TokenType, tokenize_stream
from gram.core.parser import Checkpoint, ParseControl, Parser
from gram.utilities.error import ParserError
from gram.utilities.info import Node, StackInfo


class BaseParserTestCase(unittest.TestCase):
    """Caso base con configuración silenciosa y ayudantes de tokens."""

    def setUp(self) -> None:
        self.old_hide_console = config.ERROR_HIDE_CONSOLE
        self.old_exit_on_error = config.ERROR_EXIT_ON_ERROR
        config.ERROR_HIDE_CONSOLE = True
        config.ERROR_EXIT_ON_ERROR = False

    def tearDown(self) -> None:
        config.ERROR_HIDE_CONSOLE = self.old_hide_console
        config.ERROR_EXIT_ON_ERROR = self.old_exit_on_error

    def make_token(
        self,
        token: Token,
        value: str | int | float = "",
        line: int = 1,
        col: int = 0,
    ) -> TokenType:
        """Crea una instancia concreta de TokenType."""
        return TokenType(token=token, value=value, line=line, col=col)

    def sample_tokens(self) -> list[TokenType]:
        """Flujo estándar de prueba: x = 10 \n y = 20 EOF."""
        return [
            self.make_token(Token.IDENT, "x", line=1, col=0),
            self.make_token(Token.ASSIGN, "=", line=1, col=2),
            self.make_token(Token.NUMBER, 10, line=1, col=4),
            self.make_token(Token.NEWLINE, "\n", line=1, col=6),
            self.make_token(Token.IDENT, "y", line=2, col=0),
            self.make_token(Token.ASSIGN, "=", line=2, col=2),
            self.make_token(Token.NUMBER, 20, line=2, col=4),
            self.make_token(Token.EOF, "<EOF>", line=2, col=6),
        ]


# ==============================================================================
# 1. CONSUMO FÍSICO Y NAVEGACIÓN
# ==============================================================================

class TestParserConsumption(BaseParserTestCase):
    """Pruebas para consume, consume_if, current, remaining y errores posicionales."""

    def test_basic_consumption_and_state(self) -> None:
        """Verifica conteo, remanente, cursor físico y consumo secuencial."""
        parser = Parser(self.sample_tokens())

        self.assertEqual(parser.count(), 8)
        self.assertEqual(parser.remaining(), 8)
        self.assertFalse(parser.is_eof())
        self.assertEqual(parser.current().token, Token.IDENT)
        self.assertEqual(parser.pos, 0)

        # Consumo con validación de tipo esperada
        tok_x = parser.consume(Token.IDENT)
        self.assertEqual(tok_x.value, "x")
        self.assertEqual(parser.pos, 1)
        self.assertEqual(parser.remaining(), 7)

        # Consumo con validación por cadena
        tok_eq = parser.consume("=")
        self.assertEqual(tok_eq.token, Token.ASSIGN)
        self.assertEqual(parser.pos, 2)

    def test_consume_if(self) -> None:
        """Verifica consumo condicional sin avance en caso negativo."""
        parser = Parser(self.sample_tokens())

        # consume_if exitoso
        tok_ident = parser.consume_if(Token.IDENT)
        self.assertIsNotNone(tok_ident)
        self.assertEqual(tok_ident.token, Token.IDENT)
        self.assertEqual(parser.pos, 1)

        # consume_if fallido: no mueve el cursor
        tok_none = parser.consume_if(Token.STRING, Token.KEYWORD)
        self.assertIsNone(tok_none)
        self.assertEqual(parser.pos, 1)

    def test_consume_unexpected_token_error(self) -> None:
        """Verifica que un token no coincidente lance ParserError estructurado."""
        parser = Parser(self.sample_tokens())
        with self.assertRaises(ParserError) as ctx:
            parser.consume(Token.NUMBER)  # Se esperaba NUMBER, hay IDENT
        self.assertEqual(ctx.exception.code, errors.PARSER_UNEXPECTED_TOKEN)

    def test_early_eof_error_on_empty_parser(self) -> None:
        """Verifica que intentar consumir de un parser vacío lance PARSER_EARLY_EOF."""
        empty_parser = Parser([])
        with self.assertRaises(ParserError) as ctx:
            empty_parser.consume()
        self.assertEqual(ctx.exception.code, errors.PARSER_EARLY_EOF)

        with self.assertRaises(ParserError) as ctx:
            empty_parser.current()
        self.assertEqual(ctx.exception.code, errors.PARSER_EARLY_EOF)

    def test_init_with_token_stream(self) -> None:
        """Verifica que el Parser acepte directamente una instancia de TokenStream."""
        stream = TokenStream(self.sample_tokens())
        parser = Parser(stream)
        self.assertEqual(parser.count(), 8)
        self.assertEqual(parser.consume().value, "x")


# ==============================================================================
# 2. LOOKAHEAD Y EXPLORACIÓN NO DESTRUCTIVA
# ==============================================================================

class TestParserLookahead(BaseParserTestCase):
    """Pruebas de peek, peek_token, lookahead, matches y slice."""

    def test_peek_and_lookahead(self) -> None:
        """Verifica inspección anticipada sin alterar los cursores."""
        parser = Parser(self.sample_tokens())

        peek0 = parser.peek(0)
        self.assertIsNotNone(peek0)
        self.assertEqual(peek0.token, Token.IDENT)

        peek1 = parser.peek(1)
        self.assertIsNotNone(peek1)
        self.assertEqual(peek1.token, Token.ASSIGN)

        self.assertEqual(parser.peek_token(2), Token.NUMBER)
        self.assertEqual(parser.pos, 0)  # Cursor físico intacto

        # Lookahead de 3 tokens
        three = parser.lookahead(3)
        self.assertEqual(len(three), 3)
        self.assertEqual([t.token for t in three], [Token.IDENT, Token.ASSIGN, Token.NUMBER])

    def test_matches_and_slice(self) -> None:
        """Verifica matches con tokens/cadenas y extracción de subsecuencias con slice."""
        parser = Parser(self.sample_tokens())

        self.assertTrue(parser.matches(Token.IDENT, Token.KEYWORD, offset=0))
        self.assertTrue(parser.matches("x", offset=0))
        self.assertFalse(parser.matches(Token.STRING, offset=0))

        # Slice
        tokens_slice = parser.slice(0, 3)
        self.assertEqual(len(tokens_slice), 3)
        self.assertEqual([t.value for t in tokens_slice], ["x", "=", 10])


# ==============================================================================
# 3. EXPLORACIÓN VIRTUAL (FUTURE, COMMIT, ROLLBACK)
# ==============================================================================

class TestParserVirtualExploration(BaseParserTestCase):
    """Pruebas para el cursor virtual independiente."""

    def test_virtual_traversal_and_rollback(self) -> None:
        """Verifica avance con future() y descarte con rollback()."""
        parser = Parser(self.sample_tokens())

        v1 = parser.future()
        self.assertIsNotNone(v1)
        self.assertEqual(v1.value, "x")

        v2 = parser.future()
        self.assertIsNotNone(v2)
        self.assertEqual(v2.value, "=")

        self.assertEqual(parser.virtual_pos, 2)
        self.assertEqual(parser.pos, 0)  # Cursor físico no se movió

        parser.rollback()
        self.assertEqual(parser.virtual_pos, 0)

    def test_virtual_commit(self) -> None:
        """Verifica que commit() sincronice el cursor físico consumiendo lo explorado."""
        parser = Parser(self.sample_tokens())

        parser.future()
        parser.future()
        consumed = parser.commit()

        self.assertEqual(len(consumed), 2)
        self.assertEqual(parser.pos, 2)
        self.assertEqual(parser.virtual_pos, 2)

    def test_set_virtual_token(self) -> None:
        """Verifica ajuste manual y valores especiales (-1 y -2) en set_virtual_token."""
        parser = Parser(self.sample_tokens())
        parser.advance(3)  # pos = 3

        # -1 -> último token
        parser.set_virtual_token(-1)
        self.assertEqual(parser.virtual_pos, 7)

        # -2 -> sincronizar con pos físico
        parser.set_virtual_token(-2)
        self.assertEqual(parser.virtual_pos, 3)


# ==============================================================================
# 4. CHECKPOINTS Y TRANSACCIONES
# ==============================================================================

class TestParserCheckpoints(BaseParserTestCase):
    """Pruebas de Checkpoint, savepoint, restore y transaction."""

    def test_savepoint_and_restore(self) -> None:
        """Verifica guardado y restauración manual de estado."""
        parser = Parser(self.sample_tokens())

        cp = parser.savepoint()
        self.assertIsInstance(cp, Checkpoint)
        self.assertEqual(cp.pos, 0)

        parser.consume()
        parser.consume()
        self.assertEqual(parser.pos, 2)

        parser.restore(cp)
        self.assertEqual(parser.pos, 0)

    def test_transaction_success(self) -> None:
        """Verifica que una transacción exitosa conserve el avance."""
        parser = Parser(self.sample_tokens())

        with parser.transaction():
            parser.consume(Token.IDENT)
            parser.consume(Token.ASSIGN)

        self.assertEqual(parser.pos, 2)

    def test_transaction_failure_rollback(self) -> None:
        """Verifica que una transacción fallida haga rollback automático al punto inicial."""
        parser = Parser(self.sample_tokens())
        parser.advance(2)  # pos inicial = 2

        with self.assertRaises(RuntimeError):
            with parser.transaction():
                parser.consume(Token.NUMBER)
                self.assertEqual(parser.pos, 3)
                raise RuntimeError("Fallo deliberado para forzar rollback")

        self.assertEqual(parser.pos, 2)  # Restaurado a 2


# ==============================================================================
# 5. MODO BRACKET-AWARE (DELIMITADORES ABIERTOS)
# ==============================================================================

class TestParserBracketAware(BaseParserTestCase):
    """Pruebas de supresión de NEWLINE, INDENT y DEDENT dentro de brackets."""

    def test_bracket_aware_skipping(self) -> None:
        """Verifica que dentro de brackets se omitan automáticamente tokens estructurales."""
        bracket_tokens = [
            self.make_token(Token.LPAREN, "("),
            self.make_token(Token.NEWLINE, "\n"),
            self.make_token(Token.INDENT, 4),
            self.make_token(Token.IDENT, "a"),
            self.make_token(Token.NEWLINE, "\n"),
            self.make_token(Token.IDENT, "b"),
            self.make_token(Token.DEDENT, 0),
            self.make_token(Token.RPAREN, ")"),
            self.make_token(Token.NEWLINE, "\n"),
            self.make_token(Token.IDENT, "end"),
            self.make_token(Token.EOF, "<EOF>"),
        ]

        parser = Parser(bracket_tokens)

        tok_open = parser.consume(Token.LPAREN)
        self.assertEqual(tok_open.token, Token.LPAREN)
        self.assertFalse(parser.control.in_bracket)

        # Entrar al modo delimitado
        parser.enter_bracket()
        self.assertTrue(parser.control.in_bracket)
        parser.control._skip_whitespace()

        tok_a = parser.consume(Token.IDENT)
        self.assertEqual(tok_a.value, "a")

        # Al consumir 'a', _skip_whitespace salta automáticamente el NEWLINE
        tok_b = parser.consume(Token.IDENT)
        self.assertEqual(tok_b.value, "b")

        # Salir del modo delimitado antes de consumir RPAREN
        parser.exit_bracket()
        self.assertFalse(parser.control.in_bracket)

        if parser.current().token == Token.DEDENT:
            parser.consume(Token.DEDENT)

        tok_close = parser.consume(Token.RPAREN)
        self.assertEqual(tok_close.token, Token.RPAREN)

        # Fuera del delimitador, el NEWLINE posterior NO se ignora
        tok_nl = parser.consume(Token.NEWLINE)
        self.assertEqual(tok_nl.token, Token.NEWLINE)

        tok_end = parser.consume(Token.IDENT)
        self.assertEqual(tok_end.value, "end")

    def test_bracket_context_manager(self) -> None:
        """Verifica el gestor de contexto bracket_context()."""
        parser = Parser(self.sample_tokens())
        self.assertFalse(parser.control.in_bracket)

        with parser.bracket_context():
            self.assertTrue(parser.control.in_bracket)
            self.assertEqual(parser.control.bracket_depth, 1)

        self.assertFalse(parser.control.in_bracket)
        self.assertEqual(parser.control.bracket_depth, 0)


# ==============================================================================
# 6. RECUPERACIÓN Y SINCRONIZACIÓN
# ==============================================================================

class TestParserRecovery(BaseParserTestCase):
    """Pruebas para quit y synchronize."""

    def test_quit_removes_tokens(self) -> None:
        """Verifica que quit elimine todos los tokens de un tipo indicado."""
        tokens_with_comments = [
            self.make_token(Token.IDENT, "x"),
            self.make_token(Token.COMMENT, "# nota"),
            self.make_token(Token.ASSIGN, "="),
            self.make_token(Token.COMMENT, "# otra"),
            self.make_token(Token.NUMBER, 42),
        ]
        parser = Parser(tokens_with_comments)
        removed = parser.quit(Token.COMMENT)
        self.assertEqual(removed, 2)
        self.assertEqual(parser.count(), 3)
        self.assertEqual([t.token for t in parser.tokens], [Token.IDENT, Token.ASSIGN, Token.NUMBER])

    def test_synchronize_until_delimiter(self) -> None:
        """Verifica que synchronize descarte tokens hasta un delimitador de sincronización."""
        corrupted_tokens = [
            self.make_token(Token.IDENT, "x"),
            self.make_token(Token.PLUS, "+"),
            self.make_token(Token.STAR, "*"),  # Error sintáctico
            self.make_token(Token.NEWLINE, "\n"),  # Delimitador seguro
            self.make_token(Token.IDENT, "y"),
            self.make_token(Token.EOF, "<EOF>"),
        ]
        parser = Parser(corrupted_tokens)
        parser.advance(1)  # Pos en '+'

        discarded = parser.synchronize(sync_tokens=(Token.NEWLINE, Token.EOF))
        self.assertEqual([t.token for t in discarded], [Token.PLUS, Token.STAR])
        self.assertEqual(parser.current().token, Token.NEWLINE)


# ==============================================================================
# 7. TELEMETRÍA Y ENRUTAMIENTO DE NODOS
# ==============================================================================

class TestParserTelemetry(BaseParserTestCase):
    """Pruebas de redirección de nodos, scoped_node, notas y fail."""

    def test_telemetry_node_routing(self) -> None:
        """Verifica asignación y restauración de nodos de telemetría."""
        parser = Parser(self.sample_tokens())
        custom_node = Node("CUSTOM-NODE", "Nodo personalizado de regla", priority=1)

        parser.set_node(custom_node)
        self.assertIs(parser.node, custom_node)

        parser.reset_node()
        self.assertIsNot(parser.node, custom_node)

    def test_scoped_node_context(self) -> None:
        """Verifica redirección temporal mediante use_node."""
        parser = Parser(self.sample_tokens())
        temp_node = Node("TEMP-NODE", "Nodo temporal", priority=1)

        default_node = parser.node
        with parser.use_node(temp_node):
            self.assertIs(parser.node, temp_node)
            parser.note("Mensaje de prueba en nodo temporal")

        self.assertIs(parser.node, default_node)


if __name__ == "__main__":
    unittest.main()
