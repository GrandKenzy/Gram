"""Global error registry and snapshot writer for the error utilities."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from . import Error


class StackError:
    """Store explicitly registered errors and write them as one snapshot.

    The public ``__err__`` list remains available for compatibility with
    existing consumers. Use :meth:`add` for normal registration; it ignores
    repeated additions of the same error instance.
    """

    LOGFILE: ClassVar[Path] = Path('log/error.log')
    __err__: ClassVar[list[Error]] = []
    _index_by_identity: ClassVar[dict[int, int]] = {}

    @classmethod
    def _index_of(cls, error: Error) -> int:
        """Return the identity index, repairing the cache after direct list edits.

        Complexity: O(1) when the cache is current; O(N) during fallback repair.
        """
        identity = id(error)
        index = cls._index_by_identity.get(identity)
        if (
            index is not None
            and index < len(cls.__err__)
            and cls.__err__[index] is error
        ):
            return index

        for index, candidate in enumerate(cls.__err__):
            if candidate is error:
                cls._index_by_identity[identity] = index
                return index

        cls._index_by_identity.pop(identity, None)
        return -1

    @classmethod
    def index_of(cls, error: Error) -> int:
        """Return the zero-based index of ``error``, or ``-1`` if absent.

        Complexity: O(1) amortized for errors registered through :meth:`add`.
        """
        return cls._index_of(error)

    @classmethod
    def write(cls) -> None:
        """Overwrite ``LOGFILE`` with all explicitly registered errors.

        Errors are rendered in registration order and separated by two newline
        characters. Formatting completes before the file is opened, preventing
        a rendering failure from truncating an existing snapshot.

        Complexity: O(N) formatting plus one file write, where N is the number
        of entries in ``__err__``.
        """
        try:
            content = '\n\n'.join(
                error.stringify(ansi=False) for error in cls.__err__
            )
            if content:
                content += '\n\n'
            cls.LOGFILE.parent.mkdir(parents=True, exist_ok=True)
            cls.LOGFILE.write_text(content, encoding='utf-8')
        except OSError as exc:
            print(f'ERROR al escribir en el archivo log {cls.LOGFILE}: {exc}')

    @classmethod
    def add(cls, error: Error) -> None:
        """Register ``error`` once by object identity.

        Adding a different error instance always appends it, even when its
        rendered content is equal to an existing entry.

        Complexity: O(1) amortized.
        """
        if cls._index_of(error) >= 0:
            return
        cls._index_by_identity[id(error)] = len(cls.__err__)
        cls.__err__.append(error)

    @classmethod
    def last(cls) -> Error | None:
        """Return the most recently registered error, or ``None``."""
        if not cls.__err__:
            return None
        return cls.__err__[-1]

    @classmethod
    def all(cls) -> list[Error]:
        """Return a shallow copy of the registered error list.

        Complexity: O(N).
        """
        return cls.__err__.copy()

    @classmethod
    def count(cls) -> int:
        """Return the number of registered entries.

        Complexity: O(1).
        """
        return len(cls.__err__)

    @classmethod
    def clear(cls) -> None:
        """Remove all registered errors and reset the identity index."""
        cls.__err__.clear()
        cls._index_by_identity.clear()

    @classmethod
    def empty(cls) -> bool:
        """Return whether no errors are registered.

        Complexity: O(1).
        """
        return not cls.__err__


__all__ = ['StackError']
