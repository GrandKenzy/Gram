"""
Contrato Base para Plugins del Framework Gram (`gram.plugins.base`).
===================================================================
Define la clase abstracta ``PluginBase`` como el **único** mecanismo de
extensión de Gram. No hay compatibilidad hacia atrás con módulos de funciones
sueltas; todo plugin debe subclasificar ``PluginBase``.

Puntos de extensión disponibles:
  1. **Léxico**: ``get_keywords()``, ``get_word_groups()``, ``get_tokens()``.
  2. **Sintáctico**: ``get_combinators()``, ``get_rules()``, ``get_grammar()``,
     ``extend_declarations()``.
  3. **AST / Semántico**: ``transform_ast()``, ``validate_ast()``.
  4. **Ciclo de vida**: ``on_load()``, ``on_unload()``.
  5. **Ejecución y CLI**: ``process()``, ``cli()``.
"""
from __future__ import annotations

from abc import ABC
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from gram.core.ast.nodes import ASTProgram
    from gram.core.combinators.base import Combinator, RuleItem
    from gram.core.lexer.tokens import CustomToken
    from gram.core.lexer.words import Keyword
    from gram.plugins.manifest import PluginManifest


class PluginBase(ABC):
    """
    Clase base obligatoria para todos los plugins de Gram.

    Subclasifica esta clase en ``main.py`` de tu plugin e implementa
    los métodos que correspondan a las capacidades que deseas añadir.
    Los métodos no implementados retornan valores seguros por defecto.
    """

    #: Nombre del plugin. Se sobreescribe automáticamente desde el manifest.
    plugin_name: str = ""
    #: Versión en formato semver. Se sobreescribe desde el manifest.
    version: str = "1.0.0"
    #: Descripción breve. Se sobreescribe desde el manifest.
    description: str = ""

    def __init__(
        self,
        manifest: PluginManifest | None = None,
        plugin_path: Path | None = None,
    ) -> None:
        self.manifest: PluginManifest | None = manifest
        self.plugin_path: Path = plugin_path or Path()
        self.is_loaded: bool = False
        self.load_result: Any = None

        if manifest:
            if manifest.plugin_name:
                self.plugin_name = manifest.plugin_name
            if manifest.version_str:
                self.version = manifest.version_str
            if manifest.description:
                self.description = manifest.description

    # =========================================================================
    # 1. CICLO DE VIDA (LIFECYCLE)
    # =========================================================================

    def on_load(self) -> bool | None:
        """
        Ejecutado automáticamente al inicializar el plugin.

        Retornar ``False`` cancela la carga con error. Retornar ``True``
        o ``None`` indica éxito.
        """
        return True

    def on_unload(self) -> None:
        """
        Ejecutado al descargar o recargar el plugin.

        Libera recursos, cierra conexiones o persiste estado aquí.
        """

    # =========================================================================
    # 2. EXTENSIONES LÉXICAS (LEXER)
    # =========================================================================

    def get_keywords(self) -> list[Keyword | str | tuple[str, str] | tuple[str, str, str]]:
        """
        Palabras clave que deben registrarse en el Lexer de Gram.

        Formatos admitidos:
          - Instancias de ``Keyword``.
          - Cadena simple: ``'fn'``.
          - Tupla ``(name, hex_color)``: ``('let', '#569CD6')``.
          - Tupla ``(name, hex_color, group)``: ``('let', '#569CD6', 'DECLARATIONS')``.
        """
        return []

    def get_word_groups(self) -> dict[str, list[str]]:
        """
        Grupos temáticos de palabras para coincidencia mediante ``MatchGroup``.

        Ejemplo::

            return {"TYPES": ["int", "float", "str", "bool"]}
        """
        return {}

    def get_tokens(self) -> list[CustomToken | str]:
        """Tokens personalizados dinámicos para el lexer."""
        return []

    # =========================================================================
    # 3. EXTENSIONES SINTÁCTICAS Y GRAMATICALES (PARSER & COMBINATORS)
    # =========================================================================

    def get_combinators(self) -> list[type[Combinator] | Combinator]:
        """
        Combinadores sintácticos (Custom Mods) expuestos por el plugin.

        Se registran automáticamente mediante ``register_custom_mod()``.
        """
        return []

    def get_rules(self) -> list[type[RuleItem] | RuleItem]:
        """Reglas sintácticas (``RuleItem``) expuestas por el plugin."""
        return []

    def get_grammar(self) -> dict[Any, Any]:
        """
        Diccionario de reglas asignadas a sus combinadores.

        Ejemplo::

            return {MI_REGLA: Seq(Kw("fn"), Ident())}
        """
        return {}

    def extend_declarations(self) -> list[type[RuleItem] | RuleItem | Combinator]:
        """
        Reglas o combinadores que se inyectan en las alternativas de la
        regla raíz ``DECLARATION`` de Gram.

        Permite que el DSL reconozca automáticamente la nueva sintaxis sin
        reconstruir manualmente el árbol de reglas.
        """
        return []

    # =========================================================================
    # 4. TRANSFORMACIONES Y PROCESAMIENTO SEMÁNTICO (AST)
    # =========================================================================

    def transform_ast(self, ast: ASTProgram) -> ASTProgram:
        """
        Paso de transformación o enriquecimiento del AST tras el parsing.

        Recibe el ``ASTProgram`` generado y retorna la versión modificada.
        """
        return ast

    def validate_ast(self, ast: ASTProgram) -> list[Any]:
        """
        Verificaciones semánticas o análisis estático sobre el AST.

        Retorna una lista de problemas, advertencias o diagnósticos.
        Lista vacía significa que el AST es válido para este plugin.
        """
        return []

    # =========================================================================
    # 5. PUNTO DE PROCESAMIENTO UNIFICADO Y CLI
    # =========================================================================

    def process(self, *args: Any, **kwargs: Any) -> Any:
        """
        Punto de procesamiento a demanda del plugin.

        Puede recibir código fuente, tokens, un AST o parámetros personalizados.
        """
        return True

    def cli(self, *args: Any, **kwargs: Any) -> Any:
        """Interfaz de comandos de consola del plugin."""
        return None


__all__ = [
    "PluginBase",
]
