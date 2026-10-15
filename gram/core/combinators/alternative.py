"""
Alternative Combinator (`gram.core.combinators.alternative`).
=============================================================
Defines the syntactic branching combinator (`Alt`). Evaluates candidate
combinators in priority order inside a reentrant `safe_mode` context and
surfaces the deepest atomic failure if all candidate branches are rejected.
"""
from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

from gram import errors
from gram.core.combinators.base import Combinator
from gram.core.combinators.signals import BacktrackSignal, CutFlowSignal

if TYPE_CHECKING:
    from gram.core.ast import ASTAnalyzer


class Alt(Combinator):
    """
    Alternative combinator (logical OR branch).

    Evaluates candidate combinators sequentially until the first match succeeds.
    If all candidates fail, promotes or stages the deepest candidate error
    recorded across the attempted branches.
    """

    header_class: bool = True

    def __init__(self, *combinators: Combinator, ignore: bool = False) -> None:
        """
        Initialize the alternative combinator with one or more candidate branches.

        Args:
            *combinators (Combinator): Candidate combinator branches to evaluate in order.
            ignore (bool): Whether to ignore this combinator in raytracing.
        """
        super().__init__(ignore=ignore)
        if not combinators:
            errors.GrammarError(
                "EmptyAlternatives",
                errors.GRAMMAR_COMBINATOR_FAILED,
                "El combinador Alt() requiere al menos una alternativa.",
                "Proporcione uno o más combinadores candidatos dentro de Alt(...).",
            ).raise_error()

        self.combinators: tuple[Combinator, ...] = tuple(combinators)

    def parse(self, analyzer: ASTAnalyzer) -> Any:
        """
        Evaluate candidate branches sequentially until one matches.

        Args:
            analyzer (ASTAnalyzer): Active AST analyzer instance.

        Returns:
            Any: Result of the first matching branch, or `None` if all branches fail.
        """
        parser = analyzer.parser
        father = parser.node(
            "ProcessingAlt", "Procesando combinador de Alternativas", set_target=True
        )
        analyzer.debug(f"Procesando ALT con {len(self.combinators)} alternativas")

        checkpoint = parser.savepoint("ALT-Analysis")
        # [RayTracing/Diagnostics Isolation] Guardar el estado previo de _staged_failure
        # para aislar las ramas especulativas y no contaminar combinadores (ej. Opt) en ramas posteriores.
        saved_staged = analyzer._staged_failure
        best_staged = saved_staged

        try:
            for index, combinator in enumerate(self.combinators, start=1):
                father.note(
                    f"Probando alternativa No. {index}: {combinator.type()}",
                    "normal",
                )
                # Aislar cada intento: restablecer el fallo preparado para que el intento anterior
                # no deje residuos de mayor peso que hagan fallar erróneamente combinadores opcionales.
                analyzer._staged_failure = saved_staged
                try:
                    with analyzer.safe_mode():
                        res = analyzer.visitor(combinator)
                except BacktrackSignal:
                    res = None
                except CutFlowSignal:
                    parser.restore(checkpoint)
                    father.note(
                        f"Corte (CutFlowSignal) activado en alternativa No. {index}; abortando backtracking.",
                        "warn",
                    )
                    break

                if res is None:
                    father.note(f"Alternativa No. {index} rechazada", "normal")
                    # Registrar el fallo que mayor profundidad de tokens alcanzó (mayor peso)
                    # para ofrecer el mejor diagnóstico posible si todas las alternativas fallan.
                    curr_staged = analyzer._staged_failure
                    if curr_staged is not None:
                        if best_staged is None or curr_staged[0] > best_staged[0]:
                            best_staged = curr_staged
                    parser.restore(checkpoint)
                    continue

                father.note(f"Alternativa No. {index} aceptada", "success")
                analyzer.discard_staged_failure(min_weight=parser.pos)
                return res

            # Si todas las alternativas fueron rechazadas, restaurar el fallo más profundo
            # para que el reporte de errores y los hooks de diagnóstico muestren la causa más cercana.
            analyzer._staged_failure = best_staged
            father.note("Todas las alternativas fueron rechazadas", "error")
            curr_tok = parser.peek() if not parser.empty() else None
            tok_info = (
                f" en línea {curr_tok.line}, columna {curr_tok.col} ({curr_tok.token.name})"
                if curr_tok is not None
                else ""
            )
            fallback = errors.GrammarError(
                "NoAlternativeMatched",
                errors.GRAMMAR_COMBINATOR_FAILED,
                f"Ninguna de las {len(self.combinators)} alternativas coincidió{tok_info}.",
                "Verifique que la expresión coincida con alguna de las reglas permitidas.",
            )

            if analyzer.safe_flag:
                analyzer.stage_failure(fallback, weight=checkpoint.pos)
            else:
                analyzer.flush_failure(fallback=fallback)

            return None
        finally:
            parser.down()

    def items(self) -> tuple[Combinator, ...]:
        """Return the tuple of candidate combinators in this alternative."""
        return self.combinators

    def __iter__(self) -> Iterator[Combinator]:
        return iter(self.combinators)

    def __len__(self) -> int:
        return len(self.combinators)

    def __repr__(self) -> str:
        items = ", ".join(repr(c) for c in self.combinators)
        return f"Alt({items})"


__all__ = ["Alt"]