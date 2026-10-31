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
