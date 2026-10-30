"""Bounded error registry, identity indexing, and recovery snapshots."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Literal
from weakref import ReferenceType, ref

if TYPE_CHECKING:
    from . import Error


class StackLimitReached(RuntimeError):
    """Raised when a stack cannot accept another error safely."""


class StackRecoveryError(RuntimeError):
    """Raised when a complete spill record cannot be recovered."""


@dataclass(slots=True)
class StackLimit:
    """Configure bounded error retention and JSONL spill recovery.

    Args:
        max_entries: Maximum in-memory entries before ``raise`` mode rejects
            the next error.
        spill_threshold: Number of in-memory entries that triggers ``spill``
            mode. Defaults to 80% of ``max_entries``.
        retain_entries: Number of newest entries retained after a spill.
            Defaults to half of ``spill_threshold``.
        mode: ``"spill"`` to archive old entries, or ``"raise"`` to reject
            entries at ``max_entries``.
        path: JSONL file used for structured recovery records.
        fsync: Whether each spill batch is flushed to the operating system.

        Raises:
            ValueError: If a limit, retention value, or mode is invalid.

    Complexity: O(F) once during :meth:`prepare`, where F is the existing
    number of spill-file lines; each append batch is O(B).
    """

    max_entries: int = 10_000
    spill_threshold: int | None = None
    retain_entries: int | None = None
    mode: Literal["spill", "raise"] = "spill"
    path: Path | str = Path("log/error-spill.jsonl")
    fsync: bool = True
    _next_line: int = field(init=False, default=1, repr=False)

    def __post_init__(self) -> None:
        """Validate the policy and normalize its path."""
        if not isinstance(self.max_entries, int) or self.max_entries < 1:
            raise ValueError("max_entries must be a positive integer")
        if self.spill_threshold is None:
            self.spill_threshold = max(1, int(self.max_entries * 0.8))
        if not isinstance(self.spill_threshold, int) or not (
            1 <= self.spill_threshold <= self.max_entries
        ):
            raise ValueError(
                "spill_threshold must be between 1 and max_entries"
            )
        if self.retain_entries is None:
            self.retain_entries = self.spill_threshold // 2
        if not isinstance(self.retain_entries, int) or not (
            0 <= self.retain_entries < self.spill_threshold
        ):
            raise ValueError(
                "retain_entries must be between 0 and spill_threshold - 1"
            )
        if self.mode not in ("spill", "raise"):
            raise ValueError("mode must be 'spill' or 'raise'")
        self.path = Path(self.path)

    def prepare(self) -> None:
        """Repair an incomplete final line and position the next line number.

        Complete existing lines are preserved. An incomplete tail is removed
        so a failed write cannot poison subsequent recovery.
        """
        path = self.path
        if not path.exists():
            self._next_line = 1
            return

        complete_end = 0
        line_count = 0
        with path.open("rb+") as handle:
            while True:
                line = handle.readline()
                if not line:
                    break
                if not line.endswith(b"\n"):
                    handle.truncate(complete_end)
                    break
                line_count += 1
                complete_end = handle.tell()
        self._next_line = line_count + 1

    def append_records(self, records: list[dict[str, Any]]) -> None:
        """Append one durable JSONL batch and assign consecutive line IDs.

        Args:
            records: Serializable record payloads without a ``line`` field.

        Raises:
            OSError: If the spill file cannot be written.

        Complexity: O(B) for a batch of B records, plus one file write.
        """
        if not records:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        first_line = self._next_line
        payload = "".join(
            json.dumps(
                {**record, "line": first_line + offset},
                ensure_ascii=False,
                separators=(",", ":"),
            )
            + "\n"
            for offset, record in enumerate(records)
        )
        try:
            with self.path.open("a", encoding="utf-8", newline="") as handle:
                handle.write(payload)
                handle.flush()
                if self.fsync:
                    os.fsync(handle.fileno())
        except OSError:
            # Keep only complete records if a filesystem error left a partial
            # final line behind. The original exception remains authoritative.
            self.prepare()
            raise
        self._next_line += len(records)

    @staticmethod
    def read_records(path: Path | str) -> list[dict[str, Any]]:
        """Recover complete JSONL records, ignoring only an incomplete tail.

        Args:
            path: JSONL spill file to read.

        Returns:
            A list of decoded records in physical file order.

        Raises:
            StackRecoveryError: If a complete line is malformed or is not an
                object.

        Complexity: O(F) time and O(R) returned data for F file lines.
        """
        source = Path(path)
        if not source.exists():
            return []

        records: list[dict[str, Any]] = []
        with source.open("r", encoding="utf-8", newline="") as handle:
            for line_number, raw_line in enumerate(handle, start=1):
                if not raw_line.endswith("\n"):
                    break
                if not raw_line.strip():
                    continue
                try:
                    record = json.loads(raw_line)
                except json.JSONDecodeError as exc:
                    raise StackRecoveryError(
                        f"Malformed spill record at physical line {line_number}"
                    ) from exc
                if not isinstance(record, dict):
                    raise StackRecoveryError(
                        f"Spill record at physical line {line_number} is not an object"
                    )
                records.append(record)
        return records


class _ProtectedErrorList(list["Error"]):
    """Readable list facade that rejects unsupported direct mutation."""

    @staticmethod
    def _reject(*args: object, **kwargs: object) -> None:
        raise RuntimeError(
            "StackError.__err__ is read-only; use StackError.add(), "
            "StackError.clear(), or the stack APIs"
        )

    append = _reject
    extend = _reject
    insert = _reject
    pop = _reject
    remove = _reject
    clear = _reject
    sort = _reject
    reverse = _reject
    __setitem__ = _reject
    __delitem__ = _reject
    __iadd__ = _reject
    __imul__ = _reject


class StackError:
    """Register errors by identity and optionally spill old entries to JSONL.

    ``__err__`` remains a readable list for compatibility. Its public
    mutators intentionally raise ``RuntimeError`` because an untracked list
    edit would invalidate the O(1) identity index. Use :meth:`add`,
    :meth:`clear`, and :meth:`_pop_recent` instead.

    Errors are not registered automatically. A different instance with equal
    rendered content is retained, while repeated additions of the same object
    are ignored, including after that object has been spilled.
    """

    LOGFILE: ClassVar[Path] = Path("log/error.log")
    __err__: ClassVar[_ProtectedErrorList] = _ProtectedErrorList()
    _index_by_identity: ClassVar[dict[int, int]] = {}
    _sequence_by_identity: ClassVar[dict[int, int]] = {}
    _seen_refs: ClassVar[dict[int, ReferenceType[Error]]] = {}
    _next_sequence: ClassVar[int] = 1
    _storage_object_id: ClassVar[int] = id(__err__)
    _storage_length: ClassVar[int] = 0
    _limit: ClassVar[StackLimit | None] = None
    _spilled_count: ClassVar[int] = 0

    @classmethod
    def _ensure_storage(cls) -> None:
        """Reject replacement or hidden mutation of the public list."""
        storage = cls.__err__
        if not isinstance(storage, _ProtectedErrorList):
            raise RuntimeError(
                "StackError.__err__ was replaced; use StackError.clear()"
            )
        if id(storage) != cls._storage_object_id:
            raise RuntimeError(
                "StackError.__err__ was replaced; use StackError.clear()"
            )
        if len(storage) != cls._storage_length:
            raise RuntimeError(
                "StackError.__err__ was modified outside StackError APIs"
            )

    @classmethod
    def _remember(cls, error: Error) -> None:
        """Remember an error without retaining spilled objects strongly."""
        try:
            identity = id(error)

            def forget(reference: ReferenceType[Error]) -> None:
                if cls._seen_refs.get(identity) is reference:
                    cls._seen_refs.pop(identity, None)

            cls._seen_refs[identity] = ref(error, forget)
        except TypeError as exc:
            raise TypeError("StackError.add() requires a weak-referenceable error") from exc

    @classmethod
    def _rebuild_index(cls) -> None:
        """Rebuild active indices after a cold-path prefix removal."""
        previous_sequences = dict(cls._sequence_by_identity)
        cls._index_by_identity.clear()
        cls._sequence_by_identity.clear()
        for index, error in enumerate(cls.__err__):
            identity = id(error)
            cls._index_by_identity[identity] = index
            sequence = previous_sequences.get(identity)
            if sequence is None:
                sequence = cls._next_sequence
                cls._next_sequence += 1
            cls._sequence_by_identity[identity] = sequence

    @classmethod
    def configure_limit(cls, limit: StackLimit | None) -> None:
        """Enable or disable bounded retention without changing stack APIs.

        Args:
            limit: A prepared policy, or ``None`` to disable automatic spills.

        Raises:
            TypeError: If ``limit`` is not a :class:`StackLimit` or ``None``.
            OSError: If the configured spill file cannot be prepared.
            StackLimitReached: If existing entries cannot satisfy the policy.

        Complexity: O(F + N) when enabling a policy, where F is the existing
        spill-file size and N is the current active stack size.
        """
        cls._ensure_storage()
        if limit is not None and not isinstance(limit, StackLimit):
            raise TypeError("limit must be a StackLimit or None")
        if limit is not None:
            limit.prepare()
        previous = cls._limit
        cls._limit = limit
        try:
            cls._enforce_limit()
        except Exception:
            cls._limit = previous
            raise

    @classmethod
    def _enforce_limit(cls) -> None:
        """Apply the active limit after a registration or configuration."""
        limit = cls._limit
        if limit is None or not cls.__err__:
            return
        if limit.mode == "raise":
            if len(cls.__err__) > limit.max_entries:
                raise StackLimitReached(
                    f"StackError reached its limit of {limit.max_entries} entries"
                )
            return
        if len(cls.__err__) >= limit.spill_threshold:
            retain = limit.retain_entries
            cls._spill_prefix(len(cls.__err__) - retain)

    @classmethod
    def _record_for(cls, error: Error) -> dict[str, Any]:
        """Build one structured, recoverable spill record."""
        return {
            "seq": cls._sequence_by_identity[id(error)],
            "type": error.__class__.__name__,
            "name": error.name,
            "code": error.code.stringify(),
            "file": getattr(error, "file", "unknown"),
            "origin": getattr(error, "origin", "unknown"),
            "caution": list(getattr(error, "caution", ())),
            "rendered": error.stringify(ansi=False),
        }

    @classmethod
    def _spill_prefix(cls, count: int) -> None:
        """Write and remove the oldest active entries as one batch."""
        limit = cls._limit
        if limit is None or count <= 0:
            return
        entries = list(cls.__err__[:count])
        try:
            limit.append_records([cls._record_for(error) for error in entries])
        except OSError as exc:
            raise StackLimitReached(
                f"Unable to spill StackError entries to {limit.path}"
            ) from exc

        list.__delitem__(cls.__err__, slice(0, count))
        cls._storage_length -= count
        cls._spilled_count += count
        cls._rebuild_index()

    @classmethod
    def index_of(cls, error: Error) -> int:
        """Return an active error's zero-based index, or ``-1``.

        Complexity: O(1) for API-managed entries. Direct low-level mutation is
        detected and rejected rather than falling back to an O(N) scan.
        """
        cls._ensure_storage()
        identity = id(error)
        index = cls._index_by_identity.get(identity)
        if index is not None and cls.__err__[index] is error:
            return index
        return -1

    @classmethod
    def write(cls) -> None:
        """Overwrite ``LOGFILE`` with the active in-memory error snapshot.

        Structured spilled records remain in :class:`StackLimit`'s JSONL file
        and can be recovered with :meth:`recover`. Formatting is completed
        before opening the text snapshot, so rendering failures do not truncate
        the previous file.

        Complexity: O(N) formatting plus one file write for N active entries.
        """
        cls._ensure_storage()
        try:
            content = "\n\n".join(
                error.stringify(ansi=False) for error in cls.__err__
            )
            if content:
                content += "\n\n"
            cls.LOGFILE.parent.mkdir(parents=True, exist_ok=True)
            cls.LOGFILE.write_text(content, encoding="utf-8")
        except OSError as exc:
            print(f"ERROR al escribir en el archivo log {cls.LOGFILE}: {exc}")

    @classmethod
    def add(cls, error: Error) -> None:
        """Register an error once by object identity.

        Args:
            error: Weak-referenceable structured error to register.

        Raises:
            StackLimitReached: If the active limit rejects or cannot spill the
                new entry.
            TypeError: If ``error`` cannot be tracked by identity.
            RuntimeError: If ``__err__`` was externally altered.

        Complexity: O(1) amortized on the normal path. A spill is O(B) for the
        batch written when the configured threshold is reached.
        """
        cls._ensure_storage()
        identity = id(error)
        seen_reference = cls._seen_refs.get(identity)
        if seen_reference is not None and seen_reference() is error:
            return
        try:
            ref(error)
        except TypeError as exc:
            raise TypeError(
                "StackError.add() requires a weak-referenceable error"
            ) from exc
        limit = cls._limit
        if limit is not None and limit.mode == "raise":
            if len(cls.__err__) >= limit.max_entries:
                raise StackLimitReached(
                    f"StackError reached its limit of {limit.max_entries} entries"
                )

        sequence = cls._next_sequence
        cls._next_sequence += 1
        list.append(cls.__err__, error)
        cls._storage_length += 1
        cls._index_by_identity[identity] = len(cls.__err__) - 1
        cls._sequence_by_identity[identity] = sequence
        cls._remember(error)
        cls._enforce_limit()

    @classmethod
    def recover(cls, path: Path | str | None = None) -> list[dict[str, Any]]:
        """Recover structured spill records by line number and sequence ID.

        Args:
            path: Optional override. When omitted, the active limit's path is
                used.

        Returns:
            Decoded JSONL records. An incomplete final line is ignored.

        Raises:
            ValueError: If no path is provided and no limit is configured.
            StackRecoveryError: If a complete spill line is malformed.

        Complexity: O(F) time and O(R) returned records.
        """
        cls._ensure_storage()
        if path is None:
            if cls._limit is None:
                raise ValueError("No StackLimit is configured")
            path = cls._limit.path
        return StackLimit.read_records(path)

    @classmethod
    def _pop_recent(cls, count: int) -> list[Error]:
        """Remove up to ``count`` active entries for error recovery internals."""
        cls._ensure_storage()
        if count <= 0:
            return []
        count = min(count, len(cls.__err__))
        start = len(cls.__err__) - count
        entries = list(cls.__err__[start:])
        list.__delitem__(cls.__err__, slice(start, None))
        cls._storage_length -= count
        for error in entries:
            identity = id(error)
            cls._index_by_identity.pop(identity, None)
            cls._sequence_by_identity.pop(identity, None)
            cls._seen_refs.pop(identity, None)
        cls._rebuild_index()
        return entries

    @classmethod
    def last(cls) -> Error | None:
        """Return the newest active error, or ``None`` when the stack is empty."""
        cls._ensure_storage()
        if not cls.__err__:
            return None
        return cls.__err__[-1]

    @classmethod
    def all(cls) -> list[Error]:
        """Return a shallow copy of active in-memory errors in registration order.

        Complexity: O(N) for N active entries; spilled entries are available
        through :meth:`recover`.
        """
        cls._ensure_storage()
        return list(cls.__err__)

    @classmethod
    def count(cls) -> int:
        """Return the number of active in-memory entries. Complexity: O(1)."""
        cls._ensure_storage()
        return len(cls.__err__)

    @classmethod
    def total_count(cls) -> int:
        """Return active entries plus entries spilled in this stack session."""
        cls._ensure_storage()
        return len(cls.__err__) + cls._spilled_count

    @classmethod
    def clear(cls) -> None:
        """Clear active entries, indices, and session spill accounting.

        The JSONL recovery file is intentionally preserved. Callers can use
        :meth:`recover` after clearing to rescue records already written.
        """
        cls._ensure_storage()
        list.clear(cls.__err__)
        cls._index_by_identity.clear()
        cls._sequence_by_identity.clear()
        cls._seen_refs.clear()
        cls._storage_length = 0
        cls._spilled_count = 0

    @classmethod
    def empty(cls) -> bool:
        """Return whether the active in-memory stack is empty. Complexity: O(1)."""
        return cls.count() == 0


__all__ = [
    "StackError",
    "StackLimit",
    "StackLimitReached",
    "StackRecoveryError",
]
