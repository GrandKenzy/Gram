# Repetition and Delimited Combinators

Repetition combinators evaluate loops, token scanning up to a stopping condition or indentation level, and delimiter-separated sequences.

---

## 1. `Many` (Zero-or-More)

Repeatedly evaluates `combinator` ($0..n$ times) while tokens remain in the stream (`not parser.empty()`).

### Constructor
```python
Many(combinator: Combinator)
```

### Execution & Loop Termination
Each iteration saves a checkpoint (`"MANY-Iteration"`) and runs `combinator` inside an isolated `analyzer.failure_scope()`:
- **Match:** Appends the result to `results`. If the child matched without advancing the cursor (`parser.pos == checkpoint.pos`), the loop terminates immediately to prevent infinite zero-width loops.
- **Mismatch (`res is None`):** Restores the iteration checkpoint and exits the loop.
  - If the failed iteration had already advanced past `checkpoint.pos` (`attempt.candidate[0] > checkpoint.pos`), that deep partial failure is staged and published (when not inside an outer `safe_mode`).
  - If the iteration failed cleanly at `checkpoint.pos`, the failure is discarded.
- **Signals:**
  - `BreakFlowSignal`: Restores the current iteration checkpoint and exits the loop cleanly.
  - `SkipFlowSignal`: If `parser.pos == checkpoint.pos`, restores the checkpoint and exits the loop; if the iteration had already advanced the cursor, keeps the consumed tokens and starts the next iteration.
- **Return Value:** Always returns `list[Any]` (`[]` when 0 iterations match).

### Example
```python
from gram.core.combinators import Many, MatchGroup, MatchToken, Seq
from gram.core.lexer import Token

declarations = Many(
    Seq(MatchGroup("types"), MatchToken(Token.IDENT))
)
```

---

## 2. `Some` (One-or-More)

Repeatedly evaluates `combinator` ($1..n$ times). Requires at least one successful iteration.

### Constructor
```python
Some(combinator: Combinator)
```

### Execution & Return Shape
- Shares the same iteration, `BreakFlowSignal`, `SkipFlowSignal`, and zero-width guard behavior as `Many`.
- **1 or more matches:** Returns `list[Any]` of matched results (and publishes any deeper partial failure from the final rejected iteration when not in `safe_mode`).
- **0 matches:** Restores the initial checkpoint, stages/publishes the first iteration's failure candidate (or `SomeMinimumNotMet`), and returns `None`.

### Example
```python
from gram.core.combinators import MatchToken, Some
from gram.core.lexer import Token

non_empty_idents = Some(MatchToken(Token.IDENT))
```

---

## 3. `Until`

Probes `target` at each cursor position and, while `target` does not match, consumes one token at a time and converts it via `analyzer.delegate_return_node(tok)`.

### Constructor
```python
Until(
    target: Combinator,
    *,
    consume_target: bool = False,
    max_tokens: int | None = None,
)
```

- `consume_target`:
  - `False` (default): Restores the probe checkpoint when `target` matches, leaving the `target` tokens unconsumed in the stream.
  - `True`: Keeps the `target` tokens consumed and appends (or extends, if `target` returned a `list`) `target`'s result into the returned list.
- `max_tokens`: Optional maximum number of single-token steps allowed before `target` must match.

