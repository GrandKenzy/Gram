"""
Deterministic C Lexer Table Exporter (`tools/export_lexer_tables.py`).
======================================================================
Exports a Gram `Session` (keywords, word groups, symbols, multiline delimiters,
lexical configuration, and diagnostic codes) into standalone, deterministic C
translation units and a JSON manifest with a SHA-256 content hash.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from gram import config as default_config, errors
from gram.core.lexer.multiline import get_multline
from gram.core.lexer.tokens import Token
from gram.sessions import Session

ABI_MAJOR = 1
ABI_MINOR = 1
ABI_VERSION = f"{ABI_MAJOR}.{ABI_MINOR}"
CUSTOM_TOKEN_BASE = 1000

_INDENT_MODE_MAP: dict[str, tuple[int, str]] = {
    "spaces": (0, "GRAM_INDENT_SPACES"),
    "tabs": (1, "GRAM_INDENT_TABS"),
    "mixed": (2, "GRAM_INDENT_MIXED"),
}


def c_escape_utf8(text: str) -> tuple[str, int, int]:
    """
    Encode `text` as a C string literal with deterministic octal byte escapes
    for non-ASCII UTF-8 bytes, returning `(c_literal, utf8_byte_len, codepoint_len)`.
    """
    raw = text.encode("utf-8")
    parts: list[str] = ['"']
    for b in raw:
        if b == 0x22:  # '"'
            parts.append('\\"')
        elif b == 0x5C:  # '\\'
            parts.append("\\\\")
        elif b == 0x0A:
            parts.append("\\n")
        elif b == 0x0D:
            parts.append("\\r")
        elif b == 0x09:
            parts.append("\\t")
        elif 0x20 <= b <= 0x7E:
            parts.append(chr(b))
        else:
            # 3-digit octal escape avoids C hex-escape greedy continuation
            parts.append(f"\\{b:03o}")
    parts.append('"')
    return "".join(parts), len(raw), len(text)


def _validate_and_normalize_session(session: Session) -> dict[str, Any]:
    """Validate a `Session` for C export and return a canonical normalized dictionary."""
    cfg = session.config

    indent_style = cfg.get(
        "LEXER_INDENT_STYLE",
        getattr(default_config, "LEXER_INDENT_STYLE", "spaces"),
    )
    if not isinstance(indent_style, str) or indent_style not in _INDENT_MODE_MAP:
        raise ValueError(
            f"Unsupported LEXER_INDENT_STYLE={indent_style!r}; "
            f"expected one of {sorted(_INDENT_MODE_MAP)}."
        )

    tab_width = cfg.get(
        "LEXER_TAB_WIDTH",
        getattr(default_config, "LEXER_TAB_WIDTH", 4),
    )
    if isinstance(tab_width, bool) or not isinstance(tab_width, int) or tab_width < 1:
        raise ValueError(
            f"Unsupported LEXER_TAB_WIDTH={tab_width!r}; expected an integer >= 1."
        )

    comment_token = cfg.get(
        "LEXER_COMMENT_TOKEN",
        getattr(default_config, "LEXER_COMMENT_TOKEN", "#"),
    )
    if not isinstance(comment_token, str) or not comment_token:
        raise ValueError(
            f"Unsupported LEXER_COMMENT_TOKEN={comment_token!r}; expected a non-empty string."
        )

    block_comment_open = cfg.get(
        "LEXER_BLOCK_COMMENT_TOKEN",
        getattr(default_config, "LEXER_BLOCK_COMMENT_TOKEN", "/*"),
    )
    if block_comment_open is not None and (
        not isinstance(block_comment_open, str) or not block_comment_open
    ):
        raise ValueError(
            f"Unsupported LEXER_BLOCK_COMMENT_TOKEN={block_comment_open!r}."
        )

    ident_underscores = cfg.get(
        "LEXER_IDENT_UNDERSCORES",
        getattr(default_config, "LEXER_IDENT_UNDERSCORES", -1),
    )
    if (
        isinstance(ident_underscores, bool)
        or not isinstance(ident_underscores, int)
        or ident_underscores < -2
        or ident_underscores > 2147483647
    ):
        raise ValueError(
            f"Unsupported LEXER_IDENT_UNDERSCORES={ident_underscores!r}; "
            f"must be -1, -2, or an integer between 0 and 2147483647."
        )

    # 1. Extract and validate keywords
    seen_keywords: set[str] = set()
    raw_keywords = list(session.keywords.values())
    raw_keywords.sort(key=lambda kw: kw.name.encode("utf-8"))

    keywords_data: list[dict[str, Any]] = []
    for idx, kw in enumerate(raw_keywords):
        if not kw.name or not isinstance(kw.name, str):
            raise ValueError(f"Invalid empty keyword at index {idx}.")
        if kw.name in seen_keywords:
            raise ValueError(f"Duplicate keyword detected during export: {kw.name!r}.")
        seen_keywords.add(kw.name)
        keywords_data.append(
            {
                "id": idx,
                "name": kw.name,
                "description": kw.description or "",
            }
        )

    kw_id_by_name = {item["name"]: item["id"] for item in keywords_data}

    # 2. Extract and validate word groups
    seen_groups: set[str] = set()
    raw_groups_dict = getattr(session, "groups", None)
    if raw_groups_dict is None:
        raw_groups_dict = getattr(session, "word_groups", {})
    raw_groups = list(raw_groups_dict.values())
    raw_groups.sort(key=lambda grp: grp.name.encode("utf-8"))

    groups_data: list[dict[str, Any]] = []
    kw_to_groups: dict[int, list[int]] = {item["id"]: [] for item in keywords_data}

    for g_idx, grp in enumerate(raw_groups):
        if not grp.name or not isinstance(grp.name, str):
            raise ValueError(f"Invalid empty word group at index {g_idx}.")
        if grp.name in seen_groups:
            raise ValueError(f"Duplicate word group detected: {grp.name!r}.")
        seen_groups.add(grp.name)

        grp_items = getattr(grp, "values", None)
        if grp_items is None:
            grp_items = getattr(grp, "words", [])
        member_names = sorted(
            (w.name if hasattr(w, "name") else str(w) for w in grp_items),
            key=lambda s: s.encode("utf-8"),
        )
        member_ids: list[int] = []
        seen_members: set[str] = set()
        for m_name in member_names:
            if m_name in seen_members:
                raise ValueError(
                    f"Duplicate keyword {m_name!r} inside word group {grp.name!r}."
                )
            seen_members.add(m_name)
            if m_name not in kw_id_by_name:
                raise ValueError(
                    f"Word group {grp.name!r} references unregistered keyword {m_name!r}."
                )
            kid = kw_id_by_name[m_name]
            member_ids.append(kid)
            kw_to_groups[kid].append(g_idx)

        groups_data.append(
            {
                "id": g_idx,
                "name": grp.name,
                "keyword_ids": member_ids,
                "keywords": member_names,
            }
        )

    for item in keywords_data:
        item["group_ids"] = sorted(kw_to_groups[item["id"]])

    # 3. Extract and validate symbols (string keys only, sorted by descending length)
    string_symbols: dict[str, Token | str] = {}
    for k, v in session.symbols.items():
        if isinstance(k, str):
            if not k:
                raise ValueError("Empty symbol string is not allowed in symbol table.")
            if k in string_symbols and string_symbols[k] != v:
                raise ValueError(f"Conflicting symbol mapping for {k!r}.")
            string_symbols[k] = v

    if comment_token not in string_symbols:
        raise ValueError(
            f"LEXER_COMMENT_TOKEN={comment_token!r} is not registered in session.symbols."
        )

    # Sort by descending character length, then descending UTF-8 byte length, then UTF-8 bytes
    sorted_sym_texts = sorted(
        string_symbols.keys(),
        key=lambda s: (-len(s), -len(s.encode("utf-8")), s.encode("utf-8")),
    )

    custom_offset = 0
    symbols_data: list[dict[str, Any]] = []
    for sym_text in sorted_sym_texts:
        target = string_symbols[sym_text]
        if isinstance(target, Token):
            token_id = int(target.value)
            token_name = f"GRAM_TOKEN_{target.name}"
            is_custom = False
        else:
            token_id = CUSTOM_TOKEN_BASE + custom_offset
            token_name = f"GRAM_TOKEN_CUSTOM_{custom_offset}"
            custom_offset += 1
            is_custom = True

        symbols_data.append(
            {
                "text": sym_text,
                "token_id": token_id,
                "token_c_name": token_name,
                "is_custom": is_custom,
            }
        )

    # 4. Multiline delimiters
    support_docstrings = bool(
        cfg.get(
            "LEXER_SUPPORT_DOCSTRINGS",
            getattr(default_config, "LEXER_SUPPORT_DOCSTRINGS", True),
        )
    )
    support_block_comments = bool(
        cfg.get(
            "LEXER_SUPPORT_BLOCK_COMMENTS",
            getattr(default_config, "LEXER_SUPPORT_BLOCK_COMMENTS", True),
        )
    )
    ml_map = dict(get_multline())
    if not support_docstrings:
        ml_map.pop('"""', None)
        ml_map.pop("'''", None)
    if support_block_comments and block_comment_open:
        ml_map[block_comment_open] = "*/"

    sorted_ml = sorted(
        ml_map.items(),
        key=lambda kv: (-len(kv[0]), -len(kv[0].encode("utf-8")), kv[0].encode("utf-8")),
    )
    multiline_data: list[dict[str, Any]] = []
    for opening, closing in sorted_ml:
        is_blk = bool(support_block_comments and block_comment_open and opening == block_comment_open)
        multiline_data.append(
            {
                "opening": opening,
                "closing": closing,
                "token_c_name": "GRAM_TOKEN_COMMENT" if is_blk else "GRAM_TOKEN_STRING",
                "decode_escapes": 0 if is_blk else 1,
                "is_block_comment": 1 if is_blk else 0,
            }
        )

    # 5. Config & literals
    bool_true = cfg.get("TOKEN_BOOL_TRUE", getattr(default_config, "TOKEN_BOOL_TRUE", "true"))
    bool_false = cfg.get("TOKEN_BOOL_FALSE", getattr(default_config, "TOKEN_BOOL_FALSE", "false"))
    null_lit = cfg.get("TOKEN_NULL", getattr(default_config, "TOKEN_NULL", "null"))

    error_exit = bool(
        cfg.get("ERROR_EXIT_ON_ERROR", getattr(default_config, "ERROR_EXIT_ON_ERROR", True))
    )

    config_data = {
        "tab_width": int(tab_width),
        "indentation_mode": indent_style,
        "indentation_mode_c": _INDENT_MODE_MAP[indent_style][1],
        "add_info": int(bool(cfg.get("LEXER_ADD_INFO", getattr(default_config, "LEXER_ADD_INFO", True)))),
        "support_triple_strings": int(support_docstrings),
        "support_prefixed_strings": int(
            bool(cfg.get("LEXER_SUPPORT_PREFIXED_STRINGS", getattr(default_config, "LEXER_SUPPORT_PREFIXED_STRINGS", True)))
        ),
        "support_indent": int(bool(cfg.get("SUPPORT_INDENT", getattr(default_config, "SUPPORT_INDENT", True)))),
        "error_policy_c": "GRAM_ERROR_POLICY_STOP_ON_ERROR" if error_exit else "GRAM_ERROR_POLICY_RECOVER",
        "support_leading_dot_numbers": int(
            bool(cfg.get("LEXER_SUPPORT_LEADING_DOT_NUMBERS", getattr(default_config, "LEXER_SUPPORT_LEADING_DOT_NUMBERS", True)))
        ),
        "support_triple_dot": int(
            bool(cfg.get("SUPPORT_TRIPLE_DOT", getattr(default_config, "SUPPORT_TRIPLE_DOT", True)))
        ),
        "support_block_comments": int(support_block_comments),
        "ignore_empty_lines": int(
            bool(cfg.get("LEXER_IGNORE_EMPTY_LINES", getattr(default_config, "LEXER_IGNORE_EMPTY_LINES", True)))
        ),
        "ignore_newlines": int(
            bool(cfg.get("LEXER_IGNORE_NEWLINES", getattr(default_config, "LEXER_IGNORE_NEWLINES", True)))
        ),
        "save_comments": int(
            bool(cfg.get("LEXER_SAVE_COMMENTS", getattr(default_config, "LEXER_SAVE_COMMENTS", True)))
        ),
        "add_error": int(bool(cfg.get("LEXER_ADD_ERROR", getattr(default_config, "LEXER_ADD_ERROR", True)))),
        "ident_underscores": int(ident_underscores),
        "line_comment": comment_token,
        "block_comment_open": block_comment_open or "",
        "block_comment_close": "*/" if block_comment_open else "",
        "bool_true": bool_true if isinstance(bool_true, str) else "",
        "bool_false": bool_false if isinstance(bool_false, str) else "",
        "null_literal": null_lit if isinstance(null_lit, str) else "",
    }

    diag_codes = [
        {"c_enum": "GRAM_DIAG_CODE_EMPTY_KEYWORDS", "id": 1, "osgdc": errors.LEXER_EMPTY_KEYWORDS.code_string, "name": errors.LEXER_EMPTY_KEYWORDS.name},
        {"c_enum": "GRAM_DIAG_CODE_KEYWORD_ALREADY_EXISTS", "id": 2, "osgdc": errors.LEXER_KEYWORD_ALREADY_EXISTS.code_string, "name": errors.LEXER_KEYWORD_ALREADY_EXISTS.name},
        {"c_enum": "GRAM_DIAG_CODE_KEYWORD_NOT_FOUND", "id": 3, "osgdc": errors.LEXER_KEYWORD_NOT_FOUND.code_string, "name": errors.LEXER_KEYWORD_NOT_FOUND.name},
        {"c_enum": "GRAM_DIAG_CODE_GROUP_NOT_FOUND", "id": 4, "osgdc": errors.LEXER_GROUP_NOT_FOUND.code_string, "name": errors.LEXER_GROUP_NOT_FOUND.name},
        {"c_enum": "GRAM_DIAG_CODE_KEYWORD_INVALID_NAME", "id": 5, "osgdc": errors.LEXER_KEYWORD_INVALID_NAME.code_string, "name": errors.LEXER_KEYWORD_INVALID_NAME.name},
        {"c_enum": "GRAM_DIAG_CODE_UNEXPECTED_CHARACTER", "id": 6, "osgdc": errors.LEXER_UNEXPECTED_CHARACTER.code_string, "name": errors.LEXER_UNEXPECTED_CHARACTER.name},
        {"c_enum": "GRAM_DIAG_CODE_UNCLOSED_STRING", "id": 7, "osgdc": errors.LEXER_UNCLOSED_STRING.code_string, "name": errors.LEXER_UNCLOSED_STRING.name},
        {"c_enum": "GRAM_DIAG_CODE_INDENTATION_MISMATCH", "id": 8, "osgdc": errors.LEXER_INDENTATION_MISMATCH.code_string, "name": errors.LEXER_INDENTATION_MISMATCH.name},
        {"c_enum": "GRAM_DIAG_CODE_INVALID_NUMBER", "id": 9, "osgdc": errors.LEXER_INVALID_NUMBER.code_string, "name": errors.LEXER_INVALID_NUMBER.name},
        {"c_enum": "GRAM_DIAG_CODE_WORDGROUP_ALREADY_EXISTS", "id": 10, "osgdc": errors.LEXER_WORDGROUP_ALREADY_EXISTS.code_string, "name": errors.LEXER_WORDGROUP_ALREADY_EXISTS.name},
        {"c_enum": "GRAM_DIAG_CODE_WORDGROUP_NOT_FOUND", "id": 11, "osgdc": errors.LEXER_WORDGROUP_NOT_FOUND.code_string, "name": errors.LEXER_WORDGROUP_NOT_FOUND.name},
        {"c_enum": "GRAM_DIAG_CODE_WORDGROUP_KEYWORD_NOT_REGISTERED", "id": 12, "osgdc": errors.LEXER_WORDGROUP_KEYWORD_NOT_REGISTERED.code_string, "name": errors.LEXER_WORDGROUP_KEYWORD_NOT_REGISTERED.name},
        {"c_enum": "GRAM_DIAG_CODE_FILE_NOT_FOUND", "id": 13, "osgdc": errors.LEXER_FILE_NOT_FOUND.code_string, "name": errors.LEXER_FILE_NOT_FOUND.name},
        {"c_enum": "GRAM_DIAG_CODE_INVALID_UTF8", "id": 14, "osgdc": "S-11411", "name": "Gram.Lexer.InvalidUtf8"},
        {"c_enum": "GRAM_DIAG_CODE_INVALID_COMMENT_SYMBOL", "id": 15, "osgdc": "S-11411", "name": "Gram.Lexer.InvalidCommentSymbol"},
    ]

    canonical_payload = {
        "abi_version": ABI_VERSION,
        "config": config_data,
        "keywords": keywords_data,
        "groups": groups_data,
        "symbols": symbols_data,
        "multiline": multiline_data,
        "diagnostic_codes": diag_codes,
    }
    canonical_bytes = json.dumps(canonical_payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
    content_hash = hashlib.sha256(canonical_bytes).hexdigest()
    canonical_payload["content_hash"] = content_hash
    return canonical_payload


def export_session_tables(session: Session, output_dir: str | Path) -> dict[str, Any]:
    """
    Generate deterministic C lexer tables and manifest in `output_dir` from `session`.
    Returns the manifest dictionary.
    """
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    data = _validate_and_normalize_session(session)
    content_hash = data["content_hash"]
    cfg = data["config"]
    keywords = data["keywords"]
    groups = data["groups"]
    symbols = data["symbols"]
    multiline = data["multiline"]
    diag_codes = data["diagnostic_codes"]

    # 1. gram_lexer_config.h
    config_h_lines = [
        "/* Auto-generated by tools/export_lexer_tables.py. Do not edit manually. */",
        "#ifndef GRAM_LEXER_EXPORTED_CONFIG_H",
        "#define GRAM_LEXER_EXPORTED_CONFIG_H",
        "",
        '#include "gram_lexer.h"',
        '#include "gram_lexer_codes.h"',
        "",
        f"#define GRAM_EXPORTED_ABI_MAJOR {ABI_MAJOR}",
        f"#define GRAM_EXPORTED_ABI_MINOR {ABI_MINOR}",
        f'#define GRAM_EXPORTED_CONTENT_HASH "{content_hash}"',
        "",
        f"#define GRAM_EXPORTED_KEYWORD_COUNT {len(keywords)}u",
        f"#define GRAM_EXPORTED_GROUP_COUNT {len(groups)}u",
        f"#define GRAM_EXPORTED_SYMBOL_COUNT {len(symbols)}u",
        f"#define GRAM_EXPORTED_MULTILINE_COUNT {len(multiline)}u",
        f"#define GRAM_EXPORTED_CFG_IDENT_UNDERSCORES ({cfg['ident_underscores']})",
        "",
        "extern const GramKeywordEntry GRAM_EXPORTED_KEYWORDS[];",
        "extern const uint32_t GRAM_EXPORTED_GROUP_MEMBERSHIPS[];",
        "extern const uint32_t GRAM_EXPORTED_GROUP_MEMBERSHIP_COUNT;",
        "extern const GramGroupEntry GRAM_EXPORTED_GROUPS[];",
        "extern const uint32_t GRAM_EXPORTED_GROUP_KEYWORDS[];",
        "extern const GramSymbolEntry GRAM_EXPORTED_SYMBOLS[];",
        "extern const GramMultilineEntry GRAM_EXPORTED_MULTILINE[];",
        "extern const GramLexerTables GRAM_EXPORTED_TABLES;",
        "",
        "GramLexerConfig gram_exported_lexer_config(void);",
        "",
        "#endif /* GRAM_LEXER_EXPORTED_CONFIG_H */",
        "",
    ]
    (out_path / "gram_lexer_config.h").write_text("\n".join(config_h_lines), encoding="utf-8")

    # 2. gram_lexer_codes.h
    codes_h_lines = [
        "/* Auto-generated by tools/export_lexer_tables.py. Do not edit manually. */",
        "#ifndef GRAM_LEXER_EXPORTED_CODES_H",
        "#define GRAM_LEXER_EXPORTED_CODES_H",
        "",
        '#include "gram_diagnostics_lite.h"',
        '#include "gram_lexer_tokens.h"',
        "",
        "typedef struct {",
        "    uint32_t code;",
        "    const char *osgdc;",
        "    const char *name;",
        "} GramExportedDiagMetadata;",
        "",
    ]
    for sym in symbols:
        if sym["is_custom"]:
            codes_h_lines.append(f"#define {sym['token_c_name']} {sym['token_id']}u")
    codes_h_lines.extend(
        [
            "",
            f"#define GRAM_EXPORTED_DIAG_CODE_COUNT {len(diag_codes)}u",
            "",
            "static const GramExportedDiagMetadata GRAM_EXPORTED_DIAG_CODES[] = {",
        ]
    )
    for d in diag_codes:
        osgdc_lit, _, _ = c_escape_utf8(d["osgdc"])
        name_lit, _, _ = c_escape_utf8(d["name"])
        codes_h_lines.append(f"    {{ {d['c_enum']}, {osgdc_lit}, {name_lit} }},")
    codes_h_lines.extend(
        [
            "};",
            "",
            "#endif /* GRAM_LEXER_EXPORTED_CODES_H */",
            "",
        ]
    )
    (out_path / "gram_lexer_codes.h").write_text("\n".join(codes_h_lines), encoding="utf-8")

    # 3. gram_lexer_keywords.c
    flat_memberships: list[int] = []
    kw_c_lines = [
        "/* Auto-generated by tools/export_lexer_tables.py. Do not edit manually. */",
        '#include "gram_lexer_config.h"',
        "",
        "const GramKeywordEntry GRAM_EXPORTED_KEYWORDS[] = {",
    ]
    if keywords:
        for kw in keywords:
            lit, byte_len, _ = c_escape_utf8(kw["name"])
            g_offset = len(flat_memberships)
            g_ids = kw["group_ids"]
            flat_memberships.extend(g_ids)
            kw_c_lines.append(
                f"    {{ {lit}, {byte_len}u, {kw['id']}u, {g_offset}u, {len(g_ids)}u }},"
            )
    else:
        kw_c_lines.append("    { NULL, 0u, 0u, 0u, 0u }")
    kw_c_lines.append("};")
    kw_c_lines.append("")
    kw_c_lines.append("const uint32_t GRAM_EXPORTED_GROUP_MEMBERSHIPS[] = {")
    if flat_memberships:
        joined = ", ".join(f"{gid}u" for gid in flat_memberships)
        kw_c_lines.append(f"    {joined}")
    else:
        kw_c_lines.append("    0u")
    kw_c_lines.append("};")
    kw_c_lines.append(
        f"const uint32_t GRAM_EXPORTED_GROUP_MEMBERSHIP_COUNT = {len(flat_memberships)}u;"
    )
    kw_c_lines.append("")
    (out_path / "gram_lexer_keywords.c").write_text("\n".join(kw_c_lines), encoding="utf-8")

    # 4. gram_lexer_groups.c
    flat_group_kws: list[int] = []
    grp_c_lines = [
        "/* Auto-generated by tools/export_lexer_tables.py. Do not edit manually. */",
        '#include "gram_lexer_config.h"',
        "",
        "const GramGroupEntry GRAM_EXPORTED_GROUPS[] = {",
    ]
    if groups:
        for grp in groups:
            lit, byte_len, _ = c_escape_utf8(grp["name"])
            k_offset = len(flat_group_kws)
            k_ids = grp["keyword_ids"]
            flat_group_kws.extend(k_ids)
            grp_c_lines.append(
                f"    {{ {lit}, {byte_len}u, {grp['id']}u, {k_offset}u, {len(k_ids)}u }},"
            )
    else:
        grp_c_lines.append("    { NULL, 0u, 0u, 0u, 0u }")
    grp_c_lines.append("};")
    grp_c_lines.append("")
    grp_c_lines.append("const uint32_t GRAM_EXPORTED_GROUP_KEYWORDS[] = {")
    if flat_group_kws:
        joined = ", ".join(f"{kid}u" for kid in flat_group_kws)
        grp_c_lines.append(f"    {joined}")
    else:
        grp_c_lines.append("    0u")
    grp_c_lines.append("};")
    grp_c_lines.append("")
    (out_path / "gram_lexer_groups.c").write_text("\n".join(grp_c_lines), encoding="utf-8")

    # 5. gram_lexer_symbols.c
    sym_c_lines = [
        "/* Auto-generated by tools/export_lexer_tables.py. Do not edit manually. */",
        '#include "gram_lexer_config.h"',
        "",
        "const GramSymbolEntry GRAM_EXPORTED_SYMBOLS[] = {",
    ]
    if symbols:
        for sym in symbols:
            lit, byte_len, cp_len = c_escape_utf8(sym["text"])
            sym_c_lines.append(
                f"    {{ {lit}, {byte_len}u, {sym['token_c_name']}, {cp_len}u }},"
            )
    else:
        sym_c_lines.append("    { NULL, 0u, 0u, 0u }")
    sym_c_lines.append("};")
    sym_c_lines.append("")
    sym_c_lines.append("const GramMultilineEntry GRAM_EXPORTED_MULTILINE[] = {")
    if multiline:
        for ml in multiline:
            o_lit, o_bytes, o_cp = c_escape_utf8(ml["opening"])
            c_lit, c_bytes, c_cp = c_escape_utf8(ml["closing"])
            sym_c_lines.append(
                f"    {{ {o_lit}, {o_bytes}u, {o_cp}u, {c_lit}, {c_bytes}u, {c_cp}u, "
                f"{ml['token_c_name']}, {ml['decode_escapes']}u, {ml['is_block_comment']}u }},"
            )
    else:
        sym_c_lines.append("    { NULL, 0u, 0u, NULL, 0u, 0u, 0u, 0u, 0u }")
    sym_c_lines.append("};")
    sym_c_lines.append("")

    lc_lit, lc_bytes, _ = c_escape_utf8(cfg["line_comment"])
    bco_lit, bco_bytes, _ = c_escape_utf8(cfg["block_comment_open"])
    bcc_lit, bcc_bytes, _ = c_escape_utf8(cfg["block_comment_close"])
    bt_lit, bt_bytes, _ = c_escape_utf8(cfg["bool_true"])
    bf_lit, bf_bytes, _ = c_escape_utf8(cfg["bool_false"])
    nl_lit, nl_bytes, _ = c_escape_utf8(cfg["null_literal"])

    sym_c_lines.extend(
        [
            "const GramLexerTables GRAM_EXPORTED_TABLES = {",
            f"    GRAM_EXPORTED_KEYWORDS, {len(keywords)}u,",
            f"    GRAM_EXPORTED_GROUPS, {len(groups)}u,",
            f"    GRAM_EXPORTED_GROUP_MEMBERSHIPS, {len(flat_memberships)}u,",
            f"    GRAM_EXPORTED_SYMBOLS, {len(symbols)}u,",
            f"    GRAM_EXPORTED_MULTILINE, {len(multiline)}u,",
            f"    {lc_lit}, {lc_bytes}u,",
            f"    {bco_lit}, {bco_bytes}u,",
            f"    {bcc_lit}, {bcc_bytes}u,",
            f"    {bt_lit}, {bt_bytes}u,",
            f"    {bf_lit}, {bf_bytes}u,",
            f"    {nl_lit}, {nl_bytes}u",
            "};",
            "",
            "GramLexerConfig gram_exported_lexer_config(void) {",
            "    GramLexerConfig cfg = gram_lexer_default_config();",
            f"    cfg.tab_width = {cfg['tab_width']}u;",
            f"    cfg.indentation_mode = (uint8_t){cfg['indentation_mode_c']};",
            f"    cfg.add_info = {cfg['add_info']}u;",
            f"    cfg.support_triple_strings = {cfg['support_triple_strings']}u;",
            f"    cfg.support_prefixed_strings = {cfg['support_prefixed_strings']}u;",
            f"    cfg.support_indent = {cfg['support_indent']}u;",
            f"    cfg.error_policy = (uint8_t){cfg['error_policy_c']};",
            f"    cfg.support_leading_dot_numbers = {cfg['support_leading_dot_numbers']}u;",
            f"    cfg.support_triple_dot = {cfg['support_triple_dot']}u;",
            f"    cfg.support_block_comments = {cfg['support_block_comments']}u;",
            f"    cfg.ignore_empty_lines = {cfg['ignore_empty_lines']}u;",
            f"    cfg.ignore_newlines = {cfg['ignore_newlines']}u;",
            f"    cfg.save_comments = {cfg['save_comments']}u;",
            f"    cfg.add_error = {cfg['add_error']}u;",
            f"    cfg.ident_underscores = {cfg['ident_underscores']};",
            "    return cfg;",
            "}",
            "",
        ]
    )
    (out_path / "gram_lexer_symbols.c").write_text("\n".join(sym_c_lines), encoding="utf-8")

    # 6. gram_lexer_manifest.json
    manifest = {
        "abi_version": ABI_VERSION,
        "content_hash": content_hash,
        "counts": {
            "keywords": len(keywords),
            "groups": len(groups),
            "symbols": len(symbols),
            "multiline": len(multiline),
            "diagnostic_codes": len(diag_codes),
        },
        "files": [
            "gram_lexer_config.h",
            "gram_lexer_keywords.c",
            "gram_lexer_groups.c",
            "gram_lexer_symbols.c",
            "gram_lexer_codes.h",
            "gram_lexer_manifest.json",
        ],
        "config": cfg,
        "keywords": keywords,
        "groups": groups,
        "symbols": symbols,
        "multiline": multiline,
        "diagnostic_codes": diag_codes,
    }
    (out_path / "gram_lexer_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Export a Gram Session into deterministic C lexer tables."
    )
    parser.add_argument(
        "-o",
        "--output",
        default="generated",
        help="Target directory for generated C tables (default: generated).",
    )
    parser.add_argument(
        "--keyword",
        action="append",
        default=[],
        help="Register a keyword in the exported Session (may be repeated).",
    )
    args = parser.parse_args(argv)

    session = Session("c-export", "Many")
    if args.keyword:
        for kw in args.keyword:
            session.add_keyword(kw)
    elif session.keyword_count() == 0:
        for default_kw in ("def", "if", "else", "while", "return", "let", "fn"):
            session.add_keyword(default_kw)
        session.add_group("control", ["if", "else", "while", "return"])

    manifest = export_session_tables(session, args.output)
    print(
        f"Exported C lexer tables to {args.output} "
        f"(ABI {manifest['abi_version']}, sha256={manifest['content_hash'][:16]}...)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
