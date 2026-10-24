"""Regression tests for parser error hooks and the exit policy."""
from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from gram import config, errors
from gram.core.parser.control import ParseState
from gram.utilities import Diagnostics, ErrorAction


class TestParserDiagnosticHooks(unittest.TestCase):
    def setUp(self) -> None:
        settings = patch.multiple(
            config,
            ERROR_EXIT_ON_ERROR=True,
            ERROR_HIDE_CONSOLE=True,
            INFO_GENERATE_LOGFILE=False,
            INFO_GENERATE_LOGFILE_ON_ERROR=False,
        )
        settings.start()
        self.addCleanup(settings.stop)
        self.parser = ParseState()
        self.error = errors.ParserError(
            'UnexpectedToken',
            errors.PARSER_UNEXPECTED_TOKEN,
            'Expected an identifier.',
        )

    def test_omit_skips_storage_and_exit(self) -> None:
        hook = Mock(return_value=ErrorAction.OMIT)
        with (
            Diagnostics.hook_errors(hook),
            patch.object(self.error, 'raise_error') as raise_error,
        ):
            result = self.parser.report_error(self.error)

        self.assertIs(result, self.error)
        self.assertEqual(self.parser._errors, [])
        hook.assert_called_once_with(self.parser, self.error)
        raise_error.assert_not_called()

    def test_suppress_raise_stores_without_exiting(self) -> None:
        hook = Mock(return_value=ErrorAction.SUPPRESS_RAISE)
        self.parser.add_hook(hook)
        with patch.object(self.error, 'raise_error') as raise_error:
            result = self.parser.report_error(self.error)

        self.assertIs(result, self.error)
        self.assertEqual(self.parser._errors, [self.error])
        hook.assert_called_once_with(self.parser, self.error)
        raise_error.assert_not_called()

    def test_normal_error_obeys_enabled_exit_policy(self) -> None:
        with patch.object(
            self.error, 'raise_error', side_effect=SystemExit(1)
        ) as raise_error:
            with self.assertRaises(SystemExit) as caught:
                self.parser.report_error(self.error)

        self.assertEqual(caught.exception.code, 1)
        self.assertEqual(self.parser._errors, [self.error])
        raise_error.assert_called_once_with()

    def test_normal_error_obeys_disabled_exit_policy(self) -> None:
        with (
            patch.object(config, 'ERROR_EXIT_ON_ERROR', False),
            patch.object(self.error, 'raise_error') as raise_error,
        ):
            result = self.parser.report_error(self.error)

        self.assertIs(result, self.error)
        self.assertEqual(self.parser._errors, [self.error])
        raise_error.assert_not_called()


if __name__ == '__main__':
    unittest.main()
