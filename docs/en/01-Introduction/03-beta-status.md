# Release Status & Stability (`v2.1.0`)

> **Current Version:** `2.1.0` (Stable Production Release)

Gram `2.1.0` is the active, stable release of the Gram Framework. All core subsystems—lexical analysis, transactional backtracking parser combinators, Pratt expression engines, Abstract Syntax Tree construction, isolated language sessions, and the native C AOT compiler with binary IR—are fully implemented, documented, and verified by an automated test suite of **300 passing unit, differential, and fuzz tests**.

---

## 1. Subsystem Maturity Matrix

The table below reflects the implementation and stability status of each subsystem in Gram `2.1.0`:

| Subsystem | Module | Status | Notes |
| :--- | :--- | :--- | :--- |
| **Lexer & Token Stream** | `gram.core.lexer` | **Stable** | Decimal, hex, bin, octal, float, and scientific numbers; prefixed strings (`u8`, `L`) and multiline docstrings; customizable operators with maximal munch; indentation tracking (`spaces`, `tabs`, `mixed`); and keywords/groups. Dual backend support (`python` or `c`). |
| **Parser & Checkpoints** | `gram.core.parser` | **Stable** | Fully transactional `Checkpoint` save and restore covering cursor `pos`, virtual cursor `vpos`, `bracket_depth`, `storage`, `tk_tags`, in-place token replacements, and hook callbacks. |
| **Syntactic Combinators** | `gram.core.combinators` | **Stable** | 32 native combinators with formal `CombinatorKind` signatures. Includes matching, sequence, ordered alternative, repetitions, delimiters, Pratt expression engines (`ArithmeticExpr`, `ConditionalExpr`, `DualExpr`), `SameLine`, `Until`, and `CaptureRaw`. |
| **AST & RayTracing** | `gram.core.ast` | **Stable** | Declarative `RuleItem` hierarchy with `nodeable` transparency, typed node generation (`ASTRef`, `ArrayNode`, `RawNode`, terminals), and diagnostic `RayTracing` (`"off"`, `"basic"`, `"detailed"`). |
| **Language Sessions** | `gram.sessions` | **Stable** | Isolated `Session` architecture owning lexer catalogs, parser instances, diagnostic settings, table exports, and AOT compilation without polluting global process state. |
| **Diagnostics & Errors** | `gram.utilities`, `gram.errors` | **Stable** | Structured error codes, snapshot logging, memory caps (`StackLimit`), and diagnostic hooks (`Diagnostics.hook_errors` with `ErrorAction.SUPPRESS_RAISE` / `ErrorAction.OMIT`). |
| **Native C Lexer & DiagnosticsLite** | `native/gram_lexer/` | **Stable** | Reentrant C11 lexical runtime with zero dynamic allocations per token, decoupled `DiagnosticsLite` engine, static table exporter, and differential verification. |
| **Native C Parser & Binary IR (GIR)** | `gram.core.parser.c_generator` | **Stable** | AOT C11 parser compiler with predictive switch dispatch, contiguous `GramAstArena` with undo log, Pratt expression generation in C, relocatable GIR 1.0 binary serialization, and unified driver. |
| **VS Code & LSP Tooling** | `gram.vsix` | **Stable** | Schema indexing (`VSIXAnalyzer`), ANSI color previews (`ASTColorResolver`), extension packaging (`pack_vsix`, `up`), and JSON-RPC stdio Language Server (`LSPServer`). |

---

## 2. Core Behavioral Guarantees

1. **Zero External Runtime Dependencies:**
   The Gram Python runtime requires only Python 3.12+ standard library modules. The generated C runtime requires standard C11 and compiles with any conforming C compiler (`gcc`, `clang`, `msvc`).
2. **Deterministic Syntactic Invariants:**
   - Checkpoint rollback is guaranteed: any speculative path failure in `Alt`, `Opt`, `Until`, `CaptureRaw`, or Pratt expressions completely rolls back all cursor mutations, tags, storage, and AST arena allocations.
   - Entrypoint contract: the root grammar entrypoint is defined via a `RuleItem` whose `entrypoint` is an `Alt` composed of `Ref` branches.
3. **Closed AOT Compilation Contract:**
   The C parser compiler strictly verifies every combinator in the grammar rule graph against `COMPILABLE_COMBINATOR_KINDS`. Non-compilable constructs (such as arbitrary Python callbacks or uncompilable combinators) are rejected upfront at export time, preventing false syntactic successes in native code.
