# VSIX y Herramientas de Editor (Beta)

> [!WARNING]
> **Aviso de Estado Beta:**  
> El paquete `gram.vsix` (extracción de esquemas, coloreado de tokens, empaquetado de `.vsix` y servidor de lenguaje JSON-RPC integrado) se encuentra actualmente en fase **Beta**. Los flujos de trabajo principales son completamente funcionales y con cero dependencias externas, pero las heurísticas de mapeo de reglas a LSP y las opciones de generación del manifiesto están bajo desarrollo activo.

`gram.vsix` te permite adjuntar metadatos declarativos de editor directamente a tus clases `RuleItem` y definiciones de `Keyword`, y utilizar esos metadatos para:
1. Renderizar previsualizaciones con resaltado de sintaxis ANSI TrueColor de 24 bits en la terminal (`ASTColorResolver`).
2. Extraer un esquema canónico del lenguaje serializable en JSON (`VSIXAnalyzer`).
3. Generar los archivos completos de una extensión de Visual Studio Code (`package.json`, `language-configuration.json`, TextMate `.tmLanguage.json`, `snippets.json` y cliente LSP en `extension.js`) mediante `VSIXGenerator`.
4. Empaquetar un archivo `.vsix` sin Node.js e instalarlo en VS Code (`pack_vsix`, `install_extension`, `up`).

---

## 1. Mapas Declarativos de Editor en `RuleItem`

Cualquier `RuleItem` con **`nodeable = True`** puede definir cinco atributos de diccionario opcionales:

```python
from gram import combinators as cmb
from gram import lexer

class ImportDecl(cmb.RuleItem):
    name = "IMPORT_DECL"
    nodeable = True  # Requerido para mapas de ASTColorResolver y VSIXAnalyzer
    description = "Importa un módulo externo dentro del ámbito actual."

    entrypoint = cmb.Seq(
        cmb.MatchKeyword("import"),
        cmb.MatchToken(lexer.Token.IDENT),
        cmb.MatchToken(lexer.Token.SEMICOLON),
    )

    # 1. Coloreado de tokens (colores hexadecimales o ámbitos TextMate)
    colors = {
        "import": "#FF79C6",
        "@import:1": "#8BE9FD",
        -1: "#6272A4",
    }

    # 2. Autocompletado de palabras clave / prefijos
    autocomplete = {
        0: "import",
    }

    # 3. Sugerencias de valores (lista/tupla estática o invocable sin argumentos)
    suggestions = {
        1: ["math", "sys", "io", "http"],
    }

    # 4. Pistas de tipo / fragmentos (hints)
    hints = {
        0: "import <nombre_modulo>;",
    }

    # 5. Pistas integradas de parámetros (playhints / inlay hints)
    playhints = {
        1: "module",
    }
```

> [!IMPORTANT]
> **Requisito de `nodeable = True`:**  
> `ASTColorResolver` recorre los nodos `ASTRef` en el AST parseado y hace coincidir `ref_node.name` con las clases `RuleItem` registradas. Si una regla define `nodeable = False`, no se emite ningún nodo `ASTRef` para dicha regla, y `VSIXAnalyzer` registra una advertencia: `"Rule '<name>' defines editor maps but nodeable is False."`

---

## 2. Cómo Resuelve Claves en `colors` el `TokenSelector`

Cuando `ASTColorResolver` evalúa un nodo `ASTRef` coincidente, aplana todas las instancias de `TokenType` dentro de ese nodo en orden fuente (`collect_node_tokens(ref_node)`) y resuelve cada clave de `RuleItem.colors` utilizando `TokenSelector.resolve_indices(key, tokens)`:

| Formato de Clave Selectora | Ejemplo | Comportamiento de Resolución |
| :--- | :--- | :--- |
| **`int` positivo o `str` numérico** | `0`, `1`, `"0"` | Coincide con la posición del token basada en índice 0 dentro de la lista aplanada de tokens del `ASTRef`. |
| **`int` negativo o `str` numérico** | `-1`, `"-1"` | Coincide relativo al final de la lista de tokens del `ASTRef` (`len(tokens) + idx`, donde `-1` es el último token). |
| **Ancla (`@TOKEN`)** | `"@IDENT"`, `"@="` | Coincide con cada token en la regla cuyo `tok.token.name` o lexema `str(tok.value)` sea igual al nombre del ancla. |
| **Ancla con Desplazamiento (`@TOKEN:±offset`)** | `"@import:1"`, `"@ASSIGN:-1"` | Encuentra cada token coincidente con `TOKEN` (por tipo de token o lexema) y selecciona el token en `i + offset` (ej.: `"@import:1"` selecciona el token inmediatamente posterior a `import`). |
| **Nombre de Tipo de Token o Lexema** | `"IDENT"`, `"return"`, `";"` | Coincide con cada token cuyo `tok.token.name` o `str(tok.value)` coincida con la cadena. |
| **Nombre de `WordGroup` de Keywords** | `"types"` | Coincide con cualquier `Token.KEYWORD` cuyo `Keyword.group` registrado sea igual al nombre del grupo. |

### Reglas de Precedencia y Fallback
1. **El Hijo Sobrescribe al Padre (`child_overrides_parent=True`):** Por defecto, si tanto una regla `ASTRef` exterior como una regla `ASTRef` anidada interior asignan un color a la misma ocurrencia de un token, gana el color de la regla secundaria interior.
2. **Fallback al Léxico de Palabras Clave:** Cualquier `Token.KEYWORD` al que ningún mapa `RuleItem.colors` le haya asignado color recurre automáticamente al `hex_color` registrado vía `lexer.words.add_keyword(..., hex_color=...)`.

