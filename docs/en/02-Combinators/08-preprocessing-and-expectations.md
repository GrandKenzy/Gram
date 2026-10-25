# Preprocessing, Conversions, and Expectations

These combinators validate the current token, register logical identifier
conversions, and express strict zero-width conditions without consuming tokens.

## `Preprocess`

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
