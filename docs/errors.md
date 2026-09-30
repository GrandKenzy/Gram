# Catálogo Centralizado de Errores del Framework Gram (`gram.errors`)

El catálogo oficial de errores `gram.errors` centraliza todas las instancias formales de `CodeError` bajo el estándar **OSGDC** de 5 dimensiones. Este módulo garantiza que ningún componente lógico del framework ni extensión externa instancie errores con códigos arbitrarios o cadenas mágicas dispersas, asegurando consistencia, trazabilidad e inspección estática en todo el compilador.

---

## 1. Estándar Formal OSGDC

Cada error en Gram está tipado y codificado mediante una tupla o cadena de 5 dígitos normalizados:

$$\text{Código OSGDC} = [O, S, G, D, C]$$

Donde cada posición representa un aspecto fundamental del fallo:

### 1.1 $[O]$ — Origen (Origin)
Identifica la procedencia del código que detectó o generó la condición de error.

| Valor | Constante | Significado |
| :---: | :--- | :--- |
| `0` | `UNKNOWN_ORIGIN` | Procedencia desconocida o no rastreable. |
| `1` | `NATIVE_ERROR` | Generado por componentes internos del núcleo de Gram. |
| `2` | `PLUGIN_ERROR` | Generado dentro de la lógica o manifiesto de un plugin. |

---

### 1.2 $[S]$ — Alcance (Scope)
Determina el subsistema o etapa del pipeline de compilación donde se manifestó el error.

| Valor | Constante | Subsistema |
| :---: | :--- | :--- |
| `0` | `UNKNOWN_SCOPE` | Ámbito no clasificado o genérico del sistema. |
| `1` | `LEXER_ERROR` | Analizador Léxico (tokenización, caracteres no reconocidos, indentación). |
| `2` | `PARSER_ERROR` | Motor del Parser (tokens inesperados, fin prematuro de flujo). |
| `3` | `GRAMMAR_ERROR` | Definición de Reglas, Combinadores y construcción de nodos AST. |
| `4` | `SEMANTIC_ERROR` | Análisis semántico (compatibilidad de tipos, alcance de variables, símbolos). |
| `5` | `COMPILATION_ERROR` | Compilación final, inclusión de módulos y especificaciones DSL GramLang. |

---

### 1.3 $[G]$ — Gravedad (Gravity)
Clasifica el impacto funcional del error sobre el flujo del proceso.

| Valor | Constante | Significado |
| :---: | :--- | :--- |
| `0` | `MINOR` | Advertencia o fallo menor; no detiene la ejecución ni el análisis. |
| `1` | `IMPLEMENTATION_ERROR` | Intento de invocar una característica o combinador no disponible aún. |
| `2` | `OBSOLETE_ERROR` | Uso de una sintaxis, regla o componente marcado como obsoleto. |
| `3` | `INTERNAL` | Estado inconsistente dentro de la lógica interna del compilador/framework. |
| `4` | `FATAL` | Error crítico que aborta inmediatamente el análisis sintáctico de la rama. |

---

### 1.4 $[D]$ — Documentación (Documentation)
Indica el nivel de documentación técnica y soporte formal del error.

| Valor | Constante | Nivel de Documentación |
| :---: | :--- | :--- |
| `0` | `DOCUMENTED` | Registrado formalmente en el catálogo con descripción estándar. |
| `1` | `DOCUMENTED_AND_TRACEABLE` | Documentado en detalle con causas probables, traza y pasos de reparación. |
| `2` | `NOT_DOCUMENTED` | Error ad-hoc sin especificación técnica oficial. |

---

### 1.5 $[C]$ — Condición y Usabilidad (Condition)
Describe el estado del artefacto resultante y la acción correctiva esperada.

| Valor | Constante | Estado y Reparabilidad |
| :---: | :--- | :--- |
| `0` | `USABLE` | El resultado es operable; el flujo puede continuar normalmente. |
| `1` | `REQUIRES_REPAIR` | El código fuente analizado contiene un defecto que debe ser reparado. |
| `2` | `SHOULD_REPAIR` | Se recomienda encarecidamente reparar el código para evitar inconsistencias futuras. |

