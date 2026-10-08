# Árbol de Sintaxis Abstracta y Analizador Semántico (`gram.core.ast`)

El subsistema AST (`gram.core.ast`) constituye la fase final del núcleo sintáctico del Framework Gram. Es responsable de orquestar la ejecución de las reglas gramaticales sobre el flujo de tokens entregado por el Lexer, administrar los niveles jerárquicos de indentación y bloques, supervisar el progreso de los combinadores a través del monitor **`Watcher`**, y construir una representación arbórea completa, tipada y fácilmente serializable: el **`ASTProgram`** y sus nodos **`ASTNode`**.

---

## 1. Arquitectura General del Pipeline AST

```
                      Flujo de Tokens (TokenStream)
                                    │
                                    ▼
                         PARSER (`gram.core.parser`)
                                    │
                        parser.parse(grammar)
                                    │
                                    ▼
                     ASTANALYZER (`gram.core.ast.analyzer`)
                         │                      │
                         ▼                      ▼
                  Reglas Gramaticales        WATCHER (`gram.core.watcher`)
                  (PROGRAM, DECLARATION)     (Pila de combinadores, secuencias
                         │                    y telemetría en tiempo real)
                         ▼
             Construcción Recursiva de Nodos
               ASTNode.from_rule_result()
                         │
                         ▼
            ASTPROGRAM (`gram.core.ast.nodes`)
         ┌──────────────────────────────────────┐
         │ • Sentencias raíz (declarations)     │
         │ • Comentarios extraídos (comments)   │
         │ • Desglose por niveles (levels)      │
         │ • Bloques indentados (blocks)        │
         └──────────────────┬───────────────────┘
                            │
            ┌───────────────┴───────────────┐
            ▼                               ▼
    Reporte Decorado (.txt)        Estructura JSON (.json)
   generate_decorated_tree()       generate_json_tree()
```

### Componentes del Subsistema
- **`gram.core.ast.nodes.ASTNode`**: Nodo representativo de una regla o bloque sintáctico.
- **`gram.core.ast.nodes.ASTProgram`**: Nodo raíz del programa completo analizado.
- **`gram.core.ast.nodes.generate_file_tree`**: Utilidad versátil para volcar árboles a archivos `.txt` o `.json`.
- **`gram.core.ast.analyzer.ASTAnalyzer`**: Orquestador sintáctico y constructor del AST.
- **`gram.core.watcher.Watcher`**: Monitor de ejecución de combinadores y secuencias en tiempo real.
- **`gram.core.watcher.FileWatcher`**: Vigilante de archivos y carpetas con detección de cambios mediante SHA-256 y mtime.
- **`gram.core.watcher.PluginWatcher`**: Vigilante para recarga en caliente (*hot-reload*) de plugins de Gram.

---

## 2. La Clase `ASTNode`

Representa cada nodo individual dentro del árbol sintáctico, asociando la regla gramatical que lo produjo, sus códigos, su nivel de indentación o jerarquía, los tokens consumidos y sus nodos hijos.

### Definición y Atributos

```python
@dataclass
class ASTNode:
    name: str                           # Nombre identificativo de la regla
    rule: Any = None                    # Clase RuleItem de origen
    code: int = 0                       # Código numérico de la regla
    level: int = 0                      # Nivel de indentación / profundidad
    tokens: list[TokenType]             # Tokens consumidos por este nodo
    children: list[ASTNode]             # Nodos hijos anidados
    parent: ASTNode | None = None       # Nodo padre contenedor
    attributes: dict[str, Any]          # Metadatos semánticos adicionales
```

