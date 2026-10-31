# Literals & Specialized Visitors

Gram uses a modular **visitor dispatch pattern** located in `gram.core.lexer.visitors`. Rather than running a monolithic regular expression over the entire input, `Lexer` examines the character under the cursor and dispatches control to specialized visitor modules.

---

## 1. Master Dispatcher Architecture (`visitors.visit`)

Whenever `Lexer.process()` encounters non-whitespace text that is not a comment or registered multiline delimiter, it delegates tokenization to `visitors.visit(lexer, char)`:

```python
def visit(lexer: LexerState, char: str) -> TokenType:
```

### Dispatch Precedence Order

```
Character under cursor
         │
         ├─► Prefixed String? (L"...", u"...", U"...", u8"...")
         │   (if LEXER_SUPPORT_PREFIXED_STRINGS is True)
         │   └──► DISPATCH: strings.process(..., prefix=..., start_override=...)
         │
         ├─► Quote? (' or ")
         │   └──► DISPATCH: strings.process()
         │
         ├─► Digit (0-9) OR Leading Dot (e.g., .5)?
         │   (Leading dot checked if LEXER_SUPPORT_LEADING_DOT_NUMBERS is True)
         │   └──► DISPATCH: numbers.process()
         │
         ├─► Alphabetic or Underscore ([a-zA-Z_])?
         │   └──► DISPATCH: words.process()
         │
         └─► Fallback (Operators, Delimiters, Punctuation, Unicode)
             └──► DISPATCH: symbols.process()
```

When diagnostic telemetry is active (`LEXER_ADD_INFO=True`), `visit()` pushes an execution node (`VISITOR-STRING`, `VISITOR-NUMBER`, `VISITOR-WORD`, or `VISITOR-SYMBOL`) to trace the visitor's execution, closing the node in a `finally: lexer.down()` block.

---

## 2. Numeric Literals (`visitors.numbers`)

Gram's numeric visitor parses C-compatible integer and floating-point literals with full support for radix bases, scientific notation, digit separators, and C type suffixes.

### Supported Numeric Literals

| Category | Example Syntaxes | Emitted Token | Evaluated `value` |
| :--- | :--- | :--- | :--- |
| **Decimal Integer** | `42`, `100_000` | `Token.NUMBER` | `int` (`42`, `100000`) |
| **Binary Radix** | `0b1010`, `0B1100_0011` | `Token.NUMBER` | `int` (`10`, `195`) |
| **Octal Radix** | `0o755`, `0O644` | `Token.NUMBER` | `int` (`493`, `420`) |
| **Hexadecimal Integer** | `0x1A2F`, `0XDEAD_BEEF` | `Token.NUMBER` | `int` (`6703`, `3735928559`) |
| **Decimal Float** | `3.14159`, `1.5e-4`, `2E+3` | `Token.DECIMAL` | `float` (`3.14159`, `0.00015`, `2000.0`) |
| **Leading Dot Float** | `.5`, `.125e2` | `Token.DECIMAL` | `float` (`0.5`, `12.5`) |
| **Hexadecimal Float** | `0x1.2p3`, `0x.4p-1` | `Token.DECIMAL` | `float` (`9.0`, `0.125`) |
| **Suffixed Integer** | `42UL`, `0x10ULL`, `100u` | `Token.NUMBER` | `str` (`"42UL"`, `"0x10ULL"`, `"100u"`) |
| **Suffixed Float** | `1.0f`, `2.5L`, `0x1.fp2f` | `Token.DECIMAL` | `str` (`"1.0f"`, `"2.5L"`, `"0x1.fp2f"`) |

### Key Parsing Rules & Invariants

#### 1. Token Distinction: `Token.DECIMAL` vs. `Token.NUMBER`
- Any numeric literal containing a decimal dot (`.`), a binary exponent (`p`/`P` in hex floats), or a decimal exponent (`e`/`E` in decimal floats) is classified as **`Token.DECIMAL`**.
- All standard integers and radix integers are classified as **`Token.NUMBER`**.

