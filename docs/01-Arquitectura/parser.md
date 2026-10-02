# Motor del Analizador Sintáctico de Gram (`gram.core.parser`)

El subsistema sintáctico (`gram.core.parser`) proporciona el motor desacoplado de análisis gramatical para el Framework Gram. Está diseñado siguiendo el principio de separación de responsabilidades: el **`Parser`** se enfoca en el consumo y aserción de tokens y la ejecución de reglas, mientras que **`ParseControl`** gestiona los cursores físicos y virtuales, el modo delimitado (*bracket-aware mode*), las instantáneas inmutables (**`Checkpoint`**), las transacciones con *backtracking* atómico y el enrutamiento de telemetría y errores.

---

## 1. Arquitectura General del Parser

```
                  Tokens / TokenStream (del Lexer)
                                │
                                ▼
 ┌─────────────────────────────────────────────────────────────┐
 │                           PARSER                            │
 │  ┌───────────────────────────────────────────────────────┐  │
 │  │ consume(), consume_if(), current(), bracket_context() │  │
 │  └───────────────────────────┬───────────────────────────┘  │
 │                              │ Delega                       │
 │                              ▼                              │
 │  ┌───────────────────────────────────────────────────────┐  │
 │  │                     PARSECONTROL                      │  │
 │  │  • Cursor Físico: pos, advance()                      │  │
 │  │  • Cursor Virtual: virtual_pos, future(), commit()    │  │
 │  │  • Delimitadores: enter_bracket(), _skip_whitespace() │  │
 │  │  • Puntos de Guardado: savepoint(), restore()         │  │
 │  │  • Telemetría y Errores: set_node(), fail()           │  │
 │  └───────────────────────────────────────────────────────┘  │
 └──────────────────────────────┬──────────────────────────────┘
                                │
                                ▼
                     Árbol AST / Combinadores
```

### Módulos del Subsistema
- **`gram.core.parser.core` (`Parser`)**: Clase principal del analizador sintáctico.
- **`gram.core.parser.control` (`ParseControl`)**: Controlador de estado, navegación, cursores y transacciones.
- **`gram.core.parser.checkpoint` (`Checkpoint`)**: Estructura inmutable para capturar y restaurar el estado en backtracking.
- **`gram.core.parser.stack`**: Instancia `StackInfo` dedicada a la telemetría y diagnósticos de parsing.

---

## 2. La Clase `Parser`

El `Parser` proporciona una interfaz fluida para que los combinadores y analizadores gramaticales consuman tokens de forma determinista y segura.

### Constructor
```python
Parser(
    tokens: Sequence[TokenType] | TokenStream | None = None,
    control: ParseControl | None = None,
    node: Node | StackInfo | None = None,
    stack: StackInfo | Node | None = None,
)
```
- **`tokens`**: Secuencia de tokens o instancia de `TokenStream` emitida por el lexer.
- **`control`**: Instancia personalizada de `ParseControl` (si se omite, se crea una automáticamente).
- **`node` / `stack`**: Destino de telemetría y registro de errores.

### Métodos de Consumo Físico
- **`current(node=None) -> TokenType`**: Retorna el token bajo el cursor físico sin consumirlo. Si no quedan tokens, levanta `errors.PARSER_EARLY_EOF`.
- **`consume(expected=None, node=None) -> TokenType`**:
  - Verifica que queden tokens disponibles.
  - Si se proporciona `expected` (`Token` o `str`), comprueba que el token actual coincida. En caso de discrepancia, levanta `errors.PARSER_UNEXPECTED_TOKEN`.
  - Avanza el cursor físico una posición.
  - Si está en modo *bracket-aware*, salta automáticamente tokens de espacio en blanco (`NEWLINE`, `INDENT`, `DEDENT`).
  - Notifica al `watcher` (si está activo) y retorna el token consumido.
- **`consume_if(*expected: Token | str, node=None) -> TokenType | None`**:
  - Si el token actual coincide con alguno de los tipos provistos, lo consume y lo retorna.
  - De lo contrario, retorna `None` sin mover el cursor.
- **`advance(steps=1) -> int`**: Avanza el cursor físico directamente el número de pasos indicado.

---

## 3. Navegación y Lookahead No Destructivo

El parser permite inspeccionar tokens futuros sin consumir el flujo:

```python
# Inspección relativa
parser.peek(0)        # Token actual sin consumir
parser.peek(1)        # Siguiente token sin consumir
parser.peek_token(1)  # Tipo Token del siguiente elemento

# Inspección múltiple
tokens = parser.lookahead(3)  # Lista con los siguientes 3 tokens

# Verificación de coincidencia
if parser.matches(Token.IDENT, Token.KEYWORD):
    ...

# Extracción de subsecuencia
slice_tokens = parser.slice(0, 5)
```

---

