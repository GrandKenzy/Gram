# Combinadores Sintácticos de Gram

Los combinadores sintácticos son las unidades fundamentales del parser de **Gram** (`gram.core.combinators`). Cada combinador hereda de `Combinator` y define cómo se consumen, repiten, bifurcan o transforman en nodos del Árbol de Sintaxis Abstracta (`ASTNode`) los tokens proporcionados por `Parser`.

Los combinadores se integran con:
- **Puntos de Control (`parser.savepoint` / `parser.restore`):** Las ramas fallidas revierten el cursor de tokens (`pos`), el cursor virtual (`vpos`), la profundidad de delimitadores, `parser.storage`, `parser.tk_tags` y las sustituciones en sitio (`parser.replace_token_at`).
- **Ámbitos de Fallo Aislados (`analyzer.failure_scope`):** Las exploraciones especulativas (`Alt`, `Opt`, `Many`, `Some`, `Separator`, `Until`, `If`, `Not`, `Peek`) aíslan los fallos candidatos para que las ramas descartadas no contaminen el diagnóstico final.
- **RayTracing (`analyzer.raytracing`):** Controlado mediante `ASTAnalyzer(..., trace="off" | "basic" | "detailed")`.

---

## Categorías de Combinadores

| Categoría | Combinadores | Propósito |
| :--- | :--- | :--- |
| **[01. Coincidencia](./01-matching.md)** | `MatchToken`, `MatchKeyword`, `MatchGroup`, `MatchSeqSymbol`, `generador_expr` | Consumen un único token por tipo de `Token`, palabra clave, grupo léxico (`WordGroup`) o patrón regex. |
| **[02. Estructurales](./02-estructurales.md)** | `Seq`, `Alt`, `Opt`, `Enclosed` | Secuencias ordenadas (`+`), alternativas priorizadas (`\|`), cláusulas opcionales ($0..1$) y bloques delimitados por paréntesis, corchetes o llaves. |
| **[03. Repetición](./03-repeticion.md)** | `Many`, `Some`, `Until`, `UntilIndent`, `Separator` | Bucles $0..n$ y $1..n$, escaneo de tokens hasta un combinador objetivo o nivel de indentación, y listas delimitadas (`ArrayNode`). |
| **[04. Reglas y Almacenamiento](./04-reglas-y-almacenamiento.md)** | `RuleItem`, `Ref`, `Item`, `Literal`, `Save`, `Load` | Reglas de producción declarativas, referencias a reglas (`ASTRef`), secuencias atómicas (`ItemNode`), literales primitivos (`LiteralNode`) y operaciones en `parser.storage`. |
| **[05. Lookahead y Control](./05-lookahead-y-control.md)** | `Peek`, `Not`, `If`, `Skip`, `Tag`, `Tokenize`, `ErrorCombinator` | Lookahead positivo/negativo de ancho cero, bifurcaciones condicionales, señales de control de flujo, etiquetado de tokens (`parser.tk_tags`), tokens compuestos y captura de errores. |
| **[06. Validación Fluida](./06-validacion-fluida.md)** | `Req` | Validación encadenada y transformaciones en sitio sobre una copia del token antes de la delegación al AST. |
| **[08. Preprocesamiento y expectativas](./08-preprocesamiento-y-expectativas.md)** | `Preprocess`, `Convert`, `Expected` | Validaciones personalizadas, conversiones lógicas de identificadores y aserciones estrictas sobre el flujo. |
| **[07. Expresiones Pratt](./07-expresiones.md)** | `ArithmeticExpr`, `ConditionalExpr`, `DualExpr` | Análisis de expresiones Top-Down Operator Precedence (Pratt) para operadores prefijos unarios (`ASTUnaryOp`) e infijos binarios (`ASTBinaryOp`). |

---

## Contrato de Ejecución Central

Cada combinador hereda de `Combinator` (`gram.core.combinators.base.Combinator`) e implementa el método `parse`:

```python
def parse(self, analyzer: ASTAnalyzer) -> Any:
    ...
```

### Convenciones de Retorno
- **Nodo(s) Coincidentes:** Avanza `parser.pos` tras consumir los tokens y devuelve un `ASTNode`, una `list` de nodos o un `TokenType`.
- **Omisión Limpia (`[]`):** Devuelto por `Opt` (cuando no coincide en su posición inicial), `Many` (cuando coinciden 0 iteraciones), `Peek`, `Not` y `Enclosed(..., allow_empty=True)` vacío. Dentro de `Seq`, un resultado `[]` se considera un paso exitoso sin añadir una lista vacía a la salida de `Seq`.
- **Fallo (`None`):** Restaura el `parser` al punto de control del combinador y registra o prepara un error de diagnóstico.

### Sobrecarga de Operadores en `Combinator`
- `comb_a + comb_b` construye un `Seq(comb_a, comb_b)` aplanado.
- `comb_a | comb_b` construye un `Alt(comb_a, comb_b)` aplanado.

### Modos de Traza (`ASTAnalyzer(..., trace=...)`)
- `trace="off"`: Desactiva los registros y callbacks de traza. Los checkpoints del parser y los diagnósticos de parser/AST siguen funcionando normalmente.
- `trace="basic"` (por defecto): Registra combinadores evaluados (`ignore=False`) y niveles de anidamiento en `raytracing.trace`, nombres de reglas en `raytracing.paths` y ramas en `raytracing.branches`.
- `trace="detailed"`: Registra deliberadamente instrumentación completa: instancias de `TraceRecord` (`combinator`, `depth`, `start`, `end`, `outcome`, `exception_type`) para cada combinador evaluado y retrocesos en `raytracing.backtracks` y `raytracing.furthest`. Es el modo pesado para diseñar parsers y lexers dedicados, y se formatea con `raytracing.detailed()`.

### Auditoría predictiva de alternativas

`Alt(..., audit=True)` activa un plan predictivo estático y cacheado. Solo puede
reordenar ramas exactas, no anulables y sin efectos laterales, priorizando el
consumo garantizado de tokens. La tupla pública `Alt.combinators` conserva el
orden declarado.
Las ramas opacas, recursivas, de ancho cero, ilimitadas o con control de flujo
actúan como barreras y no se reordenan. El comportamiento predeterminado
`audit=False` no cambia. Con `trace="detailed"`, los intentos están disponibles
en `analyzer.raytracing.alternative_records` con índice declarado, índice
planificado, intervalo de cursor y resultado.
