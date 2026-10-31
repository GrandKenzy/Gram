# Combinadores de Coincidencia Léxica

Los combinadores de coincidencia (`gram.core.combinators.match`) inspeccionan el token ubicado en `parser.pos`. Cuando coinciden, consumen el token (`parser.consume()`), descartan fallos candidatos obsoletos anteriores a la nueva posición y devuelven el nodo terminal `ASTNode` generado por `analyzer.delegate_return_node(token)`.

### Delegación de Token a Nodo del AST (`analyzer.delegate_return_node`)

Cada combinador de coincidencia delega el `TokenType` consumido a través de `ASTState.delegate_return_node(current)`, el cual mapea `current.token` de la siguiente forma:

| `current.token` | Subclase de `ASTNode` Retornada |
| :--- | :--- |
| `Token.IDENT` | `Identifier` |
| `Token.NUMBER` | `LiteralNumber` |
| `Token.STRING` | `LiteralString` |
| `Token.KEYWORD` | `ASTKeyword` |
| Cualquier otro `Token` o `CustomToken` | `LiteralSymbol` |

Todas las clases de nodos terminales heredan de `ASTTokenNode` (`gram.core.ast.nodes.ASTTokenNode`), exponiendo el `TokenType` consumido a través del atributo `node.token`.

---

## 1. `MatchToken`

Valida que el token actual coincida con un miembro específico del enum `Token`, un `CustomToken` o una cadena con el nombre canónico del `Token`.

> **Importante:** `MatchToken` rechaza explícitamente tokens de tipo `Token.KEYWORD` (reportando `UnexpectedKeywordToken`). Las palabras clave deben coincidir mediante `MatchKeyword` o `MatchGroup`.

### Constructor
```python
MatchToken(token: Token | CustomToken | str)
```

- Pasar un `str` lo resuelve mediante `Token.from_string(token)`. Si la cadena no coincide con ningún miembro de `Token`, se lanza `InvalidTokenReference` (`GrammarError`) en el momento de la instanciación.

### Retorno y Diagnósticos
- **Coincidencia:** Consume el token y retorna el `ASTTokenNode` correspondiente (`Identifier`, `LiteralNumber`, `LiteralString` o `LiteralSymbol`).
- **Discrepancia / EOF:** Deja `parser.pos` intacto, reporta `EmptyTokenStream`, `EOFReached`, `UnexpectedKeywordToken` o `TokenMismatch` (`ParserError`), y retorna `None`.

### Ejemplo
```python
from gram.core.combinators import MatchToken
from gram.core.lexer import Token

match_ident = MatchToken(Token.IDENT)
match_number = MatchToken("NUMBER")
```

---

## 2. `MatchKeyword`

Valida que el token actual tenga `current.token == Token.KEYWORD` y `current.value == keyword`.

### Constructor
```python
MatchKeyword(keyword: str | Keyword)
```

### Retorno y Diagnósticos
- **Coincidencia:** Consume el token y retorna un nodo `ASTKeyword` que contiene el token.
- **Discrepancia / EOF:** Reporta `EmptyTokenStream`, `KeywordTypeMismatch` o `KeywordValueMismatch` (`ParserError`) y retorna `None`.

### Ejemplo
```python
from gram.core.combinators import MatchKeyword
from gram.core.lexer import words

words.add_keyword("return")
match_return = MatchKeyword("return")
```

---

## 3. `MatchGroup`

Valida que el valor del token actual pertenezca a un `WordGroup` registrado en `gram.core.lexer.words` (`words.exists_in_group(current.value, group)`), con filtrado opcional de inclusión o exclusión.

### Constructor
```python
MatchGroup(
    group: str | WordGroup,
    values: Iterable[str] | None = None,
    behavior_values: Literal["allow", "deny", "none"] = "none",
)
```

