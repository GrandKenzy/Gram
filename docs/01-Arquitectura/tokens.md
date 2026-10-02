# Catálogo de Tokens y Tipos Léxicos (`gram.core.lexer.tokens`)

El módulo `gram.core.lexer.tokens` constituye el fundamento léxico del compilador del Framework Gram. Define el catálogo completo e inmutable de tipos de token (`Token`), la unidad atómica de emisión léxica con metadatos posicionales (`TokenType`), el soporte de tokens dinámicos en tiempo de ejecución (`CustomToken`) y el mapa bidireccional de operadores y caracteres especiales (`MAP_SYMBOLS`).

---

## 1. La Enumeración `Token`

Representa las categorías gramaticales y sintácticas base de Gram, organizadas formalmente en 11 categorías lógicas:

### 1.1 Estructura y Flujo de Control
- `EOF`: Fin de archivo / stream de entrada.
- `NEWLINE`: Salto de línea lógico significativo.
- `IDENT`: Identificador de variable, función o regla.
- `INDENT`: Incremento en el nivel de indentación de bloque.
- `DEDENT`: Decremento en el nivel de indentación de bloque.
- `COMMENT`: Comentario de línea o bloque.
- `KEYWORD`: Palabra clave reservada del lenguaje o DSL.

### 1.2 Literales
- `STRING`: Literal de cadena de texto (`"..."` o `'...'`).
- `CHAR`: Literal de carácter individual.
- `NUMBER`: Literal numérico entero o de punto flotante.
- `BOOL`: Literal booleano (`True`, `False`).
- `NULL`: Literal de ausencia de valor (`None`, `null`).
- `DOCSTRING`: Cadena de documentación de bloque o función.

### 1.3 Operadores Aritméticos
- `PLUS` (`+`), `MINUS` (`-`), `STAR` (`*`), `SLASH` (`/`), `PERCENT` (`%`)
- `POW` (`**`), `FLOOR_DIV` (`//`), `INCREMENT` (`++`), `DECREMENT` (`--`)

### 1.4 Operadores de Asignación
- `ASSIGN` (`=`), `PLUS_ASSIGN` (`+=`), `MINUS_ASSIGN` (`-=`), `STAR_ASSIGN` (`*=`)
- `SLASH_ASSIGN` (`/=`), `PERCENT_ASSIGN` (`%=`), `POW_ASSIGN` (`**=`), `FLOOR_DIV_ASSIGN` (`//=`)
- `AND_ASSIGN` (`&=`), `OR_ASSIGN` (`|=`), `XOR_ASSIGN` (`^=`), `SHL_ASSIGN` (`<<=`), `SHR_ASSIGN` (`>>=`)
- `WALRUS` (`:=`)

### 1.5 Operadores de Comparación
- `EQUAL` (`==`), `NOT_EQUAL` (`!=`)
- `LESS` (`<`), `GREATER` (`>`), `LESS_EQUAL` (`<=`), `GREATER_EQUAL` (`>=`)

### 1.6 Operadores Lógicos y Bitwise
- `NOT` (`~`), `NOT_LOGIC` (`!`), `AND_LOGIC` (`&&`), `OR_LOGIC` (`||`)
- `AND` (`&`), `OR` (`|`), `XOR` (`^`), `SHL` (`<<`), `SHR` (`>>`)

### 1.7 Delimitadores
- `LPAREN` (`(`), `RPAREN` (`)`)
- `LBRACKET` (`[`), `RBRACKET` (`]`)
- `LBRACE` (`{`), `RBRACE` (`}`)

