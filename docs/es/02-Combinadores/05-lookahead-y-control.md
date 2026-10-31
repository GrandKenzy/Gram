# Combinadores de Lookahead, Control de Flujo y Etiquetado

Estos combinadores realizan aserciones de ancho cero (`Peek`, `Not`), bifurcación condicional (`If`), señalización de control de flujo (`Skip`), etiquetado de posiciones de tokens (`Tag`), fusión de tokens (`Tokenize`) y captura diagnóstica de errores (`ErrorCombinator`).

---

## 1. `Peek` (Lookahead Positivo)

Evalúa `combinator` dentro de un `analyzer.failure_scope()` aislado y siempre restaura el checkpoint en un bloque `finally`, de modo que el cursor nunca avanza.

### Constructor
```python
Peek(combinator: Combinator)
```

### Forma de Retorno y Diagnósticos
- **El hijo coincide (`res is not None`):** Restaura el checkpoint y retorna `[]` (para que los combinadores `Seq` envolventes continúen con éxito sin añadir un nodo al árbol).
- **El hijo falla (`res is None`):** Restaura el checkpoint, reporta `scope.candidate` (o `PositiveLookaheadFailed` si no se preparó un candidato) y retorna `None`.

### Ejemplo
```python
from gram.core.combinators import MatchToken, Peek
from gram.core.lexer import Token

assert_next_is_ident = Peek(MatchToken(Token.IDENT))
```

---

## 2. `Not` (Lookahead Negativo)

Afirma que `combinator` **no** coincide en `parser.pos`. Evalúa `combinator` dentro de un `analyzer.failure_scope()` aislado y siempre restaura el checkpoint.

### Constructor
```python
Not(combinator: Combinator)
```

### Forma de Retorno y Diagnósticos
- **El hijo falla (`res is None`):** Descarta el fallo interno del hijo, restaura el checkpoint y retorna `[]`.
- **El hijo coincide (`res is not None`):** Restaura el checkpoint, reporta `NegativeLookaheadFailed` (`GrammarError`) y retorna `None`.

### Ejemplo
```python
from gram.core.combinators import MatchKeyword, Not

not_return = Not(MatchKeyword("return"))
```

---

## 3. `If` (Bifurcación Condicional)

Evalúa una o más `conditions` especulativamente dentro de `analyzer.failure_scope()` y se bifurca hacia `ok` o `fail`.

### Constructor
```python
If(
    conditions: Sequence[Combinator] | Combinator,
    ok: Sequence[Combinator] | Combinator | None = None,
    fail: Sequence[Combinator] | Combinator | None = None,
    *,
    restore: bool = False,
)
```

- Pasar una `list` o `tuple` para `ok` o `fail` lo envuelve automáticamente en `Seq(*branch)`.
- Pasar una secuencia vacía en `conditions` lanza `EmptyIfConditions` (`GrammarError`) en tiempo de construcción.

### Formas de Retorno
- **Cuando todas las `conditions` tienen éxito:**
  - `restore=False` (por defecto): Mantiene los tokens de la condición consumidos.
    - Si se especifica `ok`: evalúa `ok` y retorna `[*cond_results, ok_res]` (o restaura el checkpoint inicial y retorna `None` si `ok` falla).
    - Si `ok is None`: retorna `cond_results`.
  - `restore=True`: Restaura el checkpoint inicial antes de ejecutar `ok`.
    - Si se especifica `ok`: retorna `analyzer.visitor(self.ok)`.
    - Si `ok is None`: retorna `cond_results`.
- **Cuando cualquier condición falla:** Restaura el checkpoint inicial.
  - Si se especifica `fail`: retorna `analyzer.visitor(self.fail)`.
  - Si `fail is None`: reporta el fallo candidato del ámbito de la condición (o `IfConditionNotMet`) y retorna `None`.

### Ejemplo
```python
from gram.core.combinators import If, MatchKeyword, MatchToken
from gram.core.lexer import Token

branch = If(
    conditions=MatchKeyword("let"),
    ok=MatchToken(Token.IDENT),
    fail=MatchToken(Token.NUMBER),
)
```

---

## 4. `Skip` y Señales de Control de Flujo

`Skip(signal)` lanza `signal()` cuando es visitado. Las señales heredan de `ControlFlowSignal` (`gram.core.combinators.signals`).

### Constructor
```python
Skip(signal: type[ControlFlowSignal])
```

### Referencia de Señales (`gram.core.combinators.signals`)

| Clase de Señal | `FlowKind` | Manejada Por | Rollback / efecto |
| :--- | :--- | :--- | :--- |
| `SkipFlowSignal` | `STOP_SEQUENCE` | `Seq`, `Many`, `Some`, `Separator` | `Seq` retorna los nodos acumulados. Las repeticiones restauran solo un skip sin consumo; después de consumir conservan los tokens y continúan. `Separator` restaura su checkpoint. |
| `BreakFlowSignal` | `STOP_REPETITION` | `Many`, `Some`, `Separator` | Restaura el checkpoint de la iteración/separador actual y termina la repetición. |
| `BacktrackSignal` | `BACKTRACK_ALTERNATIVE` | `Alt` | Descarta la rama actual, restaura el checkpoint de `Alt` e intenta la siguiente. |
| `CutFlowSignal` | `COMMIT_ALTERNATIVE` | `Alt` vía `ASTState.failure_scope` | Transporta `_failure_candidate`, restaura el checkpoint de `Alt` y termina `Alt` sin probar ramas posteriores. |
| `AbortFlowSignal` | `ABORT` | Invocador / nivel superior | Los combinadores estructurales no la recuperan y el análisis termina inmediatamente. |

