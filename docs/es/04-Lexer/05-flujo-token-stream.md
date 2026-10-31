# Navegación del Flujo de Tokens (`TokenStream`)

Mientras que `Lexer.process()` retorna una lista plana nativa de Python (`list[TokenType]`), Gram proporciona `TokenStream` (`gram.core.lexer.items.TokenStream`) como un contenedor navegable, inspeccionable, filtrable y gestionado mediante cursores.

---

## 1. Instanciación de `TokenStream`

Puedes obtener un `TokenStream` directamente desde `Lexer.stream()` o envolviendo una secuencia de tokens existente:

```python
from gram.core.lexer import Lexer, TokenStream, words
words.add_keyword("let", allow_override=True)

# 1. Directamente desde el Lexer
stream = Lexer("let x = 10;").stream()

# 2. Envolviendo una lista de tokens existente
tokens = Lexer("let y = 20;").process()
stream = TokenStream(tokens)
```

La secuencia de tokens subyacente se almacena como una tupla inmutable `tuple[TokenType, ...]`, garantizando que la colección no pueda mutar accidentalmente durante su consumo.

---

## 2. Inspección del Cursor y Estado

`TokenStream` gestiona un cursor entero interno `_pos` que avanza conforme se consumen tokens.

### Propiedades y Métodos de Estado

| Miembro | Tipo de Retorno | Descripción |
| :--- | :--- | :--- |
| `stream.position` | `int` | Índice actual del cursor ($0 \le \text{pos} \le \text{len}$). Puede leerse o asignarse directamente. |
| `stream.tokens` | `tuple[TokenType, ...]` | Tupla inmutable con todos los tokens del flujo. |
| `stream.has_next()` | `bool` | Retorna `True` si quedan tokens pendientes distintos de `EOF`. |
| `stream.is_eof()` | `bool` | Retorna `True` si el cursor alcanzó `Token.EOF` o el final del flujo. |
| `stream.current()` | `TokenType \| None` | Retorna el token bajo el cursor actual sin consumirlo. Retorna `None` fuera de rango. |
| `stream.peek(offset=0)` | `TokenType \| None` | Inspecciona el token en `position + offset` sin desplazar el cursor. Retorna `None` fuera de rango. |

```python
stream = Lexer("let a = 10;").stream()

print(stream.position)        # 0
print(stream.current().token) # Token.KEYWORD ("let")
print(stream.peek(1).token)   # Token.IDENT ("a")
print(stream.peek(2).token)   # Token.ASSIGN ("=")
print(stream.has_next())      # True
```

---

## 3. API de Consumo y Coincidencia de Patrones

`TokenStream` ofrece cuatro métodos complementarios para consumir tokens: `advance()`, `check()`, `match()` y `consume()`.

### `advance() -> TokenType`
Consume el token actual e incrementa el cursor en 1. Si se invoca habiendo alcanzado el final, retorna un token sintético `TokenType(Token.EOF, None, line, col)`:

```python
tok1 = stream.advance()  # Consume 'let'
tok2 = stream.advance()  # Consume 'a'
```

### `check(*expected: Token | TokenType | str) -> bool`
Retorna `True` si el token bajo el cursor coincide con **cualquiera** de los criterios en `expected` sin desplazar el cursor:
- Si es `Token`, evalúa `curr.token == exp`.
- Si es `TokenType`, evalúa la igualdad estructural `curr == exp`.
- Si es `str`, evalúa `curr.value == exp` o `curr.token.name == exp`.

```python
if stream.check(Token.IDENT, "let"):
    print("Coincide con un identificador o con 'let'")
```

### `match(*expected: Token | TokenType | str) -> bool`
Consumo condicional: ejecuta `check(*expected)`. Si coincide, avanza el cursor mediante `advance()` y retorna `True`; de lo contrario, deja el cursor intacto y retorna `False`:

```python
# Consume '=' sólo si está presente:
if stream.match(Token.ASSIGN, "="):
    print("¡Operador de asignación consumido!")
```

### `consume(expected=None, message="") -> TokenType`
Consumo obligatorio. Verifica que el token actual coincida con `expected` antes de avanzar. Si no coincide, lanza un error estructurado `errors.ParserError`:
- Si se alcanzó el final prematuramente, lanza `PARSER_EARLY_EOF`.
- Si el token no concuerda, lanza `PARSER_UNEXPECTED_TOKEN` con las coordenadas y detalles del error.

```python
# Consumo estricto con aserción:
token_let = stream.consume(Token.KEYWORD, "Se esperaba la palabra clave 'let'")
token_nombre = stream.consume(Token.IDENT, "Se esperaba el nombre de la variable")
stream.consume("=", "Se esperaba '=' después del identificador")
```

---

## 4. Control del Cursor: `rewind()` y `reset()`

`TokenStream` permite retrocesos y reinicios del cursor para análisis especulativo:

```python
stream = Lexer("let x = 42;").stream()

stream.advance()  # Consume 'let' (pos = 1)
stream.advance()  # Consume 'x'   (pos = 2)

# Retroceder 1 posición:
stream.rewind(1)
print(stream.current().value)  # 'x' (pos = 1)

# Reiniciar el cursor al inicio del flujo:
stream.reset()
print(stream.current().value)  # 'let' (pos = 0)
```

---

## 5. Rebanadas y Filtrado de Tokens

### `slice(start: int, end: int | None = None) -> list[TokenType]`
Extrae una sub-lista de tokens entre `start` y `end`:

```python
stream = Lexer("let x = 10;").stream()
sub_tokens = stream.slice(0, 3)
print([t.value for t in sub_tokens])
# ['let', 'x', '=']
```

### `filter_tokens(*exclude: Token) -> TokenStream`
Retorna un **nuevo `TokenStream`** excluyendo todos los tokens cuyo tipo coincida con los miembros indicados en `exclude`:

```python
from gram.core.lexer import Lexer, Token, words
from gram import config
config.LEXER_IGNORE_NEWLINES = False
words.add_keyword("dummy", allow_override=True)

# Generar un flujo que contiene saltos de línea NEWLINE:
stream = Lexer("a = 1\nb = 2").stream()

# Filtrar los tokens NEWLINE:
flujo_limpio = stream.filter_tokens(Token.NEWLINE)
print([t.token for t in flujo_limpio])
# [Token.IDENT, Token.ASSIGN, Token.NUMBER,
#  Token.IDENT, Token.ASSIGN, Token.NUMBER, Token.EOF]
```

---

## 6. Protocolos de Secuencia de Python

`TokenStream` implementa los protocolos nativos de colecciones de Python:

```python
stream = Lexer("let x = 10;").stream()

# 1. Conteo total de tokens
total = len(stream)

# 2. Acceso por índice y rebanado directo
primer_token = stream[0]
sub_bloque = stream[1:3]

# 3. Iteración directa
for token in stream:
    if token.token == Token.EOF:
        break
    print(token)
```
