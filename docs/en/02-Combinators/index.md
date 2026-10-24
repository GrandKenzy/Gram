# Gram Syntactic Combinators

Syntactic combinators are the building blocks of the **Gram** parser (`gram.core.combinators`). Each combinator subclasses `Combinator` and defines how tokens from `Parser` are matched, repeated, branched, or converted into Abstract Syntax Tree (`ASTNode`) instances.

Combinators integrate with:
- **Checkpoints (`parser.savepoint` / `parser.restore`):** Failed branches restore the token cursor, virtual cursor (`vpos`), bracket depth, `parser.storage`, `parser.tk_tags`, and in-place token replacements (`parser.replace_token_at`).
- **Isolated Failure Scopes (`analyzer.failure_scope`):** Speculative probes (`Alt`, `Opt`, `Many`, `Some`, `Separator`, `Until`, `If`, `Not`, `Peek`, and expression atoms) isolate local failure candidates so discarded branches do not leak stale diagnostics.
- **RayTracing (`analyzer.raytracing`):** Controlled via `ASTAnalyzer(..., trace="off" | "basic" | "detailed")`.

---

## Combinator Categories

| Category | Combinators | Purpose |
| :--- | :--- | :--- |
| **[01. Matching](./01-matching.md)** | `MatchToken`, `MatchKeyword`, `MatchGroup`, `MatchSymbol` / `MatchSeqSymbol`, `generador_expr` | Consume a single token by `Token` type, keyword string, `WordGroup`, or regex pattern. |
| **[02. Structural](./02-structural.md)** | `Seq` (`Sequence`), `Alt`, `Opt`, `Enclosed` | Ordered sequences (`+`), prioritized alternatives (`\|`), optional clauses ($0..1$), and bracket-delimited blocks. |
| **[03. Repetition](./03-repetition.md)** | `Many`, `Some`, `Until`, `UntilIndent`, `Separator` | $0..n$ and $1..n$ loops, token scanning up to a target combinator or indentation level, and delimited lists (`ArrayNode`). |
| **[04. Rules & Storage](./04-rules-and-storage.md)** | `RuleItem`, `Ref`, `Item`, `Literal`, `Save`, `Load` | Declarative production rules, rule references (`ASTRef`), atomic token sequences (`ItemNode`), primitive literals (`LiteralNode`), and `parser.storage` operations. |
| **[05. Lookahead & Control](./05-lookahead-and-control.md)** | `Peek`, `Not`, `If`, `Skip`, `Tag`, `Tokenize`, `ErrorCombinator` | Zero-width positive/negative lookahead, conditional branching, control-flow signals, token position tagging (`parser.tk_tags`), composite tokens, and error capture. |
| **[06. Fluent Validation](./06-fluent-validation.md)** | `Req` | Chained token value validations and in-place transformations on a cloned token before AST delegation. |
| **[07. Pratt Expressions](./07-expressions.md)** | `ArithmeticExpr`, `ConditionalExpr`, `DualExpr` | Top-Down Operator Precedence (Pratt) expression parsing for prefix unary (`ASTUnaryOp`) and infix binary (`ASTBinaryOp`) operators. |

---

## Core Execution Contract

Every combinator subclasses `Combinator` (`gram.core.combinators.base.Combinator`) and implements:

```python
def parse(self, analyzer: ASTAnalyzer) -> Any:
    ...
```

### Return Value Conventions
- **Matched Node(s):** Advances `parser.pos` past the consumed tokens and returns an `ASTNode`, a `list` of nodes, or a `TokenType`.
- **Clean Omission (`[]`):** Returned by `Opt` (when omitted at its starting position), `Many` (when 0 iterations match), `Peek`, `Not`, and empty `Enclosed(..., allow_empty=True)`. Inside `Seq`, a `[]` result is treated as a successful step without appending an empty list to `Seq`'s output list.
- **Failure (`None`):** Restores `parser` to the combinator's checkpoint and stages or reports a diagnostic error.

### Operator Overloads on `Combinator`
- `comb_a + comb_b` builds a flattened `Seq(comb_a, comb_b)`.
- `comb_a | comb_b` builds a flattened `Alt(comb_a, comb_b)`.

### Tracing Modes (`ASTAnalyzer(..., trace=...)`)
- `trace="off"`: Bypasses `RayTracing` and does not register checkpoint hooks on `parser.hookr`.
- `trace="basic"` (default): Records evaluated combinators (` ignore=False`) and nesting depth in `raytracing.trace`, rule names in `raytracing.paths`, and per-rule branches in `raytracing.branches`.
- `trace="detailed"`: Also records a `TraceRecord` (`combinator`, `depth`, `start`, `end`, `outcome`, `exception_type`) for each evaluated combinator and tracks rollback positions in `raytracing.backtracks` / `raytracing.furthest`. Format with `raytracing.detailed()`.
