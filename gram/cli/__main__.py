"""
Punto de entrada para ejecución modular: python -m gram.cli <comando>
"""
from __future__ import annotations

import sys
from gram.cli.core import main

if __name__ == "__main__":
    sys.exit(main())
