"""
Pruebas Unitarias del Árbol de Sintaxis Abstracta (`gram.tests.test_ast`).
==========================================================================
Valida exhaustivamente todos los componentes de `gram.core.ast` y `gram.core.watcher`:
  1. Watcher, FileWatcher y PluginWatcher: monitoreo de combinadores, secuencias y archivos.
  2. ASTNode: jerarquía de nodos, propiedades, búsqueda, recorrido walk, formato y serialización.
  3. ASTProgram: inspección por niveles, estadísticas, bloques, volcado y exportación (.txt / .json).
  4. ASTAnalyzer: validación de gramática (PROGRAM, DECLARATION, Ref), recolección de comentarios,
     rastreo de niveles de indentación y parsing end-to-end con Parser.parse.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gram import config, errors
from gram.core.ast import ASTAnalyzer, ASTNode, ASTProgram, Identifier, generate_file_tree
from gram.core.combinators import (
    Alt,
    Many,
    MatchKeyword,
    MatchSymbol,
    MatchToken,
    Opt,
    Ref,
    Seq,
    Some,
    create_rule,
)
from gram.core.combinators.defaults import (
    BLOCK,
    DECLARATION,
    ENDLINE,
    INDENT_BLOCK,
    PASS,
    PROGRAM,
)
from gram.core.combinators.item import Item, ItemResult
from gram.core.lexer import Token, TokenType, words
from gram.core.parser import Parser
from gram.core.watcher import FileWatcher, PluginWatcher, Watcher
from gram.utilities.error import ParserError


class BaseASTTestCase(unittest.TestCase):
    """Caso base con supresión de alertas en consola y generadores de tokens."""

    def setUp(self) -> None:
        self.old_hide_console = config.ERROR_HIDE_CONSOLE
        self.old_exit_on_error = config.ERROR_EXIT_ON_ERROR
        config.ERROR_HIDE_CONSOLE = True
        config.ERROR_EXIT_ON_ERROR = False
        words.add_keyword("let")
        words.add_keyword("def")
        words.add_keyword("fn")

    def tearDown(self) -> None:
        config.ERROR_HIDE_CONSOLE = self.old_hide_console
        config.ERROR_EXIT_ON_ERROR = self.old_exit_on_error
        words.clear_all()

    def make_token(
        self,
        token: Token,
        value: str | int | float = "",
        line: int = 1,
        col: int = 0,
    ) -> TokenType:
        """Crea una instancia concreta de TokenType."""
        return TokenType(token=token, value=value, line=line, col=col)


class WatcherTestCase(BaseASTTestCase):
    """Pruebas para el sistema de telemetría y monitoreo Watcher, FileWatcher y PluginWatcher."""

    def test_watcher_lifecycle(self) -> None:
        watcher = Watcher()
        kw = MatchKeyword("let")
        tok = self.make_token(Token.KEYWORD, "let")

        watcher.enter_combinator(kw, tok)
        self.assertEqual(watcher.depth, 1)
        self.assertEqual(watcher.current_combinator, kw)
        self.assertEqual(watcher.current_token, tok)

        seq = Seq(kw)
        watcher.enter_sequence(seq, total_steps=3)
        self.assertEqual(watcher.sequence_step, 0)
        watcher.step_sequence()
        self.assertEqual(watcher.sequence_step, 1)
        watcher.exit_sequence()

        watcher.exit_combinator()
        self.assertEqual(watcher.depth, 0)
        self.assertIsNone(watcher.current_combinator)

    def test_watcher_snapshot_and_where_am_i(self) -> None:
        watcher = Watcher()
        kw = MatchKeyword("fn")
        tok = self.make_token(Token.KEYWORD, "fn")
        watcher.enter_combinator(kw, tok)

        snap = watcher.snapshot()
        self.assertIn("combinator", snap)
        self.assertIn("depth", snap)
        self.assertEqual(snap["depth"], 1)

        where = watcher.where_am_i()
        self.assertIn("fn", where)

        path = watcher.active_path()
        self.assertEqual(len(path), 1)

        watcher.exit_combinator()
        self.assertEqual(watcher.active_path(), [])

    def test_watcher_error_recording(self) -> None:
        watcher = Watcher()
        self.assertFalse(watcher.has_errors)
        watcher.record_error(Exception("test error"))
        self.assertTrue(watcher.has_errors)
        self.assertEqual(len(watcher.errors), 1)
        watcher.clear_errors()
        self.assertFalse(watcher.has_errors)

    def test_file_watcher(self) -> None:
        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".gram") as tmp:
            tmp.write("initial content")
            tmp_path = tmp.name

        try:
            fw = FileWatcher(tmp_path)
            self.assertIn(Path(tmp_path).resolve(), fw.paths)

            # Initially no modifications
            changes = fw.poll_once()
            self.assertEqual(changes["modified"], [])

            # Modify file
            Path(tmp_path).write_text("modified content", encoding="utf-8")
            changes = fw.poll_once()
            self.assertIn(Path(tmp_path).resolve(), changes["modified"])
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_plugin_watcher(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            plugin_dir = Path(tmp_dir) / "test_plugin"
            plugin_dir.mkdir()
            manifest = plugin_dir / "manifest.json"
            manifest.write_text('{"name": "test_plugin"}', encoding="utf-8")
            code_file = plugin_dir / "plugin.py"
            code_file.write_text("x = 1", encoding="utf-8")

            pw = PluginWatcher(paths=[tmp_dir])
            root = pw._find_plugin_root(code_file)
            self.assertEqual(root, plugin_dir)


class ASTNodeTestCase(BaseASTTestCase):
    """Pruebas para la estructura fundamental del nodo ASTNode."""

    def test_node_initialization_and_properties(self) -> None:
        node = ASTNode(name="VAR_DECL", code=101, level=0)
        self.assertEqual(node.name, "VAR_DECL")
        self.assertEqual(node.code, 101)
        self.assertEqual(node.level, 0)
        self.assertFalse(node.is_block)
        self.assertFalse(node.has_children)
        self.assertEqual(node.child_count, 0)
        self.assertEqual(node.depth, 0)
        self.assertIs(node.root, node)
        self.assertEqual(node.siblings, [])
        self.assertEqual(node.index_in_parent, -1)

    def test_node_values_and_identifiers(self) -> None:
        tok_id = self.make_token(Token.IDENT, "x")
        tok_eq = self.make_token(Token.ASSIGN, "=")
        tok_num = self.make_token(Token.NUMBER, 42)
        node = ASTNode(name="ASSIGN", tokens=[tok_id, tok_eq, tok_num])

        self.assertEqual(node.values, ["x", 42])
        self.assertIsInstance(node.values[0], Identifier)
        self.assertEqual(node.values[0].name, "x")
        self.assertEqual(node.value, "x")
        self.assertEqual(node.identifiers, ["x"])

    def test_identifier_value_is_distinct_from_string_literal(self) -> None:
        identifier_node = ASTNode(
            name="IDENTIFIER",
            tokens=[self.make_token(Token.IDENT, "Hola")],
        )
        string_node = ASTNode(
            name="STRING",
            tokens=[self.make_token(Token.STRING, "Hola")],
        )

        identifier, = identifier_node.values
        string_literal, = string_node.values

        self.assertIsInstance(identifier, Identifier)
        self.assertEqual(identifier, string_literal)
        self.assertNotIsInstance(string_literal, Identifier)

    def test_node_hierarchy_and_levels(self) -> None:
        parent = ASTNode(name="FUNC_DEF", level=0)
        child1 = ASTNode(name="PARAMS", level=0)  # level <= parent -> should become level 1
        child2 = ASTNode(name="BODY", level=1)

        parent.add_child(child1)
        parent.add_child(child2)

        self.assertTrue(parent.is_block)
        self.assertEqual(parent.child_count, 2)
        self.assertEqual(child1.level, 1)
        self.assertIs(child1.parent, parent)
        self.assertIs(child1.root, parent)
        self.assertEqual(child1.index_in_parent, 0)
        self.assertEqual(child2.index_in_parent, 1)
        self.assertEqual(child1.siblings, [child2])

        # remove child
        parent.remove_child(child1)
        self.assertEqual(parent.child_count, 1)
        self.assertIsNone(child1.parent)

    def test_node_queries_by_level_find_and_walk(self) -> None:
        root = ASTNode(name="PROGRAM", level=0)
        stmt1 = ASTNode(name="STMT", level=0)
        stmt2 = ASTNode(name="BLOCK", level=0)
        inner = ASTNode(name="INNER_STMT", level=1)

        root.add_child(stmt1)
        root.add_child(stmt2)
        stmt2.add_child(inner)

        self.assertEqual(len(root.by_level(0)), 1)  # root itself
        self.assertEqual(len(root.by_level(1)), 2)  # stmt1, stmt2
        self.assertEqual(len(root.by_level(2)), 1)  # inner

        # find and find_first
        found = root.find("INNER_STMT")
        self.assertEqual(len(found), 1)
        self.assertIs(found[0], inner)
        self.assertIs(root.find_first("INNER_STMT"), inner)
        self.assertIsNone(root.find_first("NON_EXISTENT"))

        # walk traversal
        nodes = list(root.walk(order="pre"))
        self.assertEqual([n.name for n in nodes], ["PROGRAM", "STMT", "BLOCK", "INNER_STMT"])

        nodes_post = list(root.walk(order="post"))
        self.assertEqual(nodes_post[-1].name, "PROGRAM")

    def test_node_to_dict_and_format(self) -> None:
        node = ASTNode(
            name="DECL",
            code=10,
            level=0,
            tokens=[self.make_token(Token.IDENT, "var_a", line=1, col=2)],
        )
        data = node.to_dict()
        self.assertEqual(data["name"], "DECL")
        self.assertEqual(data["code"], 10)
        self.assertEqual(data["level"], 0)
        self.assertEqual(len(data["tokens"]), 1)
        self.assertEqual(data["tokens"][0]["value"], "var_a")

        formatted = node.format()
        self.assertIn("DECL", formatted)
        self.assertIn("var_a", formatted)

    def test_from_rule_result(self) -> None:
        class DummyRule:
            name = "TEST_RULE"
            code = 999

        t1 = self.make_token(Token.KEYWORD, "let")
        t2 = self.make_token(Token.IDENT, "foo")
        sub_node = ASTNode(name="EXPR", tokens=[self.make_token(Token.NUMBER, 123)])

        # Single token
        node1 = ASTNode.from_rule_result(DummyRule, t1, level=0)
        self.assertEqual(node1.name, "TEST_RULE")
        self.assertEqual(node1.tokens, [t1])

        # Nested list of tokens and nodes
        node2 = ASTNode.from_rule_result(DummyRule, [t1, t2, sub_node], level=0)
        self.assertEqual(node2.tokens, [t1, t2])
        self.assertEqual(len(node2.children), 1)
        self.assertEqual(node2.children[0].name, "EXPR")

        # ItemResult
        it = ItemResult([t1, t2])
        node3 = ASTNode.from_rule_result(DummyRule, it, level=0)
        self.assertEqual(len(node3.children), 1)
        self.assertEqual(node3.children[0].name, "ITEM")
        self.assertEqual(node3.children[0].tokens, [t1, t2])


class ASTProgramTestCase(BaseASTTestCase):
    """Pruebas para el nodo raíz ASTProgram y utilidades de exportación."""

    def setUp(self) -> None:
        super().setUp()
        self.stmt1 = ASTNode(
            name="VAR_DECL",
            tokens=[self.make_token(Token.IDENT, "a"), self.make_token(Token.NUMBER, 1)],
            level=0,
        )
        self.block_stmt = ASTNode(name="IF_BLOCK", level=0)
        self.inner_stmt = ASTNode(
            name="VAR_DECL",
            tokens=[self.make_token(Token.IDENT, "b"), self.make_token(Token.NUMBER, 2)],
            level=1,
        )
        self.block_stmt.add_child(self.inner_stmt)
        self.comment_tok = self.make_token(Token.COMMENT, "# test comment", line=1, col=0)

        self.program = ASTProgram(
            body=[self.stmt1, self.block_stmt],
            comments=[self.comment_tok],
        )

    def test_program_properties(self) -> None:
        self.assertEqual(len(self.program.declarations), 2)
        self.assertEqual(len(self.program.comments), 1)
        self.assertEqual(len(self.program.blocks()), 1)
        self.assertIn(0, self.program.levels())
        self.assertIn(1, self.program.levels())
        self.assertGreaterEqual(self.program.max_depth, 1)
        self.assertEqual(self.program.total_nodes, 3)

        stats = self.program.stats
        self.assertEqual(stats["total_nodes"], 3)
        self.assertEqual(stats["total_declarations"], 2)
        self.assertEqual(stats["total_comments"], 1)

    def test_program_container_interface(self) -> None:
        self.assertEqual(len(self.program), 2)
        self.assertIs(self.program[0], self.stmt1)
        self.assertIs(self.program[1], self.block_stmt)
        stmts = list(self.program)
        self.assertEqual(len(stmts), 2)

    def test_program_search_and_queries(self) -> None:
        results = self.program.find("VAR_DECL")
        self.assertEqual(len(results), 2)
        self.assertIs(self.program.find_first("IF_BLOCK"), self.block_stmt)
        self.assertIsNone(self.program.find_first("WHILE_BLOCK"))

        level0_nodes = self.program.by_level(0)
        self.assertEqual(len(level0_nodes), 2)

    def test_program_walk_can_filter_by_level(self) -> None:
        self.assertEqual(
            list(self.program.walk(0)),
            [self.stmt1, self.block_stmt],
        )
        self.assertEqual(
            list(self.program.walk(1)),
            [self.inner_stmt],
        )
        self.assertEqual(
            list(self.program.walk("post")),
            [self.stmt1, self.inner_stmt, self.block_stmt],
        )

    def test_program_serialization_and_dumps(self) -> None:
        dump_str = self.program.dump()
        self.assertIn("ASTProgram", dump_str)
        self.assertIn("VAR_DECL", dump_str)

        dec_tree = self.program.generate_decorated_tree()
        self.assertIn("ASTProgram", dec_tree)
        self.assertIn("COMENTARIOS", dec_tree)
        self.assertIn("# test comment", dec_tree)

        json_data = self.program.generate_json_tree()
        self.assertIn("body", json_data)
        self.assertIn("comments", json_data)
        self.assertEqual(len(json_data["body"]), 2)
        self.assertEqual(len(json_data["comments"]), 1)

    def test_program_generate_file_tree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            txt_path = Path(tmp_dir) / "ast_dump.txt"
            json_path = Path(tmp_dir) / "ast_dump.json"

            # Export to .txt
            txt_res = self.program.generate_file_tree(txt_path)
            self.assertTrue(txt_path.exists())
            self.assertIn("ASTProgram", txt_path.read_text(encoding="utf-8"))
            self.assertIsInstance(txt_res, str)

            # Export to .json
            json_res = self.program.generate_file_tree(json_path)
            self.assertTrue(json_path.exists())
            loaded = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertIn("body", loaded)
            self.assertIsInstance(json_res, dict)

            # Top-level helper
            helper_txt = Path(tmp_dir) / "helper.txt"
            generate_file_tree(self.program, helper_txt)
            self.assertTrue(helper_txt.exists())

            # Swapped args
            helper_json = Path(tmp_dir) / "helper.json"
            generate_file_tree(helper_json, self.program)
            self.assertTrue(helper_json.exists())

            with self.assertRaises(TypeError):
                generate_file_tree("invalid", "invalid")


class ASTAnalyzerTestCase(BaseASTTestCase):
    """Pruebas para el motor de construcción ASTAnalyzer y validaciones de gramática."""

    def test_missing_program_rule_raises(self) -> None:
        parser = Parser([])
        # Grammar with no PROGRAM rule
        grammar = {DECLARATION: Alt(Ref("VAR_DECL"))}
        analyzer = ASTAnalyzer(parser, grammar)

        with self.assertRaises(ParserError) as ctx:
            analyzer.process()
        self.assertEqual(ctx.exception.code, errors.PROGRAM_RULE_NOT_FOUND)

    def test_missing_declaration_rule_raises(self) -> None:
        parser = Parser([])
        # Grammar with PROGRAM but no DECLARATION rule
        grammar = {PROGRAM: Many(Ref("VAR_DECL"))}
        analyzer = ASTAnalyzer(parser, grammar)

        with self.assertRaises(ParserError) as ctx:
            analyzer.process()
        self.assertEqual(ctx.exception.code, errors.DECLARATION_RULE_NOT_FOUND)

    def test_invalid_declaration_type_raises(self) -> None:
        parser = Parser([])
        # DECLARATION is Seq instead of Alt
        grammar = {
            PROGRAM: Many(Ref("DECLARATION")),
            DECLARATION: Seq(Ref("VAR_DECL")),
        }
        analyzer = ASTAnalyzer(parser, grammar)

        with self.assertRaises(ParserError) as ctx:
            analyzer.process()
        self.assertEqual(ctx.exception.code, errors.DECLARATOR_INVALID_TYPE)

    def test_invalid_declaration_element_raises(self) -> None:
        parser = Parser([])
        # DECLARATION contains a raw MatchKeyword instead of Ref
        grammar = {
            PROGRAM: Many(Ref("DECLARATION")),
            DECLARATION: Alt(MatchKeyword("let")),
        }
        analyzer = ASTAnalyzer(parser, grammar)

        with self.assertRaises(ParserError) as ctx:
            analyzer.process()
        self.assertEqual(ctx.exception.code, errors.DECLARATOR_INVALID_ELEMENT)

    def test_comment_and_trash_handling(self) -> None:
        tokens = [
            self.make_token(Token.COMMENT, "# header comment"),
            self.make_token(Token.NEWLINE, "\n"),
            self.make_token(Token.EMPTY_LINE, "\n"),
            self.make_token(Token.EOF, "<EOF>"),
        ]
        parser = Parser(tokens)

        VAR_RULE = create_rule("VAR_DECL", 100, MatchToken(Token.IDENT))
        grammar = {
            PROGRAM: Many(Ref(DECLARATION)),
            DECLARATION: Alt(Ref(VAR_RULE)),
            VAR_RULE: MatchToken(Token.IDENT),
        }

        analyzer = ASTAnalyzer(parser, grammar)
        ast_prog = analyzer.process()

        self.assertEqual(len(ast_prog.body), 0)
        self.assertEqual(len(ast_prog.comments), 1)
        self.assertEqual(ast_prog.comments[0].value, "# header comment")

    def test_end_to_end_simple_assignment(self) -> None:
        # Input: let x = 42
        tokens = [
            self.make_token(Token.KEYWORD, "let"),
            self.make_token(Token.IDENT, "x"),
            self.make_token(Token.ASSIGN, "="),
            self.make_token(Token.NUMBER, 42),
            self.make_token(Token.EOF, "<EOF>"),
        ]
        parser = Parser(tokens)

        LET_DECL = create_rule(
            "LET_DECL",
            200,
            Seq(
                MatchKeyword("let"),
                MatchToken(Token.IDENT),
                MatchSymbol("="),
                MatchToken(Token.NUMBER),
            ),
        )

        grammar = {
            PROGRAM: Many(Ref(DECLARATION)),
            DECLARATION: Alt(Ref(LET_DECL)),
            LET_DECL: Seq(
                MatchKeyword("let"),
                MatchToken(Token.IDENT),
                MatchSymbol("="),
                MatchToken(Token.NUMBER),
            ),
        }

        program = parser.parse(grammar)

        self.assertIsInstance(program, ASTProgram)
        self.assertEqual(len(program.declarations), 1)
        decl = program.declarations[0]
        self.assertEqual(decl.name, "LET_DECL")
        self.assertEqual(decl.level, 0)
        self.assertEqual(decl.identifiers, ["x"])
        self.assertEqual(decl.numbers, [42])
        self.assertEqual(decl.values, ["let", "x", 42])

    def test_end_to_end_nested_blocks_and_indentation(self) -> None:
        # Input:
        # def foo():
        #     let y = 10
        tokens = [
            self.make_token(Token.KEYWORD, "def"),
            self.make_token(Token.IDENT, "foo"),
            self.make_token(Token.LPAREN, "("),
            self.make_token(Token.RPAREN, ")"),
            self.make_token(Token.COLON, ":"),
            self.make_token(Token.INDENT, "    "),
            self.make_token(Token.KEYWORD, "let"),
            self.make_token(Token.IDENT, "y"),
            self.make_token(Token.ASSIGN, "="),
            self.make_token(Token.NUMBER, 10),
            self.make_token(Token.DEDENT, ""),
            self.make_token(Token.EOF, "<EOF>"),
        ]
        parser = Parser(tokens)

        LET_STMT = create_rule(
            "LET_STMT",
            301,
            Seq(
                MatchKeyword("let"),
                MatchToken(Token.IDENT),
                MatchSymbol("="),
                MatchToken(Token.NUMBER),
            ),
        )

        FUNC_DEF = create_rule(
            "FUNC_DEF",
            300,
            Seq(
                MatchKeyword("def"),
                MatchToken(Token.IDENT),
                MatchToken(Token.LPAREN),
                MatchToken(Token.RPAREN),
                MatchToken(Token.COLON),
                MatchToken(Token.INDENT),
                Ref(LET_STMT),
                MatchToken(Token.DEDENT),
            ),
        )

        grammar = {
            PROGRAM: Many(Ref(DECLARATION)),
            DECLARATION: Alt(Ref(FUNC_DEF), Ref(LET_STMT)),
            FUNC_DEF: Seq(
                MatchKeyword("def"),
                MatchToken(Token.IDENT),
                MatchToken(Token.LPAREN),
                MatchToken(Token.RPAREN),
                MatchToken(Token.COLON),
                MatchToken(Token.INDENT),
                Ref(LET_STMT),
                MatchToken(Token.DEDENT),
            ),
            LET_STMT: Seq(
                MatchKeyword("let"),
                MatchToken(Token.IDENT),
                MatchSymbol("="),
                MatchToken(Token.NUMBER),
            ),
        }

        program = parser.parse(grammar)

        self.assertIsInstance(program, ASTProgram)
        self.assertEqual(len(program.declarations), 1)
        func_node = program.declarations[0]
        self.assertEqual(func_node.name, "FUNC_DEF")
        self.assertEqual(func_node.level, 0)
        self.assertTrue(func_node.is_block)
        self.assertEqual(len(func_node.children), 1)

        inner = func_node.children[0]
        self.assertEqual(inner.name, "LET_STMT")
        self.assertEqual(inner.level, 1)
        self.assertEqual(inner.identifiers, ["y"])
        self.assertEqual(inner.numbers, [10])
        self.assertEqual(inner.values, ["let", "y", 10])


if __name__ == "__main__":
    unittest.main()
