"""
Punto de Entrada de Alto Nivel y Orquestación del Pipeline de Gram (`gram.core.process`).
========================================================================================
Proporciona la función unificada `process()` para analizar código fuente directamente
contra una gramática sintáctica formal y aplicar plugins opcionales en una sola invocación.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Sequence

from gram.core.ast.nodes import ASTProgram
from gram.core.combinators.base import Combinator, RuleItem, RuleType
from gram.core.combinators.many import Many
from gram.core.combinators.reference import Ref
from gram.core.lexer import Lexer
from gram.core.lexer.tokens import Token
from gram.core.parser import Parser
from gram.native.rules import DECLARATION, PROGRAM

if TYPE_CHECKING:
    from gram.plugins.base import PluginBase


def process(
    grammar: Any,
    source_or_file: str | Path | Sequence[str],
    *,
    plugins: list[str | Path | PluginBase | Any] | None = None,
    comment_token: str | Token | None = None,
    save_comments: bool | None = None,
    ignore_newlines: bool | None = None,
) -> ASTProgram:
    """
    Procesa y analiza código fuente contra una gramática formal en una sola llamada.

    Orquesta de forma transparente todo el pipeline de compilación de Gram:
      1. Carga y registra los plugins solicitados (keywords, combinadores, extensiones).
      2. Lee el código fuente desde archivo (ruta str/Path) o directamente desde string/líneas.
      3. Normaliza la gramática formal garantizando la regla raíz PROGRAM.
      4. Ejecuta el análisis léxico (Lexer) y sintáctico (Parser & ASTAnalyzer).
      5. Aplica las transformaciones y validaciones de AST definidas por los plugins.
      6. Retorna el árbol de sintaxis abstracta estructurado (ASTProgram).

    Args:
        grammar: Diccionario de reglas sintácticas ({RuleItem: Combinator}),
                 regla RuleItem única o combinador raíz.
        source_or_file: Código fuente en texto (str), lista de líneas (list[str]),
                        o ruta a un archivo existente (str o Path).
        plugins: Lista opcional de nombres de plugins, rutas o instancias de PluginBase.
        comment_token: Carácter o delimitador de comentarios (ej. '#', '//', ';').
        save_comments: Si se deben incluir tokens Token.COMMENT en el flujo.
        ignore_newlines: Si se deben descartar tokens Token.NEWLINE en el flujo.

    Returns:
        ASTProgram: Árbol de sintaxis abstracta generado.

    Ejemplo de uso:
        >>> import gram
        >>> grammar = {gram.PROGRAM: gram.Many(gram.Ref(MiRegla))}
        >>> ast = gram.process(grammar, 'archivo.txt', plugins=['expressions'])
        >>> print(ast.format())
    """
    # -------------------------------------------------------------------------
    # 1. Cargar y registrar plugins solicitados
    # -------------------------------------------------------------------------
    loaded_plugins: list[Any] = []
    if plugins:
        from gram.plugins.base import PluginBase
        from gram.plugins.manager.core import Plugin, Plugins

        for p in plugins:
            if isinstance(p, Plugin):
                if not p.is_loaded:
                    p.load()
                loaded_plugins.append(p)
            elif isinstance(p, PluginBase):
                loaded_plugins.append(p)
            elif isinstance(p, (str, Path)):
                plugin_obj = Plugins.find(str(p))
                if plugin_obj is None:
                    plugin_obj = Plugins.load(p, auto_load=True, interactive=False)
                loaded_plugins.append(plugin_obj)

    # -------------------------------------------------------------------------
    # 2. Resolver y cargar código fuente
    # -------------------------------------------------------------------------
    content: str | list[str]
    if isinstance(source_or_file, Path):
        if not source_or_file.is_file():
            raise FileNotFoundError(f"No se encontró el archivo especificado: {source_or_file}")
        with source_or_file.open("r", encoding="utf-8-sig") as f:
            content = f.read()
    elif isinstance(source_or_file, str):
        if "\n" not in source_or_file and len(source_or_file) < 512:
            candidate_path = Path(source_or_file)
            if candidate_path.is_file():
                with candidate_path.open("r", encoding="utf-8-sig") as f:
                    content = f.read()
            else:
                content = source_or_file
        else:
            content = source_or_file
    elif isinstance(source_or_file, (list, tuple)):
        content = list(source_or_file)
    else:
        content = str(source_or_file)

    # -------------------------------------------------------------------------
    # 3. Normalizar la gramática formal (Asegurar reglas PROGRAM y DECLARATION)
    # -------------------------------------------------------------------------
    from gram.core.combinators.alternative import Alt
    from gram.native.rules import PASS

    normalized_grammar: dict[Any, Any]
    if isinstance(grammar, dict):
        normalized_grammar = dict(grammar)
    elif isinstance(grammar, type) and issubclass(grammar, RuleItem):
        rule_grammar = getattr(grammar, "grammar", None)
        normalized_grammar = {grammar: rule_grammar} if rule_grammar is not None else {grammar: grammar}
    elif isinstance(grammar, Combinator):
        normalized_grammar = {"__ROOT_COMBINATOR__": grammar}
    else:
        normalized_grammar = dict(grammar) if hasattr(grammar, "__iter__") else {PASS: grammar}

    # Asegurar DECLARATION de tipo Alt
    decl_key = None
    if DECLARATION in normalized_grammar:
        decl_key = DECLARATION
    else:
        for k in normalized_grammar:
            if getattr(k, "name", str(k)) == "DECLARATION":
                decl_key = k
                break

    if decl_key is not None:
        if not isinstance(normalized_grammar[decl_key], Alt):
            normalized_grammar[decl_key] = Alt(normalized_grammar[decl_key])
    else:
        # Sintetizar DECLARATION como Alt de todas las reglas de usuario disponibles
        candidate_rules = [
            Ref(k)
            for k in normalized_grammar
            if k is not PROGRAM and getattr(k, "name", str(k)) not in ("PROGRAM", "DECLARATION")
        ]
        if not candidate_rules:
            prog_comb = normalized_grammar.get(PROGRAM)
            if prog_comb is not None:
                inner = getattr(prog_comb, "combinator", None)
                if isinstance(inner, Ref):
                    candidate_rules = [inner]
                elif inner is not None:
                    candidate_rules = [Ref(inner) if isinstance(inner, type) and issubclass(inner, RuleItem) else inner]

        if not candidate_rules:
            candidate_rules = [Ref(PASS)]
        normalized_grammar[DECLARATION] = Alt(*candidate_rules)

    # Asegurar regla raíz PROGRAM
    has_program = PROGRAM in normalized_grammar or any(
        getattr(k, "name", str(k)) == "PROGRAM" for k in normalized_grammar
    )
    if not has_program:
        target_decl = decl_key or DECLARATION
        normalized_grammar[PROGRAM] = Many(Ref(target_decl))

    # -------------------------------------------------------------------------
    # 4. Tokenización y Análisis Sintáctico (Lexer + Parser + ASTAnalyzer)
    # -------------------------------------------------------------------------
    lexer = Lexer(
        content,
        comment_token=comment_token,
        save_comments=save_comments,
        ignore_newlines=ignore_newlines,
    )
    tokens = lexer.process()

    parser = Parser(tokens)
    ast: ASTProgram = parser.parse(normalized_grammar)

    # -------------------------------------------------------------------------
    # 5. Transformaciones y Validaciones de AST mediante Plugins
    # -------------------------------------------------------------------------
    for p in loaded_plugins:
        instance = getattr(p, "instance", p)
        if hasattr(instance, "transform_ast") and callable(instance.transform_ast):
            transformed = instance.transform_ast(ast)
            if transformed is not None and isinstance(transformed, ASTProgram):
                ast = transformed
        if hasattr(instance, "validate_ast") and callable(instance.validate_ast):
            instance.validate_ast(ast)

    # -------------------------------------------------------------------------
    # 6. Poda y limpieza final de nodos vacíos
    # -------------------------------------------------------------------------
    ast.prune_empty()

    return ast


__all__ = ["process"]
