# Guía y Referencia del Subsistema VSIX y LSP (`gram.vsix`)

El subsistema `gram.vsix` de Gram transforma automáticamente cualquier gramática, regla o plugin definido en Gram en una extensión completa y empaquetada para Visual Studio Code (`.vsix`), dotada de servidor de lenguaje Language Server Protocol (LSP), resaltado de colores, autocompletado, marcado de diagnósticos y enlaces al compilador.

---

## 1. Arquitectura y Capacidades Cardinales

A diferencia de aproximaciones tradicionales donde el soporte para editores se construye manualmente en TypeScript, Gram unifica el ciclo de vida: **los mismos metadatos que definen la sintaxis de ejecución generan la experiencia de desarrollo en VS Code**.

```
    Reglas Gram (RuleItem)        Palabras Clave (Keywords)       Plugins & GLang
              │                              │                           │
              └──────────────────────────────┼───────────────────────────┘
                                             │
                                             ▼
                             Extracción de Metadatos VSIX
                               (gram.vsix.extract)
                                             │
      ┌──────────────────────────────────────┼──────────────────────────────────────┐
      │                                      │                                      │
      ▼                                      ▼                                      ▼
1. TextMate Grammar                    2. Autocompletado                       3. Servidor LSP
   & Esquemas de Color                    & Snippets                              (JSON-RPC)
   • .tmLanguage.json                     • .code-snippets                        • Hover tooltips
   • gram-theme.json                      • Sugerencias de reglas                 • Diagnósticos en vivo
      │                                      │                                      │
      └──────────────────────────────────────┼──────────────────────────────────────┘
                                             │
                                             ▼
                              Generador de Paquete .VSIX
                                (gram.vsix.generate)
                                 • package.json
                                 • language-configuration.json
                                 • icon.png procedimental
                                 • ID Universal: gram.universal-extension
```

### Las 6 Características Cardinales

#### 1. Colores y Resaltado de Sintaxis
- **Extracción Automática:** Cada clase que hereda de `RuleItem` puede declarar un diccionario `colors` indexado por terminales: por ejemplo `{0: "#E5C07B", 1: "#D4AF37", 2: "#88B04B"}`.
- **Generación TextMate:** Para gramáticas compuestas por `Seq`, `Alt`, `Opt`, `Many`, `Some`, `MatchKeyword`, `MatchGroup`, `MatchToken` y `MatchSeqSymbol`, Gram genera capturas TextMate por terminal y scopes de color individuales. Los índices de ramas alternativas corresponden a la misma posición lógica. Las reglas con combinadores no representables como expresiones regulares conservan su metadato y resaltado general, pero no producen capturas contextuales por terminal.

#### 2. Autocompletado y Snippets Inteligentes
- **Extracción de Sugerencias:** Con `suggestions_autocomplete = True`, cada valor de `suggestions` puede declarar `prefix`, `body` y `description`. Se publica tanto como snippet de VS Code (`snippets/snippets.json`) como completion item en el LSP. Si es `False`, se omiten las sugerencias de esa regla en ambos canales.
- Provee autocompletado contextual tanto para palabras clave del lenguaje como para plantillas estructurales de reglas sintácticas.

#### 3. Language Server Protocol (LSP) Embebido
Gram incluye un servidor LSP nativo (`gram.vsix.lsp.GramLanguageServer`) implementado en Python sobre el protocolo estándar JSON-RPC:
- **`textDocument/didOpen` y `textDocument/didChange`:** Analiza el código fuente en tiempo real conforme el desarrollador escribe en el editor.
- **`textDocument/completion`:** Sugiere palabras clave, tokens y reglas en la posición actual del cursor.
- **`textDocument/hover`:** Muestra tarjetas emergentes con la documentación declarada en `RuleItem.description` o `RuleItem.docs`.

#### 4. Marcado de Errores y Diagnósticos en Tiempo Real
- Cada vez que el motor léxico o el analizador sintáctico de Gram detecta una discrepancia sintáctica (`ParserError`, `LexerError`), el servidor LSP traduce el error del catálogo formal OSGDC (línea, columna, mensaje y código) a un objeto `Diagnostic` de VS Code:
  - Subraya con línea roja u ondulada el token exacto que causó el error.
  - Muestra la descripción formal del fallo y sugerencias de corrección en el panel "Problemas" de VS Code.

#### 5. Empaquetado Autónomo e Icono Personalizado
- Genera la estructura de directorios requerida por VS Code con `package.json`, configuraciones de delimitadores (`language-configuration.json`), auto-cierre de comillas y llaves, y reglas de comentarios.
- Genera procedimentalmente un archivo `icon.png` oficial con el logotipo de Gram para que la extensión luzca profesional en el catálogo de VS Code.

