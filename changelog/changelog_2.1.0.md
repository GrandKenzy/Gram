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

## Runtime nativo C y DiagnosticsLite

- Runtime léxico nativo C11 independiente (`native/gram_lexer/`), reentrante y con cero asignaciones dinámicas por token, operando sobre spans en memoria del buffer UTF-8 original.
- Subsistema de diagnósticos desacoplado `DiagnosticsLite` (`gram_diagnostics_lite.h`, `diagnostics_lite.c`), sin objetos ni herencia, con soporte para sinks nulos, callbacks de usuario, buffers externos con arena para mensajes, límite máximo de diagnósticos, severidades personalizables y políticas `recover`, `stop_on_error` y `stop_on_fatal`.
- Soporte léxico completo alineado al 100% con Python: identificadores y palabras clave, grupos semánticos, máxima coincidencia de símbolos (*maximal munch*), números decimales, flotantes, binarios, octales y hexadecimales (incluyendo `0x...p...` y punto inicial), cadenas con prefijos (`L`, `u`, `U`, `u8`) y escapes `\uXXXX`, docstrings multilínea, comentarios de línea y bloque (`/* ... */`), e indentación configurable (`spaces`, `tabs`, `mixed`).
- Exportador determinista desde `Session` (`tools/export_lexer_tables.py`) que genera tablas C estáticas (`gram_lexer_config.h`, `gram_lexer_keywords.c`, `gram_lexer_groups.c`, `gram_lexer_symbols.c`, `gram_lexer_codes.h`) y manifiesto JSON con hash SHA-256 y versionado ABI 1.0.
- Adaptador opcional en Python mediante `Lexer(source, backend="python" | "c")`, manteniendo `backend="python"` como valor predeterminado sin fallback silencioso ante fallos en C.
- Comparador diferencial [`tools/compare_lexers.py`](file:///c:/Users/Kentucky/Desktop/Gram/tools/compare_lexers.py), suite de pruebas diferenciales y contratos con fixtures dorados (`tests/test_lexer_differential.py`, `tests/fixtures/lexer/golden_cases.json`) y suite de benchmarks de rendimiento y memoria (`benchmarks/lexer_python_vs_c.py`).
