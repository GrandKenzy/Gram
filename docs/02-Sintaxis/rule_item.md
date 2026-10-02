# Especificación y Documentación Oficial de `RuleItem` (`gram.core.combinators.base`)

`RuleItem` es la clase base declarativa fundamental de **Gram Framework** para modelar reglas de producción gramatical. Diseñada bajo un patrón híbrido que combina análisis sintáctico formal y soporte enriquecido para entornos de desarrollo (IDEs), `RuleItem` no solo define cómo los combinadores procesan los tokens, sino que también centraliza la telemetría, el resaltado de sintaxis (TextMate), las sugerencias de autocompletado (Snippets), la documentación flotante (LSP Hover) y el comportamiento estructural dentro del Árbol de Sintaxis Abstracta (AST).

---

## 1. Arquitectura y Ciclo de Vida de una Regla

En Gram Framework, cada regla sintáctica es una subclase de `RuleItem` administrada por la metaclase `RuleMeta`. Actúa como puente unificado entre múltiples subsistemas:

```
                            ┌────────────────────────┐
                            │    Regla Declarativa   │
                            │   class MY_RULE(Rule)  │
                            └───────────┬────────────┘
                                        │
           ┌────────────────────────────┼───────────────────────────┐
           ▼                            ▼                           ▼
 ┌──────────────────┐         ┌──────────────────┐        ┌──────────────────┐
 │   AST Analyzer   │         │  VSIX Generator  │        │    LSP Server    │
 │ process_rule()   │         │     compile()    │        │   handle_hover   │
 └─────────┬────────┘         └─────────┬────────┘        └─────────┬────────┘
           │                            │                           │
  ¿is_structural?              Extracción de Metadatos       Tarjeta Markdown:
   ├── True: Retorna valor      ├── Scopes TextMate          ├── Nombre y Código
   └── False: ASTNode           ├── Temas y Colores          └── Docs / Description
                                └── Snippets VS Code
```

---

## 2. Metaclase `RuleMeta`

`RuleItem` está configurada con la metaclase `RuleMeta`:

```python
class RuleMeta(type):
    def __repr__(cls) -> str:
        return (
            f"{cls.__name__}("
            f"code={getattr(cls, 'code', 0)!r}, "
            f"name={getattr(cls, 'name', cls.__name__)!r}, "
            f"grammar={bool(getattr(cls, 'grammar', None))}"
            f")"
        )
```

### Funciones de `RuleMeta`:
- **Introspección Rápida:** Al imprimir o inspeccionar una clase regla en la consola interactiva (REPL), depurador o logs de error, muestra de forma concisa su identificador, código numérico y si tiene gramática activa asociada.
- **Identidad Formal:** Garantiza que cada clase derivada sea tratada como un tipo sintáctico de primer orden dentro de los mapas de reglas (`RULES_BY_ID`, `RULES_BY_NAME`).

---

## 3. Catálogo Exhaustivo de Atributos y Propiedades

A continuación se detallan todas las propiedades disponibles en `RuleItem`:

| Propiedad | Tipo | Valor por Defecto | Descripción |
| :--- | :--- | :--- | :--- |
| `code` | `int` | `0` | Identificador numérico único de la regla en el catálogo global de Gram. |
| `name` | `str` | `""` | Nombre canónico de la regla. Si está vacío, hereda `cls.__name__`. |
| `description` | `str` | `""` | Resumen breve de la regla, expuesto en tooltips de autocompletado y hover de LSP. |
| `docs` | `str` | `""` | Documentación técnica detallada (soporta Markdown), mostrada en tarjetas flotantes del editor. |
| `grammar` | `Combinator \| None` | `None` | Árbol de combinadores sintácticos (`Seq`, `Alt`, `Many`, `Opt`, `MatchToken`, etc.) que define la producción. |
| `colors` | `dict[int, str]` | `{}` | Mapeo de códigos o estados a colores HEX (ej. `{0: "#6A9955"}`) para temas del editor. |
| `suggestions` | `dict[int, Any]` | `{}` | Plantillas y opciones de autocompletado para el motor de sugerencias o snippets de VS Code. |
| `suggestions_autocomplete` | `bool` | `False` | Habilita o deshabilita la exportación de las sugerencias al archivo `snippets.json` del editor. |
| `is_structural` | `bool` | `False` | Si es `True`, el AST Analyzer omite la creación de un `ASTNode` y devuelve el resultado directo. |
| `queries` | `list[Query] \| set[Query] \| Query` | `None` | Consultas dinámicas de autocompletado contextual en vivo para LSP (ej. `Query.query_roots`). |
| `hints` | `dict[int, Hints]` | `{}` | Pistas virtuales e Inlay Hints contextuales (ej. `Hints.new(processor=...)`). |

