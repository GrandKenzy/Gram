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

from gram import config

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
        self.header_class: bool = self.__class__.header_class

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
        EN: Resolve the parser from the supported analyzer or parser input.
        ES: Obtiene el parser desde el analizador o el parser recibido.

        Args:
            analyzer: Active ASTAnalyzer or Parser instance.
                      Instancia activa de ASTAnalyzer o Parser.

        Returns:
            Resolved Parser instance.
            Instancia del parser sintáctico.
        """
        from gram.core.parser.core import Parser

        if isinstance(analyzer, Parser):
            return analyzer
        return analyzer.parser

    def _get_node(self, analyzer: Any) -> InfoNode:
        """
        EN: Resolve the active telemetry node owned by the parser.
        ES: Obtiene el nodo de telemetría activo del parser.

        Args:
            analyzer: Active analyzer or parser instance.
                      Instancia del analizador o parser.

        Returns:
            Active telemetry InfoNode.
            Nodo de telemetría activo.
        """
        return self._get_parser(analyzer).node

    def _record_failure(
        self,
        analyzer: Any,
        expected: str,
        position: int,
        token: TokenType | None,
    ) -> None:
        """Record a mismatch before a combinator restores the parser cursor."""
        self._get_parser(analyzer).control.record_failure(
            expected,
            position,
            token,
        )

    def _failure_context(self, analyzer: Any) -> str | None:
        """Return the deepest token mismatch for a high-level failure message."""
        return self._get_parser(analyzer).control.failure_context()

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
        parser = self._get_parser(analyzer)
        from gram.core.ast.analyzer import ASTAnalyzer

        if isinstance(analyzer, ASTAnalyzer):
            return analyzer.process_combinator(
                combinator,
                current,
                ignore_errors=ignore_errors,
            )

        if config.PARSER_ADD_INFO:
            node = parser.node.node(
                combinator.type(),
                f"{combinator.type()} ← {current}",
            )
            with parser.use_node(node):
                return combinator.parse(
                    parser,
                    current,
                    ignore_errors=ignore_errors,
                )
        return combinator.parse(parser, current, ignore_errors=ignore_errors)

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


from gram.core.rules.codes import AutoCode, SetCode, code_manager


class RuleMeta(type):
    """
    EN:
        Metaclass for formal and declarative representation of RuleItem rules.
        Provides readable textual inspection, automatic non-colliding code allocation
        via AutoCode, and code registry tracking.

    ES:
        Metaclase para la representación formal y declarativa de reglas RuleItem.
        Facilita la inspección textual, asignación automática de códigos sin colisión
        mediante AutoCode y registro centralizado de identificadores.
    """

    def __new__(mcls, name: str, bases: tuple[type, ...], namespace: dict[str, Any]) -> type:
        raw_code = namespace.get("code")

        # Asignación automática o resolución de AutoCode
        if raw_code is AutoCode or (isinstance(raw_code, type) and issubclass(raw_code, AutoCode)):
            namespace["code"] = AutoCode()
        elif "code" not in namespace and bases:
            namespace["code"] = AutoCode()
        elif callable(raw_code) and not isinstance(raw_code, type):
            try:
                namespace["code"] = raw_code()
            except TypeError:
                pass

        cls = super().__new__(mcls, name, bases, namespace)

        # Registrar el código en el gestor global para prevenir colisiones futuras
        code_val = cls.code
        if isinstance(code_val, int) and code_val > 0:
            code_manager.register(code_val, rule=cls)

        return cls

    def __repr__(cls) -> str:
        return (
            f"{cls.__name__}("
            f"code={cls.code!r}, "
            f"name={cls.name or cls.__name__!r}, "
            f"grammar={bool(cls.grammar)}"
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
    ignore: bool = False
    no_simplify: bool = False
    queries: Any = None
    hints: dict[int, Any] = {}

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
        r_name = cls.name or cls.__name__
        r_code = cls.code
        r_desc = cls.description
        r_docs = cls.docs
        raw_colors = cls.colors or {}
        r_colors = dict(raw_colors) if isinstance(raw_colors, dict) else {}
        r_struct = cls.is_structural
        r_ignore = cls.ignore
        raw_sugg = cls.suggestions or {}
        r_sugg = dict(raw_sugg) if isinstance(raw_sugg, dict) else {}
        r_auto = cls.suggestions_autocomplete

        # Determinar queries de autocompletado dinámico
        raw_queries = cls.queries
        r_queries: list[Any] = []
        if raw_queries is not None:
            if isinstance(raw_queries, (list, tuple, set)):
                r_queries = list(raw_queries)
            else:
                r_queries = [raw_queries]

        # Extraer palabras clave asociadas a la gramática si existen
        auto_keywords: list[str] = []
        def _collect_keywords(comb: Any) -> None:
            if comb is None:
                return
            if hasattr(comb, "keyword") and isinstance(comb.keyword, str):
                auto_keywords.append(comb.keyword)
            if hasattr(comb, "combinators") and isinstance(comb.combinators, (list, tuple)):
                for sub in comb.combinators:
                    _collect_keywords(sub)
            if hasattr(comb, "combinator"):
                _collect_keywords(getattr(comb, "combinator"))
            if hasattr(comb, "values") and isinstance(comb.values, (list, tuple)):
                for sub in comb.values:
                    _collect_keywords(sub)

        _collect_keywords(cls.grammar)
        for q in r_queries:
            if hasattr(q, "trigger_keywords") and not q.trigger_keywords and auto_keywords:
                q.trigger_keywords = list(auto_keywords)

        # Determinar color primario de la regla
        color_val = "#FFFFFF"
        if 0 in r_colors:
            color_val = r_colors[0]
        elif r_colors:
            color_val = next(iter(r_colors.values()))

        # Formato de scope TextMate sanitizado
        clean_name = re.sub(r"[^a-zA-Z0-9_]", "_", r_name).lower()
        scope_name = f"entity.name.rule.gram.{clean_name}"

        # Determinar hints virtuales declarados
        raw_hints = cls.hints or {}
        r_hints = dict(raw_hints) if isinstance(raw_hints, dict) else {}

        return {
            "name": r_name,
            "code": r_code,
            "description": r_desc,
            "docs": r_docs,
            "colors": r_colors,
            "color": color_val,
            "scope": scope_name,
            "is_structural": r_struct,
            "ignore": r_ignore,
            "suggestions": r_sugg,
            "suggestions_autocomplete": r_auto,
            "queries": r_queries,
            "hints": r_hints,
            "contain_grammar": cls.contain_grammar(),
            "grammar": cls.grammar,
        }


RuleType = type[RuleItem] | str


__all__ = [
    "AutoCode",
    "Combinator",
    "RuleItem",
    "RuleMeta",
    "RuleType",
    "SetCode",
]
