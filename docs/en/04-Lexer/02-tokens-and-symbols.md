# Token Catalog & Symbol Dispatch

Gram represents all syntactic units through two central constructs:
- **`Token` (`Enum`):** The formal, immutable enumeration of all recognized lexical token types.
- **`TokenType` (`class`):** The concrete lexeme container emitted by `Lexer`, encapsulating the formal token type, source value, coordinates, and lexical flags.

---

## 1. The `Token` Enumeration

All standard tokens reside in `gram.core.lexer.tokens.Token`. They are organized into 11 logical categories:

### 1. Structure and Flow
| Token Enum Member | Typical Role | Emitted Value |
| :--- | :--- | :--- |
| `Token.EOF` | Terminal end-of-file sentinel | `None` |
| `Token.NEWLINE` | End-of-line marker (when `LEXER_IGNORE_NEWLINES=False`) | `None` |
| `Token.IDENT` | User-defined variable, function, or type identifier | `str` (e.g., `"foo"`) |
| `Token.INDENT` | Semantic block indentation increase | `int` (indentation column level) |
| `Token.DEDENT` | Semantic block indentation decrease | `int` (target column level) |
| `Token.COMMENT` | Preserved line or block comment (when `LEXER_SAVE_COMMENTS=True`) | `str` (comment body) |
| `Token.KEYWORD` | Registered language keyword from `words.MAP_KEYWORDS` | `str` (keyword name) |

### 2. Literals
| Token Enum Member | Description | Emitted Value Type |
| :--- | :--- | :--- |
| `Token.STRING` | Single-line string, docstring, or multiline literal | `str` |
| `Token.NUMBER` | Integer, binary (`0b`), octal (`0o`), hex (`0x`), or suffixed numeric | `int` or `str` (if suffixed) |
| `Token.DECIMAL` | Floating-point number (contains `.`, exponent `e`, or hex `p`) | `float` or `str` (if suffixed) |
| `Token.BOOL` | Boolean literal matching `TOKEN_BOOL_TRUE` or `TOKEN_BOOL_FALSE` | `bool` (`True` or `False`) |
| `Token.NULL` | Null/nil literal matching `TOKEN_NULL` | `None` |

### 3. Arithmetic Operators
| Enum Member | Symbol | Enum Member | Symbol |
| :--- | :--- | :--- | :--- |
| `Token.PLUS` | `+` | `Token.POW` | `**` |
| `Token.MINUS` | `-` | `Token.FLOOR_DIV` | `//` |
| `Token.STAR` | `*` | `Token.INCREMENT` | `++` |
| `Token.SLASH` | `/` | `Token.DECREMENT` | `--` |
| `Token.PERCENT` | `%` | | |

### 4. Assignment Operators
| Enum Member | Symbol | Enum Member | Symbol |
| :--- | :--- | :--- | :--- |
| `Token.ASSIGN` | `=` | `Token.FLOOR_DIV_ASSIGN` | `//=` |
| `Token.PLUS_ASSIGN` | `+=` | `Token.AND_ASSIGN` | `&=` |
| `Token.MINUS_ASSIGN` | `-=` | `Token.OR_ASSIGN` | `\|=` |
| `Token.STAR_ASSIGN` | `*=` | `Token.XOR_ASSIGN` | `^=` |
| `Token.SLASH_ASSIGN` | `/=` | `Token.SHL_ASSIGN` | `<<=` |
| `Token.PERCENT_ASSIGN` | `%=` | `Token.SHR_ASSIGN` | `>>=` |
| `Token.POW_ASSIGN` | `**=` | `Token.WALRUS` | `:=` |

### 5. Comparison Operators
| Enum Member | Symbol | Description |
| :--- | :--- | :--- |
| `Token.EQUAL` | `==` | Equality test |
| `Token.NOT_EQUAL` | `!=` | Inequality test |
| `Token.LESS` | `<` | Strictly less than |
| `Token.GREATER` | `>` | Strictly greater than |
| `Token.LESS_EQUAL` | `<=` | Less than or equal to |
| `Token.GREATER_EQUAL` | `>=` | Greater than or equal to |

### 6. Logical and Bitwise Operators
| Enum Member | Symbol | Description |
| :--- | :--- | :--- |
| `Token.NOT` | `~` | Bitwise NOT |
| `Token.NOT_LOGIC` | `!` | Logical negation / bang |
| `Token.AND_LOGIC` | `&&` | Logical conjunction |
| `Token.OR_LOGIC` | `\|\|` | Logical disjunction |
| `Token.AND` | `&` | Bitwise AND |
| `Token.OR` | `\|` | Bitwise OR |
| `Token.XOR` | `^` | Bitwise XOR |
| `Token.SHL` | `<<` | Bitwise shift left |
| `Token.SHR` | `>>` | Bitwise shift right |

