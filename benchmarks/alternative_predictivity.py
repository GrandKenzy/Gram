"""Benchmark ordered alternatives and the optional predictive audit plan.

The benchmark is intentionally compatible with both sides of the ``audit``
change. Before the feature exists, the declared-order measurement still runs
and the audited measurement is reported as unavailable. After implementation,
the same command measures both paths and checks that the public ``Alt`` shape
remains observable.
"""
from __future__ import annotations

import argparse
import inspect
import statistics
import sys
import time
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gram import config, lexer
from gram.core.combinators import Alt, MatchKeyword, MatchToken, Ref, RuleItem, Seq
from gram.core.lexer.tokens import Token
from gram.core.parser import Parser


def _supports_audit() -> bool:
    """Return whether the installed ``Alt`` accepts the additive audit option."""
    return "audit" in inspect.signature(Alt).parameters


def _check_public_api() -> None:
    """Check the observable legacy ``Alt`` collection and constructor contract."""
    first = MatchKeyword("api-first")
    second = MatchKeyword("api-second")
    alternative = Alt(first, second, ignore=True)
    if alternative.combinators != (first, second):
        raise AssertionError("Alt.combinators no longer preserves declared order")
    if alternative.items() != (first, second):
        raise AssertionError("Alt.items() no longer preserves declared order")
    if tuple(alternative) != (first, second) or len(alternative) != 2:
        raise AssertionError("Alt iteration/length contract changed")
    if alternative.ignore is not True:
        raise AssertionError("Alt(ignore=True) contract changed")


def _make_program(branches: int, audited: bool) -> type[RuleItem]:
    """Build an entrypoint with fixed, increasingly long alternatives."""
    rules: list[type[RuleItem]] = []
    for index in range(branches):
        items = [MatchKeyword(f"kind{index}")]
        items.extend(MatchToken(Token.IDENT) for _ in range(index + 1))
        items.append(MatchToken(Token.SEMICOLON))
        rules.append(
            type(
                f"PredictiveRule{index}",
                (RuleItem,),
                {"__module__": __name__, "entrypoint": Seq(*items)},
            )
        )

    options = {"audit": True} if audited and _supports_audit() else {}
    entrypoint = Alt(*(Ref(rule) for rule in rules), **options)
    return type(
        "PredictiveProgram",
        (RuleItem,),
        {"__module__": __name__, "entrypoint": entrypoint},
    )


def _build_source(branches: int, statements: int, target: int | None = None) -> str:
    """Build statements for a declared branch, defaulting to the last one."""
    target = branches - 1 if target is None else target
    return "\n".join(
        f"kind{target} "
        + " ".join(f"value_{line}_{index}" for index in range(target + 1))
        + ";"
        for line in range(statements)
    )


def _measure(
    branches: int,
    statements: int,
    repeats: int,
    trace: str,
    audited: bool,
    target: int | None = None,
) -> list[float]:
    """Measure parser execution after one warm-up run."""
    lexer.clear_all()
    for index in range(branches):
        lexer.add_keyword(f"kind{index}")
    tokens = lexer.Lexer(_build_source(branches, statements, target)).process()
    program = _make_program(branches, audited)

    def run() -> None:
        parser = Parser(list(tokens))
        result = parser.parse(program, trace=trace)
        if result is None or len(result) != statements:
            raise RuntimeError(
                f"unexpected parse result: expected {statements}, got "
                f"{None if result is None else len(result)}"
            )

    run()
    samples: list[float] = []
    for _ in range(repeats):
        started = time.perf_counter()
        run()
        samples.append(time.perf_counter() - started)
    return samples


def _report(label: str, samples: list[float]) -> None:
    print(
        f"{label:<18} median={statistics.median(samples):.6f}s "
        f"min={min(samples):.6f}s max={max(samples):.6f}s"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--branches", type=int, default=16)
    parser.add_argument("--statements", type=int, default=128)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument(
        "--trace", choices=("off", "basic", "detailed"), default="off"
    )
    parser.add_argument(
        "--target",
        type=int,
        default=None,
        help="Índice de la rama declarada que se ejecuta (por defecto, la última).",
    )
    args = parser.parse_args()
    if args.branches < 2 or args.statements < 1 or args.repeats < 1:
        parser.error("--branches debe ser >= 2; los demás valores deben ser > 0")
    if args.target is not None and not 0 <= args.target < args.branches:
        parser.error("--target debe estar entre 0 y branches - 1")

    config.ERROR_EXIT_ON_ERROR = False
    config.ERROR_HIDE_CONSOLE = True
    audit_supported = _supports_audit()
    signature = inspect.signature(Alt)
    _check_public_api()
    print(f"Alt signature: {signature}")
    print(
        f"legacy_api=ok, audit_supported={audit_supported}, "
        f"trace={args.trace}, repeats={args.repeats}"
    )
    print(
        f"branches={args.branches}, statements={args.statements}, "
        f"input=declared_branch_{args.branches - 1 if args.target is None else args.target}"
    )

    declared = _measure(
        args.branches,
        args.statements,
        args.repeats,
        args.trace,
        audited=False,
        target=args.target,
    )
    _report("declared-order", declared)

    if audit_supported:
        audited = _measure(
            args.branches,
            args.statements,
            args.repeats,
            args.trace,
            audited=True,
            target=args.target,
        )
        _report("audit=True", audited)
    else:
        print("audit=True        unavailable (baseline before feature)")

    lexer.clear_all()


if __name__ == "__main__":
    main()