---

## 2. Formato Canónico y Validación

Cada instancia de `CodeError` ensambla una cadena canónica con el siguiente formato:

$$\text{Tipo}-\text{Código de 5 dígitos} \cdot \text{NombreCualificado}$$

Por ejemplo:
- `S-11010 · Gram.Lexer.EmptyKeywords`
- `S-11411 · Gram.Lexer.UnexpectedCharacter`
- `S-13102 · Gram.Combinator.NotImplemented`
- `S-23411 · Gram.Plugin.ManifestNotFound`

El prefijo define la conformidad con los límites de grupos establecidos por `set_map_codes`:
- **`S-` (Standard / Seguro)**: Todos los dígitos respetan los rangos válidos configurados (`origin=[2], scope=[5], gravity=[4], documentation=[2], condition=[2]`).
- **`U-` (Unstandard / No Seguro)**: Algún dígito rebasa el límite permitido para su grupo.

---

## 3. Catálogo Completo de Errores

### 3.1 Analizador Léxico (Scope: `LEXER_ERROR = 1`)

| Constante | Código OSGDC | Nombre Canónico | Gravedad | Condición | Descripción |
| :--- | :---: | :--- | :---: | :---: | :--- |
| `EMPTY_KEYWORDS` | `11010` | `Gram.Lexer.EmptyKeywords` | `MINOR` | `USABLE` | El lexer se inició sin palabras clave registradas. |
| `KEYWORD_ALREADY_EXISTS` | `11010` | `Gram.Lexer.KeywordAlreadyExists` | `MINOR` | `USABLE` | La palabra clave ya existe en la tabla de símbolos léxicos. |
| `KEYWORD_NOT_FOUND` | `11010` | `Gram.Lexer.KeywordNotFound` | `MINOR` | `USABLE` | Consulta de una palabra clave inexistente en el catálogo. |
| `GROUP_NOT_FOUND` | `11010` | `Gram.Lexer.GroupNotFound` | `MINOR` | `USABLE` | Búsqueda o referencia a un grupo léxico que no existe. |
| `KEYWORD_INVALID_NAME` | `11010` | `Gram.Lexer.InvalidKeywordName` | `MINOR` | `USABLE` | Identificador de palabra clave contiene sintaxis no permitida. |
| `LEXER_UNEXPECTED_CHARACTER` | `11411` | `Gram.Lexer.UnexpectedCharacter` | `FATAL` | `REQUIRES_REPAIR` | Carácter ilegal no soportado por ningún visitor léxico. |
| `LEXER_UNCLOSED_STRING` | `11411` | `Gram.Lexer.UnclosedString` | `FATAL` | `REQUIRES_REPAIR` | Literal de texto sin comilla de cierre antes de fin de línea o EOF. |
| `LEXER_INDENTATION_MISMATCH` | `11411` | `Gram.Lexer.IndentationMismatch` | `FATAL` | `REQUIRES_REPAIR` | Descuadre en los niveles de indentación de la pila de bloques. |
| `LEXER_INVALID_NUMBER` | `11411` | `Gram.Lexer.InvalidNumber` | `FATAL` | `REQUIRES_REPAIR` | Formato numérico incorrecto (múltiples puntos, base errónea). |
| `WORDGROUP_ALREADY_EXISTS` | `11010` | `Gram.Lexer.WordGroupAlreadyExists` | `MINOR` | `USABLE` | Intento de registrar un grupo de palabras ya existente. |
| `WORDGROUP_NOT_FOUND` | `11010` | `Gram.Lexer.WordGroupNotFound` | `MINOR` | `USABLE` | Referencia a un grupo léxico de palabras inexistente. |
| `WORDGROUP_KEYWORD_NOT_REGISTERED` | `11010` | `Gram.Lexer.KeywordNotRegistered` | `MINOR` | `USABLE` | Palabra clave asociada a un grupo sin haber sido registrada. |

