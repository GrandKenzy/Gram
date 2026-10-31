"""
High-Throughput Lexer Scaling and Stress Benchmark for Gram.
============================================================
Measures raw tokenization throughput, visitor dispatch overhead,
indentation tracking cost, and telemetry scaling across varied synthetic corpora.
"""
from __future__ import annotations

import argparse
import random
import statistics
import sys
import time
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gram import config
from gram.core.lexer import Lexer, words


def _setup_keywords() -> None:
    words.clear_all()
    for kw in (
        "fn", "let", "mut", "if", "else", "while", "for", "in",
        "return", "break", "continue", "struct", "enum", "impl",
        "type", "const", "import", "as", "pub", "async", "await",
    ):
        words.add_keyword(kw, allow_override=True)


def generate_corpus(scenario: str, line_count: int, seed: int = 42) -> str:
    """Generate a reproducible corpus of source lines tailored to a scenario."""
    rng = random.Random(seed)
    lines: list[str] = []

    if scenario == "numbers":
        num_templates = [
            "{i}",
            "{i}_{i}",
            "0x{i:x}",
            "0x{i:x}ULL",
            "0b{b}",
            "0o{o}",
            "{i}.{i:02d}",
            "{i}.{i:02d}f",
            "0x1.{i:x}p{p}",
            "1.{i:02d}e-{e}",
            ".{i:02d}",
        ]
        for idx in range(line_count):
            b_val = bin(idx % 256)[2:]
            o_val = oct(idx % 512)[2:]
            tpl = num_templates[idx % len(num_templates)]
            lit = tpl.format(i=idx + 1, b=b_val, o=o_val, p=(idx % 8) + 1, e=(idx % 6) + 1)
            lines.append(f"val_{idx} = {lit} + {lit};")

    elif scenario == "strings":
        for idx in range(line_count):
            if idx % 5 == 0:
                lines.append(f'"""docstring line 1 {idx}\nline 2 with \\t and \\n\nline 3"""')
            elif idx % 5 == 1:
                lines.append(f'L"prefixed wide string {idx} with \\u0041 unicode"')
            elif idx % 5 == 2:
                lines.append(f'u8"utf-8 string literal {idx}"')
            else:
                lines.append(f'name_{idx} = "standard string {idx} with \\"escaped quotes\\"";')

    elif scenario == "operators":
        ops = ["+", "-", "*", "/", "%", "**=", "//=", ":=", "->", "=>", "==", "!=", "<=", ">=", "&&", "||", "..."]
        for idx in range(line_count):
            row_ops = " ".join(ops[i % len(ops)] for i in range(idx, idx + 8))
            lines.append(f"x_{idx} {row_ops} y_{idx};")

    elif scenario == "keywords":
        kw_list = ["fn", "let", "mut", "if", "else", "while", "return", "true", "false", "null"]
        for idx in range(line_count):
            kws = " ".join(kw_list[i % len(kw_list)] for i in range(idx, idx + 6))
            lines.append(f"{kws} id_{idx};")

    elif scenario == "indentation":
        current_depth = 0
        for idx in range(line_count):
            if idx % 8 == 0 and current_depth > 0:
                current_depth -= 1
            elif idx % 3 == 0 and current_depth < 12:
                current_depth += 1
            indent = "    " * current_depth
            lines.append(f"{indent}let item_{idx} = {idx};")

    else:  # "mixed" realistic language profile
        for idx in range(line_count):
            tier = idx % 6
            if tier == 0:
                lines.append(f"fn process_item_{idx}(input: int) -> int // header")
            elif tier == 1:
                lines.append(f'    let description = "item #{idx} ready";')
            elif tier == 2:
                lines.append(f"    let value = 0x{idx:x}ULL + 10.5e-2f;")
            elif tier == 3:
                lines.append(f"    if value >= 100 && input != 0 /* check */ :=")
            elif tier == 4:
                lines.append(f"        return value * 2;")
            else:
                lines.append(f"    return null;")

    return "\n".join(lines)


def benchmark_run(
    source: str,
    repeats: int,
    telemetry: bool,
) -> tuple[list[float], int]:
    """Execute tokenization across repeats and return timing list and token count."""
    config.LEXER_ADD_INFO = telemetry
    config.INFO_GENERATE_LOGFILE = False
    config.ERROR_EXIT_ON_ERROR = False
    config.ERROR_HIDE_CONSOLE = True
    config.LEXER_SAVE_COMMENTS = True

    samples: list[float] = []
    token_count = 0

    for _ in range(repeats):
        lexer = Lexer(source)
        start = time.perf_counter()
        tokens = lexer.process()
        elapsed = time.perf_counter() - start
        token_count = len(tokens)
        samples.append(elapsed)

    return samples, token_count


def run_benchmarks(
    scenarios: list[str],
    line_counts: list[int],
    repeats: int,
    telemetry_modes: list[bool],
) -> None:
    _setup_keywords()

    print("\n" + "=" * 92)
    print("  GRAM FRAMEWORK LEXER SCALING BENCHMARK (Python 3.12+ pure)")
    print("=" * 92)

    for scenario in scenarios:
        print(f"\n[ SCENARIO: {scenario.upper()} ]")
        print("-" * 92)
        print(f"{'Lines':>8} | {'Tokens':>10} | {'Bytes (KB)':>10} | {'Telemetry':>9} | {'Median (ms)':>11} | {'Tokens/sec':>13} | {'MB/sec':>8}")
        print("-" * 92)

        for lines in line_counts:
            source = generate_corpus(scenario, lines)
            bytes_kb = len(source.encode("utf-8")) / 1024.0

            for telem in telemetry_modes:
                telem_str = "ON" if telem else "OFF"
                samples, total_tokens = benchmark_run(source, repeats, telem)
                median_time = statistics.median(samples)
                tokens_per_sec = total_tokens / median_time if median_time > 0 else 0
                mb_per_sec = (bytes_kb / 1024.0) / median_time if median_time > 0 else 0

                print(
                    f"{lines:8d} | "
                    f"{total_tokens:10d} | "
                    f"{bytes_kb:10.1f} | "
                    f"{telem_str:>9} | "
                    f"{median_time * 1000:11.2f} | "
                    f"{int(tokens_per_sec):13,d} | "
                    f"{mb_per_sec:8.2f}"
                )
        print("-" * 92)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--lines",
        nargs="+",
        type=int,
        default=[100, 1000, 5000],
        help="Line counts to evaluate (default: 100 1000 5000)",
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=5,
        help="Number of iterations per measurement (default: 5)",
    )
    parser.add_argument(
        "--scenario",
        choices=["all", "mixed", "numbers", "strings", "operators", "keywords", "indentation"],
        default="mixed",
        help="Corpus profile to benchmark (default: mixed)",
    )
    parser.add_argument(
        "--telemetry",
        choices=["off", "on", "both"],
        default="both",
        help="Telemetry mode to benchmark (default: both)",
    )

    args = parser.parse_args()

    scenarios = (
        ["mixed", "numbers", "strings", "operators", "keywords", "indentation"]
        if args.scenario == "all"
        else [args.scenario]
    )

    telem_modes = (
        [False, True]
        if args.telemetry == "both"
        else [True] if args.telemetry == "on" else [False]
    )

    run_benchmarks(scenarios, args.lines, args.repeats, telem_modes)


if __name__ == "__main__":
    main()
