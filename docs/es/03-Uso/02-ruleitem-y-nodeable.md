# `RuleItem` y `nodeable`

En **Gram**, las reglas de producción gramaticales formales se declaran como subclases de `RuleItem` (`gram.core.combinators.RuleItem`). Comprender cómo interactúa `RuleItem` con `Ref` y con el atributo `nodeable` es fundamental para moldear Árboles de Sintaxis Abstracta (`AST`) limpios y predecibles.

---

## 1. Declarar Reglas de Producción con `RuleItem`

Cada subclase de `RuleItem` es procesada en tiempo de creación de la clase por la metaclase `RuleMeta` (`gram.core.combinators.base.RuleMeta`):

```python
from gram import combinators as cmb
from gram import lexer

class VariableDecl(cmb.RuleItem):
    """Coincide con: int x = 10;"""
    name = "VAR_DECL"           # Opcional: toma el nombre de la clase ("VariableDecl") si se omite o es "auto"
    code = cmb.AutoCode()       # Opcional: asignado automáticamente si se omite
    nodeable = True             # Por defecto: True
    description = "Sentencia de declaración de variable"

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

### Atributos Principales de `RuleItem`

| Atributo | Tipo | Por Defecto | Descripción |
| :--- | :--- | :--- | :--- |
| `entrypoint` | `Combinator \| None` | `None` | **Requerido.** El árbol combinador raíz evaluado cuando esta regla es referenciada por `Ref` o `Parser.parse()`. |
| `name` | `str` | `cls.__name__` | Etiqueta de la regla usada en `ASTRef(name, nodes)`, `RayTracing.paths` y `VSIXAnalyzer`. Si se omite, es `""` o `"auto"`, `RuleMeta` la establece como `cls.__name__`. |
| `code` | `int` | `AutoCode()` | Identificador numérico único registrado en `code_manager`. |
| `nodeable` | `bool` | `True` | Controla si `Ref(MyRule)` envuelve la salida coincidente en un nodo contenedor `ASTRef` (`True`) o inserta de forma plana los nodos secundarios directos (`False`). |
| `description` | `str` | `""` | Documentación legible de la regla exportada a tooltips hover de LSP y descripciones de fragmentos por `VSIXAnalyzer`. |
| `ignore` | `bool` | `False` | Flag de metadatos inspeccionado por `VSIXAnalyzer`. |
| `is_structural` | `bool` | `False` | Flag de metadatos que indica una regla estructural en `VSIXAnalyzer`. |

---

## 2. Códigos de Regla Automáticos (`AutoCode` y `SetCode`)

`RuleMeta` asigna automáticamente un entero `code` sin colisiones a cada subclase de `RuleItem` mediante el gestor thread-safe `code_manager` (`gram.core.rules.codes.code_manager`):
- Los códigos `0` al `20` (`CodeManager.PROTECTED_MAX`) están reservados para rangos internos del framework.
- Por defecto, los códigos de regla del usuario comienzan en `10000` (`CodeManager.DEFAULT_BASE_CODE`) e incrementan de 1 en 1.
- Puedes cambiar la base inicial o el paso antes de definir un bloque de reglas usando `SetCode(base, step=1)` (accesible vía `from gram.core.rules import AutoCode, SetCode` o `from gram.core.combinators import AutoCode, SetCode`):

```python
from gram import combinators as cmb

cmb.SetCode(20_000, step=10)

class RuleA(cmb.RuleItem):
    entrypoint = cmb.MatchToken("IDENT")

class RuleB(cmb.RuleItem):
    entrypoint = cmb.MatchToken("NUMBER")

