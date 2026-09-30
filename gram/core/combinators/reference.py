"""
Combinador de Referencia a Reglas (`gram.core.combinators.reference`).
======================================================================
Proporciona el combinador `Ref` (y alias `Reference`) para resolver dinámicamente
reglas de producción gramaticales por referencia a clase o nombre simbólico,
permitiendo recursión mutua y referencias adelantadas (forward references).
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from gram import config, errors
from gram.core.combinators.base import Combinator, RuleType
from gram.utilities import error

if TYPE_CHECKING:
    from gram.core.ast import ASTAnalyzer
    from gram.core.lexer.tokens import TokenType
    from gram.core.parser.core import Parser


class Ref(Combinator):
    """
    ES:
        Combinador de referencia a otra regla de producción gramatical.
        Resuelve dinámicamente la gramática asociada a la regla en el analizador,
        soportando recursión y referencias adelantadas.

    EN:
        Rule reference combinator resolving named rules dynamically from the grammar registry.
    """

    def __init__(self, rule: RuleType) -> None:
        """
        Inicializa la referencia a una regla gramatical.

        Args:
            rule: Clase de regla (RuleType), subclase de RuleItem, instancia o nombre en cadena.
        """
        self.rule: RuleType = rule

    @property
    def rule_name(self) -> str:
        """Retorna el nombre descriptivo de la regla referenciada."""
        if isinstance(self.rule, str):
            return self.rule
        return getattr(self.rule, "name", getattr(self.rule, "__name__", str(self.rule)))

    def get_grammar(
        self,
        analyzer: Any,
    ) -> Combinator:
        """
        Resuelve la gramática subyacente asociada a la regla referenciada.

        Args:
            analyzer: Analizador sintáctico activo con el registro de reglas.

        Returns:
            Combinator: Combinador raíz que define la gramática de la regla.

        Raises:
            GrammarError: Si la regla no tiene gramática definida o no existe.
        """
        # 1. Regla con gramática declarada directamente en la clase o instancia
        grammar = getattr(self.rule, "grammar", None)
        if grammar is not None:
            return grammar

        # 2. Búsqueda en el diccionario activo de la gramática del analizador
        analyzer_grammar = getattr(analyzer, "grammar", {})
        if isinstance(analyzer_grammar, dict):
            if self.rule in analyzer_grammar:
                return analyzer_grammar[self.rule]

            # 3. Búsqueda por nombre de regla
            for rule_key, rule_grammar in analyzer_grammar.items():
                key_name = getattr(rule_key, "name", getattr(rule_key, "__name__", str(rule_key)))
                if key_name == self.rule_name:
                    return rule_grammar

        target_node = self._get_node(analyzer)
        if target_node and getattr(config, "PARSER_ADD_ERROR", True):
            target_node.note(
                f"Referencia no resuelta: la regla {self.rule_name!r} no posee gramática",
                "Error",
            )

        error.GrammarError(
            "Regla no encontrada",
            errors.RULE_NOT_FOUND,
            f"No se encontró la definición gramatical para la regla referenciada {self.rule_name!r}.",
            f"Asegúrese de asociar una expresión gramatical a {self.rule_name!r}.",
        ).raise_error()

    def parse(
        self,
        analyzer: ASTAnalyzer | Parser | Any,
        current: TokenType | None = None,
        ignore_errors: bool = False,
    ) -> Any:
        """
        Ejecuta el análisis sintáctico resolviendo la regla referenciada.

        Args:
            analyzer: Analizador sintáctico o parser activo.
            current: Token actual posicionado o None.
            ignore_errors: Si True, no levanta excepciones ante fallos sintácticos.

        Returns:
            Any: ASTNode construido o resultado de la evaluación del combinador.
        """
        target_node = self._get_node(analyzer)

        if target_node and getattr(config, "PARSER_ADD_INFO", True):
            target_node.note(
                f"Resolviendo referencia: {self.rule_name}",
                "Normal",
            )

        grammar = self.get_grammar(analyzer)
        is_structural = getattr(self.rule, "is_structural", False)

        if (
            hasattr(analyzer, "process_rule")
            and not is_structural
            and not isinstance(self.rule, str)
        ):
            return analyzer.process_rule(
                self.rule,
                grammar,
                current,
                ignore_errors=ignore_errors,
            )

        return self._dispatch_sub(
            grammar,
            analyzer,
            current,
            ignore_errors=ignore_errors,
        )

    def __repr__(self) -> str:
        return f"<Ref> -> {self.rule_name}"


# Alias idiomático
Reference = Ref


__all__ = [
    "Ref",
    "Reference",
]
