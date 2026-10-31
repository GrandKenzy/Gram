"""
Deterministic AOT C Parser Exporter CLI (`tools/export_c_parser.py`).
=====================================================================
Compiles and exports a Gram `Session` grammar graph and entrypoint into standalone,
deterministic C translation units (`gram_ast.*`, `gram_parser.*`, the binary IR
`gram_ir.*`, the unified file opener `gram_driver.*`, the lexer tables and a JSON
manifest with SHA-256 verification). `--cli` also emits `gram_cli.c`.
"""
from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from gram.core.parser.c_generator import (
    C_PARSER_ABI_VERSION,
    export_session_c_parser,
)
from gram.sessions import Session


def _resolve_session(spec: str) -> Session:
    """Resolve a session instance given an import path string (e.g. 'my_pkg.SESSION')."""
    if ":" in spec:
        mod_name, var_name = spec.split(":", 1)
    elif "." in spec:
        parts = spec.split(".")
        mod_name = ".".join(parts[:-1])
        var_name = parts[-1]
    else:
        raise ValueError(
            f"Invalid session specifier '{spec}'. Expected format 'module:SESSION' or 'module.SESSION'."
        )

    mod = importlib.import_module(mod_name)
    session_obj = getattr(mod, var_name, None)
    if not isinstance(session_obj, Session):
        raise TypeError(
            f"Resolved object '{spec}' is of type '{type(session_obj).__name__}', expected 'Session'."
        )
    return session_obj


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compile a Gram Session grammar into standalone C translation units."
    )
    parser.add_argument(
        "--session",
        "-s",
        required=True,
        help="Session identifier to compile, formatted as 'module:SESSION_VAR' or 'module.SESSION_VAR'.",
    )
    parser.add_argument(
        "--output",
        "-o",
        required=True,
        help="Output directory path where generated C files will be written.",
    )
    parser.add_argument(
        "--no-driver",
        action="store_true",
        help="Skip the file opener, the binary IR and the lexer tables (parser + AST only).",
    )
    parser.add_argument(
        "--cli",
        action="store_true",
        help="Also emit gram_cli.c, a standalone frontend (compile/check/ast/ir commands).",
    )

    args = parser.parse_args(argv)

    try:
        session = _resolve_session(args.session)
        out_dir = Path(args.output).resolve()
        print(f"Compiling Session '{session.name}' (mode={session.mode}) to C...")
        manifest = export_session_c_parser(
            session,
            out_dir,
            emit_driver=not args.no_driver,
            emit_cli=args.cli,
        )
        print(f"Successfully generated C Parser (ABI v{C_PARSER_ABI_VERSION}):")
        print(f"  Rules compiled: {manifest['rule_count']}")
        print(f"  Content hash:   {manifest['content_hash']}")
        if manifest.get("driver"):
            print(f"  IR format:      {manifest['ir_format']} (grammar {manifest['grammar_id']})")
        print(f"  Output path:    {out_dir}")
        for f in manifest["files"]:
            print(f"    - {f}")
        for f in manifest.get("lexer_files", ()):
            print(f"    - {f} (lexer)")
        return 0
    except Exception as ex:
        print(f"Error compiling parser: {ex}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
