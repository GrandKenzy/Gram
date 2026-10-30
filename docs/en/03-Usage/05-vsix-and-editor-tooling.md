# VSIX & Editor Tooling

> [!WARNING]
> **Development Note:**
> The `gram.vsix` package (schema extraction, token coloring, `.vsix` packaging, and the built-in JSON-RPC Language Server) is functional and zero-dependency. Rule-to-LSP heuristics and manifest generation options may continue to evolve.

`gram.vsix` allows you to attach declarative editor metadata directly to your `RuleItem` classes and `Keyword` definitions, and use that metadata to:
1. Render 24-bit ANSI TrueColor syntax-highlighted previews in the terminal (`ASTColorResolver`).
2. Extract a canonical JSON-serializable language schema (`VSIXAnalyzer`).
3. Generate complete Visual Studio Code extension files (`package.json`, `language-configuration.json`, TextMate `.tmLanguage.json`, `snippets.json`, and `extension.js` LSP client) via `VSIXGenerator`.
4. Package a `.vsix` archive without Node.js and install it into VS Code (`pack_vsix`, `install_extension`, `up`).

---

## 1. Declarative Editor Maps on `RuleItem`

Any `RuleItem` with **`nodeable = True`** can define five optional dictionary attributes:

```python
from gram import combinators as cmb
from gram import lexer

class ImportDecl(cmb.RuleItem):
    name = "IMPORT_DECL"
    nodeable = True  # Required for ASTColorResolver and VSIXAnalyzer maps
    description = "Imports an external module into the current scope."

    entrypoint = cmb.Seq(
        cmb.MatchKeyword("import"),
        cmb.MatchToken(lexer.Token.IDENT),
        cmb.MatchToken(lexer.Token.SEMICOLON),
    )

    # 1. Token coloring (Hex colors or TextMate scopes)
    colors = {
        "import": "#FF79C6",
        "@import:1": "#8BE9FD",
        -1: "#6272A4",
    }

    # 2. Keyword/prefix snippet completions
    autocomplete = {
        0: "import",
    }

    # 3. Value suggestions (static list/tuple or zero-arg callable)
    suggestions = {
        1: ["math", "sys", "io", "http"],
    }

    # 4. Type / snippet hints
    hints = {
        0: "import <module_name>;",
    }

    # 5. Parameter inlay hints
    playhints = {
        1: "module",
    }
```

> [!IMPORTANT]
> **`nodeable = True` Requirement:**  
> `ASTColorResolver` walks `ASTRef` nodes in the parsed AST and matches `ref_node.name` against registered `RuleItem` classes. If a rule sets `nodeable = False`, no `ASTRef` node is emitted for that rule, and `VSIXAnalyzer` logs a warning: `"Rule '<name>' defines editor maps but nodeable is False."`

---

## 2. How `TokenSelector` Resolves Keys in `colors`

When `ASTColorResolver` evaluates a matched `ASTRef` node, it flattens all `TokenType` instances inside that node in source order (`collect_node_tokens(ref_node)`) and resolves each key in `RuleItem.colors` using `TokenSelector.resolve_indices(key, tokens)`:

| Selector Key Format | Example | Resolution Behavior |
| :--- | :--- | :--- |
| **Positive `int` or numeric `str`** | `0`, `1`, `"0"` | Matches the zero-based token position within the flattened `ASTRef` token list. |
| **Negative `int` or numeric `str`** | `-1`, `"-1"` | Matches relative to the end of the `ASTRef` token list (`len(tokens) + idx`, so `-1` is the last token). |
| **Anchor (`@TOKEN`)** | `"@IDENT"`, `"@="` | Matches every token in the rule whose `tok.token.name` or lexeme `str(tok.value)` equals the anchor name. |
| **Offset Anchor (`@TOKEN:±offset`)** | `"@import:1"`, `"@ASSIGN:-1"` | Finds every token matching `TOKEN` (by token type name or lexeme) and selects the token at `i + offset` (e.g., `"@import:1"` selects the token immediately after `import`). |
| **Token Type Name or Lexeme** | `"IDENT"`, `"return"`, `";"` | Matches every token whose `tok.token.name` or `str(tok.value)` equals the string. |
| **Keyword `WordGroup` Name** | `"types"` | Matches any `Token.KEYWORD` whose registered `Keyword.group` equals the group name. |

### Precedence & Fallback Rules
1. **Child Overrides Parent (`child_overrides_parent=True`):** By default, if both an outer `ASTRef` rule and an inner nested `ASTRef` rule assign a color to the same token occurrence, the inner child rule's color wins.
2. **Keyword Lexicon Fallback:** Any `Token.KEYWORD` that was not assigned a color by any `RuleItem.colors` map automatically falls back to the `hex_color` registered via `lexer.words.add_keyword(..., hex_color=...)`.