print(RuleA.code, RuleB.code)  # 20000 20010
```

Si `config.RULES_WARN_COLLISION` es `True`, asignar manualmente el mismo entero `code` (> 20) a dos clases `RuleItem` distintas emite un `UserWarning`.

---

## 3. ¿Qué es `nodeable`? (`nodeable = True` vs. `nodeable = False`)

Cuando una regla `ParentRule` hace referencia a otra regla `ChildRule` mediante `Ref(ChildRule)`, ¿cómo decide Gram si `ChildRule` se convierte en una rama con nombre propio (`ASTRef`) en el AST o simplemente aporta sus tokens/nodos coincidentes directamente a `ParentRule`?

Ese comportamiento lo controla **`ChildRule.nodeable`**.

### Cómo Evalúan `nodeable` los Métodos `Ref.__init__` y `Ref.parse`

En `gram/core/combinators/reference.py`:

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

Y durante `Ref.parse(analyzer)`:
1. Si `self.name` tiene valor, `Ref.parse` envuelve el resultado coincidente en `ASTRef(self.name, nodes)`.
2. Si `self.name` es `None`, `Ref.parse` retorna el `result` crudo directamente (el cual `Seq` aplana dentro de la lista `nodes` de la regla contenedora).

### Caso 1: `nodeable = True` (Por Defecto — Crea un Nodo `ASTRef`)
Usa `nodeable = True` para reglas que representen construcciones sintácticas significativas en tu AST (como declaraciones, sentencias, parámetros, punteros o cláusulas). Cada vez que `Ref(MyRule)` coincide, produce un `ASTRef(name="MyRule", nodes=[...])`.

### Caso 2: `nodeable = False` (Regla Auxiliar Transparente — Inserción Plana de Hijos)
Usa `nodeable = False` para reglas intermedias de conveniencia o agrupación que solo existen para mantener modular la gramática, sin añadir capas de anidamiento innecesarias al AST.

Por ejemplo, en un frontend de C:
- `SIGNED` coincide con `MatchGroup('signed_')` (`signed` o `unsigned`). Establecer `nodeable = False` significa que `INTRINSIC_TYPE` recibe el `ASTKeyword('unsigned')` directamente en lugar de un anidado `ASTRef('SIGNED', [ASTKeyword('unsigned')])`.
- `TYPE` es un despachador `Alt(Ref(INTRINSIC_TYPE), Ref(ALIASED_TYPE))` donde `INTRINSIC_TYPE` y `ALIASED_TYPE` ya tienen `nodeable = True`. Establecer `TYPE.nodeable = False` evita envolver `ASTRef('INTRINSIC_TYPE', ...)` dentro de un innecesario `ASTRef('TYPE', ...)`.

### Modificar `nodeable` en la Llamada (Parámetros de `Ref`)

Puedes invalidar la configuración `nodeable` de una regla objetivo en cualquier instancia concreta de `Ref`:

| `TargetRule.nodeable` | Llamada a `Ref(...)` | Salida AST Resultante |
| :--- | :--- | :--- |
| `True` | `Ref(TargetRule)` | `ASTRef(TargetRule.name, [...])` |
| `True` | `Ref(TargetRule, name="Custom")` | `ASTRef("Custom", [...])` |
| `True` | `Ref(TargetRule, strict=True)` | Nodo(s) hijo(s) directos — **sin** contenedor `ASTRef` (`strict=True` impide copiar `TargetRule.name` cuando `name=None`) |
| `False` | `Ref(TargetRule)` | Nodo(s) hijo(s) directos — **sin** contenedor `ASTRef` |
| `False` | `Ref(TargetRule, name="ForcedNode")` | `ASTRef("ForcedNode", [...])` |

### Ejemplo Ejecutable Completo

```python
from gram import combinators as cmb
from gram import lexer, parser

lexer.words.clear_all()
lexer.words.add_group("types", allow_override=True)
lexer.words.add_group("signed_", allow_override=True)
lexer.words.add_keyword("int", group="types", allow_override=True)
lexer.words.add_keyword("unsigned", group="signed_", allow_override=True)

# Regla auxiliar: nodeable = False (inserta su token directamente en INTRINSIC_TYPE)
class SIGNED(cmb.RuleItem):
    entrypoint = cmb.MatchGroup("signed_")
    nodeable = False

# Regla de tipo concreto: nodeable = True (produce ASTRef("INTRINSIC_TYPE", ...))
class INTRINSIC_TYPE(cmb.RuleItem):
    entrypoint = cmb.Some(
        cmb.Alt(
            cmb.MatchGroup("types"),
            cmb.Ref(SIGNED),
        )
    )
    nodeable = True

# Regla despachadora: nodeable = False (deja pasar INTRINSIC_TYPE sin contenedor extra)
class TYPE(cmb.RuleItem):
    entrypoint = cmb.Alt(
        cmb.Ref(INTRINSIC_TYPE),
        cmb.MatchToken(lexer.Token.IDENT),
    )
    nodeable = False

