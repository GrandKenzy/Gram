# `RuleItem` and `nodeable`

In **Gram**, formal grammar production rules are declared as subclasses of `RuleItem` (`gram.core.combinators.RuleItem`). Understanding how `RuleItem` interacts with `Ref` and the `nodeable` attribute is essential for shaping clean, predictable Abstract Syntax Trees (`AST`).

---

## 1. Declaring Production Rules with `RuleItem`

Every subclass of `RuleItem` is processed at class creation time by the `RuleMeta` metaclass (`gram.core.combinators.base.RuleMeta`):

```python
from gram import combinators as cmb
from gram import lexer

class VariableDecl(cmb.RuleItem):
    """Matches: int x = 10;"""
    name = "VAR_DECL"           # Optional: defaults to class name ("VariableDecl") if omitted or "auto"
    code = cmb.AutoCode()       # Optional: automatically allocated if omitted
    nodeable = True             # Default: True
    description = "Variable declaration statement"

    entrypoint = cmb.Seq(
        cmb.MatchGroup("types"),
        cmb.MatchToken(lexer.Token.IDENT),
        cmb.Opt(
            cmb.Seq(
                cmb.MatchToken(lexer.Token.ASSIGN),
                cmb.ArithmeticExpr(),
            )
        ),
        cmb.MatchToken(lexer.Token.SEMICOLON),
    )
```

### Core `RuleItem` Attributes

| Attribute | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `entrypoint` | `Combinator \| None` | `None` | **Required.** The root combinator tree evaluated when this rule is referenced by `Ref` or `Parser.parse()`. |
| `name` | `str` | `cls.__name__` | Rule label used in `ASTRef(name, nodes)`, `RayTracing.paths`, and `VSIXAnalyzer`. If omitted, `""`, or `"auto"`, `RuleMeta` sets it to `cls.__name__`. |
| `code` | `int` | `AutoCode()` | Unique numeric identifier registered in `code_manager`. |
| `nodeable` | `bool` | `True` | Controls whether `Ref(MyRule)` wraps the matched output in an `ASTRef` container node (`True`) or inlines the raw child nodes (`False`). |
| `description` | `str` | `""` | Human-readable rule documentation exported to LSP hover tooltips and snippet descriptions by `VSIXAnalyzer`. |
| `ignore` | `bool` | `False` | Metadata flag inspected by `VSIXAnalyzer`. |
| `is_structural` | `bool` | `False` | Metadata flag indicating a structural rule in `VSIXAnalyzer`. |

---

## 2. Automatic Rule Codes (`AutoCode` & `SetCode`)

`RuleMeta` automatically assigns a non-colliding integer `code` to every `RuleItem` subclass through the thread-safe `code_manager` (`gram.core.rules.codes.code_manager`):
- Codes `0` through `20` (`CodeManager.PROTECTED_MAX`) are reserved for internal framework ranges.
- By default, user rule codes start at `10000` (`CodeManager.DEFAULT_BASE_CODE`) and increment by `1`.
- You can change the starting base or step before defining a block of rules using `SetCode(base, step=1)` (accessible via `from gram.core.rules import AutoCode, SetCode` or `from gram.core.combinators import AutoCode, SetCode`):

```python
from gram import combinators as cmb

cmb.SetCode(20_000, step=10)

class RuleA(cmb.RuleItem):
    entrypoint = cmb.MatchToken("IDENT")

class RuleB(cmb.RuleItem):
    entrypoint = cmb.MatchToken("NUMBER")

print(RuleA.code, RuleB.code)  # 20000 20010
```

If `config.RULES_WARN_COLLISION` is `True`, manually assigning the same integer `code` (> 20) to two distinct `RuleItem` classes emits a `UserWarning`.

---

## 3. What is `nodeable`? (`nodeable = True` vs. `nodeable = False`)

When a rule `ParentRule` references another rule `ChildRule` via `Ref(ChildRule)`, how does Gram decide whether `ChildRule` becomes its own named branch (`ASTRef`) in the AST or simply contributes its matched tokens/nodes directly to `ParentRule`?

