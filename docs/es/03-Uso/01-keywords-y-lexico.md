# Keywords y Configuración Léxica

Antes de tokenizar código fuente con el `Lexer`, puedes configurar la forma en que Gram reconoce comentarios, literales multilínea, líneas en blanco, palabras clave del lenguaje (`Keyword`), grupos semánticos de palabras clave (`WordGroup`) y símbolos u operadores multicarácter personalizados.

Todas las operaciones de palabras clave y grupos residen en `gram.core.lexer.words` (accesible mediante `from gram import lexer; lexer.words`).

---

## 1. Configurar el Comportamiento del Lexer (`gram.config`)

El `Lexer` independiente consulta flags de `gram.config`; el lexer de una
sesión consulta esas mismas opciones desde la vista `Session.config`.

| Configuración | Valor por Defecto | Efecto sobre el `Lexer` |
| :--- | :--- | :--- |
| `config.LEXER_COMMENT_TOKEN` | `'#'` | Prefijo de comentario de una sola línea (ej.: `'//'`, `'#'`, `';'`). Cualquier texto desde este prefijo hasta el final de la línea se descarta fuera de literales de cadena. |
| `config.LEXER_BLOCK_COMMENT_TOKEN` | `None` | Delimitador de apertura de comentarios de bloque. Con `LEXER_SUPPORT_BLOCK_COMMENTS=True`, se cierra con `*/`. |
| `config.LEXER_SUPPORT_BLOCK_COMMENTS` | `True` | Activa o desactiva los comentarios de bloque configurados mediante `LEXER_BLOCK_COMMENT_TOKEN`. |
| `config.LEXER_SUPPORT_DOCSTRINGS` | `True` | Habilita los delimitadores multilínea predeterminados (`"""..."""` y `'''...'''`). Se emiten como `Token.STRING`. |
| `config.LEXER_SUPPORT_PREFIXED_STRINGS` | `True` | Reconoce prefijos C como `L"texto"`, `u"texto"`, `U"texto"` y `u8"texto"`. |
| `config.LEXER_SUPPORT_LEADING_DOT_NUMBERS` | `True` | Reconoce números que empiezan por punto, como `.5`. Si es `False`, se emiten `Token.DOT` y `Token.NUMBER`. |
| `config.LEXER_TAB_WIDTH` | `4` | Ancho visual usado para tabs cuando `LEXER_INDENT_STYLE` es `tabs` o `mixed`. Los valores menores que `1` se normalizan a `1`. |
| `config.LEXER_INDENT_STYLE` | `'spaces'` | Política de indentación: `spaces` conserva el ancho histórico basado solo en espacios, `tabs` cuenta tabs con `LEXER_TAB_WIDTH` y `mixed` expande ambos. |
| `config.TOKEN_BOOL_TRUE` / `config.TOKEN_BOOL_FALSE` | `'true'` / `'false'` | Define las grafías que se convierten en `Token.BOOL`. |
| `config.TOKEN_NULL` | `'null'` | Define la grafía que se convierte en `Token.NULL`. |
| `config.SUPPORT_INDENT` | `True` | Si es `False`, no se generan `Token.INDENT` ni `Token.DEDENT`. |
| `config.SUPPORT_TRIPLE_DOT` | `True` | Controla si `...` se reconoce como `Token.THREE_DOTS` o como tres tokens `Token.DOT`. |
| `config.LEXER_IGNORE_EMPTY_LINES` | `True` | Si es `True`, las líneas en blanco o con solo comentarios se omiten sin emitir tokens redundantes `Token.NEWLINE` ni perturbar el cálculo de `INDENT`/`DEDENT`. |
| `config.LEXER_ADD_INFO` | `True` | Si es `True`, emite telemetría léxica y crea nodos de proceso/visitante. Si es `False`, omite esos nodos y notas. |
| `config.LEXER_ADD_ERROR` | `True` | Si es `True`, registra notas de fallo léxico en la pila de diagnóstico del lexer. |

La clasificación de palabras es determinista. El lexer comprueba primero las
grafías booleanas configuradas (sin distinguir mayúsculas), después la grafía
de `null` (también sin distinguir mayúsculas), luego una palabra clave
registrada con coincidencia exacta y finalmente emite `Token.IDENT`. Por eso
una palabra clave `TRUE` no sustituye la grafía booleana configurada `true`.

`WordGroup.contains()` usa nombres exactos y distingue mayúsculas. Además,
`WordGroup.clear()` reinicia `keyword.group` para cada miembro, evitando
referencias obsoletas después de vaciar un grupo.

Para diagnósticos de tokens, `TokenType.formatter()` expande `$line`, `$col`,
`$len` y `$long` usando el token emitido. `$len` es la longitud del contenido
del token y `$long` es su columna final (`col + len`).

### Delimitadores multilínea

Las cadenas multilínea y los comentarios de bloque usan el mismo registro de
delimitadores. Se puede añadir una variante para el proceso actual y retirarla
cuando ya no sea necesaria:

```python
from gram.core.lexer import Lexer, add_multline, list_multline, remove_multline, words

# Lexer requiere al menos una palabra clave registrada.
words.add_keyword("placeholder", allow_override=True)
add_multline("<<<", ">>>")
print(list_multline())
# {'"""': '"""', "'''": "'''", '<<<': '>>>'}

tokens = Lexer("<<<contenido\nmultilínea>>>").process()
remove_multline("<<<")
```

Todos los delimitadores no asociados a comentarios se emiten como
`Token.STRING`. Para comentarios de bloque C se puede mantener la configuración
compatible `LEXER_BLOCK_COMMENT_TOKEN = "/*"`; internamente se procesa con el
mismo escáner multilínea. `add_multline()` modifica el registro global para
nuevas instancias; cada `Lexer` copia el registro al construirse, por lo que un
lexer ya creado no cambia si después se registra o elimina un delimitador.

| API | Descripción |
| :--- | :--- |
| `MULTLINE` | Diccionario global `apertura -> cierre` con los delimitadores registrados. |
| `add_multline(opening, closing)` | Añade o reemplaza un par de delimitadores. |
| `remove_multline(opening)` | Elimina una apertura y devuelve su cierre, o `None` si no existía. |
| `list_multline()` | Devuelve una copia independiente del registro actual. |

### Flags de cadenas

Todas las cadenas entre comillas se emiten como `Token.STRING`. El atributo
`TokenType.flags` usa `gram.core.lexer.flags`:

```python
from gram.core.lexer import flags

token.flags & flags.SIMPLE_QUOTE  # cualquier cadena simple
token.flags & flags.CHAR          # cadena cuyo valor tiene un carácter
```

Por ejemplo, `'x'` tiene `flags.CHAR | flags.SIMPLE_QUOTE`, mientras que
`"texto"` solo tiene `flags.SIMPLE_QUOTE`. Ya no existe un `Token.CHAR`
separado.

| Flag | Significado |
| :--- | :--- |
| `flags.NONE` | El token no tiene flags léxicas especiales. |
| `flags.SIMPLE_QUOTE` | El valor procede de una cadena entre comillas simples o dobles de una línea. |
| `flags.CHAR` | El valor de la cadena tiene exactamente un carácter. |

---

## 2. Registrar Palabras Clave (`words.add_keyword`)

Por defecto, cualquier palabra alfanumérica o con guion bajo (`[a-zA-Z_][a-zA-Z0-9_]*`) escaneada por el lexer se emite como `Token.IDENT`—salvo `'true'` y `'false'`, que solo se tratan como `Token.BOOL` si **no** han sido registradas como palabras clave en `words.MAP_KEYWORDS`.

Cuando se registra una palabra mediante `lexer.words.add_keyword()`, el lexer la emite con `token == Token.KEYWORD`, permitiendo que sea reconocida por `MatchKeyword` o `MatchGroup`.

### Firma

```python
lexer.words.add_keyword(
    name: str,
    hex_color: str = "#FFFFFF",
    group: str | WordGroup | None = None,
    description: str = "",
    documentation: str = "",
    *,
    color: str | None = None,
    allow_override: bool = False,
) -> Keyword
```

- **`name`**: Cadena exacta del lexema (sin espacios al inicio ni al final). Nombres vacíos lanzan `LexerError` (`LEXER_KEYWORD_INVALID_NAME`).
- **`hex_color` / `color`**: Cadena de color hexadecimal (ej.: `'#FF79C6'`) utilizada como fallback por `ASTColorResolver` y `VSIXAnalyzer`.
- **`group`**: Nombre de grupo opcional (`str`) o instancia de `WordGroup`. Si el grupo ya existe, la palabra clave se añade automáticamente a él.
- **`description` / `documentation`**: Cadenas de metadatos extraídas por `VSIXAnalyzer` para detalles de autocompletado LSP y tooltips emergentes.
- **`allow_override`**: Si es `False` (por defecto), registrar una palabra clave duplicada lanza `LexerError` (`LEXER_KEYWORD_ALREADY_EXISTS`). Establece `allow_override=True` para reemplazar limpiamente un registro existente.

---

## 3. Grupos Semánticos de Palabras Clave (`words.add_group` y `WordGroup`)

Un `WordGroup` agrupa palabras clave relacionadas bajo un identificador semántico compartido (como `'types'`, `'control'` o `'modifiers'`) de modo que las reglas gramaticales puedan coincidir con cualquier miembro en tiempo $O(1)$ usando `MatchGroup('types')`.

### Crear Grupos y Añadir Palabras Clave