# Regla de parámetro: nodeable = True (produce ASTRef("PAIR_PARAM", ...))
class PAIR_PARAM(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.Ref(TYPE),
        cmb.MatchToken(lexer.Token.IDENT),
    )
    nodeable = True

# Regla de punto de entrada raíz: debe ser un Alt de Ref(...)
class PROGRAM(cmb.RuleItem):
    entrypoint = cmb.Alt(cmb.Ref(PAIR_PARAM))

tokens = lexer.Lexer("unsigned int count").process()
ast_nodes = parser.Parser(tokens).parse(PROGRAM)
print("Root:", ast_nodes)
print("Hijos de PAIR_PARAM:", ast_nodes[0].nodes)
print("Hijos de INTRINSIC_TYPE:", ast_nodes[0].nodes[0].nodes)
# Salida:
# Root: [AstRef(nodes=2, name=PAIR_PARAM)]
# Hijos de PAIR_PARAM: [AstRef(nodes=2, name=INTRINSIC_TYPE), Identifier(value='count', line=1, col=13)]
# Hijos de INTRINSIC_TYPE: [ASTKeyword(value='unsigned', line=1, col=0), ASTKeyword(value='int', line=1, col=9)]
```

Observa cómo `PAIR_PARAM` contiene directamente `ASTRef('INTRINSIC_TYPE', [ASTKeyword('unsigned'), ASTKeyword('int')])` e `Identifier('count')`, sin nodos contenedores redundantes para `TYPE` o `SIGNED`.

---

## 4. Interacciones de `nodeable` con `Separator` y `VSIX`

1. **Validación en `Separator` (`UnnamedRefInSeparator`):**
   Cuando se pasa un `Ref` dentro de `Separator(sep=..., values=[...])`, `Separator` requiere que cada elemento `Ref` produzca un nodo `ASTRef` nombrado. Si pasas `Ref(HelperRule)` donde `HelperRule.nodeable` es `False` y no especificas un `name="..."` explícito en `Ref`, `Separator` reporta un `GrammarError` (`UnnamedRefInSeparator` / `GRAMMAR_COMBINATOR_UNSUPPORTED`).
2. **Mapas Declarativos de VSIX (`colors`, `autocomplete`, `suggestions`, `hints`, `playhints`):**
   `ASTColorResolver` proyecta `RuleItem.colors` sobre los nodos `ASTRef` haciendo coincidir `ref_node.name` con las clases `RuleItem` registradas. Si una regla tiene `nodeable = False`, nunca emite un nodo `ASTRef` en el AST, por lo que su mapa `colors` no puede proyectarse sobre el árbol (`VSIXAnalyzer` emite una advertencia si se combina `nodeable = False` con mapas de editor).

---

## 5. Reglas de Punto de Entrada Raíz (`Parser.parse` y `ASTAnalyzer`)

Cuando pasas una clase `RuleItem` raíz a `Parser(tokens).parse(ENTRYPOINT, mode="Many")` (o `ASTAnalyzer(parser, ENTRYPOINT, mode="Many")`), `ASTState.is_valid_entrypoint()` comprueba dos condiciones estructurales sobre `ENTRYPOINT`:
1. `ENTRYPOINT.entrypoint` **debe** ser un combinador `Alt` (de lo contrario reporta `AST_PROGRAM_INVALID_COMBINATOR`).
2. Cada elemento dentro de `ENTRYPOINT.entrypoint.combinators` **debe** ser un combinador `Ref` (de lo contrario reporta `AST_DECLARATOR_INVALID_ELEMENT`).

### Modos de Repetición de Nivel Superior (`"Many"` vs. `"Some"`)
- **`mode="Many"` (por defecto):** Evalúa repetidamente `ENTRYPOINT.entrypoint` a lo largo del flujo de tokens (omitiendo automáticamente los tokens `Token.NEWLINE` sueltos en el nivel superior) hasta alcanzar `Token.EOF`. Un archivo vacío retorna `[]`.
- **`mode="Some"`:** Requiere que al menos una sentencia de nivel superior coincida antes de `Token.EOF`, reportando `EntryPointMinimumNotMet` (`GRAMMAR_COMBINATOR_FAILED`) si la entrada no produce nodos en el AST.
