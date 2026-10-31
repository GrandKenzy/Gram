"""
Native C Lexer Backend Adapter (`gram.core.lexer.c_backend`).
=============================================================
Provides `ctypes` bindings to the native C lexer runtime (`native/gram_lexer`),
automatic shared-library compilation and caching, dynamic table marshaling from
`Session` or global catalogs, and full parity with `Lexer.process()`.
"""
from __future__ import annotations

import ctypes
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from gram import errors
from gram.core.lexer.flags import TokenFlags
from gram.core.lexer.tokens import Token, TokenType

if TYPE_CHECKING:
    from gram.core.lexer.core import Lexer

# Status codes from gram_lexer.h
GRAM_LEXER_TOKEN = 0
GRAM_LEXER_EOF = 1
GRAM_LEXER_ERROR = 2
GRAM_LEXER_FATAL = 3

# Indentation modes
GRAM_INDENT_SPACES = 0
GRAM_INDENT_TABS = 1
GRAM_INDENT_MIXED = 2

# Error policies
GRAM_ERROR_POLICY_RECOVER = 0
GRAM_ERROR_POLICY_STOP_ON_ERROR = 1
GRAM_ERROR_POLICY_STOP_ON_FATAL = 2

# Diagnostic codes
GRAM_DIAG_CODE_EMPTY_KEYWORDS = 1
GRAM_DIAG_CODE_UNEXPECTED_CHARACTER = 6
GRAM_DIAG_CODE_UNCLOSED_STRING = 7
GRAM_DIAG_CODE_INDENTATION_MISMATCH = 8
GRAM_DIAG_CODE_INVALID_NUMBER = 9
GRAM_DIAG_CODE_INVALID_UTF8 = 14

# Extended token flags
GRAM_TOKEN_PUBLIC_FLAGS_MASK = 0x03
GRAM_TOKEN_FLAG_HAS_ESCAPES = 1 << 8
GRAM_TOKEN_FLAG_MULTILINE = 1 << 9
GRAM_TOKEN_FLAG_BOOL_TRUE = 1 << 10
GRAM_TOKEN_FLAG_NUMERIC_SUFF = 1 << 11
GRAM_TOKEN_FLAG_BLOCK_COMMENT = 1 << 12
GRAM_TOKEN_CUSTOM_BASE = 1000


class GramDiagnosticC(ctypes.Structure):
    _fields_ = [
        ("code", ctypes.c_uint32),
        ("severity", ctypes.c_int),
        ("start", ctypes.c_uint32),
        ("end", ctypes.c_uint32),
        ("line", ctypes.c_uint32),
        ("column", ctypes.c_uint32),
        ("message", ctypes.c_char_p),
        ("message_length", ctypes.c_uint32),
    ]


GramDiagnosticSinkCFunc = ctypes.CFUNCTYPE(
    None, ctypes.c_void_p, ctypes.POINTER(GramDiagnosticC)
)


class GramDiagSinkC(ctypes.Structure):
    _fields_ = [
        ("context", ctypes.c_void_p),
        ("emit", GramDiagnosticSinkCFunc),
    ]


class GramDiagSeverityOverrideC(ctypes.Structure):
    _fields_ = [
        ("code", ctypes.c_uint32),
        ("severity", ctypes.c_int),
    ]


class GramDiagBufferC(ctypes.Structure):
    _fields_ = [
        ("items", ctypes.POINTER(GramDiagnosticC)),
        ("capacity", ctypes.c_uint32),
        ("count", ctypes.c_uint32),
        ("total_emitted", ctypes.c_uint32),
        ("dropped_count", ctypes.c_uint32),
        ("max_diagnostics", ctypes.c_uint32),
        ("policy", ctypes.c_int),
        ("halted", ctypes.c_uint8),
        ("error_count", ctypes.c_uint32),
        ("fatal_count", ctypes.c_uint32),
        ("overrides", ctypes.POINTER(GramDiagSeverityOverrideC)),
        ("override_count", ctypes.c_uint32),
        ("user_sink", GramDiagSinkC),
        ("message_arena", ctypes.c_char_p),
        ("message_arena_capacity", ctypes.c_uint32),
        ("message_arena_used", ctypes.c_uint32),
    ]


