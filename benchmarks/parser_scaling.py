"""Small generic parser-scaling benchmark for Gram.

This intentionally uses a tiny declaration grammar so results describe Gram's
lexer/parser overhead rather than any language built on top of it.
"""
from __future__ import annotations

import argparse
import statistics
import sys
import time
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gram import lexer
from gram.core.combinators import Alt, MatchKeyword, MatchToken, Ref, RuleItem, Seq
from gram.core.lexer.tokens import Token
from gram.core.parser import Parser


class Declaration(RuleItem):
    entrypoint = Seq(
        MatchKeyword("let"),
        MatchToken(Token.IDENT),
        MatchToken(Token.ASSIGN),
        MatchToken(Token.NUMBER),
        MatchToken(Token.SEMICOLON),
    )


class Program(RuleItem):
    entrypoint = Alt(Ref(Declaration))


def build_source(count: int) -> str:
    return "\n".join(f"let value_{index} = {index};" for index in range(count))


def measure(count: int, trace: str, repeats: int) -> list[float]:
    lexer.clear_all()
    lexer.add_keyword("let")
    tokens = lexer.Lexer(build_source(count)).process()
    samples: list[float] = []
    for _ in range(repeats):
        parser = Parser(list(tokens))
        start = time.perf_counter()
        result = parser.parse(Program, trace=trace)
        elapsed = time.perf_counter() - start
        if result is None or len(result) != count:
            raise RuntimeError(f"unexpected parse result for count={count}")
        samples.append(elapsed)
    return samples


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", nargs="+", type=int, default=[32, 256, 1000])
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument(
        "--trace", choices=("off", "basic", "detailed"), default="basic"
    )
    args = parser.parse_args()

    print(f"trace={args.trace}, repeats={args.repeats}")
    for count in args.count:
        samples = measure(count, args.trace, args.repeats)
        print(
            f"count={count:>5} median={statistics.median(samples):.6f}s "
            f"min={min(samples):.6f}s max={max(samples):.6f}s"
        )


if __name__ == "__main__":
    main()
