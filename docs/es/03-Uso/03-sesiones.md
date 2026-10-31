# Sesiones de Lenguaje (`gram.sessions.Session`)

> **Módulo:** `gram.sessions`  
> **Estado:** Estable (Versión `2.1.0`)  
> **Runtime:** Python 3.12+ puro (Cero dependencias externas en tiempo de ejecución)

En frontends de compiladores para múltiples lenguajes, DSLs incrustados o suites de pruebas paralelas, compartir estado global es un antipatrón. Los diccionarios globales de palabras clave, tablas mutables de símbolos y banderas de configuración como singletons provocan condiciones de carrera, contaminación cruzada entre pruebas y colisiones sintácticas accidentales.

`Session` (`gram.sessions.Session`) proporciona **aislamiento completo a nivel de proceso** para frontends de lenguaje. Cada `Session` encapsula su propio léxico (`Keyword`), grupos semánticos (`WordGroup`), mapeos personalizados de operadores (`MAP_SYMBOLS`), banderas de configuración, revisiones para combinadores predictivos e instancias dedicadas tanto de `Lexer` como de `Parser`.

---

## 1. Arquitectura y Modelo de Memoria

```
                        Espacio del Proceso de Python
 ┌────────────────────────────────────────────────────────────────────────┐
 │ Estado Global Legacy de Compatibilidad (words.MAP_KEYWORDS, config...) │
 └───────────────────▲────────────────────────────────▲───────────────────┘
                     │                                │
        session1.init() / migrate()      session2.init() / migrate()
                     │                                │
 ┌───────────────────▼──────────────┐ ┌───────────────▼──────────────────┐
 │      Session: "Dialecto-C"       │ │     Session: "Dialecto-SQL"      │
 │                                  │ │                                  │
 │ - keywords: {"int", "return"...} │ │ - keywords: {"select", "from"...}│
 │ - groups:   {"types", "storage"} │ │ - groups:   {"verbs", "clauses"} │
 │ - symbols:  {"->", "++", "/*"...}│ │ - symbols:  {"<>", "--", ";"...} │
 │ - config:   {LEXER_COMMENT: "//"}│ │ - config:   {LEXER_COMMENT: "--"}│
 │ - mode:     "Many"               │ │ - mode:     "Some"               │
 │ - entrypoint: CTranslationUnit   │ │ - entrypoint: SQLStatement       │
 │ - lexer:    Lexer (session=self) │ │ - lexer:    Lexer (session=self) │
 │ - parser:   Parser(session=self) │ │ - parser:   Parser(session=self) │
 │ - revision: int (predictivo)     │ │ - revision: int (predictivo)     │
 └──────────────────────────────────┘ └──────────────────────────────────┘
```

### Invariantes de Aislamiento de Proceso

1. **Cero Fuga Global:** Crear, configurar o mutar una sesión no modifica el estado global fuera de la ventana temporal de configuración `init()` $\to$ `migrate()`.
2. **Tokenización Independiente:** Invocar `session.tokenize()` ejecuta el análisis directamente sobre los catálogos privados de la sesión sin requerir `session.load()`.
3. **Propagación del Contexto al Parser y AST:** `session.parse()` transmite el contexto de la sesión a través de `Parser` hacia `ASTAnalyzer`, permitiendo que combinadores como `MatchGroup` y `MatchKeyword` resuelvan catálogos de grupos de forma dinámica desde la sesión activa.
4. **Invalidación de Cachés Predictivos:** Cualquier mutación a las palabras clave o grupos de la sesión incrementa automáticamente `predictive_revision`, invalidando tablas cacheadas de decisión en combinadores `Alt`.

---

## 2. Constructor y Propiedades

### Firma del Constructor

```python
Session(
    name: str,
    mode: Literal["Many", "Some"],
    entrypoint: type[RuleItem] | None = None,
)
```

