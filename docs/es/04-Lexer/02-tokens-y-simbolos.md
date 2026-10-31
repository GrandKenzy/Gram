# Catálogo de Tokens y Despacho de Símbolos

Gram representa todas las unidades sintácticas a través de dos componentes centrales:
- **`Token` (`Enum`):** La enumeración formal e inmutable de todos los tipos de tokens reconocidos por el framework.
- **`TokenType` (`class`):** La estructura concreta de lexema emitida por `Lexer`, que encapsula el tipo formal del token, el valor extraído de la fuente, las coordenadas y las banderas léxicas.

---

## 1. La Enumeración `Token`

Todos los tipos estándar residen en `gram.core.lexer.tokens.Token`, organizados formalmente en 11 categorías lógicas:

### 1. Estructura y Control de Flujo
| Miembro del Enum | Rol Típico | Valor Emitido |
| :--- | :--- | :--- |
| `Token.EOF` | Centinela de fin de archivo | `None` |
| `Token.NEWLINE` | Salto de línea lógico (cuando `LEXER_IGNORE_NEWLINES=False`) | `None` |
| `Token.IDENT` | Identificador de variable, función o tipo | `str` (ej. `"contador"`) |
| `Token.INDENT` | Incremento de nivel de bloque por indentación | `int` (nivel de columna destino) |
| `Token.DEDENT` | Decremento de nivel de bloque por indentación | `int` (nivel de columna previo) |
| `Token.COMMENT` | Comentario conservado (cuando `LEXER_SAVE_COMMENTS=True`) | `str` (cuerpo del comentario) |
| `Token.KEYWORD` | Palabra clave registrada en `words.MAP_KEYWORDS` | `str` (nombre de la keyword) |

### 2. Literales
| Miembro del Enum | Descripción | Tipo de Valor Emitido |
| :--- | :--- | :--- |
| `Token.STRING` | Cadena unilínea, docstring o literal multilínea | `str` |
| `Token.NUMBER` | Entero decimal, binario (`0b`), octal (`0o`), hex (`0x`) o numérico con sufijos | `int` o `str` (si posee sufijo) |
| `Token.DECIMAL` | Número de punto flotante (con `.`, exponente `e` o exponente hex `p`) | `float` o `str` (si posee sufijo) |
| `Token.BOOL` | Literal booleano que coincide con `TOKEN_BOOL_TRUE` o `TOKEN_BOOL_FALSE` | `bool` (`True` o `False`) |
| `Token.NULL` | Literal nulo que coincide con `TOKEN_NULL` | `None` |

### 3. Operadores Aritméticos
| Miembro del Enum | Símbolo | Miembro del Enum | Símbolo |
| :--- | :--- | :--- | :--- |
| `Token.PLUS` | `+` | `Token.POW` | `**` |
| `Token.MINUS` | `-` | `Token.FLOOR_DIV` | `//` |
| `Token.STAR` | `*` | `Token.INCREMENT` | `++` |
| `Token.SLASH` | `/` | `Token.DECREMENT` | `--` |
| `Token.PERCENT` | `%` | | |

### 4. Operadores de Asignación
| Miembro del Enum | Símbolo | Miembro del Enum | Símbolo |
| :--- | :--- | :--- | :--- |
| `Token.ASSIGN` | `=` | `Token.FLOOR_DIV_ASSIGN` | `//=` |
| `Token.PLUS_ASSIGN` | `+=` | `Token.AND_ASSIGN` | `&=` |
| `Token.MINUS_ASSIGN` | `-=` | `Token.OR_ASSIGN` | `\|=` |
| `Token.STAR_ASSIGN` | `*=` | `Token.XOR_ASSIGN` | `^=` |
| `Token.SLASH_ASSIGN` | `/=` | `Token.SHL_ASSIGN` | `<<=` |
| `Token.PERCENT_ASSIGN` | `%=` | `Token.SHR_ASSIGN` | `>>=` |
| `Token.POW_ASSIGN` | `**=` | `Token.WALRUS` | `:=` |

### 5. Operadores de Comparación
| Miembro del Enum | Símbolo | Descripción |
| :--- | :--- | :--- |
| `Token.EQUAL` | `==` | Prueba de igualdad |
| `Token.NOT_EQUAL` | `!=` | Prueba de desigualdad |
| `Token.LESS` | `<` | Estrictamente menor que |
| `Token.GREATER` | `>` | Estrictamente mayor que |
| `Token.LESS_EQUAL` | `<=` | Menor o igual que |
| `Token.GREATER_EQUAL` | `>=` | Mayor o igual que |

### 6. Operadores Lógicos y a Nivel de Bits
| Miembro del Enum | Símbolo | Descripción |
| :--- | :--- | :--- |
| `Token.NOT` | `~` | NOT a nivel de bits (complemento) |
| `Token.NOT_LOGIC` | `!` | Negación lógica |
| `Token.AND_LOGIC` | `&&` | Conjunción lógica |
| `Token.OR_LOGIC` | `\|\|` | Disyunción lógica |
| `Token.AND` | `&` | AND a nivel de bits |
| `Token.OR` | `\|` | OR a nivel de bits |
| `Token.XOR` | `^` | XOR a nivel de bits |
| `Token.SHL` | `<<` | Desplazamiento a la izquierda |
| `Token.SHR` | `>>` | Desplazamiento a la derecha |

