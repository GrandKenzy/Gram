# Compilador AOT de Parser en C

> **Módulo:** `gram.core.parser.c_generator`  
> **Estado:** Estable (Versión `2.1.0`)

El compilador Ahead-Of-Time (AOT) de Gram analiza la gramática de una `Session` a partir de su regla raíz `entrypoint`, calcula conjuntos estáticos de lookahead y genera archivos C11 autónomos y descendentes recursivos para el parser y el AST (`gram_parser.h`, `gram_parser.c`, `gram_ast.h`, `gram_ast.c`).

---

## 1. El Contrato Cerrado de Compilación

Gram impone un contrato semántico estricto para garantizar que cada gramática prototipada y verificada en Python se comporte de manera exactamente idéntica al compilarse a código C nativo.

### Verificación de Compilabilidad
Durante el recorrido del grafo de reglas, cada combinador es validado contra `COMPILABLE_COMBINATOR_KINDS` (`gram.core.combinators.kinds`):
- Los combinadores declarativos (`MatchToken`, `MatchKeyword`, `MatchGroup`, `MatchSeqSymbol`, `Literal`, `Seq`, `Alt`, `Opt`, `Many`, `Some`, `Until`, `CaptureRaw`, `Enclosed`, `Separator`, `SameLine`, expresiones Pratt) se compilan directamente a ramas optimizadas en C.
- Los combinadores no compilables (como `Convert`, funciones lambda arbitrarias de Python o clases externas no anotadas) son rechazados inmediatamente en tiempo de exportación con `GrammarCompilerError("NonCompilableCombinator")`.
- Los objetivos de `Ref` deben ser subclases válidas de `RuleItem` o instancias de `Combinator`; de lo contrario, se genera `GrammarCompilerError("InvalidRefTarget")`.
- Expresiones regulares dinámicas en `MatchSeqSymbol` lanzan `GrammarCompilerError("DynamicRegexInSymbolUnsupported")`.

---

## 2. Despacho Predictivo de Alternativas (`switch`)

En los parsers PEG estándar, evaluar alternativas (`Alt`) requiere un retroceso lineal secuencial en cada una de las ramas.

El generador C de Gram realiza un análisis estático de `first_set` (primer conjunto) sobre todas las ramas de cada `Alt`:
1. **Partición por Tipo de Token:** Aquellas ramas cuyos primeros tokens son disjuntos se despachan mediante un único `switch (tok->kind)` en C.
2. **Partición Secundaria por Carácter Inicial:** Cuando múltiples ramas comienzan con `GRAM_TOKEN_KEYWORD`, el generador emite un `switch (source[tok->start])` secundario anidado que inspecciona el primer carácter de la palabra clave (ej. `'f'` para `fn`, `'l'` para `let`).
3. **Respaldo con Backtracking Conservador:** Si los conjuntos de primer token se solapan o existe una rama opaca, el generador recurre a pruebas ordenadas PEG únicamente para ese subconjunto, conservando la semántica de la gramática y eliminando hasta el 90% de evaluaciones de ramas redundantes.

---

## 3. Arena de AST Contigua con Rollback Transaccional

El parser generado en C construye los nodos del AST dentro de una arena contigua preasignada (`GramAstArena`), evitando asignaciones individuales en el heap:

```c
typedef struct GramAstNode {
    uint16_t kind;          /* Tipo de nodo (GRAM_AST_RULE_*, GRAM_AST_RAW, etc.) */
    uint16_t flags;         /* Banderas de clasificación */
    uint32_t symbol_id;     /* Identificador en la tabla de cadenas */
    uint32_t token_start;   /* Índice del primer token en el búfer de tokens */
    uint32_t token_count;   /* Cantidad de tokens cubiertos por el nodo */
    uint32_t first_child;   /* Índice del primer hijo en la arena */
    uint32_t next_sibling;  /* Índice del siguiente hermano en la arena */
    uint32_t last_child;    /* Índice del hijo añadido más recientemente */
} GramAstNode;
```

### Undo Log Transaccional (`GramAstUndo`)
El retroceso en un árbol requiere deshacer enlaces hijos añadidos a nodos supervivientes.
- **`gram_parser_save(p)`:** Guarda un checkpoint en $O(1)$ que contiene el cursor actual, la cantidad de nodos en la arena y la posición del undo log.
- **`gram_parser_restore(p, cp)`:** Ejecuta una reversión en $O(k)$ sobre las $k$ mutaciones de enlaces realizadas durante el intento especulativo, restaurando los punteros originales y reduciendo `arena->count`.
- **Seguridad de Memoria:** Si `gram_ast_arena_alloc()` falla por falta de memoria, el parser activa `arena->has_error` y desenrolla limpiamente, evitando árboles corruptos.

---

## 4. Motores de Expresiones Pratt en C

Los combinadores de expresiones Pratt (`DualExpr`, `ArithmeticExpr`, `ConditionalExpr`) compilan a funciones descendentes recursivas dedicadas (`gram_parse_expr_*`):
- Los poderes de unión (*binding powers*) de los operadores se precalculan como tablas estáticas.
- Los operadores prefijos e infijos se resuelven mediante comparaciones directas de tokens.
- Se soportan de manera nativa los paréntesis de agrupación y la precedencia de `refs_before_grouping`.
- Los nodos unarios y binarios se emiten como `GRAM_AST_EXPR_UNARY` y `GRAM_AST_EXPR_BINARY`.

---

## 5. Fingerprinting de Gramática (`grammar_id`)

El manifiesto y la salida GIR incrustan una huella digital FNV-1a de 64 bits (`grammar_id`):
- Se calcula a partir del orden topológico de las reglas, la estructura combinatoria de cada regla, los binding powers de las expresiones Pratt y el catálogo léxico completo de la sesión (palabras clave, grupos, símbolos y hash de tablas exportadas).
- Modificar el cuerpo de una regla o añadir una palabra clave en la sesión altera `grammar_id`, impidiendo que analizadores posteriores consuman binarios GIR desactualizados.
