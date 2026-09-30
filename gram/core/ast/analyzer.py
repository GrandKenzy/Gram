"""
Syntactic Analyzer and AST Constructor (`gram.core.ast.analyzer`).
==================================================================
EN:
    Orchestrates execution of the token stream against formal grammar rules,
    managing indentation levels, hierarchical block detection, real-time
    Watcher supervision, and constructing the final `ASTProgram`.

ES:
    Orquesta la ejecución del flujo de tokens y las reglas gramaticales,
    administrando el nivel de indentación, la detección de bloques,
    la interacción con el vigilante Watcher y la construcción del `ASTProgram`.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from gram import config, errors
from gram.core.ast.nodes import ASTNode, ASTProgram
from gram.core.combinators.additional_stack import CombinatorAdditionalStack
from gram.core.combinators.alternative import Alt
from gram.core.combinators.base import Combinator, RuleType
from gram.core.combinators.defaults import DECLARATION, PROGRAM
from gram.core.combinators.match import MatchToken
from gram.core.combinators.mods import HARDCODED_MODS, is_hardcoded_mod
from gram.core.combinators.reference import Ref
from gram.core.combinators.tokenize import Tokenize
from gram.core.lexer.tokens import Token, TokenType
from gram.core.watcher import Watcher
from gram.utilities import error

if TYPE_CHECKING:
    from gram.core.parser import Parser
    from gram.utilities.info import Node as InfoNode


class ASTAnalyzer:
    """
    EN:
        Syntactic analyzer and Abstract Syntax Tree (AST) builder.
        Orchestrates grammar execution over the token stream provided by the Lexer
        and managed by the Parser, recognizing root declarations, resolving combinators,
        structuring hierarchical blocks, and building a formal ASTProgram.

    ES:
        Analizador sintáctico y constructor del Árbol de Sintaxis Abstracta (AST).
        Orquesta la ejecución de la gramática sobre el flujo de tokens producido por el Lexer
        y administrado por el Parser, reconociendo declaraciones raíz, resolviendo combinadores,
        estructurando bloques jerárquicos y construyendo un ASTProgram formal.
    """

    def __init__(
        self,
        parser: Parser,
        grammar: dict[RuleType, Combinator],
        node: InfoNode | None = None,
    ) -> None:
        """
        EN: Initializes the syntactic analyzer with parser and grammar rules.
        ES: Inicializa el analizador sintáctico con el parser y las reglas gramaticales.

        Args:
            parser (Parser): Parser instance containing the tokenized stream.
            grammar (dict[RuleType, Combinator]): Dictionary of grammar rules and combinators.
            node (InfoNode | None, optional): Optional telemetry node.
        """
        self.parser: Parser = parser
        self.grammar: dict[RuleType, Combinator] = grammar
        self._root_node: InfoNode | None = (
            node if node is not None
            else getattr(parser, "node", None)
        )

        self.declarator: Alt | None = None
        self.program: Combinator | None = None
        self.comments: list[TokenType] = []
        self.current_level: int = 0
        self.watcher: Watcher = Watcher()
        self.parser.watcher = self.watcher

        if self._root_node and getattr(config, "PARSER_ADD_INFO", True):
            self._root_node.note("Inicializando ASTAnalyzer", "Normal")
            self._root_node.note(
                f"Se recibieron {len(grammar)} reglas gramaticales",
                "Normal",
            )

    @property
    def node(self) -> InfoNode | None:
        """
        EN: Active telemetry node (automatically retrieves child node from scoped_node if active).
        ES: Nodo de telemetría activo (devuelve automáticamente el sub-nodo hijo en scoped_node si está activo).
        """
        if hasattr(self.parser, "control"):
            return self.parser.control.node
        return getattr(self.parser, "node", None)

    def is_started(self, node: InfoNode | None = None) -> None:
        """
        EN: Validates the existence and configuration of the root PROGRAM rule.
        ES: Verifica la existencia y validez de la regla raíz PROGRAM.

        Args:
            node (InfoNode | None, optional): Target telemetry node.

        Raises:
            ParserError: If the PROGRAM rule is missing from grammar.
        """
        target_node = node or self.node

        prog_rule = self.grammar.get(PROGRAM)
        if prog_rule is None:
            for key, val in self.grammar.items():
                if getattr(key, "name", str(key)) == "PROGRAM":
                    prog_rule = val
                    break

        if prog_rule is None:
            if target_node and getattr(config, "PARSER_ADD_ERROR", True):
                target_node.note("No se encontró la regla PROGRAM", "Error")
            error.ParserError(
                "Regla PROGRAM no encontrada",
                errors.PROGRAM_RULE_NOT_FOUND,
                "No se encontró la regla PROGRAM para inicializar el programa.",
            ).raise_error()

        if target_node and getattr(config, "PARSER_ADD_INFO", True):
            target_node.note(f"Regla PROGRAM encontrada: {prog_rule.type()}", "Success")

        if prog_rule.type() not in ("Many", "Some"):
            if target_node and getattr(config, "PARSER_ADD_INFO", True):
                target_node.note(
                    f"PROGRAM no utiliza un combinador Many o Some: {prog_rule.type()}",
                    "Advice",
                )

        self.program = prog_rule

        if target_node and getattr(config, "PARSER_ADD_INFO", True):
            target_node.note("Regla PROGRAM configurada correctamente", "Success")

    def get_declaration(self, node: InfoNode | None = None) -> None:
        """
        EN: Retrieves and validates the container DECLARATION rule for all statement alternatives.
        ES: Recupera la regla DECLARATION contenedora de todas las alternativas de sentencia.

        Args:
            node (InfoNode | None, optional): Target telemetry node.

        Raises:
            ParserError: If DECLARATION is missing or not of type Alt.
        """
        target_node = node or self.node

        decl_rule = self.grammar.get(DECLARATION)
        if decl_rule is None:
            for key, val in self.grammar.items():
                if getattr(key, "name", str(key)) == "DECLARATION":
                    decl_rule = val
                    break

        if decl_rule is None:
            if target_node and getattr(config, "PARSER_ADD_ERROR", True):
                target_node.note("No se encontró la regla DECLARATION", "Error")
            error.ParserError(
                "Regla DECLARATION no encontrada",
                errors.DECLARATION_RULE_NOT_FOUND,
                "No se encontró el declarador DECLARATION en la gramática.",
            ).raise_error()

        if target_node and getattr(config, "PARSER_ADD_INFO", True):
            target_node.note(
                f"Declarador DECLARATION encontrado: {decl_rule.type()}",
                "Success",
            )

        if not isinstance(decl_rule, Alt):
            if target_node and getattr(config, "PARSER_ADD_ERROR", True):
                target_node.note(
                    f"DECLARATION no es de tipo Alt: {decl_rule.type()}",
                    "Error",
                )
            error.ParserError(
                "Tipo de DECLARATION inválido",
                errors.DECLARATOR_INVALID_TYPE,
                "El declarador DECLARATION solo admite el combinador Alt.",
            ).raise_error()

        self.declarator = decl_rule

    def fix_declaration(self, node: InfoNode | None = None) -> None:
        """
        EN: Validates that all elements inside the DECLARATION combinator are valid Ref references.
        ES: Valida que todos los elementos de DECLARATION sean referencias Ref válidas.

        Args:
            node (InfoNode | None, optional): Target telemetry node.

        Raises:
            ParserError: If any element within DECLARATION is not a Ref instance.
        """
        target_node = node or self.node

        if self.declarator is None:
            if target_node and getattr(config, "PARSER_ADD_ERROR", True):
                target_node.note("No existe declarador para validar", "Error")
            error.ParserError(
                "Declarador no disponible",
                errors.DECLARATION_RULE_NOT_FOUND,
                "No existe un declarador válido configurado para validar.",
            ).raise_error()

        if target_node and getattr(config, "PARSER_ADD_INFO", True):
            target_node.note("Validando elementos de DECLARATION", "Normal")

        for declaration in self.declarator.items():
            if isinstance(declaration, Ref):
                if target_node and getattr(config, "PARSER_ADD_INFO", True):
                    target_node.note(
                        f"Referencia de declaración encontrada: {declaration}",
                        "Success",
                    )
            else:
                if target_node and getattr(config, "PARSER_ADD_ERROR", True):
                    target_node.note(
                        f"Elemento inválido en DECLARATION: {declaration}",
                        "Error",
                    )
                error.ParserError(
                    "Elemento de DECLARATION inválido",
                    errors.DECLARATOR_INVALID_ELEMENT,
                    "El declarador solo admite objetos tipo Ref.",
                ).raise_error()

        if target_node and getattr(config, "PARSER_ADD_INFO", True):
            target_node.note("DECLARATION validado correctamente", "Success")

    def process(self, node: InfoNode | None = None) -> ASTProgram:
        """
        EN: Executes the complete syntactic analysis over the token stream, building the ASTProgram.
        ES: Ejecuta el análisis sintáctico completo sobre el flujo de tokens, construyendo el ASTProgram.

        Args:
            node (InfoNode | None, optional): Target telemetry node.

        Returns:
            ASTProgram: Structured abstract syntax tree with statements, comments, and levels.
        """
        target_node = node or self.node

        if target_node and getattr(config, "PARSER_ADD_INFO", True):
            target_node.note("Iniciando procesamiento del AST", "Normal")

        self.is_started(node=target_node)
        self.get_declaration(node=target_node)
        self.fix_declaration(node=target_node)

        if target_node and getattr(config, "PARSER_ADD_INFO", True):
            target_node.note(
                "Gramática inicial validada; iniciando recorrido de tokens",
                "Success",
            )

        statements: list[ASTNode] = []

        while self.parser.not_empty():
            current = self.parser.consume(node=target_node)

            if target_node and getattr(config, "PARSER_ADD_INFO", True):
                target_node.note(f"Analizando token: {current}", "Normal")

            if self.quit_trash(current, node=target_node):
                if target_node and getattr(config, "PARSER_ADD_INFO", True):
                    target_node.note(
                        f"Token descartado: {current.token.name}",
                        "Advice",
                    )
                continue

            decl_node = self.match_with_declaration(current, node=target_node)
            if decl_node is not None:
                if isinstance(decl_node, ASTNode):
                    statements.append(decl_node)
                elif isinstance(decl_node, (list, tuple)):
                    for item in decl_node:
                        if isinstance(item, ASTNode):
                            statements.append(item)

        if target_node and getattr(config, "PARSER_ADD_INFO", True):
            target_node.note("No quedan tokens por procesar", "Success")

        return ASTProgram(
            body=statements,
            comments=self.comments,
        )

    def process_rule(
        self,
        rule: Any,
        grammar: Combinator,
        current: TokenType | None = None,
        ignore_errors: bool = False,
        node: InfoNode | None = None,
    ) -> Any:
        """
        EN: Executes a grammar rule and wraps its result into an ASTNode (bypasses wrapping for structural rules).
        ES: Ejecuta una regla sintáctica y empaqueta su resultado en un ASTNode correspondiente (omite envoltura en reglas estructurales).

        Args:
            rule: Rule item or class reference.
            grammar (Combinator): Combinator associated with the rule.
            current (TokenType | None, optional): Current token positioned under cursor.
            ignore_errors (bool, optional): If True, suppresses exceptions upon mismatch. Defaults to False.
            node (InfoNode | None, optional): Target telemetry node.

        Returns:
            Any: Generated ASTNode or raw result if the rule is structural.
        """
        target_node = node or self.node
        start_level = self.current_level
        rule_name = getattr(rule, "name", str(rule))

        if target_node and getattr(config, "PARSER_ADD_INFO", True):
            target_node.note(f"Procesando regla {rule_name}", "Normal")

        result = self.process_combinator(
            grammar,
            current,
            ignore_errors=ignore_errors,
        )

        if result is not None:
            if target_node and getattr(config, "PARSER_ADD_INFO", True):
                target_node.note(f"Regla {rule_name} aceptada", "Success")

            is_structural = getattr(rule, "is_structural", False)
            if not is_structural and (
                rule_name in (
                    "ENDLINE",
                    "ENTRY_INDENT_BLOCK",
                    "EXIT_INDENT_BLOCK",
                    "BLOCK",
                    "INDENT_BLOCK",
                )
                or isinstance(grammar, Tokenize)
                or isinstance(result, TokenType)
            ):
                is_structural = True

            if not is_structural:
                return ASTNode.from_rule_result(
                    rule=rule,
                    result=result,
                    level=start_level,
                )

            return result
        else:
            if target_node and getattr(config, "PARSER_ADD_INFO", True):
                target_node.note(f"Regla {rule_name} no coincidió", "Advice")
            return None

    def process_combinator(
        self,
        combinator: Combinator,
        current: TokenType | None = None,
        ignore_errors: bool = False,
    ) -> Any:
        """
        EN: Dispatches execution of an individual combinator, routing telemetry and updating the Watcher.
        ES: Despacha la ejecución de un combinador individual, conectando el Watcher y enrutando telemetría.

        Args:
            combinator (Combinator): Syntactic combinator to evaluate.
            current (TokenType | None, optional): Current token positioned under cursor.
            ignore_errors (bool, optional): If True, suppresses exceptions upon mismatch. Defaults to False.

        Returns:
            Any: Result of evaluating the combinator.
        """
        self.watcher.enter_combinator(combinator, current)
        try:
            if getattr(config, "PARSER_ADD_INFO", True) and self.node is not None:
                child = self.node.node(
                    combinator.type(),
                    f"{combinator.type()} ← {current}",
                )
                with self.parser.control.scoped_node(child):
                    return self._dispatch_combinator(combinator, current, ignore_errors)
            else:
                return self._dispatch_combinator(combinator, current, ignore_errors)
        finally:
            self.watcher.exit_combinator()

    def _dispatch_combinator(
        self,
        combinator: Combinator,
        current: TokenType | None,
        ignore_errors: bool,
    ) -> Any:
        """
        EN: Executes the concrete combinator implementation and tracks INDENT / DEDENT indentation levels.
        ES: Ejecuta el combinador concreto tras establecer la telemetría y gestiona niveles de indentación.
        """
        # 1. Hardcoded Mods (Combinadores nativos del framework)
        if is_hardcoded_mod(combinator):
            if isinstance(combinator, MatchToken):
                res = combinator.parse(self, current, ignore_errors=ignore_errors)
                if res is not None:
                    if res.token == Token.INDENT:
                        self.current_level += 1
                    elif res.token == Token.DEDENT:
                        self.current_level = max(0, self.current_level - 1)
                return res
            return combinator.parse(self, current, ignore_errors=ignore_errors)

        # 2. Custom Mods registrados en la pila adicional
        if CombinatorAdditionalStack.has(combinator):
            return CombinatorAdditionalStack.process(
                combinator, self, current, ignore_errors=ignore_errors,
            )

        # 3. Soporte transparente para Custom Mods derivados de Combinator
        if isinstance(combinator, Combinator) and hasattr(combinator, "parse"):
            return combinator.parse(self, current, ignore_errors=ignore_errors)

        # 4. Combinador no soportado
        error.ParserError(
            "Combinador no soportado",
            errors.COMBINATOR_UNSUPPORTED,
            f"El combinador {combinator!r} no está soportado por el motor de análisis.",
        ).raise_error()

    def quit_trash(self, current: TokenType, node: InfoNode | None = None) -> bool:
        """
        EN: Discards non-grammatical tokens (newlines, empty lines, EOF) and preserves comments.
        ES: Descarta tokens no gramaticales (comentarios, líneas vacías, EOF) y preserva comentarios.

        Args:
            current (TokenType): Token to evaluate.
            node (InfoNode | None, optional): Target telemetry node.

        Returns:
            bool: True if the token should be discarded from the main parsing loop.
        """
        token_name = current.token.name

        if token_name == "COMMENT":
            self.comments.append(current)
            target_node = node or self.node
            if target_node and getattr(config, "PARSER_ADD_INFO", True):
                target_node.note(
                    "COMMENT almacenado en la colección de comentarios",
                    "Advice",
                )
            return True

        if token_name in ("NEWLINE", "EMPTY_LINE", "EOF"):
            return True

        return False

    def match_with_declaration(self, current: TokenType, node: InfoNode | None = None) -> Any:
        """
        EN: Evaluates the current token against the general DECLARATION alternative rule.
        ES: Evalúa el token actual contra la regla alternativa general DECLARATION.

        Args:
            current (TokenType): Current token under evaluation.
            node (InfoNode | None, optional): Target telemetry node.

        Returns:
            Any: Matching result from DECLARATION.
        """
        target_node = node or self.node

        if self.declarator is None:
            if target_node and getattr(config, "PARSER_ADD_ERROR", True):
                target_node.note(
                    "No existe DECLARATION para realizar matching",
                    "Error",
                )
            error.ParserError(
                "Declarador no disponible",
                errors.DECLARATION_RULE_NOT_FOUND,
                "No existe un declarador disponible para procesar alternativas de sentencias.",
            ).raise_error()

        if target_node and getattr(config, "PARSER_ADD_INFO", True):
            target_node.note(f"Procesando DECLARATION con {current}", "Normal")

        return self.process_combinator(
            self.declarator,
            current,
            ignore_errors=False,
        )


__all__ = [
    "ASTAnalyzer",
]
