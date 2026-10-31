"""
Differential Lexer Comparator (`tools/compare_lexers.py`).
==========================================================
Compares the output of the Python and native C lexer backends on arbitrary
source inputs, verifying 100% parity across token kinds, values, flags,
descriptions, 1-based lines, 0-based columns, saved comments, and diagnostics.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from gram.core.lexer.core import Lexer
from gram.core.lexer.tokens import Token, TokenType
from gram.sessions import Session


@dataclass(slots=True)
class NormalizedToken:
    kind: str
    kind_id: int | str
    value: Any
    line: int
    col: int
    flags: int
    description: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "kind_id": self.kind_id,
            "value": self.value,
            "line": self.line,
            "col": self.col,
            "flags": self.flags,
            "description": self.description,
        }


@dataclass(slots=True)
class NormalizedDiagnostic:
    osgdc_code: str
    code_name: str

    def to_dict(self) -> dict[str, str]:
        return {
            "osgdc_code": self.osgdc_code,
            "code_name": self.code_name,
        }


@dataclass(slots=True)
class ComparisonResult:
    matched: bool
    python_tokens: list[NormalizedToken]
    c_tokens: list[NormalizedToken]
    python_comments: list[NormalizedToken]
    c_comments: list[NormalizedToken]
    python_diagnostics: list[NormalizedDiagnostic]
    c_diagnostics: list[NormalizedDiagnostic]
    mismatches: list[str] = field(default_factory=list)


def normalize_token(tok: TokenType) -> NormalizedToken:
    if isinstance(tok.token, Token):
        kind_name = tok.token.name
        kind_id: int | str = int(tok.token.value)
    else:
        kind_name = str(tok.token)
        kind_id = str(tok.token)
    return NormalizedToken(
        kind=kind_name,
        kind_id=kind_id,
        value=tok.value,
        line=tok.line,
        col=tok.col,
        flags=int(tok.flags),
        description=tok.description or "",
    )


def normalize_diagnostics(lexer: Lexer) -> list[NormalizedDiagnostic]:
    result: list[NormalizedDiagnostic] = []
    for err in getattr(lexer, "_errors", []):
        code_obj = getattr(err, "code", None)
        osgdc = getattr(code_obj, "code_string", "") if code_obj is not None else ""
        cname = getattr(code_obj, "name", "") if code_obj is not None else ""
        result.append(NormalizedDiagnostic(osgdc_code=osgdc, code_name=cname))
    return result


def compare_lexer_runs(
    source: str | list[str] | Path,
    *,
    session: Session | None = None,
) -> ComparisonResult:
    """Run Python and C lexers on `source` and return a detailed `ComparisonResult`."""
    py_lexer = Lexer(source, session=session, backend="python")
    c_lexer = Lexer(source, session=session, backend="c")

    py_raw_tokens = py_lexer.process()
    c_raw_tokens = c_lexer.process()

    py_tokens = [normalize_token(t) for t in py_raw_tokens]
    c_tokens = [normalize_token(t) for t in c_raw_tokens]
    py_comments = [normalize_token(t) for t in py_lexer.comments]
    c_comments = [normalize_token(t) for t in c_lexer.comments]
    py_diags = normalize_diagnostics(py_lexer)
    c_diags = normalize_diagnostics(c_lexer)

    mismatches: list[str] = []

    if len(py_tokens) != len(c_tokens):
        mismatches.append(
            f"Token count mismatch: python={len(py_tokens)} vs c={len(c_tokens)}"
        )

    for idx, (pt, ct) in enumerate(zip(py_tokens, c_tokens)):
        if pt != ct:
            mismatches.append(f"Token[{idx}] mismatch:\n  python={pt}\n  c     ={ct}")

    if len(py_comments) != len(c_comments):
        mismatches.append(
            f"Comment count mismatch: python={len(py_comments)} vs c={len(c_comments)}"
        )

    for idx, (pc, cc) in enumerate(zip(py_comments, c_comments)):
        if pc != cc:
            mismatches.append(f"Comment[{idx}] mismatch:\n  python={pc}\n  c     ={cc}")

    if len(py_diags) != len(c_diags):
        mismatches.append(
            f"Diagnostic count mismatch: python={len(py_diags)} vs c={len(c_diags)}"
        )

    for idx, (pd, cd) in enumerate(zip(py_diags, c_diags)):
        if pd != cd:
            mismatches.append(f"Diagnostic[{idx}] mismatch:\n  python={pd}\n  c     ={cd}")

    return ComparisonResult(
        matched=(len(mismatches) == 0),
        python_tokens=py_tokens,
        c_tokens=c_tokens,
        python_comments=py_comments,
        c_comments=c_comments,
        python_diagnostics=py_diags,
        c_diagnostics=c_diags,
        mismatches=mismatches,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compare Python and native C lexer outputs on a source file or snippet."
    )
    parser.add_argument("input", nargs="?", default="def add(a, b):\n    return a + b\n")
    parser.add_argument("--file", action="store_true", help="Treat input as a file path.")
    args = parser.parse_args(argv)

    session = Session("compare", "Many")
    session.config["LEXER_ADD_INFO"] = False
    session.config["ERROR_EXIT_ON_ERROR"] = False
    for kw in ("def", "if", "else", "while", "return", "let", "fn"):
        session.add_keyword(kw)

    src: str | Path = Path(args.input) if args.file else args.input
    res = compare_lexer_runs(src, session=session)
    if res.matched:
        print(
            f"OK: Python and C lexers matched identically "
            f"({len(res.python_tokens)} tokens, {len(res.python_comments)} comments, "
            f"{len(res.python_diagnostics)} diagnostics)."
        )
        return 0

    print("MISMATCH DETECTED:")
    for m in res.mismatches:
        print(" -", m)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