### Propiedades Jerárquicas
- **`is_block`**: `True` si el nodo tiene uno o más hijos.
- **`body`**: Alias para acceder a la lista `children`.
- **`has_children`**: `True` si posee descendientes inmediatos.
- **`child_count`**: Cantidad de nodos hijos directos (`len(children)`).
- **`depth`**: Profundidad genealógica del nodo respecto a la raíz (0 para la raíz).
- **`root`**: Nodo raíz en la cúspide de la jerarquía.
- **`siblings`**: Lista de nodos hermanos pertenecientes al mismo padre.
- **`index_in_parent`**: Posición ordinal dentro de la lista de hijos del padre (-1 si no tiene padre).

### Extracción Semántica de Valores
- **`values`**: Lista de valores literales (`IDENT`, `STRING`, `NUMBER`, `BOOL`, `CHAR`, palabras clave del dominio y `CustomToken`). Omite símbolos estructurales.
- **`value`**: Primer valor semántico o identificador del nodo (o `None`).
- **`identifiers`**: Lista de cadenas correspondientes a identificadores (`Token.IDENT`).
- **`numbers`**: Lista de literales numéricos (`Token.NUMBER`).
- **`strings`**: Lista de cadenas literales (`Token.STRING`).
- **`keywords`**: Lista de palabras reservadas (`Token.KEYWORD`).

### Métodos de Manipulación y Consulta
- **`add_child(child: ASTNode) -> None`**: Enlaza un nodo hijo, asigna `child.parent = self` y ajusta su nivel a `self.level + 1` si su nivel original es menor o igual al del padre.
- **`remove_child(child: ASTNode) -> None`**: Desacopla un nodo hijo y borra la referencia a su padre.
- **`set_level(new_level: int) -> None`**: Actualiza recursivamente el nivel del nodo y de todos sus descendientes.
- **`by_level(level: int) -> list[ASTNode]`**: Retorna todos los nodos descendientes (incluyendo el actual si coincide) que pertenezcan exactamente al nivel dado.
- **`find(rule_name: str) -> list[ASTNode]`**: Búsqueda recursiva de todos los descendientes con nombre de regla igual a `rule_name`.
- **`find_first(rule_name: str) -> ASTNode | None`**: Retorna el primer nodo que coincida con `rule_name`.
- **`walk(order: str = 'pre') -> Iterator[ASTNode]`**: Generador que recorre el subárbol completo en pre-orden (`order="pre"`) o post-orden (`order="post"`).
- **`to_dict() -> dict[str, Any]`**: Serialización recursiva a diccionario estándar de Python.
- **`format() -> str`**: Formateo gráfico de árbol con conectores Unicode (`├──`, `└──`).

### Factoría `from_rule_result`
```python
ASTNode.from_rule_result(rule: Any, result: Any, level: int = 0) -> ASTNode
```
Empaqueta automáticamente el resultado de un combinador (tokens, listas, tuplas, `ItemNode`, `LiteralNode` o subnodos `ASTNode`) en un `ASTNode` estructurado y coherente. `ItemNode` y `LiteralNode` preservan como fragmentos nombrados las listas de tokens que producen `Item` y `Literal`.

---

## 3. La Clase `ASTProgram`

Representa la raíz del programa analizado. Almacena las sentencias de nivel superior (`body`) y la colección de comentarios extraídos del flujo de tokens (`comments`).

### Propiedades y Estadísticas
- **`declarations`**: Alias para `body` (sentencias principales de nivel 0).
- **`comments`**: Lista de tokens `COMMENT` recolectados durante el parsing.
- **`levels() -> dict[int, list[ASTNode]]`**: Agrupa todos los nodos del AST indexados por su nivel de indentación.
- **`blocks() -> list[ASTNode]`**: Colección de todos los nodos del árbol que actúan como bloques (`is_block == True`).
- **`total_nodes`**: Número total de nodos presentes en todo el árbol sintáctico.
- **`max_depth`**: Máximo nivel de profundidad o indentación registrado.
- **`stats`**: Diccionario con métricas globales del programa:
  ```python
  {
      "total_declarations": 2,
      "total_nodes": 7,
      "total_blocks": 1,
      "total_comments": 3,
      "max_depth": 2,
      "levels": [0, 1, 2]
  }
  ```