### 7. Delimitadores
| Miembro del Enum | Símbolo | Miembro del Enum | Símbolo |
| :--- | :--- | :--- | :--- |
| `Token.LPAREN` | `(` | `Token.RPAREN` | `)` |
| `Token.LBRACKET` | `[` | `Token.RBRACKET` | `]` |
| `Token.LBRACE` | `{` | `Token.RBRACE` | `}` |

### 8. Puntuación y Símbolos Especiales
| Miembro del Enum | Símbolo | Miembro del Enum | Símbolo |
| :--- | :--- | :--- | :--- |
| `Token.COMMA` | `,` | `Token.DOLLAR` | `$` |
| `Token.DOT` | `.` | `Token.QUESTION` | `?` |
| `Token.COLON` | `:` | `Token.QUESTION_ASSIGN` | `?=` |
| `Token.SEMICOLON` | `;` | `Token.EXCLAMATION` | `!` |
| `Token.AT` | `@` | `Token.BACKSLASH` | `\` |
| `Token.HASH` | `#` | `Token.UNDERSCORE` | `_` |
| `Token.UNDERSCORES` | `__+` | | |

### 9. Flechas
| Miembro del Enum | Símbolo | Descripción |
| :--- | :--- | :--- |
| `Token.ARROW` | `->` | Flecha derecha simple (tipos de retorno, transiciones) |
| `Token.FAT_ARROW` | `=>` | Flecha gruesa (lambdas, ramas de match) |
| `Token.LEFT_ARROW` | `<-` | Flecha izquierda (recepción de canal, asignación) |
| `Token.DOUBLE_ARROW` | `<->` | Flecha bidireccional |

### 10. Símbolos Unicode (Lógica y Matemáticas)
| Miembro del Enum | Símbolo | Descripción |
| :--- | :--- | :--- |
| `Token.LOGIC_AND` | `∧` | Conjunción matemática |
| `Token.LOGIC_OR` | `∨` | Disyunción matemática |
| `Token.LOGIC_NOT` | `¬` | Negación matemática |
| `Token.SQRT` | `√` | Raíz cuadrada |
| `Token.INFINITY` | `∞` | Infinito |
| `Token.DEGREE` | `°` | Grado |
| `Token.MIDDLE_DOT` | `·` | Punto medio |
| `Token.BULLET` | `•` | Viñeta |
| `Token.SECTION` | `§` | Signo de sección |
| `Token.THREE_DOTS` | `...` | Puntos suspensivos (tres puntos) |

### 11. Estados Especiales
- **`Token.ERROR`:** Emitido cuando un carácter o fragmento no puede tokenizarse válidamente.
- **`Token.UNKNOWN`:** Estado de token no clasificado.
- **`Token.EMPTY_LINE`:** Marcador de diagnóstico para líneas completamente en blanco.

### Métodos de Clase en `Token`

```python
from gram.core.lexer import Token

# 1. Búsqueda insensible a mayúsculas por nombre en cadena
tok1 = Token.from_string("plus")       # Token.PLUS
tok2 = Token.from_string("IDENT")      # Token.IDENT

# 2. Búsqueda por código numérico ordinal
tok3 = Token.from_code(0)             # Token.EOF

# 3. Tupla inmutable con todos los miembros definidos
todos_los_tokens = Token.get_tokens()
print(f"Total de tokens definidos: {len(todos_los_tokens)}")
```

---

## 2. El Contenedor `TokenType`

Cada lexema emitido por el lexer es una instancia de `TokenType`:

```python
class TokenType:
    __slots__ = ("col", "description", "flags", "line", "token", "value")
```

### Atributos

- **`token` (`Token | CustomToken`):** Tipo formal del token (miembro del enum o token dinámico).
- **`value` (`Any`):** Valor extraído del código fuente (ej. `'mi_variable'`, `42`, `'texto'`).
- **`line` (`int`):** Número de línea física (**base 1**).
- **`col` (`int`):** Desplazamiento de columna en la línea (**base 0** crudo).
- **`description` (`str`):** Etiqueta contextual (ej. prefijo de cadena como `"L"` o `"u8"`).
- **`flags` (`TokenFlags`):** Banderas a nivel de bits asociadas durante la tokenización (ej. `SIMPLE_QUOTE`, `CHAR`).

### Métodos Clave

#### `long() -> int`
Calcula la columna final del token en la línea:
$$\text{long} = \text{col} + \text{len}(\text{str}(\text{value}))$$

#### `formatter(msg: str) -> str`
Interpola marcadores de posición del token en cadenas de diagnóstico:

