"""
Punto de entrada directo para el paquete Gram: python -m gram
=============================================================
"""
from __future__ import annotations

import sys

from gram import __version__


def main() -> int:
    """Imprime información de versión del framework."""
    print(f"Gram Framework v{__version__}")
    return 0


if __name__ == "__main__":
    sys.exit(main())