### Protocolo de Contenedor Python
`ASTProgram` implementa el protocolo de secuencias e iteración nativo:
- **`len(program)`**: Cantidad de declaraciones raíz.
- **`for stmt in program:`**: Iteración directa sobre las sentencias de nivel 0.
- **`program[0]`**: Acceso indexado por posición.
- **`program["FUNC_DEF"]`**: Búsqueda por nombre de regla mediante corchetes.
- **`bool(program)`**: Siempre `True`.

### Exportación y Visualización
- **`dump() -> str`**: Representación textual simple con niveles.
- **`generate_decorated_tree() -> str`**: Reporte técnico completo con encabezado, métricas, árbol con conectores Unicode, desglose por niveles y bloque de comentarios.
- **`generate_json_tree() -> dict[str, Any]`**: Estructura enriquecida en formato JSON con metadatos y resúmenes.
- **`generate_file_tree(output_path: str | Path | None = None) -> str | dict`**: Guarda el árbol en disco según la extensión (`.txt` genera el reporte decorado, `.json` serializa el JSON formateado con sangrías).

---

## 4. El Analizador `ASTAnalyzer`

El `ASTAnalyzer` vincula el `Parser` y el catálogo de combinadores para construir el árbol.

### Ciclo de Ejecución (`process`)
1. **Validación de `PROGRAM`**: Comprueba que la gramática defina la regla raíz `PROGRAM` y que sea de tipo iterativo (`Many` o `Some`).
2. **Validación de `DECLARATION`**: Comprueba que exista la regla `DECLARATION` y que sea de tipo alternativa (`Alt`).
3. **Validación de elementos `Ref`**: Verifica que cada rama en `DECLARATION` sea un combinador de referencia `Ref`.
4. **Bucle de Consumo**:
   - Consume tokens uno a uno a través de `parser.consume()`.
   - Si el token es `COMMENT`, lo archiva en `self.comments` y continúa.
   - Si es `NEWLINE`, `EMPTY_LINE` o `EOF`, lo descarta silenciosamente (`quit_trash`).
   - Si es un token gramatical, ejecuta `match_with_declaration` evaluando `DECLARATION`.
5. **Rastreo de Niveles**:
   - `Token.INDENT`: Incrementa `self.current_level += 1`.
   - `Token.DEDENT`: Decrementa `self.current_level = max(0, self.current_level - 1)`.
6. **Construcción y Retorno**: Ensambla y retorna la instancia final de `ASTProgram`.

---

## 5. El Monitor `Watcher` y Vigilantes de Archivos

Ubicado en `gram.core.watcher`, supervisa la ejecución sintáctica y el sistema de archivos:

### `Watcher`
Monitorea la pila de evaluación en tiempo real:
- **`enter_combinator(combinator, token)` / `exit_combinator()`**: Gestiona la pila de combinadores activos y actualiza `depth`.
- **`enter_sequence(sequence, total_steps)` / `step_sequence(index)` / `exit_sequence()`**: Supervisa el progreso ordinal paso a paso dentro de secuencias (`Seq`).
- **`snapshot() -> dict[str, Any]`**: Instantánea con estado de secuencia, paso, combinador, profundidad y token posicionado.
- **`where_am_i() -> str`**: Mensaje diagnóstico formateado:
  `"[Secuencia: Seq(...) (Paso 2/4)] -> [Combinador: MatchToken(IDENT)] -> [Token: IDENT('foo') en L1:C4]"`
- **`active_path() -> list[str]`**: Ruta de combinadores activos (ej. `['Alt', 'Seq', 'MatchToken']`).
- **`record_error(err)` / `has_errors` / `clear_errors()`**: Registro y consulta de excepciones capturadas.

