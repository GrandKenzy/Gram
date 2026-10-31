<p align="center">
  <img src="discentra_centra/badge/front.png" alt="Gram Framework" width="320">
</p>

# Gram Framework

<p align="center">
  <strong>Dual-Target Parser Framework & Language Design Toolkit</strong><br>
  Python Prototype Engine · Native C11 AOT Compiler · Pratt Expressions · Relocatable Binary IR (GIR 1.0) · VS Code / LSP Tooling
</p>

<p align="center">
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.12%2B-blue.svg" alt="Python 3.12+"></a>
  <img src="https://img.shields.io/badge/c-standard--c11-00599C.svg" alt="C11 Standard">
  <img src="https://img.shields.io/badge/version-3.0.0-informational.svg" alt="Version 3.0.0">
  <a href="tests/"><img src="https://img.shields.io/badge/tests-300%20passed-success.svg" alt="Tests: 300 passed"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Free%20Use%20%26%20Commercial%20Output-brightgreen.svg" alt="License"></a>
  <a href="https://github.com/GrandKenzy/Gram"><img src="https://img.shields.io/badge/dependencies-0%20external-brightgreen.svg" alt="Zero External Dependencies"></a>
</p>

---

## Overview

**Gram** is a zero-dependency dual-target parsing framework. It allows you to prototype grammars interactively in Python with rich diagnostics, execution raytracing, and Pratt expression parsing, and then compile them directly into autonomous, high-throughput C11 parser units (`-std=c11`) with contiguous AST arenas, predictive branch dispatch, and relocatable binary intermediate representation (**GIR 1.0**).

### What is implemented in the repository:
- **Python Lexer (`gram.core.lexer`):** Configurable tokenizer supporting keywords (`Keyword`), semantic keyword groups (`WordGroup`), custom operator symbols (`MAP_SYMBOLS`, `insert_symbol`, `disabled_symbol`), indentation tracking (`Token.INDENT` / `Token.DEDENT`), prefixed strings, docstrings, numbers, and configurable single- or multi-character comments.
- **Transactional Parser State (`gram.core.parser`):** Token stream cursor (`Parser`, `ParseState`) with immutable `Checkpoint` snapshots (`savepoint` and `restore`) that roll back the cursor, virtual lookahead cursor (`vpos`), bracket depth, `storage` dictionary, `tk_tags` token tags, and in-place token replacements.
- **Combinator Library (`gram.core.combinators`):** 32 native combinators with formal `CombinatorKind` signatures:
  - **Matching:** `MatchToken`, `MatchKeyword`, `MatchGroup`, `MatchSeqSymbol`, `generador_expr`.
  - **Structural:** `Seq`, `Alt`, `Opt`, `Enclosed`, plus `+` (`Seq`) and `|` (`Alt`) operator overloads.
  - **Repetition & Delimited Lists:** `Many`, `Some`, `Until`, `UntilIndent`, `Separator` (produces `ArrayNode`), `CaptureRaw` (produces `RawNode`).
  - **Rules, Atoms & State:** `RuleItem`, `Ref`, `Item`, `Literal`, `Save`, `Load`.
  - **Lookahead, Signals & Tagging:** `Peek`, `Not`, `If`, `Skip` (with flow signals), `Tag`, `Tokenize`, `ErrorCombinator`, `SameLine`.
  - **Fluent Token Constraints:** `Req` (case, substring, length, numeric bounds, digit counts, and value transformations).
  - **Preprocessing & Expectations:** `Preprocess`, `Convert`, and `Expected`.
  - **Pratt Expression Engine:** `ArithmeticExpr`, `ConditionalExpr`, and `DualExpr` producing `ASTBinaryOp` and `ASTUnaryOp` nodes.
- **AST & Tracing (`gram.core.ast`):** `ASTAnalyzer` validates the root entrypoint rule (`Alt` of `Ref` branches), evaluates combinators through `Visitor`, and records execution traces in `RayTracing` (`trace="off" | "basic" | "detailed"`).
- **Isolated Language Sessions (`gram.sessions`):** `Session` encapsulates lexer catalogs, parser instances, configuration flags, and AOT compilation targets without polluting global process state.
- **Native C11 Lexer & DiagnosticsLite (`native/gram_lexer`):** Zero-allocation C11 lexer runtime operating over source byte spans, with decoupled `DiagnosticsLite` sinks and static table generation.
- **Ahead-Of-Time (AOT) C11 Compiler (`gram.core.parser.c_generator`):** Compiles grammar rule graphs into standalone C11 recursive-descent parsers with predictive `switch` lookahead dispatch, contiguous `GramAstArena` with transactional undo logs, and native Pratt expression generation (~565x to ~2,400x faster than Python).
- **Gram Binary IR (`GIR 1.0`):** Relocatable, zero-copy binary format with a 72-byte header, 40-byte dense nodes, deduplicated UTF-8 string pool, and validation view.
- **Unified Driver & CLI (`gram.core.parser.c_driver`):** Memory and file-based parser drivers, error formatting, and a standalone native command-line interface (`compile`, `check`, `ast`, `ir`).
- **VS Code & LSP Tooling (`gram.vsix`):** VSIX extension generator (`VSIXGenerator`, `pack_vsix`), AST token coloring (`ASTColorResolver`), and a JSON-RPC Language Server (`LSPServer`, `LSPState`).

---

## Dual Pipeline Architecture

