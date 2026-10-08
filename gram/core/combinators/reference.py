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

    def __init__(
        self,
        rule: RuleType,
        generate_node: bool = False,
        name: str | None = None,
    ) -> None:
        """
        Inicializa la referencia a una regla gramatical.

        Args:
            rule: Clase de regla (RuleType), subclase de RuleItem, instancia o nombre en cadena.
            generate_node: Si es True, genera un RefNode al analizar con ASTAnalyzer.
            name: Nombre opcional para el RefNode generado.
        """
        self.rule: RuleType = rule
        self.generate_node: bool = generate_node
        self.name: str | None = name

    @property
    def rule_name(self) -> str:
        """Retorna el nombre descriptivo de la regla referenciada."""
        if isinstance(self.rule, str):
            return self.rule
        return self.rule.name or self.rule.__name__

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
        grammar = None if isinstance(self.rule, str) else self.rule.grammar
        if grammar is not None:
            return grammar

        # 2. Búsqueda en el diccionario activo de la gramática del analizador
        parser = self._get_parser(analyzer)
        analyzer_grammar = {} if analyzer is parser else analyzer.grammar
        if isinstance(analyzer_grammar, dict):
            if self.rule in analyzer_grammar:
                return analyzer_grammar[self.rule]

            # 3. Búsqueda por nombre de regla
            for rule_key, rule_grammar in analyzer_grammar.items():
                key_name = (
                    rule_key
                    if isinstance(rule_key, str)
                    else rule_key.name or rule_key.__name__
                )
                if key_name == self.rule_name:
                    return rule_grammar

        target_node = self._get_node(analyzer)
        if config.PARSER_ADD_ERROR:
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

        if config.PARSER_ADD_INFO:
            target_node.note(
                f"Resolviendo referencia: {self.rule_name}",
                "Normal",
            )

        grammar = self.get_grammar(analyzer)
        is_structural = (
            False if isinstance(self.rule, str) else self.rule.is_structural
        )

        if analyzer is not self._get_parser(analyzer) and (
            self.generate_node
            or (not is_structural and not isinstance(self.rule, str))
        ):
            return analyzer.process_rule(
                self.rule,
                grammar,
                current,
                ignore_errors=ignore_errors,
                generate_node=self.generate_node,
                node_name=self.name,
            )

        return self._dispatch_sub(
            grammar,
            analyzer,
            current,
            ignore_errors=ignore_errors,
        )

    def __repr__(self) -> str:
        options = []
        if self.generate_node:
            options.append("generate_node=True")
        if self.name is not None:
            options.append(f"name={self.name!r}")
        suffix = f", {', '.join(options)}" if options else ""
        return f"<Ref> -> {self.rule_name}{suffix}"


# Alias idiomático
Reference = Ref


__all__ = [
    "Ref",
    "Reference",
]
