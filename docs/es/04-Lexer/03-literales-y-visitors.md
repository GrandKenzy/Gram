# Literales y Visitors Especializados

Gram utiliza un **patrón de despacho modular por visitors** alojado en el subpaquete `gram.core.lexer.visitors`. En lugar de ejecutar una expresión regular monolítica sobre todo el archivo de entrada, `Lexer` inspecciona el carácter actual bajo el cursor y delega el control a módulos visitor altamente especializados.

---

## 1. Arquitectura del Despachador Principal (`visitors.visit`)

Siempre que el bucle de `Lexer.process()` encuentra texto que no es espacio en blanco, ni comentario, ni delimitador multilínea, delega la tokenización a `visitors.visit(lexer, char)`:

```python
def visit(lexer: LexerState, char: str) -> TokenType:
```

### Orden de Precedencia del Despacho

```
Carácter bajo el cursor
         │
         ├─► ¿Cadena con prefijo? (L"...", u"...", U"...", u8"...")
         │   (si LEXER_SUPPORT_PREFIXED_STRINGS es True)
         │   └──► DESPACHAR A: strings.process(..., prefix=..., start_override=...)
         │
         ├─► ¿Comillas? (' o ")
         │   └──► DESPACHAR A: strings.process()
         │
         ├─► ¿Dígito (0-9) O Punto inicial (ej. .5)?
         │   (El punto inicial se evalúa si LEXER_SUPPORT_LEADING_DOT_NUMBERS es True)
         │   └──► DESPACHAR A: numbers.process()
         │
         ├─► ¿Carácter alfabético o guion bajo ([a-zA-Z_])?
         │   └──► DESPACHAR A: words.process()
         │
         └─► Fallback (Operadores, Delimitadores, Puntuación, Unicode)
             └──► DESPACHAR A: symbols.process()
```

Cuando la telemetría de diagnósticos está activa (`LEXER_ADD_INFO=True`), `visit()` anida un nodo de ejecución en el árbol (`VISITOR-STRING`, `VISITOR-NUMBER`, `VISITOR-WORD` o `VISITOR-SYMBOL`) para registrar la actividad del visitor, cerrando el nodo dentro de un bloque `finally: lexer.down()`.

---

## 2. Literales Numéricos (`visitors.numbers`)

El visitor de números de Gram procesa literales enteros y de punto flotante compatibles con C, con soporte total para bases numéricas alternativas, notación científica, separadores de dígitos y sufijos de tipo.

### Literales Numéricos Soportados

| Categoría | Sintaxis de Ejemplo | Token Emitido | Tipo de `value` Evaluado |
| :--- | :--- | :--- | :--- |
| **Entero Decimal** | `42`, `100_000` | `Token.NUMBER` | `int` (`42`, `100000`) |
| **Base Binaria** | `0b1010`, `0B1100_0011` | `Token.NUMBER` | `int` (`10`, `195`) |
| **Base Octal** | `0o755`, `0O644` | `Token.NUMBER` | `int` (`493`, `420`) |
| **Entero Hexadecimal** | `0x1A2F`, `0XDEAD_BEEF` | `Token.NUMBER` | `int` (`6703`, `3735928559`) |
| **Flotante Decimal** | `3.14159`, `1.5e-4`, `2E+3` | `Token.DECIMAL` | `float` (`3.14159`, `0.00015`, `2000.0`) |
| **Flotante con Punto Inicial** | `.5`, `.125e2` | `Token.DECIMAL` | `float` (`0.5`, `12.5`) |
| **Flotante Hexadecimal** | `0x1.2p3`, `0x.4p-1` | `Token.DECIMAL` | `float` (`9.0`, `0.125`) |
| **Entero con Sufijos** | `42UL`, `0x10ULL`, `100u` | `Token.NUMBER` | `str` (`"42UL"`, `"0x10ULL"`, `"100u"`) |
| **Flotante con Sufijos** | `1.0f`, `2.5L`, `0x1.fp2f` | `Token.DECIMAL` | `str` (`"1.0f"`, `"2.5L"`, `"0x1.fp2f"`) |

### Reglas e Invariantes Clave de Análisis

