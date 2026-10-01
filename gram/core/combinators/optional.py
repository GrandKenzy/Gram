"""
EN:
    Optional Combinator (`gram.core.combinators.optional`).
    =======================================================
    Allows specifying rules or subtrees with optional cardinality (0..1).
    Evaluates the inner combinator; if it does not match, cleanly restores the
    parser cursor state and returns an `OptResult(matched=False, value=None)`
    without emitting syntax errors.

ES:
    Combinador Opcional (`gram.core.combinators.optional`).
    ======================================================
    Permite especificar reglas o subárboles sintácticos con cardinalidad opcional (0..1).
    Evalúa el combinador interno; si no coincide, restaura limpiamente el estado del cursor
    del parser y retorna un `OptResult(matched=False, value=None)` sin emitir errores.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from gram import config
from gram.core.combinators.base import Combinator
from gram.core.lexer.tokens import TokenType

if TYPE_CHECKING:
    from gram.core.ast import ASTAnalyzer
    from gram.core.parser.core import Parser


class OptResult:
    """
    EN:
        Result container for the Opt combinator evaluation.
        Always evaluates to True in boolean contexts to indicate that
        the optional rule evaluation completed with syntactic success.

    ES:
        Resultado de la evaluación del combinador Opt.
        Siempre evalúa como True en contextos booleanos para indicar que la
        evaluación de la regla opcional concluyó con éxito sintáctico.
    """

    def __init__(self, matched: bool, value: Any = None) -> None:
        self.matched: bool = matched
        self.value: Any = value

    def unwrap(self, default: Any = None) -> Any:
        """
        EN: Return recognized value if matched, or specified default.
        ES: Devuelve el valor reconocido si hubo coincidencia, o el valor por defecto.
        """
        return self.value if self.matched else default

    def __bool__(self) -> bool:
        return True

    def __eq__(self, other: object) -> bool:
        if isinstance(other, OptResult):
            return self.matched == other.matched and self.value == other.value
        return False

    def __repr__(self) -> str:
        return f"OptResult(matched={self.matched}, value={self.value!r})"


class Opt(Combinator):
    """
    EN:
        Optional combinator (0..1 occurrence).
        Evaluates inner combinator; on failure, atomically rewinds parser state
        and returns an OptResult indicating non-match without raising syntax errors.

    ES:
        Combinador opcional (cero o una ocurrencia).
        Evalúa el combinador interno; si fracasa, restaura atómicamente el estado del
        parser y retorna un OptResult indicando falta de coincidencia pero sin error.
    """
    header_class: bool = True

    def __init__(self, combinator: Combinator) -> None:
        """
        EN: Initialize optional combinator with target child combinator.
        ES: Inicializa el combinador opcional con el combinador interno.

        Args:
            combinator: Inner combinator to evaluate optionally.
                        Combinador interno a evaluar opcionalmente.
        """
        self.header_class: bool = True
        self.combinator: Combinator = combinator

    def parse(
        self,
        analyzer: ASTAnalyzer | Parser | Any,
        current: TokenType | None = None,
        ignore_errors: bool = False,
    ) -> OptResult:
        """
        EN: Execute optional evaluation against token stream.
        ES: Ejecuta la evaluación opcional contra el flujo de tokens.

        Args:
            analyzer: Active syntax analyzer or Parser instance.
                      Instancia activa del analizador sintáctico o parser.
            current: Current token available under cursor or None.
                     Token actual bajo el cursor o None.
            ignore_errors: Error tolerance indicator (always True internally).
                           Indicador de tolerancia a errores (siempre True internamente).

        Returns:
            OptResult with match status and recognized value.
            Contenedor OptResult con el estado de coincidencia y el valor obtenido.
        """
        parser = self._get_parser(analyzer)
        target_node = self._get_node(analyzer)

        if target_node and getattr(config, "PARSER_ADD_INFO", True):
            target_node.note(f"OPT iniciado con {self.combinator!r}", "Normal")

        checkpoint = parser.savepoint(node=target_node)

        # Siempre evalúa con ignore_errors=True
        try:
            result = self._dispatch_sub(
                self.combinator,
                analyzer,
                current,
                ignore_errors=True,
            )
        except Exception:
            parser.restore(checkpoint, node=target_node)
            raise

        if result is not None:
            if isinstance(result, OptResult) and not result.matched:
                parser.restore(checkpoint, node=target_node)
                if target_node and getattr(config, "PARSER_ADD_INFO", True):
                    target_node.note(
                        "OPT no encontró coincidencia; continuando sin consumir",
                        "Advice",
                    )
                return OptResult(matched=False, value=None)

            if target_node and getattr(config, "PARSER_ADD_INFO", True):
                target_node.note("OPT encontró coincidencia", "Success")
            return OptResult(matched=True, value=result)

        # Si no hubo coincidencia, restaurar exactamente el cursor
        parser.restore(checkpoint, node=target_node)

        if target_node and getattr(config, "PARSER_ADD_INFO", True):
            target_node.note(
                "OPT no encontró coincidencia; continuando sin consumir",
                "Advice",
            )

        return OptResult(matched=False, value=None)

    def __repr__(self) -> str:
        return f"Opt({self.combinator!r})"


# Alias de conveniencia
Optional = Opt


__all__ = [
    "Opt",
    "Optional",
    "OptResult",
]
