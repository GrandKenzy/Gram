# Native C Lexer and DiagnosticsLite

> **Location:** `native/gram_lexer/`  
> **Standard:** C11 (`-std=c11`)  
> **Status:** Stable (Version `3.0.0`)

The native Gram C lexer is a standalone, reentrant tokenizer written in clean C11. It delivers 100% lexical equivalence with the Python reference lexer while operating with zero dynamic allocations per token.

---

## 1. Zero-Allocation Token Architecture

Tokens do not copy strings or allocate individual heap structures. Each token records its kind, source byte offset, byte length, 1-based line, and 0-based column directly in caller-managed storage:

```c
typedef struct GramToken {
    uint32_t kind;      /* Token kind identifier (GRAM_TOKEN_*) */
    uint32_t flags;     /* Lexical metadata and classification flags */
    uint32_t start;     /* Byte offset in the UTF-8 source buffer */
    uint32_t length;    /* Token length in bytes */
    uint32_t line;      /* 1-based line number */
    uint32_t column;    /* 0-based column number */
    uint32_t value;     /* Extra payload (e.g. symbol index or keyword ID) */
} GramToken;
```

### Supported Token Syntaxes
- **Identifiers & Keywords:** ASCII and UTF-8 identifier rules, with constant-time lookup against exported static keyword tables.
- **Numbers:** Decimal, float, scientific notation, binary (`0b`), octal (`0o`), and hexadecimal (`0x`, including floating hex `0x...p...`).
- **Strings:** Single, double, and triple-quoted docstrings with escape sequences (`\n`, `\t`, `\xHH`, `\uXXXX`, `\UXXXXXXXX`) and string prefixes (`L`, `u`, `U`, `u8`).
- **Symbols & Operators:** Maximal munch longest-match matching against length-sorted symbol tables.
- **Indentation:** Configurable indentation modes (`spaces`, `tabs`, `mixed`) tracking an internal indentation stack.

---

## 2. Decoupled DiagnosticsLite

`DiagnosticsLite` (`gram_diagnostics_lite.h`, `diagnostics_lite.c`) is a high-performance diagnostic subsystem decoupled from heavyweight object systems or runtime memory managers:

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

### Sinks & Callbacks
- **Null Sink (`gram_diag_null_sink()`):** Discards all diagnostic messages for zero-overhead production runs.
- **Callback Sink (`gram_diag_callback_sink()`):** Forwards formatted diagnostic records to a user-provided function pointer.
- **Arena Buffer Sink:** Formats diagnostic messages into an external pre-allocated arena buffer.

---

## 3. Exporting Lexical Tables from a Session

To generate the static C tables corresponding to a language session, use `tools/export_lexer_tables.py` or the Python API:

```python
from gram import sessions
from tools.export_lexer_tables import export_session_tables

session = sessions.Session("MyLang", "Many")
session.add_keyword("fn")
session.add_keyword("let")
session.add_group("$TYPES", ["int", "float", "bool"])

manifest = export_session_tables(session, "build/lexer_tables")
print("Tables exported. Content hash:", manifest["content_hash"])
```

### Exported Units
- `gram_lexer_config.h`: Preprocessor definitions for comment tokens, tab width, and indentation rules.
- `gram_lexer_keywords.c`: Static hash table of reserved keywords.
- `gram_lexer_groups.c`: Static membership matrices for semantic keyword groups.
- `gram_lexer_symbols.c`: Sorted symbol tables for maximal munch matching.
- `gram_lexer_codes.h`: Numeric identifiers for tokens and diagnostic codes.
- `gram_lexer_manifest.json`: Verification manifest containing ABI 1.0 specifications and SHA-256 hashes.

---

## 4. Differential Verification

Gram includes an automated verification harness [`tools/compare_lexers.py`](../../tools/compare_lexers.py) that executes the Python and C lexers on identical inputs to verify token-for-token equality (kinds, spans, lines, columns, and values) across hundreds of synthetic test cases.
