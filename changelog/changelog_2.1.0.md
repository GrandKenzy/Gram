# Gram `2.1.0`

## Utilería de diagnosticos

- Paquete integrado de diagnóstico con `Diagnostics`, `errors` e `info`.
- `Diagnostics` conserva su API y mejora hooks, scopes, targets y deduplicación.
- `errors` mejora la validación de códigos, el registro de errores y la escritura de snapshots.
- `info` centraliza nodos, targets y flujos de notas (`debug`, `warn`, `advice`, `error`, `fatal`).
- Logs más seguros e idempotentes, con benchmark y pruebas de regresión incluidos.
- `StackError` optimiza la deduplicación e indexación por identidad y protege su almacenamiento público contra mutaciones no controladas.
- `StackLimit` limita la memoria, permite volcado JSONL con identificadores de línea y secuencia, recuperación de registros y modo de error al alcanzar el límite.
- `ErrorCombinator` conserva la recuperación de errores usando las operaciones controladas del stack; la suite actual alcanza 228 pruebas exitosas.

## Análisis léxico y lexer

- `Session` ahora posee el catálogo y la configuración efectiva del lexer, con
  instancias predefinidas de lexer/parser y tokenización aislada por sesión.
- `add_group()` y `add_keyword()` pueden configurar directamente una sesión;
  `WordGroupManager` queda obsoleto y falla al instanciarse.
- Aislados también los símbolos del lexer y sincronizadas las mutaciones de
  sesión con los lectores legacy después de `load()`.
- Corregido el avance seguro ante dígitos Unicode y literales numéricos malformados, evitando bucles infinitos con errores suprimidos.
- Reforzada la conversión numérica: los hexadecimales con `e/E` o `f/F` se interpretan correctamente y los separadores inválidos generan `Token.ERROR` sin fragmentarse.
- Alineados `TokenType.__eq__` y `__hash__` para mantener un comportamiento consistente en conjuntos y diccionarios.
- Resueltos los pendientes léxicos: `LEXER_ADD_INFO` evita construir nodos de telemetría, `fail()` respeta la política de errores y `Session` reconstruye índices de símbolos de forma segura.
- Añadidas políticas de indentación `spaces`, `tabs` y `mixed` con `LEXER_TAB_WIDTH`, además de limpieza correcta de referencias al vaciar `WordGroup`.
- Corregidos los contratos de clasificación de booleanos, documentación de cadenas y `$len` en `TokenType.formatter()`.

## Parser y AST

- `Session.parse()` reutiliza su parser predefinido y propaga la sesión al
  `ASTAnalyzer`, aislando las flags de diagnóstico de parser y AST.
- `MatchGroup` resuelve grupos desde la sesión activa del parser en lugar de
  depender del catálogo global.
- Se preserva la API directa de `Parser` y `ASTAnalyzer`; los combinadores
  reciben la vista de sesión cuando necesitan configuración contextual.
- `Alt(audit=True)` añade perfiles de consumo, caché de planes predictivos y
  reordenamiento conservador sin mutar el orden público de alternativas.
- La auditoría predictiva usa `first_set` para omitir ramas exactas imposibles
  en el token actual, conserva barreras opacas y cae al orden compilado si no
  hay una predicción segura; se añadieron pruebas diferenciales de resultados,
  cursor y diagnósticos entre `audit=False` y `audit=True`.
- La caché predictiva detecta cambios en combinadores anidados, `entrypoint` y
  sesiones con comprobación O(1) mientras no haya mutaciones; las conversiones
  locales se resuelven dinámicamente sin reutilizar dispatch obsoleto.
- El benchmark de alternativas redujo de `0.191345 s` a `0.045692 s` la
  mediana del caso auditado con 16 ramas y 128 sentencias.
- El parser evita escaneos repetidos de indentación y trabajo vacío de hooks,
  mejorando el rendimiento observable de los modos normales.
- Las restauraciones de traza liberan snapshots temporales y las flags de
  entrypoints se restauran al finalizar el análisis.
- `trace="detailed"` registra intentos de alternativas para medir consumo,
  retrocesos y orden planificado sin añadir coste a `off` ni `basic`.
- `MatchSeqSymbol` ya relabela tokens mediante el mecanismo transaccional del
  parser, evitando mutaciones que sobrevivían a un rollback de `Alt` o `Seq`.
- `trace="detailed"` conserva instrumentación completa y deliberadamente
  pesada para diseñar parsers y lexers dedicados.
- Las expresiones usan despacho predictivo cacheado para omitir `Ref` imposibles,
  conservando el orden y la prioridad de referencias sobre paréntesis.
- `ArithmeticExpr`, `ConditionalExpr` y `DualExpr` respetan conversiones lógicas
  del parser y evitan serializar árboles recursivos completos en el camino normal.
- Las señales de control conservan sus clases compatibles y ahora exponen
  `FlowKind`; `trace="detailed"` también registra esa clasificación para
  distinguir secuencia, repetición, backtracking, commit y abort.
- Nuevo combinador nativo `SameLine` (`gram/core/combinators/same_line.py`) para
  exigir continuidad de línea entre el último token consumido y el siguiente
  elemento sintáctico, integrado con el análisis predictivo (`first_set`).
- Sistema formal de firmas semánticas `CombinatorKind` (`gram/core/combinators/kinds.py`)
  en los 32 combinadores nativos de Gram (`COMPILABLE_COMBINATOR_KINDS`,
  `is_semantic_combinator`, `is_compilable_combinator`), permitiendo distinguir
  combinadores declarativos compilables y rechazar combinadores externos o con
  callbacks arbitrarios de Python.

