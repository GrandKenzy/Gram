# Diagnósticos y Sistema de Errores

Gram incluye un motor de telemetría de diagnóstico jerárquico (`gram.utilities.Diagnostics`, `gram.utilities.info`) y un catálogo formal de errores en 5 dimensiones (`gram.errors`, `gram.utilities.error`).

Tanto `ParseState` (`Parser`) como `ASTState` (`ASTAnalyzer`) heredan de `Diagnostics`, y también puedes heredar de `Diagnostics` directamente en tus propias fases de compilación (como analizadores semánticos o generadores de código).

---

## 1. Uso de `Diagnostics` para Telemetría Jerárquica

`Diagnostics` (`gram.utilities.Diagnostics`) administra un árbol de objetos `Node` de telemetría respaldado por `StackInfo` (`gram.utilities.info.StackInfo`).

### Heredar o Instanciar `Diagnostics`

```python
from gram.utilities import Diagnostics

class CompilerState(Diagnostics):
    def __init__(self) -> None:
        super().__init__(
            file="compiler-log",         # Bajo ./log/ cuando no hay una fuente activa
            name="COMPILER",             # Título del nodo raíz de telemetría
            description="Semantic pass", # Descripción del nodo raíz
            expose_nodes=True,           # Mostrar nodos secundarios al formatear en texto
            generate_log_file=False,     # True para registrar ./log/compiler-log.log inmediatamente
            generate_on_error=False,     # True para volcar el log al finalizar el proceso (atexit)
        )
```

### Emitir Notas y Construir Subárboles de Telemetría

- **Métodos de registro en `Diagnostics`:**
  - `diag.debug(msg)` $\rightarrow$ emite una nota `'normal'` en el nodo activo.
  - `diag.warn(msg)` $\rightarrow$ emite una nota `'warn'`.
  - `diag.advice(msg)` $\rightarrow$ emite una nota `'advice'`.
  - `diag.success(msg)` $\rightarrow$ emite una nota `'success'`.
  - `diag.error(msg)` $\rightarrow$ emite una nota `'error'`.
  - `diag.fatal(msg)` $\rightarrow$ emite una nota `'fatal'`.
- **Ámbitos de nodos secundarios (`node` y `down`):**
  - `diag.node(name, description="", set_target=True)` crea un `Node` secundario bajo el objetivo actual y lo activa cuando `set_target=True`.
  - `diag.down()` extrae el objetivo activo y devuelve el foco a su nodo padre.

```python
from gram.utilities import Diagnostics

diag = Diagnostics(
    file="semantic",
    name="SEMANTIC",
    description="Type checking pipeline",
    expose_nodes=True,
)

diag.debug("Iniciando resolución de módulos")
diag_node = diag.node("CheckFunction", "Validando fn 'main'", set_target=True)
try:
    diag.advice("Tipo de retorno inferido como 'int'")
    diag.success("Función 'main' validada")
finally:
    diag.down()

# Renderizar el árbol jerárquico de telemetría en texto (o imprimir con diag.stack.console()):
print(diag.stack.stringify(ansi=False))
```

### Persistir Logs de Telemetría en Disco

- Invocar `diag.stack.write()` escribe el árbol formateado mediante `gram.utilities.info.Log`. Sin una fuente activa, la ruta es `./log/<file>.log`; una fuente activa en `Format.FileTar` añade un directorio de fuente/rid.
- Invocar `gram.utilities.info.StackInfo.show_all()` escribe una vez el snapshot de cada `StackInfo` registrado.
- Para las fases integradas de Gram (`LexerState`, `Parser`, `ASTAnalyzer`), la verbosidad de telemetría y la creación automática de logs se configuran con `gram.config`:
  - `config.LEXER_ADD_INFO`, `config.PARSER_ADD_INFO`, `config.AST_ADD_INFO` (por defecto `True`).
  - `config.INFO_GENERATE_LOGFILE` (por defecto `False`) e `config.INFO_GENERATE_LOGFILE_ON_ERROR` (por defecto `False`).

---

## 2. Errores Estructurados OSGDC (`gram.errors`)