---

### 3.2 Motor del Parser (Scope: `PARSER_ERROR = 2`)

| Constante | Código OSGDC | Nombre Canónico | Gravedad | Condición | Descripción |
| :--- | :---: | :--- | :---: | :---: | :--- |
| `PARSER_UNEXPECTED_TOKEN` | `12411` | `Gram.Parser.UnexpectedToken` | `FATAL` | `REQUIRES_REPAIR` | Token no coincide con ninguna alternativa gramatical válida. |
| `PARSER_EARLY_EOF` | `12411` | `Gram.Parser.EarlyEOF` | `FATAL` | `REQUIRES_REPAIR` | Fin prematuro del flujo de tokens durante una regla obligatoria. |
| `PARSER_NOT_STARTED` | `12311` | `Gram.Parser.NotStarted` | `INTERNAL` | `REQUIRES_REPAIR` | Intento de procesar tokens en un parser no inicializado. |

---

### 3.3 Reglas, Combinadores y AST (Scope: `GRAMMAR_ERROR = 3`)

| Constante | Código OSGDC | Nombre Canónico | Gravedad | Condición | Descripción |
| :--- | :---: | :--- | :---: | :---: | :--- |
| `ANY_NOT_IMPLEMENTED` | `13102` | `Gram.Combinator.NotImplemented` | `IMPLEMENTATION_ERROR` | `SHOULD_REPAIR` | Combinador `Any` o función aún no implementada. |
| `COMBINATOR_FAILED` | `13010` | `Gram.Combinator.Failed` | `MINOR` | `USABLE` | Fallo recuperable de coincidencia en un combinador. |
| `TOKENIZE_EMPTY_COMBINATORS` | `13411` | `Gram.Combinator.TokenizeEmpty` | `FATAL` | `REQUIRES_REPAIR` | Creación de regla `Tokenize` sin combinadores hijos. |
| `RULE_NOT_FOUND` | `13411` | `Gram.Grammar.RuleNotFound` | `FATAL` | `REQUIRES_REPAIR` | Referencia (`Ref`) a una regla gramatical no registrada. |
| `DUPLICATE_RULE` | `13411` | `Gram.Grammar.DuplicateRule` | `FATAL` | `REQUIRES_REPAIR` | Definición repetida del mismo ID o nombre de regla. |
| `RULE_PROTECTED_ID` | `13411` | `Gram.Grammar.ProtectedRuleId` | `FATAL` | `REQUIRES_REPAIR` | Intento de sobrescribir una regla reservada del núcleo (0-20). |
| `PROGRAM_RULE_NOT_FOUND` | `13411` | `Gram.AST.ProgramRuleNotFound` | `FATAL` | `REQUIRES_REPAIR` | Regla raíz `PROGRAM` no encontrada para construir el AST. |
| `PROGRAM_INVALID_COMBINATOR` | `13010` | `Gram.AST.ProgramInvalidCombinator` | `MINOR` | `USABLE` | La regla `PROGRAM` tiene una estructura combinatoria irregular. |
| `DECLARATION_RULE_NOT_FOUND` | `13411` | `Gram.AST.DeclarationRuleNotFound` | `FATAL` | `REQUIRES_REPAIR` | Regla `DECLARATION` requerida no hallada en la gramática. |
| `DECLARATOR_INVALID_TYPE` | `13411` | `Gram.AST.DeclaratorInvalidType` | `FATAL` | `REQUIRES_REPAIR` | Tipo de nodo declarador inválido en la estructura del AST. |
| `DECLARATOR_INVALID_ELEMENT` | `13411` | `Gram.AST.DeclaratorInvalidElement` | `FATAL` | `REQUIRES_REPAIR` | Elemento hijo ilegal dentro de un declarador del AST. |
| `COMBINATOR_UNSUPPORTED` | `13411` | `Gram.Combinator.Unsupported` | `FATAL` | `REQUIRES_REPAIR` | Operación combinatoria no soportada por el motor de análisis. |

---

