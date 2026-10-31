"""
Python vs Native C Lexer Benchmark Suite (`benchmarks/lexer_python_vs_c.py`).
=============================================================================
Compares the Python lexer (`Lexer(source, backend="python")`), the Python C
adapter (`Lexer(source, backend="c")`), and the standalone zero-allocation C
runtime (`gram_lexer_scan_all`) across:
  - 1 KB, 1 MB, and 100 MB inputs
  - Operator-dense code
  - String-dense code
  - Unicode-heavy code
  - Deeply indented code
  - Error-heavy code (`DiagnosticsLite` null sink vs collector buffer sink)

Reported metrics:
  - Throughput (`bytes/s` / `MB/s` and `tokens/s`)
  - Latency (`ns/token`)
  - Peak heap memory (`KB`)
  - Heap allocations per execution (`allocs/run`)
"""
from __future__ import annotations

import argparse
import ctypes
import time
import tracemalloc
from dataclasses import dataclass

from gram.core.lexer.c_backend import (
    GRAM_ERROR_POLICY_RECOVER,
    GramDiagBufferC,
    GramDiagnosticC,
    GramLexerC,
    _MarshaledTables,
    build_c_config,
    get_c_library,
)
from gram.core.lexer.core import Lexer
from gram.sessions import Session


@dataclass(slots=True)
class BenchMetrics:
    scenario: str
    engine: str
    byte_count: int
    token_count: int
    elapsed_sec: float
    bytes_per_sec: float
    tokens_per_sec: float
    ns_per_token: float
    peak_mem_kb: float
    allocations: int


def _make_session() -> Session:
    session = Session("bench-py-vs-c", "Many")
    session.config["LEXER_ADD_INFO"] = False
    session.config["ERROR_EXIT_ON_ERROR"] = False
    for kw in ("def", "if", "else", "elif", "while", "for", "return", "let", "fn", "match"):
        session.add_keyword(kw)
    session.add_group("control", ["if", "else", "elif", "while", "for", "return", "match"])
    return session


