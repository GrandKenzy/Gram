# Configuration & Diagnostics Reference

Gram provides a rich, unified telemetry and configuration framework governing the lexical analysis subsystem.

---

## 1. Exhaustive Configuration Options

All lexer flags reside in `gram.config`. When running inside a `Session`, the lexer reads overrides from `session.config` first before falling back to `gram.config`.

| Setting Flag | Type | Default | Operational Effect on `Lexer` |
| :--- | :--- | :--- | :--- |
| `LEXER_COMMENT_TOKEN` | `str \| Token \| tuple` | `'#'` | Defines prefix marker(s) for single-line comments outside string literals (e.g., `'//'`, `';'`, `'--'`). |
| `LEXER_BLOCK_COMMENT_TOKEN` | `str \| None` | `None` | Opening delimiter for multi-line block comments (e.g., `'/*'`). Closes strictly with `'*/'`. |
| `LEXER_SUPPORT_BLOCK_COMMENTS` | `bool` | `True` | When `False`, block comments configured in `LEXER_BLOCK_COMMENT_TOKEN` are parsed as normal symbols. |
| `LEXER_SUPPORT_DOCSTRINGS` | `bool` | `True` | Enables Python-style triple-quoted multiline string literals (`"""..."""` and `'''...'''`). |
| `LEXER_SUPPORT_PREFIXED_STRINGS` | `bool` | `True` | Recognizes C string prefixes (`L"..."`, `u"..."`, `U"..."`, `u8"..."`), saving prefix to `token.description`. |
| `LEXER_SUPPORT_LEADING_DOT_NUMBERS` | `bool` | `True` | When `True`, `.5` is tokenized as `Token.DECIMAL(0.5)`. When `False`, emits `Token.DOT` and `Token.NUMBER(5)`. |
| `LEXER_TAB_WIDTH` | `int` | `4` | Visual column span for tab characters when `LEXER_INDENT_STYLE` is `"tabs"` or `"mixed"`. Minimum `1`. |
| `LEXER_INDENT_STYLE` | `str` | `'spaces'` | Indentation calculation policy: `"spaces"` (space-only), `"tabs"` (tab-only), or `"mixed"` (column expansion). |
| `SUPPORT_INDENT` | `bool` | `True` | Master toggle for indentation tracking. When `False`, omits `Token.INDENT` and `Token.DEDENT` entirely. |
| `SUPPORT_TRIPLE_DOT` | `bool` | `True` | When `True`, `...` emits `Token.THREE_DOTS`. When `False`, emits three consecutive `Token.DOT` tokens. |
| `LEXER_IGNORE_EMPTY_LINES` | `bool` | `True` | When `True`, blank and comment-only lines are skipped without emitting redundant `Token.NEWLINE` tokens. |
| `LEXER_IGNORE_NEWLINES` | `bool` | `True` | When `True`, newline characters at the end of lines are discarded rather than emitting `Token.NEWLINE`. |
| `LEXER_SAVE_COMMENTS` | `bool` | `True` | When `True`, scanned comments are stored in `lexer.comments`. When `False`, comments are discarded immediately. |
| `LEXER_IDENT_UNDERSCORES` | `int` | `-1` | Controls leading/internal underscore behavior in identifiers: `-1` (unlimited, default), `-2` (unlimited only if followed by characters; standalone `_` emits `UNDERSCORE`), `0` (no underscores permitted in identifiers; all `_` emit `UNDERSCORE`), or `k >= 1` (at most `k` leading underscores in identifier; excess leading underscores emit `UNDERSCORE`). |
| `TOKEN_BOOL_TRUE` | `str` | `'true'` | Lexeme spelling converted to `Token.BOOL` with `value=True` (case-insensitive). |
| `TOKEN_BOOL_FALSE` | `str` | `'false'` | Lexeme spelling converted to `Token.BOOL` with `value=False` (case-insensitive). |
| `TOKEN_NULL` | `str` | `'null'` | Lexeme spelling converted to `Token.NULL` with `value=None` (case-insensitive). |
| `LEXER_ADD_INFO` | `bool` | `True` | Enables diagnostic execution nodes and notes in the `Diagnostics` stack. |
| `LEXER_ADD_ERROR` | `bool` | `True` | Records lexical failure entries in the active diagnostic stack. |
| `ERROR_EXIT_ON_ERROR` | `bool` | `True` | When `True`, unhandled errors call `sys.exit(1)`. Set to `False` to collect diagnostics without crashing. |
| `ERROR_HIDE_CONSOLE` | `bool` | `False` | When `True`, suppresses ANSI console output during error reporting. |

