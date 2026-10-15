# Gram Syntactic Combinators

Syntactic combinators are the foundational building blocks of the **Gram Framework** parser engine. Each combinator encapsulates a declarative strategy for evaluating, matching, repeating, or transforming tokens from the lexer stream into Abstract Syntax Tree (AST) nodes.

Combinators are composable, reentrant, and integrate natively with the parser's transactional backtracking engine (`savepoint` and `restore`) as well as the `RayTracing` telemetry subsystem.

---

## Combinator Categories

The framework categorizes combinators by syntactic function:

| Category | Combinators | Primary Purpose |
| :--- | :--- | :--- |
| **[Matching](./01-matching.md)** | `MatchToken`, `MatchKeyword`, `MatchSymbol`, `MatchGroup`, `MatchSeqSymbol` | Atomic validation and consumption of specific tokens, keywords, symbols, or semantic word groups. |
| **[Structural](./02-structural.md)** | `Seq`, `Alt`, `Opt`, `Enclosed` | Ordering, alternatives, optional cardinality, and delimited bracket/parenthesis grouping. |
| **[Repetition](./03-repetition.md)** | `Many`, `Some`, `Until`, `UntilIndent`, `Separator` / `Sep` | Loops ($0..n$, $1..n$), delimiter consumption, and separated lists with trailing support. |
| **[Rules & Storage](./04-rules-and-storage.md)** | `Ref`, `Item`, `Literal`, `Save`, `Load` | Production rule references, atomic token sequences, literals, and session-level parser storage. |
| **[Lookahead & Control](./05-lookahead-and-control.md)** | `Peek`, `Not`, `If`, `Skip`, `Tag`, `Tokenize`, `ErrorCombinator` | Zero-width positive/negative lookahead, branching, control signals, token tagging, and error capture. |
| **[Fluent Validation](./06-fluent-validation.md)** | `Req` | Fluent constraints (case, bounds, prefix/suffix) and in-place transformations on matched tokens. |
| **[Pratt Expressions](./07-expressions.md)** | `ArithmeticExpr`, `ConditionalExpr`, `DualExpr` | Precedence-climbing binary and unary expression parsers with parenthesis overrides. |

---

## Core Execution Semantics

Every combinator subclasses the base `Combinator` class and implements:

```python
def parse(self, analyzer: ASTAnalyzer) -> Any:
    ...
```

- **Success**: Advances the physical cursor `parser.pos` past consumed tokens and returns an AST node, a list of nodes, or a metadata token.
- **Mismatch**: Restores the cursor position to its initial checkpoint and returns `None` (or `[]` in optional contexts such as `Opt`, `Many`, `Peek`, `Not`).
- **Telemetry & Tracing**: If not flagged with `ignore=True`, evaluations are tracked in `RayTracing`, recording visited paths and execution branches.
