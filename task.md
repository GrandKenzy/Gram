# Task: C Lexer Runtime and DiagnosticsLite

## Objetivo

Crear la primera capa nativa de Gram: un lexer independiente escrito en C,
generado y configurado desde `Session`, sin utilizar todavía el parser, el AST,
los combinadores ni `Diagnostics` como runtime.

Gram seguirá siendo la fuente de verdad semántica. El código C será un runtime
pequeño, reentrante y orientado a producción, mientras que Gram generará las
tablas específicas de cada lenguaje.

## Alcance cerrado

### Incluido

- Runtime de lexer en C.
- `DiagnosticsLite` sin objetos ni herencia.
- Tokens, spans, líneas, columnas y flags.
- UTF-8.
- Identificadores y keywords.
- Word groups.
- Símbolos y operadores con máxima coincidencia.
- Números.
- Strings y escapes.
- Comentarios y espacios.
- Indentación.
- Tokens especiales, booleanos, null y tokens personalizados.
- Recuperación de errores léxicos.
- Exportación de tablas desde `Session`.
- Pruebas diferenciales Python/C.
- Benchmarks de velocidad, memoria y asignaciones.

### Fuera de alcance

- Parser.
- AST.
- Combinadores.
- `RuleItem` como runtime C.
- `RayTracing`.
- Generación de parsers.
- Conversión de tokens en nodos.
- Portar `Diagnostics`, `StackError`, `Info` o `StackInfo` completos a C.
- Cambiar el backend Python predeterminado.

No modificar ni sobrescribir documentación concurrente de otras tareas,
especialmente `docs/en/04-Lexer/` y `docs/es/04-Lexer/` si contienen cambios no
rastreados.

## Principios de diseño

1. No transpilar las utilidades Python completas a C.
2. Mantener el runtime C independiente de Python, parser y AST.
3. No usar estado global mutable.
4. No asignar memoria por token durante el escaneo normal.
5. Usar buffers y almacenamiento proporcionados por el llamador cuando sea
   posible.
6. Mantener la API Python existente sin cambios incompatibles.
7. Comparar primero semántica; optimizar después de tener paridad.
8. Los mensajes no son el contrato principal: el contrato es código, severidad,
   posición, span y recuperación.

## Fase 1: congelar el contrato léxico

Documentar y probar el comportamiento real del lexer Python antes de escribir
el runtime C.

Registrar como contrato:

- IDs y nombres de tokens.
- Valores de tokens.
- `start`, `length`, línea y columna.
- Flags.
- EOF.
- Prioridad de visitors.
- Máxima coincidencia de símbolos.
- Keywords y grupos.
- Comentarios, espacios y líneas vacías.
- Strings, prefijos y escapes.
- Números y formatos inválidos.
- Indentación (`spaces`, `tabs`, `mixed` y ancho de tab).
- Recuperación ante errores.
- Códigos y severidades existentes.

Decisión recomendada:

- offsets internos en bytes UTF-8;
- línea iniciada en 1;
- columna compatible con el lexer Python;
- tokens representados como spans sobre el buffer original;
- no copiar el texto salvo que el consumidor lo solicite.

Crear fixtures dorados con fuente, tokens normalizados y diagnósticos esperados.

## Fase 2: implementar DiagnosticsLite

Crear una API C independiente basada en estructuras simples.

```c
typedef enum {
    GRAM_DIAG_DEBUG,
    GRAM_DIAG_ADVICE,
    GRAM_DIAG_WARN,
    GRAM_DIAG_ERROR,
    GRAM_DIAG_FATAL
} GramDiagSeverity;
```

```c
typedef struct {
    uint32_t code;
    GramDiagSeverity severity;
    uint32_t start;
    uint32_t end;
    uint32_t line;
    uint32_t column;
    const char *message;
    uint32_t message_length;
} GramDiagnostic;
```

```c
typedef void (*GramDiagnosticSink)(
    void *context,
    const GramDiagnostic *diagnostic
);
```

```c
typedef struct {
    void *context;
    GramDiagnosticSink emit;
} GramDiagSink;
```

Debe soportar:

- callback del usuario;
- buffer externo de diagnósticos;
- sink nulo;
- límite máximo de diagnósticos;
- políticas `recover`, `stop_on_error` y `stop_on_fatal`;
- códigos personalizados sin herencia;
- severidades configurables por el consumidor.

El sink no debe asumir que el mensaje tiene ownership propio. Los mensajes y
spans deben permanecer válidos durante la llamada al callback.

## Fase 3: definir la API mínima del lexer

Crear tipos públicos equivalentes a los siguientes:

```c
typedef struct {
    uint32_t kind;
    uint32_t flags;
    uint32_t start;
    uint32_t length;
    uint32_t line;
    uint32_t column;
} GramToken;
```

```c
typedef struct {
    uint32_t tab_width;
    uint8_t indentation_mode;
    uint8_t add_info;
    uint8_t support_triple_strings;
    uint8_t support_prefixed_strings;
    uint8_t support_indent;
    uint8_t error_policy;
} GramLexerConfig;
```

```c
typedef struct {
    const char *source;
    uint32_t length;
    uint32_t position;
    uint32_t line;
    uint32_t column;
    GramLexerConfig config;
    const GramLexerTables *tables;
    GramDiagSink diagnostics;
    void *user_context;
} GramLexer;
```

La API mínima debe incluir:

```c
void gram_lexer_init(...);
void gram_lexer_reset(...);
int gram_lexer_next(GramLexer *, GramToken *);
```

Estados de salida:

- `GRAM_LEXER_TOKEN`;
- `GRAM_LEXER_EOF`;
- `GRAM_LEXER_ERROR`;
- `GRAM_LEXER_FATAL`.

