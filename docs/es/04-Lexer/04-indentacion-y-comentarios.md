# Indentación, Comentarios y Delimitadores

Gram incorpora un sistema flexible y no invasivo para realizar el seguimiento de bloques por indentación y procesar comentarios sin contaminar el flujo léxico principal.

---

## 1. Motor de Indentación Semántica

Gram soporta nativamente la sintaxis basada en indentación semántica (lenguajes con regla *off-side* como Python, YAML o Nim) a través de `LexerState.process_indent()`.

### La Pila de Indentación (`self.indents`)

El lexer mantiene una pila interna de enteros inicializada en `[0]`:
- **Apilar (`Token.INDENT`):** Cuando el ancho visual inicial de la línea actual supera a `self.indents[-1]`, el nuevo nivel se apila y se emite un token `Token.INDENT`.
- **Desapilar (`Token.DEDENT`):** Cuando el ancho visual disminuye, el lexer desapila niveles hasta coincidir con un bloque exterior previo, emitiendo un token `Token.DEDENT` por cada nivel desanidado.
- **Error de Discordancia:** Si la indentación reducida no coincide con ningún nivel previo de la pila, el lexer reporta `LEXER_INDENTATION_MISMATCH`.
- **Desenrollado en EOF:** Al llegar al final del archivo fuente, cualquier nivel de indentación que permanezca abierto (`len(self.indents) > 1`) se desapila automáticamente, emitiendo tokens `Token.DEDENT` finales antes de `Token.EOF`.

```python
from gram import config
from gram.core.lexer import Lexer, Token, words

words.clear_all()
words.add_keyword("def")
words.add_keyword("pass")

codigo = """def exterior():
    pass
pass"""

tokens = Lexer(codigo).process()
print([t.token for t in tokens])
# [Token.KEYWORD, Token.IDENT, Token.LPAREN, Token.RPAREN, Token.COLON,
#  Token.INDENT, Token.KEYWORD,
#  Token.DEDENT, Token.KEYWORD, Token.EOF]
```

### Políticas de Indentación (`LEXER_INDENT_STYLE` y `LEXER_TAB_WIDTH`)

El cálculo del ancho visual de la indentación lo realiza `LexerState.indentation_width(prefix)`:

| Estilo (`LEXER_INDENT_STYLE`) | Fórmula de Ancho | Descripción |
| :--- | :--- | :--- |
| `"spaces"` *(predeterminado)* | `prefix.count(" ")` | Comportamiento estándar. Sólo los espacios ASCII cuentan para el ancho; los tabuladores se cuentan como 0. |
| `"tabs"` | `prefix.count("\t") * tab_width` | Sólo los tabuladores cuentan para el ancho; los espacios se ignoran. |
| `"mixed"` | Avanza al siguiente tab stop | Expansión visual de columnas: cada espacio suma 1 y cada tabulador avanza al siguiente múltiplo de `LEXER_TAB_WIDTH` (`width += tab_width - (width % tab_width)`). |

```python
from gram import config
from gram.core.lexer import Lexer, words
words.add_keyword("dummy", allow_override=True)

# Configurar expansión mixta de espacios y tabuladores a 8 columnas:
config.LEXER_INDENT_STYLE = "mixed"
config.LEXER_TAB_WIDTH = 8
```

### Desactivar el Seguimiento de Indentación (`SUPPORT_INDENT`)

Para lenguajes con delimitadores explícitos por llaves o de formato libre (C, Java, Rust, JavaScript), desactiva el seguimiento de indentación globalmente o por sesión:

```python
config.SUPPORT_INDENT = False
```

Cuando `SUPPORT_INDENT=False`, `process_indent()` avanza sobre los espacios iniciales sin modificar la pila `self.indents` y no emite ningún token `Token.INDENT` ni `Token.DEDENT`.

---

## 2. Comentarios de una Línea

Los comentarios unilínea descartan el texto del código fuente desde un prefijo configurado hasta el final de la línea física fuera de cadenas literales.

### Configuración (`LEXER_COMMENT_TOKEN`)

El marcador de comentario se define en `config.LEXER_COMMENT_TOKEN` (por defecto `'#'`). Acepta tres formatos de valor:

