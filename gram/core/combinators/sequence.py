"""
EN:
    Sequence Combinator (`gram.core.combinators.sequence`).
    =======================================================
    Concatenates multiple syntactic combinators in strict ordered succession.
    All combinators must match for the sequence to succeed; if any element fails,
    parser position is restored atomically to savepoint and results are discarded.

ES:
    Combinador de Secuencia (`gram.core.combinators.sequence`).
    ===========================================================
    Concatena múltiples combinadores sintácticos en orden estricto.
    Todos los combinadores deben coincidir para que la secuencia sea exitosa;
    si alguno falla, se restaura atómicamente la posición del parser y se descartan los resultados.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from gram import config, errors
from gram.core.combinators.base import Combinator
from gram.core.combinators.optional import OptResult
from gram.core.combinators.signals import BreakFlowSignal, SkipFlowSignal
from gram.utilities import error

if TYPE_CHECKING:
    from gram.core.ast import ASTAnalyzer
    from gram.core.lexer.tokens import TokenType
    from gram.core.parser.core import Parser


class Seq(Combinator):
    """
    EN:
        Strict ordered sequence combinator.
        Executes a sequence of combinators in strict order against the token stream.
        All elements must match. If any element fails, the parser state is restored
        atomically to the savepoint prior to sequence initiation.

    ES:
        Combinador de secuencia ordenada.
        Ejecuta una lista de combinadores en orden estricto contra el flujo de tokens.
        Todos deben coincidir. Si cualquiera falla, la secuencia retrocede
        atómicamente el parser al estado previo al inicio de la secuencia.
    """

    def __init__(self, *combinators: Combinator) -> None:
        """
        EN: Initialize sequence with child combinators.
        ES: Inicializa la secuencia con los combinadores hijos dados.

        Args:
            *combinators: One or more combinators to execute in sequential succession.
                          Uno o más combinadores a ejecutar secuencialmente.

        Raises:
            ParserError: If no child combinator is provided.
                         Si no se proporciona ningún combinador.
        """
        if not combinators:
            error.ParserError(
                "Secuencia vacía",
                errors.COMBINATOR_FAILED,
                "La secuencia Seq() requiere al menos un combinador.",
            ).raise_error()

        self.combinators: tuple[Combinator, ...] = tuple(combinators)

    def parse(
        self,
        analyzer: ASTAnalyzer | Parser | Any,
        current: TokenType | None = None,
        ignore_errors: bool = False,
    ) -> list[Any] | None:
        """
        EN: Parse token stream by executing each combinator in strict succession.
        ES: Analiza el flujo de tokens ejecutando cada combinador en orden estricto.

        Args:
            analyzer: Active syntax analyzer or Parser instance.
                      Instancia del analizador sintáctico o parser.
            current: Current token available under cursor or None.
                     Token actual disponible en la posición inicial o None.
            ignore_errors: If True, suppress syntax error exceptions on match failure.
                           Si True, no levanta excepciones ante fallos de coincidencia.

        Returns:
            List of element match results on success, or None on failure.
            Lista con los resultados de cada combinador si tuvo éxito, o None si falló.
        """
        parser = self._get_parser(analyzer)
        target_node = self._get_node(analyzer)

        if target_node and getattr(config, "PARSER_ADD_INFO", True):
            target_node.note(
                f"SEQ iniciado con {len(self.combinators)} combinadores",
                "Normal",
            )

        checkpoint = parser.savepoint(node=target_node)
        results: list[Any] = []

        watcher = getattr(analyzer, "watcher", None)
        if watcher:
            watcher.enter_sequence(self, len(self.combinators))

        try:
            for index, combinator in enumerate(self.combinators, start=1):
                if watcher:
                    watcher.step_sequence(index)

                # El primer combinador puede recibir current; los siguientes consumen del parser
                active_token = current if index == 1 else None

                try:
                    res = self._dispatch_sub(
                        combinator,
                        analyzer,
                        active_token,
                        ignore_errors=ignore_errors,
                    )
                except (SkipFlowSignal, BreakFlowSignal):
                    if target_node and getattr(config, "PARSER_ADD_INFO", True):
                        target_node.note(
                            f"Señal de interrupción en paso {index} de secuencia; finalizando temprano.",
                            "Advice",
                        )
                    return results

                if res is None:
                    parser.restore(checkpoint, node=target_node)

                    if target_node and getattr(config, "PARSER_ADD_INFO", True):
                        target_node.note(
                            f"SEQ abortado: el elemento {index} ({combinator!r}) no coincidió",
                            "Warn",
                        )

                    if not ignore_errors:
                        curr_tok = parser.peek()
                        tok_info = f" en {curr_tok}" if curr_tok else ""
                        error.ParserError(
                            "Fallo en secuencia",
                            errors.COMBINATOR_FAILED,
                            f"Fallo en elemento {index} de secuencia Seq({combinator!r}){tok_info}.",
                        ).raise_error()

                    return None

                if isinstance(res, OptResult):
                    results.append(res.value if res.matched else None)
                else:
                    results.append(res)

            if target_node and getattr(config, "PARSER_ADD_INFO", True):
                target_node.note(
                    f"SEQ completado correctamente ({len(self.combinators)} elementos)",
                    "Success",
                )

            return results

        except error.ParserError:
            parser.restore(checkpoint, node=target_node)
            raise
        finally:
            if watcher:
                watcher.exit_sequence()

    def items(self) -> tuple[Combinator, ...]:
        """
        EN: Return child combinators that comprise this sequence.
        ES: Retorna los combinadores que integran la secuencia.
        """
        return self.combinators

    def __iter__(self):
        return iter(self.combinators)

    def __len__(self) -> int:
        return len(self.combinators)

    def __repr__(self) -> str:
        items = ", ".join(repr(c) for c in self.combinators)
        return f"Seq({items})"


# Alias canónico
Sequence = Seq


__all__ = ["Seq", "Sequence"]
