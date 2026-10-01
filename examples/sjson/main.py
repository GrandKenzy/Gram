"""
Ejecutable de Demostración de SJSON (Super JSON con Gram Framework).
===================================================================
Compila un archivo .sjson a JSON estándar utilizando el motor Gram.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Asegurar importación de gram
_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gram.sjson import compile, compile_file


def main() -> None:
    sample_file = Path(__file__).parent / "sample.sjson"
    target = sys.argv[1] if len(sys.argv) > 1 else str(sample_file)

    print("=" * 60)
    print("Compilador SJSON (Super JSON - Gram Framework)")
    print(f"Archivo de entrada: {target}")
    print("=" * 60)

    try:
        content = Path(target).read_text(encoding="utf-8")
        compiled_json = compile(content, base_dir=Path(target).parent, indent=2)
        print("\n[OK] Documento JSON Estándar Resultante:\n")
        print(compiled_json)
    except Exception as exc:
        print(f"\n[ERROR] Fallo al compilar: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
