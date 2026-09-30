# Motor del Analizador Léxico de Gram (`gram.core.lexer`)

El subsistema léxico (`gram.core.lexer`) es el componente responsable de transformar código fuente estructurado en un flujo continuo y determinista de lexemas clasificados (`TokenType`). Proporciona soporte integral para sintaxis sensible a la indentación (estilo Python/off-side rule), delimitación de comentarios personalizable, cadenas multilínea (docstrings), literales numéricos en múltiples bases y notación científica, operadores compuestos mediante máxima coincidencia (*maximal munch*), y un catálogo extensible de palabras clave y grupos semánticos.

---

## 1. Arquitectura General del Subsistema

```
                     Código Fuente (str / list[str])
                                   │
                                   ▼
                            ┌──────────────┐
                            │ check_state()│ (Verifica existencia de Keywords)
                            └──────┬───────┘
                                   │
                                   ▼
 ┌─────────────────────────────────────────────────────────────────────────┐
 │                                 LEXER                                   │
 │  ┌────────────────────────┐             ┌────────────────────────────┐  │
 │  │    process_indent()    │             │      process_comment()     │  │
 │  │  (INDENT / DEDENT)     │             │    (Comentarios de línea)  │  │
 │  └────────────────────────┘             └────────────────────────────┘  │
 │                                 │                                       │
 │                                 ▼                                       │
 │                       visit.process(lexer, char)                        │
 │                                 │                                       │
 │         ┌───────────────┬───────┴────────┬───────────────┐              │
 │         ▼               ▼                ▼               ▼              │
 │    ┌─────────┐    ┌───────────┐    ┌───────────┐   ┌───────────┐        │
 │    │ strings │    │  numbers  │    │   words   │   │  symbols  │        │
 │    └─────────┘    └───────────┘    └───────────┘   └───────────┘        │
 └─────────────────────────────────┬───────────────────────────────────────┘
                                   │
                                   ▼
                 Flujo de Tokens: list[TokenType]
                                   │
                                   ▼
               TokenStream (Navegación para el Parser)
```

### Módulos Principales
- **`gram.core.lexer` (`__init__.py`)**: Clase principal `Lexer`, funciones de conveniencia `tokenize()` y `tokenize_stream()`, y control de estado `check_state()`.
- **`gram.core.lexer.tokens`**: Catálogo inmutable `Token`, contenedor `TokenType`, tokens dinámicos `CustomToken`, y tabla bidireccional `MAP_SYMBOLS`.
- **`gram.core.lexer.words`** (y alias **`word`**): Catálogo global `MAP_KEYWORDS`, clases `Keyword`, `WordGroup` y gestor `WordGroupManager`.
- **`gram.core.lexer.visit`**: Despachador central que clasifica el carácter bajo el cursor y delega al visitor apropiado.
- **`gram.core.lexer.visitors`**: Analizadores especializados (`numbers`, `strings`, `symbols`, `words`).
- **`gram.core.lexer.items`**: Clase `TokenStream` para inspección, lookahead y consumo condicional en el parser.
- **`gram.core.lexer.stack`**: Instancia `StackInfo` para telemetría jerárquica y diagnóstico en tiempo de ejecución.

---

## 2. La Clase `Lexer`

La clase `Lexer` implementa el bucle de barrido del código fuente línea por línea y columna por columna.

### Constructor y Configuración
```python
Lexer(
    source: Sequence[str] | str,
    comment_token: str | Token | None = None,
    save_comments: bool | None = None,
    ignore_newlines: bool | None = None,
)
```
- **`source`**: Código fuente como cadena multilínea o secuencia de líneas.
- **`comment_token`**: Delimitador para comentarios de línea (por defecto `#`, configurable en `config.LEXER_COMMENT_TOKEN` o personalizado, e.g. `;` o `//`).
- **`save_comments`**: Determina si se emiten tokens `Token.COMMENT` en el flujo de salida o si se omiten silenciosamente (`config.LEXER_SAVE_COMMENTS`).
- **`ignore_newlines`**: Si es `True`, no guarda ni emite tokens `Token.NEWLINE` (`config.LEXER_IGNORE_NEWLINES`). Por defecto es `True`.

