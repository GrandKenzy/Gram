# Combinador de Validación Fluida (`Req`)

`Req` (`gram.core.combinators.req.Req`) valida que el token en `parser.pos` coincida con un tipo de token objetivo y ejecuta una cadena de funciones de validación y transformación sobre una copia superficial (`copy.copy`) del token antes de delegarlo a `analyzer.delegate_return_node(cloned_token)`.

---

## 1. Constructor

```python
Req(target_token: Token | CustomToken | str)
```

- `target_token`: Miembro del enum `Token` esperado, `CustomToken` o cadena con el nombre del token (`Token.IDENT`, `"IDENT"`, etc.).
- Cada método de validación o transformación encadenado agrega una operación a `self._operations` y retorna `self`.

---

## 2. Métodos de Validación

Si alguna validación falla, `Req` deja inalterado `parser.pos`, reporta `ReqConstraintFailed` (`GrammarError`) y retorna `None`.

### Comprobaciones de Mayúsculas, Minúsculas y Formato de Nombre
- `.is_lower()`: Requiere que `str(t.value).islower()` sea `True`.
- `.is_upper()`: Requiere que `str(t.value).isupper()` sea `True`.
- `.is_snake_case()`: Requiere `val == val.lower()` y `" " not in val` (donde `val = str(t.value)`).
- `.is_camel_case()`: Requiere que `val` no esté vacío, `val[0].isalpha()`, `"_" not in val` y `" " not in val`.

### Comprobaciones de Prefijo, Sufijo y Subcadenas
- `.startswith(prefix: str)`: Requiere `str(t.value).startswith(prefix)`.
- `.endswith(suffix: str)`: Requiere `str(t.value).endswith(suffix)`.
- `.contains(*items: str)`: Requiere que cada subcadena en `items` aparezca en `str(t.value)`.
- `.excludes(*items: str)`: Requiere que ninguna subcadena en `items` aparezca en `str(t.value)`.

### Longitud, Límites Numéricos e Igualdad
- `.length(n: int)`: Requiere `len(str(t.value)) == n`.
- `.min(n: int | float)`:
  - Si `isinstance(t.value, (int, float))`: requiere `t.value >= n`.
  - En caso contrario: requiere `len(str(t.value)) >= n`.
- `.max(n: int | float)`:
  - Si `isinstance(t.value, (int, float))`: requiere `t.value <= n`.
  - En caso contrario: requiere `len(str(t.value)) <= n`.
- `.mindig(n: int)`: Requiere al menos `n` caracteres en `str(t.value)` que cumplan `char.isdigit()`.
- `.maxdig(n: int)`: Requiere como máximo `n` caracteres en `str(t.value)` que cumplan `char.isdigit()`.
- `.equal(expected: Any)`: Requiere `str(t.value) == str(expected)`.
- `.unequal(not_expected: Any)`: Requiere `str(t.value) != str(not_expected)`.

---

## 3. Métodos de Transformación

Las transformaciones mutan `cloned_token.value` in-situ (sin mutar el token original en `parser.tokens` si un paso subsiguiente falla):

- `.apply_lower()`: Asigna `t.value = str(t.value).lower()`.
- `.apply_upper()`: Asigna `t.value = str(t.value).upper()`.
- `.apply_camel()`: Divide `str(t.value).replace("_", " ")` por espacios en blanco y une como `parts[0].lower() + "".join(x.title() for x in parts[1:])`.
- `.apply_zfill(width: int)`: Asigna `t.value = str(t.value).zfill(width)`.
- `.replace(old: str, new: str)`: Asigna `t.value = str(t.value).replace(old, new)`.
- `.change(new_val: Any)`: Asigna `t.value = new_val`.
- `.addl(prefix: str)`: Asigna `t.value = prefix + str(t.value)`.
- `.addr(suffix: str)`: Asigna `t.value = str(t.value) + suffix`.
- `.transform(target_fn: Callable[[Any], Any])`: Asigna `t.value = target_fn(t.value)`. Si `target_fn` lanza una excepción, `Req` la captura y reporta `ReqConstraintFailed`.

---

## 4. Forma de Retorno y Diagnósticos

- **Éxito:** Consume el token de `parser` y retorna `analyzer.delegate_return_node(cloned_token)` (`Identifier`, `LiteralNumber`, `LiteralString`, `ASTKeyword` o `LiteralSymbol`), donde `node.token.value` contiene el valor transformado.
- **Diagnósticos en Fallo:**
  - `ReqUnexpectedEOF` (`ParserError`) si `parser.empty()` es `True`.
  - `ReqTokenMismatch` (`ParserError`) si el nombre del tipo del token actual no coincide con `target_token`.
  - `ReqConstraintFailed` (`GrammarError`) si cualquier validación o paso `.transform()` falla.

---

## 5. Ejemplo

```python
from gram.core.combinators import Req
from gram.core.lexer import Token

# Identificador snake_case en minúsculas de al menos 3 caracteres, normalizado a MAYÚSCULAS
const_name = (
    Req(Token.IDENT)
    .is_snake_case()
    .min(3)
    .apply_upper()
)

# Número entre 10 y 100 inclusive
port_number = Req(Token.NUMBER).min(10).max(100)
```
