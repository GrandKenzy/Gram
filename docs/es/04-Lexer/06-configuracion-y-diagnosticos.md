# Configuración y Diagnósticos

Gram proporciona un sistema unificado y robusto de telemetría y configuración que gobierna todo el subsistema de análisis léxico.

---

## 1. Opciones Exhaustivas de Configuración

Todas las banderas del lexer residen en `gram.config`. Cuando se ejecuta dentro de una `Session`, el lexer consulta primero los valores específicos de `session.config` antes de recurrir al valor global de `gram.config`.

| Bandera de Ajuste | Tipo | Predeterminado | Efecto Operativo en el `Lexer` |
| :--- | :--- | :--- | :--- |
| `LEXER_COMMENT_TOKEN` | `str \| Token \| tuple` | `'#'` | Define el marcador o prefijos para comentarios de una línea fuera de cadenas literales (ej. `'//'`, `';'`, `'--'`). |
| `LEXER_BLOCK_COMMENT_TOKEN` | `str \| None` | `None` | Delimitador de apertura para comentarios de bloque multilínea (ej. `'/*'`). Cierra estrictamente con `'*/'`. |
| `LEXER_SUPPORT_BLOCK_COMMENTS` | `bool` | `True` | Si es `False`, los comentarios de bloque configurados en `LEXER_BLOCK_COMMENT_TOKEN` se procesan como operadores normales. |
| `LEXER_SUPPORT_DOCSTRINGS` | `bool` | `True` | Habilita cadenas multilínea con triples comillas al estilo Python (`"""..."""` y `'''...'''`). |
| `LEXER_SUPPORT_PREFIXED_STRINGS` | `bool` | `True` | Reconoce prefijos C en cadenas (`L"..."`, `u"..."`, `U"..."`, `u8"..."`), guardando el prefijo en `token.description`. |
| `LEXER_SUPPORT_LEADING_DOT_NUMBERS` | `bool` | `True` | Si es `True`, `.5` se tokeniza como `Token.DECIMAL(0.5)`. Si es `False`, emite `Token.DOT` y `Token.NUMBER(5)`. |
| `LEXER_TAB_WIDTH` | `int` | `4` | Ancho visual de columnas para tabuladores cuando `LEXER_INDENT_STYLE` es `"tabs"` o `"mixed"`. Mínimo `1`. |
| `LEXER_INDENT_STYLE` | `str` | `'spaces'` | Política de indentación: `"spaces"` (sólo espacios), `"tabs"` (sólo tabs) o `"mixed"` (expansión visual). |
| `SUPPORT_INDENT` | `bool` | `True` | Interruptor maestro de indentación. Si es `False`, omite por completo los tokens `Token.INDENT` y `Token.DEDENT`. |
| `SUPPORT_TRIPLE_DOT` | `bool` | `True` | Si es `True`, `...` emite `Token.THREE_DOTS`. Si es `False`, emite tres tokens `Token.DOT` consecutivos. |
| `LEXER_IGNORE_EMPTY_LINES` | `bool` | `True` | Si es `True`, las líneas vacías o de sólo comentarios se ignoran sin emitir tokens `Token.NEWLINE` redundantes. |
| `LEXER_IGNORE_NEWLINES` | `bool` | `True` | Si es `True`, los caracteres de salto de línea se descartan en vez de emitir `Token.NEWLINE`. |
| `LEXER_SAVE_COMMENTS` | `bool` | `True` | Si es `True`, los comentarios escaneados se guardan en `lexer.comments`. Si es `False`, se descartan al vuelo. |
| `LEXER_IDENT_UNDERSCORES` | `int` | `-1` | Control de guiones bajos en identificadores: `-1` (ilimitados, por defecto), `-2` (ilimitados sólo si hay caracteres posteriores; secuencias aisladas de `_` emiten `UNDERSCORE`), `0` (ningún identificador permite `_`; todos los `_` emiten `UNDERSCORE`), o `k >= 1` (máximo `k` guiones bajos iniciales en identificador; el exceso emite tokens `UNDERSCORE` individuales). |
| `TOKEN_BOOL_TRUE` | `str` | `'true'` | Valor textual que se convierte a `Token.BOOL` con `value=True` (insensible a mayúsculas). |
| `TOKEN_BOOL_FALSE` | `str` | `'false'` | Valor textual que se convierte a `Token.BOOL` con `value=False` (insensible a mayúsculas). |
| `TOKEN_NULL` | `str` | `'null'` | Valor textual que se convierte a `Token.NULL` con `value=None` (insensible a mayúsculas). |
| `LEXER_ADD_INFO` | `bool` | `True` | Habilita la creación de nodos de ejecución y notas de telemetría en la pila de `Diagnostics`. |
| `LEXER_ADD_ERROR` | `bool` | `True` | Registra entradas de fallos léxicos en la pila de diagnóstico activa. |
| `ERROR_EXIT_ON_ERROR` | `bool` | `True` | Si es `True`, los errores no controlados terminan el proceso vía `sys.exit(1)`. Cámbialo a `False` para recolectar diagnósticos. |
| `ERROR_HIDE_CONSOLE` | `bool` | `False` | Si es `True`, suprime la salida formateada ANSI en la consola al reportar errores. |

