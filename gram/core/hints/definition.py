"""
Definición de Pistas Virtuales e Inlay Hints (`gram.core.hints.definition`).
==========================================================================
Define las clases `Hints`, `VirtualHint` y la enumeración `InlayHintKind` para
la generación declarativa de pistas visuales virtuales en editores y LSP.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Callable


class InlayHintKind(IntEnum):
    """
    EN: Standard LSP 3.17 InlayHintKind enumeration.
    ES: Enumeración estándar InlayHintKind de LSP 3.17.
    """
    Type = 1       # Pistas de tipo (ej. ': int', '-> bool')
    Parameter = 2  # Nombres de parámetros (ej. 'ancho:')


@dataclass
class VirtualHint:
    """
    EN: Concrete instance of a virtual inlay hint.
    ES: Instancia concreta de una pista virtual incrustada (Inlay Hint).
    """
    id: str
    line: int        # Índice de línea base 0
    character: int   # Índice de columna base 0
    text: str        # Etiqueta o texto a mostrar en el editor
    kind: int = InlayHintKind.Type
    padding_left: bool = True
    padding_right: bool = False
    description: str = ""
    is_physical: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_lsp_dict(self) -> dict[str, Any]:
        """
        EN: Formats the virtual hint into an official LSP InlayHint object with textEdits.
        ES: Formatea la pista virtual en un objeto oficial InlayHint de LSP con textEdits para materialización.
        """
        clean_text = self.text
        return {
            "position": {
                "line": self.line,
                "character": self.character,
            },
            "label": clean_text,
            "kind": int(self.kind),
            "paddingLeft": self.padding_left,
            "paddingRight": self.padding_right,
            "tooltip": {
                "kind": "markdown",
                "value": self.description or f"Pista inferida: `{clean_text}`",
            },
            "textEdits": [
                {
                    "range": {
                        "start": {"line": self.line, "character": self.character},
                        "end": {"line": self.line, "character": self.character},
                    },
                    "newText": clean_text,
                }
            ],
        }


class Hints:
    """
    EN:
        Declarative builder and provider for virtual hints in RuleItems.
        Associates token indices with processor functions that compute inferred text.

    ES:
        Constructor declarativo y proveedor de pistas virtuales para RuleItems.
        Asocia índices de tokens con funciones de procesamiento que computan texto inferido.
    """

    def __init__(
        self,
        processor: Callable[[Any], str | None],
        kind: int | InlayHintKind = InlayHintKind.Type,
        padding_left: bool = True,
        padding_right: bool = False,
        description: str = "",
        **metadata: Any,
    ) -> None:
        """
        EN: Initializes a Hints definition with a processor callable.
        ES: Inicializa la definición de Hints con una función procesadora.
        """
        if not callable(processor):
            raise TypeError("El 'processor' de Hints debe ser una función o método invocable.")
        self.processor: Callable[[Any], str | None] = processor
        self.kind: int = int(kind)
        self.padding_left: bool = padding_left
        self.padding_right: bool = padding_right
        self.description: str = description
        self.metadata: dict[str, Any] = metadata

    @classmethod
    def new(
        cls,
        processor: Callable[[Any], str | None],
        kind: int | InlayHintKind = InlayHintKind.Type,
        padding_left: bool = True,
        padding_right: bool = False,
        description: str = "",
        **metadata: Any,
    ) -> Hints:
        """
        EN: Factory creating a new Hints processor definition for RuleItem.hints.
        ES: Crea una nueva definición de procesador Hints para RuleItem.hints.

        Args:
            processor: Función que recibe el token objetivo y retorna un str con la anotación inferida.
            kind: Tipo de pista (InlayHintKind.Type=1 o InlayHintKind.Parameter=2).
            padding_left: Si añade espacio antes de la pista en el editor.
            padding_right: Si añade espacio después de la pista.
            description: Descripción para el tooltip al pasar el cursor.

        Returns:
            Instancia configurada de Hints.
        """
        return cls(
            processor=processor,
            kind=kind,
            padding_left=padding_left,
            padding_right=padding_right,
            description=description,
            **metadata,
        )

    def process(self, token: Any) -> str | None:
        """
        EN: Executes the processor on target token and sanitizes the output string.
        ES: Ejecuta el procesador sobre el token objetivo y sanitiza el texto resultante.
        """
        try:
            raw_output = self.processor(token)
            if raw_output is None:
                return None
            clean_str = str(raw_output).strip()
            # Eliminar saltos de línea y retornos de carro (las pistas deben ser en una sola línea)
            clean_str = clean_str.replace("\r", "").replace("\n", " ").strip()
            if not clean_str:
                return None
            return clean_str
        except Exception:
            return None

    def __repr__(self) -> str:
        proc_name = getattr(self.processor, "__name__", str(self.processor))
        return f"<Hints processor={proc_name!r} kind={self.kind}>"


__all__ = [
    "Hints",
    "InlayHintKind",
    "VirtualHint",
]
