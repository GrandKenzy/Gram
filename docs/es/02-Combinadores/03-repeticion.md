# Combinadores de Repetición y Delimitación

Los combinadores de repetición evalúan bucles, escaneo de tokens hasta una condición de parada o nivel de indentación, y secuencias separadas por delimitadores.

---

## 1. `Many` (Cero o Más)

Evalúa repetidamente `combinator` ($0..n$ veces) mientras queden tokens en el flujo (`not parser.empty()`).

### Constructor
```python
Many(combinator: Combinator)
```

### Ejecución y Terminación de Bucles
Cada iteración guarda un checkpoint (`"MANY-Iteration"`) y ejecuta `combinator` dentro de un `analyzer.failure_scope()` aislado:
- **Coincidencia:** Agrega el resultado a `results`. Si el hijo coincidió sin hacer avanzar el cursor (`parser.pos == checkpoint.pos`), el bucle termina inmediatamente para evitar bucles infinitos de ancho cero.
- **Sin coincidencia (`res is None`):** Restaura el checkpoint de la iteración y sale del bucle.
  - Si la iteración fallida ya había avanzado más allá de `checkpoint.pos` (`attempt.candidate[0] > checkpoint.pos`), ese fallo parcial profundo se prepara y publica (cuando no esté dentro de un `safe_mode` exterior).
  - Si la iteración falló limpiamente en `checkpoint.pos`, el fallo se descarta.
- **Señales:**
  - `BreakFlowSignal`: Restaura el checkpoint de la iteración actual y sale limpiamente del bucle.
  - `SkipFlowSignal`: Si `parser.pos == checkpoint.pos`, restaura el checkpoint y sale del bucle; si la iteración ya había avanzado el cursor, conserva los tokens consumidos y comienza la siguiente iteración.
- **Valor de Retorno:** Siempre retorna `list[Any]` (`[]` cuando coinciden 0 iteraciones).

### Ejemplo
```python
from gram.core.combinators import Many, MatchGroup, MatchToken, Seq
from gram.core.lexer import Token

declarations = Many(
    Seq(MatchGroup("types"), MatchToken(Token.IDENT))
)
```

---

## 2. `Some` (Uno o Más)

Evalúa repetidamente `combinator` ($1..n$ veces). Requiere al menos una iteración exitosa.

### Constructor
```python
Some(combinator: Combinator)
```

### Ejecución y Forma de Retorno
- Comparte el mismo comportamiento de iteración, `BreakFlowSignal`, `SkipFlowSignal` y protección contra ancho cero que `Many`.
- **1 o más coincidencias:** Retorna `list[Any]` con los resultados coincidentes (y publica cualquier fallo parcial más profundo de la última iteración rechazada cuando no está en `safe_mode`).
- **0 coincidencias:** Restaura el checkpoint inicial, prepara/publica el candidato de fallo de la primera iteración (o `SomeMinimumNotMet`) y retorna `None`.

### Ejemplo
```python
from gram.core.combinators import MatchToken, Some
from gram.core.lexer import Token

non_empty_idents = Some(MatchToken(Token.IDENT))
```

---

## 3. `Until`

Examina `target` en cada posición del cursor y, mientras `target` no coincida, consume un token a la vez y lo convierte a través de `analyzer.delegate_return_node(tok)`.

### Constructor
```python
Until(
    target: Combinator,
    *,
    consume_target: bool = False,
    max_tokens: int | None = None,
)
```

- `consume_target`:
  - `False` (por defecto): Restaura el checkpoint del sondeo cuando `target` coincide, dejando los tokens de `target` sin consumir en el flujo.
  - `True`: Mantiene los tokens de `target` consumidos y agrega (o extiende, si `target` retornó una `list`) el resultado de `target` en la lista devuelta.
- `max_tokens`: Número máximo opcional de pasos de un solo token permitidos antes de que `target` deba coincidir.

### Valor de Retorno y Diagnósticos
- **Coincidencia:** Retorna `list[Any]` con elementos `ASTTokenNode` delegados consumidos antes de `target` (más el resultado de `target` cuando `consume_target=True`).
- **EOF o `max_tokens` alcanzado sin coincidir con `target`:** Restaura el checkpoint inicial, reporta `UntilTargetNotFound` (`GrammarError`) y retorna `None`.

### Ejemplo
```python
from gram.core.combinators import MatchToken, Until
from gram.core.lexer import Token

# Recolecta tokens como nodos AST hasta ';', dejando ';' en parser.pos
until_semicolon = Until(MatchToken(Token.SEMICOLON), consume_target=False)
```

---

## 4. `UntilIndent`