---

## 3. Terminal 24-Bit ANSI TrueColor Preview

You can resolve token colors on any parsed AST and render a 24-bit ANSI TrueColor preview string using `resolve_ast_colors` and `preview_colored_source`:

```python
from gram import combinators as cmb
from gram import lexer, parser, vsix

lexer.words.clear_all()
lexer.words.add_keyword("let", hex_color="#FF79C6", allow_override=True)

class LetDecl(cmb.RuleItem):
    nodeable = True
    entrypoint = cmb.Seq(
        cmb.MatchKeyword("let"),
        cmb.MatchToken(lexer.Token.IDENT),
        cmb.MatchToken(lexer.Token.ASSIGN),
        cmb.MatchToken(lexer.Token.NUMBER),
    )
    colors = {
        "@ASSIGN:-1": "#50FA7B",  # Identifier before '='
        "ASSIGN": "#FF79C6",      # '=' symbol
        -1: "#BD93F9",            # Number literal at the end
    }

class Program(cmb.RuleItem):
    entrypoint = cmb.Alt(cmb.Ref(LetDecl))

source = "let speed = 100"
tokens = lexer.Lexer(source).process()
ast_roots = parser.Parser(tokens).parse(Program)

# 1. Inspect resolved ColoredToken instances:
colored_tokens = vsix.resolve_ast_colors(ast_roots)
for ct in colored_tokens:
    print(f"{ct.token.value!r:8} -> {ct.color} (from {ct.rule_name}[{ct.token_index!r}])")

# 2. Generate 24-bit ANSI TrueColor string for terminal display:
ansi_preview = vsix.preview_colored_source(source, ast_roots)
print(ansi_preview)
```

Output:

```text
'speed'  -> #50FA7B (from LetDecl['@ASSIGN:-1'])
'='      -> #FF79C6 (from LetDecl['ASSIGN'])
100      -> #BD93F9 (from LetDecl[-1])
'let'    -> #FF79C6 (from LexerKeyword[0])
```

---

## 4. Generating and Packaging a VS Code Extension

### Step 1: Declare Extension Metadata (`vsix.declare_info`)

Use `vsix.declare_info()` (or granular helpers `set_package`, `set_language`, `set_author`, `set_repository`, `set_meta`) to configure the extension manifest:

```python
from gram import vsix

vsix.declare_info(
    name="my-dsl-support",
    display_name="My DSL Language Support",
    description="Syntax highlighting, snippets, and LSP for My DSL",
    version="0.1.0",
    publisher="my-org",
    language_id="mydsl",
    language_name="MyDSL",
    file_extensions=[".mydsl"],
)
```

### Step 2: Analyze the Grammar (`VSIXAnalyzer`) and Export Artifacts (`VSIXGenerator`)

```python
# 1. Extract canonical schema from the root RuleItem entrypoint:
schema = vsix.VSIXAnalyzer(output="vscode").process(Program)

# 2. Generate VS Code extension files in ./vscode_extension:
generator = vsix.VSIXGenerator(schema)
artifacts = generator.export("./vscode_extension")
# Writes:
# - ./vscode_extension/package.json
# - ./vscode_extension/language-configuration.json
# - ./vscode_extension/syntaxes/mydsl.tmLanguage.json
# - ./vscode_extension/snippets/snippets.json
# - ./vscode_extension/extension.js
```

### Step 3: Package `.vsix` and Deploy (`pack_vsix` / `up`)

`vsix.pack_vsix()` builds an Open Packaging Conventions (OPC) `.vsix` zip archive directly in Python without requiring Node.js or `vsce`.

`vsix.up()` orchestrates export, `.vsix` packaging, local installation into `~/.vscode/extensions`, and optional VS Code launch in a single call:

```python
# Package ./vscode_extension into a standalone .vsix archive without installing:
vsix_file = vsix.pack_vsix("./vscode_extension")

# Or export, package, and install into VS Code in one step:
status = vsix.up(
    generator,
    pack=True,
    install=True,
    launch=False,
)
```

---

## 5. Built-in Language Server (`gram.vsix.lsp`)

The generated `extension.js` client automatically spawns Gram's pure-Python stdio Language Server:

```bash
python -u -m gram.vsix.lsp.server --entrypoint my_module:Program --workspace /path/to/workspace
```

Under the hood, `LSPState` (`gram.vsix.lsp.state.LSPState`) uses `Diagnostics.hook_errors` with `ErrorAction.SUPPRESS_RAISE` and `config.ERROR_EXIT_ON_ERROR = False` to run `Lexer` and `Parser` on every `textDocument/didOpen` and `textDocument/didChange` event, converting captured `Error` instances into LSP diagnostics alongside completion, hover, and inlay hint responses.