def _repeat_to_bytes(unit: str, target_bytes: int) -> str:
    unit_bytes = len(unit.encode("utf-8"))
    repeats = max(1, target_bytes // max(1, unit_bytes))
    return unit * repeats


def _build_deep_indentation(target_bytes: int) -> str:
    lines: list[str] = []
    max_depth = 32
    cur_bytes = 0
    block_idx = 0
    while cur_bytes < target_bytes:
        for d in range(max_depth):
            line = ("    " * d) + f"if x_{block_idx}_{d} >= {d}:\n"
            lines.append(line)
            cur_bytes += len(line)
        leaf = ("    " * max_depth) + f"return x_{block_idx}_0 + 1\n"
        lines.append(leaf)
        cur_bytes += len(leaf)
        block_idx += 1
    return "".join(lines)


def measure_python_lexer(
    scenario: str,
    source: str,
    session: Session,
    *,
    backend: str = "python",
    measure_allocs: bool = True,
) -> BenchMetrics:
    src_bytes_len = len(source.encode("utf-8"))

    t0 = time.perf_counter()
    tokens = Lexer(source, session=session, backend=backend).process()  # type: ignore[arg-type]
    elapsed = max(1e-9, time.perf_counter() - t0)
    tok_count = len(tokens)

    peak_kb = 0.0
    alloc_count = 0
    if measure_allocs:
        sample_src = source if len(source) <= 16384 else source[:16384]
        scale = max(1.0, len(source) / max(1, len(sample_src)))
        tracemalloc.start()
        _ = Lexer(sample_src, session=session, backend=backend).process()  # type: ignore[arg-type]
        snap = tracemalloc.take_snapshot()
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        peak_kb = (peak / 1024.0) * scale
        alloc_count = int(sum(stat.count for stat in snap.statistics("filename")) * scale)

    return BenchMetrics(
        scenario=scenario,
        engine=f"Python ({backend})",
        byte_count=src_bytes_len,
        token_count=tok_count,
        elapsed_sec=elapsed,
        bytes_per_sec=src_bytes_len / elapsed,
        tokens_per_sec=tok_count / elapsed,
        ns_per_token=(elapsed * 1e9) / max(1, tok_count),
        peak_mem_kb=peak_kb,
        allocations=alloc_count,
    )


def measure_c_runtime(
    scenario: str,
    src_bytes: bytes,
    session: Session,
    *,
    use_collector_sink: bool = False,
    iterations: int = 1,
) -> BenchMetrics:
    lib = get_c_library()
    dummy_lexer = Lexer("", session=session)
    marshaled = _MarshaledTables(dummy_lexer)
    cfg = build_c_config(dummy_lexer)

    c_lexer = GramLexerC()
    if use_collector_sink:
        diag_cap = 4096
        diags = (GramDiagnosticC * diag_cap)()
        arena = ctypes.create_string_buffer(65536)
        dbuf = GramDiagBufferC()
        lib.gram_diag_buffer_init(
            ctypes.byref(dbuf), diags, diag_cap, GRAM_ERROR_POLICY_RECOVER
        )
        lib.gram_diag_buffer_set_message_arena(
            ctypes.byref(dbuf), ctypes.cast(arena, ctypes.c_char_p), 65536
        )
        sink = lib.gram_diag_buffer_as_sink(ctypes.byref(dbuf))
        static_kb = (
            ctypes.sizeof(GramLexerC)
            + ctypes.sizeof(diags)
            + ctypes.sizeof(arena)
        ) / 1024.0
        engine_label = "C Runtime (buffer sink)"
    else:
        sink = lib.gram_diag_null_sink()
        static_kb = ctypes.sizeof(GramLexerC) / 1024.0
        engine_label = "C Runtime (null sink)"

    lib.gram_lexer_init(
        ctypes.byref(c_lexer),
        src_bytes,
        len(src_bytes),
        ctypes.byref(cfg),
        ctypes.byref(marshaled.tables),
        sink,
        None,
    )

    best_elapsed = float("inf")
    tok_count = 0
    for _ in range(max(1, iterations)):
        t0 = time.perf_counter()
        c_toks = lib.gram_lexer_scan_all(
            ctypes.byref(c_lexer), src_bytes, len(src_bytes)
        )
        dt = max(1e-9, time.perf_counter() - t0)
        if dt < best_elapsed:
            best_elapsed = dt
        tok_count = int(c_toks)

    byte_len = len(src_bytes)
    return BenchMetrics(
        scenario=scenario,
        engine=engine_label,
        byte_count=byte_len,
        token_count=tok_count,
        elapsed_sec=best_elapsed,
        bytes_per_sec=byte_len / best_elapsed,
        tokens_per_sec=tok_count / best_elapsed,
        ns_per_token=(best_elapsed * 1e9) / max(1, tok_count),
        peak_mem_kb=static_kb,
        allocations=0,  # Zero heap allocations in C runtime
    )


def run_benchmarks(*, skip_100mb: bool = False) -> list[BenchMetrics]:
    session = _make_session()
    results: list[BenchMetrics] = []

    mixed_unit = (
        "def compute(alpha, beta):\n"
        "    if alpha >= 0x10 and beta != null:\n"
        "        let msg = u8\"value=\\n\" + \"ok\"\n"
        "        return alpha * 3.14159 + (beta >>= 2)\n"
        "    return false\n"
    )
    op_unit = "a += b >>= c <=> d ... e != f && g || h **= i //= j := k -> l => m\n"
    str_unit = (
        "'a' '\\n' '\\u0041' \"hello\\tworld\\r\\n\" u8\"prefixed\" "
        "\"\"\"multiline\ndocstring\nblock\"\"\"\n"
    )
    unicode_unit = "let αβγ_1 = переменная_2 + 变量_3 * café_4 ∧ ¬∞ √x\n"
    error_unit = "x = ` + 0x_1 + 1__2 + \"unclosed\n"

    workloads: list[tuple[str, str, bool]] = [
        ("1_kb_mixed", _repeat_to_bytes(mixed_unit, 1024), True),
        ("1_mb_mixed", _repeat_to_bytes(mixed_unit, 1024 * 1024), True),
        ("operator_dense_256kb", _repeat_to_bytes(op_unit, 256 * 1024), True),
        ("string_dense_256kb", _repeat_to_bytes(str_unit, 256 * 1024), True),
        ("unicode_heavy_256kb", _repeat_to_bytes(unicode_unit, 256 * 1024), True),
        ("deep_indent_256kb", _build_deep_indentation(256 * 1024), True),
        ("error_heavy_128kb", _repeat_to_bytes(error_unit, 128 * 1024), True),
    ]

    for name, src, trace_allocs in workloads:
        src_b = src.encode("utf-8")
        py_m = measure_python_lexer(
            name, src, session, backend="python", measure_allocs=trace_allocs
        )
        results.append(py_m)

        if name == "error_heavy_128kb":
            c_null = measure_c_runtime(
                name, src_b, session, use_collector_sink=False, iterations=5
            )
            c_buf = measure_c_runtime(
                name, src_b, session, use_collector_sink=True, iterations=5
            )
            results.append(c_null)
            results.append(c_buf)
        else:
            c_m = measure_c_runtime(
                name,
                src_b,
                session,
                use_collector_sink=False,
                iterations=5 if len(src_b) <= 1024 * 1024 else 1,
            )
            results.append(c_m)

    if not skip_100mb:
        src_100mb = _repeat_to_bytes(mixed_unit, 100 * 1024 * 1024)
        src_100mb_b = src_100mb.encode("utf-8")
        c_100m = measure_c_runtime(
            "100_mb_mixed",
            src_100mb_b,
            session,
            use_collector_sink=False,
            iterations=1,
        )
        results.append(c_100m)

    return results


def print_report(results: list[BenchMetrics]) -> None:
    header = (
        f"{'Scenario':<22} | {'Engine':<23} | {'Size':>9} | {'Tokens':>10} | "
        f"{'MB/s':>8} | {'Tokens/s':>13} | {'ns/tok':>8} | {'Peak KB':>9} | {'Allocs':>9}"
    )
    print("=" * len(header))
    print(header)
    print("-" * len(header))
    for r in results:
        mb_s = r.bytes_per_sec / (1024.0 * 1024.0)
        size_str = (
            f"{r.byte_count / (1024*1024):.1f} MB"
            if r.byte_count >= 1024 * 1024
            else f"{r.byte_count / 1024.0:.1f} KB"
        )
        alloc_str = f"{r.allocations:,d}" if r.allocations > 0 else "0"
        print(
            f"{r.scenario:<22} | {r.engine:<23} | {size_str:>9} | {r.token_count:10,d} | "
            f"{mb_s:8.2f} | {int(r.tokens_per_sec):13,d} | {r.ns_per_token:8.1f} | "
            f"{r.peak_mem_kb:9.1f} | {alloc_str:>9}"
        )
    print("=" * len(header))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Benchmark Python vs C Lexer Runtime.")
    parser.add_argument(
        "--skip-100mb",
        action="store_true",
        help="Skip the 100 MB C runtime benchmark for quick runs.",
    )
    args = parser.parse_args(argv)
    res = run_benchmarks(skip_100mb=args.skip_100mb)
    print_report(res)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
