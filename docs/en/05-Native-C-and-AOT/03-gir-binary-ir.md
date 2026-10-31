# Gram Binary Intermediate Representation (GIR 1.0)

> **Module:** `gram.core.parser.c_driver`  
> **Format Version:** `1.0` (`GIR\0`)  
> **Status:** Stable (Version `3.0.0`)

Gram Binary IR (`GIR`) is a compact, relocatable, zero-copy binary serialization format for Abstract Syntax Trees produced by the native C parser. It allows compilers, linters, and analysis tools to stream, cache, and traverse parsed ASTs without paying the serialization or deserialization costs of JSON, XML, or protobufs.

---

## 1. Binary Layout Specification

A `.gir` binary buffer consists of three contiguous, 8-byte aligned sections:

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Header (72 bytes)                                        │
│    Magic: "GIR\0" | Major: 1, Minor: 0                      │
│    Grammar ID, Source Hash, Source Size, Offsets, Counts    │
├─────────────────────────────────────────────────────────────┤
│ 2. Deduplicated UTF-8 String Pool                           │
│    Offsets Table (uint32_t[string_count + 1])               │
│    Contiguous Null-Terminated Strings (pool_bytes)          │
├─────────────────────────────────────────────────────────────┤
│ 3. Dense Node Table (40 bytes per node)                     │
│    Nodes 0..N (8-byte aligned)                              │
│    Node 0: Reserved NULL node                               │
│    Node 1..N: Preorder AST nodes                            │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Header Structure (`GramIrHeader`, 72 bytes)

```c
typedef struct GramIrHeader {
    char     magic[4];                /* Always "GIR\0" (0x00524947) */
    uint16_t version_major;           /* Format major version (1) */
    uint16_t version_minor;           /* Format minor version (0) */
    uint32_t flags;                   /* Format flags (bit 0: little-endian) */
    uint32_t header_size;             /* Size of this header in bytes (72) */
    uint64_t grammar_id;              /* 64-bit SHA-256 fingerprint of the grammar & lexicon */
    uint64_t source_hash;             /* 64-bit FNV-1a hash of the source text */
    uint32_t source_size;             /* Original source size in bytes */
    uint32_t string_count;            /* Number of unique strings in the pool */
    uint32_t string_offsets_offset;   /* File offset of the string offsets table */
    uint32_t string_pool_offset;      /* File offset of the string byte buffer */
    uint32_t string_pool_bytes;       /* Total size of the string pool in bytes */
    uint32_t nodes_offset;            /* File offset of the node table (8-byte aligned) */
    uint32_t node_count;              /* Total node count (including dummy sentinel node 0) */
    uint32_t root_index;              /* Index of the root AST node in the node table */
    uint64_t total_size;              /* Total file size in bytes */
} GramIrHeader;
```

---

## 3. Node Structure (`GramIrNode`, 40 bytes)

Nodes use array indices rather than machine memory pointers, making the entire file relocatable across memory spaces and architectures:

```c
typedef struct GramIrNode {
    uint16_t kind;           /* Node kind identifier (GramAstKind) */
    uint16_t flags;          /* Classification flags (see table below) */
    uint32_t symbol_id;      /* Index into string pool (rule name / lexeme) */
    uint32_t value;          /* Extra metadata payload (rule ID or token kind) */
    uint32_t src_start;      /* Byte offset in original UTF-8 source text */
    uint32_t src_length;     /* Byte length in original UTF-8 source text */
    uint32_t line;           /* 1-based line number */
    uint32_t column;         /* 0-based column number */
    uint32_t first_child;    /* Index of first child node (0 if none) */
    uint32_t next_sibling;   /* Index of next sibling node (0 if none) */
    uint32_t child_count;    /* Number of direct children */
} GramIrNode;
```

### Node Classification Flags
| Flag Constant | Value | Description |
| :--- | :--- | :--- |
| `GRAM_IR_NODE_TERMINAL` | `0x01` | Leaf terminal node (keyword, identifier, symbol, number, string). |
| `GRAM_IR_NODE_RULE` | `0x02` | Composite grammar rule node (`ASTRef`). |
| `GRAM_IR_NODE_EXPR` | `0x04` | Pratt expression node (`EXPR_UNARY` or `EXPR_BINARY`). |
| `GRAM_IR_NODE_ARRAY` | `0x08` | Sequence or delimited array (`ARRAY`). |
| `GRAM_IR_NODE_RAW` | `0x10` | Opaque raw code block captured via `CaptureRaw` (`RAW`). |

---

## 4. C View API (`GramIrView`)

The `GramIrView` API allows reading and validating a `.gir` file without copying memory:

```c
#include "gram_ir.h"

GramIrView view;
if (gram_ir_read_file("output.gir", &view) == GRAM_IR_OK) {
    if (gram_ir_view_matches_grammar(&view)) {
        printf("Valid GIR for grammar 0x%llx with %u nodes\n",
               (unsigned long long)view.header->grammar_id,
               view.header->node_count);
        
        /* Dump tree structure in human-readable indented format */
        gram_ir_dump(&view, stdout);
    }
    gram_ir_view_free(&view);
}
```

### Structural Validation & Cycle Rejection
`gram_ir_view_init()` performs comprehensive validation before accepting a binary buffer:
- Verifies magic number, versions, and total buffer size.
- Ensures all offsets and sizes fit within buffer bounds and follow 8-byte alignment.
- Performs iterative preorder validation to detect corrupted child links, out-of-range sibling indices, or cyclic loops.

---

## 5. Consuming GIR in Python (`gram.ir`)

Gram includes native, zero-dependency Python support for reading, traversing, and querying `.gir` files via `gram.ir`:

```python
from gram import ir

# Load from file or bytes in microseconds
view = ir.load_gir("output.gir", source_text=source_code)

print(f"Nodes: {view.node_count}, Grammar: 0x{view.header.grammar_id:016x}")

# 1. Preorder traversal
for node in view.walk(order="pre"):
    indent = "  " * node.depth
    print(f"{indent}{node.kind_name} [{node.line}:{node.column}] -> {node.text!r}")

# 2. Tree navigation
root = view.root
for child in root.children:
    print("Direct child:", child.kind_name, child.span)

# 3. Querying nodes
functions = list(root.find("FunctionDecl"))
first_ident = root.find_first("IDENT")
```

---

## 6. Optional C AOT Tree Walker (`--walker` / `emit_walker=True`)

When compiling a parser to C, passing `emit_walker=True` (or CLI flag `--walker`) generates `gram_ir_walker.h` and `gram_ir_walker.c`:

```c
#include "gram_ir_walker.h"

static GramIrWalkAction my_visitor(
    const GramIrView *view,
    uint32_t node_idx,
    uint32_t depth,
    bool is_enter,
    void *user_data
) {
    if (is_enter) {
        const char *name = gram_ir_node_name(view, node_idx);
        printf("%*sEntering %s\n", (int)(depth * 2), "", name);

        /* Prune subtree if we do not wish to inspect its children */
        if (strcmp(name, "IgnoredBlock") == 0) {
            return GRAM_IR_WALK_PRUNE;
        }
    } else {
        printf("%*sLeaving node %u\n", (int)(depth * 2), "", (unsigned)node_idx);
    }
    return GRAM_IR_WALK_CONTINUE;
}

/* Traverse tree starting from root */
gram_ir_walk(&view, 0, my_visitor, NULL);

/* Search helpers */
uint32_t ident_idx = gram_ir_find_first(&view, 0, "IDENT");
if (ident_idx > 0) {
    printf("Found identifier: %s\n", gram_ir_node_text(&view, ident_idx, NULL));
}
```