### 7. Delimiters
| Enum Member | Symbol | Enum Member | Symbol |
| :--- | :--- | :--- | :--- |
| `Token.LPAREN` | `(` | `Token.RPAREN` | `)` |
| `Token.LBRACKET` | `[` | `Token.RBRACKET` | `]` |
| `Token.LBRACE` | `{` | `Token.RBRACE` | `}` |

### 8. Punctuation and Special Symbols
| Enum Member | Symbol | Enum Member | Symbol |
| :--- | :--- | :--- | :--- |
| `Token.COMMA` | `,` | `Token.DOLLAR` | `$` |
| `Token.DOT` | `.` | `Token.QUESTION` | `?` |
| `Token.COLON` | `:` | `Token.QUESTION_ASSIGN` | `?=` |
| `Token.SEMICOLON` | `;` | `Token.EXCLAMATION` | `!` |
| `Token.AT` | `@` | `Token.BACKSLASH` | `\` |
| `Token.HASH` | `#` | `Token.UNDERSCORE` | `_` |

### 9. Arrows
| Enum Member | Symbol | Description |
| :--- | :--- | :--- |
| `Token.ARROW` | `->` | Right single arrow (return types, transitions) |
| `Token.FAT_ARROW` | `=>` | Fat arrow (lambdas, match arms) |
| `Token.LEFT_ARROW` | `<-` | Left arrow (channel reception, assignment) |
| `Token.DOUBLE_ARROW` | `<->` | Bidirectional arrow |

### 10. Unicode (Logic & Mathematics)
| Enum Member | Symbol | Description |
| :--- | :--- | :--- |
| `Token.LOGIC_AND` | `∧` | Mathematical conjunction |
| `Token.LOGIC_OR` | `∨` | Mathematical disjunction |
| `Token.LOGIC_NOT` | `¬` | Mathematical negation |
| `Token.SQRT` | `√` | Square root symbol |
| `Token.INFINITY` | `∞` | Infinity symbol |
| `Token.DEGREE` | `°` | Degree symbol |
| `Token.MIDDLE_DOT` | `·` | Middle dot |
| `Token.BULLET` | `•` | Bullet delimiter |
| `Token.SECTION` | `§` | Section sign |
| `Token.THREE_DOTS` | `...` | Ellipsis (triple dot) |

### 11. Special States
- **`Token.ERROR`:** Emitted when a character or construct cannot be tokenized.
- **`Token.UNKNOWN`:** Unclassified token state.
- **`Token.EMPTY_LINE`:** Diagnostic marker for completely blank source lines.

### Helper Classmethods on `Token`

```python
from gram.core.lexer import Token

# 1. Lookup by string name (case-insensitive)
tok1 = Token.from_string("plus")       # Token.PLUS
tok2 = Token.from_string("IDENT")      # Token.IDENT

# 2. Lookup by integer ordinal code
tok3 = Token.from_code(0)             # Token.EOF

# 3. Complete immutable tuple of all tokens
all_tokens = Token.get_tokens()
print(f"Total defined tokens: {len(all_tokens)}")
```

---

## 2. The `TokenType` Container

Every lexeme emitted by the lexer is an instance of `TokenType`:

```python
class TokenType:
    __slots__ = ("col", "description", "flags", "line", "token", "value")
```

### Attributes

- **`token` (`Token | CustomToken`):** The formal token type enum member or dynamic token.
- **`value` (`Any`):** The scanned payload from the source (e.g., `'my_variable'`, `42`, `'string text'`).
- **`line` (`int`):** Physical source line number (**1-based**).
- **`col` (`int`):** Column offset (**0-based** raw index).
- **`description` (`str`):** Contextual tag (e.g., string prefix such as `"L"` or `"u8"`).
- **`flags` (`TokenFlags`):** Bitwise flags attached during tokenization (e.g., `SIMPLE_QUOTE`, `CHAR`).

### Key Methods

#### `long() -> int`
Computes the ending column coordinate of the token:
$$\text{long} = \text{col} + \text{len}(\text{str}(\text{value}))$$

#### `formatter(msg: str) -> str`
Interpolates token placeholders into diagnostic strings:

