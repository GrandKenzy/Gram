# Estado de la Versión y Estabilidad (`v3.0.0`)

> **Versión Actual:** `3.0.0` (Versión Estable para Producción)

Gram `3.0.0` es la versión activa y estable de Gram Framework. Todos los subsistemas centrales (análisis léxico, combinadores transaccionales con backtracking, motores de expresiones Pratt, construcción del Árbol de Sintaxis Abstracta, sesiones de lenguaje aisladas y el compilador nativo AOT en C con IR binario) se encuentran implementados, documentados y verificados mediante una suite automatizada de **300 pruebas unitarias, diferenciales y de fuzzing**.

---

## 1. Matriz de Madurez de Subsistemas

La tabla siguiente refleja el estado de implementación y estabilidad de cada subsistema en Gram `3.0.0`:

| Subsistema | Módulo | Estado | Notas |
| :--- | :--- | :--- | :--- |
| **Lexer y Flujo de Tokens** | `gram.core.lexer` | **Estable** | Números decimales, hex, binarios, octales, flotantes y notación científica; cadenas con prefijos (`u8`, `L`) y docstrings multilínea; operadores configurables con maximal munch; seguimiento de indentación (`spaces`, `tabs`, `mixed`); y palabras clave/grupos. Soporte de backend dual (`python` o `c`). |
| **Parser y Checkpoints** | `gram.core.parser` | **Estable** | Puntos de guardado transaccionales (`Checkpoint`) con guardado y restauración de cursor `pos`, cursor virtual `vpos`, profundidad de corchetes `bracket_depth`, almacenamiento `storage`, etiquetas de tokens `tk_tags`, reemplazos en sitio y callbacks de hooks. |
| **Combinadores Sintácticos** | `gram.core.combinators` | **Estable** | 32 combinadores nativos con firmas formales `CombinatorKind`. Coincidencia, secuencia, alternativa ordenada, repeticiones, delimitadores, expresiones Pratt (`ArithmeticExpr`, `ConditionalExpr`, `DualExpr`), `SameLine`, `Until` y `CaptureRaw`. |
| **AST y RayTracing** | `gram.core.ast` | **Estable** | Jerarquía declarativa `RuleItem` con transparencia `nodeable`, generación de nodos tipados (`ASTRef`, `ArrayNode`, `RawNode`, terminales) y telemetría diagnóstica `RayTracing` (`"off"`, `"basic"`, `"detailed"`). |
| **Sesiones de Lenguaje** | `gram.sessions` | **Estable** | Arquitectura `Session` aislada que gestiona catálogos léxicos, instancias de parser, configuración diagnóstica, exportación de tablas y compilación AOT sin contaminar el estado global del proceso. |
| **Diagnósticos y Errores** | `gram.utilities`, `gram.errors` | **Estable** | Códigos de error estructurados, registro de snapshots, límite de memoria en pila (`StackLimit`) y ganchos de diagnóstico (`Diagnostics.hook_errors` con `ErrorAction.SUPPRESS_RAISE` / `ErrorAction.OMIT`). |
| **Lexer C Nativo y DiagnosticsLite** | `native/gram_lexer/` | **Estable** | Runtime léxico C11 reentrante sin asignaciones dinámicas por token, motor desacoplado `DiagnosticsLite`, exportador de tablas estáticas y verificación diferencial. |
| **Parser C Nativo e IR Binario (GIR)** | `gram.core.parser.c_generator` | **Estable** | Compilador AOT de parser en C11 con despacho predictivo `switch`, arena contigua `GramAstArena` con undo log, generación de expresiones Pratt en C, serialización binaria relocalizable GIR 1.0 y driver unificado. |
| **Tooling VSIX y LSP** | `gram.vsix` | **Estable** | Indexación de esquemas (`VSIXAnalyzer`), previsualizaciones de color ANSI (`ASTColorResolver`), empaquetado de extensiones (`pack_vsix`, `up`) y servidor de lenguaje JSON-RPC por stdio (`LSPServer`). |

---

## 2. Garantías de Comportamiento Centrales

1. **Cero Dependencias Externas en Runtime:**
   El runtime en Python de Gram solo requiere la biblioteca estándar de Python 3.12+. El runtime C generado requiere C11 estándar y compila con cualquier compilador C compatible (`gcc`, `clang`, `msvc`).
2. **Invariantes Sintácticos Deterministas:**
   - Rollback transaccional garantizado: cualquier intento fallido en `Alt`, `Opt`, `Until`, `CaptureRaw` o expresiones Pratt revierte por completo los cambios de cursor, etiquetas, storage y asignaciones en la arena AST.
   - Contrato de entrypoint: la raíz de la gramática se define mediante un `RuleItem` cuyo `entrypoint` es un `Alt` compuesto de ramas `Ref`.
3. **Contrato Cerrado de Compilación AOT:**
   El compilador de parser en C valida estrictamente cada combinador del grafo de reglas contra `COMPILABLE_COMBINATOR_KINDS`. Las construcciones no compilables (como callbacks arbitrarios en Python o combinadores no soportados) se rechazan de inmediato al exportar, previniendo éxitos sintácticos falsos en código nativo.