class GramTokenC(ctypes.Structure):
    _fields_ = [
        ("kind", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
        ("start", ctypes.c_uint32),
        ("length", ctypes.c_uint32),
        ("line", ctypes.c_uint32),
        ("column", ctypes.c_uint32),
        ("content_start", ctypes.c_uint32),
        ("content_length", ctypes.c_uint32),
        ("prefix_start", ctypes.c_uint32),
        ("prefix_length", ctypes.c_uint32),
    ]


class GramLexerConfigC(ctypes.Structure):
    _fields_ = [
        ("tab_width", ctypes.c_uint32),
        ("indentation_mode", ctypes.c_uint8),
        ("add_info", ctypes.c_uint8),
        ("support_triple_strings", ctypes.c_uint8),
        ("support_prefixed_strings", ctypes.c_uint8),
        ("support_indent", ctypes.c_uint8),
        ("error_policy", ctypes.c_uint8),
        ("support_leading_dot_numbers", ctypes.c_uint8),
        ("support_triple_dot", ctypes.c_uint8),
        ("support_block_comments", ctypes.c_uint8),
        ("ignore_empty_lines", ctypes.c_uint8),
        ("ignore_newlines", ctypes.c_uint8),
        ("save_comments", ctypes.c_uint8),
        ("add_error", ctypes.c_uint8),
    ]


class GramKeywordEntryC(ctypes.Structure):
    _fields_ = [
        ("text", ctypes.c_char_p),
        ("length", ctypes.c_uint32),
        ("keyword_id", ctypes.c_uint32),
        ("group_offset", ctypes.c_uint32),
        ("group_count", ctypes.c_uint32),
    ]


class GramGroupEntryC(ctypes.Structure):
    _fields_ = [
        ("name", ctypes.c_char_p),
        ("length", ctypes.c_uint32),
        ("group_id", ctypes.c_uint32),
        ("keyword_offset", ctypes.c_uint32),
        ("keyword_count", ctypes.c_uint32),
    ]


class GramSymbolEntryC(ctypes.Structure):
    _fields_ = [
        ("text", ctypes.c_char_p),
        ("length", ctypes.c_uint32),
        ("token_kind", ctypes.c_uint32),
        ("codepoint_length", ctypes.c_uint32),
    ]


class GramMultilineEntryC(ctypes.Structure):
    _fields_ = [
        ("opening", ctypes.c_char_p),
        ("opening_length", ctypes.c_uint32),
        ("opening_codepoints", ctypes.c_uint32),
        ("closing", ctypes.c_char_p),
        ("closing_length", ctypes.c_uint32),
        ("closing_codepoints", ctypes.c_uint32),
        ("token_kind", ctypes.c_uint32),
        ("decode_escapes", ctypes.c_uint8),
        ("is_block_comment", ctypes.c_uint8),
    ]


class GramLexerTablesC(ctypes.Structure):
    _fields_ = [
        ("keywords", ctypes.POINTER(GramKeywordEntryC)),
        ("keyword_count", ctypes.c_uint32),
        ("groups", ctypes.POINTER(GramGroupEntryC)),
        ("group_count", ctypes.c_uint32),
        ("group_memberships", ctypes.POINTER(ctypes.c_uint32)),
        ("group_membership_count", ctypes.c_uint32),
        ("symbols", ctypes.POINTER(GramSymbolEntryC)),
        ("symbol_count", ctypes.c_uint32),
        ("multiline", ctypes.POINTER(GramMultilineEntryC)),
        ("multiline_count", ctypes.c_uint32),
        ("line_comment", ctypes.c_char_p),
        ("line_comment_length", ctypes.c_uint32),
        ("block_comment_open", ctypes.c_char_p),
        ("block_comment_open_length", ctypes.c_uint32),
        ("block_comment_close", ctypes.c_char_p),
        ("block_comment_close_length", ctypes.c_uint32),
        ("bool_true", ctypes.c_char_p),
        ("bool_true_length", ctypes.c_uint32),
        ("bool_false", ctypes.c_char_p),
        ("bool_false_length", ctypes.c_uint32),
        ("null_literal", ctypes.c_char_p),
        ("null_literal_length", ctypes.c_uint32),
    ]


class GramLexerC(ctypes.Structure):
    _fields_ = [
        ("source", ctypes.c_char_p),
        ("length", ctypes.c_uint32),
        ("position", ctypes.c_uint32),
        ("line", ctypes.c_uint32),
        ("column", ctypes.c_uint32),
        ("config", GramLexerConfigC),
        ("tables", ctypes.POINTER(GramLexerTablesC)),
        ("diagnostics", GramDiagSinkC),
        ("user_context", ctypes.c_void_p),
        ("line_start", ctypes.c_uint32),
        ("line_end", ctypes.c_uint32),
        ("next_line_start", ctypes.c_uint32),
        ("total_lines", ctypes.c_uint32),
        ("has_current_line", ctypes.c_uint8),
        ("line_indent_processed", ctypes.c_uint8),
        ("line_newline_pending", ctypes.c_uint8),
        ("eof_emitted", ctypes.c_uint8),
        ("halted", ctypes.c_uint8),
        ("state_checked", ctypes.c_uint8),
        ("indents", ctypes.c_uint32 * 256),
        ("indent_depth", ctypes.c_uint32),
        ("pending_dedents", ctypes.c_uint32),
        ("pending_dedent_line", ctypes.c_uint32),
        ("pending_dedent_col", ctypes.c_uint32),
        ("pending_dedent_offset", ctypes.c_uint32),
    ]


_LIB_CACHE: ctypes.CDLL | None = None


def _native_root() -> Path:
    return Path(__file__).resolve().parents[3] / "native" / "gram_lexer"


def _shared_lib_name() -> str:
    if sys.platform == "win32":
        return "gram_lexer.dll"
    if sys.platform == "darwin":
        return "libgram_lexer.dylib"
    return "libgram_lexer.so"


def get_c_library(*, force_rebuild: bool = False) -> ctypes.CDLL:
    """Compile (if needed) and load the native C lexer shared library."""
    global _LIB_CACHE
    if _LIB_CACHE is not None and not force_rebuild:
        return _LIB_CACHE

    root = _native_root()
    inc_dir = root / "include"
    src_dir = root / "src"
    build_dir = root / "build"
    build_dir.mkdir(parents=True, exist_ok=True)
    lib_path = build_dir / _shared_lib_name()

    c_sources = sorted(src_dir.glob("*.c"))
    c_headers = sorted(inc_dir.glob("*.h")) + sorted(src_dir.glob("*.h"))
    if not c_sources:
        raise RuntimeError(f"C lexer sources not found in {src_dir}")

    needs_build = force_rebuild or not lib_path.exists()
    if not needs_build:
        lib_mtime = lib_path.stat().st_mtime
        for f in c_sources + c_headers:
            if f.stat().st_mtime > lib_mtime:
                needs_build = True
                break

    if needs_build:
        compiler = shutil.which("gcc") or shutil.which("clang")
        if compiler is None:
            raise RuntimeError(
                "No C compiler (gcc or clang) found in PATH to build native C lexer."
            )
        cmd = [
            compiler,
            "-std=c11",
            "-O3",
            "-shared",
            "-I",
            str(inc_dir),
            *[str(s) for s in c_sources],
            "-o",
            str(lib_path),
        ]
        if sys.platform != "win32":
            cmd.insert(3, "-fPIC")
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            raise RuntimeError(
                f"Failed to compile native C lexer:\n{proc.stderr or proc.stdout}"
            )

    lib = ctypes.CDLL(str(lib_path))

    lib.gram_diag_null_sink.argtypes = []
    lib.gram_diag_null_sink.restype = GramDiagSinkC

    lib.gram_diag_buffer_init.argtypes = [
        ctypes.POINTER(GramDiagBufferC),
        ctypes.POINTER(GramDiagnosticC),
        ctypes.c_uint32,
        ctypes.c_int,
    ]
    lib.gram_diag_buffer_init.restype = None

    lib.gram_diag_buffer_set_message_arena.argtypes = [
        ctypes.POINTER(GramDiagBufferC),
        ctypes.c_char_p,
        ctypes.c_uint32,
    ]
    lib.gram_diag_buffer_set_message_arena.restype = None

    lib.gram_diag_buffer_set_max_limit.argtypes = [
        ctypes.POINTER(GramDiagBufferC),
        ctypes.c_uint32,
    ]
    lib.gram_diag_buffer_set_max_limit.restype = None

    lib.gram_diag_buffer_set_overrides.argtypes = [
        ctypes.POINTER(GramDiagBufferC),
        ctypes.POINTER(GramDiagSeverityOverrideC),
        ctypes.c_uint32,
    ]
    lib.gram_diag_buffer_set_overrides.restype = None

    lib.gram_diag_buffer_set_user_sink.argtypes = [
        ctypes.POINTER(GramDiagBufferC),
        GramDiagSinkC,
    ]
    lib.gram_diag_buffer_set_user_sink.restype = None

    lib.gram_diag_buffer_as_sink.argtypes = [ctypes.POINTER(GramDiagBufferC)]
    lib.gram_diag_buffer_as_sink.restype = GramDiagSinkC

    lib.gram_lexer_default_config.argtypes = []
    lib.gram_lexer_default_config.restype = GramLexerConfigC

    lib.gram_lexer_init.argtypes = [
        ctypes.POINTER(GramLexerC),
        ctypes.c_char_p,
        ctypes.c_uint32,
        ctypes.POINTER(GramLexerConfigC),
        ctypes.POINTER(GramLexerTablesC),
        GramDiagSinkC,
        ctypes.c_void_p,
    ]
    lib.gram_lexer_init.restype = None

    lib.gram_lexer_reset.argtypes = [
        ctypes.POINTER(GramLexerC),
        ctypes.c_char_p,
        ctypes.c_uint32,
    ]
    lib.gram_lexer_reset.restype = None

    lib.gram_lexer_next.argtypes = [
        ctypes.POINTER(GramLexerC),
        ctypes.POINTER(GramTokenC),
    ]
    lib.gram_lexer_next.restype = ctypes.c_int

    lib.gram_lexer_scan_all.argtypes = [
        ctypes.POINTER(GramLexerC),
        ctypes.c_char_p,
        ctypes.c_uint32,
    ]
    lib.gram_lexer_scan_all.restype = ctypes.c_uint32

    lib.gram_lexer_decode_string.argtypes = [
        ctypes.POINTER(GramLexerC),
        ctypes.POINTER(GramTokenC),
        ctypes.c_char_p,
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_uint32),
        ctypes.POINTER(ctypes.c_uint32),
    ]
    lib.gram_lexer_decode_string.restype = ctypes.c_int

    _LIB_CACHE = lib
    return lib


