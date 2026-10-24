# Lookahead, Control Signals, and Tagging Combinators

These combinators perform zero-width assertions (`Peek`, `Not`), conditional branching (`If`), flow-control signaling (`Skip`), token position tagging (`Tag`), token fusion (`Tokenize`), and diagnostic error capture (`ErrorCombinator`).

---

## 1. `Peek` (Positive Lookahead)

Evaluates `combinator` inside an isolated `analyzer.failure_scope()` and always restores the checkpoint in a `finally` block so the cursor never advances.

### Constructor
```python
Peek(combinator: Combinator)
```

### Return Shape & Diagnostics
- **Child matches (`res is not None`):** Restores the checkpoint and returns `[]` (so enclosing `Seq` combinators succeed without adding a node).
- **Child fails (`res is None`):** Restores the checkpoint, reports `scope.candidate` (or `PositiveLookaheadFailed` if no candidate was staged), and returns `None`.

### Example
```python
from gram.core.combinators import MatchToken, Peek
from gram.core.lexer import Token

assert_next_is_ident = Peek(MatchToken(Token.IDENT))
```

---

## 2. `Not` (Negative Lookahead)

Asserts that `combinator` does **not** match at `parser.pos`. Evaluates `combinator` inside an isolated `analyzer.failure_scope()` and always restores the checkpoint.

### Constructor
```python
Not(combinator: Combinator)
```

### Return Shape & Diagnostics
- **Child fails (`res is None`):** Discards the child's internal failure, restores the checkpoint, and returns `[]`.
- **Child matches (`res is not None`):** Restores the checkpoint, reports `NegativeLookaheadFailed` (`GrammarError`), and returns `None`.

### Example
```python
from gram.core.combinators import MatchKeyword, Not

not_return = Not(MatchKeyword("return"))
```

---

## 3. `If` (Conditional Branching)

Evaluates one or more `conditions` speculatively inside `analyzer.failure_scope()` and branches to `ok` or `fail`.

### Constructor
```python
If(
    conditions: Sequence[Combinator] | Combinator,
    ok: Sequence[Combinator] | Combinator | None = None,
    fail: Sequence[Combinator] | Combinator | None = None,
    *,
    restore: bool = False,
)
```

- Passing a `list` or `tuple` for `ok` or `fail` automatically wraps it in `Seq(*branch)`.
- Passing an empty sequence for `conditions` raises `EmptyIfConditions` (`GrammarError`) at construction time.

### Return Shapes
- **When all `conditions` succeed:**
  - `restore=False` (default): Keeps the condition tokens consumed.
    - If `ok` is provided: evaluates `ok` and returns `[*cond_results, ok_res]` (or restores the initial checkpoint and returns `None` if `ok` fails).
    - If `ok is None`: returns `cond_results`.
  - `restore=True`: Restores the initial checkpoint before running `ok`.
    - If `ok` is provided: returns `analyzer.visitor(self.ok)`.
    - If `ok is None`: returns `cond_results`.
- **When any condition fails:** Restores the initial checkpoint.
  - If `fail` is provided: returns `analyzer.visitor(self.fail)`.
  - If `fail is None`: reports the condition scope's failure candidate (or `IfConditionNotMet`) and returns `None`.

### Example
```python
from gram.core.combinators import If, MatchKeyword, MatchToken
from gram.core.lexer import Token

branch = If(
    conditions=MatchKeyword("let"),
    ok=MatchToken(Token.IDENT),
    fail=MatchToken(Token.NUMBER),
)
```

---

## 4. `Skip` and Control-Flow Signals

`Skip(signal)` raises `signal()` when visited. Signals inherit from `ControlFlowSignal` (`gram.core.combinators.signals`).

### Constructor
```python
Skip(signal: type[ControlFlowSignal])
```

### Signal Reference (`gram.core.combinators.signals`)

| Signal Class | Handled By | Effect |
| :--- | :--- | :--- |
| `SkipFlowSignal` | `Seq`, `Many`, `Some`, `Separator` | In `Seq`: stops the sequence early and returns the nodes collected so far. In `Many`/`Some`: if `parser.pos == checkpoint.pos`, restores checkpoint and exits loop; if tokens were consumed in the current iteration, keeps them and continues to the next iteration. In `Separator`: restores the separator checkpoint and exits the loop. |
| `BreakFlowSignal` | `Many`, `Some`, `Separator` | Propagates through `Seq`. Restores the current iteration/separator checkpoint and exits the repetition loop cleanly. |
| `BacktrackSignal` | `Alt` | Propagates through `Seq`. Rejects the current `Alt` branch, restores `Alt`'s checkpoint, and tries the next alternative. |
| `CutFlowSignal` | `Alt` (via `ASTState.failure_scope`) | Propagates through `Seq`. Commits to the current `Alt` branch: carries the branch's `_failure_candidate`, restores `Alt`'s checkpoint, and aborts `Alt` without trying remaining branches. |
| `AbortFlowSignal` | Caller / top-level | Propagates uncaught through `Seq` and `Alt` to abort parsing immediately. |

