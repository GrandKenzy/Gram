"""
Gram Binary IR (GIR 1.0) Deserializer and High-Performance Tree Walker (`gram.ir.reader`).
========================================================================================
Provides zero-dependency binary decoding and object-oriented AST tree navigation
over relocatable `.gir` buffers produced by the Gram native C Ahead-Of-Time pipeline.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
import struct
from typing import IO, Any, Iterator, Literal

from gram.core.lexer.tokens import Token

# Binary layout constants matching gram_ir.h
GIR_MAGIC = b"GIR\0"
GIR_VERSION_MAJOR = 1
GIR_VERSION_MINOR = 0

HEADER_STRUCT_FORMAT = "<4sHHIIQQIIIIIIIIQ"
HEADER_SIZE = 72

NODE_STRUCT_FORMAT = "<HHIIIIIIIII"
NODE_SIZE = 40

# Node flags matching gram_ir.h
GIR_NODE_TERMINAL = 0x1
GIR_NODE_RULE = 0x2
GIR_NODE_EXPR = 0x4
GIR_NODE_ARRAY = 0x8
GIR_NODE_RAW = 0x10


def _fnv1a_64(data: bytes) -> int:
    """Compute 64-bit FNV-1a hash matching gram_ir_hash64 in C."""
    h = 1469598103934665603
    prime = 1099511628211
    for b in data:
        h = ((h ^ b) * prime) & 0xFFFFFFFFFFFFFFFF
    return h


@dataclass(frozen=True, slots=True)
class GirHeader:
    """Metadata header of a GIR 1.0 binary buffer (72 bytes)."""

    magic: bytes
    version_major: int
    version_minor: int
    flags: int
    header_size: int
    grammar_id: int
    source_hash: int
    source_size: int
    string_count: int
    string_offsets_offset: int
    string_pool_offset: int
    string_pool_bytes: int
    nodes_offset: int
    node_count: int
    root_index: int
    total_size: int

    @property
    def version(self) -> tuple[int, int]:
        return self.version_major, self.version_minor

    @property
    def is_little_endian(self) -> bool:
        return bool(self.flags & 0x1)


class GirNode:
    """An individual AST node within a parsed GIR buffer."""

    __slots__ = (
        "_children",
        "_parent",
        "_text_override",
        "child_count",
        "column",
        "depth",
        "first_child_index",
        "flags",
        "index",
        "kind",
        "line",
        "next_sibling_index",
        "src_length",
        "src_start",
        "symbol_id",
        "value",
        "view",
    )

    def __init__(
        self,
        view: GirView,
        index: int,
        kind: int,
        flags: int,
        symbol_id: int,
        value: int,
        src_start: int,
        src_length: int,
        line: int,
        column: int,
        first_child_index: int,
        next_sibling_index: int,
        child_count: int,
        depth: int = 0,
    ) -> None:
        self.view = view
        self.index = index
        self.kind = kind
        self.flags = flags
        self.symbol_id = symbol_id
        self.value = value
        self.src_start = src_start
        self.src_length = src_length
        self.line = line
        self.column = column
        self.first_child_index = first_child_index
        self.next_sibling_index = next_sibling_index
        self.child_count = child_count
        self.depth = depth
        self._children: list[GirNode] | None = None
        self._parent: GirNode | None = None
        self._text_override: str | None = None

    @property
    def is_terminal(self) -> bool:
        """Return True if this node represents a lexical terminal token."""
        return bool(self.flags & GIR_NODE_TERMINAL)

    @property
    def is_rule(self) -> bool:
        """Return True if this node represents a parsed grammatical rule."""
        return bool(self.flags & GIR_NODE_RULE)

    @property
    def is_expr(self) -> bool:
        """Return True if this node represents a Pratt expression (unary or binary)."""
        return bool(self.flags & GIR_NODE_EXPR)

    @property
    def is_array(self) -> bool:
        """Return True if this node represents an array/repetition sequence."""
        return bool(self.flags & GIR_NODE_ARRAY)

    @property
    def is_raw(self) -> bool:
        """Return True if this node represents an opaque unparsed block (CaptureRaw)."""
        return bool(self.flags & GIR_NODE_RAW)

    @property
    def symbol_name(self) -> str:
        """Raw string from the GIR pool associated with this node's symbol_id."""
        return self.view.get_string(self.symbol_id)

    @property
    def kind_name(self) -> str:
        """Self-describing type name: token name for terminals, rule/kind name for non-terminals."""
        if self.is_terminal:
            tok = Token.from_code(self.value)
            return tok.name if tok is not None else f"TOKEN_{self.value}"
        return self.symbol_name

    @property
    def text(self) -> str:
        """Source text or captured lexeme corresponding to this node."""
        if self._text_override is not None:
            return self._text_override
        if self.is_terminal:
            return self.symbol_name
        if self.view.source_bytes is not None and self.src_length > 0:
            end = self.src_start + self.src_length
            raw = self.view.source_bytes[self.src_start : end]
            return raw.decode("utf-8", errors="replace")
        return self.symbol_name

    @property
    def span(self) -> tuple[int, int]:
        """Byte offset range in the source buffer `(src_start, src_start + src_length)`."""
        return self.src_start, self.src_start + self.src_length

    @property
    def parent(self) -> GirNode | None:
        """Parent node in the tree hierarchy, or None if this is the root node."""
        return self._parent

    @property
    def children(self) -> list[GirNode]:
        """List of immediate child nodes."""
        if self._children is None:
            res: list[GirNode] = []
            curr_idx = self.first_child_index
            while curr_idx != 0 and curr_idx < len(self.view.nodes):
                child = self.view.nodes[curr_idx]
                child._parent = self
                child.depth = self.depth + 1
                res.append(child)
                curr_idx = child.next_sibling_index
            self._children = res
        return self._children

    def walk(self, order: Literal["pre", "post"] = "pre") -> Iterator[GirNode]:
        """
        Recursively traverse all descendant nodes in either preorder or postorder.

        Args:
            order: "pre" for preorder (parent before children), "post" for postorder.

        Yields:
            GirNode: Each visited node in traversal order.
        """
        if order == "pre":
            yield self
            for child in self.children:
                yield from child.walk(order=order)
        elif order == "post":
            for child in self.children:
                yield from child.walk(order=order)
            yield self
        else:
            raise ValueError(f"Unsupported walk order {order!r}; must be 'pre' or 'post'.")

    def find(self, name: str) -> Iterator[GirNode]:
        """
        Search and yield all descendant nodes matching `name` against `kind_name` or `symbol_name`.
        """
        for node in self.walk():
            if node.kind_name == name or node.symbol_name == name:
                yield node

    def find_first(self, name: str) -> GirNode | None:
        """
        Return the first descendant node matching `name`, or None if not found.
        """
        for node in self.find(name):
            return node
        return None

    def __repr__(self) -> str:
        tag = self.kind_name
        extra = f" {self.text!r}" if self.is_terminal or self.is_raw else ""
        return (
            f"<GirNode #{self.index} {tag}{extra} "
            f"@{self.line}:{self.column} [{self.src_start}+{self.src_length}]>"
        )