---

## 3. Previsualización Terminal en ANSI TrueColor de 24 Bits

Puedes resolver los colores de los tokens en cualquier AST parseado y generar una cadena formateada en TrueColor ANSI de 24 bits usando `resolve_ast_colors` y `preview_colored_source`:

```python
from gram import combinators as cmb
from gram import lexer, parser, vsix

lexer.words.clear_all()
lexer.words.add_keyword("let", hex_color="#FF79C6", allow_override=True)

class LetDecl(cmb.RuleItem):
    nodeable = True
    entrypoint = cmb.Seq(
        cmb.MatchKeyword("let"),
        cmb.MatchToken(lexer.Token.IDENT),
        cmb.MatchToken(lexer.Token.ASSIGN),
        cmb.MatchToken(lexer.Token.NUMBER),
    )
    colors = {
        "@ASSIGN:-1": "#50FA7B",  # Identificador antes de '='
        "ASSIGN": "#FF79C6",      # Símbolo '='
        -1: "#BD93F9",            # Literal numérico al final
    }

class Program(cmb.RuleItem):
    entrypoint = cmb.Alt(cmb.Ref(LetDecl))

source = "let speed = 100"
tokens = lexer.Lexer(source).process()
ast_roots = parser.Parser(tokens).parse(Program)

# 1. Inspeccionar instancias ColoredToken resueltas:
colored_tokens = vsix.resolve_ast_colors(ast_roots)
for ct in colored_tokens:
    print(f"{ct.token.value!r:8} -> {ct.color} (desde {ct.rule_name}[{ct.token_index!r}])")

# 2. Generar cadena ANSI TrueColor de 24 bits para mostrar en consola:
ansi_preview = vsix.preview_colored_source(source, ast_roots)
print(ansi_preview)
```

Salida:

```text
'speed'  -> #50FA7B (desde LetDecl['@ASSIGN:-1'])
'='      -> #FF79C6 (desde LetDecl['ASSIGN'])
100      -> #BD93F9 (desde LetDecl[-1])
'let'    -> #FF79C6 (desde LexerKeyword[0])
```

---

## 4. Generar y Empaquetar una Extensión de VS Code

### Paso 1: Declarar Metadatos de la Extensión (`vsix.declare_info`)

Utiliza `vsix.declare_info()` (o las funciones granulares `set_package`, `set_language`, `set_author`, `set_repository`, `set_meta`) para configurar el manifiesto de la extensión:

```python
from gram import vsix

vsix.declare_info(
    name="my-dsl-support",
    display_name="My DSL Language Support",
    description="Resaltado de sintaxis, fragmentos y LSP para My DSL",
    version="0.1.0",
    publisher="my-org",
    language_id="mydsl",
    language_name="MyDSL",
    file_extensions=[".mydsl"],
)
```

### Paso 2: Analizar la Gramática (`VSIXAnalyzer`) y Exportar Artefactos (`VSIXGenerator`)

```python
# 1. Extraer esquema canónico desde el RuleItem punto de entrada raíz:
schema = vsix.VSIXAnalyzer(output="vscode").process(Program)

# 2. Generar archivos de extensión para VS Code en ./vscode_extension:
generator = vsix.VSIXGenerator(schema)
artifacts = generator.export("./vscode_extension")
# Escribe:
# - ./vscode_extension/package.json
# - ./vscode_extension/language-configuration.json
# - ./vscode_extension/syntaxes/mydsl.tmLanguage.json
# - ./vscode_extension/snippets/snippets.json
# - ./vscode_extension/extension.js
```

### Paso 3: Empaquetar `.vsix` e Instalar (`pack_vsix` / `up`)

`vsix.pack_vsix()` construye un archivo zip `.vsix` con Open Packaging Conventions (OPC) directamente en Python sin requerir Node.js ni `vsce`.

`vsix.up()` orquesta la exportación, el empaquetado `.vsix`, la instalación local en `~/.vscode/extensions` y el inicio opcional de VS Code en una sola llamada:

```python
# Empaquetar ./vscode_extension en un archivo .vsix independiente sin instalar:
vsix_file = vsix.pack_vsix("./vscode_extension")

# O exportar, empaquetar e instalar en VS Code en un solo paso:
status = vsix.up(
    generator,
    pack=True,
    install=True,
    launch=False,
)
```

---

## 5. Servidor de Lenguaje Integrado (`gram.vsix.lsp`)

El cliente `extension.js` generado inicia automáticamente el servidor de lenguaje en Python puro por stdio de Gram:

```bash
python -u -m gram.vsix.lsp.server --entrypoint mi_modulo:Program --workspace /ruta/al/workspace
```

Internamente, `LSPState` (`gram.vsix.lsp.state.LSPState`) utiliza `Diagnostics.hook_errors` con `ErrorAction.SUPPRESS_RAISE` y `config.ERROR_EXIT_ON_ERROR = False` para ejecutar `Lexer` y `Parser` en cada evento `textDocument/didOpen` y `textDocument/didChange`, convirtiendo las instancias capturadas de `Error` en diagnósticos LSP junto con respuestas para autocompletado, hover e inlay hints.