#### 1. Distinción de Tokens: `Token.DECIMAL` vs. `Token.NUMBER`
- Cualquier literal numérico que contenga un punto decimal (`.`), un exponente binario (`p`/`P` en flotantes hexadecimales) o un exponente decimal (`e`/`E` en números decimales) se clasifica estrictamente como **`Token.DECIMAL`**.
- Todos los enteros convencionales y literales con base (`0b`, `0o`, `0x`) se clasifican como **`Token.NUMBER`**.

#### 2. Contrato de Preservación de Sufijos
Cuando los literales numéricos incluyen sufijos de tipo al estilo C (`u`, `U`, `l`, `L`, `f`, `F`):
- **Números sin sufijo:** Se convierten directamente a tipos primitivos `int` o `float` de Python para su uso inmediato.
- **Números con sufijo:** Conservan su representación exacta en **cadena de texto** (ej. `"1.0f"`). Esto permite que las fases semánticas posteriores o chequeadores de tipos distingan con precisión `int`, `unsigned long`, `float` y `double` sin tener que volver a escanear el código fuente.

#### 3. Validación de Separadores por Guion Bajo (`_has_invalid_separator`)
Los guiones bajos (`_`) pueden utilizarse como separadores visuales de dígitos, pero no pueden ubicarse en posiciones inválidas:
- `1_000_000` ── Válido.
- `_123` ── Se escanea como `Token.IDENT` (`"_123"`), no como número.
- `123_` ── Separador final inválido. Emite `Token.ERROR` y reporta `LEXER_INVALID_NUMBER`.
- `1__2` ── Separadores consecutivos inválidos. Emite `Token.ERROR`.
- `0x_12` ── Separador inválido tras el prefijo de base. Emite `Token.ERROR`.

#### 4. Precedencia de Base Hexadecimal
Dado que los dígitos hexadecimales incluyen `e`, `E`, `f` y `F`, el visitor evalúa los literales hexadecimales antes de verificar exponentes decimales o sufijos flotantes. Esto evita que literales válidos como `0xface` o `0x1f` se interpreten erróneamente como números científicos corruptos.

---

## 3. Cadenas y Literales Multilínea (`visitors.strings`)

El visitor de cadenas procesa cadenas unilínea entre comillas, literales con prefijo y docstrings multilínea.

### Cadenas Unilínea (`'...'` y `"..."`)

Delimitadas por comillas simples o dobles equivalentes:

```python
from gram.core.lexer import Lexer, Token, flags, words
words.add_keyword("dummy", allow_override=True)

tokens = Lexer("'hola' \"mundo\"").process()
print(tokens[0])  # TokenType(token=Token.STRING, value='hola', flags=SIMPLE_QUOTE)
```

#### Resolución de Secuencias de Escape (`process_escape`)

Las secuencias de escape estándar de C/Python se decodifican automáticamente:

| Secuencia de Escape | Carácter Decodificado | Significado |
| :--- | :--- | :--- |
| `\n` | `"\n"` | Salto de línea |
| `\r` | `"\r"` | Retorno de carro |
| `\t` | `"\t"` | Tabulador horizontal |
| `\b` | `"\b"` | Retroceso (Backspace) |
| `\f` | `"\f"` | Salto de página (Form feed) |
| `\v` | `"\v"` | Tabulador vertical |
| `\0` | `"\0"` | Byte nulo |
| `\\` | `"\\"` | Barra invertida literal |
| `\"` | `"\""` | Comilla doble escapada |
| `\'` | `"\'"` | Comilla simple escapada |
| `\uXXXX` | `chr(0xXXXX)` | Punto de código Unicode hex de 4 dígitos (ej. `\u00A9` -> `©`) |

Cualquier carácter de escape no reconocido `\c` se conserva como la secuencia literal `"\c"`.

### Cadenas con Prefijos (Estilo C)

Cuando `config.LEXER_SUPPORT_PREFIXED_STRINGS=True`, Gram reconoce los prefijos antepuestos a las comillas:
- `L"..."` / `L'...'` ── Cadena / carácter ancho (*wide*).
- `u"..."` / `u'...'` ── Cadena UTF-16.
- `U"..."` / `U'...'` ── Cadena UTF-32.
- `u8"..."` / `u8'...'` ── Cadena UTF-8.