---

### 3.1. `code: int`
Identificador numérico exclusivo de la regla gramatical. Gram organiza los rangos numéricos para evitar colisiones:

- **Rango Protegido del Sistema (0 a 20):** Reservado para reglas primitivas y estructurales del núcleo (`gram.native.rules`):
  - `0`: `PROGRAM` (Regla raíz del programa)
  - `1`: `DECLARATION` (Contenedor de declaraciones de alto nivel)
  - `2`: `ENDLINE` (Fin de línea o fin de archivo con comentarios opcionales)
  - `3`: `BLOCK` (Contenedor abstracto de bloques)
  - `4`: `INDENT_BLOCK` (Bloques estructurados por indentación `INDENT...DEDENT`)
  - `5`: `DOCSTRING` (Cadenas multilínea de documentación)
  - `6`: `HEXADECIMAL` (Literales hexadecimales)
  - `30`: `PASS` (Instrucción nula)
- **Rango Recomendado para Plugins y Usuarios (100 a 100,000):** Todo DSL, lenguaje derivado o plugin debe asignar identificadores `>= 100` (`RECOMMENDED_MIN_PLUGIN_ID`).

```python
class VAR_DECL(RuleItem):
    code: int = 1050  # Código dentro del rango seguro
    name: str = "VAR_DECL"
```

---

### 3.2. `name: str`
Nombre canónico de la regla sintáctica.
- Si se omite o se define como cadena vacía, los métodos `compile()` y `ASTNode.from_rule_result()` toman automáticamente el nombre de la clase Python (`cls.__name__`).
- Se utiliza como identificador en `ASTNode.name`, en los selectores de búsqueda del AST (`node["VAR_DECL"]` o `node.find_all("VAR_DECL")`) y para sanear el nombre del scope TextMate (`entity.name.rule.gram.<clean_name>`).

---

### 3.3. `description: str`
Descripción corta en texto plano.
- Usada por el Language Server Protocol (`handle_hover` en `gram.vsix.lsp`) como el primer párrafo descriptivo cuando el usuario pasa el ratón sobre una palabra clave o regla en el editor.
- Usada como campo `"description"` en los fragmentos de código de VS Code (`snippets/snippets.json`).

---

### 3.4. `docs: str`
Cadena de documentación extendida.
- Soporta formato **Markdown**.
- Permite documentar ejemplos de sintaxis, reglas semánticas, advertencias o casos de uso.
- Si `description` no está presente, el servidor LSP recurre a `docs` para desplegar la tarjeta flotante de ayuda.

```python
class FUNCTION_DEF(RuleItem):
    code: int = 1200
    name: str = "FUNCTION_DEF"
    description: str = "Declaración de función con parámetros tipados"
    docs: str = """
    ### Sintaxis:
    ```gst
    def nombre_funcion(arg1: int, arg2: str) -> bool:
        # cuerpo
    ```
    Define una subrutina invocable con verificación estática de tipos.
    """
```

---

### 3.5. `grammar: Combinator | None`
Define la estructura sintáctica formal mediante la composición de combinadores de Gram (`Seq`, `Alt`, `Opt`, `Many`, `Some`, `MatchToken`, `MatchKeyword`, `Ref`, `Separator`, etc.).

