# Language Sessions (`gram.sessions.Session`)

`Session` owns the effective lexer catalog and the configuration that belongs
to a language frontend. Its lexer keeps a reference to the session, so two
languages can coexist without sharing keywords, groups, or lexer flags.

Parser and AST session propagation is now active: `Session.parse()` reuses the
pre-created `session.parser`, passes the session to `ASTAnalyzer`, and resolves
parser/AST diagnostic flags from the session. Catalog-aware combinators such as
`MatchGroup` resolve groups from that same session; static grammar definitions
remain shared.

## Constructor

```python
from gram.sessions import Session

session = Session("C frontend", "Many", entrypoint=CProgram)
```

`mode` is `"Many"` or `"Some"`; another value raises `ValueError`.

Each session exposes `session.lexer`, `session.parser`, `session.keywords`,
`session.groups`, `session.symbols`, and a filtered `session.config`. The configuration contains
lexer, parser, AST, error-generation, and info/log-generation settings. Plugin
and environment settings remain global.

## Lexer setup lifecycle

```python
session = Session("Script", "Many")
session.init()

session.add_group("types")
session.add_keyword("int", group="types")
config.LEXER_COMMENT_TOKEN = ";"

# Optional compatibility form during the init/migrate window:
# lexer.words.add_keyword("fn")

session.migrate()
tokens = session.tokenize("int value; ; comment", "sample.dsl")
```

`init()` snapshots the process state and routes loose
`words.add_group()` / `words.add_keyword()` calls to this session. Use
`clear_global()` explicitly if an existing session catalog must be emptied.
`migrate()` stores the session and restores the state that was active before
`init()`. The session lexer does not require `load()` to tokenize.

`load()` is available when legacy parser/combinator consumers need the session
catalog and settings in the process-wide compatibility registries. It requires
`migrate()` first and rebuilds derived symbol indexes.

`clear_global()` now clears the session-owned keyword and group dictionaries;
it does not erase another session's catalog.

## Isolated frontends

```python
from gram import config

c = Session("C", "Many")
c.init()
c.add_keyword("int")
config.LEXER_COMMENT_TOKEN = "//"
c.migrate()

script = Session("Script", "Many")
script.init()
script.add_keyword("fn")
config.LEXER_COMMENT_TOKEN = ";"
script.migrate()

c_tokens = c.tokenize("int value; // comment", "sample.c")
script_tokens = script.tokenize("fn main(); comment", "sample.dsl")
```

`int` is a keyword only in `c`; `fn` is a keyword only in `script`. Calling
`load()` on either session also makes its catalog and symbols visible to legacy
`gram.core.lexer.words` readers until another catalog is loaded. Subsequent
registrations through `session.add_group()` or `session.add_keyword()` keep
those legacy views synchronized.

## Compatibility notes

- The loose `words.add_group()` and `words.add_keyword()` functions remain
  available for the transition period and are the only legacy registration
  entry points.
- `WordGroupManager` remains importable for old imports, but instantiating it
  raises `RuntimeError`; use `Session.add_group()` or `words.add_group()`.
- `Keyword` and `WordGroup` are value objects. Registration is performed by
  the add functions, not by constructing them directly.
- `MULTLINE` remains a global delimiter registry and is not included in a
  session snapshot.

## Sharing conversions

Conversion sharing remains explicit and parser-compatible:

```python
state = c.new_conversion_state()
c.parse(header_tokens, "header.h", conversion_state=state)
c.parse(source_tokens, "main.c", conversion_state=state)
```
