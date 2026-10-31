# Sesiones de Lenguaje (`gram.sessions.Session`)

`Session` es dueña del catálogo léxico efectivo y de la configuración que
pertenece a un frontend. Su lexer conserva una vista de la sesión, por lo que
varios lenguajes pueden coexistir sin compartir palabras clave, grupos ni
flags del lexer.

La propagación de sesión al parser y al AST ya está activa: `Session.parse()`
reutiliza `session.parser`, transmite la sesión a `ASTAnalyzer` y resuelve las
flags de diagnóstico de parser/AST desde la sesión. Los combinadores que
consultan catálogos, como `MatchGroup`, resuelven sus grupos desde esa misma
sesión; las definiciones gramaticales estáticas siguen siendo compartidas.

## Constructor

```python
from gram.sessions import Session

session = Session("Frontend C", "Many", entrypoint=CProgram)
```

`mode` debe ser `"Many"` o `"Some"`; cualquier otro valor lanza
`ValueError`.

Cada sesión expone `session.lexer`, `session.parser`, `session.keywords`,
`session.groups`, `session.symbols` y un `session.config` filtrado. La configuración contiene
opciones de lexer, parser, AST, generación de errores y generación de
información/logs. Las opciones de plugins y del entorno siguen siendo
globales.

## Ciclo de configuración del lexer

```python
session = Session("Script", "Many")
session.init()

session.add_group("types")
session.add_keyword("int", group="types")
config.LEXER_COMMENT_TOKEN = ";"

# Forma de compatibilidad durante la ventana init/migrate:
# lexer.words.add_keyword("fn")

session.migrate()
tokens = session.tokenize("int value; ; comment", "sample.dsl")
```

`init()` guarda el estado del proceso y dirige las llamadas sueltas
`words.add_group()` / `words.add_keyword()` hacia esa sesión. Use
`clear_global()` explícitamente si debe vaciar un catálogo existente.
`migrate()` guarda la sesión y restaura el estado que estaba activo antes de
`init()`. El lexer de la sesión no necesita `load()` para tokenizar.

`load()` está disponible cuando consumidores legacy del parser/combinadores
necesitan que el catálogo y la configuración de la sesión aparezcan en los
registros globales de compatibilidad. Requiere haber llamado a `migrate()` y
reconstruye los índices derivados de símbolos.

`clear_global()` ahora limpia los diccionarios de palabras y grupos de la
sesión; no borra el catálogo de otra sesión.

## Frontends aislados

```python
from gram import config

c = Session("C", "Many")
c.init()
c.add_keyword("int")
config.LEXER_COMMENT_TOKEN = "//"
c.migrate()

script = Session("Script", "Many")
script.init()
script.add_keyword("fn")
config.LEXER_COMMENT_TOKEN = ";"
script.migrate()

c_tokens = c.tokenize("int value; // comment", "sample.c")
script_tokens = script.tokenize("fn main(); comment", "sample.dsl")
```

`int` es palabra clave solo en `c`; `fn` solo en `script`. Llamar a `load()`
en cualquiera de las sesiones también hace que su catálogo y símbolos sean
visibles para lectores legacy de `gram.core.lexer.words` hasta cargar otro
catálogo. Los registros posteriores mediante `session.add_group()` o
`session.add_keyword()` mantienen esas vistas legacy sincronizadas.

## Notas de compatibilidad

- Las funciones sueltas `words.add_group()` y `words.add_keyword()` siguen
  disponibles durante la transición y son las únicas entradas legacy de
  registro.
- `WordGroupManager` sigue siendo importable para imports antiguos, pero
  instanciarlo lanza `RuntimeError`; use `Session.add_group()` o
  `words.add_group()`.
- `Keyword` y `WordGroup` son objetos de valor. El registro lo realizan las
  funciones `add`, no su construcción directa.
- `MULTLINE` sigue siendo un registro global y no forma parte de las
  instantáneas de una sesión.

## Compartir conversiones

El uso compartido de conversiones sigue siendo explícito y compatible con el
parser:

```python
state = c.new_conversion_state()
c.parse(header_tokens, "header.h", conversion_state=state)
c.parse(source_tokens, "main.c", conversion_state=state)
```
