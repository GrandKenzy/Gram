# Combinadores Sintácticos de Gram

Los combinadores sintácticos son los bloques fundamentales del analizador de **Gram** (`gram.core.combinators`). Cada combinador hereda de `Combinator` y define cómo los tokens provenientes del `Parser` se reconocen, repiten, ramifican o transforman en instancias del Árbol de Sintaxis Abstracta (`ASTNode`).

Los combinadores se integran con:
- **Puntos de guardado (`parser.savepoint` / `parser.restore`):** Las ramas fallidas revierten el cursor de tokens, cursor virtual (`vpos`), profundidad de corchetes, `parser.storage`, `parser.tk_tags` y reemplazos de tokens en sitio (`parser.replace_token_at`).
- **Ámbitos aislados de error (`analyzer.failure_scope`):** Pruebas especulativas (`Alt`, `Opt`, `Many`, `Some`, `Separator`, `Until`, `If`, `Not`, `Peek` y expresiones) aíslan errores locales para que ramas descartadas no filtren diagnósticos obsoletos.
- **RayTracing (`analyzer.raytracing`):** Controlado vía `ASTAnalyzer(..., trace="off" | "basic" | "detailed")`.

---

## Categorías de Combinadores

| Categoría | Combinadores | Propósito |
| :--- | :--- | :--- |
| **[01. Coincidencia](./01-matching.md)** | `MatchToken`, `MatchKeyword`, `MatchGroup`, `MatchSeqSymbol`, `generador_expr` | Consumen un único token por tipo de `Token`, palabra clave, grupo léxico (`WordGroup`) o patrón regex. |
| **[02. Estructurales](./02-estructurales.md)** | `Seq`, `Alt`, `Opt`, `Enclosed` | Secuencias ordenadas (`+`), alternativas priorizadas (`\|`), cláusulas opcionales ($0..1$) y bloques delimitados por paréntesis, corchetes o llaves. |
| **[03. Repetición](./03-repeticion.md)** | `Many`, `Some`, `Until`, `UntilIndent`, `Separator`, `CaptureRaw` | Bucles $0..n$ y $1..n$, escaneo de tokens hasta un combinador objetivo o nivel de indentación, listas delimitadas (`ArrayNode`) y bloques en crudo (`RawNode`). |
| **[04. Reglas y Almacenamiento](./04-reglas-y-almacenamiento.md)** | `RuleItem`, `Ref`, `Item`, `Literal`, `Save`, `Load` | Reglas de producción declarativas, referencias a reglas (`ASTRef`), secuencias atómicas (`ItemNode`), literales primitivos (`LiteralNode`) y operaciones en `parser.storage`. |
| **[05. Lookahead y Control](./05-lookahead-y-control.md)** | `Peek`, `Not`, `If`, `Skip`, `Tag`, `Tokenize`, `ErrorCombinator`, `SameLine` | Lookahead de ancho cero, bifurcaciones condicionales, señales de control, etiquetado de tokens, tokens compuestos, captura de errores y continuidad de línea. |
| **[06. Validación Fluida](./06-validacion-fluida.md)** | `Req` | Validación encadenada y transformaciones en sitio sobre una copia del token antes de la delegación al AST. |
| **[08. Preprocesamiento y expectativas](./08-preprocesamiento-y-expectativas.md)** | `Preprocess`, `Convert`, `Expected` | Validaciones personalizadas, conversiones lógicas de identificadores y aserciones estrictas sobre el flujo. |
| **[07. Expresiones Pratt](./07-expresiones.md)** | `ArithmeticExpr`, `ConditionalExpr`, `DualExpr` | Análisis de expresiones Top-Down Operator Precedence (Pratt) para operadores prefijos unarios (`ASTUnaryOp`) e infijos binarios (`ASTBinaryOp`). |

---

## Firmas Semánticas y Compilabilidad AOT (`CombinatorKind`)

Gram proporciona una clasificación formal para sus 32 combinadores nativos en `gram.core.combinators.kinds`:
- **`CombinatorKind`:** Enumeración que identifica el rol formal del combinador (`MATCH_TOKEN`, `MATCH_KEYWORD`, `SEQ`, `ALT`, `MANY`, `EXPR_PRATT`, `CAPTURE_RAW`, etc.).
- **`COMPILABLE_COMBINATOR_KINDS`:** Conjunto estricto y cerrado de combinadores soportados por el generador AOT de parsers en C11.
- **`is_compilable_combinator(comb)`:** Retorna `True` si `comb` posee una semántica declarativa compilable a C (o `False` si requiere callbacks arbitrarios de Python o introspección en runtime).
- Cualquier intento de compilar combinadores no soportados (como `Convert` o combinadores externos no registrados) lanza `GrammarCompilerError` de forma temprana durante la exportación AOT.

---

## Contrato de Ejecución Central

Cada combinador hereda de `Combinator` (`gram.core.combinators.base.Combinator`) e implementa el método `parse`:

```python
def parse(self, analyzer: ASTAnalyzer) -> Any:
    ...
```

### Convenciones de Retorno
- **Nodo(s) Coincidente(s):** Avanza `parser.pos` superando los tokens consumidos y retorna un `ASTNode`, una `list` de nodos o un `TokenType`.
- **Omisión Limpia (`[]`):** Retornado por `Opt` (cuando se omite en su posición inicial), `Many` (cuando coinciden 0 repeticiones), `Peek`, `Not` y bloques vacíos `Enclosed(..., allow_empty=True)`. Dentro de un `Seq`, un retorno `[]` se toma como paso exitoso sin añadir una lista vacía a los resultados de `Seq`.
- **Fallo (`None`):** Restaura el `parser` al checkpoint previo del combinador y reporta o prepara un error de diagnóstico.

### Sobrecarga de Operadores en `Combinator`
- `comb_a + comb_b` construye un `Seq(comb_a, comb_b)` aplanado.
- `comb_a | comb_b` construye un `Alt(comb_a, comb_b)` aplanado.

### Modos de Rastreo (`ASTAnalyzer(..., trace=...)`)
- `trace="off"`: Desactiva el registro de trazas y llamadas a hooks de rastreo. Los checkpoints y diagnósticos del parser/AST se ejecutan con normalidad.
- `trace="basic"` (predeterminado): Registra combinadores evaluados (`ignore=False`) y niveles de anidamiento en `raytracing.trace`, nombres de reglas en `raytracing.paths` y ramas evaluadas en `raytracing.branches`.
- `trace="detailed"`: Registra intencionalmente un `TraceRecord` completo (`combinator`, `depth`, `start`, `end`, `outcome`, `exception_type`, `flow_kind`) para cada combinador evaluado, y sigue las posiciones de retroceso en `raytracing.backtracks` / `raytracing.furthest`. Está pensado para el diseño de analizadores sintácticos dedicados y se formatea con `raytracing.detailed()`.
