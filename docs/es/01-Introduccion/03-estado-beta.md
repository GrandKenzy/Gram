# Estado Beta (`v2.0.0b2`)

> Esta página conserva el historial del ciclo Beta anterior a `2.1.0`. Gram `2.1.0` es la versión estable actual.

> [!IMPORTANT]
> **Gram `2.0.0b2` se encuentra actualmente en fase Beta.**
> Si bien los motores centrales de análisis léxico, análisis sintáctico, checkpoints, sesiones y diagnósticos son utilizados activamente en proyectos reales (como lenguajes de dominio específico y motores de scripting personalizados) y están respaldados por una suite de 179 pruebas unitarias y de estrés, aún pueden ocurrir ajustes menores de API antes de la versión final estable `2.0.0`.

---

## 1. Matriz de Madurez de Subsistemas

La siguiente tabla refleja el estado real de implementación de cada subsistema en la versión `2.0.0b2`:

| Subsistema | Módulo | Estado | Notas |
| :--- | :--- | :--- | :--- |
| **Lexer y Flujo de Tokens** | `gram.core.lexer` | **Beta (Núcleo Estable)** | Soporte completo para números (hex, bin, oct, flotantes, notación científica), cadenas y literales multilínea, símbolos personalizados, tracking opcional de `INDENT`/`DEDENT`, `Keyword` y `WordGroup`. |
| **Parser y Checkpoints** | `gram.core.parser` | **Beta (Núcleo Estable)** | Puntos de control transaccionales con `Checkpoint` cubriendo `pos`, `vpos`, `bracket_depth`, `storage`, `tk_tags` y sustituciones en sitio (`replace_token_at`). |
| **Combinadores Sintácticos** | `gram.core.combinators` | **Beta (Núcleo Estable)** | Los combinadores disponibles y los parsers de expresiones Pratt (`ArithmeticExpr`, `ConditionalExpr`, `DualExpr`) están implementados y verificados con tests. |
| **AST y RayTracing** | `gram.core.ast` | **Beta (Núcleo Estable)** | Soporte para modos de traza `"off"`, `"basic"` y `"detailed"` (`Trace`, `TraceRecord`, `backtracks`, `furthest`) y ponderación de fallos por posición de cursor. |
| **Sesiones de Lenguaje** | `gram.sessions` | **Beta (Núcleo Estable)** | Toma instantáneas y conmuta en memoria `MAP_KEYWORDS`, `WordGroupManager`, `MAP_SYMBOLS` y `gram.config` para soportar múltiples lenguajes en un mismo proceso. |
| **Diagnósticos y Errores** | `gram.utilities`, `gram.errors` | **Beta (Núcleo Estable)** | Catálogo formal de errores OSGDC en 5 dimensiones, `StackError`, telemetría jerárquica con `StackInfo` e interceptores de fallos (`ErrorAction`). |
| **Tooling VSIX y LSP** | `gram.vsix` | **Beta (Experimental)** | Extracción de esquemas (`VSIXAnalyzer`), previsualización ANSI TrueColor (`ASTColorResolver`), generador de extensiones VS Code (`VSIXGenerator`), empaquetador `.vsix` (`pack_vsix`, `up`) y servidor LSP stdio (`gram.vsix.lsp.server`). Continúa en desarrollo activo. |
| **Helper de Alto Nivel `process()`** | `gram.core.process` | **Incompleto (Stub)** | `gram.process()` actualmente inicializa `Lexer` y `Parser` sin culminar la ejecución ni retornar el AST. No debe usarse en `2.0.0b2`; utiliza `Lexer` + `Parser` (o `Session.tokenize()` + `Session.parse()`) directamente. |

---

## 2. Puntos Clave de Comportamiento en `2.0.0b2`

1. **`config.ERROR_EXIT_ON_ERROR` está activo por defecto (`True`):**
   Fuera de contextos especulativos (`safe_mode()` / `failure_context()`), cualquier error sintáctico o léxico no controlado imprime el recuadro formal OSGDC y finaliza el proceso con `sys.exit(1)`.
   - Si estás integrando Gram dentro de un runner de pruebas, un REPL o un compilador que captura excepciones de Python o inspecciona `parser._errors`, establece `config.ERROR_EXIT_ON_ERROR = False` o envuelve la ejecución en `with Diagnostics.hook_errors(...):` retornando `ErrorAction.SUPPRESS_RAISE` o `ErrorAction.OMIT`.
2. **Fijar versiones en entornos de producción:**
   Dado que la rama `main` recibe actualizaciones continuas de la serie `2.0.0b*`, los proyectos que requieran reproducibilidad estricta deben fijar la dependencia a un tag de Git inmutable (por ejemplo `tag = "v2.0.0b2"` en `vnma.toml` o `git checkout v2.0.0b2`).