Todas las excepciones formales en Gram heredan de `gram.utilities.error.Error` y portan un código **OSGDC** de 5 dimensiones (`CodeError`) definido en `gram.errors`.

### Las 5 Dimensiones OSGDC

Cada `CodeError` se formatea como `<Tipo>-<O><S><G><D><C> · <Nombre>` (por ejemplo, `S-12411 · Gram.Parser.UnexpectedToken`), donde `S` indica un código estándar dentro de rango:

| Posición | Dimensión | Valores en `gram.errors` |
| :--- | :--- | :--- |
| **`O`** | **Origen** | `0`: Desconocido (`CODE_UNKNOWN_ORIGIN`), `1`: Nativo (`CODE_NATIVE_ERROR`), `2`: Plugin (`CODE_PLUGIN_ERROR`) |
| **`S`** | **Alcance (Scope)** | `0`: Desconocido, `1`: Lexer, `2`: Parser, `3`: Grammar/AST, `4`: Semántico, `5`: Compilación/DSL |
| **`G`** | **Gravedad** | `0`: Menor, `1`: Error de Implementación, `2`: Obsoleto, `3`: Interno, `4`: Fatal |
| **`D`** | **Documentación** | `0`: Documentado, `1`: Documentado y Rastreable, `2`: No Documentado |
| **`C`** | **Condición** | `0`: Usable, `1`: Requiere Reparación, `2`: Debería Repararse |

`set_map_codes()` valida todos los límites antes de reemplazar los mapas públicos
de códigos. Si un límite es inválido, los mapas anteriores permanecen intactos.
`CodeError` indexa el primer símbolo proporcionado para cada grupo y evalúa la
seguridad en O(número de grupos configurados).

### Clases de Error de Dominio

`gram.errors` proporciona 8 subclases de dominio de `Error`:
- `errors.LexerError` (ej.: `LEXER_UNEXPECTED_CHARACTER`, `LEXER_UNCLOSED_STRING`, `LEXER_INDENTATION_MISMATCH`)
- `errors.ParserError` (ej.: `PARSER_UNEXPECTED_TOKEN`, `PARSER_EARLY_EOF`, `PARSER_SYNTAX_ERROR`)
- `errors.GrammarError` (ej.: `GRAMMAR_COMBINATOR_FAILED`, `GRAMMAR_RULE_NOT_FOUND`, `GRAMMAR_COMBINATOR_UNSUPPORTED`)
- `errors.ASTError` (ej.: `AST_PROGRAM_RULE_NOT_FOUND`, `AST_PROGRAM_INVALID_COMBINATOR`, `AST_DECLARATOR_INVALID_ELEMENT`)
- `errors.SemanticError` (ej.: `SEMANTIC_TYPE_MISMATCH`, `SEMANTIC_UNDEFINED_SYMBOL`, `SEMANTIC_DUPLICATE_SYMBOL`, `SEMANTIC_SCOPE_VIOLATION`)
- `errors.CompilationError`
- `errors.PluginError`
- `errors.SystemError`

### Crear y Emitir un Error Estructurado

```python
from gram import config, errors

err = errors.SemanticError(
    "TypeMismatch",
    errors.SEMANTIC_TYPE_MISMATCH,
    "No se puede asignar un valor de tipo 'str' a la variable 'count' de tipo 'int' en línea 4, columna 10.",
    "Convierte la expresión a 'int' o modifica la declaración de tipo de la variable.",
)

# Formatear sin lanzar:
print(err.stringify(ansi=False))
```

Salida:

```text
|---------------- ERROR -----------------|
Name: TypeMismatch, Type: SemanticError.

CAUTION: No se puede asignar un valor de tipo 'str' a la variable 'count' de tipo 'int' en línea 4, columna 10.

Convierte la expresión a 'int' o modifica la declaración de tipo de la variable.

INF:
    FILE: unknown
    ORIGIN: ...
    CODE: S-14411 · Gram.Semantic.TypeMismatch

|------------- END OF ERROR -------------|
```

### Política de Salida (`config.ERROR_EXIT_ON_ERROR`) y `StackError`