### 3.4 Análisis Semántico (Scope: `SEMANTIC_ERROR = 4`)

| Constante | Código OSGDC | Nombre Canónico | Gravedad | Condición | Descripción |
| :--- | :---: | :--- | :---: | :---: | :--- |
| `SEMANTIC_TYPE_MISMATCH` | `14411` | `Gram.Semantic.TypeMismatch` | `FATAL` | `REQUIRES_REPAIR` | Incompatibilidad de tipos en expresiones o asignaciones. |
| `SEMANTIC_UNDEFINED_SYMBOL` | `14411` | `Gram.Semantic.UndefinedSymbol` | `FATAL` | `REQUIRES_REPAIR` | Referencia a una variable o símbolo no declarado en el ámbito. |
| `SEMANTIC_DUPLICATE_SYMBOL` | `14411` | `Gram.Semantic.DuplicateSymbol` | `FATAL` | `REQUIRES_REPAIR` | Redeclaración ilegal de un identificador en el mismo ámbito. |
| `SEMANTIC_INVALID_OPERATION` | `14411` | `Gram.Semantic.InvalidOperation` | `FATAL` | `REQUIRES_REPAIR` | Operación no definida o inválida entre los tipos dados. |
| `SEMANTIC_SCOPE_VIOLATION` | `14411` | `Gram.Semantic.ScopeViolation` | `FATAL` | `REQUIRES_REPAIR` | Acceso a un símbolo fuera de sus límites de visibilidad. |
| `SEMANTIC_IMMUTABILITY_VIOLATION` | `14411` | `Gram.Semantic.ImmutabilityViolation` | `FATAL` | `REQUIRES_REPAIR` | Intento de reasignar o mutar un símbolo o constante inmutable. |

---

### 3.5 DSL y Compilación (Scope: `COMPILATION_ERROR = 5`)

| Constante | Código OSGDC | Nombre Canónico | Gravedad | Condición | Descripción |
| :--- | :---: | :--- | :---: | :---: | :--- |
| `DSL_SYNTAX_ERROR` | `15411` | `Gram.DSL.SyntaxError` | `FATAL` | `REQUIRES_REPAIR` | Discrepancia sintáctica en la especificación del lenguaje GramLang. |
| `DSL_INCLUDE_NOT_FOUND` | `15411` | `Gram.DSL.IncludeNotFound` | `FATAL` | `REQUIRES_REPAIR` | Archivo o módulo referenciado en `include` no encontrado. |
| `GLANG_INCLUDE_PLUGIN_NOT_LOADED` | `15411` | `Gram.DSL.IncludePluginNotLoaded` | `FATAL` | `REQUIRES_REPAIR` | Inclusión de reglas de un plugin no cargado en el entorno. |
| `GLANG_IMMUTABILITY_VIOLATION` | `15411` | `Gram.DSL.ImmutabilityViolation` | `FATAL` | `REQUIRES_REPAIR` | Modificación ilegal de reglas inmutables de GramLang. |

---

### 3.6 Plugins y Manifiestos (Origin: `PLUGIN_ERROR = 2`, Scope: `GRAMMAR_ERROR = 3`)

