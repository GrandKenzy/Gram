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
from gram.core.ast.nodes import ASTNode, ASTProgram, RefNode
from gram.core.combinators.additional_stack import CombinatorAdditionalStack
from gram.core.combinators.alternative import Alt
from gram.core.combinators.base import Combinator, RuleType
from gram.core.combinators.defaults import DECLARATION, PROGRAM
from gram.core.combinators.match import MatchToken
from gram.core.combinators.mods import is_hardcoded_mod
from gram.core.combinators.reference import Ref
from gram.core.combinators.tokenize import Tokenize
from gram.core.lexer.tokens import Token, TokenType
from gram.core.watcher import Watcher
from gram.utilities import error
from gram.utilities.info import StackInfo

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
        self.stack: StackInfo = StackInfo(
            "ast-log",
            "AST",
            "Registro y diagnóstico del procesamiento del AST",
            expose_nodes=True,
            generate_on_error=config.INFO_GENERATE_LOGFILE_ON_ERROR,
            generate_log_file=config.INFO_GENERATE_LOGFILE,
        )
        parent_node = node or parser.node
        self.stack.main = parent_node.node(
            "AST",
            "Procesamiento y construcción del árbol sintáctico",
            priority=2,
        )

        self.declarator: Alt | None = None
        self.comments: list[TokenType] = []
        self.current_level: int = 0
        self.watcher: Watcher = Watcher()
        self.parser.watcher = self.watcher

        if config.PARSER_ADD_INFO:
            self.stack.note("Inicializando ASTAnalyzer", "normal")
            self.stack.note(
                f"Se recibieron {len(grammar)} reglas gramaticales",
                "normal",
            )

    @property
    def node(self) -> InfoNode:
        """
        EN: Active telemetry node (automatically retrieves child node from scoped_node if active).
        ES: Nodo de telemetría activo (devuelve automáticamente el sub-nodo hijo en scoped_node si está activo).
        """
        return self.parser.node

    @staticmethod
    def _rule_name(rule: RuleType) -> str:
        if isinstance(rule, str):
            return rule
        return rule.name or rule.__name__

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
                if self._rule_name(key) == "PROGRAM":
                    prog_rule = val
                    break

        if prog_rule is None:
            if config.PARSER_ADD_ERROR:
                target_node.note("No se encontró la regla PROGRAM", "error")
            error.ParserError(
                "Regla PROGRAM no encontrada",
                errors.PROGRAM_RULE_NOT_FOUND,
                "No se encontró la regla PROGRAM para inicializar el programa.",
            ).raise_error()
            return

        if config.PARSER_ADD_INFO:
            target_node.note(f"Regla PROGRAM encontrada: {prog_rule.type()}", "success")

        if prog_rule.type() not in ("Many", "Some"):
            if config.PARSER_ADD_INFO:
                target_node.note(
                    f"PROGRAM no utiliza un combinador Many o Some: {prog_rule.type()}",
                    "advice",
                )

        if config.PARSER_ADD_INFO:
            target_node.note("Regla PROGRAM configurada correctamente", "success")

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
                if self._rule_name(key) == "DECLARATION":
                    decl_rule = val
                    break

        if decl_rule is None:
            if config.PARSER_ADD_ERROR:
                target_node.note("No se encontró la regla DECLARATION", "error")
            error.ParserError(
                "Regla DECLARATION no encontrada",
                errors.DECLARATION_RULE_NOT_FOUND,
                "No se encontró el declarador DECLARATION en la gramática.",
            ).raise_error()
            return

        if config.PARSER_ADD_INFO:
            target_node.note(
                f"Declarador DECLARATION encontrado: {decl_rule.type()}",
                "success",
            )

        if not isinstance(decl_rule, Alt):
            if config.PARSER_ADD_ERROR:
                target_node.note(
                    f"DECLARATION no es de tipo Alt: {decl_rule.type()}",
                    "error",
                )
            error.ParserError(
                "Tipo de DECLARATION inválido",
                errors.DECLARATOR_INVALID_TYPE,
                "El declarador DECLARATION solo admite el combinador Alt.",
            ).raise_error()
            return

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

        declarator = self.declarator
        if declarator is None:
            if config.PARSER_ADD_ERROR:
                target_node.note("No existe declarador para validar", "error")
            error.ParserError(
                "Declarador no disponible",
                errors.DECLARATION_RULE_NOT_FOUND,
                "No existe un declarador válido configurado para validar.",
            ).raise_error()
            return

        if config.PARSER_ADD_INFO:
            target_node.note("Validando elementos de DECLARATION", "normal")

        for declaration in declarator.items():
            if isinstance(declaration, Ref):
                if config.PARSER_ADD_INFO:
                    target_node.note(
                        f"Referencia de declaración encontrada: {declaration}",
                        "success",
                    )
            else:
                if config.PARSER_ADD_ERROR:
                    target_node.note(
                        f"Elemento inválido en DECLARATION: {declaration}",
                        "error",
                    )
                error.ParserError(
                    "Elemento de DECLARATION inválido",
                    errors.DECLARATOR_INVALID_ELEMENT,
                    "El declarador solo admite objetos tipo Ref.",
                ).raise_error()

        if config.PARSER_ADD_INFO:
            target_node.note("DECLARATION validado correctamente", "success")

    def process(self, node: InfoNode | None = None) -> ASTProgram:
        """
        EN: Executes the complete syntactic analysis over the token stream, building the ASTProgram.
        ES: Ejecuta el análisis sintáctico completo sobre el flujo de tokens, construyendo el ASTProgram.

        Args:
            node (InfoNode | None, optional): Target telemetry node.

        Returns:
            ASTProgram: Structured abstract syntax tree with statements, comments, and levels.
        """
        with self.parser.use_node(node or self.stack):
            return self._process()

    def _process(self) -> ASTProgram:
        target_node = self.node

        if config.PARSER_ADD_INFO:
            target_node.note("Iniciando procesamiento del AST", "normal")

        self.is_started()
        self.get_declaration()
        self.fix_declaration()

        if config.PARSER_ADD_INFO:
            target_node.note(
                "Gramática inicial validada; iniciando recorrido de tokens",
                "success",
            )

        statements: list[ASTNode] = []

        while self.parser.not_empty():
            current = self.parser.peek()
            if current is None:
                break

            if config.PARSER_ADD_INFO:
                target_node.note(f"Analizando token: {current}", "normal")

            if self.quit_trash(current):
                if config.PARSER_ADD_INFO:
                    target_node.note(
                        f"Token descartado: {current.token.name}",
                        "advice",
                    )
                self.parser.consume()
                continue

            decl_node = self.match_with_declaration(current)
            if decl_node is not None:
                if isinstance(decl_node, ASTNode):
                    statements.append(decl_node)
                elif isinstance(decl_node, (list, tuple)):
                    for item in decl_node:
                        if isinstance(item, ASTNode):
                            statements.append(item)

        if config.PARSER_ADD_INFO:
            target_node.note("No quedan tokens por procesar", "success")

        return ASTProgram(
            body=statements,
            comments=self.comments,
        )

    def process_rule(
        self,
        rule: RuleType,
        grammar: Combinator,
        current: TokenType | None = None,
        ignore_errors: bool = False,
        node: InfoNode | None = None,
        generate_node: bool = False,
        node_name: str | None = None,
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
            generate_node (bool, optional): If True, wraps the rule result in a RefNode.
            node_name (str | None, optional): Optional name for a generated RefNode.

        Returns:
            Any: Generated ASTNode or raw result if the rule is structural.
        """
        target_node = node or self.node
        start_level = self.current_level
        rule_name = self._rule_name(rule)

        if config.PARSER_ADD_INFO:
            target_node.note(f"Procesando regla {rule_name}", "normal")

        result = self.process_combinator(
            grammar,
            current,
            ignore_errors=ignore_errors,
        )

        if result is not None:
            if config.PARSER_ADD_INFO:
                target_node.note(f"Regla {rule_name} aceptada", "success")

            is_structural = (
                False if isinstance(rule, str) else rule.is_structural or rule.ignore
            )
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
                result = ASTNode.from_rule_result(
                    rule=rule,
                    result=result,
                    level=start_level,
                )

            if generate_node:
                return RefNode.from_result(
                    rule=rule,
                    result=result,
                    level=start_level,
                    name=node_name or "RefNode",
                )

            return result
        else:
            if config.PARSER_ADD_INFO:
                target_node.note(f"Regla {rule_name} no coincidió", "advice")
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
            if config.PARSER_ADD_INFO:
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
        return combinator.parse(self, current, ignore_errors=ignore_errors)

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
            if config.PARSER_ADD_INFO:
                target_node.note(
                    "COMMENT almacenado en la colección de comentarios",
                    "advice",
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

        declarator = self.declarator
        if declarator is None:
            if config.PARSER_ADD_ERROR:
                target_node.note(
                    "No existe DECLARATION para realizar matching",
                    "error",
                )
            error.ParserError(
                "Declarador no disponible",
                errors.DECLARATION_RULE_NOT_FOUND,
                "No existe un declarador disponible para procesar alternativas de sentencias.",
            ).raise_error()
            return None

        if config.PARSER_ADD_INFO:
            target_node.note(f"Procesando DECLARATION con {current}", "normal")

        return self.process_combinator(
            declarator,
            current,
            ignore_errors=False,
        )


__all__ = [
    "ASTAnalyzer",
]