- Si `grammar` es `None`, la regla actúa como un **símbolo abstracto o punto de anclaje** (como `PROGRAM`, `DECLARATION` o `BLOCK`), cuya gramática se asigna dinámicamente o se extiende mediante plugins con `extend_declarations()`.
- Para reglas con recursividad mutua o referencias hacia adelante, se debe utilizar `Ref(NombreRegla)` o asignar la propiedad `grammar` después de haber definido las clases correspondientes.

```python
# Asignación declarativa directa
class IF_STMT(RuleItem):
    code: int = 1300
    grammar = Seq(
        MatchKeyword("if"),
        Ref("EXPRESSION"),
        MatchToken("COLON"),
        Ref("BLOCK"),
    )
```

---

### 3.6. `colors: dict[int, str]`
Mapeo de códigos o subíndices a cadenas de color hexadecimal (ejemplo: `{0: "#4EC9B0"}`).
- **Resolución de Color Primario:**
  El método `compile()` extrae el color primario de la regla buscando primero la clave `0`. Si no existe la clave `0`, toma el primer valor del diccionario. Si el diccionario está vacío, el color por defecto es `#FFFFFF`.
- **Integración con Temas VSIX:**
  El generador de temas de Visual Studio Code (`gram.vsix.generate.generate_theme`) toma este color e inyecta una regla de token en `themes/gram-theme.json`:
  ```json
  {
      "name": "Gram Rule: VAR_DECL",
      "scope": ["entity.name.rule.gram.var_decl"],
      "settings": {
          "foreground": "#4EC9B0",
          "fontStyle": "normal"
      }
  }
  ```

---

### 3.7. `suggestions: dict[int, Any]`
Define plantillas de código y sugerencias contextuales para el editor. Puede adoptar dos estructuras:

1. **Lista de tuplas `[(label, doc), ...]`, indexada por número:**
   ```python
   suggestions: dict[int, Any] = {
       0: [
           ("let", "Declaración de variable inmutable"),
           ("mut", "Declaración de variable mutable"),
       ]
   }
   ```
2. **Diccionario estructurado de Snippet para VS Code:**
   ```python
   suggestions: dict[int, Any] = {
       "for_loop": {
           "prefix": "forin",
           "body": [
               "for ${1:item} in ${2:iterable}:",
               "    ${0:pass}",
           ],
           "description": "Bucle for-in iterativo"
       }
   }
   ```
   El compilador de VSIX exporta estas definiciones directamente a `.vscode/snippets/snippets.json`.

---

### 3.8. `suggestions_autocomplete: bool`
Bandera booleana (`True` o `False`).
- Cuando es `True`, indica al generador de extensiones VSIX que procese e incluya las sugerencias de esta regla en el autocompletado global de VS Code.
- Si es `False`, las sugerencias quedan reservadas únicamente para uso interno o análisis contextual.

---

### 3.9. `is_structural: bool`
Controla el tratamiento del nodo en el analizador de sintaxis abstracta (`ASTAnalyzer`).