### Return Value & Diagnostics
- **Match:** Returns `list[Any]` of delegated `ASTTokenNode` items consumed before `target` (plus `target`'s result when `consume_target=True`).
- **EOF or `max_tokens` reached without matching `target`:** Restores the initial checkpoint, reports `UntilTargetNotFound` (`GrammarError`), and returns `None`.

### Example
```python
from gram.core.combinators import MatchToken, Until
from gram.core.lexer import Token

# Collects tokens as AST nodes up to ';', leaving ';' at parser.pos
until_semicolon = Until(MatchToken(Token.SEMICOLON), consume_target=False)
```

---

## 4. `UntilIndent`

Consumes tokens one by one (converting each via `analyzer.delegate_return_node`) until encountering a `Token.INDENT` or `Token.DEDENT` token that satisfies `target`.

### Constructor
```python
UntilIndent(
    target: int | Literal["back", "front"] | str,
    *,
    consume_target: bool = False,
    allow_eof: bool = False,
    max_tokens: int | None = None,
)
```

- `target`:
  - `int` ($\ge 0$): Matches when a `DEDENT` reaches $\le \text{target}$ (from a higher initial level) or an `INDENT` reaches $\ge \text{target}$ (from a lower initial level), or equals `target`.
  - `"back"`: Matches a `Token.DEDENT` whose indentation value is lower than the indentation level active when `UntilIndent` started.
  - `"front"`: Matches a `Token.INDENT` whose indentation value is higher than the indentation level active when `UntilIndent` started.
  - Any negative integer or unrecognized string raises `InvalidUntilIndentTarget` (`GrammarError`) at construction time.
- `consume_target`: If `False` (default), stops before the matching `INDENT`/`DEDENT` token. If `True`, consumes it and appends its delegated node.
- `allow_eof`: If `True`, reaching `EOF` without seeing the target indentation token succeeds and returns `collected`.

### Return Value & Diagnostics
- **Match:** Returns `list[Any]` of delegated `ASTNode` instances.
- **Failure:** If `EOF` or `max_tokens` is reached without matching (and `allow_eof=False`), restores the initial checkpoint, reports `UntilIndentTargetNotFound` (`GrammarError`), and returns `None`.

### Example
```python
from gram.core.combinators import UntilIndent

# Consume tokens until dedenting below the current block level
body_tokens = UntilIndent("back", consume_target=False, allow_eof=True)
```

---

## 5. `Separator`

Parses delimiter-separated elements (such as `a, b, c`) with minimum/maximum element counts and optional trailing delimiter support.

> **Note:** The class is named `Separator` (there is no `Sep` alias in `gram.core.combinators`).

### Constructor
```python
Separator(
    values: Sequence[Any] | Combinator | Token | type[RuleItem] | str,
    sep: Combinator | Token | str = Token.COMMA,
    min: int = 0,
    max: int | None = None,
    allow_trailing: bool = True,
)
```

- **`values` normalization:** Accepts a single item or a sequence of:
  - `Token` enum members or valid `Token` name/symbol strings (wrapped in `MatchToken`).
  - `RuleItem` subclasses with `nodeable = True` (wrapped in `Ref(rule)`).
  - `Ref` instances that produce an `ASTRef` (`name` is non-empty, which is automatic when `rule.nodeable = True`). Passing a `Ref` with `name=None` and `nodeable=False` raises `UnnamedRefInSeparator` (`GrammarError`).
  - Any other `Combinator` instance.
  - Unrecognized strings raise `InvalidSeparatorTokenName`; unsupported types raise `UnsupportedSeparatorValue`.
- **`sep` normalization:** Accepts a `Combinator`, a `Token` enum member, or a `str` (resolved via `Token.from_string`, `MAP_SYMBOLS`, or `MatchSymbol`). Unsupported types raise `UnsupportedSeparatorDelimiter`.
- `min`: Minimum required elements (defaults to `0`).
- `max`: Optional cap on matched elements (`None` for unbounded).
- `allow_trailing`: When `True` (default), allows a trailing separator after the last matched element without requiring another element.

### Return Shape (`ArrayNode`)
Returns an `ArrayNode` (`gram.core.ast.nodes.ArrayNode`) on success, or `None` if fewer than `min` elements matched:
- `node.items`: `tuple[Any, ...]` of matched element nodes.
- `node.trailing`: `bool` (`True` if a trailing separator was consumed).
- Supports `len(node)`, `iter(node)`, `node[i]`, and `bool(node)`.

### Example
```python
from gram.core.combinators import Separator
from gram.core.lexer import Token

ident_list = Separator(
    values=[Token.IDENT],
    sep=Token.COMMA,
    min=1,
    allow_trailing=True,
)
```
