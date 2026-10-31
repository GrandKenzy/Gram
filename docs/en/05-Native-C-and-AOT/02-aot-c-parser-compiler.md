# Ahead-Of-Time (AOT) C Parser Compiler

> **Module:** `gram.core.parser.c_generator`  
> **Status:** Stable (Version `2.1.0`)

The Gram Ahead-Of-Time (AOT) compiler analyzes a `Session`'s grammar starting from its root `entrypoint` rule, computes static lookahead sets, and generates fully standalone, recursive-descent C11 parser and AST files (`gram_parser.h`, `gram_parser.c`, `gram_ast.h`, `gram_ast.c`).

---

## 1. The Closed Compilation Contract

Gram enforces a strict semantic contract to guarantee that every grammar prototype verified in Python behaves identically when compiled to native C.

### Compilability Verification
During grammar graph traversal, every combinator is validated against `COMPILABLE_COMBINATOR_KINDS` (`gram.core.combinators.kinds`):
- Declarative combinators (`MatchToken`, `MatchKeyword`, `MatchGroup`, `MatchSeqSymbol`, `Literal`, `Seq`, `Alt`, `Opt`, `Many`, `Some`, `Until`, `CaptureRaw`, `Enclosed`, `Separator`, `SameLine`, Pratt expressions) are compiled directly into optimized C branches.
- Non-compilable combinators (such as `Convert`, arbitrary Python lambda validators, or external unannotated classes) are rejected immediately at export time with `GrammarCompilerError("NonCompilableCombinator")`.
- `Ref` targets must be valid `RuleItem` subclasses or `Combinator` instances; invalid targets raise `GrammarCompilerError("InvalidRefTarget")`.
- Dynamic regular expressions in `MatchSeqSymbol` raise `GrammarCompilerError("DynamicRegexInSymbolUnsupported")`.

---

## 2. Predictive Alternative Dispatch (`switch`)

In standard PEG parsers, evaluating alternatives (`Alt`) requires sequential linear backtracking across each branch.

The Gram C generator performs static `first_set` lookahead analysis across all branches of each `Alt`:
1. **Token Kind Partitioning:** Branches with disjoint first tokens are dispatched using a single C `switch (tok->kind)`.
2. **Keyword First-Character Partitioning:** When multiple branches begin with `GRAM_TOKEN_KEYWORD`, the generator emits a secondary nested `switch (source[tok->start])` inspecting the first character of the keyword (e.g. `'f'` for `fn`, `'l'` for `let`).
3. **Conservative Backtracking Fallback:** If lookaheads overlap or an opaque branch exists, the generator falls back to PEG ordered trials for that specific subset, preserving grammar semantics while eliminating up to 90% of redundant branch evaluations.

---

## 3. Contiguous AST Arena with Transactional Rollback

The generated C parser constructs AST nodes inside a preallocated contiguous arena (`GramAstArena`), avoiding individual heap allocations:

```c
typedef struct GramAstNode {
    uint16_t kind;          /* Node kind (GRAM_AST_RULE_*, GRAM_AST_RAW, etc.) */
    uint16_t flags;         /* Node classification flags */
    uint32_t symbol_id;     /* Identifier in the rule/symbol string table */
    uint32_t token_start;   /* Index of the first token in the token buffer */
    uint32_t token_count;   /* Number of tokens covered by this node */
    uint32_t first_child;   /* Arena index of the first child node */
    uint32_t next_sibling;  /* Arena index of the next sibling node */
    uint32_t last_child;    /* Arena index of the most recently attached child */
} GramAstNode;
```

### Transactional Undo Log (`GramAstUndo`)
Backtracking in a tree requires undoing child attachments made to existing surviving nodes.
- **`gram_parser_save(p)`:** Saves an $O(1)$ checkpoint containing the current cursor, arena count, and undo log head.
- **`gram_parser_restore(p, cp)`:** Performs an $O(k)$ rollback across the $k$ link mutations performed during the speculative attempt, restoring original sibling links and shrinking `arena->count`.
- **Memory Safety:** If `gram_ast_arena_alloc()` fails due to out-of-memory, the parser sets `arena->has_error` and unwinds cleanly, preventing corrupted trees.

---

## 4. Pratt Expression Engines in C

Pratt expression combinators (`DualExpr`, `ArithmeticExpr`, `ConditionalExpr`) compile into standalone recursive-descent Pratt parsing functions (`gram_parse_expr_*`):
- Operator binding powers are pre-calculated as static tables.
- Prefix and infix operators are resolved with direct token comparisons.
- Grouping parentheses and `refs_before_grouping` precedence are natively supported.
- Unary and binary nodes are emitted as `GRAM_AST_EXPR_UNARY` and `GRAM_AST_EXPR_BINARY`.

---

## 5. Grammar Fingerprinting (`grammar_id`)

The manifest and GIR output embed a 64-bit FNV-1a fingerprint (`grammar_id`):
- Calculated from the topological order of rule names, rule combinatorial structures, Pratt binding powers, and the session's complete lexical catalog (keywords, groups, symbols, and exported table hashes).
- Changing either a rule body or a session keyword alters `grammar_id`, preventing outdated binary IR from being processed by mismatched compilers.
