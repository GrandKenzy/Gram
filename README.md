# Gram Framework

<p align="center">
  <strong>Pure-Python Meta-Interpretation & Language Design Engine</strong><br>
  Combinator parsing with atomic backtracking, AST RayTracing telemetry, Pratt expression engine, GLANG DSL, and Language Server Protocol (LSP) tooling for VS Code.
</p>

<p align="center">
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.10%2B-blue.svg" alt="Python 3.10+"></a>
  <img src="https://img.shields.io/badge/version-2.0.0%20Beta-informational.svg" alt="Version 2.0.0 Beta">
  <a href="tests/"><img src="https://img.shields.io/badge/tests-45%20passed-success.svg" alt="Tests: 45 passed"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Free%20Use%20%26%20Commercial%20Output-brightgreen.svg" alt="License"></a>
  <a href="https://github.com/GrandKenzy/Gram"><img src="https://img.shields.io/badge/dependencies-0%20external-brightgreen.svg" alt="Zero External Dependencies"></a>
</p>

> **Gram v2.0.0 Beta Release:**  
> Gram has evolved into **v2.0.0 Beta**, introducing unified AST **RayTracing** telemetry, immutable **TokenInfo** snapshots, the **Hookr** event observer pattern for LSP/IDE tools, a modernized **Pratt expression climbing engine**, and an exhaustive test suite with comprehensive documentation.

---

## What is Gram?

**Gram** is a zero-dependency, pure-Python framework designed to build programming languages, domain-specific languages (DSLs), and structured data formats with high expressiveness, modularity, and strict typing.

Rather than relying on external parser generators or complex C extensions, Gram provides:
- **Atomic Backtracking Combinator Engine:** Composable parsing primitives (`Seq`, `Alt`, `Many`, `Sep`, `Enclosed`, etc.) with atomic `savepoint` and `restore` semantics.
- **AST RayTracing Telemetry:** Full execution tracing (`RayTracing`, `RayRecord`) capturing rule call-stacks, execution duration, token spans, and path profiling for real-time LSP diagnostics.
- **Hookr Observer Pipeline:** Non-intrusive event emitter hook system (`before_match`, `after_match`, `on_backtrack`, `on_error`, `on_complete`) decoupling parser telemetry from AST transformations.
- **TokenInfo Snapshots:** Immutable, rich token metadata (row, column, length, value, token type, custom group, source text) for diagnostics and language tooling.
- **Pratt Expression Engine:** Infix, prefix, and ternary operator precedence parsing (`DualExpr`, `ArithmeticExpr`, `ConditionalExpr`, `ChainL`, `ChainR`).
- **VS Code Extension & LSP Tooling:** Native generator creating VS Code extensions (VSIX) with TextMate syntax highlighting, live completion, and Language Server Protocol (`gram.vsix.lsp`) communication.
- **GLANG DSL & Plugin Architecture:** Declarative grammar definition language with AST static security auditing (`gram check`).

---

## Architecture Overview

```
                         ┌─────────────────────────┐
                         │       Source Code       │
                         └───────────┬─────────────┘
                                     │
                                     ▼
                         ┌─────────────────────────┐
                         │       Lexer Engine      │  <-- Keywords, custom groups,
                         └───────────┬─────────────┘      indents/dedents, comments
                                     │ Stream of Tokens (TokenInfo)
                                     ▼
                         ┌─────────────────────────┐
                         │   Parser & Combinators  │ <== Hookr Event Emitter
                         └───────────┬─────────────┘     (savepoint / restore backtracking)
                                     │
                                     ▼
                         ┌─────────────────────────┐
                         │   ASTAnalyzer Engine    │ <== RayTracing Telemetry
                         └───────────┬─────────────┘     (call stack, profiling, AST nodes)
                                     │
            ┌────────────────────────┼────────────────────────┐
            ▼                        ▼                        ▼
     ┌──────────────┐         ┌──────────────┐         ┌──────────────┐
     │  Plugin      │         │  GLANG DSL   │         │  VSIX & LSP  │
     │  Sandbox AST │         │  Compiler    │         │  for VS Code │
     └──────────────┘         └──────────────┘         └──────────────┘
```

