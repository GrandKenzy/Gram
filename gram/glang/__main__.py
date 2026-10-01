"""
Punto de entrada directo para GLANG: python -m gram.glang [comando | archivo.glang]
===================================================================================
"""
from __future__ import annotations

import sys
from gram.cli.core import main

if __name__ == "__main__":
    # Prepend 'glang' subcomando si no está presente
    args = sys.argv[1:]
    if not args or args[0] != "glang":
        sys.exit(main(["glang"] + args))
    else:
        sys.exit(main(args))
