# Combinadores Estructurales

Los combinadores estructurales componen combinadores secundarios (hijos) en secuencias ordenadas, alternativas priorizadas, elementos opcionales y bloques delimitados.

---

## 1. `Seq` / `Sequence`

`Seq` (con alias `Sequence`) evalúa los combinadores secundarios en orden lineal. También puedes componer secuencias usando el operador `+` (`comb1 + comb2`).

### Constructor
```python
Seq(*combinators: Combinator)
```

- Lanza `EmptySequence` (`GrammarError`) en tiempo de construcción si se invoca sin argumentos.

### Ejecución y Forma de Retorno
- Guarda un punto de restauración (checkpoint `"SEQ-Analysis"`) antes de evaluar a los hijos.
- Para cada combinador secundario:
  - Si el hijo retorna `None`, `Seq` restaura el checkpoint, prepara/emite `SequenceElementMismatch` (a menos que ya se hubiera preparado un fallo más profundo) y retorna `None`.
  - Si el hijo retorna `[]` (por ejemplo, un `Opt` omitido, un `Many` con 0 coincidencias, `Peek` o `Not`), `Seq` trata el paso como exitoso y **omite** `[]` de la lista de salida.
  - En cualquier otro caso, `Seq` agrega el resultado del hijo a `results`.
- **Señales de Control de Flujo:**
  - `SkipFlowSignal` es capturada por `Seq`: la secuencia se detiene de inmediato y retorna los `results` acumulados hasta el momento como una coincidencia exitosa.
  - `BacktrackSignal`, `BreakFlowSignal`, `CutFlowSignal` y `AbortFlowSignal` **no** son capturadas por `Seq` y se propagan hacia el combinador contenedor (`Alt`, `Many`, `Some`, `Separator`).
- **Valor de Retorno:** `list[Any]` con los resultados de los hijos distintos de `[]` en caso de éxito, o `None` en caso de fallo.

### Ejemplo
```python
from gram.core.combinators import MatchKeyword, MatchToken, Opt, Seq
from gram.core.lexer import Token

# Usando Seq(...) o el operador +:
let_binding = Seq(
    MatchKeyword("let"),
    MatchToken(Token.IDENT),
    Opt(MatchToken(Token.ASSIGN) + MatchToken(Token.NUMBER)),
)
```

---

## 2. `Alt` (Alternativa)

Evalúa las ramas candidatas en orden hasta que la primera rama devuelva un resultado distinto de `None`. También puedes componer alternativas usando el operador `|` (`comb1 | comb2`).

### Constructor
```python
Alt(*combinators: Combinator, ignore: bool = False)
```

- `ignore`: Si es `True`, el `Visitor` no incrementa la profundidad de anidamiento ni registra este contenedor `Alt` en el `RayTracing` (`ASTAnalyzer.is_valid_entrypoint` establece `ignore = True` en el `Alt` raíz del punto de entrada).
- Lanza `EmptyAlternatives` (`GrammarError`) en tiempo de construcción si se invoca sin ramas.

### Ejecución, Señales y Diagnósticos
- Cada rama se evalúa dentro de un `analyzer.failure_scope()` aislado.
- Si una rama retorna `None` (o lanza `BacktrackSignal`), `Alt` restaura el checkpoint, conserva el candidato de fallo más profundo (`best_staged`) entre las ramas rechazadas e intenta con la siguiente rama.
- Si una rama lanza `CutFlowSignal`:
  - `Alt` se compromete con el fallo candidato de esa rama (descartando los candidatos de ramas anteriores), restaura el checkpoint, deja de intentar con las ramas restantes y reporta el error.
- Si todas las ramas fallan, `Alt` reporta `best_staged` (o `NoAlternativeMatched` en la posición inicial si ninguna rama preparó un error específico) y retorna `None`.
- **Valor de Retorno:** El valor de retorno exacto de la primera rama coincidente, o `None`.

### Ejemplo
```python
from gram.core.combinators import Alt, MatchToken
from gram.core.lexer import Token

atom = (
    MatchToken(Token.NUMBER)
    | MatchToken(Token.STRING)
    | MatchToken(Token.IDENT)
)
```

---

## 3. `Opt` (Opcional)

Evalúa un único combinador secundario con cardinalidad $0..1$ dentro de `analyzer.failure_scope()`.

### Constructor
```python
Opt(combinator: Combinator)
```

- Lanza `InvalidOptionalTarget` (`GrammarError`) en tiempo de construcción si `combinator` no es una instancia de `Combinator`.

### Ejecución y Fallos Parciales Profundos
- **Coincidencia:** Retorna el resultado del combinador secundario directamente.
- **Omisión Limpia (0 tokens consumidos):** Si el hijo falla sin avanzar más allá de `checkpoint.pos` (`candidate` es `None` o `candidate[0] <= checkpoint.pos`), `Opt` restaura el checkpoint sin reportar un error y retorna `[]`.
- **Fallo Parcial Profundo (`candidate[0] > checkpoint.pos`):** Si el hijo consumió uno o más tokens antes de fallar dentro de una subregla de múltiples pasos (por ejemplo, coincidiendo con `=` en `Opt(Seq(MatchToken(Token.ASSIGN), MatchToken(Token.NUMBER)))` y fallando por la falta del número), `Opt` restaura el checkpoint, reporta el candidato de fallo profundo y retorna `None`.

### Ejemplo
```python
from gram.core.combinators import MatchToken, Opt, Seq
from gram.core.lexer import Token

optional_initializer = Opt(
    Seq(MatchToken(Token.ASSIGN), MatchToken(Token.NUMBER))
)
```

---

## 4. `Enclosed`

Coincide con un `Token` de apertura, un combinador de contenido interno (`content`) y un `Token` de cierre.

### Constructor
```python
Enclosed(
    open: Token,
    content: Combinator,
    close: Token,
    skip_whitespace: bool = True,
    allow_empty: bool = True,
)
```

- `open` y `close` deben ser miembros del enum `Token`; cualquier otro tipo lanza `InvalidDelimiterType` (`GrammarError`) en tiempo de construcción.
- `skip_whitespace`: Si es `True`, invoca `parser.enter_delimiter()` / `parser.exit_delimiter()` y `parser.skip_whitespace()`, lo que incrementa `parser.bracket_depth` y omite `Token.NEWLINE`, `Token.INDENT` y `Token.DEDENT` dentro de los delimitadores.
- `allow_empty`: Si es `True`, y `close` sigue inmediatamente a `open`, `content` no se evalúa y `Enclosed` retorna `[]`. Si es `False`, delimitadores vacíos (o una coincidencia de `content` que consuma 0 tokens) fallan con `EmptyEnclosedContent`.

### Valor de Retorno y Diagnósticos
- **Coincidencia:** Retorna el resultado de `content` (o `[]` cuando está vacío y `allow_empty=True`). Los tokens `open` y `close` se consumen pero no se incluyen en el valor retornado.
- **Fallo:** Restaura el checkpoint inicial, reporta uno de `UnexpectedEOFBeforeOpenDelimiter`, `OpeningDelimiterMismatch`, `EmptyEnclosedContent`, `EnclosedContentMismatch`, `UnclosedDelimiterEOF` o `ClosingDelimiterMismatch`, y retorna `None`.

### Ejemplo
```python
from gram.core.combinators import Enclosed, Separator
from gram.core.lexer import Token

param_list = Enclosed(
    open=Token.LPAREN,
    content=Separator(values=[Token.IDENT], sep=Token.COMMA),
    close=Token.RPAREN,
    skip_whitespace=True,
    allow_empty=True,
)
```
