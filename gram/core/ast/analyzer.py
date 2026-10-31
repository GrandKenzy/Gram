"""
Abstract Syntax Tree Analyzer (`gram.core.ast.analyzer`).
=========================================================
Defines `ASTAnalyzer`, which validates the root grammar entrypoint and drives
top-level traversal via `visit_many` or `visit_some` while surfacing the
deepest staged syntax error whenever unconsumed tokens remain before EOF.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from gram import errors
from gram.core.ast.control import ASTState
from gram.core.ast.raytracing import RayTracing
from gram.core.ast.visitor import Visitor
from gram.core.combinators import Combinator, RuleItem
from gram.core.lexer import Token

from gram.core.ast.nodes import ASTNode

if TYPE_CHECKING:
    from gram.core.lexer import TokenType
    from gram.core.parser import Parser
    from gram.sessions import Session


class ASTAnalyzer(ASTState):
    """
    Coordinates syntactic evaluation and AST construction by pairing a `Parser`
    instance with a root grammar `RuleItem` entrypoint.
    """

    def __init__(
        self,
        parser: Parser,
        entrypoint: type[RuleItem],
        logfile: str | None = None,
        mode: Literal["Many", "Some"] = "Many",
        *,
        trace: Literal["off", "basic", "detailed"] = "basic",
        session: "Session | None" = None,
    ) -> None:
        if trace not in ('off', 'basic', 'detailed'):
            raise ValueError(f'Unknown tracing mode: {trace!r}')
        effective_session = (
            session if session is not None else getattr(parser, "session", None)
        )
        super().__init__(logfile, session=effective_session)
        self.parser: Parser = parser
        self.entrypoint: type[RuleItem] = entrypoint
        self.comments: list[TokenType] = []
        self.current_level: int = 0
        self.mode: Literal["Many", "Some"] = mode
        self.stack_errors: list[str] = []
        self.trace_mode = trace
        self._active = False
        self._entrypoint_mutations: list[tuple[Combinator, str, bool]] = []

        self.debug(
            f"Analizador AST Inicializado. Entrada={self.entrypoint.name} grámaticas"
        )
        
        self.raytracing = RayTracing(mode=trace)
        self._activate()

    def _activate(self) -> None:
        """Make this analyzer the sole observer of its parser."""
        previous = self.parser.analyzer_ast_instance
        if previous is not self:
            if previous is not None:
                previous.close()
            self.parser.analyzer_ast_instance = self
        if not self._active:
            if self.trace_mode != 'off':
                self.parser.hookr.add(self.dispatch_raytracing_process)
            self._active = True

    def close(self) -> None:
        """Detach observation and release temporary snapshots, preserving results."""
        if self._active:
            if self.trace_mode != 'off':
                self.parser.hookr.remove(self.dispatch_raytracing_process)
            self._active = False
        close = getattr(self.raytracing, 'close', None)
        if close is not None:
            close()
        for target, attribute, previous in reversed(self._entrypoint_mutations):
            setattr(target, attribute, previous)
        self._entrypoint_mutations.clear()

    def dispatch_raytracing_process(self, state: str, checkpoint: Any = None) -> None:
        if state == 'save':
            self.raytracing.lift(checkpoint)
        elif state == 'restore':
            if self.trace_mode == 'detailed':
                self.raytracing.observe_position(self.parser._restore_from_pos)
            self.raytracing.unreach(checkpoint)

    def visitor(self, combinator: Combinator) -> Any:
        """Dispatch `combinator` to the AST `Visitor` function."""
        if not self._active:
            self._activate()
        return Visitor(self, combinator)

    def visit_many(self, entry: Combinator) -> list[Any]:
        """
        Repeatedly evaluate the root `entry` combinator across the token stream
        until `EOF` is reached.

        If `entry` fails to match while non-EOF tokens remain in the stream,
        flushes the deepest staged failure (`flush_failure`) so the exact
        originating syntax error is reported.
        """
        results: list[Any] = []

        while not self.parser.is_eof():
            # Skip standalone newline tokens between top-level statements
            if self.parser.consume_if(Token.NEWLINE):
                continue
            if self.parser.is_eof():
                break

            checkpoint = self.parser.savepoint("AST-VisitMany")
            res = Visitor(self, entry)

            if res is None:
                self.parser.restore(checkpoint)
                curr_tok = self.parser.peek() if not self.parser.empty() else None
                tok_info = (
                    f" en línea {curr_tok.line}, columna {curr_tok.col} "
                    f"({curr_tok.token.name}: {curr_tok.value!r})"
                    if curr_tok is not None
                    else ""
                )
                fallback = errors.GrammarError(
                    "EntryPointNoMatch",
                    errors.GRAMMAR_COMBINATOR_FAILED,
                    f'Ninguna regla del Entrypoint "{self.entrypoint.name}" coincidió{tok_info}.',
                    "Verifique la sintaxis de la declaración o sentencia en esa posición.",
                )
                self.flush_failure(fallback=fallback)
                break

            results.append(res)
            self.discard_staged_failure(min_weight=self.parser.pos)

            if self.parser.pos == checkpoint.pos:
                break

        return results

    def visit_some(self, entry: Combinator) -> list[Any] | None:
        """
        Evaluate the root `entry` combinator requiring at least one top-level
        match before `EOF`.
        """
        results = self.visit_many(entry)
        if not results:
            fallback = errors.GrammarError(
                "EntryPointMinimumNotMet",
                errors.GRAMMAR_COMBINATOR_FAILED,
                f'Se esperaba al menos una sentencia válida para el Entrypoint "{self.entrypoint.name}".',
                "El código fuente no produjo ningún nodo en modo 'Some'.",
            )
            self.flush_failure(fallback=fallback)
            return None
        return results

    def process(self) -> (list[ASTNode] | None):
        """Run an analysis and detach its observer on every exit path."""
        self._activate()
        try:
            return self._process()
        finally:
            self.close()

    def _process(self) -> (list[ASTNode] | None):
        """
        Validate the grammar entrypoint and execute top-level AST generation
        using `visit_many` or `visit_some`.
        """
        self.debug(f"Generando AST en modo {self.mode}")

        entry = getattr(self.entrypoint, "entrypoint", None)

        if not entry:
            self.error("No se encontró ningún combinador en el punto de entrada")
            self.report_error(
                errors.ASTError(
                    "EmptyEntryPoint",
                    errors.AST_PROGRAM_RULE_NOT_FOUND,
                    f'El Entrypoint "{self.entrypoint.name}" no contiene ningún combinador gramatical.',
                    'Asegúrese de definir el atributo "entrypoint" con una regla válida en el punto de entrada.',
                )
            )
            return None

        self.node(
            "EntryPointRevision", "Revisando validéz del EntryPoint", set_target=True
        )
        try:
            if not self.is_valid_entrypoint(self.entrypoint):
                return None
        finally:
            self.down()

        if self.mode == "Many":
            return self.visit_many(entry)
        return self.visit_some(entry)


__all__ = ["ASTAnalyzer"]
