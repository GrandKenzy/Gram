# Driver Unificado en C y CLI Autónomo

> **Módulo:** `gram.core.parser.c_driver`  
> **Estándar:** C11 (`-std=c11`)  
> **Estado:** Estable (Versión `2.1.0`)

El Driver en C de Gram (`gram_driver.h`, `gram_driver.c`) unifica la lectura de archivos, el escaneo léxico, el análisis sintáctico, la construcción del AST, la serialización de IR binario y el reporte de errores en una API de C ergonómica y sin dependencias externas.

Cuando se exporta con `emit_cli=True`, el generador también emite `gram_cli.c`, produciendo un compilador nativo autónomo y una herramienta de inspección de lenguaje.

---

## 1. API del Driver Unificado (`gram_driver.h`)

El driver ofrece dos modos operativos dependiendo de si su pipeline consume los ASTs directamente en memoria o genera artefactos binarios a disco.

### Modo A: AST en Memoria (`gram_parse_*`)
Analiza el código fuente en memoria, retornando el búfer de tokens y la arena del AST:

```c
#include "gram_driver.h"

GramParseResult resultado;
GramDriverError err;

GramDriverStatus estado = gram_parse_file("input.src", &resultado, &err);
if (estado == GRAM_DRIVER_OK) {
    printf("Análisis exitoso de %zu tokens; la raíz del AST es el nodo #%u\n",
           resultado.token_count, resultado.root);
    
    /* Acceso directo a resultado.arena.nodes[resultado.root] */
    
    gram_parse_result_free(&resultado);
} else {
    fprintf(stderr, "%s:%u:%u: %s\n",
            "input.src", err.line, err.column, err.message);
}
```

### Modo B: Compilación Directa a IR Binario (`gram_compile_*`)
Analiza el código fuente y emite un búfer binario `.gir` o lo escribe directamente en disco:

```c
#include "gram_driver.h"

GramDriverError err;
GramDriverStatus estado = gram_compile_file_to_ir_file(
    "input.src",
    "output.gir",
    &err
);

if (estado != GRAM_DRIVER_OK) {
    fprintf(stderr, "Error de compilación: %s\n", err.message);
}
```

### Funciones Principales de la API
| Función | Descripción |
| :--- | :--- |
| `gram_parse_source(src, len, out, err)` | Tokeniza y analiza una cadena fuente en memoria hacia un `GramParseResult`. |
| `gram_parse_file(path, out, err)` | Lee un archivo (omitiendo BOM UTF-8), tokeniza y analiza hacia un `GramParseResult`. |
| `gram_parse_result_free(r)` | Libera la memoria del búfer de tokens y de la arena del AST. |
| `gram_compile_source_to_ir(src, len, blob, err)` | Compila una cadena fuente directamente hacia un `GramIrBlob`. |
| `gram_compile_file_to_ir(path, blob, err)` | Compila un archivo fuente directamente hacia un `GramIrBlob`. |
| `gram_compile_file_to_ir_file(in, out, err)` | Compila un archivo fuente directamente a un archivo `.gir` en disco. |
| `gram_ir_blob_free(blob)` | Libera la memoria del blob de IR binario. |

---

## 2. CLI Nativo Autónomo (`gram_cli.c`)

Cuando se invoca `Session.export_c_parser(..., emit_cli=True)`, el directorio de salida incluye `gram_cli.c`. Compilar esta unidad produce un ejecutable autónomo.

### Compilación del CLI
```bash
gcc -std=c11 -O2 -Wall -Wextra \
    -I native/gram_lexer/include \
    -I native/gram_lexer/src \
    -I build/exported_parser \
    build/exported_parser/gram_cli.c \
    build/exported_parser/*.c \
    native/gram_lexer/src/*.c \
    -o gram_compiler
```

### Subcomandos

#### 1. `compile`
Compila un archivo fuente en un archivo binario `.gir`:
```bash
./gram_compiler compile source.lang -o build/output.gir
```

#### 2. `check`
Valida la sintaxis del código fuente y mide el tiempo de análisis:
```bash
./gram_compiler check source.lang --repeat 10
# Salida: OK (541 tokens in 0.000943s, 573579 lines/s)
```

#### 3. `ast`
Muestra una representación textual indentada del AST construido en memoria:
```bash
./gram_compiler ast source.lang
```

#### 4. `ir`
Inspecciona y muestra la estructura interna de un archivo binario `.gir`:
```bash
./gram_compiler ir build/output.gir
```

### Códigos de Salida del CLI
- `0`: Éxito.
- `1`: Error de argumentos (banderas faltantes o ruta incorrecta).
- `2`: Error léxico, de sintaxis o de E/S.
- `3`: Falta de memoria (fallo de asignación).
