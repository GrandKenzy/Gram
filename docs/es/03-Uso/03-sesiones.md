# Sesiones de Lenguaje (`gram.sessions.Session`)

En **Gram**, los catálogos léxicos (`lexer.words.MAP_KEYWORDS`, `lexer.words.groups`, `lexer.tokens.MAP_SYMBOLS`) y las opciones de tiempo de ejecución (`gram.config`) son registros globales.

Cuando un compilador o herramienta necesita parsear múltiples lenguajes o formatos de archivo dentro del mismo proceso de Python—por ejemplo, un flujo de trabajo que procesa un DSL de configuración (comentarios con `;`, docstrings activados), archivos `.c` (comentarios con `//`, palabras clave de C) y contratos de cabecera `.h`—**`gram.sessions.Session`** aisla el estado de cada lenguaje y permite alternar entre ellos in-situ.

---

## 1. Cómo Funciona `Session`

`Session` (`gram.sessions.Session`) captura y restaura cuatro registros globales:
1. **`words.MAP_KEYWORDS`**: Todas las instancias de `Keyword` registradas.
2. **`words.groups._groups`**: Todas las instancias de `WordGroup` registradas.
3. **`tokens.MAP_SYMBOLS`**: El diccionario de búsqueda de símbolos a `Token`.
4. **`gram.config`**: Todas las flags de configuración en mayúsculas (`config.save()` / `config.load()`).

Las instantáneas (snapshots) se almacenan dentro de la instancia de `Session` como tuplas compactas, y `session.load()` muta los diccionarios globales in-situ para que las referencias existentes de los módulos sigan siendo válidas.

### Firma del Constructor

```python
from gram import sessions

session = sessions.Session(
    name: str,
    mode: Literal["Many", "Some"],
    entrypoint: type[RuleItem] | None = None,
)
```

- **`name`**: Identificador descriptivo para la sesión (ej.: `"Session From C"`).
- **`mode`**: Modo del parser de nivel superior (`"Many"` para $0..n$ sentencias o `"Some"` para $1..n$ sentencias). Pasar cualquier otro valor lanza `ValueError`.
- **`entrypoint`**: Clase `RuleItem` raíz por defecto opcional usada por `session.parse()` cuando no se pasa `entrypoint` en la llamada.

---

## 2. Ciclo de Vida de una Sesión

Definir una sesión de lenguaje sigue un patrón estricto de inicialización en 4 pasos, seguido de `load()` / `tokenize()` / `parse()` en tiempo de ejecución:

| Método | Fase | Acción |
| :--- | :--- | :--- |
| `session.clear_global()` | Configuración (Paso 1) | Llama a `words.clear_all()`, limpiando `MAP_KEYWORDS` y `words.groups` para que las palabras clave de lenguajes anteriores no se filtren en esta sesión. |
| `session.init()` | Configuración (Paso 2) | Guarda una instantánea de `gram.config` y `tokens.MAP_SYMBOLS` globales que estaban activos antes de configurar esta sesión. |
| *(Configurar lenguaje)* | Configuración (Paso 3) | Establece flags de `gram.config`, registra `words.add_group()` / `words.add_keyword()`, registra símbolos personalizados y define/importa clases `RuleItem`. |
| `session.migrate()` | Configuración (Paso 4) | Guarda en `self` los `MAP_KEYWORDS`, `WordGroup`s, `config` y `MAP_SYMBOLS` de la sesión, y restaura la instantánea previa de `config` y `MAP_SYMBOLS` capturada por `init()`. |
| `session.load()` | Ejecución | Aplica las palabras clave, grupos, símbolos y `config` guardados de esta sesión a los registros globales. (Debe haberse llamado a `migrate()` previamente, o lanzará `RuntimeError`.) |
| `session.tokenize(source, name)` | Ejecución | Ejecuta `Lexer(source, name).process()` bajo el estado de la sesión activa y retorna `list[TokenType]`. |
| `session.parse(tokens, name, entrypoint=None, conversion_state=None)` | Ejecución | Ejecuta el parser usando `entrypoint` o `self.entrypoint`; el estado opcional permite compartir conversiones explícitamente entre archivos. |

---

## 3. Ejemplo de Frontend Multilenguaje

El siguiente ejemplo completo y ejecutable demuestra dos sesiones de lenguaje aisladas—un frontend estilo C (comentarios `//`, palabra clave `int`) y un frontend para un DSL de scripting (comentarios `;`, palabra clave `fn`)—coexistiendo en el mismo proceso:

