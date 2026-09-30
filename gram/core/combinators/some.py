"""
EN:
    One-or-More Repetition Combinator (`gram.core.combinators.some`).
    ================================================================
    Defines non-empty repetition (1..n or regex plus +).
    Requires at least one mandatory match to succeed.
    If zero matches occur, restores parser state and returns None or raises
    a syntax error depending on ignore_errors.

ES:
    Combinador de Repetición Una o Más Veces (`gram.core.combinators.some`).
    ========================================================================
    Define el combinador de repetición no vacía (1..n o signo +).
    Requiere al menos una coincidencia obligatoria para tener éxito.
    Si no coincide al menos una vez, restaura la posición del parser y
    retorna None o levanta un error sintáctico según ignore_errors.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from gram import config, errors
from gram.core.combinators.base import Combinator
from gram.core.combinators.optional import OptResult
from gram.core.combinators.signals import AbortFlowSignal, BreakFlowSignal, SkipFlowSignal
from gram.utilities import error

if TYPE_CHECKING:
    from gram.core.ast import ASTAnalyzer
    from gram.core.lexer.tokens import TokenType
    from gram.core.parser.core import Parser


class Some(Combinator):
    """
    EN:
        One-or-more repetition combinator (1..n / Kleene plus).
        Requires at least one mandatory occurrence of the inner combinator.
        Accumulates subsequent matches as long as they match on the token stream.

    ES:
        Combinador de repetición una o más veces (1..n).
        Exige al menos una coincidencia obligatoria del combinador interno.
        Acumula subsecuentes coincidencias mientras existan en el flujo de tokens.
    """

    def __init__(self, combinator: Combinator) -> None:
        """
        EN: Initialize mandatory repetition combinator with child combinator.
        ES: Inicializa el combinador de repetición obligatoria con el combinador hijo.

        Args:
            combinator: Syntactic combinator to repeat.
                        Combinador sintáctico a repetir.
        """
        self.combinator: Combinator = combinator

    def parse(
        self,
        analyzer: ASTAnalyzer | Parser | Any,
        current: TokenType | None = None,
        ignore_errors: bool = False,
    ) -> list[Any] | None:
        """
        EN: Execute inner combinator requiring at least one match.
        ES: Ejecuta el combinador exigiendo al menos 1 coincidencia.

        Args:
            analyzer: Active syntax analyzer or Parser instance.
                      Instancia del analizador sintáctico o parser.
            current: Current token available under cursor or None.
                     Token actual disponible en la posición inicial o None.
            ignore_errors: If True, suppress syntax exceptions on mismatch.
                           Si True, no levanta excepciones ante fallos.

        Returns:
            List of match results (at least 1 item) or None on failure.
            Lista con los resultados recolectados (mínimo 1 elemento) o None si no coincidió.
        """
        parser = self._get_parser(analyzer)
        target_node = self._get_node(analyzer)

        if target_node and getattr(config, "PARSER_ADD_INFO", True):
            target_node.note(
                f"SOME iniciado con {self.combinator!r}",
                "Normal",
            )

        initial_checkpoint = parser.savepoint(node=target_node)
        results: list[Any] = []
        active_token = current

        while True:
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
                parser.restore(initial_checkpoint, node=target_node)
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

        if not results:
            parser.restore(initial_checkpoint, node=target_node)

            if target_node and getattr(config, "PARSER_ADD_INFO", True):
                target_node.note(
                    f"SOME rechazado: se requería al menos 1 coincidencia para {self.combinator!r}",
                    "Warn",
                )

            if not ignore_errors:
                curr_tok = current or parser.peek()
                tok_info = f" en {curr_tok}" if curr_tok else ""
                error.ParserError(
                    "Ocurrencia mínima no alcanzada",
                    errors.COMBINATOR_FAILED,
                    f"Se esperaba al menos una ocurrencia de {self.combinator!r}{tok_info}.",
                ).raise_error()

            return None

        if target_node and getattr(config, "PARSER_ADD_INFO", True):
            target_node.note(
                f"SOME completado: {len(results)} coincidencias",
                "Success",
            )

        return results

    def __repr__(self) -> str:
        return f"Some({self.combinator!r})"


__all__ = ["Some"]
