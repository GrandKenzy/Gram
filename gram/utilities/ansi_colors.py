"""
Módulo de Colores y Estilos ANSI del Framework Gram.
=====================================================
Proporciona secuencias de escape ANSI para formateo en terminales compatibles,
paleta de colores temáticos y glifos estándar para el reporte de mensajes.
"""
from __future__ import annotations

import re

# Patrón regex para remover secuencias de escape ANSI
_ANSI_ESCAPE_PATTERN: re.Pattern[str] = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')


class ANSI:
    """
    Constantes de secuencias de escape ANSI para control de formato en consola.
    """
    RESET: str = '\033[0m'

    # Estilos
    BOLD: str = '\033[1m'
    DIM: str = '\033[2m'
    ITALIC: str = '\033[3m'
    UNDERLINE: str = '\033[4m'

    # Colores Estándar
    RED: str = '\033[31m'
    GREEN: str = '\033[32m'
    YELLOW: str = '\033[33m'
    BLUE: str = '\033[34m'
    MAGENTA: str = '\033[35m'
    CYAN: str = '\033[36m'
    WHITE: str = '\033[37m'

    # Colores Brillantes
    BRIGHT_RED: str = '\033[91m'
    BRIGHT_GREEN: str = '\033[92m'
    BRIGHT_YELLOW: str = '\033[93m'
    BRIGHT_BLUE: str = '\033[94m'
    BRIGHT_MAGENTA: str = '\033[95m'
    BRIGHT_CYAN: str = '\033[96m'
    BRIGHT_WHITE: str = '\033[97m'


# Mapa de colores semánticos por categoría de mensaje
COLORS: dict[str, str] = {
    'Normal': '\033[37m',    # Blanco estándar
    'Success': '\033[32m',   # Verde
    'Warn': '\033[33m',      # Amarillo
    'Error': '\033[31m',     # Rojo
    'Advice': '\033[34m',    # Azul
}

RESET: str = ANSI.RESET

# Glifos/Iconos estándar por categoría de mensaje
ICONS: dict[str, str] = {
    'Normal': '· ',
    'Success': '✔ ',
    'Warn': '⚠ ',
    'Error': '✖ ',
    'Advice': 'ℹ ',
}


def strip_ansi(text: str) -> str:
    """Remueve todas las secuencias de escape ANSI del texto provisto."""
    return _ANSI_ESCAPE_PATTERN.sub('', text)


__all__ = [
    'ANSI',
    'COLORS',
    'RESET',
    'ICONS',
    'strip_ansi',
]
