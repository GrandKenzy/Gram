# Keywords & Lexicon Setup

Before tokenizing source code with `Lexer`, you configure how Gram recognizes comments, multiline literals, blank lines, language keywords (`Keyword`), semantic keyword groups (`WordGroup`), and custom multi-character symbols.

All keyword and group operations live in `gram.core.lexer.words` (accessible via `from gram import lexer; lexer.words`).

---

## 1. Configuring Lexer Behavior (`gram.config`)

The standalone `Lexer` reads flags from `gram.config`; a session-owned lexer
reads the same settings from its `Session.config` view instead.

| Setting | Default | Effect on `Lexer` |
| :--- | :--- | :--- |
| `config.LEXER_COMMENT_TOKEN` | `'#'` | Single-line comment prefix (e.g., `'//'`, `'#'`, `';'`). Any text from this prefix to the end of the line is discarded outside string literals. |
| `config.LEXER_BLOCK_COMMENT_TOKEN` | `None` | Opening delimiter for block comments. When `LEXER_SUPPORT_BLOCK_COMMENTS=True`, it closes with `*/`. |
| `config.LEXER_SUPPORT_BLOCK_COMMENTS` | `True` | Enables or disables block comments configured through `LEXER_BLOCK_COMMENT_TOKEN`. |
| `config.LEXER_SUPPORT_DOCSTRINGS` | `True` | Enables the default multiline delimiters (`"""..."""` and `'''...'''`). They emit `Token.STRING`. |
| `config.LEXER_SUPPORT_PREFIXED_STRINGS` | `True` | Recognizes C prefixes such as `L"text"`, `u"text"`, `U"text"`, and `u8"text"`. |
| `config.LEXER_SUPPORT_LEADING_DOT_NUMBERS` | `True` | Recognizes numbers beginning with a dot, such as `.5`. If `False`, the lexer emits `Token.DOT` and `Token.NUMBER`. |
| `config.LEXER_TAB_WIDTH` | `4` | Visual width used for tabs when `LEXER_INDENT_STYLE` is `tabs` or `mixed`. Values below `1` are normalized to `1`. |
| `config.LEXER_INDENT_STYLE` | `'spaces'` | Indentation policy: `spaces` preserves the legacy space-only width, `tabs` counts tabs at `LEXER_TAB_WIDTH`, and `mixed` expands both spaces and tabs. |
| `config.TOKEN_BOOL_TRUE` / `config.TOKEN_BOOL_FALSE` | `'true'` / `'false'` | Defines the spellings converted to `Token.BOOL`. |
| `config.TOKEN_NULL` | `'null'` | Defines the spelling converted to `Token.NULL`. |
| `config.SUPPORT_INDENT` | `True` | When `False`, the lexer emits neither `Token.INDENT` nor `Token.DEDENT`. |
| `config.SUPPORT_TRIPLE_DOT` | `True` | Controls whether `...` is recognized as `Token.THREE_DOTS` or as three `Token.DOT` tokens. |
| `config.LEXER_IGNORE_EMPTY_LINES` | `True` | When `True`, blank or comment-only lines are skipped without emitting redundant `Token.NEWLINE` tokens or perturbing `INDENT`/`DEDENT` calculation. |
| `config.LEXER_ADD_INFO` | `True` | When `True`, emits lexical telemetry and creates lexer process/visitor nodes. When `False`, those nodes and notes are skipped. |
| `config.LEXER_ADD_ERROR` | `True` | When `True`, records lexical failure notes in the lexer diagnostic stack. |

Word classification is deterministic. The lexer checks configured boolean
spellings first (case-insensitive), then the configured null spelling
(case-insensitive), then an exact registered keyword spelling, and finally
emits `Token.IDENT`. A keyword named `TRUE` therefore does not override the
configured boolean spelling `true`.

`WordGroup.contains()` uses exact, case-sensitive names. `WordGroup.clear()`
also resets `keyword.group` for every member, so clearing a group cannot leave
stale group references behind.

For token diagnostics, `TokenType.formatter()` expands `$line`, `$col`, `$len`,
and `$long` from the emitted token. `$len` is the length of the token payload;
`$long` is its ending column (`col + len`).

### Multiline delimiters

Multiline strings and block comments use the same delimiter registry. Add a
variant for the current process and remove it when it is no longer needed:

```python
from gram.core.lexer import Lexer, add_multline, list_multline, remove_multline, words

# Lexer requires at least one registered keyword.
words.add_keyword("placeholder", allow_override=True)
add_multline("<<<", ">>>")
print(list_multline())
# {'"""': '"""', "'''": "'''", '<<<': '>>>'}

tokens = Lexer("<<<multiline\ncontent>>>").process()
remove_multline("<<<")
```

Delimiters not associated with comments emit `Token.STRING`. For C block
comments, keep the compatible `LEXER_BLOCK_COMMENT_TOKEN = "/*"` setting; the
same multiline scanner handles it internally. `add_multline()` changes the
global registry for new instances; each `Lexer` copies the registry when it is
created, so an existing lexer is unaffected by later registrations or removals.

| API | Description |
| :--- | :--- |
| `MULTLINE` | Global `opening -> closing` dictionary containing registered delimiters. |
| `add_multline(opening, closing)` | Adds or replaces a delimiter pair. |
| `remove_multline(opening)` | Removes an opening delimiter and returns its closing delimiter, or `None` if absent. |
| `list_multline()` | Returns an independent copy of the current registry. |

### String flags

All quoted strings emit `Token.STRING`. The `TokenType.flags` attribute uses
`gram.core.lexer.flags`:

```python
from gram.core.lexer import flags

token.flags & flags.SIMPLE_QUOTE  # any simple quoted string
token.flags & flags.CHAR          # string whose value has one character
```

For example, `'x'` has `flags.CHAR | flags.SIMPLE_QUOTE`, while `"text"` only
has `flags.SIMPLE_QUOTE`. There is no separate `Token.CHAR` anymore.

| Flag | Meaning |
| :--- | :--- |
| `flags.NONE` | The token has no special lexical flags. |
| `flags.SIMPLE_QUOTE` | The value comes from a single-line string delimited by single or double quotes. |
| `flags.CHAR` | The string value contains exactly one character. |

---

## 2. Registering Keywords (`words.add_keyword`)

By default, any alphabetic/underscore word (`[a-zA-Z_][a-zA-Z0-9_]*`) scanned by the lexer is emitted as `Token.IDENT`—except for `'true'` and `'false'`, which are only treated as `Token.BOOL` if they have **not** been registered as keywords in `words.MAP_KEYWORDS`.

When a word is registered via `lexer.words.add_keyword()`, the lexer emits it with `token == Token.KEYWORD`, allowing it to be matched by `MatchKeyword` or `MatchGroup`.

### Signature

```python
lexer.words.add_keyword(
    name: str,
    hex_color: str = "#FFFFFF",
    group: str | WordGroup | None = None,
    description: str = "",
    documentation: str = "",
    *,
    color: str | None = None,
    allow_override: bool = False,
) -> Keyword
```

- **`name`**: Exact lexeme string (stripped of leading/trailing whitespace). Empty names raise `LexerError` (`LEXER_KEYWORD_INVALID_NAME`).
- **`hex_color` / `color`**: Hexadecimal color string (e.g., `'#FF79C6'`) used as a fallback by `ASTColorResolver` and `VSIXAnalyzer`.
- **`group`**: Optional group name (`str`) or `WordGroup` instance. If the group already exists, the keyword is automatically added to it.
- **`description` / `documentation`**: Metadata strings extracted by `VSIXAnalyzer` for LSP completion details and hover tooltips.
- **`allow_override`**: When `False` (default), registering a duplicate keyword raises `LexerError` (`LEXER_KEYWORD_ALREADY_EXISTS`). Set `allow_override=True` to replace an existing registration cleanly.

---

## 3. Semantic Word Groups (`words.add_group` & `WordGroup`)

A `WordGroup` groups related keywords under a shared semantic identifier (such as `'types'`, `'control'`, or `'modifiers'`) so grammar rules can match any member in $O(1)$ time using `MatchGroup('types')`.

### Creating Groups and Populating Keywords

> [!IMPORTANT]
> Every keyword added to a `WordGroup` **must** be registered in `MAP_KEYWORDS` first (or passed as a `Keyword` instance). Attempting to add an unregistered string to a `WordGroup` raises `LexerError` (`LEXER_WORDGROUP_KEYWORD_NOT_REGISTERED`).
> Furthermore, a `Keyword` tracks a single `kw.group` attribute: if `kw.group` is already set to a different group name, `other_group.add_keyword(kw)` is a no-op and returns `None`.