| Marcador | Reemplazado Por | Ejemplo de Salida |
| :--- | :--- | :--- |
| `$name` | `self.token.name` | `"IDENT"` |
| `$value` / `$content` | `str(self.value)` | `"contador"` |
| `$line` | `str(self.line)` | `"12"` |
| `$col` | `str(self.col)` | `"4"` |
| `$len` | Longitud en caracteres del valor | `"8"` |
| `$long` | Columna final (`col + len`) | `"12"` |
| `$symbol` / `$sym` | Símbolo textual desde `MAP_SYMBOLS` | `"+"` |

```python
token = TokenType(Token.IDENT, "contador", line=11, col=4)
print(token.formatter("Error en $name '$value' ($line:$col, fin: $long)"))
# "Error en IDENT 'contador' (12:4, fin: 12)"
```

#### Contrato de Igualdad y Hash
- **Igualdad (`__eq__`):** Dos instancias de `TokenType` son iguales si coinciden tanto su `token` como su `value`. Comparar un `TokenType` directamente contra un `Token` o `CustomToken` evalúa si `self.token == other`.
- **Hash (`__hash__`):** Calcula `hash(self.token)`. Esto permite indexar y consultar conjuntos y diccionarios de forma coherente tanto con instancias `TokenType` como con miembros `Token`.

---

## 3. Tokens Dinámicos en Tiempo de Ejecución: `CustomToken`

`CustomToken` permite sintetizar tipos de tokens dinámicos sin modificar la enumeración inmutable `Token`:

```python
from gram.core.lexer import CustomToken, Token

# Crear un token dinámico para literales de expresiones regulares o marcadores DSL:
REGEX_TOKEN = CustomToken("REGEX", description="Literal de expresión regular")

# La comparación funciona contra cadenas, otros CustomTokens y miembros Token:
print(REGEX_TOKEN == "REGEX")         # True
print(repr(REGEX_TOKEN))              # "Token.REGEX"
```

Combinadores como `Tokenize` e `Item` admiten indistintamente miembros de `Token` o instancias de `CustomToken`.

---

## 4. Banderas Léxicas: `TokenFlags`

Asignadas en `token.flags` mediante `gram.core.lexer.flags`:

```python
class TokenFlags(IntFlag):
    NONE = 0
    SIMPLE_QUOTE = 1 << 0
    CHAR = 1 << 1
```

- **`flags.SIMPLE_QUOTE`:** Se activa en cadenas delimitadas por comillas simples (`'...'`) o dobles (`"..."`).
- **`flags.CHAR`:** Se activa cuando el contenido de una cadena tiene exactamente 1 carácter (ej. `'a'` o `"x"`).

```python
from gram.core.lexer import Lexer, flags, words
words.add_keyword("dummy", allow_override=True)

tokens = Lexer("'c' \"cadena larga\"").process()
tok_char, tok_str = tokens[0], tokens[1]

print(bool(tok_char.flags & flags.CHAR))          # True
print(bool(tok_char.flags & flags.SIMPLE_QUOTE))  # True
print(bool(tok_str.flags & flags.CHAR))           # False
```

---

## 5. El Motor de Operadores y `MAP_SYMBOLS`

Gram resuelve operadores mediante un diccionario bidireccional especializado, `MAP_SYMBOLS` (`_MapSymbolsDict`):

- **Búsqueda directa:** `MAP_SYMBOLS["+"] -> Token.PLUS`
- **Búsqueda inversa por Token:** `MAP_SYMBOLS[Token.PLUS] -> "+"`
- **Búsqueda inversa por Nombre:** `MAP_SYMBOLS["PLUS"] -> "+"`

### Resolución por Longitud Máxima (*Maximal Munch*)

Gram implementa **maximal munch** (coincidencia más larga): los operadores se evalúan usando `tokens.get_sorted_symbols()`, que ordena los símbolos registrados de mayor a menor longitud:

```python
# '<<=' (longitud 3) se evalúa antes que '<<' (longitud 2) y '<' (longitud 1)
# '**' (longitud 2) se evalúa antes que '*' (longitud 1)
# '->' (longitud 2) se evalúa antes que '-' (longitud 1)
```

### Registro Dinámico de Símbolos: `insert_symbol` y `disabled_symbol`

Puedes extender o modificar la tabla de operadores en tiempo de ejecución:

```python
from gram.core.lexer import Token, disabled_symbol, insert_symbol

# 1. Registrar un nuevo operador personalizado asociado a un miembro Token existente
insert_symbol("<>", Token.NOT_EQUAL)

# 2. Deshabilitar un operador para evitar colisiones con sintaxis propia
token_antiguo = disabled_symbol("§")
```

#### Invariantes y Validaciones de `insert_symbol`:
- `symbol` debe ser un `str` no vacío sin caracteres de espacio en blanco.
- `token` debe ser un miembro válido de la enumeración `Token`.
- Si `symbol` ya está asociado a otro token, `insert_symbol()` lanza un `ValueError` para prevenir sobrescrituras accidentales (usa `disabled_symbol()` antes de reasignarlo).
- Llamar a `insert_symbol()` o `disabled_symbol()` reconstruye de forma automática el índice inverso y la lista ordenada por longitud en sitio mediante `_sync_symbol_indexes()`.
