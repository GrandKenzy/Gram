# Structural Combinators

Structural combinators compose child combinators into ordered sequences, prioritized alternatives, optional elements, and delimiter-enclosed blocks.

---

## 1. `Seq` / `Sequence`

`Seq` (aliased as `Sequence`) evaluates child combinators in linear order. You can also compose sequences with the `+` operator (`comb1 + comb2`).

### Constructor
```python
Seq(*combinators: Combinator)
```

- Raises `EmptySequence` (`GrammarError`) at construction time if called with no arguments.

### Execution & Return Shape
- Saves a checkpoint (`"SEQ-Analysis"`) before evaluating children.
- For each child combinator:
  - If the child returns `None`, `Seq` restores the checkpoint, stages/flushes `SequenceElementMismatch` (unless a deeper failure was already staged), and returns `None`.
  - If the child returns `[]` (for example, an omitted `Opt`, a 0-match `Many`, `Peek`, or `Not`), `Seq` treats the step as successful and **omits** `[]` from the output list.
  - Otherwise, `Seq` appends the child's result to `results`.
- **Control-Flow Signals:**
  - `SkipFlowSignal` is caught by `Seq`: the sequence stops immediately and returns the `results` accumulated so far as a successful match.
  - `BacktrackSignal`, `BreakFlowSignal`, `CutFlowSignal`, and `AbortFlowSignal` are **not** caught by `Seq` and propagate to the enclosing combinator (`Alt`, `Many`, `Some`, `Separator`).
- **Return Value:** `list[Any]` of non-`[]` child results on success, or `None` on failure.

### Example
```python
from gram.core.combinators import MatchKeyword, MatchToken, Opt, Seq
from gram.core.lexer import Token

# Using Seq(...) or the + operator:
let_binding = Seq(
    MatchKeyword("let"),
    MatchToken(Token.IDENT),
    Opt(MatchToken(Token.ASSIGN) + MatchToken(Token.NUMBER)),
)
```

---

## 2. `Alt` (Alternative)

Evaluates candidate branches in order until the first branch returns a non-`None` result. You can also compose alternatives with the `|` operator (`comb1 | comb2`).

### Constructor
```python
Alt(*combinators: Combinator, ignore: bool = False)
```

- `ignore`: When `True`, `Visitor` does not increment nesting depth or record this `Alt` container itself in `RayTracing` (`ASTAnalyzer.is_valid_entrypoint` sets `ignore = True` on the root entrypoint `Alt`).
- Raises `EmptyAlternatives` (`GrammarError`) at construction time if called with no branches.

### Execution, Signals & Diagnostics
- Each branch is evaluated inside an isolated `analyzer.failure_scope()`.
- If a branch returns `None` (or raises `BacktrackSignal`), `Alt` restores the checkpoint, keeps the deepest failure candidate (`best_staged`) across rejected branches, and tries the next branch.
- If a branch raises `CutFlowSignal`:
  - `Alt` commits to that branch's failure candidate (discarding candidates from earlier branches), restores the checkpoint, stops trying remaining branches, and reports the failure.
- If all branches fail, `Alt` reports `best_staged` (or `NoAlternativeMatched` at the starting position if no branch staged a specific error) and returns `None`.
- **Return Value:** The exact return value of the first matching branch, or `None`.

### Example
```python
from gram.core.combinators import Alt, MatchToken
from gram.core.lexer import Token

atom = (
    MatchToken(Token.NUMBER)
    | MatchToken(Token.STRING)
    | MatchToken(Token.IDENT)
)
```

---

## 3. `Opt` (Optional)

Evaluates a single child combinator with $0..1$ cardinality inside `analyzer.failure_scope()`.

### Constructor
```python
Opt(combinator: Combinator)
```

- Raises `InvalidOptionalTarget` (`GrammarError`) at construction time if `combinator` is not a `Combinator` instance.

### Execution & Deep Partial Failures
- **Matched:** Returns the child combinator's result directly.
- **Clean Omission (0 tokens consumed):** If the child fails without advancing past `checkpoint.pos` (`candidate` is `None` or `candidate[0] <= checkpoint.pos`), `Opt` restores the checkpoint without reporting an error and returns `[]`.
- **Deep Partial Failure (`candidate[0] > checkpoint.pos`):** If the child consumed one or more tokens before failing inside a multi-step sub-rule (for example, matching `=` in `Opt(Seq(MatchToken(Token.ASSIGN), MatchToken(Token.NUMBER)))` and failing on the missing number), `Opt` restores the checkpoint, reports the deep failure candidate, and returns `None`.

### Example
```python
from gram.core.combinators import MatchToken, Opt, Seq
from gram.core.lexer import Token

optional_initializer = Opt(
    Seq(MatchToken(Token.ASSIGN), MatchToken(Token.NUMBER))
)
```

---

## 4. `Enclosed`

Matches an opening `Token`, an inner `content` combinator, and a closing `Token`.

### Constructor
```python
Enclosed(
    open: Token,
    content: Combinator,
    close: Token,
    skip_whitespace: bool = True,
    allow_empty: bool = True,
)
```

- `open` and `close` must be `Token` enum members; any other type raises `InvalidDelimiterType` (`GrammarError`) at construction time.
- `skip_whitespace`: When `True`, calls `parser.enter_delimiter()` / `parser.exit_delimiter()` and `parser.skip_whitespace()`, which increments `parser.bracket_depth` and skips `Token.NEWLINE`, `Token.INDENT`, and `Token.DEDENT` inside the delimiters.
- `allow_empty`: When `True`, if `close` immediately follows `open`, `content` is not evaluated and `Enclosed` returns `[]`. When `False`, empty delimiters (or a `content` match that consumes 0 tokens) fail with `EmptyEnclosedContent`.

### Return Value & Diagnostics
- **Match:** Returns the result of `content` (or `[]` when empty and `allow_empty=True`). The `open` and `close` tokens are consumed but not included in the returned value.
- **Failure:** Restores the initial checkpoint, reports one of `UnexpectedEOFBeforeOpenDelimiter`, `OpeningDelimiterMismatch`, `EmptyEnclosedContent`, `EnclosedContentMismatch`, `UnclosedDelimiterEOF`, or `ClosingDelimiterMismatch`, and returns `None`.

### Example
```python
from gram.core.combinators import Enclosed, Separator
from gram.core.lexer import Token

param_list = Enclosed(
    open=Token.LPAREN,
    content=Separator(values=[Token.IDENT], sep=Token.COMMA),
    close=Token.RPAREN,
    skip_whitespace=True,
    allow_empty=True,
)
```