```python
from gram import config, lexer

# Reset any previous global keywords/groups
lexer.words.clear_all()

# Configure C-style single-line comments
config.LEXER_COMMENT_TOKEN = "//"

# 1. Create semantic word groups first
types_group = lexer.words.add_group(
    "types",
    color_group="#3B82F6",
    description="Primitive scalar types",
    allow_override=True,
)
signed_group = lexer.words.add_group(
    "signed_",
    color_group="#60A5FA",
    description="Sign modifiers",
    allow_override=True,
)

# 2. Register keywords and bind them to their groups
for kw_name in ("void", "char", "short", "int", "long", "float", "double"):
    lexer.words.add_keyword(
        kw_name,
        hex_color="#3B82F6",
        group="types",
        description=f"Primitive type '{kw_name}'",
        allow_override=True,
    )

for kw_name in ("signed", "unsigned"):
    lexer.words.add_keyword(
        kw_name,
        hex_color="#60A5FA",
        group="signed_",
        allow_override=True,
    )

# Standalone control keyword without a group
lexer.words.add_keyword("return", hex_color="#FF79C6", allow_override=True)

print("Total keywords:", lexer.words.count_keywords())
print("Types group members:", types_group.values)
print("Is 'int' in 'types'?", lexer.words.exists_in_group("int", "types"))
```

### Catalog Inspection & Cleanup Helpers

| Function | Return Type | Description |
| :--- | :--- | :--- |
| `words.get_keyword(name, *, strict=False)` | `Keyword \| None` | Returns the `Keyword` instance or `None` (raises `LEXER_KEYWORD_NOT_FOUND` if `strict=True`). |
| `words.keyword_exists(name)` | `bool` | Returns `True` if `name` is in `MAP_KEYWORDS`. |
| `words.remove_keyword(name, *, strict=False)` | `Keyword \| None` | Removes `name` from `MAP_KEYWORDS` and from all `WordGroup` instances. |
| `words.all_keywords()` / `words.all_keyword_names()` | `list[Keyword]` / `list[str]` | Lists all registered `Keyword` objects or string names. |
| `words.get_group(name, *, strict=False)` | `WordGroup \| None` | Returns the `WordGroup` instance or `None` (raises `LEXER_WORDGROUP_NOT_FOUND` if `strict=True`). |
| `words.group_exists(name)` | `bool` | Returns `True` if the group is registered. |
| `words.exists_in_group(kw, group)` | `bool` | $O(1)$ membership check inside `group`. |
| `words.remove_group(name)` | `WordGroup \| None` | Removes the group and resets `kw.group = None` on its members. `WordGroup.clear()` performs the same reference cleanup without removing the group. |
| `words.clear_all()` | `None` | Clears both `MAP_KEYWORDS` and all `WordGroup` entries. |

---

## 4. Customizing Operator Symbols (`insert_symbol` & `disabled_symbol`)

Gram's lexer includes a built-in bidirectional table (`lexer.tokens.MAP_SYMBOLS`) of 1-, 2-, and 3-character operators and delimiters (`+`, `->`, `:=`, `...`, `==`, `&&`, etc.) matched via greedy longest-match (`get_sorted_symbols()`).

You can add a new symbol lexeme mapped to an existing `Token` enum member with `lexer.tokens.insert_symbol(symbol, token)`, or disable an existing symbol lexeme with `lexer.tokens.disabled_symbol(symbol)` (which automatically rebuilds the reverse lookup and maximal-munch sorted symbol list):

```python
from gram import lexer

# Map "<>" as an alias for Token.NOT_EQUAL:
lexer.tokens.insert_symbol("<>", lexer.Token.NOT_EQUAL)

tokens = lexer.Lexer("a <> b").process()
print(tokens)
# [TokenType(token=Token.IDENT, value='a', line=1, col=0),
#  TokenType(token=Token.NOT_EQUAL, value='<>', line=1, col=2),
#  TokenType(token=Token.IDENT, value='b', line=1, col=5),
#  TokenType(token=Token.EOF, value=None, line=1, col=6)]

# Remove the custom symbol from MAP_SYMBOLS when done:
lexer.tokens.disabled_symbol("<>")
```
