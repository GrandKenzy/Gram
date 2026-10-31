"""
Python vs AOT Compiled C Parser Benchmark Suite (`benchmarks/parser_python_vs_c.py`).
===================================================================================
Compares the full frontend pipeline:
  1. Python runtime: Lexer + Parser + AST Construction (`Session.parse(source)`)
  2. AOT C11 runtime: Zero-copy File Opener + Lexer + Pratt Parser + AST Arena (`gram_parse_file` / CLI)

Grammar under test:
  - Structured language with Pratt binary/unary expressions
  - Function declarations: `fn name(arg1, arg2) { ... }`
  - Variable bindings: `let x = expr;`
  - Control flow: `if (expr) { ... } else { ... }`, `while (expr) { ... }`, `return expr;`
  - Function calls: `ident(arg1, arg2)`
  - Keyword groups: `$TYPES`, control flow keywords, punctuation, identifiers, numbers.

Usage:
  python benchmarks/parser_python_vs_c.py [--iterations 20] [--funcs 150]
"""
from __future__ import annotations

import argparse
import os
import platform
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from gram import sessions
from gram.core.combinators import (
    Alt,
    DualExpr,
    Enclosed,
    Many,
    MatchGroup,
    MatchKeyword,
    MatchToken,
    Opt,
    Ref,
    RuleItem,
    Separator,
    Seq,
)
from gram.core.lexer.tokens import Token


def build_benchmark_grammar() -> sessions.Session:
    """Build a rich, realistic grammar session with Pratt expressions and statements."""
    s = sessions.Session("bench_lang", "Many")

    for kw in ("fn", "let", "if", "else", "while", "return"):
        s.add_keyword(kw)

    for ty in ("int", "float", "bool", "string", "void"):
        s.add_keyword(ty)
    s.add_group("$TYPES", ["int", "float", "bool", "string", "void"])

    # Grammar Rules
    class TypeRef(RuleItem):
        nodeable = True
        entrypoint = MatchGroup("$TYPES")
        rule = entrypoint

    class ExprRule(RuleItem):
        nodeable = True

    class CallExpr(RuleItem):
        nodeable = True
        entrypoint = Seq(
            MatchToken(Token.IDENT),
            MatchToken(Token.LPAREN),
            Opt(Separator(Ref(ExprRule), sep=MatchToken(Token.COMMA))),
            MatchToken(Token.RPAREN),
        )
        rule = entrypoint

    class PrimaryExpr(RuleItem):
        nodeable = True
        entrypoint = Alt(
            Ref(CallExpr),
            MatchToken(Token.NUMBER),
            MatchToken(Token.DECIMAL),
            MatchToken(Token.BOOL),
            MatchToken(Token.IDENT),
            MatchToken(Token.STRING),
        )
        rule = entrypoint

    # Pratt expression loops
    ExprRule.entrypoint = DualExpr(
        Ref(PrimaryExpr, name="prim"),
        Token.NUMBER,
        Token.DECIMAL,
        Token.BOOL,
        Token.IDENT,
    )
    ExprRule.rule = ExprRule.entrypoint

    class LetStmt(RuleItem):
        nodeable = True
        entrypoint = Seq(
            MatchKeyword("let"),
            MatchToken(Token.IDENT),
            Opt(Seq(MatchToken(Token.COLON), Ref(TypeRef))),
            MatchToken(Token.ASSIGN),
            Ref(ExprRule),
            MatchToken(Token.SEMICOLON),
        )
        rule = entrypoint

    class AssignStmt(RuleItem):
        nodeable = True
        entrypoint = Seq(
            MatchToken(Token.IDENT),
            MatchToken(Token.ASSIGN),
            Ref(ExprRule),
            MatchToken(Token.SEMICOLON),
        )
        rule = entrypoint

    class ReturnStmt(RuleItem):
        nodeable = True
        entrypoint = Seq(
            MatchKeyword("return"),
            Opt(Ref(ExprRule)),
            MatchToken(Token.SEMICOLON),
        )
        rule = entrypoint

    class StmtRule(RuleItem):
        nodeable = False

    class Block(RuleItem):
        nodeable = True
        entrypoint = Seq(
            MatchToken(Token.LBRACE),
            Many(Ref(StmtRule)),
            MatchToken(Token.RBRACE),
        )
        rule = entrypoint

    class IfStmt(RuleItem):
        nodeable = True
        entrypoint = Seq(
            MatchKeyword("if"),
            MatchToken(Token.LPAREN),
            Ref(ExprRule),
            MatchToken(Token.RPAREN),
            Ref(Block),
            Opt(Seq(MatchKeyword("else"), Ref(Block))),
        )
        rule = entrypoint

    class WhileStmt(RuleItem):
        nodeable = True
        entrypoint = Seq(
            MatchKeyword("while"),
            MatchToken(Token.LPAREN),
            Ref(ExprRule),
            MatchToken(Token.RPAREN),
            Ref(Block),
        )
        rule = entrypoint

    class ExprStmt(RuleItem):
        nodeable = True
        entrypoint = Seq(Ref(ExprRule), MatchToken(Token.SEMICOLON))
        rule = entrypoint

    StmtRule.entrypoint = Alt(
        Ref(LetStmt),
        Ref(AssignStmt),
        Ref(ReturnStmt),
        Ref(IfStmt),
        Ref(WhileStmt),
        Ref(ExprStmt),
    )
    StmtRule.rule = StmtRule.entrypoint

    class Param(RuleItem):
        nodeable = True
        entrypoint = Seq(
            MatchToken(Token.IDENT),
            MatchToken(Token.COLON),
            Ref(TypeRef),
        )
        rule = entrypoint

    class FuncDef(RuleItem):
        nodeable = True
        entrypoint = Seq(
            MatchKeyword("fn"),
            MatchToken(Token.IDENT),
            MatchToken(Token.LPAREN),
            Opt(Separator(Ref(Param), sep=MatchToken(Token.COMMA))),
            MatchToken(Token.RPAREN),
            Opt(Seq(MatchToken(Token.ARROW), Ref(TypeRef))),
            Ref(Block),
        )
        rule = entrypoint

    class TopLevel(RuleItem):
        nodeable = True
        entrypoint = Alt(Ref(FuncDef), Ref(LetStmt))
        rule = entrypoint

    s.entrypoint = TopLevel
    return s


