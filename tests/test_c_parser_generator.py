"""
Unit tests for Ahead-Of-Time (AOT) C Parser, AST Generator, binary IR (GIR) and file driver.
"""
from __future__ import annotations

import json
import shutil
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path

from gram import sessions
from gram.core.ast.nodes import ASTNode, ASTRef, ASTTokenNode, ArrayNode
from gram.core.combinators import (
    Alt,
    CaptureRaw,
    Combinator,
    Convert,
    DualExpr,
    Enclosed,
    Literal,
    Many,
    MatchGroup,
    MatchKeyword,
    MatchSeqSymbol,
    MatchToken,
    Opt,
    RawNode,
    Ref,
    RuleItem,
    SameLine,
    Separator,
    Seq,
    Some,
    Until,
)
from gram.core.lexer.tokens import Token, TokenType
from gram.core.parser.c_generator import (
    GrammarCompilerError,
    export_session_c_parser,
)


class CustomUnsupportedCombinator(Combinator):
    """External combinator with no semantic signature."""
    pass


class IndexRule(RuleItem):
    nodeable = True
    entrypoint = Enclosed(
        Token.LBRACKET,
        MatchToken(Token.NUMBER),
        Token.RBRACKET,
        allow_empty=False,
    )


class PrimaryRule(RuleItem):
    nodeable = True
    entrypoint = Alt(
        Seq(
            MatchToken(Token.IDENT),
            Many(SameLine(Ref(IndexRule))),
        ),
        MatchToken(Token.NUMBER),
    )


class ExprRule(RuleItem):
    nodeable = True
    entrypoint = DualExpr(Ref(PrimaryRule))


class LetRule(RuleItem):
    nodeable = True
    entrypoint = Seq(
        Opt(MatchGroup("vis")),
        MatchKeyword("let"),
        SameLine(MatchToken(Token.IDENT)),
        MatchToken(Token.ASSIGN),
        Ref(ExprRule),
        MatchToken(Token.SEMICOLON),
    )


class ReturnRule(RuleItem):
    nodeable = True
    entrypoint = Seq(
        MatchKeyword("return"),
        Ref(ExprRule),
        MatchToken(Token.SEMICOLON),
    )


class TypeRule(RuleItem):
    """Non-nodeable: its tokens must be spliced into the enclosing DeclRule."""
    nodeable = False
    entrypoint = Seq(
        Opt(MatchKeyword("const")),
        MatchToken(Token.IDENT),
    )


class DeclRule(RuleItem):
    nodeable = True
    entrypoint = Seq(
        MatchKeyword("var"),
        MatchToken(Token.IDENT),
        MatchToken(Token.COLON),
        Ref(TypeRule),
        MatchToken(Token.SEMICOLON),
    )


class PartialRule(RuleItem):
    """The first branch consumes `var IDENT` and then fails: its attachments must be rolled back."""
    nodeable = True
    entrypoint = Alt(
        Seq(MatchKeyword("var"), MatchToken(Token.IDENT), MatchToken(Token.ASSIGN)),
        Ref(DeclRule),
    )


class BlockRule(RuleItem):
    nodeable = True
    entrypoint = Enclosed(
        Token.LBRACE,
        Some(Alt(Ref(LetRule), Ref(ReturnRule))),
        Token.RBRACE,
        allow_empty=True,
    )


class RootRule(RuleItem):
    nodeable = True
    entrypoint = Alt(Ref(BlockRule), Ref(LetRule), Ref(ReturnRule), Ref(PartialRule))


GIR_HEADER = struct.Struct("<4sHHIIQQ8IQ")
GIR_NODE = struct.Struct("<HHIIIIIIIII")

HARNESS_C = r"""
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "gram_driver.h"

int main(int argc, char **argv) {
    if (argc < 4) return 99;
    const char *src = "var x: const y;";
    size_t src_len = strlen(src);
    GramDriverError err;

    /* Uncompiled mode: in-memory AST. */
    GramParseResult r;
    if (gram_parse_source(src, src_len, &r, &err) != GRAM_DRIVER_OK) return 1;
    if (r.root == 0 || r.arena.nodes[r.root].first_child == 0) return 2;
    if (r.token_count < 2 || r.tokens[r.token_count - 1].kind != GRAM_TOKEN_EOF) return 3;
    gram_parse_result_free(&r);

    /* Compiled mode from memory. */
    GramIrBlob blob;
    if (gram_compile_source_to_ir(src, src_len, &blob, &err) != GRAM_DRIVER_OK) return 4;
    GramIrView v;
    if (gram_ir_view_init(&v, blob.data, blob.size) != GRAM_IR_OK) return 5;
    if (!gram_ir_view_matches_grammar(&v) || !gram_ir_view_matches_source(&v, src, src_len)) return 6;
    if (gram_ir_view_matches_source(&v, "var x: const z;", src_len)) return 7;
    if (v.nodes[v.header->root_index].child_count != 1) return 8;

    /* Determinism. */
    GramIrBlob again;
    if (gram_compile_source_to_ir(src, src_len, &again, &err) != GRAM_DRIVER_OK) return 9;
    if (again.size != blob.size || memcmp(again.data, blob.data, blob.size) != 0) return 10;
    gram_ir_blob_free(&again);

    /* File round trip. */
    if (gram_ir_write_file(&blob, argv[1]) != GRAM_IR_OK) return 11;
    GramIrView loaded;
    if (gram_ir_read_file(argv[1], &loaded) != GRAM_IR_OK) return 12;
    if (loaded.size != blob.size || memcmp(loaded.data, blob.data, blob.size) != 0) return 13;
    gram_ir_view_free(&loaded);

    /* Corruption is rejected. */
    uint8_t *copy = (uint8_t *)malloc(blob.size);
    if (!copy) return 14;
    memcpy(copy, blob.data, blob.size);
    GramIrView bad;
    copy[0] = 'X';
    if (gram_ir_view_init(&bad, copy, blob.size) != GRAM_IR_ERR_FORMAT) return 15;
    copy[0] = 'G';
    if (gram_ir_view_init(&bad, copy, blob.size - 8u) != GRAM_IR_ERR_FORMAT) return 16;
    if (gram_ir_view_init(&bad, copy, blob.size) != GRAM_IR_OK) return 17;
    free(copy);
    gram_ir_blob_free(&blob);

    /* Syntax errors carry a position. */
    GramIrBlob none;
    if (gram_compile_source_to_ir("var x: ;", 8, &none, &err) != GRAM_DRIVER_ERR_PARSE) return 18;
    if (err.line != 1 || err.column != 7 || strstr(err.message, ";") == NULL) return 19;

    /* Argument validation and empty input. */
    if (gram_parse_source(NULL, 5, &r, &err) != GRAM_DRIVER_ERR_ARGS) return 20;
    if (gram_compile_source_to_ir("", 0, &blob, &err) != GRAM_DRIVER_OK) return 21;
    gram_ir_blob_free(&blob);

    /* File mode and missing files. */
    if (gram_compile_file_to_ir_file(argv[2], argv[3], &err) != GRAM_DRIVER_OK) return 22;
    if (gram_compile_file_to_ir("definitely/missing.src", &blob, &err) != GRAM_DRIVER_ERR_IO) return 23;
    return 0;
}
"""