### Modos de Filtrado (`behavior_values`)
- `"none"`: Acepta cualquier palabra clave registrada en el grupo `group`.
- `"allow"`: Acepta únicamente miembros de `group` cuyo lexema esté en `values` (de lo contrario reporta `GroupValueNotAllowed`).
- `"deny"`: Acepta miembros de `group` cuyo lexema **no** esté en `values` (de lo contrario reporta `GroupValueDenied`).

### Retorno y Diagnósticos
- **Coincidencia:** Consume el token y retorna un nodo `ASTKeyword`.
- **Discrepancia / Grupo Inexistente:**
  - Si `group` no existe en `words`, reporta `WordGroupNotFound` (`LexerError`) y retorna `None`.
  - Si el token no pertenece a `group`, reporta `GroupMismatch` (`ParserError`) y retorna `None`.

### Ejemplo
```python
from gram.core.combinators import MatchGroup
from gram.core.lexer import add_group, add_keyword

add_group("types")
add_keyword("int", group="types")
add_keyword("str", group="types")
add_keyword("bool", group="types")

match_any_type = MatchGroup("types")
match_numeric_only = MatchGroup("types", values=["int"], behavior_values="allow")
```

---

## 4. `MatchSeqSymbol`

`MatchSeqSymbol` valida `str(tok.value)` contra una expresión regular compilada (`fullmatch`) y opcionalmente reclasifica el atributo `.token` con un `CustomToken` antes de delegarlo al AST.

### Constructor
```python
MatchSeqSymbol(
    pattern: str | None = None,
    symbols: list[str] | None = None,
    regex: str | None = None,
    custom_token_name: str | None = None,
    is_pattern: bool = True,
    case_sensitive: bool = False,
    raw: bool = False,
)
```

- **Prioridad de resolución del patrón:**
  1. `regex`: Se utiliza tal cual (`is_pattern` se fuerza a `True`).
  2. `symbols`: Escapa cada cadena en `symbols` y las une con `|` (`is_pattern` se fuerza a `True`).
  3. `pattern`: Se interpreta como regex si `is_pattern=True`, o se escapa con `re.escape(pattern)` si `is_pattern=False`.
- `case_sensitive`: Por defecto es `False` (`re.IGNORECASE`). Configúralo en `True` para coincidencia estricta de mayúsculas y minúsculas.
- `custom_token_name`: Cuando se proporciona, reemplaza en sitio `tok.token` con `CustomToken(custom_token_name, val_str)` antes de delegar en `analyzer.delegate_return_node(tok)`.

### Retorno y Diagnósticos
- **Coincidencia:** Consume el token y retorna el `ASTTokenNode` delegado (un `LiteralSymbol` cuando se asigna `custom_token_name`, conteniendo el `CustomToken` en `node.token.token`).
- **Discrepancia / EOF:** Reporta `SymbolUnexpectedEOF` o `SymbolMismatch` (`ParserError`) y retorna `None`.

### Ejemplo
```python
from gram.core.combinators import MatchSeqSymbol

match_colon = MatchSeqSymbol(pattern=":", is_pattern=False)

match_comparison = MatchSeqSymbol(
    symbols=["==", "!=", "<=", ">="],
    custom_token_name="COMPARISON_OP",
)
```

---

## 5. `generador_expr`

Función auxiliar en `gram.core.combinators.match` que construye una cadena de expresión regular a partir de cadenas literales y rangos de dos elementos de caracteres o enteros `[inicio, fin]`.

```python
generador_expr(*parts: str | list[str | int] | tuple[str | int, str | int]) -> str
```

- Las partes literales de tipo `str` se escapan con `re.escape`.
- Los pares consecutivos `[inicio, fin]` de `str` o `int` se combinan en una clase de caracteres `[...]`.
- Cualquier otro tipo de argumento levanta `InvalidRegexGeneratorPart` (`GrammarError`).

### Ejemplo
```python
from gram.core.combinators import MatchSeqSymbol, generador_expr

# Produce '#[A-Fa-f0-9]'
hex_digit = generador_expr("#", ["A", "F"], ["a", "f"], [0, 9])
hex_matcher = MatchSeqSymbol(pattern=hex_digit, case_sensitive=True)
```
