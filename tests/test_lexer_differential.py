"""
Differential and Contract Test Suite for the Python and Native C Lexers
(`tests/test_lexer_differential.py`).
=======================================================================
Verifies 100% parity between `Lexer(source, backend="python")` and
`Lexer(source, backend="c")`, validates golden fixtures, tests standalone C
runtime & `DiagnosticsLite` policies via `ctypes`, and verifies deterministic C
table export and compilation from `Session`.
"""
from __future__ import annotations

import ctypes
import json
import random
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from gram import errors
from gram.core.lexer.c_backend import (
    GRAM_DIAG_CODE_INDENTATION_MISMATCH,
    GRAM_DIAG_CODE_INVALID_NUMBER,
    GRAM_DIAG_CODE_INVALID_UTF8,
    GRAM_DIAG_CODE_UNCLOSED_STRING,
    GRAM_DIAG_CODE_UNEXPECTED_CHARACTER,
    GRAM_ERROR_POLICY_RECOVER,
    GRAM_ERROR_POLICY_STOP_ON_ERROR,
    GRAM_ERROR_POLICY_STOP_ON_FATAL,
    GRAM_LEXER_EOF,
    GRAM_LEXER_ERROR,
    GRAM_LEXER_FATAL,
    GRAM_LEXER_TOKEN,
    GramDiagBufferC,
    GramDiagSeverityOverrideC,
    GramDiagnosticC,
    GramDiagnosticSinkCFunc,
    GramDiagSinkC,
    GramLexerC,
    GramTokenC,
    _MarshaledTables,
    build_c_config,
    get_c_library,
)
from gram.core.lexer.core import Lexer
from gram.core.lexer.tokens import Token
from gram.sessions import Session
from tools.compare_lexers import compare_lexer_runs
from tools.export_lexer_tables import ABI_VERSION, export_session_tables

GOLDEN_FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "lexer" / "golden_cases.json"


def _make_session(**config_overrides) -> Session:
    session = Session("diff-test", "Many")
    session.config["LEXER_ADD_INFO"] = False
    session.config["ERROR_EXIT_ON_ERROR"] = False
    session.config.update(config_overrides)
    for kw in ("def", "if", "else", "elif", "while", "for", "return", "let", "fn", "match"):
        session.add_keyword(kw)
    session.add_group("control", ["if", "else", "elif", "while", "for", "return", "match"])
    session.add_group("decl", ["def", "let", "fn"])
    return session


