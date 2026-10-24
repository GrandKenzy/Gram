# Keywords y Configuración Léxica

Antes de tokenizar código fuente con el `Lexer`, puedes configurar la forma en que Gram reconoce comentarios, cadenas multilínea (docstrings), líneas en blanco, palabras clave del lenguaje (`Keyword`), grupos semánticos de palabras clave (`WordGroup`) y símbolos u operadores multicarácter personalizados.

Todas las operaciones de palabras clave y grupos residen en `gram.core.lexer.words` (accesible mediante `from gram import lexer; lexer.words`).

---

## 1. Configurar el Comportamiento del Lexer (`gram.config`)

El `Lexer` consulta varias variables globales de configuración en `gram.config`:

| Configuración | Valor por Defecto | Efecto sobre el `Lexer` |
| :--- | :--- | :--- |
| `config.LEXER_COMMENT_TOKEN` | `';'` | Prefijo de comentario de una sola línea (ej.: `'//'`, `'#'`, `';'`). Cualquier texto desde este prefijo hasta el final de la línea se descarta fuera de literales de cadena. |
| `config.LEXER_SUPPORT_DOCSTRINGS` | `True` | Si es `True`, las cadenas entre comillas triples (`"""..."""` o `'''...'''`) emiten `Token.DOCSTRING` (que `ASTState.delegate_return_node` convierte en `LiteralString`). |
| `config.LEXER_IGNORE_EMPTY_LINES` | `True` | Si es `True`, las líneas en blanco o con solo comentarios se omiten sin emitir tokens redundantes `Token.NEWLINE` ni perturbar el cálculo de `INDENT`/`DEDENT`. |
| `config.LEXER_ADD_INFO` | `False` | Si es `True`, emite notas de telemetría léxica a `LexerState`. |
| `config.LEXER_ADD_ERROR` | `False` | Si es `True`, registra notas de fallo léxico en la pila de diagnóstico del lexer. |

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
| `words.remove_group(name)` | `WordGroup \| None` | Elimina el grupo y reinicia `kw.group = None` en sus miembros. |
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