| Parámetro | Tipo | Descripción |
| :--- | :--- | :--- |
| `name` | `str` | Identificador lógico del frontend (utilizado en registradores de diagnóstico e instancias del parser). |
| `mode` | `Literal["Many", "Some"]` | Política de cardinalidad de análisis. `"Many"` analiza múltiples sentencias sucesivas hasta `Token.EOF`. `"Some"` evalúa la producción del entrypoint una sola vez. Debe ser estrictamente `"Many"` o `"Some"`, o lanzará `ValueError`. |
| `entrypoint` | `type[RuleItem] \| None` | Regla gramatical raíz por defecto evaluada durante `session.parse()`. Puede sobrescribirse por llamada en `parse()`. |

### Atributos de Instancia (`__slots__`)

| Atributo | Tipo | Descripción |
| :--- | :--- | :--- |
| `session.name` | `str` | Nombre de la sesión de lenguaje. |
| `session.mode` | `str` | Modo de análisis sintáctico (`"Many"` o `"Some"`). |
| `session.entrypoint` | `type[RuleItem] \| None` | Regla de producción raíz para el análisis AST. |
| `session.keywords` | `dict[str, Keyword]` | Catálogo aislado de palabras clave registradas. |
| `session.groups` | `dict[str, WordGroup]` | Catálogo aislado de grupos semánticos de palabras clave. |
| `session.symbols` | `_MapSymbolsDict` | Tabla bidireccional aislada de símbolos y operadores. |
| `session.symbol_order` | `list[str]` | Lista de símbolos ordenados por longitud descendente para *maximal munch*. |
| `session.config` | `dict[str, Any]` | Diccionario filtrado con todas las opciones de lexer, parser, AST, errores y logs que pertenecen a la sesión. |
| `session.lexer` | `Lexer` | Instancia dedicada del lexer enlazada a `session=self`. |
| `session.parser` | `Parser` | Instancia reutilizable del parser enlazada a `session=self`. |
| `session.predictive_revision` | `int` | Contador monótono de revisión para invalidación de cachés predictivos. |

### Claves de Configuración de la Sesión (`_SESSION_CONFIG_KEYS`)

`Session.config` captura únicamente banderas de configuración pertenecientes a las tuberías sintácticas, semánticas y de diagnóstico:
- Cualquier ajuste que comience con `LEXER_`, `PARSER_`, `AST_`, `ERROR_` o `INFO_`.
- Interruptores sintácticos esenciales: `SUPPORT_TRIPLE_DOT`, `SUPPORT_INDENT`, `TOKEN_BOOL_TRUE`, `TOKEN_BOOL_FALSE`, `TOKEN_NULL` y `LOG_HIDE_CONSOLE`.
- Las configuraciones de entorno global (como registros de plugins o generadores VSIX) son deliberadamente excluidas de las sesiones.

---

## 3. Máquina de Estados del Ciclo de Vida

Gram implementa un ciclo de vida robusto para definir, aislar y activar sesiones de lenguaje:

```
                  ┌────────────────────────┐
                  │ Instanciación Sesión   │
                  │   Session(name, mode)  │
                  └───────────┬────────────┘
                              │
                              ▼
                      session.init()
       (Guarda estado global, enlaza API words)
                              │
                              ▼
           ┌──────────────────────────────────────┐
           │      Registro de Léxico y Símbolos   │
           │  session.add_keyword() / add_group() │
           │  mutaciones de config/session.config │
           └──────────────────┬───────────────────┘
                              │
                              ▼
                     session.migrate()
    (Congela sesión, desenlaza API, restaura globales)
                              │
               ┌──────────────┴──────────────┐
               ▼                             ▼
       session.tokenize()             session.load()
        session.parse()            (Exportación legacy global)
  (Ejecución 100% aislada)
```

### Fase 1: `init()`
Prepara el almacenamiento aislado y redirige registros globales hacia esta sesión:
1. Toma una instantánea del estado global activo: `words.MAP_KEYWORDS`, `words._GLOBAL_GROUPS`, `tokens.MAP_SYMBOLS` y `config.save()`.
2. Clona los símbolos globales en `session.symbols` y sincroniza sus índices.
3. Filtra y copia las opciones de configuración en `session.config`.
4. Invoca `words.bind_session(self)`: Todas las funciones globales sueltas (`words.add_keyword()`, `words.add_group()`) se redirigen para poblar esta sesión en vez de los diccionarios globales.

