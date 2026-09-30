"""
Pila Adicional de Combinadores (`gram.core.combinators.additional_stack`).
========================================================================
Proporciona el registro central `CombinatorAdditionalStack` para admitir combinadores
personalizados provenientes de plugins o extensiones, desacoplándolos del núcleo.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from gram.core.ast import ASTAnalyzer
    from gram.core.combinators.base import Combinator
    from gram.core.lexer.tokens import TokenType
    from gram.core.parser.core import Parser


class CombinatorAdditionalStack:
    """
    ES:
        Pila y registro central de combinadores adicionales (de plugins o extensiones).
        Permite extender el catálogo de combinadores sin modificar el núcleo del framework.

    EN:
        Central registry and stack for custom/plugin combinator extensions.
    """

    _registered: list[type[Combinator] | Combinator] = []
    _handlers: dict[type[Combinator], Callable[[Any, Any, TokenType | None, bool], Any]] = {}

    @classmethod
    def register(
        cls,
        combinator_type_or_instance: type[Combinator] | Combinator,
        handler: Callable[[Any, Any, TokenType | None, bool], Any] | None = None,
    ) -> None:
        """
        Registra un combinador o clase de combinador en la pila adicional.

        Args:
            combinator_type_or_instance: Instancia o tipo de combinador a registrar.
            handler: Función despachadora opcional para procesar el combinador.
        """
        if combinator_type_or_instance not in cls._registered:
            cls._registered.append(combinator_type_or_instance)
        if handler is not None and isinstance(combinator_type_or_instance, type):
            cls._handlers[combinator_type_or_instance] = handler

    @classmethod
    def unregister(cls, combinator_type_or_instance: type[Combinator] | Combinator) -> bool:
        """
        Elimina un combinador de la pila adicional.

        Args:
            combinator_type_or_instance: Combinador a desregistrar.

        Returns:
            bool: True si fue encontrado y eliminado, False si no existía.
        """
        if combinator_type_or_instance in cls._registered:
            cls._registered.remove(combinator_type_or_instance)
            if isinstance(combinator_type_or_instance, type) and combinator_type_or_instance in cls._handlers:
                del cls._handlers[combinator_type_or_instance]
            return True
        return False

    @classmethod
    def has(cls, combinator: Any) -> bool:
        """
        Determina si un combinador o su tipo pertenece a la pila adicional.

        Args:
            combinator: Instancia o tipo a consultar.

        Returns:
            bool: True si está registrado.
        """
        for item in cls._registered:
            if isinstance(item, type) and isinstance(combinator, item):
                return True
            if item is combinator:
                return True
        return False

    @classmethod
    def process(
        cls,
        combinator: Any,
        analyzer: ASTAnalyzer | Parser | Any,
        current: TokenType | None = None,
        ignore_errors: bool = False,
    ) -> Any:
        """
        Procesa el combinador adicional contra el analizador y el token actual.

        Args:
            combinator: Combinador a ejecutar.
            analyzer: Analizador sintáctico o parser activo.
            current: Token léxico actual o None.
            ignore_errors: Si True, no levanta excepciones ante discrepancias.

        Returns:
            Any: Resultado de la ejecución del combinador o su handler.

        Raises:
            TypeError: Si el objeto no tiene método parse() ni handler registrado.
        """
        # 1. Si existe un handler específico registrado por tipo
        for comb_type, handler in cls._handlers.items():
            if isinstance(combinator, comb_type):
                return handler(combinator, analyzer, current, ignore_errors)

        # 2. Si es una instancia de Combinator, invoca su método estándar parse()
        if hasattr(combinator, "parse"):
            return combinator.parse(analyzer, current, ignore_errors=ignore_errors)

        raise TypeError(
            f"El combinador adicional {combinator!r} no cuenta con método parse() ni handler registrado."
        )

    @classmethod
    def all(cls) -> list[type[Combinator] | Combinator]:
        """Retorna copia de los combinadores registrados."""
        return cls._registered.copy()

    @classmethod
    def clear(cls) -> None:
        """Limpia todos los combinadores adicionales registrados."""
        cls._registered.clear()
        cls._handlers.clear()


__all__ = [
    "CombinatorAdditionalStack",
]