```python
from gram import combinators as cmb
from gram import config, lexer, sessions

# ==============================================================================
# 1. DEFINIR SESIÓN A: Frontend estilo C (comentarios "//")
# ==============================================================================
C_SESSION = sessions.Session("C Frontend", "Many")
C_SESSION.clear_global()
C_SESSION.init()

config.LEXER_COMMENT_TOKEN = "//"
config.LEXER_SUPPORT_DOCSTRINGS = False
config.LEXER_IGNORE_EMPTY_LINES = True

lexer.words.add_group("types", color_group="#3B82F6", allow_override=True)
lexer.words.add_keyword("int", group="types", allow_override=True)

class CVarDecl(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.MatchGroup("types"),
        cmb.MatchToken(lexer.Token.IDENT),
        cmb.MatchToken(lexer.Token.SEMICOLON),
    )

class CProgram(cmb.RuleItem):
    entrypoint = cmb.Alt(cmb.Ref(CVarDecl))

C_SESSION.entrypoint = CProgram
C_SESSION.migrate()


# ==============================================================================
# 2. DEFINIR SESIÓN B: Frontend de Script DSL (comentarios ";")
# ==============================================================================
SCRIPT_SESSION = sessions.Session("Script Frontend", "Many")
SCRIPT_SESSION.clear_global()
SCRIPT_SESSION.init()

config.LEXER_COMMENT_TOKEN = ";"
config.LEXER_SUPPORT_DOCSTRINGS = True
config.LEXER_IGNORE_EMPTY_LINES = True

lexer.words.add_keyword("fn", hex_color="#FF79C6", allow_override=True)

class ScriptFuncDecl(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.MatchKeyword("fn"),
        cmb.MatchToken(lexer.Token.IDENT),
        cmb.Enclosed(
            open=lexer.Token.LPAREN,
            close=lexer.Token.RPAREN,
            content=cmb.MatchToken(lexer.Token.IDENT),
            allow_empty=True,
        ),
    )

class ScriptProgram(cmb.RuleItem):
    entrypoint = cmb.Alt(cmb.Ref(ScriptFuncDecl))

SCRIPT_SESSION.entrypoint = ScriptProgram
SCRIPT_SESSION.migrate()


# ==============================================================================
# 3. CAMBIAR SESIONES EN TIEMPO DE EJECUCIÓN
# ==============================================================================

# Parsear código C usando C_SESSION
C_SESSION.load()
c_tokens = C_SESSION.tokenize("int counter; // C comment", "sample.c")
c_ast = C_SESSION.parse(c_tokens, "sample.c")
print("C AST:", c_ast)

# Cambiar a SCRIPT_SESSION y parsear código del Script DSL
SCRIPT_SESSION.load()
script_tokens = SCRIPT_SESSION.tokenize("fn main() ; Script comment", "sample.dsl")
script_ast = SCRIPT_SESSION.parse(script_tokens, "sample.dsl")
print("Script AST:", script_ast)
```

Salida:

```text
C AST: [AstRef(nodes=3, name=CVarDecl)]
Script AST: [AstRef(nodes=2, name=ScriptFuncDecl)]
```

Observa cómo en `C_SESSION`, `;` se tokeniza como `Token.SEMICOLON` mientras que `// C comment` se descarta como comentario; tan pronto como se llama a `SCRIPT_SESSION.load()`, `; Script comment` pasa a ser el delimitador de comentarios y `fn` se reconoce como `Token.KEYWORD`.

### Compartir conversiones entre archivos

Cada llamada a `session.parse()` comienza con conversiones aisladas si no se proporciona un estado. Para conservar adiciones de un archivo y usarlas en otro, cree un estado explícito:

```python
state = C_SESSION.new_conversion_state()
C_SESSION.parse(header_tokens, "header.h", conversion_state=state)
C_SESSION.parse(source_tokens, "main.c", conversion_state=state)
```

El estado puede copiarse con `state.clone()` o limpiarse con `state.clear()`. El estado externo solo se actualiza cuando el parseo termina correctamente.

### Registro de delimitadores multilínea

El registro `MULTLINE` (`add_multline()` / `remove_multline()`) es global y no
forma parte de las instantáneas de `Session`. Registre los delimitadores antes
de crear el `Lexer` de un archivo y elimínelos o restáurelos explícitamente si
otro lenguaje no debe verlos. Cada `Lexer` copia el registro al construirse.
