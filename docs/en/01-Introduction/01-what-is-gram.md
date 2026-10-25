# What is Gram?

**Gram** (`gram`) is a pure-Python lexical analysis, parser combinator, and Abstract Syntax Tree (`AST`) generation framework designed to build Domain-Specific Languages (DSLs), transpilers, header/contract parsers, and full compiler frontends.

---

## 1. Core Philosophy & Goals

Gram is built around four concrete engineering goals:

### A. Strict Separation of Syntactic and Semantic Phases
In many compiler toolkits, grammar definitions become entangled with symbol tables, type checking, or runtime execution. Gram enforces a strict boundary:
- **Gram's Responsibility (Syntactic Frontend):** Scan source characters into tokens (`gram.core.lexer`), validate syntactic structure using declarative combinator rules (`gram.core.combinators`), report accurate syntax errors (`gram.errors`), and output a structured Abstract Syntax Tree (`gram.core.ast`).
- **Host Compiler's Responsibility (Semantic & Backend):** Traverse the generated `ASTRef` and `ASTNode` tree to resolve scopes, check types, fold constants, and emit target code (such as C, LLVM IR, or bytecode).

### B. Declarative Grammars in Pure Python
Rather than maintaining external `.g4` or BNF text files that require a separate code-generation build step, Gram grammars are written directly in Python:
- Production rules are declared as subclasses of `RuleItem`.
- Complex structures are composed from the available combinators (`Seq`, `Alt`, `Opt`, `Many`, `Some`, `Separator`, `Enclosed`, `Until`, `UntilIndent`, `Ref`, `Req`, `Preprocess`, `Convert`, `Expected`, etc.) and Top-Down Operator Precedence (Pratt) expression parsers (`ArithmeticExpr`, `ConditionalExpr`, `DualExpr`).
- Rule identifiers are automatically assigned non-colliding integer codes via `AutoCode` and `CodeManager`.

### C. Transactional Backtracking & Deepest-Failure Diagnostics
Hand-written recursive descent parsers and naive combinator libraries often struggle with ambiguous branches: either a failed branch corrupts parser state, or backtracking discards the inner error and reports a vague top-level mismatch.

Gram solves both problems:
- **Atomic Checkpoints (`Checkpoint`):** `parser.savepoint()` and `parser.restore()` snapshot and restore the physical cursor (`pos`), virtual lookahead cursor (`vpos`), bracket nesting depth (`bracket_depth`), diagnostic target stack, key-value token storage (`parser.storage`), positional tags (`parser.tk_tags`), and in-place token overrides (`parser.replace_token_at`).
- **Weighted Speculative Failure Scopes (`failure_scope`):** While exploring speculative branches (`Alt`, `Opt`, `Many`, `Some`, `Separator`), Gram stages candidate errors weighted by the cursor index (`parser.pos`) where they occurred. If top-level parsing fails before `Token.EOF`, `ASTAnalyzer` flushes the deepest staged failure so the user sees the exact token and rule that caused the syntax error.

### D. Multi-Language Frontend Isolation
Compilers often need to parse more than one syntax within the same process (for example, parsing a custom language alongside standard C headers or external contract files). Through `gram.sessions.Session`, Gram snapshots and swaps keyword tables (`MAP_KEYWORDS`), semantic word groups (`WordGroup`), custom operator symbols (`MAP_SYMBOLS`), and `gram.config` flags in place without cross-contaminating language definitions.

---

## 2. Processing Pipeline

```text
+-------------------------------------------------------------------------+
|                         Gram Syntactic Pipeline                         |
+-------------------------------------------------------------------------+

  Source Text (str | list[str])
        |
        v
  +-----------------------------------+
  | 1. Lexer (gram.core.lexer)        |  - Scans numbers, strings, symbols,
  |    Lexer(source).process()        |    keywords, comments, INDENT/DEDENT
  +-----------------------------------+
        |
        |  list[TokenType]
        v
  +-----------------------------------+
  | 2. Parser (gram.core.parser)      |  - Manages physical/virtual cursors,
  |    Parser(tokens)                 |    checkpoints, storage, and tags
  +-----------------------------------+
        |
        v
  +-----------------------------------+
  | 3. ASTAnalyzer & Visitor          |  - Evaluates RuleItem combinators,
  |    (gram.core.ast)                |    Pratt expressions, and RayTracing
  +-----------------------------------+
        |
        |  list[ASTRef | ASTNode]
        v
  Host Semantic Analyzer / Transpiler / Compiler Backend
```

---

## 3. Submodule Map

| Submodule | Import Path | Primary Exports |
| :--- | :--- | :--- |
| **Lexer** | `from gram import lexer` | `Lexer`, `Token`, `TokenType`, `CustomToken`, `TokenStream`, `words`, `Keyword`, `WordGroup` |
| **Parser** | `from gram import parser` | `Parser`, `ParseState`, `Checkpoint`, `TokenInfo`, `Hookr` |
| **Combinators** | `from gram import combinators` | `RuleItem`, `Ref`, `Seq`, `Alt`, `Opt`, `Many`, `Some`, `Separator`, `Enclosed`, `Until`, `UntilIndent`, `MatchToken`, `MatchKeyword`, `MatchGroup`, `MatchSeqSymbol`, `Item`, `Literal`, `Save`, `Load`, `Peek`, `Not`, `If`, `Skip`, `Tag`, `Tokenize`, `ErrorCombinator`, `Req`, `ArithmeticExpr`, `ConditionalExpr`, `DualExpr` |
| **AST** | `from gram import ast` | `ASTAnalyzer`, `ASTState`, `Visitor`, `ASTNode`, `ASTRef`, `ArrayNode`, `ItemNode`, `LiteralNode`, `Identifier`, `LiteralNumber`, `LiteralString`, `LiteralSymbol`, `ASTKeyword`, `RayTracing`, `Trace`, `TraceRecord` |
| **Rules** | `from gram import rules` | `AutoCode`, `SetCode`, `CodeManager`, `code_manager` |
| **Sessions** | `from gram import sessions` | `Session` |
| **Diagnostics & Errors** | `from gram import errors, utilities` | `Diagnostics`, `ErrorAction`, `Error`, `LexerError`, `ParserError`, `ASTError`, `GrammarError`, `SemanticError`, `StackError`, `StackInfo` |
| **Configuration** | `from gram import config` | Global lexer, parser, AST, error, and log configuration flags (`save()`, `load()`, `reset_to_defaults()`) |
| **VSIX (Beta)** | `from gram import vsix` | `VSIXAnalyzer`, `VSIXGenerator`, `ASTColorResolver`, `TokenSelector`, `LSPServer`, `declare_info`, `pack_vsix`, `up` |
