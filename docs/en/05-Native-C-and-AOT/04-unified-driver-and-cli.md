# Unified C Driver and Standalone CLI

> **Module:** `gram.core.parser.c_driver`  
> **Standard:** C11 (`-std=c11`)  
> **Status:** Stable (Version `2.1.0`)

The Gram C Driver (`gram_driver.h`, `gram_driver.c`) unifies file reading, lexical scanning, parsing, AST construction, binary IR serialization, and error reporting into an ergonomic, zero-dependency C API.

When exported with `emit_cli=True`, the generator also emits `gram_cli.c`, producing a standalone native binary compiler and language inspection utility.

---

## 1. Unified Driver API (`gram_driver.h`)

The driver provides two distinct operating modes depending on whether your compiler pipeline consumes ASTs directly in memory or streams binary artifacts to disk.

### Mode A: In-Memory AST (`gram_parse_*`)
Parses source text into memory, returning the token buffer and AST arena:

```c
#include "gram_driver.h"

GramParseResult result;
GramDriverError err;

GramDriverStatus status = gram_parse_file("input.src", &result, &err);
if (status == GRAM_DRIVER_OK) {
    printf("Successfully parsed %zu tokens; AST root is node #%u\n",
           result.token_count, result.root);
    
    /* Access result.arena.nodes[result.root] directly */
    
    gram_parse_result_free(&result);
} else {
    fprintf(stderr, "%s:%u:%u: %s\n",
            "input.src", err.line, err.column, err.message);
}
```

### Mode B: Direct Binary IR Compilation (`gram_compile_*`)
Parses source text and emits a relocatable `.gir` binary buffer or writes it directly to disk:

```c
#include "gram_driver.h"

GramDriverError err;
GramDriverStatus status = gram_compile_file_to_ir_file(
    "input.src",
    "output.gir",
    &err
);

if (status != GRAM_DRIVER_OK) {
    fprintf(stderr, "Compilation error: %s\n", err.message);
}
```

### Key API Functions
| Function | Description |
| :--- | :--- |
| `gram_parse_source(src, len, out, err)` | Tokenizes and parses a source string in memory into `GramParseResult`. |
| `gram_parse_file(path, out, err)` | Reads a file (stripping UTF-8 BOM), tokenizes, and parses into `GramParseResult`. |
| `gram_parse_result_free(r)` | Releases the token buffer and AST arena memory. |
| `gram_compile_source_to_ir(src, len, blob, err)` | Compiles an in-memory source string directly into a `GramIrBlob`. |
| `gram_compile_file_to_ir(path, blob, err)` | Compiles a source file directly into a `GramIrBlob`. |
| `gram_compile_file_to_ir_file(in, out, err)` | Compiles a source file directly into an output `.gir` file on disk. |
| `gram_ir_blob_free(blob)` | Releases binary IR blob memory. |

---

## 2. Standalone Native CLI (`gram_cli.c`)

When `Session.export_c_parser(..., emit_cli=True)` is called, the output directory includes `gram_cli.c`. Compiling this unit produces a standalone compiler CLI.

### Building the CLI
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

### Subcommands

#### 1. `compile`
Compiles a source file into a binary `.gir` file:
```bash
./gram_compiler compile source.lang -o build/output.gir
```

#### 2. `check`
Validates source syntax and reports benchmark timing:
```bash
./gram_compiler check source.lang --repeat 10
# Output: OK (541 tokens in 0.000943s, 573579 lines/s)
```

#### 3. `ast`
Prints an indented textual dump of the in-memory AST:
```bash
./gram_compiler ast source.lang
```

#### 4. `ir`
Inspects and dumps the structural contents of a `.gir` binary file:
```bash
./gram_compiler ir build/output.gir
```

### CLI Exit Codes
- `0`: Success.
- `1`: Argument error (missing flags or file path).
- `2`: Lexical error, syntax error, or I/O error.
- `3`: Out of memory (allocation failure).
