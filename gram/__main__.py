"""
Punto de entrada directo para el paquete Gram: python -m gram [comando]
=======================================================================
Redirige directamente al motor CLI de Gram Framework.
"""
from __future__ import annotations

import sys
from gram.cli.core import main

if __name__ == "__main__":
    sys.exit(main())
