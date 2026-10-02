"""
Gestor de Pistas Virtuales e Inlay Hints (`gram.core.hints.manager`).
===================================================================
Provee la clase `VirtualHintManager` para insertar, eliminar, modificar,
consultar y materializar físicamente (`put`) pistas virtuales en el código fuente.
"""
from __future__ import annotations

from typing import Any
from gram.core.hints.definition import InlayHintKind, VirtualHint


class VirtualHintManager:
    """
    EN:
        Centralized manager for virtual inlay hints per document or session.
        Provides insertion, modification, removal, and physical materialization (`put`).

    ES:
        Gestor centralizado de pistas virtuales incrustadas por documento o sesión.
        Permite inserción, modificación, eliminación y materialización física (`put`).
    """

    def __init__(self) -> None:
        self._hints: dict[str, VirtualHint] = {}

    def insert_virtual(
        self,
        id: str | None = None,
        line: int = 0,
        character: int = 0,
        text: str = "",
        kind: int | InlayHintKind = InlayHintKind.Type,
        padding_left: bool = True,
        padding_right: bool = False,
        description: str = "",
        **metadata: Any,
    ) -> VirtualHint:
        """
        EN:
            Inserts or registers a virtual hint.

            Args:
                id: Optional tracking identifier. Defaults to f"{line}:{character}".
                line: 0-indexed line number.
                character: 0-indexed character column position.
                text: Inlay text to display.
                kind: Hint kind (Type=1 or Parameter=2).
                padding_left: Whether to render leading whitespace.
                padding_right: Whether to render trailing whitespace.
                description: Tooltip description for the hint.

        ES:
            Inserta o registra una pista virtual.

            Args:
                id: Identificador rastreable opcional. Por defecto es f"{line}:{character}".
                line: Línea de inserción base 0.
                character: Columna de inserción base 0.
                text: Texto de la pista a mostrar.
                kind: Tipo de pista (Type=1 o Parameter=2).
                padding_left: Si se visualiza espacio previo a la pista.
                padding_right: Si se visualiza espacio posterior a la pista.
                description: Descripción flotante para la pista.
        """
        clean_text = str(text).replace("\r", "").replace("\n", " ").strip()
        hint_id = str(id) if id is not None else f"{line}:{character}"

        hint = VirtualHint(
            id=hint_id,
            line=max(0, int(line)),
            character=max(0, int(character)),
            text=clean_text,
            kind=int(kind),
            padding_left=padding_left,
            padding_right=padding_right,
            description=description,
            metadata=metadata,
        )
        self._hints[hint_id] = hint
        return hint

    def remove_virtual(self, id: str) -> VirtualHint | None:
        """
        EN: Removes a virtual hint by its tracking identifier.
        ES: Elimina una pista virtual a partir de su identificador.
        """
        return self._hints.pop(str(id), None)

    def edit_virtual(self, id: str, new_text: str) -> VirtualHint | None:
        """
        EN: Modifies the text of an existing virtual hint.
        ES: Modifica el contenido textual de una pista virtual existente.
        """
        hint = self._hints.get(str(id))
        if hint is not None:
            clean_text = str(new_text).replace("\r", "").replace("\n", " ").strip()
            hint.text = clean_text
            return hint
        return None

    def get(self, id: str) -> VirtualHint | None:
        """Obtiene una pista virtual por su ID."""
        return self._hints.get(str(id))

    def has(self, id: str) -> bool:
        """Verifica si existe una pista con el ID especificado."""
        return str(id) in self._hints

    def clear(self) -> None:
        """Limpia todas las pistas virtuales registradas."""
        self._hints.clear()

    def count(self) -> int:
        """Cantidad de pistas virtuales activas."""
        return len(self._hints)

    def all_hints(self) -> list[VirtualHint]:
        """Retorna todas las pistas virtuales activas ordenadas por posición (línea, carácter)."""
        return sorted(self._hints.values(), key=lambda h: (h.line, h.character))

    def put(self, id: str, source_code: str) -> str:
        """
        EN:
            Materializes a virtual hint into real physical source code.
            Inserts the hint text into the target line and character column.

        ES:
            Pasa una pista de virtual a física sobre el código fuente real.
            Inserta el texto del hint en la línea y columna exactas.

        Args:
            id: Identificador de la pista virtual a materializar.
            source_code: Código fuente completo.

        Returns:
            Código fuente con el texto del hint insertado físicamente.
        """
        hint = self._hints.get(str(id))
        if hint is None or not hint.text:
            return source_code

        eol = "\r\n" if "\r\n" in source_code else "\n"
        lines = source_code.split(eol)

        if 0 <= hint.line < len(lines):
            target_line = lines[hint.line]
            col = min(len(target_line), hint.character)

            # Inserción limpia respetando espaciado
            insert_str = hint.text
            if hint.padding_left and col > 0 and target_line[col - 1] != " ":
                if not insert_str.startswith(" ") and not insert_str.startswith((":", ",", ")", "]")):
                    insert_str = " " + insert_str
            if hint.padding_right and col < len(target_line) and target_line[col] != " ":
                if not insert_str.endswith(" "):
                    insert_str = insert_str + " "

            new_line = target_line[:col] + insert_str + target_line[col:]
            lines[hint.line] = new_line
            hint.is_physical = True

            return eol.join(lines)

        return source_code

    def to_lsp_inlay_hints(
        self,
        start_line: int | None = None,
        end_line: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        EN: Exports active hints within the given line range to LSP InlayHint format.
        ES: Exporta las pistas activas dentro del rango especificado al formato LSP InlayHint.
        """
        results: list[dict[str, Any]] = []
        for h in self.all_hints():
            if start_line is not None and h.line < start_line:
                continue
            if end_line is not None and h.line > end_line:
                continue
            results.append(h.to_lsp_dict())
        return results

    def __repr__(self) -> str:
        return f"<VirtualHintManager active_hints={len(self._hints)}>"


__all__ = [
    "VirtualHintManager",
]