### `FileWatcher`
Vigilante de archivos y directorios para hot-reload:
- Detección de modificaciones, adiciones y eliminaciones comparando `st_mtime`, `st_size` y `sha256`.
- **`poll_once() -> dict[str, list[Path]]`**: Sondeo puntual manual (`added`, `modified`, `deleted`).
- **`start_async(interval=0.5)` / `stop()`**: Monitoreo en segundo plano mediante un hilo daemon desacoplado.

### `PluginWatcher`
Extensión de `FileWatcher` que detecta la raíz del plugin contenedor (`manifest.json`) ante modificaciones y dispara callbacks de recarga de forma segura y tolerante a fallos.

---

## 6. Ejemplo Completo de Uso

```python
from gram.core.lexer import Token, TokenType, words
from gram.core.parser import Parser
from gram.core.combinators import (
    Seq,
    Alt,
    Ref,
    Many,
    MatchKeyword,
    MatchToken,
    MatchSymbol,
    create_rule,
)
from gram.core.combinators.defaults import PROGRAM, DECLARATION

# 1. Registrar palabras clave del lenguaje
words.add_keyword("def")
words.add_keyword("let")

# 2. Definir flujo de tokens simulado
tokens = [
    TokenType(token=Token.KEYWORD, value="def", line=1, col=0),
    TokenType(token=Token.IDENT, value="saludar", line=1, col=4),
    TokenType(token=Token.LPAREN, value="(", line=1, col=11),
    TokenType(token=Token.RPAREN, value=")", line=1, col=12),
    TokenType(token=Token.COLON, value=":", line=1, col=13),
    TokenType(token=Token.INDENT, value="    ", line=2, col=0),
    TokenType(token=Token.KEYWORD, value="let", line=2, col=4),
    TokenType(token=Token.IDENT, value="mensaje", line=2, col=8),
    TokenType(token=Token.ASSIGN, value="=", line=2, col=16),
    TokenType(token=Token.STRING, value="hola", line=2, col=18),
    TokenType(token=Token.DEDENT, value="", line=3, col=0),
    TokenType(token=Token.EOF, value="<EOF>", line=3, col=0),
]

# 3. Definir reglas gramaticales
LET_STMT = create_rule(
    "LET_STMT",
    101,
    Seq(
        MatchKeyword("let"),
        MatchToken(Token.IDENT),
        MatchSymbol("="),
        MatchToken(Token.STRING),
    ),
)

FUNC_DEF = create_rule(
    "FUNC_DEF",
    102,
    Seq(
        MatchKeyword("def"),
        MatchToken(Token.IDENT),
        MatchToken(Token.LPAREN),
        MatchToken(Token.RPAREN),
        MatchToken(Token.COLON),
        MatchToken(Token.INDENT),
        Ref(LET_STMT),
        MatchToken(Token.DEDENT),
    ),
)

grammar = {
    PROGRAM: Many(Ref(DECLARATION)),
    DECLARATION: Alt(Ref(FUNC_DEF), Ref(LET_STMT)),
    FUNC_DEF: Seq(
        MatchKeyword("def"),
        MatchToken(Token.IDENT),
        MatchToken(Token.LPAREN),
        MatchToken(Token.RPAREN),
        MatchToken(Token.COLON),
        MatchToken(Token.INDENT),
        Ref(LET_STMT),
        MatchToken(Token.DEDENT),
    ),
    LET_STMT: Seq(
        MatchKeyword("let"),
        MatchToken(Token.IDENT),
        MatchSymbol("="),
        MatchToken(Token.STRING),
    ),
}

# 4. Analizar y obtener el ASTProgram
parser = Parser(tokens)
ast_program = parser.parse(grammar)

# 5. Inspeccionar y exportar
print(f"Total sentencias: {len(ast_program)}")
print(f"Bloques detectados: {len(ast_program.blocks())}")
print(f"Nodos totales: {ast_program.total_nodes}")

# Volcar árbol decorado a archivo de texto
ast_program.generate_file_tree("output_ast.txt")
```
