# Runtime Nativo en C y Herramientas Ahead-Of-Time (AOT)

> **Módulos:** `native/gram_lexer/`, `gram.core.parser.c_generator`, `gram.core.parser.c_driver`  
> **Estándar:** C11 (`-std=c11`, cero dependencias externas)  
> **Estado:** Estable (Versión `3.0.0`)

Gram proporciona una arquitectura de compilación dual completa:
1. **Motor de Prototipado en Python:** Diseño flexible e interactivo de gramáticas con telemetría rica, raytracing y validaciones dinámicas.
2. **Pipeline de Compilación AOT a C11 Nativo:** Parsers autónomos, sin copias innecesarias y de alto rendimiento, con despacho predictivo, arenas de AST contiguas, representación intermedia binaria relocalizable (**GIR 1.0**) y ejecutables de línea de comandos independientes.

---

## Visión General de la Arquitectura

```
Definición de Session (Keywords, Grupos, Símbolos, Reglas)
             │
             ├──► tools/export_lexer_tables.py ──► Tablas Léxicas C Estáticas
             │                                     (gram_lexer_keywords.c, etc.)
             │
             └──► Session.export_c_parser()    ──► Unidades Autónomas en C11:
                                                   ├── gram_ast.h / gram_ast.c
                                                   ├── gram_parser.h / gram_parser.c
                                                   ├── gram_ir.h / gram_ir.c
                                                   ├── gram_driver.h / gram_driver.c
                                                   └── gram_cli.c (opcional)
```

---

## Guías del Subsistema

| Guía | Resumen |
| :--- | :--- |
| **[01. Lexer C y DiagnosticsLite](./01-c-lexer-y-diagnostics-lite.md)** | Scanner léxico C11 reentrante, cero asignaciones por token, desacoplamiento de DiagnosticsLite y generación de tablas. |
| **[02. Compilador AOT de Parser C](./02-compilador-aot-parser-c.md)** | Generación AOT de parsers, optimización predictiva por switch, motores de expresiones Pratt y contratos de combinadores compilables. |
| **[03. Gram Binary IR (GIR 1.0)](./03-gir-ir-binario.md)** | Formato binario zero-copy y relocalizable con encabezado de 72 bytes, nodos densos de 40 bytes, deduplicación de cadenas e intervalos de bytes. |
| **[04. Driver Unificado y CLI](./04-driver-unificado-y-cli.md)** | Drivers de análisis sintáctico en memoria y archivos, formateo de errores y herramientas autónomas de línea de comandos (`compile`, `check`, `ast`, `ir`). |

---

## Resumen de Rendimiento

A lo largo del pipeline completo de extremo a extremo (Apertura de archivo $\to$ Lexer $\to$ Parser Pratt $\to$ Asignación en Arena AST), el frontend nativo C11 AOT ofrece:
- **Aceleración de ~565x** frente al motor puro de Python (`trace="off"` con telemetría desactivada).
- **Aceleración de ~1,542x a ~2,400x** frente al runtime predeterminado de Python (`trace="basic"`).
- Latencia de análisis en microsegundos (~940 µs para gramáticas estructuradas de 9 KB / 540 líneas).
- Reproducible de forma multiplataforma mediante [`benchmarks/parser_python_vs_c.py`](../../benchmarks/parser_python_vs_c.py).