## Runtime nativo C y DiagnosticsLite

- Runtime léxico nativo C11 independiente (`native/gram_lexer/`), reentrante y con cero asignaciones dinámicas por token, operando sobre spans en memoria del buffer UTF-8 original.
- Subsistema de diagnósticos desacoplado `DiagnosticsLite` (`gram_diagnostics_lite.h`, `diagnostics_lite.c`), sin objetos ni herencia, con soporte para sinks nulos, callbacks de usuario, buffers externos con arena para mensajes, límite máximo de diagnósticos, severidades personalizables y políticas `recover`, `stop_on_error` y `stop_on_fatal`.
- Soporte léxico completo alineado al 100% con Python: identificadores y palabras clave, grupos semánticos, máxima coincidencia de símbolos (*maximal munch*), números decimales, flotantes, binarios, octales y hexadecimales (incluyendo `0x...p...` y punto inicial), cadenas con prefijos (`L`, `u`, `U`, `u8`) y escapes `\uXXXX`, docstrings multilínea, comentarios de línea y bloque (`/* ... */`), e indentación configurable (`spaces`, `tabs`, `mixed`).
- Exportador determinista desde `Session` (`tools/export_lexer_tables.py`) que genera tablas C estáticas (`gram_lexer_config.h`, `gram_lexer_keywords.c`, `gram_lexer_groups.c`, `gram_lexer_symbols.c`, `gram_lexer_codes.h`) y manifiesto JSON con hash SHA-256 y versionado ABI 1.0.
- Adaptador opcional en Python mediante `Lexer(source, backend="python" | "c")`, manteniendo `backend="python"` como valor predeterminado sin fallback silencioso ante fallos en C.
- Comparador diferencial [`tools/compare_lexers.py`](file:///c:/Users/Kentucky/Desktop/Gram/tools/compare_lexers.py), suite de pruebas diferenciales y contratos con fixtures dorados (`tests/test_lexer_differential.py`, `tests/fixtures/lexer/golden_cases.json`) y suite de benchmarks de rendimiento y memoria (`benchmarks/lexer_python_vs_c.py`).
- Compilador AOT de Parser y generador de AST en C11 (`gram/core/parser/c_generator.py`, `Session.export_c_parser()` y CLI `tools/export_c_parser.py`) que resuelve el grafo transitivo de reglas desde el `entrypoint` de una `Session` y emite unidades C autónomas (`gram_ast.h`, `gram_ast.c`, `gram_parser.h`, `gram_parser.c` y `gram_parser_manifest.json` con hash SHA-256).
- Arena contigua de nodos AST (`GramAstArena`) con rollback transaccional O(1) (`GramParserCheckpoint`), motores Pratt en C para `DualExpr`, `ArithmeticExpr` y `ConditionalExpr` (incluyendo operadores unarios, binarios, `refs_before_grouping` y filtrado por `first_set`), y soporte nativo para `MatchGroup`, `Enclosed`, `Separator` y `SameLine`.
- Optimización predictiva de `Alt` en C mediante tablas de salto `switch (tok->kind)` y despacho secundario por carácter inicial en palabras clave (`case GRAM_TOKEN_KEYWORD:`), preservando el orden semántico PEG y logrando aceleraciones de ~2,400x en el pipeline completo Lexer + Parser + AST en C frente a Python.
- Undo log transaccional O(1) en `GramAstArena` (`GramAstUndo`) junto con puntero `last_child` e inserción directa de hijos en reglas transparentes (`nodeable = False`), garantizando que los retrocesos (`gram_parser_restore`) desenlacen limpiamente los hijos añadidos a nodos padres supervivientes y registren el cursor más profundo alcanzado (`farthest`) para diagnósticos precisos.
- Driver unificado y File Opener en C (`gram_driver.h`, `gram_driver.c`, generados desde `gram/core/parser/c_driver.py`) con dos modos de operación:
  1. **Modo sin compilar (Source/File -> AST en memoria):** `gram_parse_source` y `gram_parse_file` ejecutan el lexer y el parser en C y devuelven `GramParseResult` con el arreglo de tokens y la arena AST lista para recorrer en memoria.
  2. **Modo compilado (Source/File -> Binary IR):** `gram_compile_source_to_ir`, `gram_compile_file_to_ir` y `gram_compile_file_to_ir_file` leen archivos directamente (omitiendo BOM UTF-8), tokenizan y parsean internamente sin exponer arreglos intermedios de tokens y emiten un buffer o archivo `.gir`.
- Formato binario relocalizable y zero-copy **Gram Binary IR (`GIR`)** (`gram_ir.h`, `gram_ir.c`) con encabezado de 72 bytes (`GramIrHeader`, fingerprint FNV-1a de la gramática y versión de formato), pool deduplicado de cadenas UTF-8 alineado a 8 bytes y tabla densa de nodos de 40 bytes (`GramIrNode`) con spans de bytes (`src_start`, `src_length`) y coordenadas de origen (`line` 1-based, `column` 0-based), validador estructural `gram_ir_view_init`, serialización en disco y dumper textual `gram_ir_dump`.
- CLI nativo autónomo opcional (`gram_cli.c`, activable con `emit_cli=True` en `Session.export_c_parser()` o `--cli` en `tools/export_c_parser.py`) con subcomandos `compile`, `check`, `ast` e `ir`.