That behavior is controlled by **`ChildRule.nodeable`**.

### How `Ref.__init__` and `Ref.parse` Evaluate `nodeable`

In `gram/core/combinators/reference.py`:

```python
class Ref(Combinator):
    def __init__(
        self,
        rule: type[RuleItem],
        name: str | None = None,
        strict: bool = False,
    ) -> None:
        super().__init__()
        self.rule = rule
        self.name = name
        if self.name is None and not strict and getattr(self.rule, "nodeable", False):
            self.name = self.rule_name
```

And during `Ref.parse(analyzer)`:
1. If `self.name` is truthy, `Ref.parse` wraps the matched result into `ASTRef(self.name, nodes)`.
2. If `self.name` is `None`, `Ref.parse` returns the raw `result` directly (which `Seq` then flattens into the parent rule's `nodes` list).

### Case 1: `nodeable = True` (Default — Creates an `ASTRef` Node)
Use `nodeable = True` for rules that represent meaningful syntactic constructs in your AST (such as declarations, statements, parameters, pointers, or clauses). Every time `Ref(MyRule)` matches, it produces an `ASTRef(name="MyRule", nodes=[...])`.

### Case 2: `nodeable = False` (Transparent Helper Rule — Inlines Children)
Use `nodeable = False` for intermediate helper or grouping rules that exist only to keep your grammar modular, without adding extra nesting layers to the AST.

For example, in a C frontend:
- `SIGNED` matches `MatchGroup('signed_')` (`signed` or `unsigned`). Setting `nodeable = False` means `INTRINSIC_TYPE` receives the `ASTKeyword('unsigned')` directly instead of a nested `ASTRef('SIGNED', [ASTKeyword('unsigned')])`.
- `TYPE` is an `Alt(Ref(INTRINSIC_TYPE), Ref(ALIASED_TYPE))` dispatcher where `INTRINSIC_TYPE` and `ALIASED_TYPE` already have `nodeable = True`. Setting `TYPE.nodeable = False` prevents wrapping `ASTRef('INTRINSIC_TYPE', ...)` inside a redundant outer `ASTRef('TYPE', ...)`.

### Overriding `nodeable` at the Call Site (`Ref` Parameters)

You can override a target rule's `nodeable` setting on any specific `Ref` instance:

| `TargetRule.nodeable` | `Ref(...)` Call | Resulting AST Output |
| :--- | :--- | :--- |
| `True` | `Ref(TargetRule)` | `ASTRef(TargetRule.name, [...])` |
| `True` | `Ref(TargetRule, name="Custom")` | `ASTRef("Custom", [...])` |
| `True` | `Ref(TargetRule, strict=True)` | Raw child node(s) — **no** `ASTRef` wrapper (`strict=True` prevents copying `TargetRule.name` when `name=None`) |
| `False` | `Ref(TargetRule)` | Raw child node(s) — **no** `ASTRef` wrapper |
| `False` | `Ref(TargetRule, name="ForcedNode")` | `ASTRef("ForcedNode", [...])` |

### Side-by-Side Executable Example

```python
from gram import combinators as cmb
from gram import lexer, parser

lexer.words.clear_all()
lexer.words.add_group("types", allow_override=True)
lexer.words.add_group("signed_", allow_override=True)
lexer.words.add_keyword("int", group="types", allow_override=True)
lexer.words.add_keyword("unsigned", group="signed_", allow_override=True)

# Helper rule: nodeable = False (inlines its token into INTRINSIC_TYPE)
class SIGNED(cmb.RuleItem):
    entrypoint = cmb.MatchGroup("signed_")
    nodeable = False

# Concrete type rule: nodeable = True (produces ASTRef("INTRINSIC_TYPE", ...))
class INTRINSIC_TYPE(cmb.RuleItem):
    entrypoint = cmb.Some(
        cmb.Alt(
            cmb.MatchGroup("types"),
            cmb.Ref(SIGNED),
        )
    )
    nodeable = True

# Dispatcher rule: nodeable = False (passes INTRINSIC_TYPE through without extra wrapper)
class TYPE(cmb.RuleItem):
    entrypoint = cmb.Alt(
        cmb.Ref(INTRINSIC_TYPE),
        cmb.MatchToken(lexer.Token.IDENT),
    )
    nodeable = False

# Parameter rule: nodeable = True (produces ASTRef("PAIR_PARAM", ...))
class PAIR_PARAM(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.Ref(TYPE),
        cmb.MatchToken(lexer.Token.IDENT),
    )
    nodeable = True

# Root entrypoint rule: must be an Alt of Ref(...)
class PROGRAM(cmb.RuleItem):
    entrypoint = cmb.Alt(cmb.Ref(PAIR_PARAM))

tokens = lexer.Lexer("unsigned int count").process()
ast_nodes = parser.Parser(tokens).parse(PROGRAM)
print("Root:", ast_nodes)
print("PAIR_PARAM children:", ast_nodes[0].nodes)
print("INTRINSIC_TYPE children:", ast_nodes[0].nodes[0].nodes)
# Output:
# Root: [AstRef(nodes=2, name=PAIR_PARAM)]
# PAIR_PARAM children: [AstRef(nodes=2, name=INTRINSIC_TYPE), Identifier(value='count', line=1, col=13)]
# INTRINSIC_TYPE children: [ASTKeyword(value='unsigned', line=1, col=0), ASTKeyword(value='int', line=1, col=9)]
```

Notice how `PAIR_PARAM` contains `ASTRef('INTRINSIC_TYPE', [ASTKeyword('unsigned'), ASTKeyword('int')])` and `Identifier('count')`, with no redundant `TYPE` or `SIGNED` wrapper nodes.

---

## 4. Interactions of `nodeable` with `Separator` and `VSIX`

1. **`Separator` Validation (`UnnamedRefInSeparator`):**
   When a `Ref` is passed inside `Separator(sep=..., values=[...])`, `Separator` requires every `Ref` element to produce a named `ASTRef` node. If you pass `Ref(HelperRule)` where `HelperRule.nodeable` is `False` and no explicit `name="..."` is provided on `Ref`, `Separator` reports `GrammarError` (`UnnamedRefInSeparator` / `GRAMMAR_COMBINATOR_UNSUPPORTED`).
2. **VSIX Declarative Maps (`colors`, `autocomplete`, `suggestions`, `hints`, `playhints`):**
   `ASTColorResolver` projects `RuleItem.colors` onto `ASTRef` nodes by matching `ref_node.name` against registered `RuleItem` classes. If a rule has `nodeable = False`, it never emits an `ASTRef` node in the AST, so its `colors` map cannot be projected onto the AST (`VSIXAnalyzer` logs a warning if `nodeable = False` is combined with editor maps).

---

## 5. Root Entrypoint Rules (`Parser.parse` & `ASTAnalyzer`)

When you pass a root `RuleItem` class to `Parser(tokens).parse(ENTRYPOINT, mode="Many")` (or `ASTAnalyzer(parser, ENTRYPOINT, mode="Many")`), `ASTState.is_valid_entrypoint()` enforces two structural rules on `ENTRYPOINT`:
1. `ENTRYPOINT.entrypoint` **must** be an `Alt` combinator (`AST_PROGRAM_INVALID_COMBINATOR` otherwise).
2. Every element inside `ENTRYPOINT.entrypoint.combinators` **must** be a `Ref` combinator (`AST_DECLARATOR_INVALID_ELEMENT` otherwise).

### Top-Level Repetition Modes (`"Many"` vs. `"Some"`)
- **`mode="Many"` (default):** Repeatedly evaluates `ENTRYPOINT.entrypoint` across the token stream (automatically skipping standalone top-level `Token.NEWLINE` tokens) until `Token.EOF` is reached. An empty file returns `[]`.
- **`mode="Some"`:** Requires at least one top-level statement to match before `Token.EOF`, reporting `EntryPointMinimumNotMet` (`GRAMMAR_COMBINATOR_FAILED`) if the input produces no AST nodes.