> [!IMPORTANT]
> Cada palabra clave añadida a un `WordGroup` **debe** estar registrada previamente en `MAP_KEYWORDS` (o pasarse como una instancia de `Keyword`). Intentar añadir una cadena no registrada a un `WordGroup` lanza `LexerError` (`LEXER_WORDGROUP_KEYWORD_NOT_REGISTERED`).
> Además, un `Keyword` mantiene un único atributo `kw.group`: si `kw.group` ya está asignado a otro nombre de grupo, `other_group.add_keyword(kw)` no realiza ninguna operación y retorna `None`.

```python
from gram import config, lexer

# Reiniciar palabras clave y grupos globales anteriores
lexer.words.clear_all()

# Configurar comentarios de una línea al estilo C
config.LEXER_COMMENT_TOKEN = "//"

# 1. Crear primero los grupos de palabras semánticos
types_group = lexer.words.add_group(
    "types",
    color_group="#3B82F6",
    description="Primitive scalar types",
    allow_override=True,
)
signed_group = lexer.words.add_group(
    "signed_",
    color_group="#60A5FA",
    description="Sign modifiers",
    allow_override=True,
)

# 2. Registrar palabras clave y vincularlas a sus grupos
for kw_name in ("void", "char", "short", "int", "long", "float", "double"):
    lexer.words.add_keyword(
        kw_name,
        hex_color="#3B82F6",
        group="types",
        description=f"Primitive type '{kw_name}'",
        allow_override=True,
    )

for kw_name in ("signed", "unsigned"):
    lexer.words.add_keyword(
        kw_name,
        hex_color="#60A5FA",
        group="signed_",
        allow_override=True,
    )

# Palabra clave de control independiente sin grupo
lexer.words.add_keyword("return", hex_color="#FF79C6", allow_override=True)

print("Total de keywords:", lexer.words.count_keywords())
print("Miembros del grupo types:", types_group.values)
print("¿Está 'int' en 'types'?", lexer.words.exists_in_group("int", "types"))
```

### Funciones Auxiliares de Inspección y Limpieza del Catálogo

| Función | Tipo de Retorno | Descripción |
| :--- | :--- | :--- |
| `words.get_keyword(name, *, strict=False)` | `Keyword \| None` | Retorna la instancia de `Keyword` o `None` (lanza `LEXER_KEYWORD_NOT_FOUND` si `strict=True`). |
| `words.keyword_exists(name)` | `bool` | Retorna `True` si `name` está registrado en `MAP_KEYWORDS`. |
| `words.remove_keyword(name, *, strict=False)` | `Keyword \| None` | Elimina `name` de `MAP_KEYWORDS` y de todas las instancias de `WordGroup`. |
| `words.all_keywords()` / `words.all_keyword_names()` | `list[Keyword]` / `list[str]` | Lista todos los objetos `Keyword` o nombres en cadena registrados. |
| `words.get_group(name, *, strict=False)` | `WordGroup \| None` | Retorna la instancia de `WordGroup` o `None` (lanza `LEXER_WORDGROUP_NOT_FOUND` si `strict=True`). |
| `words.group_exists(name)` | `bool` | Retorna `True` si el grupo está registrado. |
| `words.exists_in_group(kw, group)` | `bool` | Verificación de pertenencia en $O(1)$ dentro de `group`. |
| `words.remove_group(name)` | `WordGroup \| None` | Elimina el grupo y reinicia `kw.group = None` en sus miembros. `WordGroup.clear()` hace la misma limpieza sin eliminar el grupo. |
| `words.clear_all()` | `None` | Limpia tanto `MAP_KEYWORDS` como todas las entradas de `WordGroup`. |

---

## 4. Personalizar Símbolos de Operadores (`insert_symbol` y `disabled_symbol`)

El lexer de Gram incluye una tabla bidireccional integrada (`lexer.tokens.MAP_SYMBOLS`) de operadores y delimitadores de 1, 2 y 3 caracteres (`+`, `->`, `:=`, `...`, `==`, `&&`, etc.) evaluados mediante coincidencia voraz del más largo (*maximal-munch* con `get_sorted_symbols()`).

Puedes agregar un nuevo lexema de símbolo mapeado a un miembro existente del enum `Token` con `lexer.tokens.insert_symbol(symbol, token)`, o desactivar un lexema de símbolo existente con `lexer.tokens.disabled_symbol(symbol)` (lo cual reconstruye automáticamente la búsqueda inversa y la lista ordenada de símbolos):

```python
from gram import lexer

# Mapear "<>" como alias para Token.NOT_EQUAL:
lexer.tokens.insert_symbol("<>", lexer.Token.NOT_EQUAL)

tokens = lexer.Lexer("a <> b").process()
print(tokens)
# [TokenType(token=Token.IDENT, value='a', line=1, col=0),
#  TokenType(token=Token.NOT_EQUAL, value='<>', line=1, col=2),
#  TokenType(token=Token.IDENT, value='b', line=1, col=5),
#  TokenType(token=Token.EOF, value=None, line=1, col=6)]

# Eliminar el símbolo personalizado de MAP_SYMBOLS al finalizar:
lexer.tokens.disabled_symbol("<>")
```
