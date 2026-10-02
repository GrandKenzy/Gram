# Referencia y Diagnóstico

Esta sección agrupa los catálogos técnicos de referencia formal, especificaciones de diagnóstico y códigos estándar del **Framework Gram**.

---

## Estándar de Diagnósticos OSGDC

Gram implementa una metodología rigurosa para la gestión de errores y diagnósticos a lo largo de todas las etapas del compilador. Ningún componente o extensión puede emitir excepciones genéricas o mensajes no clasificados.

El estándar **OSGDC** descompone cada fallo en 5 dimensiones deterministas:

| Dimensión | Significado | Ejemplos |
| :---: | :--- | :--- |
| **`[O]`** | **Origen** | `N` (Nativo/Core), `P` (Plugin), `E` (Externo), `U` (Usuario) |
| **`[S]`** | **Subsistema** | `LEX` (Lexer), `PAR` (Parser), `AST` (Árbol), `PLG` (Plugins), `GLG` (GLANG), `VSX` (VSIX) |
| **`[G]`** | **Gravedad** | `INFO`, `WARN`, `ERROR`, `FATAL` |
| **`[D]`** | **Documentación** | Enlace o identificador a la guía canónica de resolución |
| **`[C]`** | **Condición** | Código numérico secuencial del error dentro de su subsistema |

---

## Módulos de esta Sección

| Módulo | Documento | Descripción |
| :--- | :--- | :--- |
| **Catálogo de Errores OSGDC** | [errors.md](errors.md) | Catálogo exhaustivo y formal de todas las constantes `CodeError` del framework, tabla de rangos por subsistema, matriz de severidad y ejemplos de captura/manejo. |