def generate_benchmark_source(function_count: int = 100) -> str:
    """Generate realistic, deterministic source code for the benchmark grammar."""
    lines: list[str] = [
        "let global_seed: int = 42;",
        "",
    ]
    for i in range(function_count):
        lines.extend([
            f"fn compute_kernel_{i}(x: int, y: float, flag: bool) -> int {{",
            f"let acc: int = (x * 2) + 10;",
            f"let limit: int = 100;",
            f"while (acc < limit) {{",
            f"acc = acc + 1;",
            f"if (acc == 50) {{",
            f"acc = acc + 5;",
            f"}} else {{",
            f"acc = acc + 2;",
            f"}}",
            f"}}",
            f"if (flag) {{",
            f"let r: int = compute_kernel_{i}(acc, 3.14, false);",
            f"return r;",
            f"}}",
            f"return acc + x;",
            f"}}",
            "",
        ])
    return "\n".join(lines)


def compile_native_c(session: sessions.Session, temp_dir: Path) -> Path:
    """Export the grammar to C and compile a standalone executable with GCC."""
    gcc = shutil.which("gcc")
    if not gcc:
        raise RuntimeError("GCC compiler not found in PATH")

    session.export_c_parser(temp_dir, emit_driver=True, emit_cli=True)

    native_inc = PROJECT_ROOT / "native" / "gram_lexer" / "include"
    native_src = PROJECT_ROOT / "native" / "gram_lexer" / "src"

    sources = [
        "gram_ast.c",
        "gram_parser.c",
        "gram_ir.c",
        "gram_driver.c",
        "gram_lexer_keywords.c",
        "gram_lexer_symbols.c",
        "gram_lexer_groups.c",
    ]
    common = [str(temp_dir / name) for name in sources] + [
        str(native_src / name)
        for name in (
            "lexer.c",
            "indentation.c",
            "numbers.c",
            "strings.c",
            "symbols.c",
            "utf8.c",
            "diagnostics_lite.c",
        )
    ]
    exe_name = "gram_bench.exe" if os.name == "nt" else "gram_bench"
    exe_path = temp_dir / exe_name

    cmd = [
        gcc,
        "-std=c11",
        "-O2",
        "-Wall",
        "-Wextra",
        f"-I{native_inc}",
        f"-I{native_src}",
        f"-I{temp_dir}",
        str(temp_dir / "gram_cli.c"),
        *common,
        "-o",
        str(exe_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    return exe_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Gram Python vs Native C Parser Benchmark")
    parser.add_argument("--iterations", type=int, default=10, help="Number of timed iterations (default: 10)")
    parser.add_argument("--funcs", type=int, default=100, help="Number of functions to generate (default: 100)")
    parser.add_argument("--warmup", type=int, default=2, help="Number of warmup iterations (default: 2)")
    args = parser.parse_args()

    print("=" * 78)
    print("  Gram Framework — Python vs Native C AOT Parser Benchmark")
    print("=" * 78)
    print(f"Platform:      {platform.system()} {platform.release()} ({platform.machine()})")
    print(f"Python:        {sys.version.split()[0]}")
    gcc = shutil.which("gcc")
    if gcc:
        gcc_ver = subprocess.run([gcc, "--version"], capture_output=True, text=True).stdout.splitlines()[0]
        print(f"Compiler:      {gcc_ver} (-O2 -std=c11)")
    else:
        print("Compiler:      GCC not found!")
        sys.exit(1)

    print("\n[1/3] Generating benchmark grammar and synthetic codebase...")
    session = build_benchmark_grammar()
    source_code = generate_benchmark_source(args.funcs)
    source_bytes = source_code.encode("utf-8")
    line_count = source_code.count("\n")
    byte_count = len(source_bytes)

    print(f"      Source Size:  {byte_count:,} bytes ({byte_count / 1024:.1f} KB)")
    print(f"      Lines:        {line_count:,} lines")
    print(f"      Functions:    {args.funcs} functions")

    with tempfile.TemporaryDirectory() as td:
        temp_dir = Path(td)
        src_file = temp_dir / "input.src"
        src_file.write_bytes(source_bytes)

        print("\n[2/3] Compiling grammar to native C11 (AOT)...")
        t_export0 = time.perf_counter()
        exe_path = compile_native_c(session, temp_dir)
        t_export = time.perf_counter() - t_export0
        print(f"      Generated & compiled C11 executable in {t_export:.2f}s")

        # Measure token count using C CLI check
        tokens_info = subprocess.run([str(exe_path), "check", str(src_file)], capture_output=True, text=True)
        if tokens_info.returncode != 0:
            print(f"Error in C parsing: {tokens_info.stderr}")
            sys.exit(1)

        print("\n[3/3] Executing differential benchmarks...")

        # Warmup Python
        for _ in range(args.warmup):
            toks = session.tokenize(source_code, "bench")
            session.parse(toks, "bench")

        # Benchmark Python
        print(f"      Running Python (Lexer + Parser + AST) [{args.iterations} runs]...")
        py_times: list[float] = []
        for _ in range(args.iterations):
            t0 = time.perf_counter()
            toks = session.tokenize(source_code, "bench")
            ast = session.parse(toks, "bench")
            t1 = time.perf_counter()
            py_times.append(t1 - t0)
            del toks
            del ast

        # Warmup C
        for _ in range(args.warmup):
            subprocess.run([str(exe_path), "check", str(src_file)], check=True, capture_output=True)

        # Benchmark C
        print(f"      Running Native C11 (Opener + Lexer + Parser + AST) [{args.iterations} runs]...")
        # We run the C parser repeatedly in a batch to minimize process startup noise
        c_batch_script = temp_dir / "batch_c.c"
        c_batch_exe = temp_dir / "batch_c.exe" if os.name == "nt" else temp_dir / "batch_c"

        batch_code = f"""
#include "gram_driver.h"
#include <stdio.h>
#include <stdlib.h>
#include <windows.h>

int main(void) {{
    LARGE_INTEGER freq, t0, t1;
    QueryPerformanceFrequency(&freq);

    const int iters = {args.iterations};
    double times[{args.iterations}];

    for (int i = 0; i < iters; i++) {{
        GramParseResult r;
        GramDriverError err;
        QueryPerformanceCounter(&t0);
        GramDriverStatus st = gram_parse_file("{src_file.as_posix()}", &r, &err);
        QueryPerformanceCounter(&t1);
        if (st != GRAM_DRIVER_OK) {{
            fprintf(stderr, "Error: %s\\n", err.message);
            return 1;
        }}
        times[i] = (double)(t1.QuadPart - t0.QuadPart) / (double)freq.QuadPart;
        gram_parse_result_free(&r);
    }}

    for (int i = 0; i < iters; i++) {{
        printf("%.9f\\n", times[i]);
    }}
    return 0;
}}
"""
        c_batch_script.write_text(batch_code, encoding="utf-8")
        native_inc = PROJECT_ROOT / "native" / "gram_lexer" / "include"
        native_src = PROJECT_ROOT / "native" / "gram_lexer" / "src"
        sources = [
            "gram_ast.c", "gram_parser.c", "gram_ir.c", "gram_driver.c",
            "gram_lexer_keywords.c", "gram_lexer_symbols.c", "gram_lexer_groups.c",
        ]
        common = [str(temp_dir / name) for name in sources] + [
            str(native_src / name)
            for name in (
                "lexer.c", "indentation.c", "numbers.c", "strings.c",
                "symbols.c", "utf8.c", "diagnostics_lite.c",
            )
        ]
        gcc = shutil.which("gcc")
        subprocess.run(
            [
                gcc, "-std=c11", "-O2", "-Wall", "-Wextra",
                f"-I{native_inc}", f"-I{native_src}", f"-I{temp_dir}",
                str(c_batch_script), *common, "-o", str(c_batch_exe),
            ],
            check=True, capture_output=True, text=True,
        )

        c_proc = subprocess.run([str(c_batch_exe)], check=True, capture_output=True, text=True)
        c_times = [float(line.strip()) for line in c_proc.stdout.strip().splitlines() if line.strip()]

    # Statistics
    py_median = statistics.median(py_times)
    py_mean = statistics.mean(py_times)
    c_median = statistics.median(c_times)
    c_mean = statistics.mean(c_times)

    speedup = py_median / c_median if c_median > 0 else float("inf")
    py_throughput_mb = (byte_count / (1024 * 1024)) / py_median
    c_throughput_mb = (byte_count / (1024 * 1024)) / c_median

    print("\n" + "=" * 78)
    print("  Benchmark Results Summary")
    print("=" * 78)
    print(f"Metric                  Python Runtime         Native C11 (AOT)       Speedup")
    print("-" * 78)
    print(f"Median Time:            {py_median * 1000:10.3f} ms        {c_median * 1_000_000:10.1f} µs        {speedup:8.1f}x")
    print(f"Mean Time:              {py_mean * 1000:10.3f} ms        {c_mean * 1_000_000:10.1f} µs        {py_mean / c_mean:8.1f}x")
    print(f"Throughput:             {py_throughput_mb:10.2f} MB/s      {c_throughput_mb:10.2f} MB/s       {speedup:8.1f}x")
    print(f"Lines / Second:         {line_count / py_median:10.0f} l/s       {line_count / c_median:10.0f} l/s      {speedup:8.1f}x")
    print("=" * 78)
    print(f"\nConclusion: The native C11 AOT frontend is ~{speedup:,.0f}x faster than Python")
    print(f"on the complete end-to-end pipeline (File -> Lexer -> Parser -> AST Arena).\n")


if __name__ == "__main__":
    main()