El prefijo detectado se guarda directamente en `token.description`:

```python
tokens = Lexer('L"texto ancho" u8"texto utf8"').process()
print(tokens[0].description)  # "L"
print(tokens[0].value)        # "texto ancho"
print(tokens[1].description)  # "u8"
```

### Cadenas Multilínea y Docstrings (`"""..."""` y `'''...'''`)

Cuando `config.LEXER_SUPPORT_DOCSTRINGS=True`, los bloques entre comillas triples abarcan múltiples líneas físicas:

```python
codigo = '''"""
Línea 1
Línea 2
"""'''
tokens = Lexer(codigo).process()
print(tokens[0].value)  # "\nLínea 1\nLínea 2\n"
```

El escaneo multilínea actualiza `lexer.line` y `lexer.col` dinámicamente mientras conserva el `start_line` y columna inicial original para el `TokenType` generado.

### Delimitadores Multilínea Personalizados (`add_multline`)

Puedes registrar pares de apertura y cierre arbitrarios mediante `gram.core.lexer.multiline`:

```python
from gram.core.lexer import Lexer, add_multline, list_multline, remove_multline, words
words.add_keyword("dummy", allow_override=True)

# Registrar un delimitador personalizado de bloque crudo:
add_multline("<<<", ">>>")

tokens = Lexer("<<<contenido\nmultilínea\ncrudo>>>").process()
print(tokens[0].value)  # "contenido\nmultilínea\ncrudo"

# Limpieza posterior
remove_multline("<<<")
```

---

## 4. Palabras, Keywords y Booleanos (`visitors.words`)

El visitor de palabras procesa secuencias contiguas de caracteres alfanuméricos y guiones bajos (`[a-zA-Z_][a-zA-Z0-9_]*`), reguladas por `ident_underscores`.

### Control de Guiones Bajos Iniciales en Identificadores (`ident_underscores`)

Gram permite controlar con total precisión cómo se gestionan los guiones bajos al comienzo de los identificadores mediante `config.LEXER_IDENT_UNDERSCORES` o `Session(..., ident_underscores=...)`:

> [!NOTE]
> La configuración `ident_underscores` aplica **estrictamente al comienzo (guiones bajos iniciales)** del identificador. Los guiones bajos intermedios o finales en identificadores que comienzan con caracteres alfanuméricos (como `A______B` o `D____________`) son completamente agnósticos a estas reglas y se conservan siempre íntegros dentro del `IDENT` en todos los modos.

| Modo | Semántica | Entrada de Ejemplo | Tokens Emitidos |
| :--- | :--- | :--- | :--- |
| **`-1` (Por defecto)** | Guiones bajos iniciales ilimitados; secuencias aisladas de `_` son `IDENT`. | `___Hola`<br>`___`<br>`A______B` | `[IDENT("___Hola")]`<br>`[IDENT("___")]`<br>`[IDENT("A______B")]` |
| **`-2`** | Guiones bajos iniciales ilimitados **sólo si van seguidos de caracteres alfanuméricos**; secuencias aisladas emiten `UNDERSCORE`. | `___Hola`<br>`___`<br>`D____________` | `[IDENT("___Hola")]`<br>`[UNDERSCORE, UNDERSCORE, UNDERSCORE]`<br>`[IDENT("D____________")]` |
| **`0`** | Ningún identificador permite guiones bajos iniciales; todo `_` inicial o aislado emite `UNDERSCORE`. | `_H`<br>`__H`<br>`A______B` | `[UNDERSCORE, IDENT("H")]`<br>`[UNDERSCORE, UNDERSCORE, IDENT("H")]`<br>`[IDENT("A______B")]` |
| **`k >= 1`** | Máximo `k` guiones bajos iniciales en `IDENT`; el exceso previo se emite como tokens `UNDERSCORE` individuales. | `__H` (con `k=1`)<br>`___H` (con `k=1`)<br>`A______B` | `[UNDERSCORE, IDENT("_H")]`<br>`[UNDERSCORE, UNDERSCORE, IDENT("_H")]`<br>`[IDENT("A______B")]` |

