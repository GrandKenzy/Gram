"""
Ejecutable de Demostración de CExample (Parser de C con Gram Framework).
========================================================================
Analiza sintácticamente un archivo de código fuente en C (.c), construye su
árbol de sintaxis abstracta (AST) con Gram y extrae la tabla de símbolos.

Uso:
    python examples/CExample/main.py [ruta/al/archivo.c]
"""
from __future__ import annotations

import sys
from pathlib import Path

# Asegurar disponibilidad del paquete gram y del módulo examples
_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from examples.CExample.c_parser import CParser


def main() -> None:
    default_sample = Path(__file__).parent / "sample.c"
    target_path = Path(sys.argv[1]) if len(sys.argv) > 1 else default_sample

    print("=" * 70)
    print("  Gram Framework - CExample: Motor Mínimo de Parsing de Lenguaje C")
    print("=" * 70)
    print(f"Archivo objetivo: {target_path.resolve()}\n")

    if not target_path.exists():
        print(f"[ERROR] El archivo '{target_path}' no existe.")
        sys.exit(1)

    try:
        parser = CParser()
        ast = parser.parse_file(target_path)
        symbols = parser.extract_symbols(ast)

        # 1. Resumen de Directivas y Símbolos
        print("-" * 70)
        print("  1. RESUMEN DE SÍMBOLOS EXTRAÍDOS")
        print("-" * 70)

        includes = symbols.get("includes", [])
        if includes:
            print("Directivas #include:")
            for inc in includes:
                print(f"  * #include {inc}")
        else:
            print("Directivas #include: (ninguna)")

        variables = symbols.get("variables", [])
        print(f"\nVariables Globales ({len(variables)}):")
        if variables:
            for v in variables:
                print(f"  * Línea {v['line']:2d}: {v['type']} {v['name']}")
        else:
            print("  (ninguna)")

        functions = symbols.get("functions", [])
        print(f"\nFunciones ({len(functions)}):")
        if functions:
            for f in functions:
                kind = "Definición" if f["is_definition"] else "Prototipo"
                print(f"  * Línea {f['line']:2d}: [{kind:10s}] {f['return_type']} {f['name']}()")
        else:
            print("  (ninguna)")

        # 2. Representación Jerárquica del AST
        print("\n" + "-" * 70)
        print("  2. ÁRBOL DE SINTAXIS ABSTRACTA (AST)")
        print("-" * 70)
        tree_view = parser.format_tree(ast, ascii_only=True)
        print(tree_view)

        # 3. Métricas del Análisis
        print("\n" + "-" * 70)
        print("  3. MÉTRICAS DEL ANÁLISIS")
        print("-" * 70)
        print(f"Total declaraciones raíz analizadas: {symbols.get('total_top_level_declarations', 0)}")
        print(f"Distribución de sentencias: {symbols.get('statements_by_type', {})}")
        print("\n[OK] Análisis sintáctico completado con éxito con Gram Framework.\n")

    except Exception as exc:
        print(f"\n[ERROR] Ocurrió una excepción durante el parsing: {exc}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
