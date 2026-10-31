# Lexer C Nativo y DiagnosticsLite

> **Ubicación:** `native/gram_lexer/`  
> **Estándar:** C11 (`-std=c11`)  
> **Estado:** Estable (Versión `3.0.0`)

El lexer en C nativo de Gram es un tokenizador reentrante y autónomo escrito en C11 estándar. Proporciona una equivalencia léxica del 100% frente al lexer de referencia en Python, operando con cero asignaciones dinámicas de memoria por token.

---

## 1. Arquitectura de Tokens sin Asignación Dinámica

Los tokens no duplican cadenas ni asignan estructuras individuales en el heap. Cada token almacena su tipo, byte offset en el código fuente, longitud en bytes, línea (base 1) y columna (base 0) directamente en el almacenamiento provisto por el llamador:

```c
typedef struct GramToken {
    uint32_t kind;      /* Identificador de tipo de token (GRAM_TOKEN_*) */
    uint32_t flags;     /* Metadatos léxicos y banderas de clasificación */
    uint32_t start;     /* Byte offset dentro del búfer UTF-8 */
    uint32_t length;    /* Longitud del token en bytes */
    uint32_t line;      /* Número de línea (base 1) */
    uint32_t column;    /* Número de columna (base 0) */
    uint32_t value;     /* Carga útil extra (ej. índice de símbolo o ID de keyword) */
} GramToken;
```

### Sintaxis Léxicas Soportadas
- **Identificadores y Palabras Clave:** Reglas de identificadores ASCII y UTF-8, con resolución en tiempo constante mediante tablas hash estáticas exportadas.
- **Números:** Decimales, flotantes, notación científica, binarios (`0b`), octales (`0o`) y hexadecimales (`0x`, incluidos flotantes hexadecimales `0x...p...`).
- **Cadenas:** Literales de comillas simples, dobles y triples (docstrings) con secuencias de escape (`\n`, `\t`, `\xHH`, `\uXXXX`, `\UXXXXXXXX`) y prefijos (`L`, `u`, `U`, `u8`).
- **Símbolos y Operadores:** Coincidencia por maximal munch (*longest match*) sobre tablas ordenadas por longitud.
- **Indentación:** Modos configurables de indentación (`spaces`, `tabs`, `mixed`) con seguimiento mediante una pila interna.

---

## 2. DiagnosticsLite Desacoplado

`DiagnosticsLite` (`gram_diagnostics_lite.h`, `diagnostics_lite.c`) es un subsistema de diagnóstico de alto rendimiento desacoplado de jerarquías de objetos pesadas o administradores de memoria:

```c
typedef enum {
    GRAM_SEV_DEBUG = 0,
    GRAM_SEV_INFO,
    GRAM_SEV_WARN,
    GRAM_SEV_ADVICE,
    GRAM_SEV_ERROR,
    GRAM_SEV_FATAL,
} GramSeverity;

typedef enum {
    GRAM_DIAG_RECOVER = 0,
    GRAM_DIAG_STOP_ON_ERROR,
    GRAM_DIAG_STOP_ON_FATAL,
} GramDiagPolicy;
```

### Receptores (*Sinks*) y Callbacks
- **Null Sink (`gram_diag_null_sink()`):** Descarta todos los mensajes de diagnóstico para ejecuciones de producción con cero sobrecarga.
- **Callback Sink (`gram_diag_callback_sink()`):** Reenvía los registros formateados a un puntero de función definido por el usuario.
- **Arena Buffer Sink:** Formatea los diagnósticos dentro de un búfer de arena preasignado externamente.

---

## 3. Exportación de Tablas Léxicas desde una Sesión

Para generar las tablas estáticas en C correspondientes a una sesión de lenguaje, use `tools/export_lexer_tables.py` o la API de Python:

```python
from gram import sessions
from tools.export_lexer_tables import export_session_tables

session = sessions.Session("MiLenguaje", "Many")
session.add_keyword("fn")
session.add_keyword("let")
session.add_group("$TYPES", ["int", "float", "bool"])

manifest = export_session_tables(session, "build/lexer_tables")
print("Tablas exportadas. Hash de contenido:", manifest["content_hash"])
```

### Unidades Exportadas
- `gram_lexer_config.h`: Definiciones de preprocesador para tokens de comentarios, ancho de tabulación y reglas de indentación.
- `gram_lexer_keywords.c`: Tabla hash estática de palabras clave reservadas.
- `gram_lexer_groups.c`: Matrices estáticas de pertenencia para grupos semánticos de palabras clave.
- `gram_lexer_symbols.c`: Tablas ordenadas de operadores y símbolos para coincidencia maximal munch.
- `gram_lexer_codes.h`: Identificadores numéricos para tokens y códigos de diagnóstico.
- `gram_lexer_manifest.json`: Manifiesto de verificación con especificaciones de ABI 1.1 y hashes SHA-256.

---

## 4. Verificación Diferencial

Gram incluye un arnés de verificación automatizado [`tools/compare_lexers.py`](../../tools/compare_lexers.py) que ejecuta los lexers de Python y C sobre entradas idénticas para verificar igualdad token por token (tipos, spans, líneas, columnas y valores) a lo largo de cientos de casos de prueba sintéticos.
