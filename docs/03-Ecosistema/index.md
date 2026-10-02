# Ecosistema y Herramientas

El ecosistema de **Gram Framework** trasciende el parsing tradicional para ofrecer un conjunto integral de herramientas para el diseño, verificación, distribución y soporte de lenguajes y formatos estructurados en entornos de desarrollo modernos.

---

## Componentes del Ecosistema

```
                     ┌─────────────────────────┐
                     │     Gram Framework      │
                     └───────────┬─────────────┘
                                 │
        ┌────────────────────────┼────────────────────────┐
        ▼                        ▼                        ▼
 ┌──────────────┐         ┌──────────────┐         ┌──────────────┐
 │    GLANG     │         │   Plugins    │         │  VSIX & LSP  │
 │ Lenguaje DSL │         │  & Sandbox   │         │ para VS Code │
 └──────────────┘         └──────────────┘         └──────────────┘
```

---

## Módulos de esta Sección

| Módulo | Documento | Descripción |
| :--- | :--- | :--- |
| **DSL GLANG** | [glang.md](glang.md) | Lenguaje de Dominio Específico (DSL) declarativo para definir gramáticas en archivos `.glang` sin escribir diccionarios de Python, con compilación automática y comandos CLI. |
| **Sistema de Plugins** | [plugins.md](plugins.md) | Arquitectura de extensiones, formato de manifiesto `manifest.json`, subclases de `PluginBase`, auditoría estática AST (`gram check`), sandbox/permisos y guías de los plugins oficiales. |
| **VSIX y LSP** | [vsix.md](vsix.md) | Generación automática de extensiones empaquetadas para Visual Studio Code (`.vsix`), esquemas TextMate de color, servidor Language Server Protocol (LSP) y telemetría de diagnósticos. |

---

## Capacidades Destacadas

1. **Definición de Lenguajes sin Boilerplate (GLANG):** Escribe especificaciones gramaticales legibles con sintaxis amigable y compílalas a árboles de combinadores optimizados.
2. **Seguridad y Aislamiento:** Los plugins de terceros son analizados antes de su carga mediante inspección de nodos AST para impedir accesos no autorizados a APIs del sistema o ejecución de código arbitrario.
3. **Soporte de Editor Inmediato:** Con un solo comando (`python -m gram.cli vsix install`), tu nuevo lenguaje obtiene una extensión instalable en VS Code con resaltado y soporte LSP completo.
