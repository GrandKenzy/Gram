# 03. Usage Guide

This section provides a practical, end-to-end guide to building, isolating, diagnosing, and tooling a language frontend with **Gram**.

Whereas **[02. Combinators](../02-Combinators/index.md)** serves as a catalog of individual parsing primitives, **03. Usage** explains how the surrounding framework components—lexicon registries, `RuleItem` declarations, `nodeable` AST shaping, `Session` isolation, `Diagnostics` telemetry, and `gram.vsix` editor tooling—work together in a real compiler or DSL project.

---

## Section Overview

| Guide | Topics Covered |
| :--- | :--- |
| **[01. Keywords & Lexicon Setup](./01-keywords-and-lexicon.md)** | Initializing `Keyword` entries (`words.add_keyword`), grouping keywords into semantic `WordGroup` sets (`words.add_group`), customizing operator symbols (`tokens.insert_symbol`, `tokens.disabled_symbol`), and configuring `Lexer` behavior via `gram.config`. |
| **[02. RuleItem & `nodeable`](./02-ruleitem-and-nodeable.md)** | Authoring production rules with `RuleItem`, automatic rule ID management (`AutoCode`, `SetCode`), root entrypoint validation (`Alt(Ref(...))`), and how `nodeable = True` vs. `nodeable = False` controls `ASTRef` wrapping vs. child node inlining. |
| **[03. Language Sessions](./03-sessions.md)** | Isolating and switching between multiple language frontends in the same process using `gram.sessions.Session` (`clear_global`, `init`, `migrate`, `load`, `tokenize`, `parse`). |
| **[04. Diagnostics & Error System](./04-diagnostics-and-errors.md)** | Using `gram.utilities.Diagnostics` for hierarchical compiler telemetry (`node`, `down`, `debug`, `warn`, `error`, `StackInfo`), raising OSGDC errors (`gram.errors`, `StackError`), and intercepting failures with `Diagnostics.hook_errors` and `ErrorAction`. |
| **[05. VSIX & Editor Tooling (Beta)](./05-vsix-and-editor-tooling.md)** | Attaching `colors`, `autocomplete`, `suggestions`, `hints`, and `playhints` to `RuleItem` classes, using `TokenSelector` anchors (`@TOKEN:±offset`), rendering 24-bit ANSI TrueColor previews, and generating/packaging `.vsix` extensions and LSP servers. |

---

## Typical Frontend Workflow

```text
1. Configure Lexicon & Flags        ->  config.*, words.add_group(), words.add_keyword()
2. Declare Grammar Rules            ->  class MyRule(combinators.RuleItem): entrypoint = ...
3. Snapshot in a Session (Optional) ->  session.clear_global() -> session.init() -> ... -> session.migrate()
4. Tokenize & Parse Source          ->  Lexer(src).process() -> Parser(tokens).parse(ENTRYPOINT)
5. Inspect AST, Traces & Logs       ->  ASTRef / ASTNode tree, Diagnostics / StackInfo / StackError
6. Export Editor Tooling (Beta)     ->  VSIXAnalyzer -> VSIXGenerator -> vsix.up()
```