### 1.8 Puntuación y Símbolos Especiales
- `COMMA` (`,`), `DOT` (`.`), `COLON` (`:`), `SEMICOLON` (`;`)
- `AT` (`@`), `HASH` (`#`), `DOLLAR` (`$`), `QUESTION` (`?`), `QUESTION_ASSIGN` (`?=`)
- `EXCLAMATION` (`!`), `BACKSLASH` (`\`), `UNDERSCORE` (`_`)

### 1.9 Flechas
- `ARROW` (`->`), `FAT_ARROW` (`=>`), `LEFT_ARROW` (`<-`), `DOUBLE_ARROW` (`<->`)

### 1.10 Símbolos Unicode (Lógica y Matemática)
- Lógicos: `LOGIC_AND` (`∧`), `LOGIC_OR` (`∨`), `LOGIC_NOT` (`¬`)
- Matemáticos: `SQRT` (`√`), `INFINITY` (`∞`), `DEGREE` (`°`)
- Notación: `MIDDLE_DOT` (`·`), `BULLET` (`•`), `SECTION` (`§`), `THREE_DOTS` (`...`)

### 1.11 Estados Especiales
- `ERROR`: Estado o token de fallo léxico.
- `UNKNOWN`: Token no clasificado o carácter desconocido.
- `EMPTY_LINE`: Línea vacía consumida.

### Métodos de Consulta de `Token`
```python
from gram.core.lexer.tokens import Token

# Por nombre textual (insensible a mayúsculas)
tok = Token.from_string("plus")       # Token.PLUS
tok = Token.from_string("IDENT")      # Token.IDENT

# Por valor ordinal
tok = Token.from_code(0)              # Token.EOF

# Colección inmutable completa
todos = Token.get_tokens()            # tuple[Token, ...]
```

---

## 2. Tokens Dinámicos con `CustomToken`

Permite a los plugins y creadores de DSLs registrar tipos de token dinámicos en tiempo de ejecución sin mutar la enumeración inmutable `Token`:

```python
from gram.core.lexer.tokens import CustomToken, Token

mi_token = CustomToken("SQL_SELECT", "SELECT")

# Comparaciones flexibles soportadas
print(mi_token == "SQL_SELECT")       # True
print(mi_token == CustomToken("SQL_SELECT")) # True
```

---

## 3. La Clase de Emisión `TokenType`

Cada elemento generado durante el proceso de tokenización es una instancia de `TokenType`. Contiene el valor concreto capturado del código fuente y sus coordenadas espaciales:

```python
from gram.core.lexer.tokens import Token, TokenType

tok = TokenType(
    token=Token.NUMBER,
    value=42,
    line=3,
    col=10,
    description="Literal entero base 10"
)

print(tok.token) # Token.NUMBER
print(tok.value) # 42
print(tok.line)  # 3
print(tok.col)   # 10
```

### Interpolación de Mensajes (`formatter`)
`tok.formatter(msg)` interpola variables contextuales para emitir diagnósticos detallados:
- `$name`: Nombre del token (`NUMBER`).
- `$value` / `$content`: Contenido o lexema (`42`).
- `$line`: Línea de origen (`3`).
- `$col`: Columna de origen (`10`).
- `$symbol`: Símbolo representativo si está en `MAP_SYMBOLS`.

### Emisión de Errores con `raise_error()`
Se conecta de manera natural con el catálogo formal OSGDC y la clase `LexerError`:

```python
# Emisión estructurada utilizando el catálogo oficial
tok.raise_error(
    "Formato numérico no admitido",
    "El número '$value' en la línea $line contiene caracteres no válidos.",
    "Elimine el sufijo desconocido."
)
```

---

## 4. Tabla `MAP_SYMBOLS` y Búsqueda Bidireccional

`MAP_SYMBOLS` implementa un diccionario bidireccional optimizado (`_MapSymbolsDict`) que permite resolver en $O(1)$ tanto el token asociado a un símbolo como el símbolo de un token:

```python
from gram.core.lexer.tokens import MAP_SYMBOLS, Token

# 1. Búsqueda por símbolo textual
tok = MAP_SYMBOLS['+=']           # Token.PLUS_ASSIGN

# 2. Búsqueda inversa por enumeración
sym = MAP_SYMBOLS.get(Token.PLUS_ASSIGN) # '+='

# 3. Búsqueda inversa por nombre
sym = MAP_SYMBOLS.get('PLUS_ASSIGN')     # '+='
```

### Principio de Coincidencia Máxima (Maximal Munch)
La función `get_sorted_symbols() -> list[str]` retorna todos los símbolos ordenados por longitud descendente:

```python
from gram.core.lexer.tokens import get_sorted_symbols

simbolos = get_sorted_symbols()
# ['<<=', '>>=', '//=', '**=', '<->', '...', '==', '!=', '<=', '>=', '+=', ...]
```

Esto garantiza que secuencias de caracteres como `<<=` se reconozcan como un único operador `SHL_ASSIGN` antes de descomponerse erróneamente en `<<` o `<`.
