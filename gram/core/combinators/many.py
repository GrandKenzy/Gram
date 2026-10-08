"""
EN:
    Zero-or-More Repetition Combinator (`gram.core.combinators.many`).
    ==================================================================
    Defines the arbitrary repetition combinator (0..n or Kleene star *).
    Accepts any number of consecutive matches of the inner combinator,
    accumulating results into a list. If zero matches occur, returns an empty
    list `[]` with syntactic success.

ES:
    Combinador de Repetición Cero o Más Veces (`gram.core.combinators.many`).
    ========================================================================
    Define el combinador de repetición arbitraria (0..n o estrella de Kleene *).
    Acepta cualquier cantidad de repeticiones consecutivas del combinador interno,
    acumulando los resultados en una lista. Si no coincide ninguna vez, retorna
    una lista vacía `[]` con éxito sintáctico.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from gram import config
from gram.core.combinators.base import Combinator
from gram.core.combinators.optional import OptResult
from gram.core.combinators.signals import AbortFlowSignal, BreakFlowSignal, SkipFlowSignal

if TYPE_CHECKING:
    from gram.core.ast import ASTAnalyzer
    from gram.core.lexer.tokens import TokenType
    from gram.core.parser.core import Parser


class Many(Combinator):
    """
    EN:
        Zero-or-more repetition combinator (Kleene star 0..n).
        Accepts any number of consecutive occurrences of the inner combinator.
        Returns a list of all accumulated match results. If zero occurrences match,
        returns an empty list `[]` with success.

    ES:
        Combinador de repetición cero o más veces (0..n).
        Acepta cualquier número de ocurrencias consecutivas del combinador interno.
        Retorna una lista con todos los resultados acumulados. Si no hay ocurrencias,
        retorna una lista vacía `[]` con éxito.
    """
    header_class: bool = True

    def __init__(self, combinator: Combinator) -> None:
        """
        EN: Initialize repetition combinator with target child combinator.
        ES: Inicializa el combinador de repetición con el combinador hijo a repetir.

        Args:
            combinator: Syntactic child combinator to repeat.
                        Combinador sintáctico a repetir.
        """
        self.header_class: bool = True
        self.combinator: Combinator = combinator

    def parse(
        self,
        analyzer: ASTAnalyzer | Parser | Any,
        current: TokenType | None = None,
        ignore_errors: bool = False,
    ) -> list[Any]:
        """
        EN: Execute inner combinator repeatedly while it continues to match.
        ES: Ejecuta el combinador repetidamente mientras continúe coincidiendo.

        Args:
            analyzer: Active syntax analyzer or Parser instance.
                      Instancia del analizador sintáctico o parser.
            current: Current token available under cursor or None.
                     Token actual disponible en la posición inicial o None.
            ignore_errors: If True, suppress syntax exceptions on mismatch.
                           Si True, no levanta excepciones ante fallos.

        Returns:
            List of accumulated match results (may be empty `[]`).
            Lista con los resultados recolectados (puede ser vacía `[]`).
        """
        parser = self._get_parser(analyzer)
        target_node = self._get_node(analyzer)

        if config.PARSER_ADD_INFO:
            target_node.note(
                f"MANY iniciado con {self.combinator!r}",
                "Normal",
            )

        results: list[Any] = []
        active_token = current

        while True:
            # Si ya no hay token activo ni tokens en el parser, salir
            if active_token is None and not parser.not_empty():
                break

            checkpoint = parser.savepoint(node=target_node)

            try:
                res = self._dispatch_sub(
                    self.combinator,
                    analyzer,
                    active_token,
                    ignore_errors=True,
                )
            except (BreakFlowSignal, SkipFlowSignal):
                parser.restore(checkpoint, node=target_node)
                break
            except AbortFlowSignal:
                parser.restore(checkpoint, node=target_node)
                raise

            if res is None or (isinstance(res, OptResult) and not res.matched):
                parser.restore(checkpoint, node=target_node)
                break

            # Salvaguarda contra bucles infinitos si el combinador no avanza el parser
            if parser.pos == checkpoint.pos and active_token is None:
                results.append(res)
                break

            results.append(res)
            active_token = None

        if config.PARSER_ADD_INFO:
            target_node.note(
                f"MANY finalizado: {len(results)} coincidencias acumuladas",
                "Success",
            )

        return results

    def __repr__(self) -> str:
        return f"Many({self.combinator!r})"


__all__ = ["Many"]
