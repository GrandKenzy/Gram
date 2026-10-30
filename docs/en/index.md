# Gram Framework Documentation

> **Version:** `2.1.0` (Stable)
> **Runtime:** Pure Python 3.12+ (Zero external runtime dependencies)

Welcome to the official English documentation for **Gram**, a pure-Python lexical analysis, parser combinator, and Abstract Syntax Tree (`AST`) generation framework for building Domain-Specific Languages (DSLs), transpilers, and compiler frontends.

---

## Documentation Index

### [01. Introduction](./01-Introduction/index.md)
High-level overview of the framework, its design goals, installation instructions, and current stable release.
- **[01. What is Gram?](./01-Introduction/01-what-is-gram.md)** — Core architecture, strict separation between syntactic and semantic phases, and design objectives.
- **[02. Installation](./01-Introduction/02-installation.md)** — Installing Gram via **VNMA** (`vnma.toml`, Git branches, tags, and live editable links) or directly via Git and `PYTHONPATH`.
- **[03. Historical Beta Status](./01-Introduction/03-beta-status.md)** — Archived stability matrix for the pre-`2.1.0` beta cycle.

### [02. Combinators](./02-Combinators/index.md)
Reference guide for all available syntactic combinators in `gram.core.combinators`, execution contracts, and Pratt expression engines.
- **[01. Matching Combinators](./02-Combinators/01-matching.md)** — `MatchToken`, `MatchKeyword`, `MatchGroup`, `MatchSeqSymbol`, and `generador_expr`.
- **[02. Structural Combinators](./02-Combinators/02-structural.md)** — `Seq` (`+`), `Alt` (`|`), `Opt`, and `Enclosed`.
- **[03. Repetition Combinators](./02-Combinators/03-repetition.md)** — `Many`, `Some`, `Until`, `UntilIndent`, and `Separator`.
- **[04. Rules & Storage](./02-Combinators/04-rules-and-storage.md)** — `RuleItem`, `Ref`, `Item`, `Literal`, `Save`, and `Load`.
- **[05. Lookahead & Control](./02-Combinators/05-lookahead-and-control.md)** — `Peek`, `Not`, `If`, `Skip`, `Tag`, `Tokenize`, and `ErrorCombinator`.
- **[06. Fluent Token Validation](./02-Combinators/06-fluent-validation.md)** — `Req` fluent validation and in-place token transformation chains.
- **[08. Preprocessing and Expectations](./02-Combinators/08-preprocessing-and-expectations.md)** — `Preprocess`, `Convert`, and `Expected` for validation, logical conversions, and strict assertions.
- **[07. Pratt Expressions](./02-Combinators/07-expressions.md)** — `ArithmeticExpr`, `ConditionalExpr`, `DualExpr`, `bind_left`, and `bind_right`.

### [03. Usage Guide](./03-Usage/index.md)
Practical guides for structuring language frontends, managing multi-language sessions, handling diagnostics, and generating editor tooling.
- **[01. Keywords & Lexicon Setup](./03-Usage/01-keywords-and-lexicon.md)** — Registering `Keyword` entries, `WordGroup` catalogs, custom symbols, and lexer flags.
- **[02. RuleItem & `nodeable`](./03-Usage/02-ruleitem-and-nodeable.md)** — Defining production rules with `RuleItem`, `AutoCode`/`SetCode`, root entrypoints, and how `nodeable` controls `ASTRef` wrapping vs. node inlining.
- **[03. Language Sessions](./03-Usage/03-sessions.md)** — Isolating and switching between multiple language frontends using `gram.sessions.Session`.
- **[04. Diagnostics & Error System](./03-Usage/04-diagnostics-and-errors.md)** — Hierarchical telemetry with `Diagnostics`, OSGDC error codes, `StackError`, and non-invasive error hooks (`ErrorAction`).
- **[05. VSIX & Editor Tooling](./03-Usage/05-vsix-and-editor-tooling.md)** — Declarative editor maps on `RuleItem`, `TokenSelector`, ANSI TrueColor previews, VS Code extension generation, and the built-in LSP server.
