"""
Punto de Entrada de Alto Nivel y Orquestación del Pipeline de Gram (`gram.core.process`).
========================================================================================
Proporciona la función unificada `process()` para analizar código fuente directamente
contra una gramática sintáctica formal en una sola invocación.
"""
from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from gram.core.lexer import Lexer
from gram.core.parser import Parser
from gram.utilities import Format, info


def process(
    grammar: Any,
    source_or_file: str | Path | Sequence[str],
    *,
    clean_stack: bool = False,
    show_on_end: bool = False
):
    """
    Procesa y analiza código fuente contra una gramática formal en una sola llamada.

    Orquesta de forma transparente el pipeline de análisis sintáctico de Gram:
      1. Lee el código fuente desde archivo (ruta str/Path) o directamente desde string/líneas.
      2. Normaliza la gramática formal garantizando la regla raíz PROGRAM.
      3. Ejecuta el análisis léxico (Lexer) y sintáctico (Parser & ASTAnalyzer).
      4. Retorna el árbol de sintaxis abstracta estructurado (ASTProgram).

    Args:
        grammar: Diccionario de reglas sintácticas ({RuleItem: Combinator}),
                 regla RuleItem única o combinador raíz.
        source_or_file: Código fuente en texto (str), lista de líneas (list[str]),
                        o ruta a un archivo existente (str o Path).
        clean_stack: Limpia la pila de información antes de procesar.
        show_on_end: Muestra el contenido de la pila al finalizar.

    Returns:
        ASTProgram: Árbol de sintaxis abstracta generado.

    Ejemplo de uso:
        >>> import gram
        >>> grammar = {gram.PROGRAM: gram.Many(gram.Ref(MiRegla))}
        >>> ast = gram.process(grammar, 'archivo.txt')
        >>> print(ast.format())
    """
    
    if clean_stack:
        info.StackInfo.clear_and_clean_all()
    

    # -------------------------------------------------------------------------
    # 2. Resolver y cargar código fuente
    # -------------------------------------------------------------------------
    content: str | list[str]
    if isinstance(source_or_file, Path):
        if not source_or_file.is_file():
            raise FileNotFoundError(f"No se encontró el archivo especificado: {source_or_file}")
        with source_or_file.open("r", encoding="utf-8-sig") as f:
            content = f.read()
        Format.FileTar.set(source_or_file.absolute())

    elif isinstance(source_or_file, str):
        if "\n" not in source_or_file and len(source_or_file) < 512:
            candidate_path = Path(source_or_file)
            if candidate_path.is_file():
                with candidate_path.open("r", encoding="utf-8-sig") as f:
                    content = f.read()
                Format.FileTar.set(candidate_path.absolute())
                
            else:
                content = source_or_file
        else:
            content = source_or_file
    elif isinstance(source_or_file, (list, tuple)):
        content = list(source_or_file)
    else:
        content = str(source_or_file)



    # -------------------------------------------------------------------------
    # 4. Tokenización y Análisis Sintáctico (Lexer + Parser + ASTAnalyzer)
    # -------------------------------------------------------------------------
    lexer = Lexer(content)
    tokens = lexer.process()
    parser = Parser(tokens)
    # ast = parser.parse(entrypoint)

    # -------------------------------------------------------------------------
    # 5. Poda y limpieza final de nodos vacíos
    # -------------------------------------------------------------------------


    if show_on_end:
        info.StackInfo.show_all()
        info.StackInfo.clear_and_clean_all()

    # return ast


__all__ = ["process"]