```
Python Runtime (Development, Prototyping & LSP)
Source Text ──► Lexer ──► Parser (Checkpoints) ──► ASTAnalyzer ──► AST Nodes / RayTracing

                         │
                         ▼ Session.export_c_parser()
Native C11 Runtime (Production AOT Frontend)
Source File ──► Driver / Lexer ──► Pratt Parser ──► Contiguous AST Arena ──► GIR 1.0 Binary
                (Zero allocations) (Predictive switch) (Transactional undo log) (Relocatable)
```

---

## Installation

Gram requires Python 3.12+ and has zero external dependencies for its Python runtime. Native compilation requires any conforming C11 compiler (`gcc`, `clang`, or `msvc`).

### 1. From Source (Git Checkout)

```bash
git clone https://github.com/GrandKenzy/Gram.git
cd Gram
python -m gram
# Output: Gram Framework v3.0.0
```

### 2. Optional VNMA Integration

```toml
[project]
name = "my-compiler"
version = "0.1.0"

[dependencies]
gram-framework = { git = "https://github.com/GrandKenzy/Gram.git", tag = "v3.0.0" }
```

---

## Quickstart

### 1. Defining a Grammar in Python

```python
from gram import sessions
from gram.core.ast import ASTAnalyzer
from gram.core.combinators import (
    Alt,
    ArithmeticExpr,
    MatchKeyword,
    MatchToken,
    Ref,
    RuleItem,
    Seq,
)
from gram.core.lexer import Token

# 1. Define production rules
class LetStmt(RuleItem):
    nodeable = True
    entrypoint = Seq(
        MatchKeyword("let"),
        MatchToken(Token.IDENT),
        MatchToken(Token.ASSIGN),
        ArithmeticExpr(Token.NUMBER, Token.IDENT),
        MatchToken(Token.SEMICOLON),
    )
    rule = entrypoint

class Program(RuleItem):
    nodeable = True
    entrypoint = Alt(Ref(LetStmt))
    rule = entrypoint

# 2. Configure an isolated language session
session = sessions.Session("MyLang", "Many", entrypoint=Program)
session.add_keyword("let")

# 3. Tokenize and parse
source = "let total = 10 + 20 * 3;"
tokens = session.tokenize(source, "main.src")
ast = session.parse(tokens, "main.src", trace="basic")

print("Generated AST:", ast)
```

### 2. Exporting to Native C11 (AOT)

```python
# Compile the session grammar to standalone C11 with CLI
manifest = session.export_c_parser("build/native_parser", emit_cli=True)
print("Exported files:", manifest["files"])
print("Grammar fingerprint:", manifest["grammar_id"])
```

### 3. Building and Running the Native Compiler

```bash
gcc -std=c11 -O2 \
    -I native/gram_lexer/include \
    -I native/gram_lexer/src \
    -I build/native_parser \
    build/native_parser/gram_cli.c \
    build/native_parser/*.c \
    native/gram_lexer/src/*.c \
    -o mylangc

# Check syntax and benchmark parse time
./mylangc check main.src --repeat 5

# Compile source directly to binary GIR
./mylangc compile main.src -o main.gir

# Dump binary GIR tree
./mylangc ir main.gir
```

---

## Performance Benchmark

Measured on the complete end-to-end pipeline (File Reading $\to$ Lexer $\to$ Pratt Parser $\to$ AST Arena Allocation) via [`benchmarks/parser_python_vs_c.py`](benchmarks/parser_python_vs_c.py):

| Metric | Python (`trace="basic"`) | Python (`trace="off"`) | Native C11 (AOT) | Speedup (vs off / basic) |
| :--- | :--- | :--- | :--- | :--- |
| **Median Time** | 1,454.5 ms | 532.5 ms | 0.94 ms (943 µs) | **564.6x / 1,542.1x** |
| **Throughput** | 0.01 MB/s | 0.02 MB/s | 9.14 MB/s | **564.6x / 1,542.1x** |
| **Lines / Second**| 372 l/s | 1,016 l/s | 573,579 l/s | **564.6x / 1,542.1x** |

---

## Documentation

Exhaustive documentation is available in English and Spanish:
- **[English Documentation](docs/en/index.md)**
- **[Documentación en Español](docs/es/index.md)**

Section Index:
- **01. Introduction / Introducción:** [EN](docs/en/01-Introduction/index.md) | [ES](docs/es/01-Introduccion/index.md)
- **02. Combinators / Combinadores:** [EN](docs/en/02-Combinators/index.md) | [ES](docs/es/02-Combinadores/index.md)
- **03. Usage Guide / Guía de Uso:** [EN](docs/en/03-Usage/index.md) | [ES](docs/es/03-Uso/index.md)
- **04. Lexer / Analizador Léxico:** [EN](docs/en/04-Lexer/index.md) | [ES](docs/es/04-Lexer/index.md)
- **05. Native C Runtime & AOT / Runtime C Nativo y AOT:** [EN](docs/en/05-Native-C-and-AOT/index.md) | [ES](docs/es/05-Nativo-C-y-AOT/index.md)

---

## Running the Test Suite

Run the full automated test suite (300 tests) using Python's built-in `unittest` discovery:

```bash
python -m unittest discover -s tests
```

---

## License

Gram is distributed under the **Free Use & Commercial Output License** (see [LICENSE](LICENSE)). Languages, parsers, compilers, and tools built with Gram belong to their creators and may be distributed or commercialized without royalties.

---

<p align="center">
  <img src="discentra_centra/badge/footer.jpeg" alt="Gram Framework" width="100%">
</p>