class _MarshaledTables:
    """Holds ctypes arrays and byte buffers alive during a C lexing run."""

    def __init__(self, lexer: "Lexer") -> None:
        self._keepalive: list[Any] = []
        self.custom_token_map: dict[int, Token | str] = {}
        self.tables = GramLexerTablesC()

        # 1. Keywords
        if lexer.session is not None:
            kw_names = list(lexer.session.keywords.keys())
        else:
            from gram.core.lexer import words

            kw_names = list(words.MAP_KEYWORDS.keys())

        kw_array_type = GramKeywordEntryC * max(1, len(kw_names))
        kw_array = kw_array_type()
        for idx, name in enumerate(kw_names):
            b = name.encode("utf-8")
            self._keepalive.append(b)
            kw_array[idx].text = b
            kw_array[idx].length = len(b)
            kw_array[idx].keyword_id = idx
            kw_array[idx].group_offset = 0
            kw_array[idx].group_count = 0
        self._keepalive.append(kw_array)
        self.tables.keywords = ctypes.cast(kw_array, ctypes.POINTER(GramKeywordEntryC))
        self.tables.keyword_count = len(kw_names)

        # 2. Symbols in maximal-munch order
        sym_map = lexer.get_symbols()
        sorted_syms = lexer.sorted_symbols()
        sym_array_type = GramSymbolEntryC * max(1, len(sorted_syms))
        sym_array = sym_array_type()
        custom_idx = 0

        for idx, sym_str in enumerate(sorted_syms):
            b = sym_str.encode("utf-8")
            self._keepalive.append(b)
            target = sym_map[sym_str]
            if isinstance(target, Token):
                kind_id = int(target.value)
            else:
                kind_id = GRAM_TOKEN_CUSTOM_BASE + custom_idx
                self.custom_token_map[kind_id] = target
                custom_idx += 1
            sym_array[idx].text = b
            sym_array[idx].length = len(b)
            sym_array[idx].token_kind = kind_id
            sym_array[idx].codepoint_length = len(sym_str)

        self._keepalive.append(sym_array)
        self.tables.symbols = ctypes.cast(sym_array, ctypes.POINTER(GramSymbolEntryC))
        self.tables.symbol_count = len(sorted_syms)

        # 3. Multiline entries (sorted by descending length of opening delimiter)
        ml_items = sorted(lexer.multiline.items(), key=lambda kv: len(kv[0]), reverse=True)
        ml_array_type = GramMultilineEntryC * max(1, len(ml_items))
        ml_array = ml_array_type()
        support_blk = bool(lexer.get_config("LEXER_SUPPORT_BLOCK_COMMENTS", True))
        blk_tok = lexer.block_comment_token

        for idx, (opening, closing) in enumerate(ml_items):
            ob = opening.encode("utf-8")
            cb = closing.encode("utf-8")
            self._keepalive.append(ob)
            self._keepalive.append(cb)
            is_blk = bool(support_blk and blk_tok and opening == blk_tok)
            ml_array[idx].opening = ob
            ml_array[idx].opening_length = len(ob)
            ml_array[idx].opening_codepoints = len(opening)
            ml_array[idx].closing = cb
            ml_array[idx].closing_length = len(cb)
            ml_array[idx].closing_codepoints = len(closing)
            ml_array[idx].token_kind = int(Token.COMMENT.value if is_blk else Token.STRING.value)
            ml_array[idx].decode_escapes = 0 if is_blk else 1
            ml_array[idx].is_block_comment = 1 if is_blk else 0

        self._keepalive.append(ml_array)
        self.tables.multiline = ctypes.cast(ml_array, ctypes.POINTER(GramMultilineEntryC))
        self.tables.multiline_count = len(ml_items)

        # 4. Comment and literal markers
        if isinstance(lexer.comment_token, Token):
            line_comm = sym_map.get(lexer.comment_token, "#")
            if not isinstance(line_comm, str):
                line_comm = "#"
        elif isinstance(lexer.comment_token, str):
            line_comm = lexer.comment_token
        else:
            line_comm = "#"

        lc_b = line_comm.encode("utf-8")
        self._keepalive.append(lc_b)
        self.tables.line_comment = lc_b
        self.tables.line_comment_length = len(lc_b)

        if support_blk and isinstance(blk_tok, str) and blk_tok:
            bco_b = blk_tok.encode("utf-8")
            bcc_b = b"*/"
            self._keepalive.extend([bco_b, bcc_b])
            self.tables.block_comment_open = bco_b
            self.tables.block_comment_open_length = len(bco_b)
            self.tables.block_comment_close = bcc_b
            self.tables.block_comment_close_length = len(bcc_b)

        bt = lexer.get_config("TOKEN_BOOL_TRUE", "true")
        bf = lexer.get_config("TOKEN_BOOL_FALSE", "false")
        nl = lexer.get_config("TOKEN_NULL", "null")

        bt_b = bt.encode("utf-8") if isinstance(bt, str) and bt else b""
        bf_b = bf.encode("utf-8") if isinstance(bf, str) and bf else b""
        nl_b = nl.encode("utf-8") if isinstance(nl, str) and nl else b""
        self._keepalive.extend([bt_b, bf_b, nl_b])

        self.tables.bool_true = bt_b
        self.tables.bool_true_length = len(bt_b)
        self.tables.bool_false = bf_b
        self.tables.bool_false_length = len(bf_b)
        self.tables.null_literal = nl_b
        self.tables.null_literal_length = len(nl_b)


