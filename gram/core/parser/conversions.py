"""Transferable logical token-conversion state."""
from __future__ import annotations

from collections.abc import Mapping

from gram.core.lexer import CustomToken, Token

ConversionTarget = Token | CustomToken


class ConversionState:
    """Explicit conversion state that can be copied between file parsers.

    A state is independent by default. Sharing only happens when the same
    instance is deliberately passed to multiple parses.
    """

    __slots__ = ("_conversions",)

    def __init__(
        self,
        conversions: Mapping[str, ConversionTarget] | ConversionState | None = None,
    ) -> None:
        self._conversions: dict[str, ConversionTarget] = {}
        if conversions is not None:
            self.replace(conversions)

    def export(self) -> dict[str, ConversionTarget]:
        """Return a detached dictionary snapshot suitable for a new parser."""
        return dict(self._conversions)

    def replace(
        self,
        conversions: Mapping[str, ConversionTarget] | ConversionState,
    ) -> None:
        """Replace this state with a detached copy of another state or mapping."""
        source = (
            conversions.export()
            if isinstance(conversions, ConversionState)
            else dict(conversions)
        )
        for name, target in source.items():
            self._validate(name, target)
        self._conversions = source

    def register(self, name: str, target: ConversionTarget, *, replace: bool = False) -> None:
        """Register one exact identifier conversion, rejecting conflicts by default."""
        self._validate(name, target)
        existing = self._conversions.get(name)
        if existing is not None and existing != target and not replace:
            raise ValueError(
                f"La conversión para {name!r} ya está registrada como {existing!r}."
            )
        self._conversions[name] = target

    def clear(self) -> None:
        """Remove every conversion from this state."""
        self._conversions.clear()

    def clone(self) -> ConversionState:
        """Return an independent copy of this state."""
        return ConversionState(self)

    @staticmethod
    def _validate(name: str, target: ConversionTarget) -> None:
        if not isinstance(name, str) or not name:
            raise ValueError("El nombre de conversión debe ser un str no vacío.")
        if not isinstance(target, (Token, CustomToken)):
            raise TypeError("El destino de conversión debe ser Token o CustomToken.")


__all__ = ["ConversionState", "ConversionTarget"]