---

## 2. Telemetría de Diagnósticos y Árbol de Ejecución

`LexerState` hereda directamente de `Diagnostics` (`gram.utilities.Diagnostics`), proporcionando telemetría estructurada profunda para frontends de lenguaje.

### Pila Jerárquica de Diagnósticos

Cuando `LEXER_ADD_INFO=True`, el lexer genera automáticamente nodos anidados de telemetría:
- `LEXER`: Inicializado al crear el lexer, registrando el conteo total de líneas y configuración de logs.
- `LexingProcess`: Activo durante la ejecución de `process()`, registrando la generación paso a paso de tokens.
- `VISITOR-STRING` / `VISITOR-NUMBER` / `VISITOR-WORD` / `VISITOR-SYMBOL`: Nodos anidados bajo `LexingProcess` por cada carácter despachado.

```python
from gram import config
from gram.core.lexer import Lexer, words
words.add_keyword("let", allow_override=True)

# Habilitar registro detallado en archivo de log:
config.INFO_GENERATE_LOGFILE = True
lexer = Lexer("let x = 42;", logfile="compilador.log")
tokens = lexer.process()

# Acceder a la pila activa de diagnóstico:
stack = lexer.stack
print(f"Nodos de diagnóstico registrados: {len(stack.main.nodes)}")
```

### Desactivar Telemetría para Máximo Rendimiento

En compiladores de producción, suites de pruebas automatizadas o pruebas de rendimiento masivo, configura `LEXER_ADD_INFO = False`:
- Se salta la creación de nodos `StackInfo`.
- Se desactiva el formateo de notas y llamadas a emisores de telemetría.
- El bucle de escaneo se ejecuta a velocidad pura de Python sin sobrecarga alguna de observabilidad.

---

## 3. Manejo de Errores y Políticas de Salida

Cuando el lexer encuentra sintaxis inválida o caracteres no reconocidos, invoca `LexerState.report_error(err)` o `LexerState.fail(name, code, *caution)`.

```python
def report_error(self, err: errors.Error) -> errors.Error:
    res = self.record_failure(err)
    if (
        res is not None
        and not getattr(err, "_suppress_raise", False)
        and self.get_config("ERROR_EXIT_ON_ERROR", True)
    ):
        err.raise_error()
    return err
```

### Recolección de Errores sin Terminar el Proceso

Desde la versión `2.0.0b1`, `config.ERROR_EXIT_ON_ERROR` está predeterminado en `True`. Para recolectar errores programáticamente (por ejemplo, en servidores LSP de editores, IDEs o pruebas unitarias):

```python
from gram import config, errors
from gram.core.lexer import Lexer, words
words.add_keyword("dummy", allow_override=True)

# 1. Desactivar la terminación del proceso:
config.ERROR_EXIT_ON_ERROR = False
config.ERROR_HIDE_CONSOLE = True

# 2. Tokenizar código fuente con errores sintácticos:
lexer = Lexer('int x = "cadena sin cerrar')
tokens = lexer.process()

# 3. Inspeccionar los fallos de diagnóstico recolectados:
for failure in lexer.failures:
    print(f"Error [{failure.code}]: {failure.message}")
    for hint in failure.caution:
        print(f"  Consejo: {hint}")
```

### Registro de Ganchos de Error (`ErrorAction`)

Puedes interceptar y modificar el comportamiento de error dinámicamente mediante ganchos (*error hooks*):

```python
from gram.utilities import Diagnostics, ErrorAction

def mi_gancho_de_error(err):
    # Suprime sys.exit(1) mientras conserva el registro de telemetría:
    return ErrorAction.SUPPRESS_RAISE

Diagnostics.register_error_hook(mi_gancho_de_error)
```

---

## 4. Matriz de Códigos de Error Léxico OSGDC

Gram implementa el estándar de códigos de error OSGDC en todas las condiciones de fallo dentro de `gram.errors`:

| Identificador del Código | Constante del Enum | Causa que lo Dispara | Consejo de Resolución Recomendado |
| :--- | :--- | :--- | :--- |
| `LEXER_UNEXPECTED_CHARACTER` | `errors.LEXER_UNEXPECTED_CHARACTER` | Carácter que no coincide con ningún número, cadena, palabra, comentario u operador en `MAP_SYMBOLS`. | Registra el carácter u operador mediante `insert_symbol(simb, Token)` o ajusta los marcadores de comentarios. |
| `LEXER_UNCLOSED_STRING` | `errors.LEXER_UNCLOSED_STRING` | Se alcanzó el fin de línea o fin de archivo sin encontrar la comilla de cierre (`"`, `'`) o delimitador de docstring (`"""`, `'''`). | Asegúrate de cerrar la cadena con la comilla coincidente antes del final de la línea física. |
| `LEXER_INVALID_NUMBER` | `errors.LEXER_INVALID_NUMBER` | Literal numérico malformado (ej. guiones bajos mal ubicados `1__2`, `123_`, base inválida o exponente corrupto). | Verifica el prefijo de base (`0x`, `0b`, `0o`), la sintaxis del exponente y la posición de los guiones bajos. |
| `LEXER_INDENTATION_MISMATCH` | `errors.LEXER_INDENTATION_MISMATCH` | La desindentación de una línea no coincide con ningún nivel previo en la pila de indentación. | Revisa la consistencia de espacios/tabs y asegúrate de que el desalineamiento concuerde con un bloque superior. |
| `LEXER_EMPTY_KEYWORDS` | `errors.LEXER_EMPTY_KEYWORDS` | Se llamó a `Lexer.process()` con 0 palabras clave registradas en `words.MAP_KEYWORDS` o en la sesión activa. | Registra al menos una palabra clave de tu lenguaje con `words.add_keyword()` antes de escanear. |
| `LEXER_KEYWORD_INVALID_NAME` | `errors.LEXER_KEYWORD_INVALID_NAME` | Llamada a `words.add_keyword("")` con una cadena vacía o compuesta sólo de espacios en blanco. | Proporciona un identificador válido no vacío para la palabra clave. |
| `LEXER_KEYWORD_ALREADY_EXISTS` | `errors.LEXER_KEYWORD_ALREADY_EXISTS` | Intento de registrar una palabra clave previamente registrada sin activar `allow_override=True`. | Pasa `allow_override=True` para reemplazarla o utiliza un nombre de palabra clave diferente. |
| `LEXER_KEYWORD_NOT_FOUND` | `errors.LEXER_KEYWORD_NOT_FOUND` | Falló la búsqueda estricta de una palabra clave (`words.get_keyword(name, strict=True)`). | Asegúrate de registrar la palabra clave antes de consultarla en modo estricto. |
| `LEXER_WORDGROUP_NOT_FOUND` | `errors.LEXER_WORDGROUP_NOT_FOUND` | Falló la consulta estricta de un grupo (`words.get_group(name, strict=True)`). | Registra el grupo previamente mediante `words.add_group(name)`. |
| `LEXER_WORDGROUP_ALREADY_EXISTS` | `errors.LEXER_WORDGROUP_ALREADY_EXISTS` | Intento de crear un `WordGroup` con un nombre existente sin `allow_override=True`. | Pasa `allow_override=True` o valida el identificador del grupo. |
| `LEXER_WORDGROUP_KEYWORD_NOT_REGISTERED` | `errors.LEXER_WORDGROUP_KEYWORD_NOT_REGISTERED` | Intento de asociar un nombre de palabra clave no registrado a un `WordGroup`. | Registra primero la palabra clave con `words.add_keyword(kw)` antes de asociarla al grupo. |
| `LEXER_FILE_NOT_FOUND` | `errors.LEXER_FILE_NOT_FOUND` | `Lexer(Path("inexistente.gram"))` recibió una ruta de archivo que no existe en el sistema de archivos. | Verifica la existencia de la ruta del archivo y los permisos de lectura. |

---

## 5. Sesiones de Lenguaje y Ámbitos Léxicos

Al construir frontends para múltiples lenguajes en un mismo proceso, DSLs incrustados o suites de pruebas paralelas, utiliza `gram.sessions.Session` para aislar palabras clave, símbolos y configuraciones léxicas sin contaminación cruzada.

```python
from gram.sessions import Session
from gram.core.lexer import Token

# 1. Crear sesiones independientes para dos dialectos distintos:
session_sql = Session("Dialecto_SQL", "Many")
session_c = Session("Dialecto_C", "Many")

# 2. Configurar la sesión SQL:
session_sql.init()
session_sql.config["LEXER_COMMENT_TOKEN"] = "--"
session_sql.add_keyword("select")
session_sql.add_keyword("from")
session_sql.migrate()

# 3. Configurar la sesión C:
session_c.init()
session_c.config["LEXER_COMMENT_TOKEN"] = "//"
session_c.add_keyword("int")
session_c.add_keyword("return")
session_c.migrate()

# 4. Tokenizar con aislamiento garantizado por sesión:
tokens_sql = session_sql.tokenize("select * from usuarios; -- Consulta SQL")
tokens_c = session_c.tokenize("int main() { return 0; } // Código C")

# La sesión SQL sólo reconoce keywords de SQL:
print([t.value for t in tokens_sql if t.token == Token.KEYWORD])
# ['select', 'from']

# La sesión C sólo reconoce keywords de C:
print([t.value for t in tokens_c if t.token == Token.KEYWORD])
# ['int', 'return']
```

Durante `Session.init()`, Gram invoca internamente `words.bind_session(session)`, enrutando todas las llamadas globales a `words.add_keyword()` y `words.add_group()` directamente hacia los catálogos privados de la sesión hasta que se llama a `session.migrate()`.