class GirView:
    """
    Validated in-memory view over a flat Gram Binary IR (`.gir`) buffer.
    """

    __slots__ = (
        "_data",
        "_source_bytes",
        "header",
        "nodes",
        "strings",
    )

    def __init__(
        self,
        data: bytes | bytearray | memoryview,
        source: str | bytes | None = None,
    ) -> None:
        raw = bytes(data) if not isinstance(data, (bytes, memoryview)) else data
        if len(raw) < HEADER_SIZE:
            raise ValueError(
                f"Invalid GIR buffer: length {len(raw)} is smaller than header size ({HEADER_SIZE} bytes)."
            )

        fields = struct.unpack_from(HEADER_STRUCT_FORMAT, raw, 0)
        (
            magic,
            v_maj,
            v_min,
            flags,
            hdr_size,
            grammar_id,
            source_hash,
            source_size,
            string_count,
            str_off_off,
            str_pool_off,
            str_pool_bytes,
            nodes_off,
            node_count,
            root_index,
            total_size,
        ) = fields

        if magic != GIR_MAGIC:
            raise ValueError(f"Invalid GIR magic identifier: expected {GIR_MAGIC!r}, got {magic!r}.")
        if v_maj != GIR_VERSION_MAJOR:
            raise ValueError(
                f"Unsupported GIR major version {v_maj}.{v_min}; expected {GIR_VERSION_MAJOR}.x."
            )
        if not (flags & 0x1):
            raise ValueError("Unsupported big-endian GIR buffer; only little-endian buffers are supported.")
        if hdr_size < HEADER_SIZE:
            raise ValueError(f"Corrupt GIR header size: {hdr_size} bytes.")
        if total_size > len(raw):
            raise ValueError(
                f"Truncated GIR buffer: expected total size {total_size} bytes, available {len(raw)} bytes."
            )

        self.header = GirHeader(
            magic=magic,
            version_major=v_maj,
            version_minor=v_min,
            flags=flags,
            header_size=hdr_size,
            grammar_id=grammar_id,
            source_hash=source_hash,
            source_size=source_size,
            string_count=string_count,
            string_offsets_offset=str_off_off,
            string_pool_offset=str_pool_off,
            string_pool_bytes=str_pool_bytes,
            nodes_offset=nodes_off,
            node_count=node_count,
            root_index=root_index,
            total_size=total_size,
        )
        self._data = raw

        # Source buffer for span slicing
        if isinstance(source, str):
            self._source_bytes = source.encode("utf-8")
        elif isinstance(source, (bytes, bytearray, memoryview)):
            self._source_bytes = bytes(source)
        else:
            self._source_bytes = None

        # 1. Unpack string offsets and decode string pool
        str_offsets_count = string_count + 1
        str_offsets_fmt = f"<{str_offsets_count}I"
        str_offsets_bytes = str_offsets_count * 4
        if str_off_off + str_offsets_bytes > len(raw):
            raise ValueError("Truncated GIR string offsets table.")
        offsets = struct.unpack_from(str_offsets_fmt, raw, str_off_off)

        if str_pool_off + str_pool_bytes > len(raw):
            raise ValueError("Truncated GIR string pool.")
        pool_bytes = raw[str_pool_off : str_pool_off + str_pool_bytes]

        strings_list: list[str] = []
        for i in range(string_count):
            start = offsets[i]
            end = offsets[i + 1]
            if end > str_pool_bytes or start > end:
                raise ValueError(f"Invalid string pool boundaries for id {i}: [{start}, {end}].")
            raw_s = pool_bytes[start:end]
            if raw_s.endswith(b"\0"):
                raw_s = raw_s[:-1]
            strings_list.append(raw_s.decode("utf-8", errors="replace"))
        self.strings = tuple(strings_list)

        # 2. Unpack node table
        nodes_expected_bytes = node_count * NODE_SIZE
        if nodes_off + nodes_expected_bytes > len(raw):
            raise ValueError("Truncated GIR nodes table.")

        nodes_list: list[GirNode] = []
        for idx in range(node_count):
            offset = nodes_off + idx * NODE_SIZE
            node_fields = struct.unpack_from(NODE_STRUCT_FORMAT, raw, offset)
            (
                kind,
                node_flags,
                symbol_id,
                value,
                src_start,
                src_length,
                line,
                col,
                first_child,
                next_sibling,
                child_count,
            ) = node_fields
            node = GirNode(
                view=self,
                index=idx,
                kind=kind,
                flags=node_flags,
                symbol_id=symbol_id,
                value=value,
                src_start=src_start,
                src_length=src_length,
                line=line,
                column=col,
                first_child_index=first_child,
                next_sibling_index=next_sibling,
                child_count=child_count,
                depth=0,
            )
            nodes_list.append(node)
        self.nodes = tuple(nodes_list)

        # Precompute children and parent tree relationships
        if 0 < self.header.root_index < len(self.nodes):
            self._link_tree(self.nodes[self.header.root_index], parent=None, depth=0)

    def _link_tree(self, node: GirNode, parent: GirNode | None, depth: int) -> None:
        node._parent = parent
        node.depth = depth
        _ = node.children  # trigger lazy children list population
        for child in node.children:
            self._link_tree(child, parent=node, depth=depth + 1)

    @property
    def root(self) -> GirNode:
        """The root `GirNode` of the parsed AST, or the null sentinel if empty."""
        idx = self.header.root_index
        if 0 < idx < len(self.nodes):
            return self.nodes[idx]
        return self.nodes[0]

    @property
    def node_count(self) -> int:
        """Total number of nodes (including root and children, excluding null sentinel 0)."""
        return max(0, self.header.node_count - 1)

    @property
    def source_bytes(self) -> bytes | None:
        """Active source bytes buffer if attached."""
        return self._source_bytes

    def attach_source(self, source: str | bytes) -> None:
        """Attach original source text/bytes for accurate span string resolution."""
        if isinstance(source, str):
            self._source_bytes = source.encode("utf-8")
        else:
            self._source_bytes = bytes(source)

    def get_string(self, symbol_id: int) -> str:
        """Retrieve an interned string by ID from the GIR string pool."""
        if 0 <= symbol_id < len(self.strings):
            return self.strings[symbol_id]
        return ""

    def matches_grammar(self, grammar_id: int) -> bool:
        """Return True if this IR was generated by a grammar with fingerprint `grammar_id`."""
        return self.header.grammar_id == grammar_id

    def matches_source(self, source: str | bytes) -> bool:
        """Return True if `source` matches the 64-bit FNV-1a hash stored in the GIR header."""
        raw = source.encode("utf-8") if isinstance(source, str) else bytes(source)
        return _fnv1a_64(raw) == self.header.source_hash

    def walk(self, order: Literal["pre", "post"] = "pre") -> Iterator[GirNode]:
        """
        Traverse all nodes in the parsed AST starting from the root node.

        Args:
            order: "pre" for preorder (top-down), "post" for postorder (bottom-up).
        """
        root = self.root
        if root.index != 0:
            yield from root.walk(order=order)

    def dump(self, file: IO[str] | None = None) -> str:
        """
        Format and print the GIR tree in a human-readable indented format matching C `gram_ir_dump`.
        """
        lines: list[str] = []
        h = self.header
        lines.append(
            f"GIR v{h.version_major}.{h.version_minor}  "
            f"nodes={self.node_count} strings={h.string_count} pool={h.string_pool_bytes} bytes  "
            f"total={h.total_size} bytes"
        )
        for node in self.walk(order="pre"):
            indent = "  " * node.depth
            if node.is_terminal:
                lines.append(
                    f"{indent}{node.kind_name} {node.text!r} @{node.line}:{node.column} [{node.src_start}+{node.src_length}]"
                )
            else:
                count_str = f" ({node.child_count})" if node.child_count else ""
                lines.append(
                    f"{indent}{node.kind_name}{count_str} @{node.line}:{node.column} [{node.src_start}+{node.src_length}]"
                )
        result = "\n".join(lines)
        if file is not None:
            file.write(result + "\n")
        return result

    @classmethod
    def from_bytes(
        cls,
        data: bytes | bytearray | memoryview,
        source: str | bytes | None = None,
    ) -> GirView:
        """Construct a `GirView` from an in-memory byte buffer."""
        return cls(data, source=source)

    @classmethod
    def from_file(
        cls,
        path: str | Path,
        source: str | bytes | None = None,
    ) -> GirView:
        """Read and construct a `GirView` from a `.gir` file on disk."""
        data = Path(path).read_bytes()
        return cls(data, source=source)