class TestLexerDifferential(unittest.TestCase):
    """Differential tests comparing Python and C lexer backends across all contract areas."""

    def assert_parity(self, source: str | list[str], *, session: Session | None = None) -> None:
        active_session = session or _make_session()
        res = compare_lexer_runs(source, session=active_session)
        if not res.matched:
            self.fail("Python vs C lexer mismatch:\n" + "\n".join(res.mismatches))

    def test_default_backend_remains_python(self) -> None:
        session = _make_session()
        lexer = Lexer("let x = 1", session=session)
        self.assertEqual(lexer.backend, "python")
        with self.assertRaises(ValueError):
            Lexer("let x = 1", session=session, backend="invalid")  # type: ignore[arg-type]

    def test_empty_and_whitespace_sources(self) -> None:
        for src in ("", "\n", "\r\n", "\n\n", "   ", "   \n\t  \n"):
            with self.subTest(src=repr(src)):
                self.assert_parity(src)
                self.assert_parity(
                    src,
                    session=_make_session(
                        LEXER_IGNORE_EMPTY_LINES=False,
                        LEXER_IGNORE_NEWLINES=False,
                    ),
                )

    def test_keywords_groups_booleans_and_null(self) -> None:
        src = (
            "def if else elif while for return let fn match "
            "true FALSE True False null NULL Null "
            "ident_1 _private true_var null_ptr def_fn"
        )
        self.assert_parity(src)
        self.assert_parity(
            "si no nulo verdad falso",
            session=_make_session(
                TOKEN_BOOL_TRUE="verdad",
                TOKEN_BOOL_FALSE="falso",
                TOKEN_NULL="nulo",
            ),
        )

    def test_overlapping_symbols_and_maximal_munch(self) -> None:
        src = (
            "+ ++ += - -- -= -> * ** *= / // //= /= % %= "
            "= == != < <= << <<= <- <=> > >= >> >>= "
            "& && &= | || |= ^ ^= ! ? ?= := ... .. . "
            "( ) [ ] { } , : ; @ # $ \\ _ => "
            "∧ ∨ ¬ √ ∞ ° · • §"
        )
        session = _make_session()
        session.symbols["<=>"] = "SPACESHIP"
        session.symbol_order[:] = sorted(
            (k for k in session.symbols if isinstance(k, str)),
            key=len,
            reverse=True,
        )
        self.assert_parity(src, session=session)
        self.assert_parity(
            "a...b .. c . d",
            session=_make_session(SUPPORT_TRIPLE_DOT=False),
        )

    def test_numbers_valid_and_malformed(self) -> None:
        valid_numbers = (
            "0 42 1_000_000 0xdeadbeef 0XCAFE_BABE 0b1010_0101 0B11 0o755 0O17 "
            ".5 .125_4 0.0 3.14159 10. 1e10 1E+10 2.5e-3 0x1.8p+2 0x1p-4 0x.8p0 "
            "1u 1U 1l 1L 1ul 1ULL 0xffU 0b101L 3.14f 3.14F 2.0l 2.0L 0x1.fp2f"
        )
        self.assert_parity(valid_numbers)

        malformed_numbers = (
            "1__2 100_ 0x_1 0b_0 0o_7 123abc 0x1g 0b102 0o78 "
            "1.2.3 1e 1e+ 1e2e3 0x.p1 .5_ "
        )
        self.assert_parity(malformed_numbers)
        self.assert_parity(
            ".5 .0",
            session=_make_session(LEXER_SUPPORT_LEADING_DOT_NUMBERS=False),
        )

    def test_strings_prefixes_escapes_and_multiline(self) -> None:
        valid_strings = (
            "'a' \"b\" '' \"\" '\\n' '\\r' '\\t' '\\b' '\\f' '\\v' '\\0' '\\\\' '\\'' '\\\"' "
            "'\\u0041' '\\u03b1' \"\\u00e9\" \"unknown \\x \\q escapes\" "
            "u8\"utf8\" L\"wide\" u'char16' U'char32' "
            "\"\"\"multiline\nline 2\n\\tindented\\u0042\"\"\" "
            "'''single\r\ntriple\rquotes'''"
        )
        self.assert_parity(valid_strings)
        self.assert_parity(
            "u8\"no_prefix\" L'no_prefix' \"\"\"no_docstring\"\"\"",
            session=_make_session(
                LEXER_SUPPORT_PREFIXED_STRINGS=False,
                LEXER_SUPPORT_DOCSTRINGS=False,
            ),
        )

        unclosed_cases = [
            "\"unclosed single line\nx = 1",
            "'trailing backslash\\\ny = 2",
            "\"\"\"unclosed multiline\nline 2\nline 3",
            "u8\"unclosed prefixed\nz = 3",
        ]
        for case in unclosed_cases:
            with self.subTest(case=repr(case)):
                self.assert_parity(case)

    def test_comments_line_and_block(self) -> None:
        src = (
            "# pure comment line\n"
            "    # indented comment line\n"
            "def f(x): # inline comment\n"
            "    /* inline block */ return /* mid */ x + 1\n"
            "/* multiline\n"
            "   block comment */\n"
            "let y = 2\n"
        )
        self.assert_parity(src, session=_make_session(LEXER_SAVE_COMMENTS=True))
        self.assert_parity(src, session=_make_session(LEXER_SAVE_COMMENTS=False))
        self.assert_parity(
            "/* unclosed block comment\nstill inside comment",
            session=_make_session(LEXER_SAVE_COMMENTS=True),
        )

    def test_indentation_modes_and_mismatches(self) -> None:
        spaces_src = (
            "if true:\n"
            "    # comment inside block\n"
            "\n"
            "    if false:\n"
            "        while true:\n"
            "            return 1\n"
            "    return 2\n"
            "let done = true\n"
        )
        self.assert_parity(spaces_src, session=_make_session(LEXER_INDENT_STYLE="spaces"))

        tabs_src = "if true:\n\tif false:\n\t\treturn 1\n\treturn 2\n"
        self.assert_parity(
            tabs_src,
            session=_make_session(LEXER_INDENT_STYLE="tabs", LEXER_TAB_WIDTH=4),
        )

        mixed_src = "if true:\n  \treturn 1\n    \treturn 2\n"
        self.assert_parity(
            mixed_src,
            session=_make_session(LEXER_INDENT_STYLE="mixed", LEXER_TAB_WIDTH=4),
        )

        mismatch_src = (
            "if true:\n"
            "    if false:\n"
            "        return 1\n"
            "  return 2\n"
            "   return 3\n"
        )
        self.assert_parity(mismatch_src)
        self.assert_parity(
            mismatch_src,
            session=_make_session(SUPPORT_INDENT=False),
        )

    def test_unicode_valid_and_invalid_and_multiple_errors(self) -> None:
        unicode_src = (
            "let αβγ = переменная + 变量_1 + café\n"
            "let bad_digit = ١ + x١ + 🚀 + ~\n"
            "let more_errs = 0x_bad + \"unclosed\n"
            "return αβγ\n"
        )
        self.assert_parity(unicode_src)

        # Test invalid UTF-8 sequences directly in C runtime (overlong, surrogate, truncated)
        lib = get_c_library()
        session = _make_session()
        dummy_lexer = Lexer("", session=session)
        marshaled = _MarshaledTables(dummy_lexer)
        cfg = build_c_config(dummy_lexer)

        diags = (GramDiagnosticC * 16)()
        dbuf = GramDiagBufferC()
        lib.gram_diag_buffer_init(
            ctypes.byref(dbuf), diags, 16, GRAM_ERROR_POLICY_RECOVER
        )
        sink = lib.gram_diag_buffer_as_sink(ctypes.byref(dbuf))

        bad_bytes = b"let x = \xc0\xaf + \xed\xa0\x80 + \xf0\x9f\x9a\n"
        c_lexer = GramLexerC()
        lib.gram_lexer_init(
            ctypes.byref(c_lexer),
            bad_bytes,
            len(bad_bytes),
            ctypes.byref(cfg),
            ctypes.byref(marshaled.tables),
            sink,
            None,
        )
        tok = GramTokenC()
        error_tokens = 0
        while True:
            st = lib.gram_lexer_next(ctypes.byref(c_lexer), ctypes.byref(tok))
            if st == GRAM_LEXER_ERROR:
                error_tokens += 1
            if st in (GRAM_LEXER_EOF, GRAM_LEXER_FATAL):
                break
        self.assertGreaterEqual(error_tokens, 3)
        self.assertGreaterEqual(dbuf.count, 3)
        self.assertEqual(diags[0].code, GRAM_DIAG_CODE_INVALID_UTF8)

    def test_very_long_tokens_and_large_input(self) -> None:
        long_ident = "a" * 8192
        long_str = '"' + ("x\\n" * 2048) + '"'
        long_num = "9" * 4096
        self.assert_parity(f"let {long_ident} = {long_str} + {long_num}\n")

        lines = [
            f"def func_{i}(a_{i}, b_{i}):\n    if a_{i} >= {i}:\n        return a_{i} + b_{i} * 0x{i:x}\n"
            for i in range(400)
        ]
        self.assert_parity("".join(lines))

    def test_deterministic_random_fuzzing(self) -> None:
        rng = random.Random(20261030)
        fragments = [
            "def", "if", "else", "while", "return", "true", "false", "null",
            "foo", "_bar9", "αβ", "café", "0", "42", "0x1f", "0b101", ".25",
            "3.14e-2", "10ULL", "1__2", "0x_f", "'c'", "'\\n'", "\"str\\u0041\"",
            "u8\"hi\"", "\"\"\"doc\nline\"\"\"", "+", "-", ">>=", "...", "<=>",
            "==", "!=", "(", ")", ":", "#", "/*blk*/", "@", "~", "١", " ", "\t",
        ]
        for seed_iter in range(25):
            lines: list[str] = []
            indent = 0
            for _ in range(15):
                delta = rng.choice([-4, 0, 0, 4, 2])
                indent = max(0, min(16, indent + delta))
                row = [rng.choice(fragments) for _ in range(rng.randint(1, 10))]
                lines.append((" " * indent) + " ".join(row))
            src = "\n".join(lines) + "\n"
            with self.subTest(seed_iter=seed_iter):
                self.assert_parity(src)

    def test_golden_fixtures(self) -> None:
        session = _make_session()
        cases = [
            {"name": "empty_source", "source": ""},
            {
                "name": "basic_function",
                "source": "def calc(x, y):\n    if x >= y:\n        return x + y\n    return 0\n",
            },
            {
                "name": "numbers_and_suffixes",
                "source": "0 42 1_000 0xFF 0b1010 0o77 .5 3.14 1e-9 0x1.8p+2 10ULL 3.14f",
            },
            {
                "name": "strings_and_escapes",
                "source": "'a' '\\n' '\\u0041' \"hello\\tworld\" u8\"utf8\" L'w' \"\"\"multi\nline\"\"\"",
            },
            {
                "name": "comments_and_operators",
                "source": "# header\nx = 1 >>= 2 # inline\n/* block\ncomment */ y := x ...",
            },
            {"name": "unicode_identifiers", "source": "let αβγ = café_1 + 变量\n"},
            {
                "name": "lexical_errors_recovery",
                "source": "x = @\ny = 0x_1\nz = \"unclosed\nw = 1\n",
            },
        ]
        if not GOLDEN_FIXTURE_PATH.exists():
            GOLDEN_FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
            payload = []
            for c in cases:
                r = compare_lexer_runs(c["source"], session=session)
                self.assertTrue(r.matched, r.mismatches)
                payload.append(
                    {
                        "name": c["name"],
                        "source": c["source"],
                        "tokens": [t.to_dict() for t in r.python_tokens],
                        "comments": [cm.to_dict() for cm in r.python_comments],
                        "diagnostics": [d.to_dict() for d in r.python_diagnostics],
                    }
                )
            GOLDEN_FIXTURE_PATH.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

        golden_data = json.loads(GOLDEN_FIXTURE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(len(golden_data), len(cases))
        for entry in golden_data:
            with self.subTest(fixture=entry["name"]):
                res = compare_lexer_runs(entry["source"], session=session)
                self.assertTrue(res.matched, res.mismatches)
                self.assertEqual([t.to_dict() for t in res.c_tokens], entry["tokens"])
                self.assertEqual([c.to_dict() for c in res.c_comments], entry["comments"])
                self.assertEqual([d.to_dict() for d in res.c_diagnostics], entry["diagnostics"])

    def test_diagnostics_lite_sinks_limits_and_policies(self) -> None:
        lib = get_c_library()
        session = _make_session()
        dummy_lexer = Lexer("", session=session)
        marshaled = _MarshaledTables(dummy_lexer)
        cfg = build_c_config(dummy_lexer)

        # 1. Max limit + user callback sink + message arena
        diags = (GramDiagnosticC * 8)()
        arena = ctypes.create_string_buffer(512)
        dbuf = GramDiagBufferC()
        lib.gram_diag_buffer_init(ctypes.byref(dbuf), diags, 8, GRAM_ERROR_POLICY_RECOVER)
        lib.gram_diag_buffer_set_message_arena(
            ctypes.byref(dbuf), ctypes.cast(arena, ctypes.c_char_p), 512
        )
        lib.gram_diag_buffer_set_max_limit(ctypes.byref(dbuf), 2)

        cb_codes: list[int] = []

        @GramDiagnosticSinkCFunc
        def _user_cb(_ctx: int, d_ptr) -> None:
            cb_codes.append(int(d_ptr.contents.code))

        lib.gram_diag_buffer_set_user_sink(
            ctypes.byref(dbuf), GramDiagSinkC(context=None, emit=_user_cb)
        )
        sink = lib.gram_diag_buffer_as_sink(ctypes.byref(dbuf))

        src = b"0x_1 0b_2 1__3 \"unclosed\n"
        c_lexer = GramLexerC()
        lib.gram_lexer_init(
            ctypes.byref(c_lexer),
            src,
            len(src),
            ctypes.byref(cfg),
            ctypes.byref(marshaled.tables),
            sink,
            None,
        )
        tok = GramTokenC()
        while lib.gram_lexer_next(ctypes.byref(c_lexer), ctypes.byref(tok)) not in (
            GRAM_LEXER_EOF,
            GRAM_LEXER_FATAL,
        ):
            pass

        self.assertEqual(dbuf.count, 2)
        self.assertEqual(dbuf.total_emitted, 4)
        self.assertEqual(dbuf.dropped_count, 2)
        self.assertEqual(len(cb_codes), 2)

        # 2. Severity override upgrading an error to FATAL under STOP_ON_FATAL
        lib.gram_diag_buffer_init(
            ctypes.byref(dbuf), diags, 8, GRAM_ERROR_POLICY_STOP_ON_FATAL
        )
        overrides = (GramDiagSeverityOverrideC * 1)()
        overrides[0].code = GRAM_DIAG_CODE_UNEXPECTED_CHARACTER
        overrides[0].severity = 4  # GRAM_DIAG_FATAL
        lib.gram_diag_buffer_set_overrides(ctypes.byref(dbuf), overrides, 1)
        cfg.error_policy = GRAM_ERROR_POLICY_STOP_ON_FATAL

        lib.gram_lexer_init(
            ctypes.byref(c_lexer),
            b"` + 1",
            5,
            ctypes.byref(cfg),
            ctypes.byref(marshaled.tables),
            lib.gram_diag_buffer_as_sink(ctypes.byref(dbuf)),
            None,
        )
        st = lib.gram_lexer_next(ctypes.byref(c_lexer), ctypes.byref(tok))
        self.assertEqual(st, GRAM_LEXER_FATAL)
        self.assertEqual(dbuf.halted, 1)
        self.assertEqual(dbuf.fatal_count, 1)

    def test_session_c_table_exporter_and_gcc_compilation(self) -> None:
        session = _make_session()
        session.symbols["<=>"] = "SPACESHIP"

        with tempfile.TemporaryDirectory() as tmpdir:
            m1 = export_session_tables(session, tmpdir)
            m2 = export_session_tables(session, tmpdir)
            self.assertEqual(m1["content_hash"], m2["content_hash"])
            self.assertEqual(m1["abi_version"], ABI_VERSION)
            self.assertEqual(m1["abi_version"], "1.1")

            for fname in (
                "gram_lexer_config.h",
                "gram_lexer_keywords.c",
                "gram_lexer_groups.c",
                "gram_lexer_symbols.c",
                "gram_lexer_codes.h",
                "gram_lexer_manifest.json",
            ):
                self.assertTrue((Path(tmpdir) / fname).exists(), fname)

            compiler = shutil.which("gcc") or shutil.which("clang")
            self.assertIsNotNone(compiler)
            inc_dir = Path(__file__).resolve().parents[1] / "native" / "gram_lexer" / "include"
            src_dir = Path(__file__).resolve().parents[1] / "native" / "gram_lexer" / "src"

            # Write a tiny C harness that links the exported tables with the C runtime
            harness_c = Path(tmpdir) / "test_exported_main.c"
            harness_c.write_text(
                '#include "gram_lexer_config.h"\n'
                "#include <assert.h>\n"
                "#include <string.h>\n"
                "int main(void) {\n"
                "    GramLexerConfig cfg = gram_exported_lexer_config();\n"
                "    GramLexer lexer;\n"
                "    GramToken tok;\n"
                '    const char *src = "def f(x):\\n    return x <=> 1\\n";\n'
                "    gram_lexer_init(&lexer, src, (uint32_t)strlen(src), &cfg, &GRAM_EXPORTED_TABLES, gram_diag_null_sink(), NULL);\n"
                "    assert(gram_lexer_next(&lexer, &tok) == GRAM_LEXER_TOKEN && tok.kind == GRAM_TOKEN_KEYWORD);\n"
                "    return 0;\n"
                "}\n",
                encoding="utf-8",
            )
            exe_path = Path(tmpdir) / "test_exported.exe"
            cmd = [
                compiler,
                "-std=c11",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-I",
                str(inc_dir),
                "-I",
                str(tmpdir),
                *[str(p) for p in sorted(src_dir.glob("*.c"))],
                str(Path(tmpdir) / "gram_lexer_keywords.c"),
                str(Path(tmpdir) / "gram_lexer_groups.c"),
                str(Path(tmpdir) / "gram_lexer_symbols.c"),
                str(harness_c),
                "-o",
                str(exe_path),
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
            run_proc = subprocess.run([str(exe_path)], capture_output=True, text=True, check=False)
            self.assertEqual(run_proc.returncode, 0, run_proc.stderr or run_proc.stdout)

        # Verify exporter rejects invalid configurations
        bad_session = _make_session(LEXER_INDENT_STYLE="invalid_mode")
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(ValueError):
                export_session_tables(bad_session, tmpdir)

    def test_native_c_unit_suite(self) -> None:
        compiler = shutil.which("gcc") or shutil.which("clang")
        self.assertIsNotNone(compiler)
        root = Path(__file__).resolve().parents[1] / "native" / "gram_lexer"
        inc_dir = root / "include"
        src_dir = root / "src"
        test_c = root / "tests" / "test_c_runtime.c"

        with tempfile.TemporaryDirectory() as tmpdir:
            exe_path = Path(tmpdir) / "test_c_runtime.exe"
            cmd = [
                compiler,
                "-std=c11",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-O2",
                "-I",
                str(inc_dir),
                *[str(p) for p in sorted(src_dir.glob("*.c"))],
                str(test_c),
                "-o",
                str(exe_path),
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
            run_proc = subprocess.run([str(exe_path)], capture_output=True, text=True, check=False)
            self.assertEqual(run_proc.returncode, 0, run_proc.stderr or run_proc.stdout)
            self.assertIn("All C runtime unit tests passed", run_proc.stdout)


if __name__ == "__main__":
    unittest.main()