1. **Cadena simple o múltiple:** Prefijos de uno o varios caracteres (ej. `'#'`, `'//'`, `'--'`, `';'`, `'<->'`).
2. **Miembro `Token`:** Símbolo mapeado (ej. `Token.FLOOR_DIV` para `'//'`).
3. **Tupla / Lista de marcadores:** Múltiples prefijos válidos en simultáneo (ej. `(Token.FLOOR_DIV, '#', ';')`).

```python
from gram import config
from gram.core.lexer import Lexer, Token, words
words.add_keyword("dummy", allow_override=True)

# 1. Comentarios estilo C++:
config.LEXER_COMMENT_TOKEN = "//"

# 2. Comentarios estilo SQL / Lua:
config.LEXER_COMMENT_TOKEN = "--"

# 3. Múltiples prefijos simultáneos:
config.LEXER_COMMENT_TOKEN = ("//", "#", ";")
```

### Preservación de Comentarios (`LEXER_SAVE_COMMENTS`)

Por defecto, `config.LEXER_SAVE_COMMENTS = True`. Los comentarios escaneados se capturan en la lista `lexer.comments` como instancias de `TokenType(Token.COMMENT, content, line, col)`:

```python
config.LEXER_COMMENT_TOKEN = "//"
lexer = Lexer("int x = 10; // inicializar variable\nint y = 20;")
tokens = lexer.process()

# El flujo principal de tokens NO contiene Token.COMMENT:
print([t.token for t in tokens])
# [Token.KEYWORD, Token.IDENT, Token.ASSIGN, Token.NUMBER, Token.SEMICOLON, ...]

# Los comentarios preservados son accesibles vía lexer.comments:
print(lexer.comments)
# [TokenType(token=Token.COMMENT, value=' inicializar variable', line=1, col=12)]
```

> [!TIP]
> Conservar los comentarios en `lexer.comments` en lugar de emitirlos en el flujo de tokens evita que las reglas sintácticas (`Seq`, `Alt`, `RuleItem`) tengan que contemplar comentarios intermedios entre cada token de la gramática.

---

## 3. Comentarios de Bloque (Estilo C)

Gram soporta comentarios multilínea de bloque (`/* ... */`):

```python
from gram import config
from gram.core.lexer import Lexer, words
words.add_keyword("dummy", allow_override=True)

config.LEXER_BLOCK_COMMENT_TOKEN = "/*"
config.LEXER_SUPPORT_BLOCK_COMMENTS = True

codigo = """
x = 1; /* comentario de bloque en línea */ y = 2;
/* comentario
   de bloque multilínea */
z = 3;
"""

lexer = Lexer(codigo)
tokens = lexer.process()

print([t.value for t in tokens if t.value is not None])
# ['x', '=', 1, ';', 'y', '=', 2, ';', 'z', '=', 3, ';']

print(len(lexer.comments))
# 2 comentarios de bloque capturados
```

### Invariantes para Comentarios de Bloque:
1. Los comentarios de bloque siempre cierran con `"*/"`.
2. Los comentarios de bloque en la misma línea que el código conservan todos los tokens que les siguen.
3. Pueden abarcar múltiples líneas físicas sin disparar tokens espurios `Token.NEWLINE` ni alterar la indentación.
4. Establecer `LEXER_SUPPORT_BLOCK_COMMENTS = False` desactiva los comentarios de bloque, provocando que `"/*"` se tokenice como `Token.SLASH` seguido de `Token.STAR`.

---

## 4. Líneas Vacías y Líneas de Sólo Comentarios

Gram maneja limpiamente las líneas vacías y los comentarios aislados:

- **`config.LEXER_IGNORE_EMPTY_LINES` (`bool`, por defecto `True`):** Cuando es `True`, las líneas completamente en blanco no emiten tokens redundantes `Token.NEWLINE` ni provocan cambios en la pila de indentación.
- **`config.LEXER_IGNORE_NEWLINES` (`bool`, por defecto `True`):** Cuando es `True`, se omiten los saltos de línea `Token.NEWLINE`. Establécelo en `False` si en tu DSL los saltos de línea actúan como terminadores de sentencias (como en Python o Go).
- **Líneas Puras de Comentarios:** Una línea que sólo contiene espacios y un comentario se procesa antes de evaluar la indentación. Nunca agrega ni retira niveles de la pila, garantizando que un comentario dentro de un bloque indentado no provoque errores de discordancia (*indentation mismatch*).