Todas heredan de `ControlFlowSignal`, pero se mantienen como clases públicas
distintas para conservar el significado de los handlers `except` existentes.
`FlowKind` expone la directiva semántica sin reemplazar esas clases.

### Ejemplo
```python
from gram.core.combinators import Alt, MatchKeyword, MatchToken, Seq, Skip
from gram.core.combinators.signals import BacktrackSignal, CutFlowSignal, SkipFlowSignal
from gram.core.lexer import Token

# Salida anticipada en Seq: retorna [LiteralNumber(1)] y se detiene en pos=1
early_seq = Seq(
    MatchToken(Token.NUMBER),
    Skip(SkipFlowSignal),
    MatchToken(Token.NUMBER),
)

# Forzar a Alt a descartar la rama 1 e intentar la rama 2
alt_backtrack = Alt(
    Seq(MatchKeyword("int"), Skip(BacktrackSignal)),
    Seq(MatchKeyword("int"), MatchToken(Token.IDENT)),
)
```

---

## 5. `Tag`

Asocia, elimina o afirma etiquetas de cadena en el índice del token actual (`parser.pos`) dentro del diccionario seguro ante checkpoints `parser.tk_tags: dict[int, frozenset[str]]`. Nunca consume tokens (`parser.pos` no cambia).

### Constructor y Métodos de Clase
```python
Tag(tag: str, mode: Literal["add", "remove", "exists", "not_exists"] = "add")

Tag.add(tag: str) -> Tag
Tag.remove(tag: str) -> Tag
Tag.exists(tag: str) -> Tag
Tag.not_exists(tag: str) -> Tag
```

### Valor de Retorno y Diagnósticos
- **Éxito:** Retorna el `TokenType` en `parser.pos` sin avanzar `parser.pos`.
- **Fallo / EOF:**
  - Reporta `TagUnexpectedEOF` (`ParserError`) si el flujo está vacío.
  - Reporta `RequiredTagMissing` (`GrammarError`) si `mode == "exists"` y `tag` no está presente en `parser.pos`.
  - Reporta `ForbiddenTagPresent` (`GrammarError`) si `mode == "not_exists"` y `tag` está presente en `parser.pos`.

---

## 6. `Tokenize`

Evalúa una secuencia de combinadores secundarios productores de tokens (`Seq(*combinators)`) y fusiona todos los tokens coincidentes en un único `TokenType` cuyo `.token` es un `CustomToken(name=..., value=combined_value)`.

### Constructor
```python
Tokenize(
    *combinators: Combinator,
    token_name: str = "CustomToken",
    name: str | None = None,
    join_char: str = "",
)
```

- Si se especifica `name`, anula a `token_name`.
- Lanza `EmptyTokenizeCombinators` (`GrammarError`) en tiempo de construcción si se invoca sin combinadores secundarios.

### Valor de Retorno y Diagnósticos
- Cada resultado hijo debe ser un `TokenType`, un objeto con atributo `.token: TokenType` (como `ASTTokenNode`), o una lista/tupla anidada de estos. Si algún hijo produce un objeto que no sea token (como un `ASTRef`), `Tokenize` restaura el checkpoint, reporta `InvalidTokenizeElement` (`GrammarError`) y retorna `None`.
- **Coincidencia:** Retorna un `TokenType` sintetizado en la línea y columna del primer token coincidente, con su `.value` unido por `join_char`.

### Ejemplo
```python
from gram.core.combinators import MatchToken, Tokenize
from gram.core.lexer import Token

decorator_tok = Tokenize(
    MatchToken(Token.AT),
    MatchToken(Token.IDENT),
    name="DECORATOR",
    join_char="",
)
```

---

## 7. `ErrorCombinator`

Extrae y retorna instancias de `Error` registradas previamente desde la primera lista no vacía de errores entre `analyzer._errors`, `parser._errors` o `StackError.__err__`.

### Constructor
```python
ErrorCombinator(length: int = 1)
```

- `length=0`: Extrae todos los errores registrados.
- `length=N` ($N > 0$): Extrae hasta los `N` errores más recientes.

### Forma de Retorno y Diagnósticos
- **Cuando existen errores:** Elimina los errores seleccionados de la lista de errores activa y los retorna como `list[errors.Error]` en orden cronológico inverso (el más reciente primero).
- **Cuando no existen errores:** Reporta `NoErrorsToCatch` (`GrammarError`) y retorna `None`.

> **Nota:** Para registrar errores en `_errors` sin terminar el proceso antes de que `ErrorCombinator` se ejecute, establece `config.ERROR_EXIT_ON_ERROR = False` o registra un hook de error que retorne `ErrorAction.SUPPRESS_RAISE`.

---

## 8. `SameLine` (Restricción de Continuidad de Línea)

Exige que `combinator` inicie en la misma línea que el token consumido inmediatamente anterior (`parser.tokens[parser.pos - 1].line == parser.tokens[parser.pos].line`).

### Constructor
```python
SameLine(combinator: Combinator)
```

### Ejecución y Diagnósticos
- Si `parser.pos == 0`, `SameLine` tiene éxito incondicional (permitiendo el primer token de un archivo).
- Si uno o más tokens de salto de línea `NEWLINE` o saltos de línea separan el token anterior de `parser.pos`, `SameLine` falla de inmediato, restaura el checkpoint, reporta `SameLineViolation` (`GrammarError`) y retorna `None`.
- Totalmente soportado en la compilación AOT en C11 e integrado con el análisis predictivo de primer conjunto (`first_set`).

### Ejemplo
```python
from gram.core.combinators import MatchKeyword, MatchToken, SameLine, Seq
from gram.core.lexer import Token

# Prohíbe saltos de línea entre 'return' y el identificador retornado
return_estricto = Seq(
    MatchKeyword("return"),
    SameLine(MatchToken(Token.IDENT)),
)
```
