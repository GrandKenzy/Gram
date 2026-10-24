# Reglas, Átomos y Almacenamiento de Estado

Estas clases y combinadores definen reglas modulares de gramática (`RuleItem`, `Ref`), secuencias atómicas de tokens (`Item`), verificaciones de valores literales (`Literal`) y almacenamiento de tokens seguro ante checkpoints (`Save`, `Load`).

---

## 1. `RuleItem` (Clase de Regla de Producción)

Clase base declarativa (`gram.core.combinators.base.RuleItem`) para reglas gramaticales. Su metaclase (`RuleMeta`) asigna automáticamente `name` (tomando por defecto el nombre de la clase) y asigna un `code` numérico único a través de `AutoCode` en `code_manager`.

### Atributos de Clase
```python
class MyRule(RuleItem):
    entrypoint: Combinator | None = None
    name: str = ""            # Por defecto 'MyRule'
    code: int = 0             # Auto-asignado >= 21 a menos que se use SetCode(n)
    nodeable: bool = True     # Si es True, Ref(MyRule) envuelve los resultados en ASTRef
    description: str = ""

    # Mapas opcionales de metadatos VSIX / LSP (con claves por índice de token o 'this'):
    colors: dict[int | str, str] = {}
    autocomplete: dict[int | str, str] = {}
    suggestions: dict[int | str, Any] = {}
    hints: dict[int | str, str] = {}
    playhints: dict[int | str, str] = {}
```

### Requisitos del Punto de Entrada Raíz (Entrypoint)
Cuando se pasa una subclase de `RuleItem` como `entrypoint` raíz a `ASTAnalyzer(parser, RootRule)` o `Parser.parse(RootRule)`, `ASTState.is_valid_entrypoint()` comprueba que:
1. `RootRule.entrypoint` sea un combinador `Alt` (de lo contrario reporta `InvalidEntryPointCombinator`).
2. Cada hijo dentro de ese `Alt` sea un combinador `Ref` (de lo contrario reporta `InvalidEntryPointElement`).

---

## 2. `Ref` (Referencia a Regla)

Delega el parseo a `rule.entrypoint` en tiempo de evaluación, permitiendo recursión mutua y referencias anticipadas (*forward references*).

### Constructor
```python
Ref(
    rule: type[RuleItem],
    name: str | None = None,
    strict: bool = False,
)
```

- `name`: Etiqueta para el nodo `ASTRef` resultante.
- `strict`:
  - Si es `False` (por defecto) y `name is None`, si `getattr(rule, "nodeable", False)` es `True` (que es el valor predeterminado en `RuleItem`), `self.name` se establece automáticamente como `rule.name`.
  - Si es `True` y `name is None`, `self.name` permanece como `None` incluso si `rule.nodeable` es `True`.

### Forma de Retorno y Diagnósticos
- Si `rule.entrypoint` es `None`, reporta `EmptyRuleReference` (`GrammarError`) y retorna `None`.
- Si `self.name` no está vacío: envuelve el resultado coincidente en `ASTRef(name=self.name, nodes=...)` (`nodes` es siempre una `list`).
- Si `self.name` es `None`: retorna el resultado directo de `rule.entrypoint` sin envolverlo en `ASTRef`.

### Ejemplo
```python
from gram.core.combinators import MatchKeyword, MatchToken, Ref, RuleItem, Seq
from gram.core.lexer import Token

class Expr(RuleItem):
    nodeable = True
    entrypoint = MatchToken(Token.NUMBER)

class ReturnStmt(RuleItem):
    entrypoint = Seq(
        MatchKeyword("return"),
        Ref(Expr),  # produce ASTRef(name='Expr', nodes=[LiteralNumber])
    )
```

---

## 3. `Item`

Evalúa una secuencia fija de combinadores productores de tokens como una unidad atómica y aplana todos los objetos `TokenType` coincidentes en un `ItemNode` (subclase de `list[TokenType]`).

### Constructor
```python
Item(*matchs: Combinator)
```

### Ejecución y Forma de Retorno
- Si se invoca sin combinadores (`Item()`), retorna un `ItemNode([])` vacío.
- Evalúa cada hijo dentro de `analyzer.safe_mode()`.
- Si algún hijo retorna `None`, restaura el checkpoint inicial, reporta/emite `IncompleteItemSequence` (`GrammarError`) y retorna `None`.
- Extrae objetos `TokenType` del resultado de cada hijo (`TokenType`, `ASTTokenNode` mediante `.token`, `ItemNode`, `LiteralNode`, `list`, `tuple`). Si un hijo retorna cualquier otro objeto (como un `ASTRef`), restaura el checkpoint, reporta `InvalidItemElementType` (`GrammarError`) y retorna `None`.
- **Valor de Retorno:** `ItemNode(tokens)` en caso de éxito, o `None` en caso de fallo.

### Ejemplo
```python
from gram.core.combinators import Item, MatchToken
from gram.core.lexer import Token

double_colon = Item(
    MatchToken(Token.COLON),
    MatchToken(Token.COLON),
)
```