- **`False` (por defecto - Regla Semántica):**
  Al coincidir la regla, el método `ASTAnalyzer.process_rule()` captura todos los tokens y subnodos resultantes y los empaqueta dentro de una instancia de [`ASTNode`](file:///C:/Users/Kentucky/Desktop/Gram/gram/core/ast/nodes.py) mediante `ASTNode.from_rule_result(rule, result, level)`. La regla aparece formalmente como un nodo del árbol sintáctico.
  
- **`True` (Regla Estructural / De Paso):**
  La regla se procesa y valida sintácticamente, pero **no genera un nodo `ASTNode` intermedio**. En su lugar, el resultado plano del combinador es devuelto directamente al nodo padre.
  
  **¿Cuándo usar `is_structural = True`?**
  1. En separadores, puntuación o delimitadores (`COMMA`, `SEMICOLON`, `PAREN_OPEN`).
  2. En reglas de fin de línea como `ENDLINE` (`NEWLINE`, comentarios o `EOF`).
  3. En envoltorios de indentación (`INDENT_BLOCK`, `BLOCK`).
  4. En agrupadores puramente sintácticos que de otro modo añadirían niveles innecesarios de anidamiento al AST.

```python
class ENDLINE(RuleItem):
    code: int = 2
    name: str = "ENDLINE"
    is_structural: bool = True  # No crea un ASTNode "ENDLINE" contaminando el árbol
    grammar = Seq(
        Opt(MatchToken("COMMENT")),
        Alt(MatchToken("NEWLINE"), MatchToken("EOF")),
    )
```

---

### 3.10. `queries: list[Query] | set[Query] | Query | None`
Define consultas dinámicas de autocompletado contextual e IntelliSense para el editor en tiempo real.

A diferencia de `suggestions` (que genera fragmentos estáticos de texto en tiempo de compilación), `queries` delega la resolución al servidor LSP ([`gram.vsix.lsp`](file:///C:/Users/Kentucky/Desktop/Gram/gram/vsix/lsp.py)) en vivo, permitiendo consultar el sistema de archivos, directorios y recursos mientras el usuario escribe en el editor.

> [!NOTE]
> **Extensibilidad y Futuras Versiones:**
> La arquitectura interna de `Query` está construida sobre controladores desacoplados (`_handler`). En la versión actual, el framework proporciona y valida exclusivamente el método de fábrica oficial `Query.query_roots(...)` (o su alias `query.query_roots(...)`). Si en el futuro se extiende el sistema de queries, se abrirá la API para permitir funciones arbitrarias `query(function)` que reciban el token y consulten tablas de símbolos en memoria, miembros de clases/enums o variables del entorno léxico.

#### Método de fábrica `Query.query_roots(...)`:
```python
from gram.core.combinators import RuleItem, Seq, MatchKeyword, MatchToken, query
from gram.core.lexer.tokens import Token

class INCLUDE_STMT(RuleItem):
    code: int = 1100
    name: str = "INCLUDE_STMT"
    description: str = "Inclusión de cabeceras C o fuentes de librerías"

    queries = {
        query.query_roots(
            path="./",            # Ruta base a inspeccionar
            exts=[".h", ".c"],    # Extensiones de archivo permitidas
            folder=True,          # Permitir navegación interactiva por carpetas
            current_token=True,   # Navegar dentro de subcarpetas según el token actual
        )
    }

    grammar = Seq(
        MatchKeyword("include"),
        MatchToken(Token.STRING),
    )
```

#### Parámetros de `query_roots`:
1. **`path: str = "./"`:**
   Ruta del directorio raíz a inspeccionar. Puede ser `"./"` (carpeta del archivo abierto en el editor o del espacio de trabajo), una ruta relativa fuera del archivo (ej. `"../libs"`, `"source/"`) o una ruta absoluta (ej. `"C:/libs"`).
2. **`exts: Sequence[str] | None = None`:**
   Lista o conjunto de extensiones de archivo permitidas (ej. `[".gst", ".h", ".c"]` o `["gst", "h"]`). Si está vacío o `None`, lista todos los archivos sin filtrar extensión.
3. **`folder: bool = True`:**
   Si es `True`, muestra también los directorios con el icono de carpeta nativo de VS Code (`CompletionItemKind.Folder`, valor `19`). Si es `False`, oculta los directorios y lista exclusivamente archivos.
4. **`current_token: bool = True`:**
   Si es `True`, lee la cadena que el usuario está escribiendo bajo el cursor (incluso entre comillas `"hola/`), desinfecta comillas y barras diagonales, y si contiene `/`, navega automáticamente dentro de esa subcarpeta para listar su contenido en tiempo real.
5. **`trigger_keywords: Sequence[str] | None = None`:**
   Palabras clave opcionales que activan esta consulta. Si no se especifica, `RuleItem.compile()` inspecciona la gramática de la regla (`cls.grammar`) y asocia automáticamente los combinadores `MatchKeyword` encontrados (o el nombre de la regla en minúsculas).

---

### 3.11. `hints: dict[int, Hints]`
Define pistas visuales virtuales (**Inlay Hints**) en tiempo real para el editor. Permite proyectar anotaciones de tipo o nombres de parámetros inferidos de forma "fantasma" (sin alterar físicamente el archivo en disco).

#### Funcionamiento y Materialización:
- **Indexación por Token:** Se indexa por la posición ordinal del token en la regla (`0`, `1`, etc.), de forma análoga a `colors`. El sistema sitúa la pista virtual inmediatamente después del lexema (`token.col + len(token.value)`).
- **Procesador Dinámico (`processor`):** Recibe el token objetivo y debe retornar un `str` con la anotación inferida (ej. `": int"` o `"-> bool"`). Si retorna `""` o `None`, no se proyecta ninguna pista.
- **Limpieza Automática:** Cuando el usuario edita o borra la línea, el servidor LSP actualiza el árbol AST y las pistas no coincidentes desaparecen de forma inmediata del editor.
- **Materialización Nativa en VS Code (`textEdits`):** Cada pista virtual enviada por Gram a VS Code incluye su objeto `textEdits`. Al interactuar o aceptar la acción en el editor, VS Code inserta físicamente el texto en el archivo.
- **Materialización Programática (`put`):** Para scripts CLI, herramientas de formateo o migraciones por lotes, la clase `VirtualHintManager` expone el método `put(id, source_code)` que inserta físicamente el texto en el código fuente.

#### Ejemplo de Declaración en `RuleItem`:
```python
from gram.core.combinators import RuleItem, Seq, MatchKeyword, MatchToken, Hints
from gram.core.lexer.tokens import Token

def infer_var_type(token):
    # Lógica de inferencia de tipo según el contexto del token
    return ": int" if token.value == "x" else None

class VAR_DECL(RuleItem):
    code = 1050
    name = "VAR_DECL"

    hints = {
        1: Hints.new(processor=infer_var_type, kind=1, padding_left=True)
    }

    grammar = Seq(
        MatchKeyword("let"),
        MatchToken(Token.IDENT),
    )
```

#### Métodos de Gestión en `VirtualHintManager`:
Para control programático o manual de pistas virtuales, Gram provee [`VirtualHintManager`](file:///C:/Users/Kentucky/Desktop/Gram/gram/core/hints/manager.py):
- **`insert_virtual(id, line, character, text, kind, ...)`:** Inserta o registra una pista virtual con un ID rastreable (ej. `"line:col"`).
- **`remove_virtual(id)`:** Elimina una pista virtual por su ID.
- **`edit_virtual(id, new_text)`:** Modifica el texto proyectado por una pista existente.
- **`put(id, source_code)`:** Pasa la pista de virtual a física sobre el código fuente real.

---

## 4. Métodos de `RuleItem`

### 4.1. `contain_grammar() -> bool`
```python
@classmethod
def contain_grammar(cls) -> bool:
    return cls.grammar is not None
```
Verifica si la clase tiene un combinador gramatical concreto asignado. Es utilizado por el motor de análisis y por `glang.reinterpreter` para determinar si una regla requiere resolución tardía o ya está lista para ejecución.

---

### 4.2. `compile() -> dict[str, Any]`
Compila todos los metadatos declarativos de la regla en un diccionario estandarizado, listo para ser consumido por herramientas de compilación, generadores de extensiones VSIX y servidores LSP.

```python
@classmethod
def compile(cls) -> dict[str, Any]:
    ...
```

#### Diccionario Retornado:
```python
{
    "name": "MY_RULE",
    "code": 1050,
    "description": "Descripción corta de la regla",
    "docs": "Markdown extendido con documentación...",
    "colors": {0: "#4EC9B0"},
    "color": "#4EC9B0",                     # Color primario resuelto
    "scope": "entity.name.rule.gram.my_rule", # Scope TextMate sanitizado
    "is_structural": False,
    "suggestions": {...},
    "suggestions_autocomplete": True,
    "contain_grammar": True,
    "grammar": <Seq combinator...>,
}
```

#### Sanitización de Scope TextMate:
El método sanitiza automáticamente el nombre de la regla reemplazando caracteres no alfanuméricos por guiones bajos y transformándolo a minúsculas:
```python
clean_name = re.sub(r"[^a-zA-Z0-9_]", "_", r_name).lower()
scope_name = f"entity.name.rule.gram.{clean_name}"
```

---

## 5. Integración con los Subsistemas de Gram

### 5.1. Conexión con `ASTAnalyzer` (`gram.core.ast.analyzer`)
Cuando el parser ejecuta una regla mediante `analyzer.process_rule(rule, grammar)`:

1. Ejecuta el combinador asociado.
2. Si la regla coincide (`result is not None`):
   - Evalúa `rule.is_structural`.
   - Si `is_structural` es `False`, invoca `ASTNode.from_rule_result(rule, result, start_level)`.
   - Si `is_structural` es `True`, retorna el valor crudo directamente.
   
```python
# Lógica interna en ASTAnalyzer.process_rule:
is_structural = getattr(rule, "is_structural", False)
if not is_structural and (
    rule_name in ("ENDLINE", "ENTRY_INDENT_BLOCK", "EXIT_INDENT_BLOCK", "BLOCK", "INDENT_BLOCK")
    or isinstance(grammar, Tokenize)
    or isinstance(result, TokenType)
):
    is_structural = True

if not is_structural:
    return ASTNode.from_rule_result(
        rule=rule,
        result=result,
        level=start_level,
    )
return result
```

### 5.2. Conexión con el Generador VSIX (`gram.vsix`)
- **Extracción (`gram.vsix.extract`):** Escanea los módulos del lenguaje y recolecta todas las clases que heredan de `RuleItem`, invocando su método `compile()`.
- **Sintaxis TextMate (`gram.vsix.generate.generate_syntax_grammar`):** Mapea cada `scope` compilado con los patrones de captura del lenguaje.
- **Tema de Color (`gram.vsix.generate.generate_theme`):** Genera reglas de color para cada `scope` utilizando `r_meta.color`. Si `is_structural` es `True`, configura el estilo como `bold`.
- **Snippets (`gram.vsix.generate.generate_snippets`):** Si `suggestions_autocomplete` es `True`, genera bloques de inserción rápida para cada plantilla en `suggestions`.

### 5.3. Conexión con el Servidor LSP (`gram.vsix.lsp`)
Al solicitar información flotante sobre un elemento de código (`textDocument/hover`):
```python
elif word_under_cursor in self.metadata.rules:
    r = self.metadata.rules[word_under_cursor]
    markdown_doc = (
        f"**Gram Rule:** `{r.name}` (código `{r.code}`)\n\n"
        f"{r.description or r.docs}\n\n"
        f"*Ámbito:* `{r.scope}`"
    )
```

### 5.4. Conexión con el Sistema de Plugins (`gram.plugins.base.PluginBase`)
Los plugins exponen reglas a Gram implementando `get_rules()` y `extend_declarations()`:
```python
class MiPlugin(PluginBase):
    def get_rules(self) -> list[type[RuleItem]]:
        return [MI_NUEVA_REGLA]

    def extend_declarations(self) -> list[type[RuleItem]]:
        return [MI_NUEVA_REGLA]
```

---

## 6. Ejemplos Prácticos de Implementación

### Ejemplo 1: Regla Semántica Completa (Declaración de Variable)
```python
from gram.core.combinators import RuleItem, Seq, MatchKeyword, MatchToken, Opt, Ref
from gram.core.lexer.tokens import Token

class VAR_DECL(RuleItem):
    """Regla para declaración de variables en el lenguaje."""
    code: int = 1010
    name: str = "VAR_DECL"
    description: str = "Declaración de variable con tipo opcional e inicializador"
    docs: str = """
    ### Declaración de Variable
    Sintaxis:
    ```
    let <nombre> [: <tipo>] = <expresion>;
    ```
    Ejemplo:
    ```
    let contador: int = 0;
    ```
    """
    colors: dict[int, str] = {0: "#4EC9B0"}
    suggestions: dict[int, Any] = {
        "let_decl": {
            "prefix": "let",
            "body": [
                "let ${1:variable}: ${2:int} = ${3:valor};"
            ],
            "description": "Declarar variable tipada"
        }
    }
    suggestions_autocomplete: bool = True
    is_structural: bool = False

    grammar = Seq(
        MatchKeyword("let"),
        MatchToken(Token.IDENT),
        Opt(Seq(MatchToken(Token.COLON), MatchToken(Token.IDENT))),
        MatchToken(Token.ASSIGN),
        Ref("EXPRESSION"),
        MatchToken(Token.SEMICOLON),
    )
```

---

### Ejemplo 2: Regla Estructural (Envoltorio de Paréntesis)
```python
from gram.core.combinators import RuleItem, Seq, MatchToken, Ref
from gram.core.lexer.tokens import Token

class PAREN_EXPR(RuleItem):
    """
    Regla estructural que agrupa una expresión entre paréntesis.
    Al tener is_structural = True, no ensucia el árbol AST con nodos intermedios.
    """
    code: int = 1020
    name: str = "PAREN_EXPR"
    description: str = "Expresión delimitada por paréntesis"
    is_structural: bool = True  # <--- Salto en el AST

    grammar = Seq(
        MatchToken(Token.LPAREN),
        Ref("EXPRESSION"),
        MatchToken(Token.RPAREN),
    )
```

---

### Ejemplo 3: Reglas Recursivas con Asignación Posterior
Para definir gramáticas recursivas (como estructuras JSON, bloques o expresiones binarias), se declaran las clases `RuleItem` primero y se asigna su combinador `grammar` posteriormente:

```python
from gram.core.combinators import RuleItem, Seq, Alt, Separator, MatchToken, Ref
from gram.core.lexer.tokens import Token

class JSON_VALUE(RuleItem):
    code = 5001
    name = "JSON_VALUE"

class JSON_ARRAY(RuleItem):
    code = 5002
    name = "JSON_ARRAY"
    colors = {0: "#CE9178"}

# Gramática recursiva
JSON_ARRAY.grammar = Seq(
    MatchToken(Token.LBRACKET),
    Separator(values=[Ref(JSON_VALUE)], sep=Token.COMMA, allow_trailing=True),
    MatchToken(Token.RBRACKET),
)

JSON_VALUE.grammar = Alt(
    MatchToken(Token.STRING),
    MatchToken(Token.NUMBER),
    Ref(JSON_ARRAY),
)
```

---

## 7. Buenas Prácticas y Reglas de Diseño

1. **Gestión de Identificadores (`code`):**
   - Nunca use códigos del `0` al `20` en reglas de usuario o plugins. Estos están reservados para el núcleo de Gram (`PROTECTED_MIN_ID` / `PROTECTED_MAX_ID`).
   - Mantenga un archivo o enumeración centralizada de identificadores en su proyecto para evitar duplicidades accidentales.
2. **Definición de Nombres (`name`):**
   - Utilice siempre mayúsculas continuas con guiones bajos (`UPPER_SNAKE_CASE`) para nombres de reglas.
   - Asegúrese de que el nombre sea consistente con la clase Python asociada.
3. **Uso Adecuado de `is_structural`:**
   - Active `is_structural = True` en signos de puntuación, fin de línea, comentarios y bloques de delimitación donde el valor semántico no requiera una caja `ASTNode`.
   - Déjelo en `False` (predeterminado) en toda construcción semántica relevante para compiladores, transpiladores o generadores de código (declaraciones, expresiones, asignaciones, llamadas).
4. **Referencias Circulares:**
   - Emplee siempre `Ref(NombreRegla)` o `Ref("NOMBRE_REGLA")` en combinadores donde las reglas se invocan mutuamente, evitando errores de inicialización por referencias no resueltas.
5. **Enriquecimiento para IDEs:**
   - Defina siempre `description` y al menos un color en `colors: {0: "#HEX"}`. Esto garantiza que cualquier extensión VSIX o Language Server generado para su lenguaje tenga documentación interactiva inmediata y resaltado visual distintivo.
