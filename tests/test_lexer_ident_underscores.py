"""
Tests for lexer identifier underscore configuration (`LEXER_IDENT_UNDERSCORES` / `ident_underscores`).
====================================================================================================
Verifies:
- Mode -1 (default): unlimited leading underscores, pure underscore sequences are IDENT.
- Mode -2: unlimited leading underscores if followed by alnum; pure underscore sequences are UNDERSCORE tokens.
- Mode 0: no IDENT allows underscores (leading or internal); all underscores become UNDERSCORE tokens.
- Mode 1..k: at most k leading underscores in IDENT; excess leading underscores become individual UNDERSCORE tokens.
- Parity between Python lexer backend and Native C lexer backend.
- End-to-end C AOT parser compilation and execution with ident_underscores.
"""
from __future__ import annotations

import pathlib
import shutil
import subprocess
import tempfile
import unittest

from gram import sessions
from gram.core.combinators import MatchKeyword, MatchToken, RuleItem, Seq
from gram.core.lexer import Token


class TestLexerIdentUnderscores(unittest.TestCase):
    def _tokens(self, session: sessions.Session, text: str, backend: str = "python") -> list[tuple[str, object]]:
        toks = session.tokenize(text, "test", backend=backend)  # type: ignore[call-arg]
        return [(t.token.name, t.value) for t in toks if t.token != Token.EOF]

    def test_default_mode_minus_1(self) -> None:
        """Mode -1 (default): unlimited leading underscores; standalone underscores are IDENT."""
        session = sessions.Session("ModeMinus1", "Some")
        session.add_keyword("kw")
        self.assertEqual(session.ident_underscores, -1)

        # Standalone underscores remain single IDENT
        self.assertEqual(self._tokens(session, "_"), [("IDENT", "_")])
        self.assertEqual(self._tokens(session, "___"), [("IDENT", "___")])

        # Arbitrary leading underscores
        self.assertEqual(self._tokens(session, "_H"), [("IDENT", "_H")])
        self.assertEqual(self._tokens(session, "__H"), [("IDENT", "__H")])
        self.assertEqual(self._tokens(session, "___H"), [("IDENT", "___H")])
        self.assertEqual(
            self._tokens(session, "_____________________________________________________Hola"),
            [("IDENT", "_____________________________________________________Hola")],
        )

        # Internal underscores
        self.assertEqual(self._tokens(session, "foo_bar"), [("IDENT", "foo_bar")])
        self.assertEqual(self._tokens(session, "foo__bar"), [("IDENT", "foo__bar")])

    def test_mode_minus_2(self) -> None:
        """Mode -2: unlimited leading underscores IF followed by alnum; standalone underscores become UNDERSCORE tokens."""
        session = sessions.Session("ModeMinus2", "Some", ident_underscores=-2)
        session.add_keyword("kw")
        self.assertEqual(session.ident_underscores, -2)

        # Standalone underscores must have a character; otherwise emitted as individual UNDERSCORE tokens
        self.assertEqual(self._tokens(session, "_"), [("UNDERSCORE", "_")])
        self.assertEqual(
            self._tokens(session, "___"),
            [("UNDERSCORE", "_"), ("UNDERSCORE", "_"), ("UNDERSCORE", "_")],
        )

        # Followed by alnum: unlimited leading underscores allowed
        self.assertEqual(self._tokens(session, "_H"), [("IDENT", "_H")])
        self.assertEqual(self._tokens(session, "__H"), [("IDENT", "__H")])
        self.assertEqual(self._tokens(session, "___H"), [("IDENT", "___H")])
        self.assertEqual(
            self._tokens(session, "_____________________________________________________Hola"),
            [("IDENT", "_____________________________________________________Hola")],
        )

        # Internal underscores allowed
        self.assertEqual(self._tokens(session, "foo_bar"), [("IDENT", "foo_bar")])

    def test_mode_0(self) -> None:
        """Mode 0: no leading underscores allowed in IDENT; internal and trailing underscores remain part of IDENT."""
        session = sessions.Session("Mode0", "Some", ident_underscores=0)
        session.add_keyword("kw")
        self.assertEqual(session.ident_underscores, 0)

        # Standalone underscores
        self.assertEqual(self._tokens(session, "_"), [("UNDERSCORE", "_")])
        self.assertEqual(
            self._tokens(session, "___"),
            [("UNDERSCORE", "_"), ("UNDERSCORE", "_"), ("UNDERSCORE", "_")],
        )

        # Leading underscores: underscore is separated from identifier
        self.assertEqual(
            self._tokens(session, "_H"),
            [("UNDERSCORE", "_"), ("IDENT", "H")],
        )
        self.assertEqual(
            self._tokens(session, "__H"),
            [("UNDERSCORE", "_"), ("UNDERSCORE", "_"), ("IDENT", "H")],
        )

        # Internal and trailing underscores starting with letter are completely preserved
        self.assertEqual(self._tokens(session, "A______B"), [("IDENT", "A______B")])
        self.assertEqual(self._tokens(session, "D____________"), [("IDENT", "D____________")])
        self.assertEqual(self._tokens(session, "foo_bar"), [("IDENT", "foo_bar")])

    def test_mode_1(self) -> None:
        """Mode 1: at most 1 leading underscore in IDENT; excess leading underscores become individual UNDERSCORE tokens."""
        session = sessions.Session("Mode1", "Some", ident_underscores=1)
        session.add_keyword("kw")
        self.assertEqual(session.ident_underscores, 1)

        # Standalone underscores have no character -> individual UNDERSCORE tokens
        self.assertEqual(self._tokens(session, "_"), [("UNDERSCORE", "_")])
        self.assertEqual(
            self._tokens(session, "__"),
            [("UNDERSCORE", "_"), ("UNDERSCORE", "_")],
        )

        # Exactly 1 leading underscore -> valid IDENT
        self.assertEqual(self._tokens(session, "_H"), [("IDENT", "_H")])

        # 2 leading underscores -> 1 excess UNDERSCORE token, then IDENT("_H")
        self.assertEqual(
            self._tokens(session, "__H"),
            [("UNDERSCORE", "_"), ("IDENT", "_H")],
        )

        # 3 leading underscores -> 2 excess UNDERSCORE tokens, then IDENT("_H")
        self.assertEqual(
            self._tokens(session, "___H"),
            [("UNDERSCORE", "_"), ("UNDERSCORE", "_"), ("IDENT", "_H")],
        )

        # Internal underscores allowed
        self.assertEqual(self._tokens(session, "foo_bar"), [("IDENT", "foo_bar")])
        self.assertEqual(self._tokens(session, "_foo_bar"), [("IDENT", "_foo_bar")])

    def test_mode_2(self) -> None:
        """Mode 2: at most 2 leading underscores in IDENT; excess leading underscores become individual UNDERSCORE tokens."""
        session = sessions.Session("Mode2", "Some", ident_underscores=2)
        session.add_keyword("kw")
        self.assertEqual(session.ident_underscores, 2)

        # Standalone
        self.assertEqual(
            self._tokens(session, "___"),
            [("UNDERSCORE", "_"), ("UNDERSCORE", "_"), ("UNDERSCORE", "_")],
        )

        # Up to 2 leading underscores
        self.assertEqual(self._tokens(session, "_H"), [("IDENT", "_H")])
        self.assertEqual(self._tokens(session, "__H"), [("IDENT", "__H")])

        # 3 leading underscores -> 1 excess UNDERSCORE, then IDENT("__H")
        self.assertEqual(
            self._tokens(session, "___H"),
            [("UNDERSCORE", "_"), ("IDENT", "__H")],
        )

        # 4 leading underscores -> 2 excess UNDERSCOREs, then IDENT("__H")
        self.assertEqual(
            self._tokens(session, "____H"),
            [("UNDERSCORE", "_"), ("UNDERSCORE", "_"), ("IDENT", "__H")],
        )

    def test_backend_c_differential_parity(self) -> None:
        """Verify differential parity between Python backend and native C backend across all modes."""
        cases = [
            (-1, "_ __ ___ _H __H ___H ____Hola foo_bar A______B D____________"),
            (-2, "_ __ ___ _H __H ___H ____Hola foo_bar A______B D____________"),
            (0, "_ __ ___ _H __H ___H ____Hola foo_bar A______B D____________"),
            (1, "_ __ ___ _H __H ___H ____Hola foo_bar A______B D____________"),
            (2, "_ __ ___ _H __H ___H ____Hola foo_bar A______B D____________"),
            (3, "_ __ ___ _H __H ___H ____Hola foo_bar A______B D____________"),
        ]

        for mode, text in cases:
            with self.subTest(mode=mode, text=text):
                session = sessions.Session(f"DiffMode_{mode}", "Some", ident_underscores=mode)
                session.add_keyword("kw")

                py_tokens = self._tokens(session, text, backend="python")
                c_tokens = self._tokens(session, text, backend="c")
                self.assertEqual(py_tokens, c_tokens, f"Mismatch in mode {mode} for input: {text!r}")

    def test_aot_c_compiler_execution_with_ident_underscores(self) -> None:
        """Compile a grammar to C with ident_underscores=1 and verify standalone CLI accepts parsed AST."""
        if shutil.which("gcc") is None:
            self.skipTest("GCC is required for native AOT CLI compilation test")

        class ItemRule(RuleItem):
            nodeable = True
            entrypoint = Seq(
                MatchToken(Token.UNDERSCORE),
                MatchToken(Token.IDENT),
                MatchKeyword("end"),
            )
            rule = entrypoint

        session = sessions.Session("AotUnderscoreSession", "Some", ident_underscores=1)
        session.add_keyword("end")
        session.entrypoint = ItemRule

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
            out_dir = pathlib.Path(tmp_dir)
            session.export_c_parser(out_dir, emit_driver=True, emit_cli=True)

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

            # Input: "__H end"
            # In mode 1, "__H" is split into: UNDERSCORE ("_") and IDENT ("_H").
            # The grammar expects: UNDERSCORE, IDENT, "end".
            # Thus, "__H end" matches ItemRule!
            src_file = out_dir / "test.src"
            src_file.write_text("__H end", encoding="utf-8")
            res = subprocess.run([str(cli_exe), "check", str(src_file)], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, f"CLI check failed: {res.stderr}")

            # Input: "_H end"
            # In mode 1, "_H" is single IDENT ("_H"). The grammar expects UNDERSCORE first, so it must fail!
            src_fail = out_dir / "fail.src"
            src_fail.write_text("_H end", encoding="utf-8")
            res_fail = subprocess.run([str(cli_exe), "check", str(src_fail)], capture_output=True, text=True)
            self.assertEqual(res_fail.returncode, 2, "Expected syntax error because UNDERSCORE was missing")


if __name__ == "__main__":
    unittest.main()
