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
import os
import sys
from functools import lru_cache
from pathlib import Path
from types import FrameType
from collections.abc import Callable

from .. import Format
from . import codes, stack
from .codes import CodeError, Codes, set_map_codes
from .stack import StackError


_dispatch_error_hooks: Callable[[object, 'Error'], str] | None = None
_should_exit: Callable[[], bool] = lambda: False
_hide_console: Callable[[], bool] = lambda: False


def configure_runtime(
    *,
    should_exit: Callable[[], bool] | None = None,
    hide_console: Callable[[], bool] | None = None,
    dispatch_error_hooks: Callable[[object, 'Error'], str] | None = None,
) -> None:
    """Inject optional host policies without importing a host framework."""
    global _dispatch_error_hooks, _should_exit, _hide_console
    if should_exit is not None:
        _should_exit = should_exit
    if hide_console is not None:
        _hide_console = hide_console
    if dispatch_error_hooks is not None:
        _dispatch_error_hooks = dispatch_error_hooks


@lru_cache(maxsize=4096)
def _resolve_origin(filename: str, cwd: str) -> str:
    """Resolve an error origin once per filename and working directory."""
    path = Path(filename)
    if not path.is_absolute():
        path = Path(cwd) / path
    return str(path.resolve())


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
        file (str): Source identity active when the error was instantiated.
    """

    name: str
    code: CodeError
    caution: tuple[str, ...]
    origin: str
    file: str

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
        self.file = Format.FileTar.file or 'unknown'
        self._error_hooks_dispatched = False

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
            return _resolve_origin(caller.f_code.co_filename, os.getcwd())
        except (OSError, ValueError):
            return caller.f_code.co_filename

    def __str__(self) -> str:
        """Return the short name of the error."""
        return self.name

    def get_index(self) -> int:
        """Return this error's registry index, or ``-1`` when unregistered.

        Complexity: O(1) amortized when registered through ``StackError.add``;
        direct external edits may require an O(N) cache repair.
        """
        return StackError.index_of(self)

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
        target_file = self.file

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

    def raise_error(
        self,
        exit: bool | None = None,
        *,
        hide_console: bool | None = None,
        dispatch: bool = True,
    ) -> None:
        """
        Print the error to the console (unless muted by the injected host policy)
        and either terminate the process with exit code 1 or raise `self`.

        Args:
            exit (bool | None): Explicit override for the configured host policy.
            hide_console (bool | None): Explicit console visibility override.
            dispatch (bool): Whether to evaluate the injected error hook dispatcher.
        """
        action = 'store'
        if dispatch and not self._error_hooks_dispatched:
            if _dispatch_error_hooks is not None:
                action = _dispatch_error_hooks(self, self)
            self._error_hooks_dispatched = True

        if action == 'omit' or getattr(self, "_suppress_raise", False):
            return

        muted = _hide_console() if hide_console is None else hide_console
        if not muted:
            self.print()

        should_exit = _should_exit() if exit is None else exit
        if should_exit:
            sys.exit(1)
        raise self


__all__ = [
    'CodeError',
    'Codes',
    'Error',
    'StackError',
    'configure_runtime',
    'codes',
    'set_map_codes',
    'stack',
]