---

## Installation

### From Source Repository:

```bash
git clone https://github.com/GrandKenzy/Gram.git
cd Gram
pip install -e .
```

### Verification:

```bash
python -m gram --version
# Or using the console launcher:
gram --version
```

### Uninstallation:

```bash
gram uninstall
# Skip confirmation prompt:
gram uninstall --yes
```

---

## Quickstart (Python API)

Define a grammar rule, parse structured input, construct an AST, and inspect execution telemetry via RayTracing:

```python
from gram.core.ast.analyzer import ASTAnalyzer
from gram.core.combinators import (
    DECLARATION,
    PROGRAM,
    Alt,
    Many,
    MatchKeyword,
    MatchToken,
    Ref,
    RuleItem,
    Seq,
)
from gram.core.lexer import Lexer, Token, words
from gram.core.parser import Parser

# 1. Register language keywords and syntax theme colors
words.add_keyword("let", hex_color="#569CD6", description="Variable declaration")

# 2. Define grammar rules using RuleItem
class LetStatement(RuleItem):
    name = "LetStatement"
    grammar = Seq(
        MatchKeyword("let"),
        MatchToken(Token.IDENT),
        MatchToken(Token.ASSIGN),
        MatchToken(Token.NUMBER),
    )

# 3. Assemble root grammar table
grammar = {
    PROGRAM: Many(Ref(DECLARATION)),
    DECLARATION: Alt(Ref(LetStatement)),
    LetStatement: LetStatement.grammar,
}

# 4. Tokenize source code
source_code = "let total = 100"
lexer = Lexer(source_code)
tokens = [t for t in lexer.process() if t.token != Token.EOF]

# 5. Parse and build AST
parser = Parser(tokens)
analyzer = ASTAnalyzer(parser, grammar)
ast = analyzer.process()

# 6. Inspect AST nodes
for node in ast.body:
    print(node.format())
    # Output: └── [L0] LetStatement (code=0) -> values=['let', 'total', 100]

# 7. Telemetry & Profiling with RayTracing (v2.0.0 Beta)
if analyzer.raytracing:
    print(analyzer.raytracing.stringify())
    # Detailed tree of rule executions, durations, and token consumption
```

---

## What's New in v2.0.0 Beta

| Feature | Description | Reference |
| :--- | :--- | :--- |
| **AST RayTracing Telemetry** | Full rule execution tree recording duration, token intervals, and status (`SUCCESS`, `FAILED`, `BACKTRACKED`). | `gram.core.ast.raytracing` |
| **Immutable `TokenInfo`** | Clean `get_token_info()` interface delivering row, col, length, source text, and custom token category. | `gram.core.parser.core.Parser.get_token_info` |
| **Hookr Observer Pipeline** | Reactive hooks (`before_match`, `after_match`, `on_backtrack`, `on_error`) for decoupled IDE/LSP listeners. | `gram.core.parser.hookr` |
| **Combinator `ignore` Flag** | Explicit bypass of auxiliary wrapper nodes (e.g., entrypoint `Alt` wrappers) in tracing and AST generation. | `gram.core.combinators.base.Combinator` |
| **Pratt Expression Engine** | Modernized precedence parsing (`DualExpr`, `ArithmeticExpr`, `ConditionalExpr`) with ternary and binary chains. | `gram.core.combinators.expressions` |
| **Exhaustive Test Suite** | 45 comprehensive unit tests covering all combinator variants, return types, and failure states. | `tests/combinators/` |
| **English Technical Docs** | Fully updated documentation modules with practical usage guides and code examples. | `docs/en/01-Combinadores/` |

---

## Technical Documentation

Detailed guides and technical references are located in [`docs/en/01-Combinadores/`](docs/en/01-Combinadores/README.md):

