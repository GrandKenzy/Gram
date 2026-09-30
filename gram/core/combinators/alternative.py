"""
EN:
    Alternative Combinator (`gram.core.combinators.alternative`).
    =============================================================
    Defines the syntactic branching combinator (Alt / Alternative).
    Evaluates candidate combinators in priority order and returns the result of the first
    successful branch. If a branch fails, automatically backtracks the parser cursor
    and attempts the subsequent alternative.

ES:
    Combinador de Alternativas (`gram.core.combinators.alternative`).
    ================================================================
    Define el combinador de bifurcación sintáctica (Alt / Alternative).
    Evalúa los combinadores candidatos en orden y retorna el resultado de la primera
    alternativa exitosa. Si una alternativa fracasa, retrocede automáticamente
    el cursor del parser (backtracking) e intenta con la siguiente.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from gram import config, errors
from gram.core.combinators.base import Combinator
from gram.core.combinators.optional import OptResult
from gram.core.combinators.signals import AbortFlowSignal, CutFlowSignal
from gram.utilities import error

if TYPE_CHECKING:
    from gram.core.ast import ASTAnalyzer
    from gram.core.lexer.tokens import TokenType
    from gram.core.parser.core import Parser


class Alt(Combinator):
    """
    EN:
        Alternative combinator (logical OR branch).
        Evaluates candidate combinators in sequential order until the first
        match succeeds on the token stream. If a candidate fails, automatically
        backtracks cursor state to savepoint and attempts the next candidate.

    ES:
        Combinador de alternativas (o / or).
        Evalúa los combinadores candidatos en orden secuencial hasta encontrar
        el primero que coincida con éxito con el flujo de tokens.
        Si una alternativa no empareja, realiza backtracking automático restaurando
        el estado del cursor y prueba la alternativa siguiente.
    """

    def __init__(self, *combinators: Combinator) -> None:
        """
        EN: Initialize alternative combinator with candidate branches.
        ES: Inicializa el combinador con una lista de alternativas posibles.

        Args:
            *combinators: One or more candidate combinator branches.
                          Uno o más combinadores candidatos.

        Raises:
            ParserError: If no candidate combinator is provided.
                         Si no se proporciona ninguna alternativa.
        """
        if not combinators:
            error.ParserError(
                "Alternativas vacías",
                errors.COMBINATOR_FAILED,
                "El combinador Alt() requiere al menos una alternativa.",
            ).raise_error()

        self.combinators: tuple[Combinator, ...] = tuple(combinators)

    def parse(
        self,
        analyzer: ASTAnalyzer | Parser | Any,
        current: TokenType | None = None,
        ignore_errors: bool = False,
    ) -> Any:
        """
        EN: Try each candidate alternative in order until a match is found.
        ES: Prueba cada alternativa candidata en orden hasta encontrar una coincidencia.

        Args:
            analyzer: Active syntax analyzer or Parser instance.
                      Instancia del analizador sintáctico o parser.
            current: Current token available under cursor or None.
                     Token actual disponible en la posición inicial o None.
            ignore_errors: If True, suppress syntax error exceptions on branch failure.
                           Si True, no levanta excepciones ante la falta de coincidencia.

        Returns:
            Result of the first matching branch, or None if none matched.
            El resultado del primer combinador que haya coincidido, o None si ninguno lo hizo.
        """
        parser = self._get_parser(analyzer)
        target_node = self._get_node(analyzer)

        if target_node and getattr(config, "PARSER_ADD_INFO", True):
            target_node.note(
                f"ALT iniciado con {len(self.combinators)} alternativas",
                "Normal",
            )

        checkpoint = parser.savepoint(node=target_node)

        for index, combinator in enumerate(self.combinators, start=1):
            if target_node and getattr(config, "PARSER_ADD_INFO", True):
                target_node.note(
                    f"Probando alternativa {index}: {combinator!r}",
                    "Normal",
                )

            # Restaurar el estado del cursor antes de evaluar cada rama
            parser.restore(checkpoint, node=target_node)

            try:
                res = self._dispatch_sub(
                    combinator,
                    analyzer,
                    current,
                    ignore_errors=True,
                )
            except CutFlowSignal:
                if target_node and getattr(config, "PARSER_ADD_INFO", True):
                    target_node.note("Corte de flujo (CutFlowSignal) detectado en alternativa.", "Advice")
                parser.restore(checkpoint, node=target_node)
                if not ignore_errors:
                    error.ParserError(
                        "Corte de alternativas por señal CutFlowSignal",
                        errors.COMBINATOR_FAILED,
                    ).raise_error()
                return None
            except AbortFlowSignal:
                parser.restore(checkpoint, node=target_node)
                raise

            if res is not None:
                if isinstance(res, OptResult) and not res.matched:
                    continue

                if target_node and getattr(config, "PARSER_ADD_INFO", True):
                    target_node.note(
                        f"Alternativa {index} aceptada",
                        "Success",
                    )

                return res

            if target_node and getattr(config, "PARSER_ADD_INFO", True):
                target_node.note(
                    f"Alternativa {index} rechazada",
                    "Advice",
                )

        # Restaurar estado inicial al fracasar todas las alternativas
        parser.restore(checkpoint, node=target_node)

        if not ignore_errors:
            tried = [repr(c).splitlines()[0].strip() for c in self.combinators]
            tried_str = ", ".join(tried)
            curr_tok = current or parser.peek()
            tok_info = f" en {curr_tok}" if curr_tok else ""

            if target_node and getattr(config, "PARSER_ADD_ERROR", True):
                target_node.note(
                    f"Ninguna alternativa coincidió{tok_info}",
                    "Error",
                )

            error.ParserError(
                "Alternativa no encontrada",
                errors.PARSER_UNEXPECTED_TOKEN,
                f"Ninguna alternativa sintáctica coincidió{tok_info}. Candidatos: [{tried_str}].",
            ).raise_error()

        return None

    def items(self) -> tuple[Combinator, ...]:
        """
        EN: Return candidate combinators contained in this alternative rule.
        ES: Retorna las alternativas contenidas en la regla.
        """
        return self.combinators

    def __iter__(self):
        return iter(self.combinators)

    def __len__(self) -> int:
        return len(self.combinators)

    def __repr__(self) -> str:
        items = ", ".join(repr(c) for c in self.combinators)
        return f"Alt({items})"


# Alias canónico
Alternative = Alt


__all__ = ["Alt", "Alternative"]