El estado debe ser reutilizable y reentrante.

## Fase 4: exportar `Session` a tablas C

Implementar una herramienta de exportación desde una `Session` que genere:

```text
generated/
    gram_lexer_config.h
    gram_lexer_keywords.c
    gram_lexer_groups.c
    gram_lexer_symbols.c
    gram_lexer_codes.h
    gram_lexer_manifest.json
```

Las tablas deben incluir:

- keywords;
- grupos y pertenencia;
- símbolos;
- token IDs;
- configuración efectiva;
- códigos de diagnóstico;
- versión del ABI;
- hash de contenido.

Requisitos del generador:

- salida determinista;
- orden estable;
- símbolos ordenados por longitud descendente o trie equivalente;
- escape correcto de UTF-8;
- detección de duplicados y conflictos;
- rechazo explícito de configuraciones no soportadas;
- ningún estado global del proceso en el resultado generado.

## Fase 5: implementar el scanner por capas

Implementar y probar en este orden:

1. Cursor, EOF, límites y UTF-8.
2. Líneas, columnas y offsets.
3. Espacios, comentarios y líneas vacías.
4. Identificadores y keywords.
5. Word groups.
6. Símbolos con máxima coincidencia.
7. Números y formatos inválidos.
8. Strings, escapes, prefijos y triples.
9. Booleanos, null y tokens especiales.
10. Indentación y dedents múltiples.
11. Recuperación y acumulación de errores.

Cada capa debe tener fixtures positivos, negativos y de límites antes de añadir
la siguiente.

## Fase 6: pruebas diferenciales

Ejecutar el mismo origen contra Python y C y comparar:

- cantidad y orden de tokens;
- tipo y flags;
- spans;
- línea y columna;
- EOF;
- códigos de error;
- severidades;
- orden de diagnósticos;
- recuperación posterior al error.

Casos obligatorios:

- Unicode válido e inválido;
- fuente vacía;
- símbolos solapados;
- keywords y grupos;
- comentarios;
- números válidos y malformados;
- strings sin cierre;
- escapes inválidos;
- indentación mixta;
- múltiples errores en un mismo archivo;
- tokens muy largos;
- archivos grandes.

Añadir fuzzing determinista para buscar divergencias Python/C. Los mensajes
textuales se compararán solo después de estabilizar los campos estructurados.

## Fase 7: integración opcional con Python

Crear un adaptador separado después de conseguir paridad independiente:

```python
Lexer(source, backend="python")
Lexer(source, backend="c")
```

El adaptador convertirá:

- `GramToken` a `TokenType`;
- `GramDiagnostic` a `LexerError`.

El backend C debe ser explícito. No hacer fallback silencioso a Python.
La API existente de `Lexer(source).process()` continuará usando Python hasta que
exista evidencia suficiente para cambiar el valor predeterminado.

## Fase 8: benchmarks

Medir Python y C en:

- bytes por segundo;
- tokens por segundo;
- tiempo por token;
- memoria máxima;
- asignaciones;
- fuentes con y sin errores;
- Unicode;
- muchos símbolos;
- muchos keywords;
- strings grandes;
- indentación profunda;
- archivos de 1 KB, 1 MB y 100 MB.

Medir `DiagnosticsLite` con:

- sink nulo;
- callback;
- buffer externo.

No aceptar una mejora de velocidad que cambie el contrato léxico o haga crecer
la memoria sin límite.

## Fase 9: ABI, compilación y seguridad

Usar inicialmente C11 o un subconjunto compatible con C99.

Validar compilación en los toolchains soportados por el proyecto y mantener:

```c
#define GRAM_LEXER_ABI_MAJOR 1
#define GRAM_LEXER_ABI_MINOR 0
```

Revisar especialmente:

- overflow de offsets y longitudes;
- UTF-8 truncado;
- entradas sin terminador nulo;
- tokens de tamaño extremo;
- contador de líneas;
- stacks de indentación;
- límites de diagnósticos;
- ownership de buffers;
- reentrancia y uso simultáneo de varias sesiones.

## Organización propuesta

```text
native/
    gram_lexer/
        include/
            gram_lexer.h
            gram_diagnostics_lite.h
            gram_lexer_tokens.h
        src/
            lexer.c
            utf8.c
            numbers.c
            strings.c
            symbols.c
            indentation.c
            diagnostics_lite.c
        tests/

tools/
    export_lexer_tables.py
    compare_lexers.py

tests/
    test_lexer_differential.py
    fixtures/lexer/

benchmarks/
    lexer_python_vs_c.py
```

## Criterios de aceptación

- El lexer C compila y funciona sin importar parser ni AST.
- `DiagnosticsLite` no depende de objetos Python ni de memoria global mutable.
- Las tablas C se generan desde `Session` de forma determinista.
- Python y C producen tokens equivalentes en todos los fixtures soportados.
- Los códigos, spans, líneas, columnas y severidades coinciden.
- No hay asignación por token en el camino normal.
- El backend Python existente no cambia.
- El backend C no hace fallback silencioso.
- La memoria usada por diagnósticos y tokens tiene límites explícitos.
- El rendimiento y la memoria se miden antes de considerar C como backend
  predeterminado.
- No se implementa ninguna parte del parser o del AST en esta tarea.

## Primer entregable recomendado

1. Contrato léxico y fixtures dorados.
2. `gram_diagnostics_lite.h/.c` con pruebas.
3. `GramToken`, `GramLexerConfig` y API mínima.
4. Lexer C con UTF-8, identificadores, keywords, símbolos y EOF.
5. Comparación inicial Python/C.

No avanzar a números, strings o indentación hasta que esta primera comparación
sea estable.