### Example
```python
from gram.core.combinators import Alt, MatchKeyword, MatchToken, Seq, Skip
from gram.core.combinators.signals import BacktrackSignal, CutFlowSignal, SkipFlowSignal
from gram.core.lexer import Token

# Early exit in Seq: returns [LiteralNumber(1)] and stops at pos=1
early_seq = Seq(
    MatchToken(Token.NUMBER),
    Skip(SkipFlowSignal),
    MatchToken(Token.NUMBER),
)

# Force Alt to abandon branch 1 and try branch 2
alt_backtrack = Alt(
    Seq(MatchKeyword("int"), Skip(BacktrackSignal)),
    Seq(MatchKeyword("int"), MatchToken(Token.IDENT)),
)
```

---

## 5. `Tag`

Attaches, removes, or asserts string tags on the current token index (`parser.pos`) inside the checkpoint-safe dictionary `parser.tk_tags: dict[int, frozenset[str]]`. Never consumes tokens (`parser.pos` does not change).

### Constructor & Classmethods
```python
Tag(tag: str, mode: Literal["add", "remove", "exists", "not_exists"] = "add")

Tag.add(tag: str) -> Tag
Tag.remove(tag: str) -> Tag
Tag.exists(tag: str) -> Tag
Tag.not_exists(tag: str) -> Tag   # also aliased as Tag.unexists(tag)
```

### Return Value & Diagnostics
- **Success:** Returns the `TokenType` at `parser.pos` without advancing `parser.pos`.
- **Failure / EOF:**
  - Reports `TagUnexpectedEOF` (`ParserError`) if the stream is empty.
  - Reports `RequiredTagMissing` (`GrammarError`) if `mode == "exists"` and `tag` is not present at `parser.pos`.
  - Reports `ForbiddenTagPresent` (`GrammarError`) if `mode == "not_exists"` and `tag` is present at `parser.pos`.

---

## 6. `Tokenize`

Evaluates a sequence of token-producing child combinators (`Seq(*combinators)`) and merges all matched tokens into a single `TokenType` whose `.token` is a `CustomToken(name=..., value=combined_value)`.

### Constructor
```python
Tokenize(
    *combinators: Combinator,
    token_name: str = "CustomToken",
    name: str | None = None,
    join_char: str = "",
)
```

- If `name` is provided, it overrides `token_name`.
- Raises `EmptyTokenizeCombinators` (`GrammarError`) at construction time if called with no child combinators.

### Return Value & Diagnostics
- Every child result must be a `TokenType`, an object with a `.token: TokenType` attribute (such as `ASTTokenNode`), or a nested `list`/`tuple` of those. If any child produces a non-token object (such as `ASTRef`), `Tokenize` restores the checkpoint, reports `InvalidTokenizeElement` (`GrammarError`), and returns `None`.
- **Match:** Returns a synthesized `TokenType` at the line and column of the first matched token, with `.value` joined by `join_char`.

### Example
```python
from gram.core.combinators import MatchToken, Tokenize
from gram.core.lexer import Token

decorator_tok = Tokenize(
    MatchToken(Token.AT),
    MatchToken(Token.IDENT),
    name="DECORATOR",
    join_char="",
)
```

---

## 7. `ErrorCombinator`

Pops and returns previously recorded `Error` instances from the first non-empty error list among `analyzer._errors`, `parser._errors`, or `StackError.__err__`.

### Constructor
```python
ErrorCombinator(length: int = 1)
```

- `length=0`: Pops all recorded errors.
- `length=N` ($N > 0$): Pops up to the `N` most recent errors.

### Return Shape & Diagnostics
- **When errors exist:** Removes the selected errors from the active error list and returns them as `list[errors.Error]` in reverse chronological order (most recent first).
- **When no errors exist:** Reports `NoErrorsToCatch` (`GrammarError`) and returns `None`.

> **Note:** To record errors into `_errors` without terminating the process before `ErrorCombinator` runs, either set `config.ERROR_EXIT_ON_ERROR = False` or register an error hook returning `ErrorAction.SUPPRESS_RAISE`.