#### 2. Suffix Preservation Contract
When numeric literals contain C suffixes (`u`, `U`, `l`, `L`, `f`, `F`):
- **Unsuffixed numbers:** Converted directly to Python `int` or `float` for immediate runtime use.
- **Suffixed numbers:** Preserved as their exact **raw string** representation (e.g., `"1.0f"`). This allows downstream semantic analyzers or compiler frontends to distinguish `int`, `unsigned long`, `float`, and `double` without having to re-parse the source code.

#### 3. Underscore Separator Validation (`_has_invalid_separator`)
Underscores (`_`) can be used as visual separators between literal digits, but cannot be misplaced:
- `1_000_000` ── Valid.
- `_123` ── Scanned as `Token.IDENT` (`"_123"`), not a number.
- `123_` ── Invalid trailing separator. Emits `Token.ERROR` and reports `LEXER_INVALID_NUMBER`.
- `1__2` ── Invalid consecutive separators. Emits `Token.ERROR`.
- `0x_12` ── Invalid radix separator. Emits `Token.ERROR`.

#### 4. Hexadecimal Radix Precedence
Because hexadecimal digits include `e`, `E`, `f`, and `F`, the visitor tests for hexadecimal literals before evaluating decimal exponents or float suffixes. This guarantees that literals like `0xface` and `0x1f` are correctly parsed as hexadecimal integers rather than corrupt decimal scientific numbers.

---

## 3. String & Multiline Literals (`visitors.strings`)

The string visitor scans single-line quoted strings, prefixed strings, and multiline docstrings.

### Single-Line Strings (`'...'` and `"..."`)

Single-line strings are delimited by matching single or double quotation marks:

```python
from gram.core.lexer import Lexer, Token, flags, words
words.add_keyword("dummy", allow_override=True)

tokens = Lexer("'hello' \"world\"").process()
print(tokens[0])  # TokenType(token=Token.STRING, value='hello', flags=SIMPLE_QUOTE)
```

#### Escape Sequence Resolution (`process_escape`)

Standard C/Python escape sequences are decoded automatically:

| Escape Sequence | Decoded Character | Meaning |
| :--- | :--- | :--- |
| `\n` | `"\n"` | Newline (Line feed) |
| `\r` | `"\r"` | Carriage return |
| `\t` | `"\t"` | Horizontal tab |
| `\b` | `"\b"` | Backspace |
| `\f` | `"\f"` | Form feed |
| `\v` | `"\v"` | Vertical tab |
| `\0` | `"\0"` | Null byte |
| `\\` | `"\\"` | Literal backslash |
| `\"` | `"\""` | Escaped double quote |
| `\'` | `"\'"` | Escaped single quote |
| `\uXXXX` | `chr(0xXXXX)` | 4-digit hexadecimal Unicode codepoint (e.g., `\u00A9` -> `©`) |

Any unrecognized escape character `\c` falls back to the literal escaped pair `"\c"`.

### Prefixed Strings (C-Style)

When `config.LEXER_SUPPORT_PREFIXED_STRINGS=True`, Gram recognizes prefixes before quotes:
- `L"..."` / `L'...'` ── Wide character / string.
- `u"..."` / `u'...'` ── UTF-16 string.
- `U"..."` / `U'...'` ── UTF-32 string.
- `u8"..."` / `u8'...'` ── UTF-8 string.

The prefix is stored directly in `token.description`:

```python
tokens = Lexer('L"wide text" u8"utf8 text"').process()
print(tokens[0].description)  # "L"
print(tokens[0].value)        # "wide text"
print(tokens[1].description)  # "u8"
```

### Multiline Strings & Docstrings (`"""..."""` and `'''...'''`)

When `config.LEXER_SUPPORT_DOCSTRINGS=True`, triple-quoted literals can span multiple source lines:

```python
code = '''"""
Line 1
Line 2
"""'''
tokens = Lexer(code).process()
print(tokens[0].value)  # "\nLine 1\nLine 2\n"
```

