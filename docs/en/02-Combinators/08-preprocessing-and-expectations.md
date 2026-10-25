# Preprocessing, Conversions, and Expectations

These combinators validate the current token, register logical identifier
conversions, and express strict zero-width conditions without consuming tokens.

## `Preprocess`

> [!WARNING]
> **`Preprocess` is experimental and dangerous.** The callback runs inside
> the analysis, and responsibility for its effects belongs entirely to the
> user. Gram cannot know whether custom logic respects your lexer, symbol
> tables, conversions, or AST model. `Preprocess` gives you complete freedom
> to inspect and coordinate analysis, but it can also violate parser invariants
> and produce results that are difficult to debug.

`Preprocess` is not a sandbox or an automatic second lexer phase: it is an
extension point executed on the current effective token. Gram's only strict
guarantees are that the callback must return exactly `True` and must not move
`parser.pos`. Any external state you modify—files, globals, lexer registries,
or external services—must be managed and rolled back by your own code.

### Tools for keeping control

Before using `Preprocess` to change a frontend's behavior, combine it with
mechanisms that make state lifetime explicit:

- **Checkpoints and rollback:** create `parser.savepoint("name")` before a
  delicate operation and call `parser.restore(checkpoint)` to roll back. The
  rollback covers parser-tracked state—cursor, conversions, tags, storage,
  and token replacements—but it cannot undo external effects performed by the
  callback.
- **`failure_scope()` / `safe_mode()`:** group speculative validations so a
  diagnostic is not published immediately when `Alt`, `Opt`, or another
  control combinator may still discard the attempt.
- **Sessions (`gram.sessions.Session`):** isolate different language
  configurations. Configure the lexer inside a session and use
  `clear_global()`, `init()`, `migrate()`, and `load()` to switch frontends
  without leaking lexer registries between files.
- **Explicit conversions:** use `parser.export_conversions()` and
  `parser.import_conversions()` to share only the conversions you intend. To
  preserve them between files, pass a `ConversionState`; without one, each
  parse starts isolated.
- **`Save` and `Load` with dedicated storage:** keep dynamic data in a mapping
  owned by your frontend instead of always relying on `parser.storage`. The
  parser can track that mapping and include it in checkpoints.
- **`Expected` and `MatchToken`:** express invariants declaratively as
  combinators. This reduces the manual validation that the callback must do
  and lets the parser report failures consistently.
- **Diagnostics and `RayTracing`:** during development, disable immediate
  error exit when you need to inspect multiple failures, and use detailed
  tracing to observe restored positions, branches, and analysis outcomes.

### Practical rules

1. Keep the callback short, deterministic, and free of I/O.
2. Read the received token and avoid `consume()`, `advance()`, or any call that
   changes `parser.pos`.
3. Do not mix global lexer registries with file-specific state; use `Session`
   or an explicit context structure.
4. If the callback mutates state Gram does not know about, define your own
   snapshot and rollback beside the parser checkpoint.
5. Always test success, rejection, exception, and backtracking paths.

```python
from gram.core.combinators import MatchToken, Preprocess, Seq
from gram.core.lexer import Token

Preprocess(func)
```

The callback receives `(analyzer, token)` and must return exactly `True`:

```python
def valid_name(analyzer, token):
    return str(token.value).isidentifier()

rule = Seq(Preprocess(valid_name), MatchToken(Token.IDENT))
```

`False`, `None`, any other return value, or an exception produces an error.
`Preprocess` must not move the parser cursor.

## `Convert`

```python
from gram.core.combinators import Convert, MatchToken, Seq
from gram.core.lexer import Token

Convert("Bunga", Token.DOT)
Convert("Bunga", Token.DOT, scope=True)
```

The conversion is exact and only applies to identifiers with the specified
value.

- `scope=False`: converts only the current token.
- `scope=True`: registers the conversion in the parser, so future tokens are
  resolved logically with the new type.

The physical token stream is not traversed or rewritten in full. `MatchToken`
consults the logical type:

```python
Seq(
    Convert("Bunga", Token.DOT, scope=True),
    MatchToken(Token.DOT),
)
```

Scoped conversions are part of parser checkpoints and are reverted during
backtracking.

### Sharing conversions between files

Active conversions can be exported as an independent copy:

```python
exported = parser_a.export_conversions()
parser_b.import_conversions(exported)
```

To share them directly across `Session.parse()` calls, use `ConversionState`:

```python
state = session.new_conversion_state()

session.parse(tokens_a, "a.c", conversion_state=state)
session.parse(tokens_b, "b.c", conversion_state=state)
```

Without `conversion_state`, each file starts with a fresh conversion state. A
state can be cloned or cleared:

```python
isolated = state.clone()
state.clear()
```

The external state is updated only when parsing completes successfully.

## `Expected`

All variants are zero-width assertions:

```python
from gram.core.combinators import Expected

Expected.newline()
Expected.count(3)
Expected.ncount(2)
Expected.indent(4)
```

- `newline`: the next significant token must be on a later line.
- `count`: exactly `n` tokens must remain before `EOF`.
- `ncount`: exactly `n` tokens must not remain before `EOF`.
- `indent`: the active indentation column must be `n`.

No variant consumes tokens.