### Fase 2: Registro
Dentro de la ventana `init()` $\to$ `migrate()`, registra palabras clave, grupos y configuraciones:

```python
from gram import config
from gram.sessions import Session

session = Session("Subconjunto-C", "Many")
session.init()

# 1. Registrar grupos y palabras clave directamente o vía words
session.add_group("types", color_group="#3B82F6")
session.add_keyword("int", group="types")
session.add_keyword("return", hex_color="#FF79C6")

# 2. Configurar opciones del lexer para la sesión
config.LEXER_COMMENT_TOKEN = "//"
config.LEXER_BLOCK_COMMENT_TOKEN = "/*"
config.SUPPORT_INDENT = False
```

### Fase 3: `migrate()`
Congela la configuración de la sesión y restaura el estado global del proceso:
1. Empaqueta `session.keywords`, `session.groups`, `session.symbols` y `session.config` en atributos congelados (`session.words`, `session.group`, etc.).
2. Desvincula la sesión mediante `words.unbind_session(self)`.
3. Restaura los diccionarios globales (`words.MAP_KEYWORDS`, `words._GLOBAL_GROUPS`, `tokens.MAP_SYMBOLS`) y recarga la configuración previa con `config.load()`.
4. Incrementa `_predictive_revision`.

> [!IMPORTANT]
> Al culminar `migrate()`, la sesión es completamente autosuficiente. Puede tokenizar y parsear entradas de forma autónoma sin leer ni escribir en variables o diccionarios globales.

### Fase 4: `load()` (Compatibilidad Legacy)
Activa el contenido de la sesión en los diccionarios globales de compatibilidad del proceso:
- Sobrescribe `words.MAP_KEYWORDS`, `words._GLOBAL_GROUPS` y `tokens.MAP_SYMBOLS` con los catálogos de esta sesión.
- Carga `session.config` en `gram.config`.
- Establece `session._loaded = True`. Cualquier llamada directa posterior a `session.add_keyword()` o `session.add_group()` sincroniza de inmediato hacia los diccionarios globales mediante `_sync_legacy_catalog()`.
- Lanza `RuntimeError` si se invoca antes de haber llamado a `migrate()`.

### Fase 5: `clear_global()`
Limpia los diccionarios internos `keywords` y `groups` de la sesión. Si se invoca antes de `init()` (previo a cualquier captura de respaldo), también vacía los catálogos globales `words.MAP_KEYWORDS` y `words._GLOBAL_GROUPS`.

---

## 4. Tubería de Ejecución (`tokenize` y `parse`)

### Tokenización: `session.tokenize()`

```python
def tokenize(self, source: list[str] | str, name: str) -> list[TokenType]:
```

Tokeniza `source` utilizando `session.lexer`. Debido a que `session.lexer` posee una referencia a `self`, todas las consultas de palabras clave, grupos, símbolos y banderas se resuelven directamente desde `session.keywords`, `session.symbols` y `session.config`.

```python
tokens = session.tokenize("int contador = 42; // inicialización", "main.c")
```

### Análisis Sintáctico: `session.parse()`

```python
def parse(
    self,
    tokens: list[TokenType],
    name: str,
    entrypoint: type[RuleItem] | None = None,
    *,
    conversion_state: ConversionState | MutableMapping[str, ConversionTarget] | None = None,
    trace: Literal["off", "basic", "detailed"] = "basic",
) -> list[ASTNode]:
```

Ejecuta el análisis sintáctico y la construcción del AST:
1. Resuelve la regla de entrada: utiliza `entrypoint` si se suministra, recurriendo a `self.entrypoint` por defecto. Si ninguno existe, lanza `RuntimeError("No se especificó una entrada")`.
2. Reinicia la instancia reutilizable `session.parser` con los nuevos `tokens`, nombre de la unidad de compilación `name` y estado opcional de conversiones.
3. Transmite `session=self` al `Parser` y al `ASTAnalyzer`. Combinadores como `MatchGroup` validan pertenencia contra `session.groups`.
4. Evalúa la gramática según la política de `session.mode` (`"Many"` o `"Some"`).
5. Si el análisis culmina con éxito y se proporcionó `conversion_state`, exporta las nuevas conversiones de tokens hacia `conversion_state`.
6. Retorna la lista resultante de nodos `list[ASTNode]`.

