# Native C Runtime and Ahead-Of-Time (AOT) Tooling

> **Module:** `native/gram_lexer/`, `gram.core.parser.c_generator`, `gram.core.parser.c_driver`  
> **Standard:** C11 (`-std=c11`, zero external dependencies)  
> **Status:** Stable (Version `2.1.0`)

Gram provides a complete, dual-layer compilation architecture:
1. **Python Prototype Engine:** Flexible, interactive grammar design with rich telemetry, tracing, and dynamic validation.
2. **Native C11 AOT Compilation Pipeline:** Zero-copy, high-throughput standalone parsers with predictive dispatch, contiguous AST arenas, relocatable binary IR (GIR 1.0), and autonomous command-line frontends.

---

## Architecture Overview

```
Session Definition (Keywords, Groups, Symbols, Rules)
             │
             ├──► tools/export_lexer_tables.py ──► Static C Lexer Tables
             │                                     (gram_lexer_keywords.c, etc.)
             │
             └──► Session.export_c_parser()    ──► Standalone C11 Units:
                                                   ├── gram_ast.h / gram_ast.c
                                                   ├── gram_parser.h / gram_parser.c
                                                   ├── gram_ir.h / gram_ir.c
                                                   ├── gram_driver.h / gram_driver.c
                                                   └── gram_cli.c (optional)
```

---

## Subsystem Guides

| Guide | Summary |
| :--- | :--- |
| **[01. C Lexer & DiagnosticsLite](./01-c-lexer-and-diagnostics-lite.md)** | Reentrant C11 lexical scanner, zero allocations per token, DiagnosticsLite decoupling, and table generation. |
| **[02. AOT C Parser Compiler](./02-aot-c-parser-compiler.md)** | Ahead-Of-Time parser generation, predictive switch optimization, Pratt expression engines, and compilable combinator contracts. |
| **[03. Gram Binary IR (GIR 1.0)](./03-gir-binary-ir.md)** | Relocatable, zero-copy binary format with 72-byte header, 40-byte dense nodes, string deduplication, and byte spans. |
| **[04. Unified Driver & CLI](./04-unified-driver-and-cli.md)** | Memory and file-based parser drivers, error formatting, and standalone command-line tooling (`compile`, `check`, `ast`, `ir`). |

---

## Performance Summary

Across the full end-to-end pipeline (File Opening $\to$ Lexer $\to$ Pratt Parser $\to$ AST Arena Allocation), the native C11 AOT frontend delivers:
- **~565x speedup** compared to pure Python runtime (`trace="off"` with telemetry disabled).
- **~1,542x to ~2,400x speedup** compared to default Python runtime (`trace="basic"`).
- Microsecond parse latency (~940 µs on 9 KB / 540 lines of structured grammar).
- Fully reproducible via [`benchmarks/parser_python_vs_c.py`](../../benchmarks/parser_python_vs_c.py).