| Placeholder | Replaced With | Example Output |
| :--- | :--- | :--- |
| `$name` | `self.token.name` | `"IDENT"` |
| `$value` / `$content` | `str(self.value)` | `"counter"` |
| `$line` | `str(self.line)` | `"12"` |
| `$col` | `str(self.col)` | `"4"` |
| `$len` | Length of payload string | `"7"` |
| `$long` | Ending column (`col + len`) | `"11"` |
| `$symbol` / `$sym` | Symbol string from `MAP_SYMBOLS` | `"+"` |

```python
token = TokenType(Token.IDENT, "counter", line=11, col=4)
print(token.formatter("Error at $name '$value' ($line:$col, end: $long)"))
# "Error at IDENT 'counter' (12:4, end: 11)"
```

#### Structural Equality & Hash Contract
- **Equality (`__eq__`):** Two `TokenType` instances are equal if both their `token` and `value` match. In addition, comparing a `TokenType` directly against a `Token` or `CustomToken` checks if `self.token == other`.
- **Hashing (`__hash__`):** Hashes `hash(self.token)`. This ensures agreement between set/dict lookups across both `TokenType` instances and bare `Token` members.

---

## 3. Dynamic Tokens: `CustomToken`

`CustomToken` enables language developers to synthesize dynamic token types at runtime without modifying Gram's immutable `Token` enum:

```python
from gram.core.lexer import CustomToken, Token

# Create a dynamic token for regex literals or domain-specific markers:
REGEX_TOKEN = CustomToken("REGEX", description="Regular expression literal")

# Equality works across strings, other CustomTokens, and Token types:
print(REGEX_TOKEN == "REGEX")         # True
print(repr(REGEX_TOKEN))              # "Token.REGEX"
```

Combinators like `Tokenize` and `Item` seamlessly match both native `Token` members and `CustomToken` instances.

---

## 4. Lexical Flags: `TokenFlags`

Attached to `token.flags` via `gram.core.lexer.flags`:

```python
class TokenFlags(IntFlag):
    NONE = 0
    SIMPLE_QUOTE = 1 << 0
    CHAR = 1 << 1
```

- **`flags.SIMPLE_QUOTE`:** Set on string literals delimited by single quotes (`'...'`) or double quotes (`"..."`).
- **`flags.CHAR`:** Set when a string literal's payload has an exact length of 1 (e.g., `'a'` or `"x"`).

```python
from gram.core.lexer import Lexer, flags, words
words.add_keyword("dummy", allow_override=True)

tokens = Lexer("'c' \"long string\"").process()
char_tok, str_tok = tokens[0], tokens[1]

print(bool(char_tok.flags & flags.CHAR))          # True
print(bool(char_tok.flags & flags.SIMPLE_QUOTE))  # True
print(bool(str_tok.flags & flags.CHAR))           # False
```

---

## 5. The Operator Engine & `MAP_SYMBOLS`

Gram resolves operators through a specialized bidirectional table, `MAP_SYMBOLS` (`_MapSymbolsDict`):

- **Forward lookup:** `MAP_SYMBOLS["+"] -> Token.PLUS`
- **Reverse lookup by Token:** `MAP_SYMBOLS[Token.PLUS] -> "+"`
- **Reverse lookup by Name:** `MAP_SYMBOLS["PLUS"] -> "+"`

### Maximal Munch Resolution

Gram enforces **maximal munch** (longest-match): operators are matched using `tokens.get_sorted_symbols()`, which sorts registered symbols by length descending:

```python
# '<<=' (len 3) is checked before '<<' (len 2) and '<' (len 1)
# '**' (len 2) is checked before '*' (len 1)
# '->' (len 2) is checked before '-' (len 1)
```

### Custom Symbol Registration: `insert_symbol` & `disabled_symbol`

You can extend or modify the operator table at runtime:

```python
from gram.core.lexer import Token, disabled_symbol, insert_symbol

# 1. Register a new custom operator for an existing Token member
insert_symbol("<>", Token.NOT_EQUAL)

# 2. Disable an operator to avoid collision with custom syntax
old_token = disabled_symbol("§")
```

#### Validation Invariants in `insert_symbol`:
- `symbol` must be a non-empty `str` with no whitespace characters.
- `token` must be an existing member of `Token`.
- If `symbol` is already mapped to a different token, `insert_symbol()` raises `ValueError` to prevent accidental overwrites (use `disabled_symbol()` first).
- Calling `insert_symbol()` or `disabled_symbol()` automatically rebuilds the reverse lookup index and the length-sorted maximal-munch list in place via `_sync_symbol_indexes()`.
