"""
Punto de Entrada CLI para SJSON (`python -m sjson`).
===================================================
Uso:
    python -m sjson compile archivo.sjson [-o destino.json] [--indent 2]
    python -m sjson parse archivo.sjson
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sjson import compile, compile_file, parse


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sjson",
        description="Compilador SJSON (Super JSON con variables, cálculos, comentarios '//' y extend)",
    )
    subparsers = parser.add_subparsers(dest="command", help="Comando a ejecutar")

    # compile
    p_compile = subparsers.add_parser("compile", help="Compila un archivo .sjson a JSON estándar")
    p_compile.add_argument("file", help="Ruta al archivo .sjson de origen")
    p_compile.add_argument("-o", "--output", default=None, help="Ruta de destino del archivo .json")
    p_compile.add_argument("--indent", type=int, default=4, help="Nivel de indentación en espacios (defecto: 4)")

    # parse / print
    p_parse = subparsers.add_parser("parse", help="Compila y muestra el resultado en stdout")
    p_parse.add_argument("file", help="Ruta al archivo .sjson de origen")
    p_parse.add_argument("--indent", type=int, default=4, help="Nivel de indentación en espacios (defecto: 4)")

    args = parser.parse_args(argv)

    if not args.command:
        # Si se pasó un archivo directamente como argumento posicional
        if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
            target_file = Path(sys.argv[1]).resolve()
            if target_file.is_file():
                try:
                    res_path = compile_file(target_file)
                    print(f"[OK] SJSON compilado exitosamente:")
                    print(f"     Origen:  {target_file}")
                    print(f"     Destino: {res_path}")
                    return 0
                except Exception as exc:
                    print(f"[ERROR SJSON] {exc}")
                    return 1

        parser.print_help()
        return 0

    if args.command == "compile":
        try:
            in_file = Path(args.file).resolve()
            out_file = Path(args.output).resolve() if args.output else None
            res_path = compile_file(in_file, output_file=out_file, indent=args.indent)
            print(f"[OK] Archivo compilado a JSON estándar: {res_path}")
            return 0
        except Exception as exc:
            print(f"[ERROR SJSON] {exc}")
            return 1

    elif args.command == "parse":
        try:
            in_file = Path(args.file).resolve()
            source = in_file.read_text(encoding="utf-8-sig")
            compiled_json = compile(source, base_dir=in_file.parent, indent=args.indent)
            print(compiled_json)
            return 0
        except Exception as exc:
            print(f"[ERROR SJSON] {exc}")
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