Consume tokens uno a uno (convirtiendo cada uno mediante `analyzer.delegate_return_node`) hasta encontrar un token `Token.INDENT` o `Token.DEDENT` que satisfaga `target`.

### Constructor
```python
UntilIndent(
    target: int | Literal["back", "front"] | str,
    *,
    consume_target: bool = False,
    allow_eof: bool = False,
    max_tokens: int | None = None,
)
```

- `target`:
  - `int` ($\ge 0$): Coincide cuando un `DEDENT` alcanza $\le \text{target}$ (desde un nivel inicial más alto) o un `INDENT` alcanza $\ge \text{target}$ (desde un nivel inicial más bajo), o es igual a `target`.
  - `"back"`: Coincide con un `Token.DEDENT` cuyo valor de indentación es inferior al nivel de indentación activo cuando `UntilIndent` comenzó.
  - `"front"`: Coincide con un `Token.INDENT` cuyo valor de indentación es superior al nivel de indentación activo cuando `UntilIndent` comenzó.
  - Cualquier entero negativo o cadena desconocida lanza `InvalidUntilIndentTarget` (`GrammarError`) en tiempo de construcción.
- `consume_target`: Si es `False` (por defecto), se detiene antes del token `INDENT`/`DEDENT` coincidente. Si es `True`, lo consume y agrega su nodo delegado.
- `allow_eof`: Si es `True`, alcanzar `EOF` sin encontrar el token de indentación objetivo tiene éxito y retorna `collected`.

### Valor de Retorno y Diagnósticos
- **Coincidencia:** Retorna `list[Any]` con instancias de nodos `ASTNode` delegados.
- **Fallo:** Si se alcanza `EOF` o `max_tokens` sin coincidencia (y `allow_eof=False`), restaura el checkpoint inicial, reporta `UntilIndentTargetNotFound` (`GrammarError`) y retorna `None`.

### Ejemplo
```python
from gram.core.combinators import UntilIndent

# Consume tokens hasta desindentar por debajo del nivel del bloque actual
body_tokens = UntilIndent("back", consume_target=False, allow_eof=True)
```

---

## 5. `Separator`

Parsea elementos separados por delimitadores (como `a, b, c`) con conteos mínimo/máximo de elementos y soporte para delimitador final opcional (*trailing delimiter*).

> **Nota:** La clase se llama `Separator` (no existe el alias `Sep` en `gram.core.combinators`).

### Constructor
```python
Separator(
    values: Sequence[Any] | Combinator | Token | type[RuleItem] | str,
    sep: Combinator | Token | str = Token.COMMA,
    min: int = 0,
    max: int | None = None,
    allow_trailing: bool = True,
)
```

- **Normalización de `values`:** Acepta un solo elemento o una secuencia de:
  - Miembros del enum `Token` o cadenas válidas con el nombre/símbolo del `Token` (envueltos en `MatchToken`).
  - Subclases de `RuleItem` con `nodeable = True` (envueltas en `Ref(rule)`).
  - Instancias de `Ref` que producen un `ASTRef` (`name` no está vacío, lo cual es automático cuando `rule.nodeable = True`). Pasar un `Ref` con `name=None` y `nodeable=False` lanza `UnnamedRefInSeparator` (`GrammarError`).
  - Cualquier otra instancia de `Combinator`.
  - Cadenas no reconocidas lanzan `InvalidSeparatorTokenName`; tipos no soportados lanzan `UnsupportedSeparatorValue`.
- **Normalización de `sep`:** Acepta un `Combinator`, un miembro del enum `Token` o un `str` (resuelto vía `Token.from_string`, `MAP_SYMBOLS` o `MatchSymbol`). Tipos no soportados lanzan `UnsupportedSeparatorDelimiter`.
- `min`: Mínimo de elementos requeridos (por defecto `0`).
- `max`: Límite superior opcional de elementos coincidentes (`None` para ilimitado).
- `allow_trailing`: Si es `True` (por defecto), permite un separador al final tras el último elemento coincidente sin requerir otro elemento.

### Forma de Retorno (`ArrayNode`)
Retorna un `ArrayNode` (`gram.core.ast.nodes.ArrayNode`) en caso de éxito, o `None` si coincidieron menos de `min` elementos:
- `node.items`: `tuple[Any, ...]` con los nodos de elementos coincidentes.
- `node.trailing`: `bool` (`True` si se consumió un separador final).
- Soporta `len(node)`, `iter(node)`, `node[i]` y `bool(node)`.

### Ejemplo
```python
from gram.core.combinators import Separator
from gram.core.lexer import Token

ident_list = Separator(
    values=[Token.IDENT],
    sep=Token.COMMA,
    min=1,
    allow_trailing=True,
)
```