Cuando se invoca `err.raise_error()` (o `parser.report_error(err)` / `analyzer.report_error(err)` fuera de `safe_mode()`):
1. A menos que `config.ERROR_HIDE_CONSOLE` sea `True`, la caja del error se imprime en stdout.
2. Si `config.ERROR_EXIT_ON_ERROR` es `True` (**el valor por defecto en `2.1.0`**), Gram ejecuta `sys.exit(1)`.
3. Si `config.ERROR_EXIT_ON_ERROR` es `False`, Gram lanza `err` como una excepción ordinaria de Python.

Los errores no se agregan automáticamente a `StackError`. Para rastrearlos en el
registro global (`gram.utilities.error.StackError`) y volcarlos en `./log/error.log`:
- `StackError.add(err)` registra una instancia una sola vez por identidad; otra instancia distinta se conserva aunque su texto sea igual.
- `StackError.all()`, `StackError.last()`, `StackError.count()`, `StackError.clear()` inspeccionan o reinician la pila.
- `StackError.index_of(err)` devuelve el índice registrado comenzando en cero, o `-1`.
- `StackError.write()` sobrescribe el snapshot en texto plano, conserva el orden de registro y separa las entradas con líneas vacías.

---

## 3. Intercepción No Invasiva de Errores (`Diagnostics.hook_errors`)

Al construir un Servidor de Lenguaje para IDE (`LSPState`), un linter multierror o una suite de pruebas, a menudo se desea ejecutar el lexer y el parser **sin** que `sys.exit(1)` termine el proceso ni se lance una excepción no capturada, recolectando al mismo tiempo todos los objetos `Error`.

`Diagnostics` proporciona hooks a nivel de instancia (`diag.add_hook(fn)`) y un gestor de contexto global (`Diagnostics.hook_errors(fn)`). Cada hook recibe `(sender, err)` y retorna una directiva `ErrorAction` (`gram.utilities.ErrorAction`):

| Directiva | Constante | Efecto |
| :--- | :--- | :--- |
| `"store"` | `ErrorAction.STORE` | Comportamiento por defecto: agrega `err` a `sender._errors` y respeta `config.ERROR_EXIT_ON_ERROR`. |
| `"suppress"` | `ErrorAction.SUPPRESS_RAISE` | Agrega `err` a `sender._errors`, establece `err._suppress_raise = True` y **evita** imprimir, lanzar excepciones o invocar `sys.exit(1)`. |
| `"omit"` | `ErrorAction.OMIT` | Ignora completamente `err`: **no** lo guarda en `sender._errors` y **no** lanza excepción ni sale. |
| `"raise"` | `ErrorAction.RAISE` | Agrega `err` a `sender._errors` e invoca inmediatamente `err.raise_error()`. |

### Ejemplo: Recolectar Errores de Sintaxis sin Terminar el Proceso

```python
from gram import combinators as cmb
from gram import lexer, parser
from gram.utilities import Diagnostics, ErrorAction, error

class Stmt(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.MatchToken(lexer.Token.IDENT),
        cmb.MatchToken(lexer.Token.ASSIGN),
        cmb.MatchToken(lexer.Token.NUMBER),
    )

class Program(cmb.RuleItem):
    entrypoint = cmb.Alt(cmb.Ref(Stmt))

captured: list[error.Error] = []

def intercept_errors(sender: object, err: error.Error) -> str:
    captured.append(err)
    return ErrorAction.SUPPRESS_RAISE

# Parsear entrada mal formada ("x = ;" en lugar de "x = 1") sin salir ni imprimir en consola
with Diagnostics.hook_errors(intercept_errors):
    tokens = lexer.Lexer("x = ;").process()
    ast_nodes = parser.Parser(tokens).parse(Program)

print("Errores capturados:", len(captured))
print("Nombre del error más profundo:", captured[0].name)
print("Código de error:", captured[0].code.stringify())
```

Salida:

```text
Errores capturados: 2
Nombre del error más profundo: TokenMismatch
Código de error: S-12411 · Gram.Parser.UnexpectedToken
```