---

## 2. Diagnostic Telemetry & Execution Tracing

`LexerState` inherits directly from `Diagnostics` (`gram.utilities.Diagnostics`), providing deep, structured telemetry for language frontends.

### Hierarchical Diagnostic Stack

When `LEXER_ADD_INFO=True`, the lexer automatically creates nested telemetry nodes:
- `LEXER`: Initialized at lexer creation, tracking total lines and logfile configuration.
- `LexingProcess`: Active throughout `process()`, tracking step-by-step token production.
- `VISITOR-STRING` / `VISITOR-NUMBER` / `VISITOR-WORD` / `VISITOR-SYMBOL`: Nested under `LexingProcess` for each dispatched character.

```python
from gram import config
from gram.core.lexer import Lexer, words
words.add_keyword("let", allow_override=True)

# Enable detailed logging to a diagnostic file:
config.INFO_GENERATE_LOGFILE = True
lexer = Lexer("let x = 42;", logfile="my_compiler.log")
tokens = lexer.process()

# Access the active diagnostic stack:
stack = lexer.stack
print(f"Recorded diagnostic nodes: {len(stack.main.nodes)}")
```

### Disabling Telemetry for High Performance

In production compilers, test suites, or performance benchmarks, set `LEXER_ADD_INFO = False`:
- Skips creation of `StackInfo` nodes.
- Disables note string formatting and sender calls.
- Executes the scanning loop at raw Python speed with zero telemetry overhead.

---

## 3. Error Handling & Exit Policies

When the lexer encounters invalid syntax or malformed tokens, it invokes `LexerState.report_error(err)` or `LexerState.fail(name, code, *caution)`.

```python
def report_error(self, err: errors.Error) -> errors.Error:
    res = self.record_failure(err)
    if (
        res is not None
        and not getattr(err, "_suppress_raise", False)
        and self.get_config("ERROR_EXIT_ON_ERROR", True)
    ):
        err.raise_error()
    return err
```

### Collecting Errors Without Process Exit

Since version `2.0.0b1`, `config.ERROR_EXIT_ON_ERROR` defaults to `True`. To collect errors programmatically (for example, in Language Server diagnostics, IDEs, or unit tests):

```python
from gram import config, errors
from gram.core.lexer import Lexer, words
words.add_keyword("dummy", allow_override=True)

# 1. Disable exit on error:
config.ERROR_EXIT_ON_ERROR = False
config.ERROR_HIDE_CONSOLE = True

# 2. Tokenize malformed source:
lexer = Lexer('int x = "unclosed string')
tokens = lexer.process()

# 3. Inspect collected diagnostic errors:
for failure in lexer.failures:
    print(f"Error [{failure.code}]: {failure.message}")
    for hint in failure.caution:
        print(f"  Hint: {hint}")
```

### Registering Error Hooks (`ErrorAction`)

You can intercept and modify error handling dynamically using error hooks:

```python
from gram.utilities import Diagnostics, ErrorAction

def my_error_hook(err):
    # Suppress terminal exit while recording telemetry:
    return ErrorAction.SUPPRESS_RAISE

Diagnostics.register_error_hook(my_error_hook)
```

---

## 4. OSGDC Lexer Error Codes Matrix

Gram adheres to the OSGDC error code standard across all failure conditions in `gram.errors`:

| Error Code Identifier | Code Enum | Trigger Cause | Recommended Resolution Hint |
| :--- | :--- | :--- | :--- |
| `LEXER_UNEXPECTED_CHARACTER` | `errors.LEXER_UNEXPECTED_CHARACTER` | Character encountered that cannot be matched to any number, string, word, comment, or symbol in `MAP_SYMBOLS`. | Register the character/operator using `insert_symbol(sym, Token)` or configure custom comment markers. |
| `LEXER_UNCLOSED_STRING` | `errors.LEXER_UNCLOSED_STRING` | End of line or end of file reached before closing quotation mark (`"`, `'`) or docstring delimiter (`"""`, `'''`). | Ensure matching closing quotation marks or multiline delimiters before end of line. |
| `LEXER_INVALID_NUMBER` | `errors.LEXER_INVALID_NUMBER` | Malformed numeric literal (e.g., misplaced underscores `1__2`, `123_`, invalid radix digit, or invalid exponent). | Verify base prefix (`0x`, `0b`, `0o`), exponent syntax, and digit separator placement. |
| `LEXER_INDENTATION_MISMATCH` | `errors.LEXER_INDENTATION_MISMATCH` | Decreased line indentation does not match any previous level on the indentation stack. | Check spacing consistency and ensure dedents align with an enclosing block. |
| `LEXER_EMPTY_KEYWORDS` | `errors.LEXER_EMPTY_KEYWORDS` | `Lexer.process()` invoked with 0 registered keywords in `words.MAP_KEYWORDS` or the active session. | Register at least one language keyword using `words.add_keyword()` before scanning. |
| `LEXER_KEYWORD_INVALID_NAME` | `errors.LEXER_KEYWORD_INVALID_NAME` | `words.add_keyword("")` invoked with an empty or whitespace-only name. | Provide a non-empty alphanumeric keyword identifier. |
| `LEXER_KEYWORD_ALREADY_EXISTS` | `errors.LEXER_KEYWORD_ALREADY_EXISTS` | Attempting to register an already existing keyword without setting `allow_override=True`. | Pass `allow_override=True` to replace an existing registration or choose another name. |
| `LEXER_KEYWORD_NOT_FOUND` | `errors.LEXER_KEYWORD_NOT_FOUND` | Strict keyword lookup (`words.get_keyword(name, strict=True)`) failed. | Ensure keyword is registered prior to querying. |
| `LEXER_WORDGROUP_NOT_FOUND` | `errors.LEXER_WORDGROUP_NOT_FOUND` | Strict group query (`words.get_group(name, strict=True)`) failed. | Register the group with `words.add_group(name)`. |
| `LEXER_WORDGROUP_ALREADY_EXISTS` | `errors.LEXER_WORDGROUP_ALREADY_EXISTS` | Attempting to create an existing `WordGroup` without `allow_override=True`. | Pass `allow_override=True` or verify group naming. |
| `LEXER_WORDGROUP_KEYWORD_NOT_REGISTERED` | `errors.LEXER_WORDGROUP_KEYWORD_NOT_REGISTERED` | Attempting to add an unregistered string keyword to a `WordGroup`. | Register the keyword via `words.add_keyword(kw)` before adding it to a group. |
| `LEXER_FILE_NOT_FOUND` | `errors.LEXER_FILE_NOT_FOUND` | `Lexer(Path("nonexistent.gram"))` received a file path that does not exist on disk. | Verify file path and read permissions. |

---

## 5. Multi-Language Sessions & Lexicon Scoping

When building multi-language frontends, embedded DSLs, or parallel test suites, use `gram.sessions.Session` to prevent cross-contamination of keywords, symbols, and lexer configurations.

```python
from gram.sessions import Session
from gram.core.lexer import Token

# 1. Create independent sessions for two distinct DSLs:
session_sql = Session("SQL_Dialect", "Many")
session_c = Session("C_Dialect", "Many")

# 2. Configure SQL session:
session_sql.init()
session_sql.config["LEXER_COMMENT_TOKEN"] = "--"
session_sql.add_keyword("select")
session_sql.add_keyword("from")
session_sql.migrate()

# 3. Configure C session:
session_c.init()
session_c.config["LEXER_COMMENT_TOKEN"] = "//"
session_c.add_keyword("int")
session_c.add_keyword("return")
session_c.migrate()

# 4. Tokenize with session isolation:
tokens_sql = session_sql.tokenize("select * from users; -- SQL query")
tokens_c = session_c.tokenize("int main() { return 0; } // C code")

# SQL session only recognizes SQL keywords:
print([t.value for t in tokens_sql if t.token == Token.KEYWORD])
# ['select', 'from']

# C session only recognizes C keywords:
print([t.value for t in tokens_c if t.token == Token.KEYWORD])
# ['int', 'return']
```

Inside `Session.init()`, Gram calls `words.bind_session(session)`, routing all loose calls to `words.add_keyword()` and `words.add_group()` directly to the session's internal catalogs until `session.migrate()` is called.
