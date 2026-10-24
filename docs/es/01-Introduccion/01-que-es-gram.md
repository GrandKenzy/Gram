# ¿Qué es Gram?

**Gram** (`gram`) es un framework en Python puro, sin dependencias externas en tiempo de ejecución, para análisis léxico, combinadores de análisis sintáctico y generación de Árboles de Sintaxis Abstracta (`AST`). Está concebido para construir lenguajes de dominio específico (DSLs), transpiladores, analizadores de contratos/cabeceras y frontends de compiladores.

---

## 1. Filosofía y Objetivos de Diseño

Gram está diseñado en torno a cuatro principios de ingeniería:

### A. Desacoplamiento Estricto entre Sintaxis y Semántica
En muchas herramientas para compiladores, las reglas gramaticales se mezclan con tablas de símbolos, chequeo de tipos o generación de código máquina. Gram impone una frontera limpia:
- **Responsabilidad de Gram (Frontend Sintáctico):** Escanear caracteres en tokens estructurados (`gram.core.lexer`), validar la estructura sintáctica mediante combinadores declarativos (`gram.core.combinators`), emitir diagnósticos exactos (`gram.errors`) y construir el Árbol de Sintaxis Abstracta (`gram.core.ast`).
- **Responsabilidad del Compilador Host (Semántica y Backend):** Recorrer el árbol `ASTRef` y `ASTNode` resultante para resolver ámbitos, verificar tipos, optimizar y generar el código de destino (como C, LLVM IR o bytecode).

### B. Gramáticas Declarativas en Python Puro
En lugar de depender de archivos de texto externos (`.g4`, archivos BNF) que exigen un paso de precompilación o generación de código, las gramáticas de Gram se escriben directamente en Python:
- Las reglas de producción se declaran como subclases de `RuleItem`.
- Se componen estructuras complejas mediante 28 combinadores (`Seq`, `Alt`, `Opt`, `Many`, `Some`, `Separator`, `Enclosed`, `Until`, `UntilIndent`, `Ref`, `Req`, etc.) y motores de expresiones Pratt (`ArithmeticExpr`, `ConditionalExpr`, `DualExpr`).
- A cada regla se le asigna automáticamente un identificador numérico único mediante `AutoCode` y `CodeManager`.

### C. Backtracking Transaccional y Diagnóstico del Fallo más Profundo
Los analizadores descendentes recursivos tradicionales suelen tener dificultades con ramas ambiguas: o bien una rama fallida corrompe el estado del cursor, o bien el backtracking descarta el error interno y muestra un mensaje superficial.

Gram resuelve esto con dos mecanismos nativos:
- **Puntos de Control Atómicos (`Checkpoint`):** `parser.savepoint()` y `parser.restore()` guardan y restablecen el cursor físico (`pos`), el cursor virtual de lookahead (`vpos`), la profundidad de delimitadores (`bracket_depth`), la pila de objetivos de telemetría, el almacenamiento clave-valor (`parser.storage`), las etiquetas de posición (`parser.tk_tags`) y las sustituciones en sitio (`parser.replace_token_at`).
- **Ámbitos de Fallo Ponderados (`failure_scope`):** Al evaluar ramas especulativas (`Alt`, `Opt`, `Many`, `Some`, `Separator`), Gram almacena en una fase intermedia los errores candidatos ponderados por el índice del cursor (`parser.pos`) donde ocurrieron. Si el parseo superior no alcanza `Token.EOF`, `ASTAnalyzer` promueve el error más profundo para que el programador vea la causa raíz real del error sintáctico.

### D. Aislamiento de Múltiples Frontends de Lenguaje
Un compilador frecuentemente necesita parsear más de un lenguaje en el mismo proceso (por ejemplo, parsear el lenguaje propio junto con cabeceras C o contratos externos). A través de `gram.sessions.Session`, Gram toma instantáneas y conmuta en memoria las tablas de palabras clave (`MAP_KEYWORDS`), los grupos de palabras (`WordGroup`), los símbolos de operadores (`MAP_SYMBOLS`) y las banderas de `gram.config` sin contaminación cruzada.

---

## 2. Pipeline de Procesamiento

```text
+-------------------------------------------------------------------------+
|                        Pipeline Sintáctico de Gram                      |
+-------------------------------------------------------------------------+

  Texto Fuente (str | list[str])
        |
        v
  +-----------------------------------+
  | 1. Lexer (gram.core.lexer)        |  - Escanea números, strings, símbolos,
  |    Lexer(source).process()        |    keywords, comentarios e INDENT/DEDENT
  +-----------------------------------+
        |
        |  list[TokenType]
        v
  +-----------------------------------+
  | 2. Parser (gram.core.parser)      |  - Administra cursores físicos y virtuales,
  |    Parser(tokens)                 |    checkpoints, storage y tags
  +-----------------------------------+
        |
        v
  +-----------------------------------+
  | 3. ASTAnalyzer y Visitor          |  - Evalúa la jerarquía de RuleItems,
  |    (gram.core.ast)                |    combinadores, Pratt y RayTracing
  +-----------------------------------+
        |
        |  list[ASTRef | ASTNode]
        v
  Analizador Semántico / Transpilador / Backend del Compilador Host
```

---

## 3. Mapa de Submódulos

| Submódulo | Ruta de Importación | Exportaciones Principales |
| :--- | :--- | :--- |
| **Léxico** | `from gram import lexer` | `Lexer`, `Token`, `TokenType`, `CustomToken`, `TokenStream`, `words`, `Keyword`, `WordGroup` |
| **Parser** | `from gram import parser` | `Parser`, `ParseState`, `Checkpoint`, `TokenInfo`, `Hookr` |
| **Combinadores** | `from gram import combinators` | `RuleItem`, `Ref`, `Seq`, `Alt`, `Opt`, `Many`, `Some`, `Separator`, `Enclosed`, `Until`, `UntilIndent`, `MatchToken`, `MatchKeyword`, `MatchGroup`, `MatchSymbol`, `Item`, `Literal`, `Save`, `Load`, `Peek`, `Not`, `If`, `Skip`, `Tag`, `Tokenize`, `ErrorCombinator`, `Req`, `ArithmeticExpr`, `ConditionalExpr`, `DualExpr` |
| **AST** | `from gram import ast` | `ASTAnalyzer`, `ASTState`, `Visitor`, `ASTNode`, `ASTRef`, `ArrayNode`, `ItemNode`, `LiteralNode`, `Identifier`, `LiteralNumber`, `LiteralString`, `LiteralSymbol`, `ASTKeyword`, `RayTracing`, `Trace`, `TraceRecord` |
| **Reglas** | `from gram import rules` | `AutoCode`, `SetCode`, `CodeManager`, `code_manager` |
| **Sesiones** | `from gram import sessions` | `Session` |
| **Diagnósticos y Errores** | `from gram import errors, utilities` | `Diagnostics`, `ErrorAction`, `Error`, `LexerError`, `ParserError`, `ASTError`, `GrammarError`, `SemanticError`, `StackError`, `StackInfo` |
| **Configuración** | `from gram import config` | Banderas globales de configuración para lexer, parser, AST, errores y logs (`save()`, `load()`, `reset_to_defaults()`) |
| **VSIX (Beta)** | `from gram import vsix` | `VSIXAnalyzer`, `VSIXGenerator`, `ASTColorResolver`, `TokenSelector`, `LSPServer`, `declare_info`, `pack_vsix`, `up` |
