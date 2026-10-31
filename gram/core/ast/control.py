"""
AST State and Diagnostic Control (`gram.core.ast.control`).
===========================================================
Adapts the standalone `Diagnostics` toolkit to Gram's AST subsystem, wiring
session-aware diagnostic settings, cursor-weighted failure staging, and
token-to-ASTNode delegation.
"""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING

from gram import config, errors, utilities
from gram.core.ast.nodes import (
    ASTKeyword,
    ASTNode,
    Identifier,
    LiteralNumber,
    LiteralString,
    LiteralSymbol,
)
from gram.core.combinators import Alt, Ref, RuleItem
from gram.core.combinators.signals import CutFlowSignal
from gram.core.lexer import Token, TokenType

if TYPE_CHECKING:
    from gram.core.parser import Parser
    from gram.sessions import Session

_TOKEN_NODE_MAP: dict[Token, type[ASTNode]] = {
    Token.IDENT: Identifier,
    Token.NUMBER: LiteralNumber,
    Token.DECIMAL: LiteralNumber,
    Token.STRING: LiteralString,
    Token.KEYWORD: ASTKeyword,
}


class ASTState(utilities.Diagnostics):
    """
    Gram-specific AST diagnostic state bridging `utilities.Diagnostics` with
    parser cursor positions and session settings, falling back to `gram.config`.
    """

    parser: Parser

    def __init__(
        self,
        logfile: str | None = None,
        *,
        session: "Session | None" = None,
    ) -> None:
        self.session = session
        super().__init__(
            logfile or "ast-parser",
            "AST",
            "pending",
            True,
            self.get_config("INFO_GENERATE_LOGFILE", False),
            self.get_config("INFO_GENERATE_LOGFILE_ON_ERROR", False),
        )

    def get_config(self, name: str, default=None):
        """Return a session setting, falling back to global configuration."""
        if self.session is not None:
            return self.session.config.get(name, getattr(config, name, default))
        return getattr(config, name, default)

    @contextmanager
    def safe_mode(self) -> Iterator[None]:
        """Enter a reentrant speculative parsing context (`failure_context`)."""
        with self.failure_context():
            yield

    @contextmanager
    def failure_scope(self) -> Iterator[utilities._FailureScope]:
        """Keep a committed failure on its cut signal while restoring the scope."""
        try:
            with super().failure_scope() as scope:
                yield scope
        except CutFlowSignal as signal:
            candidate = scope.candidate
            carried = signal._failure_candidate
            if candidate is not None and (
                carried is None or candidate[0] > carried[0]
            ):
                signal._failure_candidate = candidate
            raise

    def report_error(
        self, err: errors.Error, *, pos: int | None = None
    ) -> errors.Error:
        """
        Report or stage an AST/Combinator error using the parser's cursor position.

        - Inside `safe_mode()` (`in_failure_context == True`), stages `err` weighted by
          the current parser cursor position (`pos > staged_weight`).
        - Outside `safe_mode()`, records `err` permanently and triggers `fail()`
          if `config.ERROR_EXIT_ON_ERROR` is enabled.
        """
        cursor_pos = (
            pos
            if pos is not None
            else (self.parser.pos if hasattr(self, "parser") else 0)
        )

        if self.in_failure_context:
            return self.stage_failure(err, weight=cursor_pos)

        self.discard_staged_failure()
        res = self.record_failure(err)
        if (
            res is not None
            and not getattr(err, "_suppress_raise", False)
            and self.get_config("ERROR_EXIT_ON_ERROR", True)
        ):
            self.fail(err, exit=True)
        return err

    def flush_failure(
        self, fallback: errors.Error | None = None
    ) -> errors.Error | None:
        """
        Promote the deepest staged failure (or `fallback`) and raise/exit if
        `config.ERROR_EXIT_ON_ERROR` is enabled.
        """
        target = self.promote_staged_failure(fallback=fallback, record=False)
        if target is not None:
            self.record_failure(target)
        if (
            target is not None
            and not getattr(target, "_suppress_raise", False)
            and self.get_config("ERROR_EXIT_ON_ERROR", True)
        ):
            self.fail(target, exit=True)
        return target

    def sender(self, msg: str, nt: utilities.Format.LogType) -> None:  # type: ignore[override]
        """Emit a diagnostic note only when `config.AST_ADD_INFO` is enabled."""
        if self.get_config("AST_ADD_INFO", True):
            self.current().note(msg, nt)

    def delegate_return_node(self, current: TokenType | None) -> ASTNode | None:
        """Instantiate and return the terminal `ASTNode` corresponding to `current`."""
        if current is None:
            self.error(
                "Cannot delegate AST node creation: received None instead of TokenType."
            )
            self.report_error(
                errors.ASTError(
                    "InvalidDeclaratorToken",
                    errors.AST_DECLARATOR_INVALID_TYPE,
                    "Se intentó generar un nodo terminal del AST a partir de un token nulo (None).",
                    "Verifique que el combinador haya consumido un token válido antes de delegar al AST.",
                )
            )
            return None

        self.node(
            "DelegatingAstNode", "Generating AST node from token", set_target=True
        )
        try:
            tok_type = current.token
            if tok_type in _TOKEN_NODE_MAP:
                node_cls = _TOKEN_NODE_MAP[tok_type]
            else:
                node_cls = LiteralSymbol

            self.success(
                f"Generated {node_cls.__name__} from {tok_type}. "
                f"Line={current.line}, Col={current.col}"
            )
            return node_cls(current)
        finally:
            self.down()

    def is_valid_entrypoint(self, entrypoint: type[RuleItem]) -> bool:
        """
        Validate that `entrypoint.entrypoint` is an `Alt` combinator composed
        exclusively of `Ref` combinators.
        """
        if not isinstance(entrypoint.entrypoint, Alt):
            self.error(f"El entrypoint {entrypoint.name} debe ser de tipo Alt.")
            self.report_error(
                errors.ASTError(
                    "InvalidEntryPointCombinator",
                    errors.AST_PROGRAM_INVALID_COMBINATOR,
                    f'El Entrypoint "{entrypoint.name}" utiliza un combinador raíz inválido '
                    f"({type(entrypoint.entrypoint).__name__}).",
                    "Defina la gramática del Entrypoint utilizando un combinador Alt(...).",
                )
            )
            return False

        root = entrypoint.entrypoint
        if root.ignore is not True:
            mutations = getattr(self, "_entrypoint_mutations", None)
            if mutations is not None:
                mutations.append((root, "ignore", root.ignore))
            root.ignore = True
        for i, child in enumerate(entrypoint.entrypoint.combinators):
            if not isinstance(child, Ref):
                self.error(
                    f"El combinador en la posición {i} del entrypoint no es un Ref. "
                    "Todos los combinadores dentro de EntryPoint deben ser Ref"
                )
                self.report_error(
                    errors.ASTError(
                        "InvalidEntryPointElement",
                        errors.AST_DECLARATOR_INVALID_ELEMENT,
                        f'El elemento en la posición {i} del Entrypoint "{entrypoint.name}" '
                        f'es de tipo "{type(child).__name__}" en lugar de "Ref".',
                        "Pase un Entrypoint de tipo Alt compuesto únicamente por referencias Ref(...).",
                    )
                )
                return False
            if child.branchable is not True:
                mutations = getattr(self, "_entrypoint_mutations", None)
                if mutations is not None:
                    mutations.append((child, "branchable", child.branchable))
                child.branchable = True

        self.success("El entrypoint es válido")
        return True


__all__ = ["ASTState"]