class TestCParserGenerator(unittest.TestCase):
    """Tests AOT C parser generation, predictive switch optimization, and GCC execution."""

    def setUp(self) -> None:
        self.session = sessions.Session("TestCParsingSession", "Many")
        self.session.add_group("vis", color_group="#FFFFFF")
        self.session.add_keyword("pub", group="vis")
        self.session.add_keyword("priv", group="vis")
        for keyword in ("let", "return", "var", "const"):
            self.session.add_keyword(keyword)
        self.session.entrypoint = RootRule

    def test_crawl_and_generate_deterministic_units(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest = self.session.export_c_parser(tmpdir)
            self.assertEqual(manifest["session_name"], "TestCParsingSession")
            self.assertEqual(manifest["mode"], "Many")
            self.assertGreaterEqual(manifest["rule_count"], 8)
            for rule in ("RootRule", "LetRule", "ReturnRule", "BlockRule", "ExprRule", "TypeRule", "DeclRule"):
                self.assertIn(rule, manifest["rules"])

            out_path = Path(tmpdir)
            for name in (
                "gram_ast.h", "gram_ast.c", "gram_parser.h", "gram_parser.c",
                "gram_ir.h", "gram_ir.c", "gram_driver.h", "gram_driver.c",
                "gram_lexer_config.h", "gram_lexer_keywords.c", "gram_parser_manifest.json",
            ):
                self.assertTrue((out_path / name).is_file(), name)
            self.assertFalse((out_path / "gram_cli.c").exists())
            self.assertTrue(manifest["driver"])
            self.assertEqual(manifest["ir_format"], "GIR 1.0")

            # Verify predictive switch and keyword first-char dispatch are emitted
            parser_c = (out_path / "gram_parser.c").read_text(encoding="utf-8")
            self.assertIn("switch (alt_tok_", parser_c)
            self.assertIn("case GRAM_TOKEN_LBRACE:", parser_c)
            self.assertIn("case GRAM_TOKEN_KEYWORD:", parser_c)
            self.assertIn("switch (p->source[alt_tok_", parser_c)
            self.assertIn("case 'l':", parser_c)
            self.assertIn("case 'r':", parser_c)

            # Verify content hash reproducibility
            manifest2 = self.session.export_c_parser(tmpdir)
            self.assertEqual(manifest["content_hash"], manifest2["content_hash"])

    def test_export_without_driver_keeps_parser_only_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest = self.session.export_c_parser(tmpdir, emit_driver=False)
            self.assertFalse(manifest["driver"])
            self.assertEqual(
                manifest["files"], ["gram_ast.h", "gram_ast.c", "gram_parser.h", "gram_parser.c"]
            )
            self.assertFalse((Path(tmpdir) / "gram_driver.c").exists())
            self.assertFalse((Path(tmpdir) / "gram_lexer_config.h").exists())

    def test_cli_requires_driver(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(GrammarCompilerError):
                export_session_c_parser(self.session, tmpdir, emit_driver=False, emit_cli=True)

    def test_reject_external_combinator(self) -> None:
        class BadRule(RuleItem):
            nodeable = True
            entrypoint = Seq(MatchToken(Token.IDENT), CustomUnsupportedCombinator())

        bad_session = sessions.Session("BadSession", "Some")
        bad_session.entrypoint = BadRule

        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(GrammarCompilerError):
                bad_session.export_c_parser(tmpdir)

    def test_missing_entrypoint_raises_error(self) -> None:
        empty_session = sessions.Session("EmptySession", "Some")
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(GrammarCompilerError):
                empty_session.export_c_parser(tmpdir)


def decode_ir(data: bytes) -> tuple[dict[str, int], list[dict[str, int]], list[bytes]]:
    """Independent Python decoder for the GIR layout (cross-checks the C writer)."""
    fields = GIR_HEADER.unpack_from(data, 0)
    header = dict(zip(
        (
            "magic", "major", "minor", "flags", "header_size", "grammar_id", "source_hash",
            "source_size", "string_count", "offsets_off", "pool_off", "pool_bytes",
            "nodes_off", "node_count", "root", "total_size",
        ),
        fields,
    ))
    offsets = struct.unpack_from(f"<{header['string_count'] + 1}I", data, header["offsets_off"])
    pool = data[header["pool_off"]:header["pool_off"] + header["pool_bytes"]]
    strings = [pool[offsets[i]:offsets[i + 1] - 1] for i in range(header["string_count"])]
    nodes = [
        dict(zip(
            ("kind", "flags", "symbol", "value", "start", "length", "line", "column",
             "first_child", "next_sibling", "child_count"),
            GIR_NODE.unpack_from(data, header["nodes_off"] + i * GIR_NODE.size),
        ))
        for i in range(header["node_count"])
    ]
    return header, nodes, strings


def ir_tree(nodes: list[dict[str, int]], strings: list[bytes], index: int) -> tuple[str, list]:
    node = nodes[index]
    children = []
    child = node["first_child"]
    while child:
        children.append(ir_tree(nodes, strings, child))
        child = nodes[child]["next_sibling"]
    return strings[node["symbol"]].decode("utf-8"), children


@unittest.skipUnless(shutil.which("gcc"), "gcc compiler not found in PATH")
class TestCDriverAndIrEndToEnd(unittest.TestCase):
    """Builds the generated C (strict -Werror) and checks the CLI, the API and the IR bytes."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        cls.work = Path(cls._tmp.name)

        session = sessions.Session("DriverSession", "Many")
        session.add_group("vis", color_group="#FFFFFF")
        session.add_keyword("pub", group="vis")
        session.add_keyword("priv", group="vis")
        for keyword in ("let", "return", "var", "const"):
            session.add_keyword(keyword)
        session.entrypoint = RootRule
        cls.manifest = session.export_c_parser(cls.work, emit_cli=True)

        repo_root = Path(__file__).resolve().parent.parent
        native_inc = repo_root / "native" / "gram_lexer" / "include"
        native_src = repo_root / "native" / "gram_lexer" / "src"
        sources = [
            "gram_ast.c", "gram_parser.c", "gram_ir.c", "gram_driver.c",
            "gram_lexer_keywords.c", "gram_lexer_symbols.c", "gram_lexer_groups.c",
        ]
        common = [str(cls.work / name) for name in sources] + [
            str(native_src / name)
            for name in (
                "lexer.c", "indentation.c", "numbers.c", "strings.c",
                "symbols.c", "utf8.c", "diagnostics_lite.c",
            )
        ]
        flags = [
            "gcc", "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
            f"-I{native_inc}", f"-I{native_src}", f"-I{cls.work}",
        ]

        (cls.work / "harness.c").write_text(HARNESS_C, encoding="utf-8")
        cls.cli = cls.work / "gram_cli.exe"
        cls.harness = cls.work / "harness.exe"
        subprocess.run(
            [*flags, str(cls.work / "gram_cli.c"), *common, "-o", str(cls.cli)],
            check=True, capture_output=True, text=True,
        )
        subprocess.run(
            [*flags, str(cls.work / "harness.c"), *common, "-o", str(cls.harness)],
            check=True, capture_output=True, text=True,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(self.cli), *args], capture_output=True, text=True, check=False
        )

    def compile_to_ir(self, name: str, source: bytes) -> tuple[bytes, bytes]:
        src_path = self.work / f"{name}.src"
        ir_path = self.work / f"{name}.gir"
        src_path.write_bytes(source)
        result = self.run_cli("compile", str(src_path), "-o", str(ir_path))
        self.assertEqual(result.returncode, 0, result.stderr)
        return ir_path.read_bytes(), source

    def test_manifest_lists_cli_and_lexer_tables(self) -> None:
        self.assertIn("gram_cli.c", self.manifest["files"])
        self.assertIn("gram_lexer_config.h", self.manifest["lexer_files"])
        manifest_file = json.loads((self.work / "gram_parser_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest_file["content_hash"], self.manifest["content_hash"])

    def test_api_harness(self) -> None:
        ir_path = self.work / "harness.gir"
        src_path = self.work / "harness_in.src"
        dst_path = self.work / "harness_out.gir"
        src_path.write_text("let a = 1;\nreturn a + 2;", encoding="utf-8")
        result = subprocess.run(
            [str(self.harness), str(ir_path), str(src_path), str(dst_path)],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 0, f"harness failed at check #{result.returncode}")
        self.assertTrue(dst_path.is_file())

    def test_ir_bytes_match_independent_python_decoder(self) -> None:
        source = b"var x: const y;"
        data, _ = self.compile_to_ir("decl", source)
        header, nodes, strings = decode_ir(data)

        self.assertEqual(header["magic"], b"GIR\x00")
        self.assertEqual((header["major"], header["minor"]), (1, 0))
        self.assertEqual(header["header_size"], 72)
        self.assertEqual(header["total_size"], len(data))
        self.assertEqual(header["source_size"], len(source))
        self.assertEqual(header["nodes_off"] % 8, 0)
        self.assertEqual(header["grammar_id"], int(self.manifest["grammar_id"], 16))
        self.assertEqual(strings[0], b"")

        tree = ir_tree(nodes, strings, header["root"])
        # TypeRule is non-nodeable: `const y` is spliced straight into DeclRule.
        # PartialRule's failed first branch must leave no trace after the rollback.
        self.assertEqual(
            tree,
            ("ARRAY", [("RootRule", [("PartialRule", [("DeclRule", [
                ("var", []), ("x", []), (":", []), ("const", []), ("y", []), (";", []),
            ])])])]),
        )

        # Every terminal's span must slice the source back to its lexeme.
        for node in nodes[1:]:
            if node["flags"] & 0x1:
                lexeme = strings[node["symbol"]]
                self.assertEqual(source[node["start"]:node["start"] + node["length"]], lexeme)
        decl = next(n for n in nodes[1:] if strings[n["symbol"]] == b"DeclRule")
        self.assertEqual((decl["start"], decl["length"]), (0, len(source)))
        self.assertEqual(decl["child_count"], 6)

    def test_ir_expressions_lines_and_string_pool_dedup(self) -> None:
        source = b"let a = 1;\nreturn a + 2;"
        data, _ = self.compile_to_ir("multi", source)
        header, nodes, strings = decode_ir(data)

        self.assertEqual(len(strings), len(set(strings)), "string pool must be deduplicated")
        returns = next(n for n in nodes[1:] if strings[n["symbol"]] == b"ReturnRule")
        self.assertEqual((returns["line"], returns["column"]), (2, 0))
        binary = next(n for n in nodes[1:] if strings[n["symbol"]] == b"EXPR_BINARY")
        self.assertEqual(binary["child_count"], 2)
        self.assertEqual(source[binary["start"]:binary["start"] + binary["length"]], b"a + 2")
        self.assertTrue(binary["flags"] & 0x4)

    def test_ir_is_independent_of_utf8_bom(self) -> None:
        plain, _ = self.compile_to_ir("plain", b"let a = 1;")
        bom, _ = self.compile_to_ir("bom", b"\xef\xbb\xbflet a = 1;")
        self.assertEqual(plain, bom)

    def test_cli_dump_and_ast_modes(self) -> None:
        data, _ = self.compile_to_ir("dump", b"var x: const y;")
        dumped = self.run_cli("ir", str(self.work / "dump.gir"))
        self.assertEqual(dumped.returncode, 0, dumped.stderr)
        self.assertIn("DeclRule (6)", dumped.stdout)
        self.assertIn('KEYWORD "const"', dumped.stdout)

        ast = self.run_cli("ast", str(self.work / "dump.src"))
        self.assertEqual(ast.returncode, 0, ast.stderr)
        self.assertIn("PartialRule", ast.stdout)
        self.assertIn("TERMINAL_KEYWORD 'const'", ast.stdout)

        checked = self.run_cli("check", str(self.work / "dump.src"), "--repeat", "3")
        self.assertEqual(checked.returncode, 0, checked.stderr)
        self.assertIn("OK", checked.stdout)

    def test_cli_reports_syntax_error_position(self) -> None:
        src_path = self.work / "broken.src"
        src_path.write_text("let a = 1;\nlet b = ;", encoding="utf-8")
        result = self.run_cli("compile", str(src_path), "-o", str(self.work / "broken.gir"))
        self.assertEqual(result.returncode, 2)
        self.assertIn(":2:", result.stderr)
        self.assertIn("syntax error", result.stderr)
        self.assertFalse((self.work / "broken.gir").exists())

    def test_cli_missing_input(self) -> None:
        result = self.run_cli("check", str(self.work / "does_not_exist.src"))
        self.assertEqual(result.returncode, 2)
        self.assertIn("cannot open", result.stderr)

    def test_corrupted_ir_files_are_rejected(self) -> None:
        data, _ = self.compile_to_ir("corrupt", b"var x: const y;")
        header, nodes, _ = decode_ir(data)

        def rejected(mutated: bytes, label: str) -> None:
            path = self.work / f"mutated_{label}.gir"
            path.write_bytes(mutated)
            result = self.run_cli("ir", str(path))
            self.assertEqual(result.returncode, 2, f"{label}: {result.stdout}")

        rejected(b"XIR" + data[3:], "magic")
        rejected(data[:-8], "truncated")
        rejected(data[:40], "tiny")

        # A child link pointing back at the root creates a cycle.
        cyclic = bytearray(data)
        victim = header["nodes_off"] + 2 * GIR_NODE.size
        struct.pack_into("<I", cyclic, victim + 28, 1)
        rejected(bytes(cyclic), "cycle")

        # An out-of-range sibling index.
        dangling = bytearray(data)
        struct.pack_into("<I", dangling, victim + 32, header["node_count"] + 5)
        rejected(bytes(dangling), "dangling")


class TestCCompilerHardening(unittest.TestCase):
    """Regression tests verifying closed combinator verification, MatchGroup filters, and Literal matching."""

    def test_grammar_fingerprint_changes_when_rule_body_changes(self) -> None:
        class R1(RuleItem):
            rule = MatchKeyword("foo")

        class R2(RuleItem):
            rule = MatchKeyword("bar")

        s1 = sessions.Session("test_fp1", "Many")
        s1.add_keyword("foo")
        s1.entrypoint = R1
        s2 = sessions.Session("test_fp2", "Many")
        s2.add_keyword("bar")
        s2.entrypoint = R2
        s3 = sessions.Session("test_fp3", "Many")
        s3.add_keyword("foo")
        s3.add_keyword("extra_lexical_kw")
        s3.entrypoint = R1

        with tempfile.TemporaryDirectory() as td1, tempfile.TemporaryDirectory() as td2, tempfile.TemporaryDirectory() as td3:
            m1 = export_session_c_parser(s1, td1, emit_driver=True)
            m2 = export_session_c_parser(s2, td2, emit_driver=True)
            m3 = export_session_c_parser(s3, td3, emit_driver=True)
            self.assertNotEqual(m1["grammar_id"], m2["grammar_id"])
            self.assertNotEqual(
                m1["grammar_id"],
                m3["grammar_id"],
                "Adding a session keyword must change grammar_id even when rules are identical",
            )

    def test_ref_to_combinator_instance_and_invalid_ref_rejection(self) -> None:
        # 1. Invalid target in Ref must raise GrammarCompilerError
        class BadRefRule(RuleItem):
            rule = Ref("not_a_rule_or_combinator")  # type: ignore[arg-type]

        s_bad = sessions.Session("test_bad_ref", "Many")
        s_bad.entrypoint = BadRefRule
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(GrammarCompilerError) as ctx:
                export_session_c_parser(s_bad, td)
            self.assertEqual(ctx.exception.name, "InvalidRefTarget")

        # 2. Ref wrapping a Combinator instance must compile and execute its inner combinator
        if shutil.which("gcc") is None:
            self.skipTest("GCC compiler not found in PATH")

        inline_binding = Seq(MatchKeyword("let"), MatchToken(Token.IDENT))

        class CombRefRule(RuleItem):
            nodeable = True
            entrypoint = Ref(inline_binding)
            rule = entrypoint

        s_ok = sessions.Session("test_comb_ref", "Many")
        s_ok.add_keyword("let")
        s_ok.entrypoint = CombRefRule

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            out_dir = Path(td)
            export_session_c_parser(s_ok, out_dir, emit_driver=True, emit_cli=True)

            proj_root = Path(__file__).resolve().parent.parent
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
            subprocess.run(
                [
                    "gcc", "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
                    f"-I{native_inc}", f"-I{native_src}", f"-I{out_dir}",
                    str(out_dir / "gram_cli.c"), *common, "-o", str(cli_exe),
                ],
                check=True, capture_output=True, text=True,
            )

            fpath = out_dir / "input.src"
            fpath.write_text("let my_var", encoding="utf-8")
            res_ok = subprocess.run([str(cli_exe), "check", str(fpath)], capture_output=True, text=True)
            self.assertEqual(res_ok.returncode, 0, res_ok.stderr)

            fpath.write_text("let 12345", encoding="utf-8")
            res_fail = subprocess.run([str(cli_exe), "check", str(fpath)], capture_output=True, text=True)
            self.assertEqual(res_fail.returncode, 2, "Ref(Combinator) must not compile to a vacuous ok = true")

    def test_convert_combinator_is_rejected_at_export(self) -> None:
        class ConvRule(RuleItem):
            rule = Convert("ident", Token.IDENT)

        s = sessions.Session("test_conv", "Many")
        s.entrypoint = ConvRule

        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(GrammarCompilerError) as ctx:
                export_session_c_parser(s, td)
            self.assertEqual(ctx.exception.name, "NonCompilableCombinator")
            self.assertIn("Convert", str(ctx.exception.caution))

    def test_dynamic_regex_in_match_seq_symbol_is_rejected(self) -> None:
        class RegexRule(RuleItem):
            rule = MatchSeqSymbol(regex=r"[a-z]+[0-9]*")

        s = sessions.Session("test_dyn_sym", "Many")
        s.entrypoint = RegexRule

        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(GrammarCompilerError) as ctx:
                export_session_c_parser(s, td)
            self.assertEqual(ctx.exception.name, "DynamicRegexInSymbolUnsupported")

    def test_literal_and_match_group_and_symbol_in_c(self) -> None:
        if shutil.which("gcc") is None:
            self.skipTest("GCC compiler not found in PATH")

        s = sessions.Session("test_hardening_c", "Many")
        for kw in ("int", "float", "void", "bool"):
            s.add_keyword(kw)
        s.add_group("$TYPES", ["int", "float", "void", "bool"])
        s.add_keyword("let")

        # Allow filter: only 'int' and 'float' allowed
        class TypeAllowed(RuleItem):
            rule = MatchGroup("$TYPES", values=["int", "float"], behavior_values="allow")

        # Wildcard literal and exact literal
        class LitRule(RuleItem):
            rule = Seq(MatchKeyword("let"), Literal("42"), Literal())

        class SymRule(RuleItem):
            rule = MatchSeqSymbol(symbols=["+=", "-="])

        class CaseSymRule(RuleItem):
            rule = MatchSeqSymbol(pattern="AND", is_pattern=False, case_sensitive=False)

        class RootRule(RuleItem):
            rule = Alt(Ref(TypeAllowed), Ref(LitRule), Ref(SymRule), Ref(CaseSymRule))

        s.entrypoint = RootRule

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            out_dir = Path(td)
            export_session_c_parser(s, out_dir, emit_driver=True, emit_cli=True)

            proj_root = Path(__file__).resolve().parent.parent
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

            def check_code(code: str) -> int:
                fpath = out_dir / "input.src"
                fpath.write_text(code, encoding="utf-8")
                res = subprocess.run([str(cli_exe), "check", str(fpath)], capture_output=True, text=True)
                return res.returncode

            # 1. MatchGroup allow/deny:
            self.assertEqual(check_code("int"), 0, "int should be accepted in allow filter")
            self.assertEqual(check_code("float"), 0, "float should be accepted in allow filter")
            self.assertEqual(check_code("void"), 2, "void must be rejected by allow filter")
            self.assertEqual(check_code("bool"), 2, "bool must be rejected by allow filter")

            # 2. Literal exact and wildcard:
            # 'let' (keyword) + '42' (exact literal) + 'foo' (wildcard non-keyword literal)
            self.assertEqual(check_code("let 42 foo"), 0, "let 42 foo should be accepted")
            self.assertEqual(check_code("let 99 foo"), 2, "let 99 should fail exact match for 42")
            # Wildcard Literal cannot match a keyword:
            self.assertEqual(check_code("let 42 let"), 2, "wildcard Literal must reject KEYWORD 'let'")

            # 3. MatchSeqSymbol symbols candidate list:
            self.assertEqual(check_code("+="), 0, "+= should match candidate list")
            self.assertEqual(check_code("-="), 0, "-= should match candidate list")
            self.assertEqual(check_code("*="), 2, "*= not in candidates, should fail")

            # 4. MatchSeqSymbol case-insensitive matching:
            self.assertEqual(check_code("AND"), 0, "AND exact should match")
            self.assertEqual(check_code("and"), 0, "and lowercase should match case-insensitively")
            self.assertEqual(check_code("And"), 0, "And titlecase should match case-insensitively")

    def test_until_combinator_in_c(self) -> None:
        if shutil.which("gcc") is None:
            self.skipTest("GCC compiler not found in PATH")

        s = sessions.Session("test_until_c", "Many")
        for kw in ("block", "cblock", "raw", "capped", "end"):
            s.add_keyword(kw)

        # 1. BlockUntil: consume_target=False (target is consumed by trailing MatchKeyword('end'))
        class BlockUntil(RuleItem):
            nodeable = True
            entrypoint = Seq(
                MatchKeyword("block"),
                Until(MatchKeyword("end"), consume_target=False),
                MatchKeyword("end"),
            )
            rule = entrypoint

        # 2. BlockConsumeTarget: consume_target=True
        class BlockConsumeTarget(RuleItem):
            nodeable = True
            entrypoint = Seq(
                MatchKeyword("cblock"),
                Until(MatchKeyword("end"), consume_target=True),
            )
            rule = entrypoint

        # 3. CompoundTargetUntil: Seq(COLON, end)
        class CompoundTargetUntil(RuleItem):
            nodeable = True
            entrypoint = Seq(
                MatchKeyword("raw"),
                Until(Seq(MatchToken(Token.COLON), MatchKeyword("end")), consume_target=True),
            )
            rule = entrypoint

        # 4. MaxTokensUntil: capped at 2 tokens
        class MaxTokensUntil(RuleItem):
            nodeable = True
            entrypoint = Seq(
                MatchKeyword("capped"),
                Until(MatchKeyword("end"), max_tokens=2, consume_target=True),
            )
            rule = entrypoint

        class RootUntilRule(RuleItem):
            nodeable = True
            entrypoint = Alt(
                Ref(BlockUntil),
                Ref(BlockConsumeTarget),
                Ref(CompoundTargetUntil),
                Ref(MaxTokensUntil),
            )
            rule = entrypoint

        s.entrypoint = RootUntilRule

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            out_dir = Path(td)
            export_session_c_parser(s, out_dir, emit_driver=True, emit_cli=True)

            proj_root = Path(__file__).resolve().parent.parent
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

            def check_code(code: str) -> int:
                fpath = out_dir / "input.src"
                fpath.write_text(code, encoding="utf-8")
                res = subprocess.run([str(cli_exe), "check", str(fpath)], capture_output=True, text=True)
                return res.returncode

            # consume_target=False:
            self.assertEqual(check_code("block a b c end"), 0, "block with tokens should match")
            self.assertEqual(check_code("block end"), 0, "immediate target (0 items) should match")
            self.assertEqual(check_code("block a b c"), 2, "missing end delimiter must fail and rollback")

            # consume_target=True:
            self.assertEqual(check_code("cblock x y z end"), 0, "cblock with consume_target=True should match")
            self.assertEqual(check_code("cblock end"), 0, "cblock immediate target should match")
            self.assertEqual(check_code("cblock x y z"), 2, "cblock without end must fail")

            # Compound multi-token target Seq(COLON, end):
            self.assertEqual(check_code("raw item1 item2 : end"), 0, "compound target : end should match")
            self.assertEqual(check_code("raw item1 : item2 end"), 2, "partial target match must not terminate early")

            # max_tokens cap:
            self.assertEqual(check_code("capped a b end"), 0, "capped with 2 items <= max_tokens(2) must pass")
            self.assertEqual(check_code("capped a b c end"), 2, "capped with 3 items > max_tokens(2) must fail")

            # IR inspection: check that Until produces an ARRAY node with the collected children
            fpath = out_dir / "test_ir.src"
            gir_path = out_dir / "test_ir.gir"
            fpath.write_text("block a 123 end", encoding="utf-8")
            compile_res = subprocess.run(
                [str(cli_exe), "compile", str(fpath), "-o", str(gir_path)],
                capture_output=True, text=True,
            )
            self.assertEqual(compile_res.returncode, 0, compile_res.stderr)
            self.assertTrue(gir_path.exists())

            header, nodes, strings = decode_ir(gir_path.read_bytes())
            array_nodes = [n for n in nodes if strings[n["symbol"]] == b"ARRAY"]
            self.assertGreaterEqual(len(array_nodes), 1)
            # The Until array node should have 2 children ('a' and '123')
            until_array = array_nodes[-1]
            self.assertEqual(until_array["child_count"], 2)

            # Compound target with consume_target=True and partial match rollback:
            # Input: "raw item1 : item2 : end"
            # The first ":" is a partial match of Seq(COLON, "end") that fails on "item2";
            # its partial node must be rolled back, then ":" consumed as a normal token.
            # When ": end" finally matches, both ":" and "end" must be attached to the Until ARRAY.
            # Total children in Until ARRAY: item1, :, item2, :, end -> 5 children!
            fpath_comp = out_dir / "test_comp.src"
            gir_comp = out_dir / "test_comp.gir"
            fpath_comp.write_text("raw item1 : item2 : end", encoding="utf-8")
            comp_res = subprocess.run(
                [str(cli_exe), "compile", str(fpath_comp), "-o", str(gir_comp)],
                capture_output=True, text=True,
            )
            self.assertEqual(comp_res.returncode, 0, comp_res.stderr)
            _, comp_nodes, comp_strings = decode_ir(gir_comp.read_bytes())
            comp_arrays = [n for n in comp_nodes if comp_strings[n["symbol"]] == b"ARRAY"]
            self.assertGreaterEqual(len(comp_arrays), 1)
            comp_until_array = comp_arrays[-1]
            self.assertEqual(
                comp_until_array["child_count"],
                5,
                "Compound Until(Seq(COLON, 'end'), consume_target=True) must attach ':' and 'end' to ARRAY (5 children total)",
            )

    def test_capture_raw_combinator_end_to_end(self) -> None:
        """Test CaptureRaw combinator in generated C: delimiter balancing, leaf Raw AST/GIR, rollback."""
        class AsmBlock(RuleItem):
            nodeable = True
            entrypoint = Seq(
                MatchKeyword("asm"),
                MatchToken(Token.LBRACE),
                CaptureRaw(MatchToken(Token.RBRACE), balance_delimiters=(Token.LBRACE, Token.RBRACE)),
                MatchToken(Token.RBRACE),
            )
            rule = entrypoint

        class ShaderBlock(RuleItem):
            nodeable = True
            entrypoint = Seq(
                MatchKeyword("shader"),
                CaptureRaw(MatchKeyword("end"), consume_target=True),
            )
            rule = entrypoint

        class CappedRaw(RuleItem):
            nodeable = True
            entrypoint = Seq(
                MatchKeyword("raw"),
                CaptureRaw(MatchKeyword("stop"), max_tokens=2),
                MatchKeyword("stop"),
            )
            rule = entrypoint

        class RootRawRule(RuleItem):
            nodeable = True
            entrypoint = Many(Alt(Ref(AsmBlock), Ref(ShaderBlock), Ref(CappedRaw)))
            rule = entrypoint

        raw_session = sessions.Session("RawSession", "Some")
        for kw in ("asm", "shader", "end", "raw", "stop"):
            raw_session.add_keyword(kw)
        raw_session.entrypoint = RootRawRule

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
            out_dir = Path(tmp_dir)
            export_session_c_parser(raw_session, out_dir, emit_driver=True, emit_cli=True)

            proj_root = Path(__file__).resolve().parent.parent
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

            def check_code(code: str) -> int:
                fpath = out_dir / "input.src"
                fpath.write_text(code, encoding="utf-8")
                res = subprocess.run([str(cli_exe), "check", str(fpath)], capture_output=True, text=True)
                return res.returncode

            # 1. Delimiter balancing inside assembly block:
            self.assertEqual(check_code("asm { mov eax, 1; }"), 0, "simple asm block should match")
            self.assertEqual(check_code("asm { mov eax, [rbx]; { nop; } ret; }"), 0, "nested braces with balancing must match")
            self.assertEqual(check_code("asm { mov eax, 1;"), 2, "unclosed asm block must fail and rollback")
            self.assertEqual(check_code("asm { { nop; }"), 2, "unbalanced inner brace must fail")

            # 2. consume_target=True:
            self.assertEqual(check_code("shader in vec3 p; void main() {} end"), 0, "shader block with consume_target=True should match")
            self.assertEqual(check_code("shader end"), 0, "immediate target should match")
            self.assertEqual(check_code("shader in vec3 p;"), 2, "shader without end must fail")

            # 3. max_tokens cap:
            self.assertEqual(check_code("raw a b stop"), 0, "raw with 2 tokens <= max_tokens(2) should pass")
            self.assertEqual(check_code("raw a b c stop"), 2, "raw with 3 tokens > max_tokens(2) must fail")

            # 4. GIR Inspection: check single leaf node with GRAM_AST_RAW, child_count == 0, and exact source span
            fpath = out_dir / "test_raw.src"
            gir_path = out_dir / "test_raw.gir"
            source_content = "asm { mov eax, [rsp + 0x10]; nop; }"
            fpath.write_text(source_content, encoding="utf-8")
            compile_res = subprocess.run(
                [str(cli_exe), "compile", str(fpath), "-o", str(gir_path)],
                capture_output=True, text=True,
            )
            self.assertEqual(compile_res.returncode, 0, compile_res.stderr)
            self.assertTrue(gir_path.exists())

            header, nodes, strings = decode_ir(gir_path.read_bytes())
            raw_nodes = [n for n in nodes if strings[n["symbol"]] == b"RAW"]
            self.assertEqual(len(raw_nodes), 1, "Must generate exactly 1 RAW node for the asm payload")
            raw_node = raw_nodes[0]
            self.assertEqual(raw_node["child_count"], 0, "RAW node must be a leaf with 0 children")
            self.assertEqual(raw_node["first_child"], 0, "RAW node must have first_child == 0")
            self.assertEqual(raw_node["flags"], 0x10, "RAW node flags must be GRAM_IR_NODE_RAW (0x10)")

            # Verify byte span points precisely to the raw payload in source_content
            span_bytes = source_content.encode("utf-8")[raw_node["start"]:raw_node["start"] + raw_node["length"]]
            span_text = span_bytes.decode("utf-8")
            self.assertEqual(span_text, "mov eax, [rsp + 0x10]; nop;")

            # 5. Foreign assembly characters ($0x80, @label, %eax) inside CaptureRaw vs outside CaptureRaw:
            foreign_asm = "asm { mov %eax, $0x80; @label: int $0x80; }"
            fpath_foreign = out_dir / "foreign.src"
            gir_foreign = out_dir / "foreign.gir"
            fpath_foreign.write_text(foreign_asm, encoding="utf-8")
            foreign_res = subprocess.run(
                [str(cli_exe), "compile", str(fpath_foreign), "-o", str(gir_foreign)],
                capture_output=True, text=True,
            )
            self.assertEqual(foreign_res.returncode, 0, f"Foreign assembly tokens inside CaptureRaw must succeed: {foreign_res.stderr}")
            _, f_nodes, f_strings = decode_ir(gir_foreign.read_bytes())
            f_raw = [n for n in f_nodes if f_strings[n["symbol"]] == b"RAW"][0]
            f_span = foreign_asm.encode("utf-8")[f_raw["start"]:f_raw["start"] + f_raw["length"]].decode("utf-8")
            self.assertEqual(f_span, "mov %eax, $0x80; @label: int $0x80;")

            # Foreign character '$' outside CaptureRaw must still fail with lexical error (exit code 2)
            self.assertEqual(
                check_code("asm { nop; } $0x80"),
                2,
                "Unrecognized lexical token outside CaptureRaw must be rejected",
            )

    def test_many_and_some_array_nesting_in_c(self) -> None:
        """Test that Many and Some repetition combinators emit nested GRAM_AST_ARRAY nodes in C/GIR."""
        from gram.ir.reader import GirView

        class Statement(RuleItem):
            nodeable = True
            entrypoint = Seq(MatchToken(Token.IDENT), MatchToken(Token.SEMICOLON))
            rule = entrypoint

        class AsmVariant(RuleItem):
            nodeable = True
            entrypoint = Seq(
                MatchToken(Token.AT),
                MatchKeyword("variant"),
                MatchToken(Token.COLON),
                Many(Ref(Statement)),
                MatchToken(Token.AT),
                MatchKeyword("end"),
            )
            rule = entrypoint

        class MandatoryBlock(RuleItem):
            nodeable = True
            entrypoint = Seq(
                MatchKeyword("block"),
                MatchToken(Token.COLON),
                Some(Ref(Statement)),
                MatchKeyword("end"),
            )
            rule = entrypoint

        class RootRepRule(RuleItem):
            nodeable = True
            entrypoint = Many(Alt(Ref(AsmVariant), Ref(MandatoryBlock)))
            rule = entrypoint

        rep_session = sessions.Session("RepetitionNestingSession", "Some")
        for kw in ("variant", "block", "end"):
            rep_session.add_keyword(kw)
        rep_session.entrypoint = RootRepRule

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
            out_dir = Path(tmp_dir)
            export_session_c_parser(rep_session, out_dir, emit_driver=True, emit_cli=True)

            proj_root = Path(__file__).resolve().parent.parent
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

            # 1. AsmVariant with 3 statements:
            # Must generate an ARRAY node at index 3 with the 3 Statement children.
            # Delimiters @, end must follow AFTER the ARRAY node (indices 4 and 5), exactly matching Python AST structure.
            src_3 = "@ variant : m1; m2; m3; @ end"
            fpath_3 = out_dir / "variant_3.src"
            gir_3 = out_dir / "variant_3.gir"
            fpath_3.write_text(src_3, encoding="utf-8")
            res_3 = subprocess.run([str(cli_exe), "compile", str(fpath_3), "-o", str(gir_3)], capture_output=True, text=True)
            self.assertEqual(res_3.returncode, 0, res_3.stderr)

            view_3 = GirView(gir_3.read_bytes(), source=src_3.encode("utf-8"))
            variant_node = view_3.root.find_first("AsmVariant")
            self.assertIsNotNone(variant_node)
            self.assertEqual(len(variant_node.children), 6)
            self.assertEqual(variant_node.children[0].text, "@")
            self.assertEqual(variant_node.children[1].text, "variant")
            self.assertEqual(variant_node.children[2].text, ":")

            array_node = variant_node.children[3]
            self.assertTrue(array_node.is_array)
            self.assertEqual(len(array_node), 3)
            self.assertEqual([s.kind_name for s in array_node], ["Statement", "Statement", "Statement"])
            self.assertEqual([s.children[0].text for s in array_node], ["m1", "m2", "m3"])

            self.assertEqual(variant_node.children[4].text, "@")
            self.assertEqual(variant_node.children[5].text, "end")

            # 2. AsmVariant with 0 statements:
            # Many matches 0 times; no array node is attached, leaving exactly 5 children without shifting delimiter indices.
            src_0 = "@ variant : @ end"
            fpath_0 = out_dir / "variant_0.src"
            gir_0 = out_dir / "variant_0.gir"
            fpath_0.write_text(src_0, encoding="utf-8")
            res_0 = subprocess.run([str(cli_exe), "compile", str(fpath_0), "-o", str(gir_0)], capture_output=True, text=True)
            self.assertEqual(res_0.returncode, 0, res_0.stderr)

            view_0 = GirView(gir_0.read_bytes(), source=src_0.encode("utf-8"))
            variant_0 = view_0.root.find_first("AsmVariant")
            self.assertIsNotNone(variant_0)
            self.assertEqual(len(variant_0.children), 5)
            self.assertEqual([ch.text for ch in variant_0.children], ["@", "variant", ":", "@", "end"])

            # 3. MandatoryBlock with Some:
            # 2 statements: succeeds and groups them in an ARRAY node.
            src_some_2 = "block : x; y; end"
            fpath_some = out_dir / "some_2.src"
            gir_some = out_dir / "some_2.gir"
            fpath_some.write_text(src_some_2, encoding="utf-8")
            res_some = subprocess.run([str(cli_exe), "compile", str(fpath_some), "-o", str(gir_some)], capture_output=True, text=True)
            self.assertEqual(res_some.returncode, 0, res_some.stderr)

            view_some = GirView(gir_some.read_bytes(), source=src_some_2.encode("utf-8"))
            block_node = view_some.root.find_first("MandatoryBlock")
            self.assertIsNotNone(block_node)
            self.assertEqual(len(block_node.children), 4)
            self.assertEqual(block_node.children[0].text, "block")
            self.assertEqual(block_node.children[1].text, ":")
            self.assertTrue(block_node.children[2].is_array)
            self.assertEqual(len(block_node.children[2]), 2)
            self.assertEqual([s.children[0].text for s in block_node.children[2]], ["x", "y"])
            self.assertEqual(block_node.children[3].text, "end")

            # 4. MandatoryBlock with 0 statements: Some requires at least 1 match, must fail syntax check
            fpath_fail = out_dir / "some_fail.src"
            fpath_fail.write_text("block : end", encoding="utf-8")
            res_fail = subprocess.run([str(cli_exe), "check", str(fpath_fail)], capture_output=True, text=True)
            self.assertEqual(res_fail.returncode, 2, "Some combinator with 0 matches must fail syntax check")

    def test_differential_python_ast_vs_gir_trees(self) -> None:
        """Differential equivalence verification between Python AST and C AOT / GIR across sequences and repetitions."""
        from gram.ir.reader import GirNode, GirView

        def norm_py(node: Any) -> Any:
            if isinstance(node, list):
                return ("ARRAY", [norm_py(x) for x in node])
            if isinstance(node, ArrayNode):
                return ("ARRAY", [norm_py(x) for x in node.items])
            if isinstance(node, ASTRef):
                return (node.name, [norm_py(x) for x in node.nodes])
            if isinstance(node, ASTTokenNode):
                return (node.token.token.name, str(node.token.value))
            if isinstance(node, TokenType):
                return (node.token.name, str(node.value))
            if isinstance(node, RawNode):
                return ("RAW", node.text)
            return str(node)

        def norm_gir(node: GirNode) -> Any:
            if node.is_array:
                return ("ARRAY", [norm_gir(ch) for ch in node.children])
            if node.is_raw:
                return ("RAW", node.text)
            if node.is_terminal:
                tok = Token.from_code(node.value)
                tname = tok.name if tok else node.kind_name
                return (tname, node.text)
            return (node.kind_name, [norm_gir(ch) for ch in node.children])

        # Grammar exercising:
        # 1. AsmVariant with Many(Seq(IDENT, NUMBER))
        # 2. SomeBlock with Some(Seq(IDENT, NUMBER, SEMICOLON))
        # 3. NestedSeq with Seq(IDENT, Seq(NUMBER, NUMBER), SEMICOLON)
        class AsmVariantRule(RuleItem):
            nodeable = True
            entrypoint = Seq(
                MatchToken(Token.AT),
                MatchKeyword("variant"),
                Many(Seq(MatchToken(Token.IDENT), MatchToken(Token.NUMBER))),
                MatchToken(Token.AT),
                MatchKeyword("end"),
            )
            rule = entrypoint

        class SomeBlockRule(RuleItem):
            nodeable = True
            entrypoint = Seq(
                MatchKeyword("block"),
                Some(Seq(MatchToken(Token.IDENT), MatchToken(Token.NUMBER), MatchToken(Token.SEMICOLON))),
                MatchKeyword("end"),
            )
            rule = entrypoint

        class NestedSeqRule(RuleItem):
            nodeable = True
            entrypoint = Seq(
                MatchToken(Token.IDENT),
                Seq(MatchToken(Token.NUMBER), MatchToken(Token.NUMBER)),
                MatchToken(Token.SEMICOLON),
            )
            rule = entrypoint

        class DiffRootRule(RuleItem):
            nodeable = False
            entrypoint = Alt(Ref(AsmVariantRule), Ref(SomeBlockRule), Ref(NestedSeqRule))
            rule = entrypoint

        diff_session = sessions.Session("DiffSession", "Many")
        for kw in ("variant", "block", "end"):
            diff_session.add_keyword(kw)
        diff_session.entrypoint = DiffRootRule

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
            out_dir = Path(tmp_dir)
            export_session_c_parser(diff_session, out_dir, emit_driver=True, emit_cli=True)

            proj_root = Path(__file__).resolve().parent.parent
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

            def assert_trees_match(source: str, label: str) -> None:
                # 1. Parse in Python
                ast_py = diff_session.parse(diff_session.tokenize(source, "src"), "src")
                py_tree = norm_py(ast_py)

                # 2. Compile to GIR with C AOT
                fpath = out_dir / f"{label}.src"
                gir_path = out_dir / f"{label}.gir"
                fpath.write_text(source, encoding="utf-8")
                res = subprocess.run([str(cli_exe), "compile", str(fpath), "-o", str(gir_path)], capture_output=True, text=True)
                self.assertEqual(res.returncode, 0, f"Compilation failed for {label}: {res.stderr}")

                # 3. Read GIR and normalize
                view = GirView(gir_path.read_bytes(), source=source.encode("utf-8"))
                gir_tree = norm_gir(view.root)

                # 4. Assert 100% exact topological equivalence
                self.assertEqual(py_tree, gir_tree, f"Differential mismatch on '{label}' ({source}):\nPy:  {py_tree}\nGIR: {gir_tree}")

            # Case A: Many(Seq(IDENT, NUMBER)) with multiple iterations
            assert_trees_match("@ variant foo 64 bar 32 @ end", "many_seq_multiple")

            # Case B: Many(Seq(...)) with 0 iterations (empty repetition)
            assert_trees_match("@ variant @ end", "many_seq_empty")

            # Case C: Some(Seq(IDENT, NUMBER, SEMICOLON)) with multiple iterations
            assert_trees_match("block a 1 ; b 2 ; end", "some_seq_multiple")

            # Case D: Nested Seq inside Seq
            assert_trees_match("x 10 20 ;", "nested_seq_in_seq")


class TestCaptureRawPython(unittest.TestCase):
    """Test CaptureRaw combinator and RawNode in Python ASTAnalyzer runtime."""

    def test_capture_raw_delimiters_and_node(self) -> None:
        class AsmBlock(RuleItem):
            nodeable = True
            entrypoint = Seq(
                MatchKeyword("asm"),
                MatchToken(Token.LBRACE),
                CaptureRaw(MatchToken(Token.RBRACE), balance_delimiters=(Token.LBRACE, Token.RBRACE)),
                MatchToken(Token.RBRACE),
            )

        class RootRule(RuleItem):
            nodeable = True
            entrypoint = Alt(Ref(AsmBlock))

        session = sessions.Session("AsmPythonSession", "Some")
        session.add_keyword("asm")
        session.entrypoint = RootRule

        tokens = session.tokenize("asm { mov eax, [rbx]; { nop; } ret; }", "test")
        ast = session.parse(tokens, "test")
        self.assertIsNotNone(ast)

        # Check RawNode properties
        def find_raw_nodes(node):
            found = []
            if isinstance(node, RawNode):
                found.append(node)
            elif hasattr(node, "nodes"):
                for child in node.nodes:
                    found.extend(find_raw_nodes(child))
            elif isinstance(node, list):
                for child in node:
                    found.extend(find_raw_nodes(child))
            return found

        raw_nodes = find_raw_nodes(ast)
        self.assertEqual(len(raw_nodes), 1)
        raw_node = raw_nodes[0]
        self.assertGreater(len(raw_node), 0)
        self.assertTrue(bool(raw_node))
        self.assertEqual(raw_node.text, "mov eax, [rbx]; { nop; } ret;")

    def test_capture_raw_rollback(self) -> None:
        class AsmBlock(RuleItem):
            nodeable = True
            entrypoint = Seq(
                MatchKeyword("asm"),
                MatchToken(Token.LBRACE),
                CaptureRaw(MatchToken(Token.RBRACE)),
                MatchToken(Token.RBRACE),
            )

        class RootRule(RuleItem):
            nodeable = True
            entrypoint = Alt(Ref(AsmBlock))

        session = sessions.Session("AsmFailSession", "Some")
        session.add_keyword("asm")
        session.entrypoint = RootRule

        # Missing closing brace must fail and rollback
        tokens = session.tokenize("asm { mov eax, 1", "test")
        with self.assertRaises(SystemExit):
            session.parse(tokens, "test")

    def test_capture_raw_exact_source_slice_and_max_tokens(self) -> None:
        class AsmBlock(RuleItem):
            nodeable = True
            entrypoint = Seq(
                MatchKeyword("asm"),
                MatchToken(Token.LBRACE),
                CaptureRaw(MatchToken(Token.RBRACE), balance_delimiters=(Token.LBRACE, Token.RBRACE)),
                MatchToken(Token.RBRACE),
            )

        class CappedBlock(RuleItem):
            nodeable = True
            entrypoint = Seq(
                MatchKeyword("capped"),
                CaptureRaw(MatchKeyword("end"), max_tokens=2),
                MatchKeyword("end"),
            )

        class RootRule(RuleItem):
            nodeable = True
            entrypoint = Alt(Ref(AsmBlock), Ref(CappedBlock))

        session = sessions.Session("AsmExactSession", "Some")
        for kw in ("asm", "capped", "end"):
            session.add_keyword(kw)
        session.entrypoint = RootRule

        # 1. Multiline source with comments and spaces:
        multiline_src = "asm {\n    mov eax, 0x10;  # assembly comment\n    nop;\n}"
        toks = session.tokenize(multiline_src, "test")
        ast = session.parse(toks, "test")
        self.assertIsNotNone(ast)
        raw_node = ast[0].nodes[2]  # asm, {, RawNode, }
        self.assertIsInstance(raw_node, RawNode)
        # Sliced directly from source text:
        self.assertEqual(raw_node.text, "mov eax, 0x10;  # assembly comment\n    nop;")

        # 2. max_tokens parity: counts non-layout tokens
        # "capped tok1 tok2 end" has 2 non-layout tokens -> succeeds
        toks_ok = session.tokenize("capped tok1 tok2 end", "test")
        ast_ok = session.parse(toks_ok, "test")
        self.assertIsNotNone(ast_ok)

        # "capped tok1 tok2 tok3 end" has 3 non-layout tokens -> exceeds max_tokens(2) -> fails
        toks_fail = session.tokenize("capped tok1 tok2 tok3 end", "test")
        with self.assertRaises(SystemExit):
            session.parse(toks_fail, "test")

    def test_capture_raw_empty_body(self) -> None:
        class AsmBlock(RuleItem):
            nodeable = True
            entrypoint = Seq(
                MatchKeyword("asm"),
                MatchToken(Token.LBRACE),
                CaptureRaw(MatchToken(Token.RBRACE), balance_delimiters=(Token.LBRACE, Token.RBRACE)),
                MatchToken(Token.RBRACE),
            )

        class RootRule(RuleItem):
            nodeable = True
            entrypoint = Alt(Ref(AsmBlock))

        session = sessions.Session("AsmEmptySession", "Some")
        session.add_keyword("asm")
        session.entrypoint = RootRule

        # Empty body with only whitespace
        toks = session.tokenize("asm { }", "test")
        ast = session.parse(toks, "test")
        self.assertIsNotNone(ast)
        raw_node = ast[0].nodes[2]
        self.assertIsInstance(raw_node, RawNode)
        self.assertEqual(raw_node.text, "")
        self.assertEqual(raw_node.tokens, ())
        self.assertEqual(raw_node.token_count, 0)
        self.assertEqual(len(raw_node), 0)
        self.assertIsInstance(raw_node, RawNode)
        self.assertEqual(raw_node.text, "")
        self.assertEqual(raw_node.tokens, ())
        self.assertEqual(raw_node.token_count, 0)
        self.assertEqual(len(raw_node), 0)


if __name__ == "__main__":
    unittest.main()