### Propiedades y Métodos de Posición
- **`currline`**: Retorna la línea física actual de forma segura.
- **`has_lines()`**: Indica si aún quedan líneas por procesar.
- **`is_empty()`**: Indica si la línea actual está vacía o contiene solo espacios en blanco.
- **`peek()`**: Devuelve el carácter actual sin avanzar el cursor.
- **`advance()`**: Consume y retorna el carácter actual, incrementando `col`.
- **`fail(message, code, *caution)`**: Registra el error en la pila de telemetría y levanta un `LexerError`.

### Gestión de Indentación (`process_indent`)
- Mantiene una pila interna de niveles de espacios `indents: list[int] = [0]`.
- Al inicio de cada línea física con contenido:
  - Si el número de espacios iniciales es mayor que el nivel anterior: se registra en la pila y emite un token `Token.INDENT`.
  - Si es menor: desapila los niveles hasta concordar con uno previo, emitiendo un `Token.DEDENT` por cada nivel desapilado.
  - Si la desindentación no coincide exactamente con ningún bloque anterior: lanza `errors.LEXER_INDENTATION_MISMATCH`.
- Al alcanzar el fin de archivo (`EOF`), cualquier bloque de indentación remanente es cerrado automáticamente emitiendo tokens `Token.DEDENT` hasta regresar al nivel base 0.

---

## 3. Catálogo de Palabras Clave y Grupos (`words.py` / `word.py`)

El lenguaje Gram no impone palabras clave estáticas en el código fuente duro del motor léxico; en su lugar, se registran dinámicamente mediante el subsistema `words`.

### Clase `Keyword`
Representa una palabra clave con metadatos asociados:
- **`name`**: Identificador textual único (e.g. `'def'`, `'if'`, `'return'`).
- **`hex_color`**: Color sugerido para syntax highlighting.
- **`group`**: Nombre del grupo lógico al que pertenece (opcional).
- **`description`**: Documentación contextual.
- **`_source_plugin`**: Módulo o plugin que registró la palabra clave (detección de procedencia).

### Clase `WordGroup` y `WordGroupManager`
Agrupa temáticamente palabras clave (por ejemplo tipos de datos, control de flujo o palabras de un plugin específico).
- **Regla estricta:** Solo se pueden agregar a un grupo palabras clave que ya hayan sido registradas en el catálogo de keywords. De lo contrario, lanza `errors.WORDGROUP_KEYWORD_NOT_REGISTERED`.
- Búsqueda insensible a mayúsculas mediante `contains()`.
- Soporte para verificación con el operador `in` de Python: `'i32' in grp`.

### API Funcional de `words`
```python
from gram.core.lexer import words

# Gestión de Keywords
words.add_keyword(name, hex_color="#FFFFFF", group=None, description="", allow_override=False)
words.get_keyword(name, strict=False)
words.keyword_exists(name)
words.remove_keyword(name, strict=False)
words.all_keywords()
words.all_keyword_names()
words.count_keywords()
words.is_empty()

# Gestión de Grupos
words.add_group(name, values=None, color_group="#FFA500", description="", allow_override=False)
words.get_group(name, strict=False)
words.group_exists(name)
words.remove_group(name)
words.all_groups()
words.all_group_names()
words.exists_in_group(keyword_name, group_name)

# Reseteo Global (Ideal para aislamiento en pruebas)
words.clear_all()
```

> **Compatibilidad:** El módulo `gram.core.lexer.word` funciona como un proxy transparente a `gram.core.lexer.words`.

---

## 4. Visitantes Especializados (`visitors/`)

Cada visitor es una unidad pura encargada de consumir caracteres del `Lexer` y construir el `TokenType` correspondiente:

### 4.1 Literales Numéricos (`visitors/numbers.py`)
- **Bases especiales:**
  - Hexadecimal: Prefijo `0x` o `0X` seguido de caracteres `[0-9a-fA-F]`.
  - Binario: Prefijo `0b` o `0B` seguido de `[0-1]`.
  - Octal: Prefijo `0o` o `0O` seguido de `[0-7]`.
  - Si se encuentra un prefijo sin dígitos (e.g. `0x` seguido de espacio), lanza `errors.LEXER_INVALID_NUMBER`.
- **Decimales y Notación Científica:**
  - Parte entera y parte fraccionaria separada por punto `.`.
  - Protección de rango: distingue entre decimal `3.14` y operador de rango `1..5`.
  - Exponentes: `1e5`, `2.5E-3`, `3e+2`. Exponentes vacíos lanzan `errors.LEXER_INVALID_NUMBER`.
- **Separadores visuales:** Soporte total para guiones bajos entre dígitos (e.g. `1_000_000`, `0xFF_FF`).

### 4.2 Cadenas y Docstrings (`visitors/strings.py`)
- **Cadenas estándar:** Delimitadas por `'` o `"` en una sola línea física.
- **Docstrings multilínea:** Delimitadas por triple comilla `'''` o `"""`. Pueden abarcar múltiples líneas y preservan saltos de línea físicos.
- **Secuencias de Escape:**
  - Estándar: `\n`, `\r`, `\t`, `\b`, `\f`, `\v`, `\0`, `\\`, `\'`, `\"`.
  - Unicode: `\uXXXX` interpretando 4 dígitos hexadecimales como punto de código Unicode.
- **Errores:** Cadenas o docstrings sin cerrar levantan `errors.LEXER_UNCLOSED_STRING`.

### 4.3 Símbolos y Operadores (`visitors/symbols.py`)
- Implementa **Maximal Munch**: Siempre intenta coincidir la cadena más larga posible registrada en `tokens.get_sorted_symbols()`.
  - Ejemplo: `<<=` genera `Token.SHL_ASSIGN` en lugar de `Token.SHL` (`<<`) y `Token.ASSIGN` (`=`).
  - Ejemplo: `==` genera `Token.EQUAL` en lugar de dos `Token.ASSIGN` (`=`).
- Símbolos Unicode: Reconoce operadores lógicos (`∧`, `∨`, `¬`), matemáticos (`√`, `∞`, `°`) y especiales (`...`, `·`, `•`).
- Errores: Cualquier carácter no contemplado genera `errors.LEXER_UNEXPECTED_CHARACTER`.

### 4.4 Palabras e Identificadores (`visitors/words.py`)
- Consume caracteres alfanuméricos y guiones bajos `[a-zA-Z_][a-zA-Z0-9_]*`.
- **Resolución jerárquica:**
  1. Booleanos: `'true'` -> `Token.BOOL` (valor `True`), `'false'` -> `Token.BOOL` (valor `False`).
  2. Nulos: `'null'` -> `Token.NULL` (valor `None`).
  3. Palabras clave: Si el texto está registrado en `words.MAP_KEYWORDS`, emite `Token.KEYWORD`.
  4. Identificadores: En cualquier otro caso emite `Token.IDENT`.

---

## 5. El Despachador Central (`visit.py`)

Función única `process(lexer, char)`:
1. Crea un subnodo de trazabilidad en la pila `info_node`.
2. Si `char in '"\'`: despacha a `strings.process`.
3. Si `char.isdigit()`: despacha a `numbers.process`.
4. Si `char.isalpha() or char == '_'`: despacha a `words.process`.
5. En cualquier otro caso: despacha a `symbols.process`.

---

## 6. Utilidades de Flujo: `TokenStream` (`items.py`)

`TokenStream` envuelve la lista inmutable de tokens producida por el lexer y ofrece una API fluida de navegación para el parser y los combinadores:

```python
from gram.core.lexer import tokenize_stream

stream = tokenize_stream("def suma(a, b): return a + b")

# Posición y estado
stream.position      # Índice entero actual
stream.has_next()    # True si quedan tokens antes de EOF
stream.is_eof()      # True si está en EOF

# Lectura
stream.current()     # Token actual sin consumir
stream.peek(1)       # Token siguiente sin consumir
stream.advance()     # Consume y avanza una posición

# Verificación y coincidencia
stream.check(Token.KEYWORD)       # Retorna bool sin avanzar
stream.match(Token.KEYWORD)       # Consume y retorna True si coincide
stream.consume(Token.LPAREN)      # Consume o lanza PARSER_UNEXPECTED_TOKEN

# Manipulación
stream.rewind(1)                  # Retrocede n posiciones
stream.reset()                    # Vuelve al inicio (posición 0)
filtered = stream.filter_tokens(Token.NEWLINE, Token.COMMENT)
```

---

## 7. Catálogo de Errores Formales (OSGDC)

El analizador léxico interactúa con los siguientes códigos del catálogo oficial `gram.errors`:

| Código OSGDC | Nombre Canónico | Excepción | Causa |
| :--- | :--- | :--- | :--- |
| `S-11010` | `Gram.Lexer.EmptyKeywords` | `LexerError` | Iniciar el análisis léxico sin palabras clave registradas. |
| `S-11411` | `Gram.Lexer.UnexpectedCharacter` | `LexerError` | Carácter no reconocido en la gramática léxica. |
| `S-11412` | `Gram.Lexer.InvalidNumber` | `LexerError` | Literal numérico malformado (base o exponente incompleto). |
| `S-11413` | `Gram.Lexer.UnclosedString` | `LexerError` | Cadena o docstring sin comilla de cierre. |
| `S-11415` | `Gram.Lexer.IndentationMismatch` | `LexerError` | Nivel de desindentación no coincide con ningún bloque previo. |
| `S-11416` | `Gram.Lexer.KeywordAlreadyExists` | `LexerError` | Intento de registrar una keyword ya existente sin `allow_override`. |
| `S-11417` | `Gram.Lexer.KeywordNotFound` | `LexerError` | Consulta con `strict=True` de una palabra no registrada. |
| `S-11418` | `Gram.Lexer.KeywordInvalidName` | `LexerError` | Nombre de palabra clave vacío o con blancos. |
| `S-11419` | `Gram.Lexer.WordGroupKeywordNotRegistered` | `LexerError` | Agregar a un grupo una palabra no registrada en el lexer. |
| `S-11420` | `Gram.Lexer.WordGroupAlreadyExists` | `LexerError` | Crear un grupo con nombre duplicado sin `allow_override`. |
| `S-11421` | `Gram.Lexer.WordGroupNotFound` | `LexerError` | Consulta con `strict=True` de un grupo no registrado. |

---

## 8. Ejemplos de Uso

### Ejemplo 1: Tokenización Completa de un Programa
```python
from gram.core.lexer import Lexer, add_keyword, Token

# 1. Registrar palabras clave del lenguaje
add_keyword("fn")
add_keyword("let")
add_keyword("return")

# 2. Código fuente
codigo = """
fn calcular(base, exp):
    let res = base ** exp
    return res
"""

# 3. Procesar
lexer = Lexer(codigo)
tokens = lexer.process()

for tok in tokens:
    print(f"L{tok.line:02d}:C{tok.col:02d} | {tok.token.name:<15} | {tok.value!r}")
```

### Ejemplo 2: Procesamiento con TokenStream
```python
from gram.core.lexer import tokenize_stream, Token

stream = tokenize_stream("let total = 100 + 20")

stream.consume("let")          # Consume Token.KEYWORD 'let'
ident = stream.consume(Token.IDENT)  # 'total'
stream.consume("=")            # Token.ASSIGN
num1 = stream.consume(Token.NUMBER) # 100
stream.consume("+")            # Token.PLUS
num2 = stream.consume(Token.NUMBER) # 20

print(f"Asignando {num1.value} + {num2.value} a {ident.value}")
```