## 4. Transacciones y Puntos de Guardado (`Checkpoint`)

Para permitir que reglas alternativas (*Alternative / Choice*) intenten múltiples ramas sintácticas sin corromper el flujo de tokens ante un fallo, el parser implementa puntos de guardado inmutables:

### Instantáneas Manuales
```python
cp = parser.savepoint()
try:
    # Intentar rama sintáctica A
    parser.consume(Token.IDENT)
    parser.consume(Token.ASSIGN)
except Exception:
    # Deshacer y restaurar cursores y delimitadores
    parser.restore(cp)
```

### Transacciones Atómicas
```python
with parser.transaction():
    # Si este bloque lanza cualquier excepción,
    # el parser restaura automáticamente los cursores al estado inicial
    parser.consume(Token.IDENT)
    parser.consume(Token.COLON)
```

---

## 5. Exploración Virtual (Speculative Traversal)

Además del cursor físico real, el parser posee un cursor virtual (`virtual_pos`) que permite explorar rutas gramaticales especulativamente:

- **`future() -> TokenType | None`**: Obtiene el token bajo el cursor virtual y avanza dicho cursor una posición, dejando el cursor físico intacto.
- **`peek_virtual(offset=0) -> TokenType | None`**: Inspecciona tokens relativos a la posición virtual actual.
- **`set_virtual_token(pos) -> int`**: Establece la posición virtual (`-1` para el final, `-2` para sincronizar con el cursor físico).
- **`rollback()`**: Descarta la exploración virtual y regresa `virtual_pos` a la posición del cursor físico.
- **`commit() -> list[TokenType]`**: Sincroniza el cursor físico con el virtual, consumiendo físicamente todos los tokens explorados en el intervalo.

---

## 6. Modo Delimitado (*Bracket-Aware Mode*)

En lenguajes estructurados por bloques (estilo Python/Gram), los saltos de línea e indentaciones son significativos. Sin embargo, dentro de delimitadores como paréntesis `()`, corchetes `[]` o llaves `{}`, los saltos de línea no deben romper la expresión (*implicit line joining*).

El parser implementa este comportamiento de forma nativa:
- **`enter_bracket()`**: Incrementa la profundidad de delimitadores abiertos.
- **`exit_bracket()`**: Decrementa la profundidad de delimitadores abiertos.
- **`_skip_whitespace()`**: Se ejecuta tras cada `consume()`. Mientras `bracket_depth > 0`, descarta automáticamente `Token.NEWLINE`, `Token.INDENT` y `Token.DEDENT`.
- **`bracket_context()`**: Gestor de contexto seguro:

```python
parser.consume(Token.LPAREN)
with parser.bracket_context():
    # NEWLINE, INDENT y DEDENT se omiten automáticamente entre argumentos
    parser.consume(Token.IDENT)
    parser.consume(Token.COMMA)
    parser.consume(Token.IDENT)
parser.consume(Token.RPAREN)
```

---

## 7. Recuperación ante Errores y Sincronización

- **`quit(tok: Token) -> int`**: Elimina del flujo todos los tokens del tipo indicado (por ejemplo comentarios residuales) y ajusta los cursores.
- **`synchronize(sync_tokens=None) -> list[TokenType]`**: Descarta tokens hasta alcanzar un punto de sincronización seguro (por defecto `NEWLINE`, `DEDENT` o `EOF`), permitiendo continuar el análisis tras detectar un error de sintaxis en una sentencia.

---

## 8. Diagnósticos y Errores OSGDC

El parser utiliza las excepciones estructuradas del subsistema de errores de Gram:

| Código OSGDC | Nombre Canónico | Excepción | Descripción |
| :--- | :--- | :--- | :--- |
| `S-12411` | `Gram.Parser.UnexpectedToken` | `ParserError` | Se encontró un token diferente al esperado por la regla gramatical. |
| `S-12412` | `Gram.Parser.EarlyEOF` | `ParserError` | El flujo de entrada terminó prematuramente al intentar consumir un token. |
| `S-12413` | `Gram.Parser.NotStarted` | `ParserError` | El análisis sintáctico fue invocado sin un estado válido. |

---

## 9. Ejemplo de Integración Completa

```python
from gram.core.lexer import Lexer, add_keyword, Token
from gram.core.parser import Parser

# 1. Configurar keywords y lexer
add_keyword("let")
lexer = Lexer("let x = 42\nlet y = 100")
tokens = lexer.process()

# 2. Inicializar Parser
parser = Parser(tokens)

# 3. Consumir primera sentencia: let x = 42
parser.consume("let")                 # Valida Token.KEYWORD 'let'
nombre = parser.consume(Token.IDENT)  # 'x'
parser.consume("=")                   # Token.ASSIGN
valor = parser.consume(Token.NUMBER)  # 42

print(f"Declarada variable {nombre.value} con valor {valor.value}")
```
