"""Benchmark reproducible de las utilidades de diagnóstico de Gram.

Mide emisión de notas, serialización de árboles y escritura repetida de logs.
No ejecuta el parser ni depende de datos del proyecto.
"""
from __future__ import annotations

import argparse
import statistics
import sys
import tempfile
import time
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gram.utilities import Diagnostics
from gram.utilities import Format
from gram import errors
from gram.utilities.error.codes import CodeError, Codes, set_map_codes
from gram.utilities.error.stack import StackError
from gram.utilities.info import Node, StackInfo
from gram.utilities.info.log import Log


def _samples(function, repeats: int) -> list[float]:
    """Measure one callable after a warmup call."""
    function()
    values: list[float] = []
    for _ in range(repeats):
        start = time.perf_counter()
        function()
        values.append(time.perf_counter() - start)
    return values


def _measure_emission(events: int, target: bool) -> None:
    try:
        diagnostics = Diagnostics("benchmark", "ROOT", "utility benchmark")
        if target:
            diagnostics.node("TARGET", "target benchmark", set_target=True)
        for index in range(events):
            diagnostics.debug(f"debug-{index}")
            diagnostics.warn(f"warn-{index}")
            diagnostics.advice(f"advice-{index}")
            diagnostics.error(f"error-{index}")
            diagnostics.success(f"success-{index}")
        if target:
            diagnostics.down()
    finally:
        StackInfo.clear_all()


def _emit(node: Node, method: str, message: str) -> None:
    """Use typed Node flows when available, with the legacy baseline fallback."""
    emitter = getattr(node, method, None)
    if emitter is None:
        node.note(message, method)
    else:
        emitter(message)


def _make_tree(events: int, children: int) -> Node:
    root = Node("ROOT", "utility benchmark")
    for index in range(events):
        _emit(root, "debug", f"debug-{index}")
        _emit(root, "warn", f"warn-{index}")
        _emit(root, "advice", f"advice-{index}")
        _emit(root, "error", f"error-{index}")
        _emit(root, "success", f"success-{index}")
    for index in range(children):
        child = root.node(f"CHILD-{index}", "child benchmark")
        _emit(child, "debug", f"child-debug-{index}")
        _emit(child, "warn", f"child-warn-{index}")
    return root


def _measure_stringify(events: int, children: int) -> None:
    _make_tree(events, children).stringify(expose_nodes=True, ansi=False)


def _measure_write(events: int) -> None:
    with tempfile.TemporaryDirectory(prefix="gram-utilities-benchmark-") as directory:
        previous_logfile = Log.LOGFILE
        previous_files = dict(Log._files)
        previous_file = Format.FileTar.file
        previous_rid = Format.FileTar.rid
        try:
            Log.LOGFILE = Path(directory) / "log"
            Log._files.clear()
            Format.FileTar.file = "benchmark"
            Format.FileTar.rid = 1
            stack = StackInfo(
                "utilities.log",
                "ROOT",
                "utility benchmark",
                expose_nodes=True,
                generate_log_file=True,
            )
            for index in range(events):
                stack.note(f"event-{index}")
            stack.write()
            stack.write()
        finally:
            Log.LOGFILE = previous_logfile
            Log._files.clear()
            Log._files.update(previous_files)
            Format.FileTar.file = previous_file
            Format.FileTar.rid = previous_rid


def _measure_failure_record(events: int) -> None:
    diagnostics = Diagnostics("benchmark-failures", "ROOT", "failure benchmark")

    def hook(sender: object, err: errors.Error) -> None:
        return None

    diagnostics.add_hook(hook)
    try:
        for index in range(events):
            diagnostics.record_failure(
                errors.ParserError(
                    f"Failure-{index}",
                    errors.PARSER_UNEXPECTED_TOKEN,
                    "benchmark",
                )
            )
    finally:
        StackInfo.clear_all()


def _measure_code_validation(events: int) -> None:
    set_map_codes(
        origin=[2],
        scope=[5],
        gravity=[4],
        documentation=[2],
        condition=[2],
    )
    symbols = (
        Codes("origin", 1, "origin"),
        Codes("scope", 2, "scope"),
        Codes("gravity", 1, "gravity"),
        Codes("documentation", 1, "documentation"),
        Codes("condition", 1, "condition"),
    )
    code = CodeError(symbols, "Benchmark")
    for _ in range(events):
        code.safe
        code.stringify()


def _measure_error_stack_write(events: int) -> None:
    previous_logfile = StackError.LOGFILE
    StackError.clear()
    try:
        with tempfile.TemporaryDirectory(prefix="gram-error-stack-benchmark-") as directory:
            StackError.LOGFILE = Path(directory) / "error.log"
            for index in range(events):
                StackError.add(
                    errors.ParserError(
                        f"Stack-{index}",
                        errors.PARSER_UNEXPECTED_TOKEN,
                        "benchmark",
                    )
                )
            StackError.write()
    finally:
        StackError.LOGFILE = previous_logfile
        StackError.clear()


def _measure_error_stack_index(events: int) -> None:
    StackError.clear()
    try:
        entries = [
            errors.ParserError(
                f"Index-{index}",
                errors.PARSER_UNEXPECTED_TOKEN,
                "benchmark",
            )
            for index in range(events)
        ]
        for error in entries:
            StackError.add(error)
        for error in entries:
            error.get_index()
    finally:
        StackError.clear()


def _report(name: str, values: list[float]) -> None:
    print(
        f"{name:<24} median={statistics.median(values):.6f}s "
        f"min={min(values):.6f}s max={max(values):.6f}s"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", nargs="+", type=int, default=[32, 256, 1024])
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()
    if args.repeats < 1 or any(value < 1 for value in args.events):
        parser.error("--repeats y --events deben ser mayores que cero")

    print(f"repeats={args.repeats}")
    for events in args.events:
        print(f"events={events}")
        _report(
            "emit-main",
            _samples(lambda: _measure_emission(events, target=False), args.repeats),
        )
        _report(
            "emit-target",
            _samples(lambda: _measure_emission(events, target=True), args.repeats),
        )
        _report(
            "stringify-tree",
            _samples(lambda: _measure_stringify(events, events // 4), args.repeats),
        )
        _report(
            "write-log",
            _samples(lambda: _measure_write(events), args.repeats),
        )
        _report(
            "record-failure",
            _samples(lambda: _measure_failure_record(events), args.repeats),
        )
        _report(
            "code-validation",
            _samples(lambda: _measure_code_validation(events), args.repeats),
        )
        _report(
            "error-stack-write",
            _samples(lambda: _measure_error_stack_write(events), args.repeats),
        )
        _report(
            "error-stack-index",
            _samples(lambda: _measure_error_stack_index(events), args.repeats),
        )


if __name__ == "__main__":
    main()