```python
from gram import sessions

session = sessions.Session("UnderscoreDemo", "Some", ident_underscores=1)
session.add_keyword("fn")

tokens = session.tokenize("__H = 10;", "demo")
# Emite: Token.UNDERSCORE ('_'), Token.IDENT ('_H'), Token.ASSIGN ('='), Token.NUMBER (10), Token.SEMICOLON (';')
```

### Jerarquía Determinista de 4 Niveles

La clasificación es estrictamente determinista:

```
                      Palabra Escaneada
                              │
                              ▼
                 1. ¿Booleano Configurado?
             (coincidencia insensible a mayúsculas
            contra TOKEN_BOOL_TRUE o TOKEN_BOOL_FALSE)
                 │ SÍ                     │ NO
                 ▼                        ▼
         Emitir Token.BOOL        2. ¿Nulo Configurado?
                                (coincidencia insensible a
                               mayúsculas contra TOKEN_NULL)
                                           │ SÍ       │ NO
                                           ▼          ▼
                                   Emitir Token.NULL  3. ¿Keyword Registrada?
                                                     (coincidencia exacta sensible
                                                      a mayúsculas en MAP_KEYWORDS)
                                                              │ SÍ        │ NO
                                                              ▼           ▼
                                                     Emitir Token.KEYWORD 4. Emitir Token.IDENT
```

### Ejemplos de Precedencia Determinista

1. **Booleanos sobre Keywords:** Si `TOKEN_BOOL_TRUE = "true"`, una palabra clave registrada llamada `"true"` o `"TRUE"` **nunca** sobrescribirá la clasificación del booleano.
2. **Nulo sobre Keywords:** Si `TOKEN_NULL = "null"`, la palabra `"null"` o `"NULL"` siempre emitirá `Token.NULL`.
3. **Búsqueda Exacta de Palabras Clave:** Las keywords registradas vía `words.add_keyword("if")` exigen coincidencia exacta de mayúsculas/minúsculas. `"if"` emite `Token.KEYWORD`, mientras que `"If"` o `"IF"` emitirá `Token.IDENT`.

```python
from gram import config
from gram.core.lexer import Lexer, Token, words

words.clear_all()
words.add_keyword("let")
words.add_keyword("null")  # Quedará ensombrecida por TOKEN_NULL

tokens = Lexer("let x = true; let y = null; let z = True;").process()
print([(t.token, t.value) for t in tokens])
# [(Token.KEYWORD, 'let'), (Token.IDENT, 'x'), (Token.ASSIGN, '='), (Token.BOOL, True), (Token.SEMICOLON, ';'),
#  (Token.KEYWORD, 'let'), (Token.IDENT, 'y'), (Token.ASSIGN, '='), (Token.NULL, None), (Token.SEMICOLON, ';'),
#  (Token.KEYWORD, 'let'), (Token.IDENT, 'z'), (Token.ASSIGN, '='), (Token.BOOL, True), (Token.SEMICOLON, ';'),
#  (Token.EOF, None)]
```

---

## 5. Operadores y Símbolos (`visitors.symbols`)

Cuando un carácter no coincide con palabras alfanuméricas, comillas o comentarios, el control se delega a `visitors.symbols.process()`:

1. Itera sobre `lexer.sorted_symbols()` (ordenados descendentemente por longitud).
2. Compara el fragmento de la línea: `if line[start:start+len(symbol)] == symbol:`.
3. Comprobación especial para `...`: si `config.SUPPORT_TRIPLE_DOT=False`, se omite `...`, permitiendo que cada punto se reconozca individualmente como `Token.DOT`.
4. Si un símbolo coincide, avanza `lexer.col` en `len(symbol)` y emite `TokenType(symbol_map[symbol], symbol, line, start)`.
5. Si ningún símbolo registrado coincide, avanza 1 carácter, registra un error en `Diagnostics`, reporta `LexerError` (`LEXER_UNEXPECTED_CHARACTER`) y emite `Token.ERROR`.
