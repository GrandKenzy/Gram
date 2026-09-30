"""
Módulo de Gestión y Definición de Colores para Plugins de Gram.
===============================================================
Proporciona el analizador, validador y convertidor de esquemas cromáticos
definidos en `define_colors.json` o diccionarios.
Garantiza el cumplimiento estricto de formatos RGB [R, G, B] y Hex (#RRGGBB),
prohibiendo explícitamente cualquier especificación de canal alfa (RGBA / ARGB),
y proveyendo exportación directa hacia secuencias ANSI (24-bit TrueColor) y
temas de sintaxis TextMate / VS Code.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from gram import errors
from gram.utilities import error
from gram.utilities.ansi_colors import ANSI

_HEX_COLOR_PATTERN: re.Pattern[str] = re.compile(r"^#?([0-9a-fA-F]{6})$")
_HEX_ALPHA_PATTERN: re.Pattern[str] = re.compile(r"^#?([0-9a-fA-F]{8})$")


@dataclass(frozen=True)
class ColorDefinition:
    """
    Representa una definición de color validada para una categoría sintáctica o léxica de Gram.
    """
    name: str
    r: int
    g: int
    b: int

    @property
    def rgb(self) -> tuple[int, int, int]:
        """Tupla de componentes de color (R, G, B)."""
        return (self.r, self.g, self.b)

    @property
    def hex(self) -> str:
        """Representación hexadecimal canónica '#RRGGBB' en mayúsculas."""
        return f"#{self.r:02X}{self.g:02X}{self.b:02X}"

    def to_ansi(self) -> str:
        """Genera la secuencia de escape ANSI TrueColor (24-bit) para primer plano."""
        return f"\033[38;2;{self.r};{self.g};{self.b}m"

    def colorize(self, text: str) -> str:
        """Aplica el color ANSI TrueColor al texto indicado y restaura el formato al final."""
        return f"{self.to_ansi()}{text}{ANSI.RESET}"

    def to_textmate(self) -> dict[str, Any]:
        """Genera el diccionario de estilo compatible con temas TextMate / VS Code."""
        return {
            "name": f"Gram {self.name}",
            "scope": [
                f"source.gram.{self.name.lower()}",
                f"keyword.other.{self.name.lower()}",
                f"entity.name.{self.name.lower()}",
            ],
            "settings": {
                "foreground": self.hex,
            },
        }


class PluginColors:
    """
    Contenedor y gestor de la paleta de colores declarada por un plugin.
    """

    def __init__(self, colors: dict[str, ColorDefinition] | None = None) -> None:
        self._colors: dict[str, ColorDefinition] = dict(colors or {})

    def __contains__(self, name: str) -> bool:
        return name in self._colors

    def __getitem__(self, name: str) -> ColorDefinition:
        return self._colors[name]

    def __iter__(self):
        return iter(self._colors.values())

    def __len__(self) -> int:
        return len(self._colors)

    def get(self, name: str, default: ColorDefinition | None = None) -> ColorDefinition | None:
        """Obtiene una definición de color por nombre o categoría."""
        return self._colors.get(name, default)

    def names(self) -> list[str]:
        """Retorna los nombres de todas las categorías de color registradas."""
        return list(self._colors.keys())

    def to_ansi_map(self) -> dict[str, str]:
        """Genera un mapeo de nombre de categoría a secuencia de escape ANSI."""
        return {name: c.to_ansi() for name, c in self._colors.items()}

    def to_hex_map(self) -> dict[str, str]:
        """Genera un mapeo de nombre de categoría a código hexadecimal '#RRGGBB'."""
        return {name: c.hex for name, c in self._colors.items()}

    def to_textmate_theme(self) -> list[dict[str, Any]]:
        """Genera una lista de tokens temáticos para TextMate / VS Code."""
        return [c.to_textmate() for c in self._colors.values()]


def parse_colors(data_or_file: dict[str, Any] | str | Path) -> PluginColors:
    """
    Parsea y valida exhaustivamente un esquema cromático de plugin.

    Acepta un diccionario o una ruta a un archivo JSON con formato:
        {
            "CATEGORIA": "#RRGGBB",
            "OTRA": [R, G, B]
        }

    Rechaza estrictamente canales alfa (RGBA o cadenas de 8 dígitos hexadecimales).

    Args:
        data_or_file: Diccionario con definiciones de color o ruta al archivo JSON.

    Returns:
        Instancia de PluginColors con todas las definiciones validadas.
    """
    raw_data: dict[str, Any]
    if isinstance(data_or_file, (str, Path)):
        p = Path(data_or_file).resolve()
        if not p.exists() or not p.is_file():
            error.GrammarError(
                "Archivo de colores no encontrado",
                errors.PLUGIN_MANIFEST_INVALID,
                f"No se encontró el archivo de colores en: {p}",
            ).raise_error()
        try:
            raw_data = json.loads(p.read_text(encoding="utf-8-sig"))
        except Exception as exc:
            error.GrammarError(
                "Error en sintaxis de colores",
                errors.PLUGIN_MANIFEST_INVALID,
                f"Error al analizar JSON de colores: {exc}",
            ).raise_error()
    elif isinstance(data_or_file, dict):
        raw_data = data_or_file
    else:
        error.GrammarError(
            "Tipo de datos de colores inválido",
            errors.PLUGIN_MANIFEST_INVALID,
            f"Se esperaba dict, str o Path, pero se recibió: {type(data_or_file)}",
        ).raise_error()

    colors: dict[str, ColorDefinition] = {}

    for cat_name, val in raw_data.items():
        name_clean = str(cat_name).strip()

        # Validación 1: Lista / Tupla RGB [R, G, B]
        if isinstance(val, (list, tuple)):
            if len(val) == 4:
                error.GrammarError(
                    "Canal alfa no permitido en colores",
                    errors.PLUGIN_MANIFEST_INVALID,
                    f"La categoría '{name_clean}' define 4 componentes [R, G, B, A]. "
                    f"El canal alfa está estrictamente prohibido por el estándar de colores de Gram.",
                ).raise_error()
            if len(val) != 3:
                error.GrammarError(
                    "Formato RGB inválido",
                    errors.PLUGIN_MANIFEST_INVALID,
                    f"La categoría '{name_clean}' debe tener exactamente 3 componentes [R, G, B].",
                ).raise_error()

            try:
                r, g, b = int(val[0]), int(val[1]), int(val[2])
            except (ValueError, TypeError):
                error.GrammarError(
                    "Componentes RGB no numéricos",
                    errors.PLUGIN_MANIFEST_INVALID,
                    f"Los componentes RGB de '{name_clean}' deben ser enteros entre 0 y 255.",
                ).raise_error()

            if not (0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255):
                error.GrammarError(
                    "Componentes RGB fuera de rango",
                    errors.PLUGIN_MANIFEST_INVALID,
                    f"Los componentes RGB de '{name_clean}' deben estar entre 0 y 255. Obtenidos: ({r}, {g}, {b})",
                ).raise_error()

            colors[name_clean] = ColorDefinition(name=name_clean, r=r, g=g, b=b)

        # Validación 2: Cadena Hexadecimal #RRGGBB
        elif isinstance(val, str):
            val_clean = val.strip()

            if _HEX_ALPHA_PATTERN.match(val_clean):
                error.GrammarError(
                    "Canal alfa no permitido en colores hexadecimales",
                    errors.PLUGIN_MANIFEST_INVALID,
                    f"La categoría '{name_clean}' define un color hexadecimal de 8 dígitos con alfa ('{val_clean}'). "
                    f"Gram prohíbe el canal alfa en la especificación de colores.",
                ).raise_error()

            match = _HEX_COLOR_PATTERN.match(val_clean)
            if not match:
                error.GrammarError(
                    "Formato hexadecimal de color inválido",
                    errors.PLUGIN_MANIFEST_INVALID,
                    f"El color '{val_clean}' para la categoría '{name_clean}' no es un hexadecimal válido de 6 dígitos (#RRGGBB).",
                ).raise_error()

            hex_str = match.group(1)
            r = int(hex_str[0:2], 16)
            g = int(hex_str[2:4], 16)
            b = int(hex_str[4:6], 16)

            colors[name_clean] = ColorDefinition(name=name_clean, r=r, g=g, b=b)

        else:
            error.GrammarError(
                "Valor de color inválido",
                errors.PLUGIN_MANIFEST_INVALID,
                f"El valor de color para '{name_clean}' debe ser una cadena '#RRGGBB' o una lista [R, G, B].",
            ).raise_error()

    return PluginColors(colors)


__all__ = [
    "ColorDefinition",
    "PluginColors",
    "parse_colors",
]
