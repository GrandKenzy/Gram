# Lexical Analysis Subsystem (`gram.core.lexer`)

> **Subsystem:** `gram.core.lexer`  
> **Runtime:** Pure Python 3.12+ (Zero external runtime dependencies)  
> **Status:** Stable (Version `2.1.0`)

The **Lexical Analysis Subsystem** is Gram's front-line scanning engine. It ingests source code from strings, line sequences, or file paths and converts raw character streams into an ordered sequence of strongly-typed lexeme tokens (`TokenType`) ending with a terminal `Token.EOF`.

Unlike simple regex-based tokenizers or monolithic state machines, Gram's lexer combines a clean two-class architecture (`LexerState` and `Lexer`), a specialized visitor dispatch pipeline (`gram.core.lexer.visitors`), Python-style semantic whitespace tracking, greedy maximal-munch operator resolution (`MAP_SYMBOLS`), and deep integration with Gram's diagnostic telemetry (`Diagnostics`).

---

## Architecture Overview

```
Source Code (str | list[str] | Path)
                  │
                  ▼
          ┌───────────────┐
          │  LexerState   │ ◄─── gram.config / Session.config
          └───────┬───────┘
                  │ (line cursor, col cursor, indents stack)
                  ▼
            ┌───────────┐
            │   Lexer   │ (process() main loop)
            └─────┬─────┘
                  │
     ┌────────────┼────────────────────────┬──────────────────────┐
     ▼            ▼                        ▼                      ▼
Whitespace &  Indentation Engine     Multiline Delimiters     Visitor Dispatch
Line Jumps    (INDENT / DEDENT)       (Strings & Comments)    (visitors.visit)
                                                                  │
                                   ┌──────────────┬───────────────┼──────────────┐
                                   ▼              ▼               ▼              ▼
                                Numbers        Strings         Symbols         Words
                               (DECIMAL/      (Single/Multi/  (MAP_SYMBOLS/   (BOOL/NULL/
                                NUMBER)        Escapes/Flags)  Maximal Munch)  KEYWORD/IDENT)
                                   │              │               │              │
                                   └──────────────┴───────┬───────┴──────────────┘
                                                          ▼
                                                  list[TokenType]
                                                          │
                                         ┌────────────────┴────────────────┐
                                         ▼                                 ▼
                                  Parser(tokens)               TokenStream(tokens)
```

---

## Key Capabilities

1. **Deterministic Categorization:** Words undergo a strict four-stage resolution order: configured booleans (`Token.BOOL`), configured null (`Token.NULL`), registered keywords (`Token.KEYWORD`), and user identifiers (`Token.IDENT`).
2. **Greedy Maximal-Munch Operators:** Built-in operators and custom symbols in `MAP_SYMBOLS` are dynamically sorted by length descending, guaranteeing that composite operators such as `**=`, `->`, `:=`, and `...` are matched before single characters.
3. **C-Compatible Numeric Parsing:** Handles decimal integers, floating-point forms (`3.14`, `1.5e-4`, leading dot `.5`), binary (`0b`), octal (`0o`), and hexadecimal integers/floats (`0x1.2p3`). C suffixes (`u`, `l`, `f`) are preserved as raw strings for downstream semantic analysis without loss of spelling.
4. **Semantic Indentation Tracking:** Maintains an indentation stack supporting `spaces`, `tabs`, and `mixed` visual width expansion, emitting `Token.INDENT` and `Token.DEDENT` tokens and catching indentation mismatches.
5. **Configurable Delimiters & Comments:** Single-line comments (e.g., `#`, `//`, `;`), C-style block comments (`/* ... */`), and arbitrary multiline delimiters (`add_multline`) can be registered and stripped or retained in `lexer.comments`.
6. **Session Isolation:** All keyword catalogs (`Keyword`), semantic word groups (`WordGroup`), and symbol tables (`MAP_SYMBOLS`) can be scoped to isolated `Session` instances to prevent multi-language pollution.
7. **Zero-Overhead Diagnostics:** Directly inherits from `Diagnostics`, maintaining structured execution nodes and error stacks when telemetry is enabled, or executing with minimal overhead when disabled.

---

## Chapter Directory

### [01. Architecture & State Management](./01-architecture-and-state.md)
Detailed examination of `Lexer` and `LexerState`, source ingestion (`str`, `Sequence[str]`, `Path`), cursor coordinates, indentation stack lifecycle, precondition verification via `check_state()`, and execution traces.

### [02. Token Catalog & Symbol Dispatch](./02-tokens-and-symbols.md)
Exhaustive reference for the 11 formal categories of `Token`, `TokenType` lexemes and coordinate formatting (`formatter`), runtime `CustomToken` dynamic tokens, bitwise `TokenFlags`, and the `MAP_SYMBOLS` maximal-munch engine with `insert_symbol()` and `disabled_symbol()`.

### [03. Literals & Specialized Visitors](./03-literals-and-visitors.md)
In-depth breakdown of the `visitors/` dispatch architecture: numeric literals (radix prefixes, floating points, underscores, C suffixes, `Token.DECIMAL` vs. `Token.NUMBER`), strings and docstrings (escapes, Unicode `\uXXXX`, prefixed strings `L`, `u`, `U`, `u8`), and keyword resolution precedence.

### [04. Indentation, Comments, & Delimiters](./04-indentation-and-comments.md)
Comprehensive guide to semantic whitespace tracking (`indents` stack, indent styles, visual tab expansion, mismatch detection), single-line comment variants, block comments, comment preservation in `lexer.comments`, and custom multiline delimiter registries (`add_multline`).

### [05. Token Stream Navigation (`TokenStream`)](./05-token-stream.md)
Reference manual for `TokenStream`: cursor movement (`position`, `advance`, `rewind`, `reset`), lookahead inspection (`current`, `peek`), pattern checks (`check`, `match`), strict consumption (`consume`), slicing, and token exclusion filtering (`filter_tokens`).

### [06. Configuration & Diagnostics Reference](./06-configuration-and-diagnostics.md)
Complete matrix of all `config` settings affecting the lexer, diagnostic telemetry nodes, lexical error handling (`report_error`, `fail`, error action hooks), the full table of OSGDC `LEXER_*` error codes, and multi-language session scoping.
