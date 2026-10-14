"""
Core Error Infrastructure (`gram.utilities.error`).
===================================================
Exposes the base `Error` exception class and underlying code/stack utilities
(`codes`, `stack`, `Codes`, `CodeError`, `StackError`, `set_map_codes`) so
higher-level catalogs (`gram.errors`) can define domain-specific error classes,
OSGDC dimension codes, and catalog entries.
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path
from types import FrameType

from gram.utilities import Format
from gram.utilities.error import codes, stack
from gram.utilities.error.codes import CodeError, Codes, set_map_codes
from gram.utilities.error.stack import StackError


class Error(Exception):
    """
    Base structured exception class providing OSGDC code formatting,
    automatic caller frame resolution, boxed console rendering, and
    integration with `StackError`.

    Attributes:
        name (str): Short identifier or title of the error.
        code (CodeError): Formal 5-digit OSGDC error code specification.
        caution (tuple[str, ...]): Explanatory paragraphs and repair hints.
        origin (str): Resolved file path where the error was instantiated.
    """

    name: str
    code: CodeError
    caution: tuple[str, ...]
    origin: str

    def __init__(
        self,
        name: str,
        code: CodeError,
        *caution: str,
    ) -> None:
        """
        Initialize the structured error and capture the originating caller file.

        Args:
            name (str): Short identifier of the error.
            code (CodeError): Formal OSGDC `CodeError` descriptor.
            *caution (str): Variable number of descriptive or advisory messages.
        """
        super().__init__(caution)
        self.name = name
        self.code = code
        self.caution = caution

        frame = inspect.currentframe()
        caller: FrameType | None = frame.f_back if frame is not None else None
        self.origin = self.origin_error(caller)

    @classmethod
    def origin_error(cls, caller: FrameType | None) -> str:
        """
        Resolve the absolute file path of the caller frame that instantiated the error.

        Args:
            caller (FrameType | None): The stack frame that invoked `__init__`.

        Returns:
            str: Resolved path string, or `'unknown'` if unavailable.
        """
        if caller is None:
            return 'unknown'

        try:
            return str(Path(caller.f_code.co_filename).resolve())
        except (OSError, ValueError):
            return caller.f_code.co_filename

    def __str__(self) -> str:
        """Return the short name of the error."""
        return self.name

    def get_index(self) -> int:
        """
        Return the sequential index of this error inside `StackError`,
        or `-1` if it has not been registered.
        """
        try:
            return StackError.__err__.index(self)
        except ValueError:
            return -1

    def _format_box(self, text: str) -> str:
        """Wrap `text` inside a centered 40-character decorative ASCII header bar."""
        inner_length = 38
        remaining = max(0, inner_length - len(text))
        left = remaining // 2
        right = remaining - left
        return f"|{'-' * left} {text} {'-' * right}|"

    def stringify(self, ansi: bool = False) -> str:
        """
        Build the formatted multi-line textual representation of the error.

        Args:
            ansi (bool): If True, injects ANSI color and style escape sequences.

        Returns:
            str: Formatted error block ready for console or log output.
        """
        code_str: str = self.code.stringify()
        top_header: str = self._format_box('ERROR')
        error_index: int = self.get_index()
        bottom_header: str = self._format_box(
            f'ERROR {error_index}' if error_index >= 0 else 'END OF ERROR'
        )

        caution_text: str = (
            '\n\n'.join(self.caution)
            if self.caution
            else 'No additional information provided.'
        )
        target_file: str = Format.FileTar.file or 'unknown'

        if ansi:
            return (
                f'{Format.ARED}{Format.ABOLD}{top_header}{Format.ARESET}\n'
                f'{Format.ARED}Name : {self.name}, Type: '
                f'{Format.AGREEN}{self.__class__.__name__}{Format.ARED}\n\n'
                f'{Format.ARESET}'
                f'{Format.AYELLOW}CAUTION: {Format.ARESET}'
                f'{caution_text}\n\n'
                f'{Format.ARED}INF:{Format.ARESET}\n'
                f'    FILE: {target_file}\n'
                f'    ORIGIN: {self.origin}\n'
                f'    CODE: {code_str}\n'
                f'{Format.ARED}{Format.ABOLD}{bottom_header}{Format.ARESET}'
            )

        return (
            f'{top_header}\n'
            f'Name: {self.name}, Type: {self.__class__.__name__}.\n\n'
            f'CAUTION: {caution_text}\n\n'
            f'INF:\n'
            f'    FILE: {target_file}\n'
            f'    ORIGIN: {self.origin}\n'
            f'    CODE: {code_str}\n\n'
            f'{bottom_header}'
        )

    def print(self) -> None:
        """
        Print the formatted error to standard output using ANSI colors,
        falling back to encoding-safe plain text on Unicode errors.
        """
        try:
            print(self.stringify(ansi=True))
        except (UnicodeEncodeError, UnicodeError):
            try:
                encoding = sys.stdout.encoding or 'ascii'
                safe_text = (
                    self.stringify(ansi=False)
                    .encode(encoding, errors='replace')
                    .decode(encoding)
                )
                print(safe_text)
            except Exception:
                print(f'ERROR: {self.name} - {self.caution}')

    def raise_error(self, exit: bool | None = None) -> None:
        """
        Print the error to the console (unless muted by configuration) and either
        terminate the process with exit code 1 or raise `self`.

        Args:
            exit (bool | None): Explicit override for `config.ERROR_EXIT_ON_ERROR`.
        """
        from gram import config

        if not getattr(config, 'ERROR_HIDE_CONSOLE', False):
            self.print()

        should_exit = (
            getattr(config, 'ERROR_EXIT_ON_ERROR', False) if exit is None else exit
        )
        if should_exit:
            sys.exit(1)
        raise self


__all__ = [
    'CodeError',
    'Codes',
    'Error',
    'StackError',
    'codes',
    'set_map_codes',
    'stack',
]