---

## 5. Transferencia de Estado Multi-Unidad: `ConversionState`

En lenguajes con unidades de compilación modulares (tales como cabeceras C `#include`, sentencias de importación en DSLs o declaraciones de tipos mediante macros), las definiciones o alias descubiertos en un archivo frecuentemente deben transferirse a los archivos siguientes sin contaminar sesiones ajenas.

Gram maneja esto de manera explícita y segura a través de `ConversionState` (`gram.core.parser.ConversionState`):

```python
from gram.core.parser import ConversionState

# 1. Inicializar el estado de conversión para el proyecto
estado_conv = session.new_conversion_state()

# 2. Analizar archivo de cabecera (registra typedefs/conversiones vía Convert(..., scope=True))
session.parse(header_tokens, "types.h", conversion_state=estado_conv)

# 3. Analizar código fuente principal heredando las conversiones de la cabecera
session.parse(source_tokens, "main.c", conversion_state=estado_conv)
```

### Garantías Transaccionales

Si un archivo falla al analizarse debido a un error sintáctico o un conflicto, **`conversion_state` no se actualiza**. El estado externo permanece protegido en su condición previa al intento de análisis, evitando que archivos malformados corrompan el contexto compartido de compilación.

### API de `ConversionState`

| Método | Tipo de Retorno | Descripción |
| :--- | :--- | :--- |
| `state.export()` | `dict[str, ConversionTarget]` | Retorna una copia desacoplada de todas las conversiones registradas. |
| `state.replace(source)` | `None` | Reemplaza todas las conversiones con una copia validada de `source`. |
| `state.register(name, target, *, replace=False)` | `None` | Registra una conversión identificador $\to$ `Token`. Lanza `ValueError` en caso de conflicto salvo que `replace=True`. |
| `state.clear()` | `None` | Elimina todas las conversiones registradas. |
| `state.clone()` | `ConversionState` | Retorna una copia independiente de la instancia. |

---

## 6. Invalidación Predictiva de Gramáticas (`predictive_revision`)

La librería de combinadores de Gram implementa alternativas predictivas (`Alt`), las cuales analizan los tokens anticipados (*lookahead*) y cachean ramas de decisión para despacho en tiempo $O(1)$.

Cuando el léxico o los símbolos de una sesión mutan dinámicamente:
1. `session._touch_predictive_revision()` incrementa `session._predictive_revision`.
2. Dispara automáticamente `_touch_predictive_epoch()` en `gram.core.combinators.base`.
3. Todos los combinadores predictivos inspeccionan la época de revisión, invalidando tablas de decisión obsoletas al vuelo sin necesidad de vaciar cachés manualmente.

---

## 7. Métodos de Inspección de Catálogos

`Session` ofrece métodos de consulta seguros que permiten inspeccionar sus catálogos internos sin mutar el estado global:

```python
# 1. Obtener una instancia Keyword o None
kw = session.get_keyword("int")

# 2. Obtener una instancia WordGroup o None
grupo = session.get_group("types")

# 3. Comprobar existencia del grupo
existe = session.group_exists("types")

# 4. Comprobar membresía en O(1)
es_miembro = session.exists_in_group("int", "types")

# 5. Total de palabras clave registradas en esta sesión
total = session.keyword_count()
```

---

## 8. Ejemplo Completo de Integración Multi-Lenguaje

A continuación se presenta un patrón completo donde dos frontends totalmente independientes (un lenguaje estilo C y un lenguaje de consultas estilo SQL) conviven y se ejecutan en simultáneo en el mismo proceso:

```python
from gram import combinators as cmb
from gram.core.lexer import Token
from gram.sessions import Session

# ---------------------------------------------------------------------------
# 1. Reglas de Producción Gramatical
# ---------------------------------------------------------------------------
class VarDecl(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.MatchGroup("types"),
        cmb.MatchToken(Token.IDENT),
        cmb.MatchToken(Token.ASSIGN),
        cmb.MatchToken(Token.NUMBER),
        cmb.MatchToken(Token.SEMICOLON),
    )

class CProgram(cmb.RuleItem):
    entrypoint = cmb.Alt(cmb.Ref(VarDecl))

class SelectQuery(cmb.RuleItem):
    entrypoint = cmb.Seq(
        cmb.MatchKeyword("select"),
        cmb.MatchToken(Token.IDENT),
        cmb.MatchKeyword("from"),
        cmb.MatchToken(Token.IDENT),
    )

class SQLProgram(cmb.RuleItem):
    entrypoint = cmb.Alt(cmb.Ref(SelectQuery))

# ---------------------------------------------------------------------------
# 2. Configurar Sesión 1: Frontend C
# ---------------------------------------------------------------------------
c_session = Session("Frontend-C", "Many", entrypoint=CProgram)
c_session.init()
c_session.add_group("types")
c_session.add_keyword("int", group="types")
c_session.add_keyword("float", group="types")
c_session.config["LEXER_COMMENT_TOKEN"] = "//"
c_session.config["SUPPORT_INDENT"] = False
c_session.migrate()

# ---------------------------------------------------------------------------
# 3. Configurar Sesión 2: Frontend SQL
# ---------------------------------------------------------------------------
sql_session = Session("Frontend-SQL", "Some", entrypoint=SQLProgram)
sql_session.init()
sql_session.add_keyword("select")
sql_session.add_keyword("from")
sql_session.config["LEXER_COMMENT_TOKEN"] = "--"
sql_session.migrate()

# ---------------------------------------------------------------------------
# 4. Tokenización y Análisis Sintáctico Aislados
# ---------------------------------------------------------------------------
c_source = "int puntaje = 100; // Comentario C\nfloat ratio = 2;"
c_tokens = c_session.tokenize(c_source, "game.c")
c_ast = c_session.parse(c_tokens, "game.c", trace="off")

sql_source = "select username from users -- Comentario SQL"
sql_tokens = sql_session.tokenize(sql_source, "query.sql")
sql_ast = sql_session.parse(sql_tokens, "query.sql", trace="off")

print(f"Nodos AST de C generados: {len(c_ast)}")      # 2 nodos VarDecl
print(f"Nodos AST de SQL generados: {len(sql_ast)}")  # 1 nodo SelectQuery

# Nota: 'int' NO es palabra clave en la sesión SQL
prueba_cruzada = sql_session.tokenize("int puntaje", "test.sql")
print(prueba_cruzada[0].token)  # Token.IDENT (¡no es Token.KEYWORD!)
```

---

## 7. Compilación Ahead-Of-Time (AOT) a C desde una Sesión

Una instancia de `Session` puede exportar su definición léxica y gramatical completa hacia unidades de código C11 independientes y sin dependencias externas:

```python
manifest = c_session.export_c_parser(
    "build/c_dialect",
    emit_driver=True,  # Emite el driver unificado y serializadores de GIR binario
    emit_cli=True,     # Emite un ejecutable de línea de comandos autónomo (gram_cli.c)
)

print("Archivos C generados:", manifest["files"])
print("Fingerprint de la gramática:", manifest["grammar_id"])
```

El directorio exportado contiene:
- `gram_ast.h`, `gram_ast.c`: Arena compacta de nodos AST y undo log transaccional.
- `gram_parser.h`, `gram_parser.c`: Parser descendente recursivo con tablas de salto predictivas.
- `gram_lexer_*.c`: Tablas estáticas hash para keywords, grupos y operadores de la sesión.
- `gram_driver.h`, `gram_driver.c`: Driver unificado, lector zero-copy de archivos y reportero de errores.
- `gram_ir.h`, `gram_ir.c`: Representación intermedia binaria relocalizable (GIR 1.0).
- `gram_cli.c`: Interfaz de línea de comandos autónoma con modos `compile`, `check`, `ast` e `ir`.
- `gram_parser_manifest.json`: Manifiesto de verificación con hashes SHA-256 y metadatos de compilación.