### Generar una extensión para otro lenguaje

`build_extension_directory()` acepta identidad, ID de lenguaje, extensiones, nombre y ruta de gramática/tema, configuración de lenguaje, snippets, contribuciones de VS Code y archivos adicionales. El cliente LSP de Gram es opcional y se desactiva con `include_lsp=False`. Para conservar los tooltips de documentación sin iniciar el LSP de Python, activa `include_hover=True`; el proveedor estático se genera a partir de la documentación de keywords y reglas.

```python
from gram.vsix import build_extension_directory, extract_metadata, LanguageConfiguration

metadata = extract_metadata()
metadata.file_extensions = [".sample"]
build_extension_directory(
    "build/sample-extension",
    metadata=metadata,
    ext_id="sample-language",
    ext_name="Sample Language",
    publisher="example",
    language_id="sample",
    scope_name="source.sample",
    grammar_name="Sample",
    grammar_file="sample.tmLanguage.json",
    theme_file="sample-theme.json",
    language_aliases=["Sample"],
    language_configuration=LanguageConfiguration().LineComment(";"),
    include_lsp=False,
    include_hover=True,
)
```

#### 6. Compilador Objetivo Enlazado
- La extensión puede configurarse para invocar directamente el ejecutable de Gram o un compilador personalizado (`gram run <archivo>`, `gram glang compile <archivo>`) mediante comandos rápidos o atajos de teclado (`Ctrl+Shift+B`).

---

## 2. Identificador Universal de Gram (`GRAM_FULL_ID`)

Para prevenir la proliferación de extensiones huérfanas o duplicadas, Gram utiliza un identificador universal canónico:

$$\text{Publisher: }\mathbf{gram}\quad\vert\quad\text{Name: }\mathbf{universal-extension}\quad\vert\quad\text{ID: }\mathbf{gram.universal-extension}$$

Cualquier compilación, instalación, verificación o desinstalación operará sobre este ID único, permitiendo que múltiples plugins agreguen sintaxis de forma acumulativa sin saturar el entorno del editor.

---

## 3. Comandos CLI para VSIX (`gram vsix`)

La interfaz de línea de comandos de Gram permite gestionar todo el ciclo de vida de la extensión desde la terminal:

```bash
# 1. Compilar el paquete .vsix consolidando todas las reglas y plugins cargados
python -m gram.cli vsix build

# 2. Compilar e instalar automáticamente en Visual Studio Code
python -m gram.cli vsix install

# 3. Listar extensiones de Gram actualmente instaladas en VS Code
python -m gram.cli vsix list

# 4. Desinstalar limpiamente la extensión de Visual Studio Code
python -m gram.cli vsix uninstall
```

---

## 4. API en Python (`gram.vsix`)

El subsistema se puede invocar directamente desde código Python o dentro de la función `on_load()` de un plugin:

```python
from gram import vsix

# 1. Compilar el archivo .vsix en disco
vsix_path = vsix.compile()
print(f"Paquete generado en: {vsix_path}")

# 2. Instalar directamente en la instancia activa de VS Code
exito = vsix.install()
if exito:
    print("Extensión instalada con éxito en VS Code.")

# 3. Consultar si la extensión está instalada
if vsix.is_installed():
    print("La extensión de Gram se encuentra activa en VS Code.")

# 4. Desinstalar
vsix.uninstall()
```

### Compilación Modular desde Plugins (`compile_from`)

Cuando un plugin se carga, puede solicitar la actualización de la extensión VSIX incluyendo sus propias reglas mediante `vsix.compile_from(__file__)`:

```python
from gram.plugins.base import PluginBase

class MiPlugin(PluginBase):
    def on_load(self) -> bool:
        # Registrar reglas...
        
        # Actualizar extensión de VS Code con los colores del plugin
        try:
            from gram import vsix
            vsix.compile_from(__file__)
        except Exception:
            pass

        return True
```

---

## 5. Servidor Language Server Protocol (LSP)

Para ejecutar el servidor LSP de forma independiente (por ejemplo, para integrarlo con Neovim, Emacs, Sublime Text o clientes LSP genéricos):

```bash
# Iniciar servidor LSP sobre entrada/salida estándar (stdio)
python -m gram.vsix.lsp --stdio

# Iniciar servidor LSP sobre socket TCP
python -m gram.vsix.lsp --tcp --port 5007
```

O desde Python:
```python
from gram.vsix.lsp import start_lsp_server

# Inicia el bucle de escucha del servidor LSP
start_lsp_server(mode="stdio")
```