Multiline scanning updates `lexer.line` and `lexer.col` while preserving the original `start_line` and starting column for the emitted `TokenType`.

### Custom Multiline Delimiters (`add_multline`)

You can register custom opening and closing delimiters using `gram.core.lexer.multiline`:

```python
from gram.core.lexer import Lexer, add_multline, list_multline, remove_multline, words
words.add_keyword("dummy", allow_override=True)

# Register a custom raw-block delimiter:
add_multline("<<<", ">>>")

tokens = Lexer("<<<multiline\nraw\ncontent>>>").process()
print(tokens[0].value)  # "multiline\nraw\ncontent"

# Clean up
remove_multline("<<<")
```

---

## 4. Words, Keywords, & Booleans (`visitors.words`)

The word visitor handles continuous sequences of alphanumeric characters and underscores (`[a-zA-Z_][a-zA-Z0-9_]*`).

### The 4-Step Resolution Hierarchy

Classification is strictly deterministic:

```
                      Word Scanned
                           │
                           ▼
              1. Configured Booleans?
         (case-insensitive match against
        TOKEN_BOOL_TRUE or TOKEN_BOOL_FALSE)
              │ YES                     │ NO
              ▼                         ▼
      Emit Token.BOOL             2. Configured Null?
                                (case-insensitive match
                                  against TOKEN_NULL)
                                        │ YES       │ NO
                                        ▼           ▼
                                Emit Token.NULL   3. Registered Keyword?
                                                 (exact case-sensitive match
                                                   in active MAP_KEYWORDS)
                                                        │ YES        │ NO
                                                        ▼            ▼
                                                Emit Token.KEYWORD   4. Emit Token.IDENT
```

### Deterministic Precedence Examples

1. **Booleans Over Keywords:** If `TOKEN_BOOL_TRUE = "true"`, a registered keyword named `"true"` or `"TRUE"` will **never** override the boolean classification.
2. **Null Over Keywords:** If `TOKEN_NULL = "null"`, the word `"null"` or `"NULL"` will always emit `Token.NULL`.
3. **Exact Keyword Lookup:** Keywords registered via `words.add_keyword("if")` require exact case matching. `"if"` emits `Token.KEYWORD`, while `"If"` or `"IF"` emits `Token.IDENT`.

```python
from gram import config
from gram.core.lexer import Lexer, Token, words

words.clear_all()
words.add_keyword("let")
words.add_keyword("null")  # Will be shadowed by TOKEN_NULL

tokens = Lexer("let x = true; let y = null; let z = True;").process()
print([(t.token, t.value) for t in tokens])
# [(Token.KEYWORD, 'let'), (Token.IDENT, 'x'), (Token.ASSIGN, '='), (Token.BOOL, True), (Token.SEMICOLON, ';'),
#  (Token.KEYWORD, 'let'), (Token.IDENT, 'y'), (Token.ASSIGN, '='), (Token.NULL, None), (Token.SEMICOLON, ';'),
#  (Token.KEYWORD, 'let'), (Token.IDENT, 'z'), (Token.ASSIGN, '='), (Token.BOOL, True), (Token.SEMICOLON, ';'),
#  (Token.EOF, None)]
```

---

## 5. Operators & Symbols (`visitors.symbols`)

When a character is not an alphanumeric word, quote, or comment marker, control dispatches to `visitors.symbols.process()`:

1. Iterates over `lexer.sorted_symbols()` (ordered by length descending).
2. Performs slice comparison: `if line[start:start+len(symbol)] == symbol:`.
3. Special check for `...`: if `config.SUPPORT_TRIPLE_DOT=False`, `...` is skipped, causing each dot to be tokenized as an individual `Token.DOT`.
4. If a symbol matches, advances `lexer.col` by `len(symbol)` and emits `TokenType(symbol_map[symbol], symbol, line, start)`.
5. If no registered symbol matches, advances by 1 character, logs an error to `Diagnostics`, reports `LexerError` (`LEXER_UNEXPECTED_CHARACTER`), and emits `Token.ERROR`.