- **[00. Combinators Overview & Reference Table](docs/en/01-Combinadores/README.md)**
- **[01. Token & Keyword Matching](docs/en/01-Combinadores/01-matching.md):** `MatchToken`, `MatchKeyword`, `MatchSymbol`, `MatchGroup`.
- **[02. Structural Combinators](docs/en/01-Combinadores/02-structural.md):** `Seq`, `Alt`, `Opt`, `Enclosed`.
- **[03. Repetition & Delimiters](docs/en/01-Combinadores/03-repetition.md):** `Many`, `Some`, `Sep`.
- **[04. Rule References & Token Storage](docs/en/01-Combinadores/04-rules-and-storage.md):** `Ref`, `RuleItem`, `Save`, `Load`, `Tag`.
- **[05. Lookahead & Control Flow](docs/en/01-Combinadores/05-lookahead-and-control.md):** `Peek`, `Until`, `If`, `ErrorCombinator`, `Pass`, `Tokenize`, `Query`.
- **[06. Fluent Validation](docs/en/01-Combinadores/06-fluent-validation.md):** `Req`, `SimpleCombinator`.
- **[07. Expression Parsing](docs/en/01-Combinadores/07-expressions.md):** `ChainL`, `ChainR`, `DualExpr`, `ArithmeticExpr`, `ConditionalExpr`.

---

## Unit Test Suite

Run the full combinator test suite with Python's built-in `unittest` runner:

```bash
python -m unittest discover -s tests
```

```text
.............................................
----------------------------------------------------------------------
Ran 45 tests in 2.276s

OK
```

The test suite systematically verifies:
1. Expected result structures (values, lists, tuples, dictionaries).
2. Combinator variations, arguments, and configuration options.
3. Strict error handling, fail modes, and recovery paths.

---

## Command Line Interface (CLI)

Gram provides a unified CLI via `gram` or `python -m gram`:

```bash
# Verify and audit a plugin with static AST analysis
gram check gram/plugins/source/expressions

# Install and inspect plugins
gram install gram/plugins/source/expressions
gram list

# Manage isolated virtual environments
gram env create
gram env list

# Compile a GLANG grammar file to Python
gram glang compile my_grammar.glang

# Generate and package a VS Code VSIX extension with LSP
gram vsix install
```

---

## Sample Projects

Explore real-world implementations built on Gram inside [`examples/`](examples/):

1. **[`CExample`](examples/CExample/):** A parser for an expressive subset of the C language, handling primitive types, pointers (`int*`), function prototypes, recursive loops, `#include` directives, symbol tables, and AST generation.
2. **[`sjson`](examples/sjson/):** A **Super JSON** compiler supporting variables (`let`/`var`), arithmetic expressions, comments (`//`), and file inheritance (`{ extend: "base.json" }`), compiling deterministically to RFC 8259 JSON.

---

## 🤝 Community & Collaboration

Interested in collaborating, reporting issues, or proposing new language features?
- Contact: 📫 **[kencv3002003@gmail.com](mailto:kencv3002003@gmail.com)**
- Contributions, issues, and discussions are welcome to continue advancing the framework.

---

## ☕ Support & Donations

Gram is developed to provide a modular, dependency-free compiler toolkit for the developer community. If you would like to support ongoing development:
- PayPal / Transfer: 💖 **[kencv3002003@gmail.com](mailto:kencv3002003@gmail.com)**

---

## 📄 License

Gram is distributed under the **Free Use & Commercial Output License** (see [LICENSE](LICENSE)).

- **Free of Charge:** You may freely use Gram for personal, educational, research, and commercial projects.
- **Commercial Output Allowed:** Products built with Gram (custom languages, parsers, compilers, DSL tools) belong entirely to their creators and may be commercialized without restrictions or royalties.
- **Core Immutability:** Gram core remains immutable to downstream redistribution; extensions and grammar enhancements should be authored via plugins or custom rules.
- **Non-Commercial Framework Resale:** The framework itself may not be rebranded, sublicensed, or resold as a standalone library package.
