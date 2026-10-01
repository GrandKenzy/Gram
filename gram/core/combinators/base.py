"""
EN:
    Base Class for Syntactic Combinators and Rules (`gram.core.combinators.base`).
    =============================================================================
    Defines the fundamental abstract `Combinator` class, `RuleMeta` metaclass, and
    declarative `RuleItem` base class for formal grammar production rules.

ES:
    Clase Base para Combinadores Sintácticos y Reglas (`gram.core.combinators.base`).
    ================================================================================
    Define la clase abstracta fundamental `Combinator`, la metaclase `RuleMeta` y
    la clase base declarativa `RuleItem` para la definición formal de reglas de producción.
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from gram.core.ast import ASTAnalyzer
    from gram.core.lexer.tokens import TokenType
    from gram.core.parser.core import Parser
    from gram.utilities.info import Node as InfoNode


class Combinator:
    """
    EN:
        Abstract base class for all Gram Framework syntactic combinators.
        Encapsulates a declarative strategy for token matching, consumption,
        branching, or repetition on the parser token stream.

    ES:
        Clase base abstracta para todos los combinadores sintácticos de Gram Framework.
        Cada combinador encapsula una estrategia declarativa de reconocimiento,
        consumo, bifurcación o repetición de tokens en el flujo del parser.
    """
    header_class: bool = False

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.header_class: bool = getattr(self.__class__, "header_class", False)

    def parse(
        self,
        analyzer: ASTAnalyzer | Parser | Any,
        current: TokenType | None = None,
        ignore_errors: bool = False,
    ) -> Any:
        """
        EN: Execute syntactic parsing for this combinator.
        ES: Ejecuta el análisis sintáctico del combinador.

        Args:
            analyzer: Syntax analyzer instance (ASTAnalyzer or Parser).
                      Instancia del analizador sintáctico (ASTAnalyzer o Parser).
            current: Current token under cursor, or None to consume from parser.
                     Token actual posicionado bajo el cursor, o None para consumir del parser.
            ignore_errors: If True, suppress syntax discrepancies without raising.
                           Si True, no levanta excepciones ante discrepancias sintácticas.

        Returns:
            Generated AST node, TokenType, list of results, or None if no match.
            Nodo AST generado, TokenType, lista de resultados o None si no hubo coincidencia.

        Raises:
            NotImplementedError: If the subclass does not implement parse().
                                 Si la subclase no implementa la lógica de parsing.
        """
        raise NotImplementedError(
            f"El combinador {self.__class__.__name__} debe implementar el método parse()."
        )

    def _get_parser(self, analyzer: Any) -> Parser:
        """
        EN: Safely resolve Parser instance from ASTAnalyzer or Parser.
        ES: Obtiene de forma segura la instancia del Parser a partir de ASTAnalyzer o Parser.

        Args:
            analyzer: Active ASTAnalyzer or Parser instance.
                      Instancia activa de ASTAnalyzer o Parser.

        Returns:
            Resolved Parser instance.
            Instancia del parser sintáctico.
        """
        return getattr(analyzer, "parser", analyzer)

    def _get_node(self, analyzer: Any) -> InfoNode | None:
        """
        EN: Safely resolve active telemetry node from analyzer or parser.
        ES: Obtiene de forma segura el nodo de telemetría del analizador o parser.

        Args:
            analyzer: Active analyzer or parser instance.
                      Instancia del analizador o parser.

        Returns:
            Active telemetry InfoNode or None if unavailable.
            Nodo de telemetría activo o None si no está disponible.
        """
        node = getattr(analyzer, "node", None)
        if node is not None:
            return node
        parser = getattr(analyzer, "parser", None)
        if parser is not None:
            return getattr(parser, "node", None)
        return getattr(analyzer, "STACK_INFO", None)

    def _dispatch_sub(
        self,
        combinator: Combinator,
        analyzer: Any,
        current: TokenType | None = None,
        ignore_errors: bool = False,
    ) -> Any:
        """
        EN: Dispatch child combinator execution through ASTAnalyzer or directly via parser.
        ES: Despacha la ejecución de un combinador hijo de forma unificada,
            delegando en ASTAnalyzer.process_combinator si está disponible,
            o invocando combinator.parse directamente sobre el parser.

        Args:
            combinator: Sub-combinator to evaluate.
                        Sub-combinador a evaluar.
            analyzer: Active analyzer or parser.
                      Analizador o Parser activo.
            current: Current token or None.
                     Token actual posicionado o None.
            ignore_errors: If True, suppress syntax errors.
                           Si True, suprime errores sintácticos.

        Returns:
            Result of sub-combinator evaluation.
            Resultado de la evaluación del sub-combinador.
        """
        if hasattr(analyzer, "process_combinator"):
            return analyzer.process_combinator(combinator, current, ignore_errors=ignore_errors)
        return combinator.parse(analyzer, current, ignore_errors=ignore_errors)

    @classmethod
    def type(cls) -> str:
        """
        EN: Return canonical combinator type name.
        ES: Devuelve el nombre canónico del tipo de combinador.
        """
        return cls.__name__

    def __or__(self, other: Any) -> Combinator:
        """
        EN: Binary '|' operator overload for alternative composition (Alt).
        ES: Sobrecarga del operador binario '|' para componer combinadores como alternativas (Alt).
        """
        try:
            from gram.core.combinators.alternative import Alt
            if isinstance(self, Alt):
                if isinstance(other, Alt):
                    return Alt(*(self.combinators + other.combinators))
                return Alt(*(self.combinators + (other,)))
            if isinstance(other, Alt):
                return Alt(self, *other.combinators)
            return Alt(self, other)
        except ImportError:
            return NotImplemented

    def __add__(self, other: Any) -> Combinator:
        """
        EN: Binary '+' operator overload for sequence composition (Seq).
        ES: Sobrecarga del operador binario '+' para componer combinadores en secuencia (Seq).
        """
        try:
            from gram.core.combinators.sequence import Seq
            if isinstance(self, Seq):
                if isinstance(other, Seq):
                    return Seq(*(self.combinators + other.combinators))
                return Seq(*(self.combinators + (other,)))
            if isinstance(other, Seq):
                return Seq(self, *other.combinators)
            return Seq(self, other)
        except ImportError:
            return NotImplemented

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}>"


class RuleMeta(type):
    """
    EN:
        Metaclass for formal and declarative representation of RuleItem rules.
        Provides readable textual inspection and debugging for grammar AST dumps.

    ES:
        Metaclase para la representación formal y declarativa de reglas RuleItem.
        Facilita la inspección textual, depuración e introspección de gramáticas.
    """

    def __repr__(cls) -> str:
        return (
            f"{cls.__name__}("
            f"code={getattr(cls, 'code', 0)!r}, "
            f"name={getattr(cls, 'name', cls.__name__)!r}, "
            f"grammar={bool(getattr(cls, 'grammar', None))}"
            f")"
        )


class RuleItem(metaclass=RuleMeta):
    """
    EN:
        Declarative base class for formal grammar production rules.
        Associates numeric code, grammar combinator, documentation,
        syntax highlighting colors, and autocomplete suggestions for IDEs/VSIX.

    ES:
        Clase base declarativa para reglas de producción gramatical.
        Permite asociar código numérico, combinador gramatical, documentación,
        colores de sintaxis y sugerencias de autocompletado para IDEs y VSIX.
    """

    code: int = 0
    name: str = ""
    description: str = ""
    grammar: Combinator | None = None
    docs: str = ""
    colors: dict[int, str] = {}
    suggestions: dict[int, Any] = {}
    suggestions_autocomplete: bool = False
    is_structural: bool = False

    @classmethod
    def contain_grammar(cls) -> bool:
        """
        EN: Check whether this rule defines an active grammar combinator.
        ES: Indica si la regla contiene un combinador gramatical definido.
        """
        return cls.grammar is not None

    @classmethod
    def compile(cls) -> dict[str, Any]:
        """
        EN: Compile rule metadata into a structured dictionary for editor extensions.
        ES: Compila los metadatos de la regla en un diccionario estructurado
            usable por extensiones de editor (VSIX, TextMate, Language Servers).

        Returns:
            Structured compiled metadata dictionary.
            Diccionario estructurado con los metadatos compilados de la regla.
        """
        r_name = getattr(cls, "name", "") or cls.__name__
        r_code = getattr(cls, "code", 0)
        r_desc = getattr(cls, "description", "")
        r_docs = getattr(cls, "docs", "")
        raw_colors = getattr(cls, "colors", {}) or {}
        r_colors = dict(raw_colors) if isinstance(raw_colors, dict) else {}
        r_struct = getattr(cls, "is_structural", False)
        raw_sugg = getattr(cls, "suggestions", {}) or {}
        r_sugg = dict(raw_sugg) if isinstance(raw_sugg, dict) else {}
        r_auto = getattr(cls, "suggestions_autocomplete", False)

        # Determinar color primario de la regla
        color_val = "#FFFFFF"
        if 0 in r_colors:
            color_val = r_colors[0]
        elif r_colors:
            color_val = next(iter(r_colors.values()))

        # Formato de scope TextMate sanitizado
        clean_name = re.sub(r"[^a-zA-Z0-9_]", "_", r_name).lower()
        scope_name = f"entity.name.rule.gram.{clean_name}"

        return {
            "name": r_name,
            "code": r_code,
            "description": r_desc,
            "docs": r_docs,
            "colors": r_colors,
            "color": color_val,
            "scope": scope_name,
            "is_structural": r_struct,
            "suggestions": r_sugg,
            "suggestions_autocomplete": r_auto,
            "contain_grammar": cls.contain_grammar(),
            "grammar": cls.grammar,
        }


RuleType = type[RuleItem] | str


__all__ = [
    "Combinator",
    "RuleItem",
    "RuleMeta",
    "RuleType",
]