| Constante | Código OSGDC | Nombre Canónico | Gravedad | Condición | Descripción |
| :--- | :---: | :--- | :---: | :---: | :--- |
| `PLUGIN_MANIFEST_NOT_FOUND` | `23411` | `Gram.Plugin.ManifestNotFound` | `FATAL` | `REQUIRES_REPAIR` | Archivo `manifest.json` faltante en la raíz del plugin. |
| `PLUGIN_MANIFEST_INVALID` | `23411` | `Gram.Plugin.ManifestInvalid` | `FATAL` | `REQUIRES_REPAIR` | JSON malformado o campos obligatorios faltantes en el manifiesto. |
| `PLUGIN_FOLDER_MISMATCH` | `23411` | `Gram.Plugin.FolderMismatch` | `FATAL` | `REQUIRES_REPAIR` | El nombre del directorio no coincide con `name` en el manifiesto. |
| `PLUGIN_INCOMPATIBLE_GRAM_VERSION` | `23411` | `Gram.Plugin.IncompatibleGramVersion` | `FATAL` | `REQUIRES_REPAIR` | La versión de Gram no cumple la restricción `gram_version`. |
| `PLUGIN_VENV_DISALLOWED` | `23411` | `Gram.Plugin.VenvDisallowed` | `FATAL` | `REQUIRES_REPAIR` | Intento de instalar paquetes en el intérprete global sin un venv. |
| `PLUGIN_DEPENDENCY_NOT_FOUND` | `23411` | `Gram.Plugin.DependencyNotFound` | `FATAL` | `REQUIRES_REPAIR` | Dependencia requerida por el plugin no hallada en el sistema. |
| `PLUGIN_DEPENDENCY_VERSION_MISMATCH` | `23411` | `Gram.Plugin.DependencyVersionMismatch` | `FATAL` | `REQUIRES_REPAIR` | Versión incompatible de una dependencia instalada. |
| `PLUGIN_CAPABILITY_MISSING` | `23411` | `Gram.Plugin.CapabilityMissing` | `FATAL` | `REQUIRES_REPAIR` | El plugin intenta una acción sin declarar la capacidad requerida. |
| `PLUGIN_MAIN_NOT_FOUND` | `23411` | `Gram.Plugin.MainNotFound` | `FATAL` | `REQUIRES_REPAIR` | Archivo de punto de entrada `main.py` no existe. |
| `PLUGIN_LOADED_ERROR` | `23411` | `Gram.Plugin.LoadedError` | `FATAL` | `REQUIRES_REPAIR` | Error inesperado durante la carga/importación del plugin. |
| `PLUGIN_PROCESSED_ERROR` | `23411` | `Gram.Plugin.ProcessedError` | `FATAL` | `REQUIRES_REPAIR` | Falla durante el ciclo de procesamiento de reglas del plugin. |
| `PLUGIN_CONFIG_MUTATION_DENIED` | `23411` | `Gram.Plugin.ConfigMutationDenied` | `FATAL` | `REQUIRES_REPAIR` | Intento del plugin de alterar configuraciones protegidas de Gram. |
| `PLUGIN_CONFIG_REQUIREMENT_FAILED` | `23411` | `Gram.Plugin.ConfigRequirementFailed` | `FATAL` | `REQUIRES_REPAIR` | La configuración global actual no satisface `required_config`. |
| `PLUGIN_DUPLICATE_FOUND` | `23010` | `Gram.Plugin.DuplicateFound` | `MINOR` | `USABLE` | Plugin duplicado detectado durante el descubrimiento (ignorado). |
| `PLUGIN_VERSION_MISMATCH_USE_INSTALL` | `23411` | `Gram.Plugin.VersionMismatchUseInstall` | `FATAL` | `REQUIRES_REPAIR` | Incompatibilidad que requiere reinstalación mediante CLI. |
| `PLUGIN_PROTECTED_VIOLATION` | `23411` | `Gram.Plugin.ProtectedViolation` | `FATAL` | `REQUIRES_REPAIR` | Intento de alterar o desinstalar un plugin protegido del sistema. |
| `PLUGIN_SYNTAX_ERROR` | `23411` | `Gram.Plugin.SyntaxError` | `FATAL` | `REQUIRES_REPAIR` | Error de sintaxis en el código fuente provisto por el plugin. |
| `PLUGIN_DUPLICATE_DEPENDENCY` | `23411` | `Gram.Plugin.DuplicateDependency` | `FATAL` | `REQUIRES_REPAIR` | Dependencias redundantes declaradas en el manifiesto. |
| `PLUGIN_REQUIREMENT_FILE_MISSING` | `23411` | `Gram.Plugin.RequirementFileMissing` | `FATAL` | `REQUIRES_REPAIR` | Archivo `requirements.txt` declarado pero ausente en el plugin. |
| `PLUGIN_VALIDATION_FAILED` | `23411` | `Gram.Plugin.ValidationFailed` | `FATAL` | `REQUIRES_REPAIR` | Fallo general de validación de integridad o seguridad. |
| `PLUGIN_NOT_FOUND` | `23411` | `Gram.Plugin.NotFound` | `FATAL` | `REQUIRES_REPAIR` | Plugin solicitado no localizado en los directorios de búsqueda. |

