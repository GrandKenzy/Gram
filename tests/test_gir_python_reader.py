"""
Tests for Native Python Gram Binary IR (GIR) Reader and Tree Walker (`tests/test_gir_python_reader.py`).
=======================================================================================================
Verifies zero-dependency decoding of `.gir` buffers, OOP tree navigation,
preorder/postorder walking, filtering, and error validation.
"""
from __future__ import annotations

import pathlib
import shutil
import struct
import subprocess
import tempfile
import unittest

from gram import ir, sessions
from gram.core.combinators import MatchKeyword, MatchToken, RuleItem, Seq
from gram.core.lexer import Token


class TestGirPythonReader(unittest.TestCase):
    def setUp(self) -> None:
        if shutil.which("gcc") is None:
            self.skipTest("GCC is required to generate binary .gir files for testing")

    def _compile_grammar_and_produce_gir(
        self,
        source_code: str,
    ) -> tuple[bytes, int, tempfile.TemporaryDirectory]:
        class ItemRule(RuleItem):
            nodeable = True
            entrypoint = Seq(
                MatchKeyword("def"),
                MatchToken(Token.IDENT),
                MatchKeyword("end"),
            )
            rule = entrypoint

        session = sessions.Session("GirReaderTestSession", "Some")
        session.add_keyword("def")
        session.add_keyword("end")
        session.entrypoint = ItemRule

        tmp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        out_dir = pathlib.Path(tmp_dir.name)
        manifest = session.export_c_parser(out_dir, emit_driver=True, emit_cli=True)
        grammar_id = int(manifest["grammar_id"], 16)

        proj_root = pathlib.Path(__file__).resolve().parent.parent
        native_inc = proj_root / "native" / "gram_lexer" / "include"
        native_src = proj_root / "native" / "gram_lexer" / "src"

        sources = [
            "gram_ast.c", "gram_parser.c", "gram_ir.c", "gram_driver.c",
            "gram_lexer_keywords.c", "gram_lexer_symbols.c", "gram_lexer_groups.c",
        ]
        common = [str(out_dir / name) for name in sources] + [
            str(native_src / name)
            for name in (
                "lexer.c", "indentation.c", "numbers.c", "strings.c",
                "symbols.c", "utf8.c", "diagnostics_lite.c",
            )
        ]
        cli_exe = out_dir / "gram_cli.exe"
        flags = [
            "gcc", "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
            f"-I{native_inc}", f"-I{native_src}", f"-I{out_dir}",
            str(out_dir / "gram_cli.c"), *common, "-o", str(cli_exe),
        ]
        subprocess.run(flags, check=True, capture_output=True, text=True)

        src_file = out_dir / "input.src"
        src_file.write_text(source_code, encoding="utf-8")
        gir_file = out_dir / "output.gir"

        cmd = [str(cli_exe), "compile", str(src_file), "-o", str(gir_file)]
        res = subprocess.run(cmd, check=True, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)

        gir_bytes = gir_file.read_bytes()
        return gir_bytes, grammar_id, tmp_dir

    def test_load_gir_from_bytes_and_file(self) -> None:
        source_code = "def my_function end"
        gir_bytes, grammar_id, tmp = self._compile_grammar_and_produce_gir(source_code)
        with tmp:
            gir_path = pathlib.Path(tmp.name) / "output.gir"

            # 1. Load from file path
            view_from_file = ir.load_gir(gir_path, source_text=source_code)
            self.assertIsInstance(view_from_file, ir.GirView)
            self.assertEqual(view_from_file.header.magic, b"GIR\0")
            self.assertEqual(view_from_file.header.version, (1, 0))
            self.assertTrue(view_from_file.matches_grammar(grammar_id))
            self.assertTrue(view_from_file.matches_source(source_code))

            # 2. Load from raw bytes
            view_from_bytes = ir.load(gir_bytes, source_text=source_code)
            self.assertIsInstance(view_from_bytes, ir.GirView)
            self.assertEqual(view_from_bytes.header.grammar_id, grammar_id)
            self.assertEqual(view_from_bytes.node_count, view_from_file.node_count)

    def test_tree_navigation_and_properties(self) -> None:
        source_code = "def hello end"
        gir_bytes, _, tmp = self._compile_grammar_and_produce_gir(source_code)
        with tmp:
            view = ir.load_gir(gir_bytes, source_text=source_code)
            root = view.root

            self.assertIsNotNone(root)
            self.assertEqual(root.kind_name, "ARRAY")
            self.assertTrue(root.is_array)
            self.assertFalse(root.is_terminal)
            self.assertEqual(root.depth, 0)
            self.assertIsNone(root.parent)

            # Check rule child
            self.assertEqual(len(root.children), 1)
            item_rule = root.children[0]
            self.assertEqual(item_rule.kind_name, "ItemRule")
            self.assertTrue(item_rule.is_rule)
            self.assertEqual(item_rule.parent, root)
            self.assertEqual(item_rule.depth, 1)

            # Check grandchildren
            children = item_rule.children
            self.assertEqual(len(children), 3)

            # Child 0: "def" keyword
            c0 = children[0]
            self.assertTrue(c0.is_terminal)
            self.assertEqual(c0.kind_name, "KEYWORD")
            self.assertEqual(c0.text, "def")
            self.assertEqual(c0.parent, item_rule)
            self.assertEqual(c0.depth, 2)

            # Child 1: "hello" identifier
            c1 = children[1]
            self.assertTrue(c1.is_terminal)
            self.assertEqual(c1.kind_name, "IDENT")
            self.assertEqual(c1.text, "hello")
            self.assertEqual(c1.parent, item_rule)
            self.assertEqual(c1.depth, 2)

            # Child 2: "end" keyword
            c2 = children[2]
            self.assertTrue(c2.is_terminal)
            self.assertEqual(c2.kind_name, "KEYWORD")
            self.assertEqual(c2.text, "end")
            self.assertEqual(c2.parent, item_rule)

    def test_preorder_and_postorder_traversal(self) -> None:
        source_code = "def worker end"
        gir_bytes, _, tmp = self._compile_grammar_and_produce_gir(source_code)
        with tmp:
            view = ir.load_gir(gir_bytes)

            # Preorder: Parent first, then children
            pre_names = [n.text for n in view.walk(order="pre")]
            self.assertEqual(pre_names, ["ARRAY", "ItemRule", "def", "worker", "end"])

            # Postorder: Children first, then parent
            post_names = [n.text for n in view.walk(order="post")]
            self.assertEqual(post_names, ["def", "worker", "end", "ItemRule", "ARRAY"])

    def test_find_and_find_first(self) -> None:
        source_code = "def calculate end"
        gir_bytes, _, tmp = self._compile_grammar_and_produce_gir(source_code)
        with tmp:
            view = ir.load_gir(gir_bytes)
            root = view.root

            # Find by kind_name
            ident_node = root.find_first("IDENT")
            self.assertIsNotNone(ident_node)
            self.assertEqual(ident_node.text, "calculate")

            # Find all keywords
            keywords = list(root.find("KEYWORD"))
            self.assertEqual(len(keywords), 2)
            self.assertEqual([kw.text for kw in keywords], ["def", "end"])

            # Nonexistent node
            self.assertIsNone(root.find_first("NonexistentNode"))

    def test_dump_formatting(self) -> None:
        source_code = "def sample end"
        gir_bytes, _, tmp = self._compile_grammar_and_produce_gir(source_code)
        with tmp:
            view = ir.load_gir(gir_bytes)
            dump_str = view.dump()
            self.assertIn("GIR v1.0", dump_str)
            self.assertIn("ItemRule (3)", dump_str)
            self.assertIn("KEYWORD 'def'", dump_str)
            self.assertIn("IDENT 'sample'", dump_str)

    def test_memoryview_support(self) -> None:
        source_code = "def worker end"
        gir_bytes, _, tmp = self._compile_grammar_and_produce_gir(source_code)
        with tmp:
            mv = memoryview(gir_bytes)
            view = ir.load_gir(mv, source_text=source_code)
            self.assertIsInstance(view, ir.GirView)
            self.assertEqual(view.root.kind_name, "ARRAY")
            self.assertEqual(len(view.root.children), 1)
            self.assertEqual(view.root.children[0].kind_name, "ItemRule")
            # Verify string pool decoding succeeded on memoryview
            self.assertIn("def", [n.text for n in view.walk()])

    def test_error_handling_on_invalid_gir(self) -> None:
        # Buffer too short
        with self.assertRaises(ValueError):
            ir.load_gir(b"short")

        # Invalid magic
        bad_magic = b"XYZ\0" + b"\x00" * 68
        with self.assertRaises(ValueError):
            ir.load_gir(bad_magic)

        # Invalid version
        bad_version = b"GIR\0" + struct.pack("<HH", 2, 0) + b"\x00" * 64
        with self.assertRaises(ValueError):
            ir.load_gir(bad_version)

        # Invalid type
        with self.assertRaises(TypeError):
            ir.load_gir(12345)  # type: ignore[arg-type]

    def test_corrupted_gir_tree_validation(self) -> None:
        source_code = "def test_tree end"
        gir_bytes, _, tmp = self._compile_grammar_and_produce_gir(source_code)
        with tmp:
            orig_view = ir.load_gir(gir_bytes)
            nodes_offset = orig_view.header.nodes_offset
            root_idx = orig_view.header.root_index
            root_offset = nodes_offset + root_idx * ir.reader.NODE_SIZE
            first_child_idx = orig_view.nodes[root_idx].first_child_index
            child_offset = nodes_offset + first_child_idx * ir.reader.NODE_SIZE

            # 1. Trailing extra bytes after total_size
            with self.assertRaises(ValueError):
                ir.load_gir(gir_bytes + b"EXTRA_BYTES")

            # 2. Self-referencing cycle (root points to itself as first_child)
            # first_child is at offset 28 in Node (struct <HHIIIIIIIII)
            corrupt_self = bytearray(gir_bytes)
            struct.pack_into("<I", corrupt_self, root_offset + 28, root_idx)
            with self.assertRaises(ValueError) as ctx:
                ir.load_gir(corrupt_self)
            self.assertIn("cycle detected", str(ctx.exception).lower())

            # 3. Two-node cycle (root child points back to root as first_child)
            corrupt_cycle = bytearray(gir_bytes)
            struct.pack_into("<I", corrupt_cycle, child_offset + 28, root_idx)
            struct.pack_into("<I", corrupt_cycle, child_offset + 36, 1)  # match single child
            with self.assertRaises(ValueError) as ctx:
                ir.load_gir(corrupt_cycle)
            self.assertIn("cycle detected", str(ctx.exception).lower())

            # 4. Mismatched child_count (declare 99 children when there is only 1)
            corrupt_count = bytearray(gir_bytes)
            struct.pack_into("<I", corrupt_count, root_offset + 36, 99)
            with self.assertRaises(ValueError) as ctx:
                ir.load_gir(corrupt_count)
            self.assertIn("child_count", str(ctx.exception).lower())

            # 5. Root node having a next_sibling (illegal)
            corrupt_root_sib = bytearray(gir_bytes)
            struct.pack_into("<I", corrupt_root_sib, root_offset + 32, first_child_idx)
            with self.assertRaises(ValueError) as ctx:
                ir.load_gir(corrupt_root_sib)
            self.assertIn("root node cannot have siblings", str(ctx.exception).lower())

            # 6. Invalid root_index in header (offset 60)
            corrupt_root_idx = bytearray(gir_bytes)
            struct.pack_into("<I", corrupt_root_idx, 60, 999)
            with self.assertRaises(ValueError):
                ir.load_gir(corrupt_root_idx)

    def test_deep_tree_iterative_walker_no_recursion_error(self) -> None:
        """Verify that deep trees (e.g. 2,000 deep) do not trigger RecursionError."""
        # Synthesize a valid binary GIR buffer with 2,000 chained nodes
        depth = 2000
        node_count = depth + 1  # index 0 is null sentinel, 1 is root, 2..2000 are chained children
        string_pool = b"Node\0"
        string_offsets = struct.pack("<2I", 0, len(string_pool))

        hdr_size = 72
        str_off_off = hdr_size
        str_off_bytes = len(string_offsets)
        str_pool_off = (str_off_off + str_off_bytes + 7) & ~7
        str_pool_bytes = len(string_pool)
        nodes_off = (str_pool_off + str_pool_bytes + 7) & ~7
        nodes_bytes = node_count * ir.reader.NODE_SIZE
        total_size = nodes_off + nodes_bytes

        header = struct.pack(
            ir.reader.HEADER_STRUCT_FORMAT,
            ir.GIR_MAGIC,
            1, 0,  # version 1.0
            1,     # little endian flag
            hdr_size,
            0x1234,  # grammar_id
            0, 0,    # source hash, size
            1,       # string count
            str_off_off,
            str_pool_off,
            str_pool_bytes,
            nodes_off,
            node_count,
            1,       # root_index
            total_size,
        )

        buf = bytearray(total_size)
        buf[:len(header)] = header
        buf[str_off_off : str_off_off + str_off_bytes] = string_offsets
        buf[str_pool_off : str_pool_off + str_pool_bytes] = string_pool

        # Build nodes: node 1 (root) has first_child 2, child_count 1
        # Node i has first_child i+1, child_count 1 (except last node which has first_child 0, child_count 0)
        for i in range(1, node_count):
            first_child = (i + 1) if i < node_count - 1 else 0
            child_count = 1 if i < node_count - 1 else 0
            node_bytes = struct.pack(
                ir.reader.NODE_STRUCT_FORMAT,
                0, 0,  # kind, flags
                0,     # symbol_id ("Node")
                0,     # value
                0, 0,  # src_start, length
                i, 0,  # line, col
                first_child,
                0,     # next_sibling
                child_count,
            )
            off = nodes_off + i * ir.reader.NODE_SIZE
            buf[off : off + ir.reader.NODE_SIZE] = node_bytes

        # Now load view and traverse
        view = ir.load_gir(buf)
        self.assertEqual(view.node_count, depth)

        # Preorder walk: 2000 nodes, zero recursion error
        pre_nodes = list(view.walk(order="pre"))
        self.assertEqual(len(pre_nodes), depth)

        # Postorder walk: 2000 nodes, zero recursion error
        post_nodes = list(view.walk(order="post"))
        self.assertEqual(len(post_nodes), depth)
        self.assertEqual(pre_nodes[0].index, 1)
        self.assertEqual(post_nodes[-1].index, 1)

    def test_span_validation_against_source_size(self) -> None:
        source_code = "def worker end"
        gir_bytes, _, tmp = self._compile_grammar_and_produce_gir(source_code)
        with tmp:
            view = ir.load_gir(gir_bytes, source_text=source_code)
            nodes_offset = view.header.nodes_offset
            # Mutate node 1 src_length to exceed source_size
            corrupt = bytearray(gir_bytes)
            # src_length is offset 16 in Node (struct <HHIIIIIIIII)
            struct.pack_into("<I", corrupt, nodes_offset + 1 * ir.reader.NODE_SIZE + 16, len(source_code) + 50)
            with self.assertRaises(ValueError) as ctx:
                ir.load_gir(corrupt)
            self.assertIn("source_size", str(ctx.exception).lower())

            # Also verify source_size == 0 rejects positive span
            corrupt_zero = bytearray(gir_bytes)
            # source_size is at offset 32 in header (<4sHHIIQQIIIIIIIIQ)
            struct.pack_into("<I", corrupt_zero, 32, 0)
            with self.assertRaises(ValueError) as ctx:
                ir.load_gir(corrupt_zero)
            self.assertIn("source_size", str(ctx.exception).lower())

    def test_capture_raw_tokens_exposure_in_gir(self) -> None:
        from gram.core.combinators import CaptureRaw

        class RawBlock(RuleItem):
            nodeable = True
            entrypoint = Seq(
                MatchKeyword("raw"),
                CaptureRaw(MatchKeyword("end")),
                MatchKeyword("end"),
            )
            rule = entrypoint

        session = sessions.Session("RawTokenSession", "Some")
        session.add_keyword("raw")
        session.add_keyword("end")
        session.entrypoint = RawBlock

        tmp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        with tmp_dir:
            out_dir = pathlib.Path(tmp_dir.name)
            manifest = session.export_c_parser(out_dir, emit_driver=True, emit_cli=True)

            proj_root = pathlib.Path(__file__).resolve().parent.parent
            native_inc = proj_root / "native" / "gram_lexer" / "include"
            native_src = proj_root / "native" / "gram_lexer" / "src"
            sources = [
                "gram_ast.c", "gram_parser.c", "gram_ir.c", "gram_driver.c",
                "gram_lexer_keywords.c", "gram_lexer_symbols.c", "gram_lexer_groups.c",
            ]
            common = [str(out_dir / name) for name in sources] + [
                str(native_src / name)
                for name in (
                    "lexer.c", "indentation.c", "numbers.c", "strings.c",
                    "symbols.c", "utf8.c", "diagnostics_lite.c",
                )
            ]
            cli_exe = out_dir / "gram_cli.exe"
            flags = [
                "gcc", "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
                f"-I{native_inc}", f"-I{native_src}", f"-I{out_dir}",
                str(out_dir / "gram_cli.c"), *common, "-o", str(cli_exe),
            ]
            subprocess.run(flags, check=True, capture_output=True, text=True)

            src_text = "raw mov eax, 42; nop; end"
            src_file = out_dir / "input.src"
            src_file.write_text(src_text, encoding="utf-8")
            gir_file = out_dir / "output.gir"
            subprocess.run([str(cli_exe), "compile", str(src_file), "-o", str(gir_file)], check=True)

            view = ir.load_gir(gir_file, source_text=src_text, session=session)
            # Find the RAW node
            raw_node = None
            for n in view.walk():
                if n.is_raw:
                    raw_node = n
                    break

            self.assertIsNotNone(raw_node)
            self.assertTrue(raw_node.is_raw)
            self.assertEqual(raw_node.text, "mov eax, 42; nop;")

            # 1. CaptureRaw in GIR is an O(1) leaf node with 0 children in the AST arena
            self.assertEqual(raw_node.child_count, 0)
            self.assertEqual(len(raw_node.children), 0)
            self.assertGreater(raw_node.token_count, 0)

            # 2. Check RawNode protocol compatibility (len in O(1))
            self.assertEqual(len(raw_node), raw_node.token_count)

            # 3. Verify on-demand tokens exposure via C lexer backend
            toks = raw_node.tokens
            self.assertIsInstance(toks, tuple)
            self.assertEqual(len(toks), raw_node.token_count)
            token_values = [str(t.value) for t in toks]
            self.assertIn("mov", token_values)
            self.assertIn("eax", token_values)
            self.assertIn("42", token_values)

            self.assertEqual(list(iter(raw_node)), list(toks))
            self.assertEqual(raw_node[0], toks[0])

    def test_typed_value_and_authoritative_span_text(self) -> None:
        from gram.core.lexer.tokens import Token

        source_bytes = b"let wordsize = 64; let pi = 3.14; let active = true; let empty = null; let msg = \"hi\\n\";"
        view = ir.GirView.__new__(ir.GirView)
        view._source_bytes = source_bytes
        view.strings = ("let", "wordsize", "=", "64_CORRUPT_IN_POOL")

        # 1. Terminal number node with authoritative span over source_bytes
        # Span covering "64" in source_bytes: offset 15, length 2
        num_node = ir.GirNode(
            view=view,
            index=1,
            kind=1,  # GRAM_AST_TERMINAL_TOKEN
            flags=ir.reader.GIR_NODE_TERMINAL,
            symbol_id=3,  # Points to "64_CORRUPT_IN_POOL"
            value=Token.NUMBER.value,
            src_start=15,
            src_length=2,
            line=1,
            column=15,
            first_child_index=0,
            next_sibling_index=0,
            child_count=0,
        )
        # text must be authoritative from source_bytes, not the pool
        self.assertEqual(num_node.text, "64")
        # typed_value must be int 64, not string
        self.assertEqual(num_node.typed_value, 64)
        self.assertIsInstance(num_node.typed_value, int)

        # 2. When source_bytes is None, text falls back to symbol_name
        view_no_src = ir.GirView.__new__(ir.GirView)
        view_no_src._source_bytes = None
        view_no_src.strings = ("let", "64")
        num_node_no_src = ir.GirNode(
            view=view_no_src,
            index=1,
            kind=1,
            flags=ir.reader.GIR_NODE_TERMINAL,
            symbol_id=1,
            value=Token.NUMBER.value,
            src_start=0,
            src_length=2,
            line=1,
            column=0,
            first_child_index=0,
            next_sibling_index=0,
            child_count=0,
        )
        self.assertEqual(num_node_no_src.text, "64")
        self.assertEqual(num_node_no_src.typed_value, 64)

        # 3. Test other literal types: decimal, bool, null, string, ident
        def node_for(idx: int, tok: Token, sub: bytes, sym_id: int = 0) -> ir.GirNode:
            pos = source_bytes.find(sub)
            return ir.GirNode(
                view=view,
                index=idx,
                kind=1,
                flags=ir.reader.GIR_NODE_TERMINAL,
                symbol_id=sym_id,
                value=tok.value,
                src_start=pos,
                src_length=len(sub),
                line=1,
                column=pos,
                first_child_index=0,
                next_sibling_index=0,
                child_count=0,
            )

        dec_node = node_for(2, Token.DECIMAL, b"3.14")
        self.assertEqual(dec_node.text, "3.14")
        self.assertEqual(dec_node.typed_value, 3.14)
        self.assertIsInstance(dec_node.typed_value, float)

        bool_node = node_for(3, Token.BOOL, b"true")
        self.assertEqual(bool_node.text, "true")
        self.assertEqual(bool_node.typed_value, True)
        self.assertIsInstance(bool_node.typed_value, bool)

        null_node = node_for(4, Token.NULL, b"null")
        self.assertEqual(null_node.text, "null")
        self.assertIsNone(null_node.typed_value)

        str_node = node_for(5, Token.STRING, b'"hi\\n"')
        self.assertEqual(str_node.text, '"hi\\n"')
        self.assertEqual(str_node.typed_value, "hi\n")

        ident_node = node_for(6, Token.IDENT, b"wordsize", sym_id=1)
        self.assertEqual(ident_node.text, "wordsize")
        self.assertEqual(ident_node.typed_value, "wordsize")

    def test_empty_capture_raw_in_gir_and_ast(self) -> None:
        from gram.core.ast.nodes import RawNode

        # 1. Python in-memory AST RawNode parity
        empty_raw_ast = RawNode([], "")
        self.assertEqual(empty_raw_ast.text, "")
        self.assertEqual(empty_raw_ast.tokens, ())
        self.assertEqual(empty_raw_ast.token_count, 0)
        self.assertEqual(len(empty_raw_ast), 0)

        # 2. GIR binary reader node parity for empty raw block
        view = ir.GirView.__new__(ir.GirView)
        view._source_bytes = b"raw end"
        view.strings = ("RAW",)
        empty_gir_node = ir.GirNode(
            view=view,
            index=1,
            kind=9,  # GRAM_AST_RAW
            flags=ir.reader.GIR_NODE_RAW,
            symbol_id=0,
            value=0,  # token_count = 0
            src_start=4,
            src_length=0,  # empty body
            line=1,
            column=4,
            first_child_index=0,
            next_sibling_index=0,
            child_count=0,
        )
        self.assertTrue(empty_gir_node.is_raw)
        self.assertEqual(empty_gir_node.text, "")  # Must be empty string, never "RAW"
        self.assertEqual(empty_gir_node.tokens, ())
        self.assertEqual(empty_gir_node.token_count, 0)
        self.assertEqual(len(empty_gir_node), 0)
        self.assertFalse(bool(empty_gir_node))

    def test_raw_node_serialized_children_tokens_typed(self) -> None:
        from gram.core.lexer.tokens import Token

        source_bytes = b'raw 64 "cadena" true end'
        view = ir.GirView.__new__(ir.GirView)
        view._source_bytes = source_bytes
        view.strings = ("RAW", "64", '"cadena"', "true")

        raw_parent = ir.GirNode(
            view=view,
            index=1,
            kind=9,  # GRAM_AST_RAW
            flags=ir.reader.GIR_NODE_RAW,
            symbol_id=0,
            value=3,  # 3 tokens
            src_start=4,
            src_length=len(source_bytes) - 8,
            line=1,
            column=4,
            first_child_index=2,
            next_sibling_index=0,
            child_count=3,
        )

        child_num = ir.GirNode(
            view=view, index=2, kind=1, flags=ir.reader.GIR_NODE_TERMINAL,
            symbol_id=1, value=Token.NUMBER.value, src_start=source_bytes.find(b"64"), src_length=2,
            line=1, column=4, first_child_index=0, next_sibling_index=3, child_count=0,
        )
        child_str = ir.GirNode(
            view=view, index=3, kind=1, flags=ir.reader.GIR_NODE_TERMINAL,
            symbol_id=2, value=Token.STRING.value, src_start=source_bytes.find(b'"cadena"'), src_length=8,
            line=1, column=7, first_child_index=0, next_sibling_index=4, child_count=0,
        )
        child_bool = ir.GirNode(
            view=view, index=4, kind=1, flags=ir.reader.GIR_NODE_TERMINAL,
            symbol_id=3, value=Token.BOOL.value, src_start=source_bytes.find(b"true"), src_length=4,
            line=1, column=16, first_child_index=0, next_sibling_index=0, child_count=0,
        )

        raw_parent._children = [child_num, child_str, child_bool]

        toks = raw_parent.tokens
        self.assertEqual(len(toks), 3)

        # NUMBER -> typed int 64 (not string "64")
        self.assertEqual(toks[0].token, Token.NUMBER)
        self.assertEqual(toks[0].value, 64)
        self.assertIsInstance(toks[0].value, int)

        # STRING -> unescaped "cadena" (not "\"cadena\"")
        self.assertEqual(toks[1].token, Token.STRING)
        self.assertEqual(toks[1].value, "cadena")
        self.assertIsInstance(toks[1].value, str)

        # BOOL -> bool True (not string "true")
        self.assertEqual(toks[2].token, Token.BOOL)
        self.assertIs(toks[2].value, True)


if __name__ == "__main__":
    unittest.main()