def build_c_config(lexer: "Lexer") -> GramLexerConfigC:
    """Build a `GramLexerConfigC` from `lexer`'s active configuration."""
    lib = get_c_library()
    cfg = lib.gram_lexer_default_config()

    style = lexer.get_config("LEXER_INDENT_STYLE", "spaces")
    if style == "tabs":
        cfg.indentation_mode = GRAM_INDENT_TABS
    elif style == "mixed":
        cfg.indentation_mode = GRAM_INDENT_MIXED
    else:
        cfg.indentation_mode = GRAM_INDENT_SPACES

    try:
        tab_width = int(lexer.get_config("LEXER_TAB_WIDTH", 4))
    except (TypeError, ValueError):
        tab_width = 4
    cfg.tab_width = max(1, tab_width)

    cfg.add_info = 1 if lexer.get_config("LEXER_ADD_INFO", True) else 0
    cfg.support_triple_strings = 1 if lexer.get_config("LEXER_SUPPORT_DOCSTRINGS", True) else 0
    cfg.support_prefixed_strings = (
        1 if lexer.get_config("LEXER_SUPPORT_PREFIXED_STRINGS", True) else 0
    )
    cfg.support_indent = 1 if lexer.get_config("SUPPORT_INDENT", True) else 0
    cfg.error_policy = GRAM_ERROR_POLICY_RECOVER
    cfg.support_leading_dot_numbers = (
        1 if lexer.get_config("LEXER_SUPPORT_LEADING_DOT_NUMBERS", True) else 0
    )
    cfg.support_triple_dot = 1 if lexer.get_config("SUPPORT_TRIPLE_DOT", True) else 0
    cfg.support_block_comments = (
        1 if lexer.get_config("LEXER_SUPPORT_BLOCK_COMMENTS", True) else 0
    )
    cfg.ignore_empty_lines = 1 if lexer.get_config("LEXER_IGNORE_EMPTY_LINES", True) else 0
    cfg.ignore_newlines = 1 if lexer.get_config("LEXER_IGNORE_NEWLINES", True) else 0
    cfg.save_comments = 1 if lexer.get_config("LEXER_SAVE_COMMENTS", True) else 0
    cfg.add_error = 1 if lexer.get_config("LEXER_ADD_ERROR", True) else 0
    return cfg


