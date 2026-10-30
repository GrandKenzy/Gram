"""Focused regression tests for the standalone utilities refactor."""
from __future__ import annotations

from pathlib import Path
import inspect
import tempfile
import unittest

from gram import errors
from gram.utilities import Diagnostics, ErrorAction, Format
from gram.utilities.error.codes import CodeError, Codes, set_map_codes
from gram.utilities.error.stack import StackError
from gram.utilities.info import Node, StackInfo
from gram.utilities.info.log import Log


class TestUtilitiesRefactor(unittest.TestCase):
    def setUp(self) -> None:
        StackInfo.clear_and_clean_all()
        self.logfile = Log.LOGFILE
        self.files = dict(Log._files)
        self.source_file = Format.FileTar.file
        self.source_rid = Format.FileTar.rid
        self.code_groups = {
            name: dict(group) for name, group in Codes.GROUPS.items()
        }
        self.code_limits = {
            name: set(values) for name, values in Codes.MAP_LIMITS.items()
        }
        self.code_default = Codes.DEFAULT
        self.error_entries = list(StackError.__err__)
        self.error_indexes = dict(StackError._index_by_identity)

    def tearDown(self) -> None:
        StackInfo.clear_and_clean_all()
        Log.LOGFILE = self.logfile
        Log._files.clear()
        Log._files.update(self.files)
        Format.FileTar.file = self.source_file
        Format.FileTar.rid = self.source_rid
        Codes.GROUPS.clear()
        Codes.GROUPS.update(
            {name: dict(group) for name, group in self.code_groups.items()}
        )
        Codes.MAP_LIMITS.clear()
        Codes.MAP_LIMITS.update(
            {name: set(values) for name, values in self.code_limits.items()}
        )
        Codes.DEFAULT = self.code_default
        StackError.__err__.clear()
        StackError.__err__.extend(self.error_entries)
        StackError._index_by_identity.clear()
        StackError._index_by_identity.update(self.error_indexes)

    def test_node_exposes_all_typed_flows(self) -> None:
        node = Node("ROOT", "test")
        for method in ("debug", "warn", "advice", "error", "fatal"):
            getattr(node, method)(method)

        self.assertEqual(
            [note.type for note in node.notes],
            ["normal", "warn", "advice", "error", "fatal"],
        )

    def test_stack_registry_and_targets_are_owned_by_stack_info(self) -> None:
        stack = StackInfo("test", "ROOT", "test", expose_nodes=True)
        target = stack.node("TARGET", "target", set_target=True)
        stack.warn("warning")
        stack.down()

        self.assertIn(stack, StackInfo._stacks)
        self.assertIs(stack.target, None)
        self.assertIn(target, stack.main.nodes)
        self.assertIn("warning", stack.stringify())

    def test_register_preserves_unrelated_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            Log.LOGFILE = Path(directory) / "log"
            sibling = Log.LOGFILE / "keep.log"
            sibling.parent.mkdir(parents=True)
            sibling.write_text("keep", encoding="utf-8")

            Log.register("new.log")

            self.assertEqual(sibling.read_text(encoding="utf-8"), "keep")

    def test_repeated_stack_writes_replace_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            Log.LOGFILE = Path(directory) / "log"
            stack = StackInfo(
                "test",
                "ROOT",
                "test",
                generate_log_file=True,
            )
            stack.debug("once")
            stack.write()
            stack.write()

            content = stack.log.read_text(encoding="utf-8")
            self.assertEqual(content.count("once"), 1)

    def test_staged_failure_dispatches_hooks_once(self) -> None:
        diagnostics = Diagnostics("test", "ROOT", "test")
        error = errors.ParserError(
            "TokenMismatch",
            errors.PARSER_UNEXPECTED_TOKEN,
            "expected token",
        )
        calls: list[object] = []

        def hook(sender: object, err: errors.Error) -> str:
            calls.append(err)
            return ErrorAction.SUPPRESS_RAISE

        diagnostics.add_hook(hook)
        diagnostics.stage_failure(error)
        diagnostics.fail()

        self.assertEqual(calls, [error])
        self.assertEqual(diagnostics._errors, [error])

    def test_error_keeps_the_source_file_seen_at_creation(self) -> None:
        previous = Format.FileTar.file
        try:
            Format.FileTar.file = "source-a.gram"
            error = errors.ParserError(
                "TokenMismatch",
                errors.PARSER_UNEXPECTED_TOKEN,
                "expected token",
            )
            Format.FileTar.file = "source-b.gram"

            self.assertIn("source-a.gram", error.stringify())
            self.assertNotIn("source-b.gram", error.stringify())
        finally:
            Format.FileTar.file = previous

    def test_diagnostics_signature_and_target_view_remain_compatible(self) -> None:
        class ExternalDiagnostics(Diagnostics):
            def __init__(self) -> None:
                super().__init__("external", "ROOT", "external")
                self.external_state = object()

        parameters = tuple(inspect.signature(Diagnostics.__init__).parameters)
        self.assertEqual(
            parameters,
            (
                "self",
                "file",
                "name",
                "description",
                "expose_nodes",
                "generate_log_file",
                "generate_on_error",
            ),
        )

        diagnostics = ExternalDiagnostics()
        target = diagnostics.node("TARGET", set_target=True)
        target_view = diagnostics._targets
        self.assertIs(target_view, diagnostics.stack.targets)

        diagnostics._targets = [target]
        self.assertIs(diagnostics._targets, target_view)
        self.assertEqual(diagnostics.current(), target)

    def test_hooks_keep_global_then_local_order_and_deduplicate(self) -> None:
        diagnostics = Diagnostics("hooks", "ROOT", "hooks")
        error = errors.ParserError(
            "TokenMismatch",
            errors.PARSER_UNEXPECTED_TOKEN,
            "expected token",
        )
        calls: list[str] = []

        def global_hook(sender: object, err: errors.Error) -> None:
            calls.append("global")

        def local_hook(sender: object, err: errors.Error) -> None:
            calls.append("local")

        diagnostics.add_hook(local_hook)
        with Diagnostics.hook_errors(global_hook):
            diagnostics.record_failure(error)
            diagnostics.record_failure(error)

        self.assertEqual(calls, ["global", "local"])
        self.assertEqual(diagnostics._errors, [error])

    def test_code_map_failure_is_atomic_and_code_error_keeps_first_group_code(self) -> None:
        set_map_codes(first=[9], second=["B"])
        old_groups = {name: dict(group) for name, group in Codes.GROUPS.items()}
        old_limits = {name: set(values) for name, values in Codes.MAP_LIMITS.items()}
        groups_identity = Codes.GROUPS
        limits_identity = Codes.MAP_LIMITS

        with self.assertRaises(ValueError):
            set_map_codes(first=[3], second=["?"])

        self.assertIs(Codes.GROUPS, groups_identity)
        self.assertIs(Codes.MAP_LIMITS, limits_identity)
        self.assertEqual(Codes.GROUPS, old_groups)
        self.assertEqual(Codes.MAP_LIMITS, old_limits)

        first = Codes("first", 3, "first")
        duplicate = Codes("duplicate", 4, "first")
        second = Codes("second", "B", "second")
        code = CodeError((first, duplicate, second), "Example")

        self.assertEqual(code.code_string, "3B")
        self.assertTrue(code.safe)
        self.assertEqual(code.type, "S")

    def test_stack_error_deduplicates_identity_and_repairs_direct_list_edits(self) -> None:
        first = errors.ParserError(
            "First",
            errors.PARSER_UNEXPECTED_TOKEN,
            "first",
        )
        second = errors.ParserError(
            "Second",
            errors.PARSER_UNEXPECTED_TOKEN,
            "second",
        )
        third = errors.ParserError(
            "Third",
            errors.PARSER_UNEXPECTED_TOKEN,
            "third",
        )

        StackError.add(first)
        StackError.add(first)
        StackError.add(second)
        StackError.__err__.append(third)

        self.assertEqual(StackError.count(), 3)
        self.assertEqual(first.get_index(), 0)
        self.assertEqual(second.get_index(), 1)
        self.assertEqual(third.get_index(), 2)
        self.assertEqual(StackError.all(), [first, second, third])

    def test_stack_error_writes_one_snapshot_in_order(self) -> None:
        first = errors.ParserError(
            "First",
            errors.PARSER_UNEXPECTED_TOKEN,
            "first",
        )
        second = errors.ParserError(
            "Second",
            errors.PARSER_UNEXPECTED_TOKEN,
            "second",
        )
        StackError.add(first)
        StackError.add(second)

        with tempfile.TemporaryDirectory() as directory:
            previous = StackError.LOGFILE
            try:
                StackError.LOGFILE = Path(directory) / "errors.log"
                StackError.write()
                content = StackError.LOGFILE.read_text(encoding="utf-8")
            finally:
                StackError.LOGFILE = previous

        self.assertLess(content.index("First"), content.index("Second"))
        self.assertIn("ERROR 0", content)
        self.assertIn("ERROR 1", content)


if __name__ == "__main__":
    unittest.main()
