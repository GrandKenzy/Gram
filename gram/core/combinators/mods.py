"""
Módulo de Clasificación y Registro de Combinadores (`gram.core.combinators.mods`).
=================================================================================
Formaliza la distinción de diseño entre:
- **Hardcoded Mods**: Combinadores nativos reconocidos de forma fija en el núcleo
  (`Seq`, `Alt`, `MatchToken`, `MatchKeyword`, `Enclosed`, `Separator`, etc.).
- **Custom Mods**: Combinadores extensibles que utilizan la API de integración de
  Gram para operar casi de forma nativa sin alterar el código fuente del núcleo.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, TypeVar

from gram.core.combinators.additional_stack import CombinatorAdditionalStack
from gram.core.combinators.alternative import Alt
from gram.core.combinators.any_grammar import AnyGrammar
from gram.core.combinators.base import Combinator
from gram.core.combinators.enclosed import Enclosed
from gram.core.combinators.item import Item, Literal
from gram.core.combinators.many import Many
from gram.core.combinators.match import (
    MatchGroup,
    MatchKeyword,
    MatchSeqSymbol,
    MatchToken,
)
from gram.core.combinators.optional import Opt
from gram.core.combinators.reference import Ref
from gram.core.combinators.separator import Separator
from gram.core.combinators.sequence import Seq
from gram.core.combinators.some import Some
from gram.core.combinators.tokenize import Tokenize

if TYPE_CHECKING:
    from gram.core.ast import ASTAnalyzer
    from gram.core.lexer.tokens import TokenType

T = TypeVar("T", bound=type[Combinator])

# =============================================================================
# 1. HARDCODED MODS (COMBINADORES NATIVOS DEL NÚCLEO)
# =============================================================================

HARDCODED_MODS: tuple[type[Combinator], ...] = (
    Alt,
    AnyGrammar,
    Enclosed,
    Item,
    Literal,
    Many,
    MatchGroup,
    MatchKeyword,
    MatchSeqSymbol,
    MatchToken,
    Opt,
    Ref,
    Separator,
    Seq,
    Some,
    Tokenize,
)


def is_hardcoded_mod(obj: Any) -> bool:
    """
    Verifica si un combinador (clase o instancia) pertenece exactamente a los
    combinadores nativos/hardcoded del framework Gram.
    """
    if CombinatorAdditionalStack.has(obj):
        return False
    if isinstance(obj, type):
        return obj in HARDCODED_MODS
    return type(obj) in HARDCODED_MODS


def get_hardcoded_mods() -> tuple[type[Combinator], ...]:
    """Retorna la tupla canónica de combinadores hardcoded del framework."""
    return HARDCODED_MODS


# =============================================================================
# 2. CUSTOM MODS (API DE INTEGRACIÓN EXTENSIBLE)
# =============================================================================

def register_custom_mod(
    combinator_type_or_instance: type[Combinator] | Combinator,
    handler: Callable[[Any, Any, TokenType | None, bool], Any] | None = None,
    name: str | None = None,
) -> type[Combinator] | Combinator:
    """
    Registra un combinador extensible ('custom mod') en el ecosistema Gram.

    Args:
        combinator_type_or_instance: Clase derivada de Combinator o instancia a registrar.
        handler: Función despachadora opcional para personalizar su ejecución.
        name: Nombre descriptivo opcional para telemetría y diagnóstico.

    Returns:
        El combinador o clase registrada para permitir su uso como decorador.
    """
    if name is not None:
        setattr(combinator_type_or_instance, "name", name)

    CombinatorAdditionalStack.register(combinator_type_or_instance, handler=handler)
    return combinator_type_or_instance


def custom_mod(
    cls_or_name: T | str | None = None,
) -> Callable[[T], T] | T:
    """
    Decorador para clases de combinadores que las registra automáticamente
    como Custom Mods en la API de integración de Gram.

    Uso:
        @custom_mod
        class MiCombinador(Combinator):
            def parse(self, analyzer, current=None, ignore_errors=False):
                ...
    """
    if isinstance(cls_or_name, type):
        register_custom_mod(cls_or_name)
        return cls_or_name

    def decorator(cls: T) -> T:
        name = cls_or_name if isinstance(cls_or_name, str) else None
        register_custom_mod(cls, name=name)
        return cls

    return decorator


def is_custom_mod(obj: Any) -> bool:
    """
    Verifica si un combinador (clase o instancia) está reconocido como un Custom Mod
    en la pila adicional o hereda de Combinator sin pertenecer a HARDCODED_MODS.
    """
    if is_hardcoded_mod(obj):
        return False
    if CombinatorAdditionalStack.has(obj):
        return True
    if isinstance(obj, type) and issubclass(obj, Combinator):
        return hasattr(obj, "parse")
    return isinstance(obj, Combinator) and hasattr(obj, "parse")


def get_custom_mods() -> list[type[Combinator] | Combinator]:
    """Retorna una lista con todos los combinadores registrados como Custom Mods."""
    return CombinatorAdditionalStack.all()


__all__ = [
    "HARDCODED_MODS",
    "is_hardcoded_mod",
    "get_hardcoded_mods",
    "register_custom_mod",
    "custom_mod",
    "is_custom_mod",
    "get_custom_mods",
]