def _decode_c_string_payload(
    lib: ctypes.CDLL,
    c_lexer: GramLexerC,
    c_tok: GramTokenC,
    src_bytes: bytes,
) -> str:
    """Decode a string or multiline token payload using `gram_lexer_decode_string`."""
    if (c_tok.flags & (GRAM_TOKEN_FLAG_HAS_ESCAPES | GRAM_TOKEN_FLAG_MULTILINE)) == 0:
        return src_bytes[
            c_tok.content_start : c_tok.content_start + c_tok.content_length
        ].decode("utf-8", errors="surrogatepass")

    req_len = ctypes.c_uint32(0)
    req_cp = ctypes.c_uint32(0)
    lib.gram_lexer_decode_string(
        ctypes.byref(c_lexer),
        ctypes.byref(c_tok),
        None,
        0,
        ctypes.byref(req_len),
        ctypes.byref(req_cp),
    )
    if req_len.value == 0:
        return ""
    buf = ctypes.create_string_buffer(req_len.value)
    lib.gram_lexer_decode_string(
        ctypes.byref(c_lexer),
        ctypes.byref(c_tok),
        buf,
        req_len.value,
        ctypes.byref(req_len),
        ctypes.byref(req_cp),
    )
    return buf.raw[: req_len.value].decode("utf-8", errors="surrogatepass")