def load_gir(
    source: str | Path | bytes | bytearray | memoryview,
    source_text: str | bytes | None = None,
) -> GirView:
    """
    Load and parse a Gram Binary IR (`.gir`) representation from a file path or in-memory byte buffer.

    Args:
        source: A file path (`str` or `Path`) pointing to a `.gir` file, or raw bytes.
        source_text: Optional original source code string or bytes for span text extraction.

    Returns:
        GirView: Parsed, navigable zero-dependency GIR representation.
    """
    if isinstance(source, (str, Path)) and (isinstance(source, Path) or os.path.exists(source)):
        return GirView.from_file(source, source=source_text)
    if isinstance(source, (bytes, bytearray, memoryview)):
        return GirView.from_bytes(source, source=source_text)
    if isinstance(source, str):
        # Path string that does not exist on disk
        return GirView.from_file(source, source=source_text)
    raise TypeError(f"Expected file path or bytes, got {type(source).__name__}")


load = load_gir


__all__ = [
    "GIR_MAGIC",
    "GIR_NODE_ARRAY",
    "GIR_NODE_EXPR",
    "GIR_NODE_RAW",
    "GIR_NODE_RULE",
    "GIR_NODE_TERMINAL",
    "GIR_VERSION_MAJOR",
    "GIR_VERSION_MINOR",
    "GirHeader",
    "GirNode",
    "GirView",
    "load",
    "load_gir",
]
