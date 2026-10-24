# Beta Status (`v2.0.0b1`)

> [!IMPORTANT]
> **Gram `2.0.0b1` is currently in Beta.**  
> While the core lexical, syntactic, checkpointing, session, and diagnostic engines are actively used in real compiler frontends (such as Easy-C) and verified by an automated test suite of 134 unit and fuzz tests, minor API adjustments and behavioral refinements may still occur before the final `2.0.0` stable release.

---

## 1. Subsystem Maturity Matrix

The table below reflects the factual implementation status of each subsystem in the current `2.0.0b1` codebase:

| Subsystem | Module | Status | Notes |
| :--- | :--- | :--- | :--- |
| **Lexer & Token Stream** | `gram.core.lexer` | **Beta (Stable Core)** | Full support for numbers (hex, bin, oct, float, scientific), strings, docstrings, custom symbols, `INDENT`/`DEDENT` tracking, `Keyword`, and `WordGroup`. |
| **Parser & Checkpoints** | `gram.core.parser` | **Beta (Stable Core)** | Transactional `Checkpoint` save/restore covering `pos`, `vpos`, `bracket_depth`, `storage`, `tk_tags`, and `replace_token_at` overrides. |
| **Syntactic Combinators** | `gram.core.combinators` | **Beta (Stable Core)** | All 28 combinators and Pratt expression parsers (`ArithmeticExpr`, `ConditionalExpr`, `DualExpr`) are implemented and covered by regression tests. |
| **AST & RayTracing** | `gram.core.ast` | **Beta (Stable Core)** | Supports `"off"`, `"basic"`, and `"detailed"` trace modes (`Trace`, `TraceRecord`, `backtracks`, `furthest`) and cursor-weighted failure staging. |
| **Language Sessions** | `gram.sessions` | **Beta (Stable Core)** | Snapshots and swaps global `MAP_KEYWORDS`, `WordGroupManager`, `MAP_SYMBOLS`, and `gram.config` in place across multiple language frontends. |
| **Diagnostics & Errors** | `gram.utilities`, `gram.errors` | **Beta (Stable Core)** | OSGDC 5-dimension error catalog, `StackError`, `StackInfo` hierarchical telemetry, and `Diagnostics.hook_errors` (`ErrorAction`). |
| **VSIX & LSP Tooling** | `gram.vsix` | **Beta (Experimental)** | Functional schema indexing (`VSIXAnalyzer`), 24-bit ANSI preview (`ASTColorResolver`), VS Code extension generator (`VSIXGenerator`), `.vsix` packager (`pack_vsix`, `up`), and stdio LSP server (`gram.vsix.lsp.server`). Expect ongoing improvements. |
| **High-Level `process()` Helper** | `gram.core.process` | **Incomplete Stub** | `gram.process()` currently initializes `Lexer` and `Parser` without executing or returning the AST. Do not rely on `gram.process()` in `2.0.0b1`; use `Lexer` + `Parser` (or `Session.tokenize()` + `Session.parse()`) directly. |

---

## 2. Important Behavioral Notes in `2.0.0b1`

1. **`config.ERROR_EXIT_ON_ERROR` Defaults to `True`:**
   Outside speculative combinator probes (`safe_mode()` / `failure_context()`), any unrecovered lexical, parser, or AST error prints a formatted OSGDC diagnostic box and terminates the process with `sys.exit(1)`.
   - If you are embedding Gram inside a test runner, REPL, or custom compiler driver that catches Python exceptions or inspects `parser._errors`, either set `config.ERROR_EXIT_ON_ERROR = False` or wrap execution in `with Diagnostics.hook_errors(...):` returning `ErrorAction.SUPPRESS_RAISE` or `ErrorAction.OMIT`.
2. **Pinning Versions in Production:**
   Because the `main` branch receives ongoing `2.0.0b*` updates, projects requiring deterministic builds should pin Gram to a specific Git tag (such as `tag = "v2.0.0b1"` in `vnma.toml` or `git checkout v2.0.0b1`).