def process_with_c_backend(lexer: "Lexer") -> list[TokenType]:
    """
    Execute lexical analysis for `lexer` using the native C runtime and return
    the resulting `list[TokenType]`, maintaining full parity with `Lexer.process()`.
    """
    lib = get_c_library()
    marshaled = _MarshaledTables(lexer)
    cfg = build_c_config(lexer)

    # Reconstruct exact source text from lexer.source lines (each line terminated by \n)
    source_text = "".join(f"{line}\n" for line in lexer.source)
    src_bytes = source_text.encode("utf-8")

    pending_diags: list[tuple[int, int, int, int, int]] = []

    @GramDiagnosticSinkCFunc
    def _on_diag(_ctx: int, diag_ptr: Any) -> None:
        d = diag_ptr.contents
        pending_diags.append((int(d.code), int(d.start), int(d.end), int(d.line), int(d.column)))

    sink = GramDiagSinkC(context=None, emit=_on_diag)
    c_lexer = GramLexerC()
    lib.gram_lexer_init(
        ctypes.byref(c_lexer),
        src_bytes,
        len(src_bytes),
        ctypes.byref(cfg),
        ctypes.byref(marshaled.tables),
        sink,
        None,
    )

    def _flush_pending_diags() -> None:
        while pending_diags:
            code_id, s_byte, e_byte, d_line, d_col = pending_diags.pop(0)
            snippet = src_bytes[s_byte:e_byte].decode("utf-8", errors="replace")
            if code_id == GRAM_DIAG_CODE_EMPTY_KEYWORDS:
                lexer.fail(
                    "No se han registrado palabras clave en el sistema léxico.",
                    errors.LEXER_EMPTY_KEYWORDS,
                    "Registre al menos una palabra clave con `insert_keyword()` antes de ejecutar el Lexer.",
                )
            elif code_id == GRAM_DIAG_CODE_INDENTATION_MISMATCH:
                lexer.fail(
                    f"Indentación inválida en línea {d_line}: columna {d_col}",
                    errors.LEXER_INDENTATION_MISMATCH,
                    "El nivel de indentación actual no concuerda con ningún bloque anterior.",
                )
            elif code_id == GRAM_DIAG_CODE_UNCLOSED_STRING:
                lexer.report_error(
                    errors.LexerError(
                        "UnclosedStringLiteral",
                        errors.LEXER_UNCLOSED_STRING,
                        f"Cadena sin cerrar en línea {d_line}, columna {d_col}.",
                        "Verifique el delimitador de cierre de la cadena.",
                    )
                )
            elif code_id == GRAM_DIAG_CODE_INVALID_NUMBER:
                lexer.report_error(
                    errors.LexerError(
                        "MalformedNumericLiteral",
                        errors.LEXER_INVALID_NUMBER,
                        f"Literal numérico inválido ({snippet!r}) en línea {d_line}, columna {d_col}.",
                        "Verifique la base, el exponente y los sufijos del literal.",
                    )
                )
            else:
                lexer.report_error(
                    errors.LexerError(
                        "UnexpectedCharacter",
                        errors.LEXER_UNEXPECTED_CHARACTER,
                        f"Carácter o símbolo desconocido {snippet!r} en línea {d_line}, columna {d_col}.",
                        f"El analizador léxico no reconoce el símbolo {snippet!r} en el catálogo MAP_SYMBOLS.",
                    )
                )

    tokens_list: list[TokenType] = []
    c_tok = GramTokenC()
    save_comments = bool(cfg.save_comments)

    while True:
        status = lib.gram_lexer_next(ctypes.byref(c_lexer), ctypes.byref(c_tok))
        _flush_pending_diags()

        kind = int(c_tok.kind)
        line_0 = max(0, int(c_tok.line) - 1)
        col_0 = int(c_tok.column)
        flags_pub = TokenFlags(int(c_tok.flags) & GRAM_TOKEN_PUBLIC_FLAGS_MASK)

        if kind == Token.EOF.value:
            tokens_list.append(TokenType(Token.EOF, None, line_0, col_0))
            break

        if kind == Token.NEWLINE.value:
            tokens_list.append(TokenType(Token.NEWLINE, None, line_0, col_0))
            continue

        if kind == Token.EMPTY_LINE.value:
            tokens_list.append(TokenType(Token.EMPTY_LINE, None, line_0, col_0))
            continue

        if kind == Token.NULL.value:
            tokens_list.append(TokenType(Token.NULL, None, line_0, col_0))
            continue

        if kind == Token.BOOL.value:
            val = bool(c_tok.flags & GRAM_TOKEN_FLAG_BOOL_TRUE)
            tokens_list.append(TokenType(Token.BOOL, val, line_0, col_0))
            continue

        if kind == Token.INDENT.value:
            tokens_list.append(
                TokenType(Token.INDENT, int(c_tok.content_length), line_0, col_0)
            )
            continue

        if kind == Token.DEDENT.value:
            tokens_list.append(
                TokenType(Token.DEDENT, int(c_tok.content_length), line_0, col_0)
            )
            continue

        if kind == Token.COMMENT.value:
            if save_comments:
                if c_tok.flags & GRAM_TOKEN_FLAG_MULTILINE:
                    c_val = _decode_c_string_payload(lib, c_lexer, c_tok, src_bytes)
                else:
                    c_val = src_bytes[
                        c_tok.content_start : c_tok.content_start + c_tok.content_length
                    ].decode("utf-8", errors="replace")
                lexer.comments.append(TokenType(Token.COMMENT, c_val, line_0, col_0))
            continue

        if kind == Token.STRING.value:
            s_val = _decode_c_string_payload(lib, c_lexer, c_tok, src_bytes)
            prefix_str = (
                src_bytes[
                    c_tok.prefix_start : c_tok.prefix_start + c_tok.prefix_length
                ].decode("utf-8")
                if c_tok.prefix_length > 0
                else ""
            )
            tokens_list.append(
                TokenType(
                    Token.STRING,
                    s_val,
                    line_0,
                    col_0,
                    description=prefix_str,
                    flags=flags_pub,
                )
            )
            continue

        if kind == Token.NUMBER.value:
            raw_s = src_bytes[c_tok.start : c_tok.start + c_tok.length].decode("utf-8")
            if c_tok.flags & GRAM_TOKEN_FLAG_NUMERIC_SUFF:
                n_val: int | str = raw_s
            else:
                n_val = int(raw_s.replace("_", ""), 0)
            tokens_list.append(TokenType(Token.NUMBER, n_val, line_0, col_0))
            continue

        if kind == Token.DECIMAL.value:
            raw_s = src_bytes[c_tok.start : c_tok.start + c_tok.length].decode("utf-8")
            if c_tok.flags & GRAM_TOKEN_FLAG_NUMERIC_SUFF:
                d_val: float | str = raw_s
            elif raw_s.startswith(("0x", "0X")):
                d_val = float.fromhex(raw_s.replace("_", ""))
            else:
                d_val = float(raw_s.replace("_", ""))
            tokens_list.append(TokenType(Token.DECIMAL, d_val, line_0, col_0))
            continue

        if kind == Token.ERROR.value:
            if (
                c_tok.flags & (GRAM_TOKEN_FLAG_HAS_ESCAPES | GRAM_TOKEN_FLAG_MULTILINE)
            ) or c_tok.content_start > c_tok.start:
                err_val = _decode_c_string_payload(lib, c_lexer, c_tok, src_bytes)
            else:
                err_val = src_bytes[
                    c_tok.content_start : c_tok.content_start + c_tok.content_length
                ].decode("utf-8", errors="replace")

            err_tok = TokenType(Token.ERROR, err_val, line_0, col_0)
            if c_tok.flags & GRAM_TOKEN_FLAG_BLOCK_COMMENT:
                if save_comments:
                    lexer.comments.append(err_tok)
            else:
                tokens_list.append(err_tok)
            if status == GRAM_LEXER_FATAL:
                break
            continue

        raw_lexeme = src_bytes[c_tok.start : c_tok.start + c_tok.length].decode("utf-8")
        if kind >= GRAM_TOKEN_CUSTOM_BASE:
            tok_type = marshaled.custom_token_map.get(kind, Token.UNKNOWN)
        else:
            tok_type = Token(kind)
        tokens_list.append(TokenType(tok_type, raw_lexeme, line_0, col_0))

        if status in (GRAM_LEXER_EOF, GRAM_LEXER_FATAL):
            break

    lexer.line = max(0, int(c_lexer.line) - 1)
    lexer.col = int(c_lexer.column)
    return tokens_list


__all__ = [
    "GramDiagBufferC",
    "GramDiagSeverityOverrideC",
    "GramDiagSinkC",
    "GramDiagnosticC",
    "GramDiagnosticSinkCFunc",
    "GramLexerC",
    "GramLexerConfigC",
    "GramLexerTablesC",
    "GramTokenC",
    "build_c_config",
    "get_c_library",
    "process_with_c_backend",
]
