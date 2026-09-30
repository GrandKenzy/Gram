"""
Señales de Control de Flujo Sintáctico (`gram.core.combinators.signals`).
========================================================================
Define las excepciones especializadas de control de flujo utilizadas por los
combinadores para coordinar backtracking, saltos exitosos tempranos, cortes de poda
(cut/commit), rupturas de bucles de repetición y abortos críticos en el análisis.
"""
from __future__ import annotations

from typing import Any


class ControlFlowSignal(Exception):
    """
    ES:
        Señal base para el control de flujo interno de combinadores.
        No representa un error sintáctico, sino una directiva de control de ejecución.

    EN:
        Base signal for internal combinator flow control.
    """

    def __init__(self, message: str = "Control flow signal", payload: Any = None) -> None:
        super().__init__(message)
        self.message: str = message
        self.payload: Any = payload


class SkipFlowSignal(ControlFlowSignal):
    """
    ES:
        Señal emitida para solicitar la finalización temprana y exitosa
        de una secuencia o bloque de análisis sin marcar un fallo en el cursor.

    EN:
        Signal requesting early successful completion of a sequence.
    """

    def __init__(self, message: str = "Skip flow requested", payload: Any = None) -> None:
        super().__init__(message, payload)


class BreakFlowSignal(ControlFlowSignal):
    """
    ES:
        Señal emitida para ordenar la finalización inmediata de un bucle
        de repetición (Many, Some, Separator) sin revertir los elementos acumulados.

    EN:
        Signal to break repetition loops without rolling back accumulated elements.
    """

    def __init__(self, message: str = "Break repetition loop requested", payload: Any = None) -> None:
        super().__init__(message, payload)


class CutFlowSignal(ControlFlowSignal):
    """
    ES:
        Señal de corte (Commit / Cut) que compromete la alternativa actual
        e inhibe el backtracking posterior en combinadores de selección (Alt).

    EN:
        Cut / Commit signal committing current branch and preventing further backtracking.
    """

    def __init__(self, message: str = "Commit branch / Cut backtracking", payload: Any = None) -> None:
        super().__init__(message, payload)


class BacktrackSignal(ControlFlowSignal):
    """
    ES:
        Señal emitida para forzar explícitamente el retroceso y descarte
        de la rama actual en favor de la siguiente alternativa disponible.

    EN:
        Signal to explicitly trigger backtracking to next alternative.
    """

    def __init__(self, message: str = "Backtrack requested", payload: Any = None) -> None:
        super().__init__(message, payload)


class AbortFlowSignal(ControlFlowSignal):
    """
    ES:
        Señal de interrupción fatal e inmediata de todo el proceso de análisis
        sintáctico ante condiciones críticas o límites irrecuperables.

    EN:
        Signal for fatal, immediate abortion of the entire parsing process.
    """

    def __init__(self, message: str = "Abort parsing process", payload: Any = None) -> None:
        super().__init__(message, payload)


__all__ = [
    "ControlFlowSignal",
    "SkipFlowSignal",
    "BreakFlowSignal",
    "CutFlowSignal",
    "BacktrackSignal",
    "AbortFlowSignal",
]