---

### 3.7 Errores de Sistema / Fallback (Scope: `UNKNOWN_SCOPE = 0`)

| Constante | Código OSGDC | Nombre Canónico | Gravedad | Condición | Descripción |
| :--- | :---: | :--- | :---: | :---: | :--- |
| `UNKNOWN_ERROR` | `00020` | `Gram.System.UnknownError` | `MINOR` | `USABLE` | Fallo genérico no especificado o condición desconocida. |

---

## 4. Guía de Uso en el Código

### 4.1 Lanzamiento Estructurado de Excepciones

Para lanzar un error visual estructurado en cualquier fase del compilador, se utiliza la clase base `Error` de `gram.utilities.error`:

```python
from gram.utilities.error import Error
from gram import errors

# Emisión de error fatal en la fase léxica
err = Error(
    "Carácter no reconocido",
    errors.LEXER_UNEXPECTED_CHARACTER,
    "El carácter '@' en la línea 12, columna 4 no corresponde a ningún operador ni identificador.",
    "Sugerencia: Encierre el carácter entre comillas si pretendía definir una cadena de texto."
)

# Imprimir formato visual en consola y levantar la excepción:
err.raise_error(exit=True)
```

### 4.2 Registro en la Pila Global `StackError`

Todos los errores emitidos pueden registrarse en `StackError` para inspección histórica o volcado a disco (`log/error.log`):

```python
from gram.utilities.error import StackError, Error
from gram import errors

err = Error("Regla no encontrada", errors.RULE_NOT_FOUND, "No existe la regla 'expr'.")
StackError.add(err)

print(f"Errores acumulados: {StackError.count()}")
print(f"Último error: {StackError.last()}")
StackError.write()  # Vuelca a log/error.log
```

---

## 5. API de Consulta del Catálogo

El módulo `gram.errors` incluye funciones utilitarias optimizadas para buscar y filtrar códigos:

### `all_errors() -> list[CodeError]`
Retorna todas las instancias oficiales de `CodeError` definidas en el catálogo.

```python
from gram import errors

total = errors.all_errors()
print(f"Total de errores registrados: {len(total)}")
```

### `get_error_by_code(code) -> CodeError | None`
Busca un error por entero (`11010`), tupla (`(1, 1, 0, 1, 0)`), string (`"11010"` o `"S-11010"`) o instancia:

```python
from gram import errors

err1 = errors.get_error_by_code(11411)
print(err1.name)  # Gram.Lexer.UnexpectedCharacter

err2 = errors.get_error_by_code("S-23411")
print(err2.name)  # Gram.Plugin.ManifestNotFound
```

### `get_error_by_name(name: str) -> CodeError | None`
Busca por nombre canónico completo o por sufijo descriptivo (coincidencia insensible a mayúsculas):

```python
from gram import errors

err = errors.get_error_by_name("EarlyEOF")
print(err.code_string)  # 12411
```

### `get_errors_by_scope(scope) -> list[CodeError]`
Filtra errores por constante de scope (`LEXER_ERROR`), cadena (`"lexer"`) o índice numérico (`1`):

```python
from gram import errors

lexer_errs = errors.get_errors_by_scope(errors.LEXER_ERROR)
print(f"Errores léxicos: {len(lexer_errs)}")
```

### `get_errors_by_origin(origin) -> list[CodeError]`
Filtra errores por origen (`NATIVE_ERROR`, `PLUGIN_ERROR` o `"native"`, `"plugin"`):

```python
from gram import errors

plugin_errs = errors.get_errors_by_origin(errors.PLUGIN_ERROR)
print(f"Errores de plugins: {len(plugin_errs)}")
```