---

## 4. `Literal`

Valida el `.value` primitivo del token actual contra `literal` (o acepta cualquier token que no sea una palabra clave cuando se omite `literal`).

### Constructor
```python
Literal(literal: Any = _ANY_LITERAL)
```

- Los tokens `Token.KEYWORD` siempre son rechazados (reportando `KeywordNotAllowedInLiteral`).
- Cuando se proporciona `literal`, comprueba `tok.value == literal` (incluyendo igualdad numérica entre `int` y `float`).

### Forma de Retorno y Diagnósticos
- **Coincidencia:** Consume el token y retorna `LiteralNode([tok])` (subclase de `list[TokenType]`).
- **Discrepancia / EOF:** Reporta `LiteralUnexpectedEOF`, `KeywordNotAllowedInLiteral` o `LiteralValueMismatch` (`ParserError`) y retorna `None`.

### Ejemplo
```python
from gram.core.combinators import Literal

match_zero = Literal(0)
match_any_non_keyword = Literal()
```

---

## 5. `Save`

Almacena el `TokenType` actualmente en `parser.pos` en el diccionario seguro ante checkpoints `parser.storage[name]`.

### Constructor
```python
Save(
    name: str,
    matcher: Combinator | None = None,
    *,
    consume: bool = True,
)
```

### Modos de Consumo
1. **`matcher=None` (captura de ancho cero):** Almacena `parser.peek()` en `parser.storage[name]` sin hacer avanzar `parser.pos` y retorna el `TokenType` almacenado.
2. **`matcher` provisto, `consume=True` (por defecto):** Evalúa `matcher` (haciendo avanzar `parser.pos`), almacena el token original en `parser.storage[name]` y retorna el resultado AST de `matcher`. Si `matcher` falla, restaura el checkpoint, reporta `SaveMatcherFailed` y retorna `None`.
3. **`matcher` provisto, `consume=False` (captura con lookahead validado):** Evalúa `matcher`, luego restaura el checkpoint de modo que `parser.pos` no avanza, almacena el token en `parser.storage[name]` y retorna el `TokenType`.

### Ejemplo
```python
from gram.core.combinators import MatchToken, Save
from gram.core.lexer import Token

save_open_tag = Save("open_tag", MatchToken(Token.IDENT), consume=True)
```

---

## 6. `Load`

Lee, compara o intercambia un `TokenType` guardado previamente en `parser.storage[name]`.

### Constructor
```python
Load(
    name: str,
    mode: Literal["get", "match", "unmatch", "replace", "change"] = "get",
    matcher: Combinator | None = None,
)
```

### Modos y Consumo de Tokens
> **Importante:** En los modos `"match"`, `"unmatch"`, `"replace"` y `"change"`, `Load` solo avanza `parser.pos` si se pasa un combinador `matcher`. Cuando `matcher=None`, dichos modos operan en `parser.pos` sin consumir el token.

| Modo | Comportamiento | Valor de Retorno (`matcher=None`) | Valor de Retorno (`matcher` provisto) |
| :--- | :--- | :--- | :--- |
| `"get"` | Retorna `parser.storage[name]` sin inspeccionar ni mover el cursor. | `TokenType` guardado | `TokenType` guardado (`matcher` ignorado) |
| `"match"` | Requiere `current.token == saved.token` y `current.value == saved.value` (de lo contrario reporta `LoadMatchFailed`). | `current` (`TokenType`), cursor inalterado | Resultado de `matcher` (consume token) |
| `"unmatch"` | Requiere que `current` difiera en tipo o valor respecto a `saved` (de lo contrario reporta `LoadUnmatchFailed`). | `current` (`TokenType`), cursor inalterado | Resultado de `matcher` (consume token) |
| `"replace"` | Reemplaza `parser.tokens[parser.pos]` in-situ por `saved` (rastreado para reversión por checkpoint). | `saved` (`TokenType`), cursor inalterado | Resultado de `matcher` sobre el token reemplazado |
| `"change"` | Intercambia `parser.tokens[parser.pos]` y `parser.storage[name]`. | `saved` (`TokenType`), cursor inalterado | Resultado de `matcher` sobre el token intercambiado |

### Diagnósticos
- `StorageKeyNotFound` (`GrammarError`) si `name` no está en `parser.storage`.
- `LoadUnexpectedEOF` (`ParserError`) si `mode != "get"` y el flujo está vacío.
- `LoadMatcherFailed` (`GrammarError`) si `matcher` falla (restando el checkpoint, incluyendo cualquier mutación por `"replace"` o `"change"`).

### Ejemplo
```python
from gram.core.combinators import Load, MatchToken, Save, Seq
from gram.core.lexer import Token

# Coincide con un identificador de apertura y exige que el siguiente identificador tenga el mismo token y valor:
paired_ident = Seq(
    Save("tag", MatchToken(Token.IDENT)),
    Load("tag", mode="match", matcher=MatchToken(Token.IDENT)),
)
```
