# Representación Intermedia Binaria de Gram (GIR 1.0)

> **Módulo:** `gram.core.parser.c_driver`  
> **Versión de Formato:** `1.0` (`GIR\0`)  
> **Estado:** Estable (Versión `2.1.0`)

Gram Binary IR (`GIR`) es un formato de serialización binaria compacto, relocalizable y sin copias (*zero-copy*) para Árboles de Sintaxis Abstracta producidos por el parser nativo en C. Permite a compiladores, linters y herramientas de análisis recorrer, cachear e inspeccionar ASTs en disco o memoria sin pagar los costos de serialización de formatos como JSON, XML o protobufs.

---

## 1. Especificación de la Distribución Binaria

Un búfer binario `.gir` consta de tres secciones contiguas alineadas a 8 bytes:

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Encabezado (72 bytes)                                    │
│    Magic: "GIR\0" | Major: 1, Minor: 0                      │
│    Grammar ID, Source Hash, Source Size, Offsets, Counts    │
├─────────────────────────────────────────────────────────────┤
│ 2. Pool de Cadenas UTF-8 Deduplicadas                       │
│    Tabla de Offsets (uint32_t[string_count + 1])            │
│    Cadenas Terminadas en Nulo (pool_bytes)                  │
├─────────────────────────────────────────────────────────────┤
│ 3. Tabla Densa de Nodos (40 bytes por nodo)                 │
│    Nodos 0..N (alineados a 8 bytes)                         │
│    Nodo 0: Nodo nulo reservado                              │
│    Nodos 1..N: Nodos AST en orden previo (preorder)         │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Estructura del Encabezado (`GramIrHeader`, 72 bytes)

```c
typedef struct GramIrHeader {
    char     magic[4];       /* Siempre "GIR\0" (0x00524947) */
    uint16_t major;          /* Versión mayor de formato (1) */
    uint16_t minor;          /* Versión menor de formato (0) */
    uint32_t flags;          /* Banderas (bit 0: little-endian) */
    uint32_t header_size;    /* Tamaño de este encabezado en bytes (72) */
    uint64_t grammar_id;     /* Fingerprint FNV-1a de 64 bits de la gramática */
    uint64_t source_hash;    /* Hash FNV-1a de 64 bits del texto fuente */
    uint64_t source_size;    /* Tamaño del código fuente original en bytes */
    uint32_t string_count;   /* Cantidad de cadenas únicas en el pool */
    uint32_t offsets_off;    /* Offset a la tabla de offsets de cadenas */
    uint32_t pool_off;       /* Offset al búfer de bytes de cadenas */
    uint32_t pool_bytes;     /* Tamaño total del pool de cadenas en bytes */
    uint32_t nodes_off;      /* Offset a la tabla de nodos (alineado a 8 bytes) */
    uint32_t node_count;     /* Cantidad total de nodos (incluyendo el nodo 0) */
    uint32_t root_index;     /* Índice del nodo raíz en la tabla de nodos */
    uint64_t total_size;     /* Tamaño total del archivo en bytes */
} GramIrHeader;
```

---

## 3. Estructura de Nodo (`GramIrNode`, 40 bytes)

Los nodos utilizan índices de arreglo en lugar de punteros de memoria, lo que hace que todo el archivo sea relocalizable entre procesos y arquitecturas:

```c
typedef struct GramIrNode {
    uint16_t kind;           /* Identificador de tipo de nodo */
    uint16_t flags;          /* Banderas de clasificación (ver tabla) */
    uint32_t symbol_index;   /* Índice en el pool de cadenas (nombre de regla o lexema) */
    uint32_t value;          /* Carga útil de metadatos */
    uint32_t src_start;      /* Byte offset en el texto fuente original UTF-8 */
    uint32_t src_length;     /* Longitud en bytes en el texto fuente original */
    uint32_t line;           /* Número de línea (base 1) */
    uint32_t column;         /* Número de columna (base 0) */
    uint32_t first_child;    /* Índice del primer hijo (0 si no tiene) */
    uint32_t next_sibling;   /* Índice del siguiente hermano (0 si no tiene) */
    uint32_t child_count;    /* Cantidad de hijos directos */
} GramIrNode;
```

### Banderas de Clasificación de Nodos
| Constante de Bandera | Valor | Descripción |
| :--- | :--- | :--- |
| `GRAM_IR_NODE_TERMINAL` | `0x01` | Nodo terminal hoja (palabra clave, identificador, símbolo, número, cadena). |
| `GRAM_IR_NODE_RULE` | `0x02` | Nodo de regla gramatical compuesta (`ASTRef`). |
| `GRAM_IR_NODE_EXPR` | `0x04` | Nodo de expresión Pratt (`EXPR_UNARY` o `EXPR_BINARY`). |
| `GRAM_IR_NODE_ARRAY` | `0x08` | Secuencia o arreglo delimitado (`ARRAY`). |
| `GRAM_IR_NODE_RAW` | `0x10` | Bloque opaco de código capturado mediante `CaptureRaw` (`RAW`). |

---

## 4. API de Visualización en C (`GramIrView`)

La API `GramIrView` permite leer y validar un archivo `.gir` sin copiar memoria:

```c
#include "gram_ir.h"

GramIrView view;
if (gram_ir_read_file("output.gir", &view) == GRAM_IR_OK) {
    if (gram_ir_view_matches_grammar(&view)) {
        printf("GIR válido para la gramática 0x%llx con %u nodos\n",
               (unsigned long long)view.header->grammar_id,
               view.header->node_count);
        
        /* Imprime la estructura del árbol de forma indentada y legible */
        gram_ir_dump(&view, stdout);
    }
    gram_ir_view_free(&view);
}
```

### Validación Estructural y Prevención de Ciclos
`gram_ir_view_init()` ejecuta comprobaciones exhaustivas antes de aceptar un búfer binario:
- Verifica el número mágico, las versiones y el tamaño total del búfer.
- Garantiza que todos los offsets y longitudes estén dentro de los límites del archivo y respeten la alineación a 8 bytes.
- Ejecuta una validación en preorder para detectar enlaces corruptos, índices fuera de rango o referencias cíclicas.
