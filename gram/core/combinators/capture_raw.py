"""
CaptureRaw Combinator (`gram.core.combinators.capture_raw`).
============================================================
Provides the `CaptureRaw` combinator, which captures an unparsed, opaque sequence of tokens
(e.g., inline assembler, shader source, raw payloads) into a single leaf `RawNode`
without inflating the AST arena with individual child token nodes.
"""
from __future__ import annotations

from typing import ClassVar, TYPE_CHECKING, Any, Sequence

from gram import errors
from gram.core.ast.nodes import RawNode
from gram.core.combinators.base import Combinator
from gram.core.combinators.kinds import CombinatorKind
from gram.core.lexer.tokens import Token, TokenType

if TYPE_CHECKING:
    from gram.core.ast import ASTAnalyzer


class CaptureRaw(Combinator):
    """
    Combinator that captures an opaque raw block of tokens until `self.target` matches.

    Unlike `Until`, which produces an `ARRAY` and attaches every consumed token as an AST child,
    `CaptureRaw` produces a single leaf `RawNode` (and in C AOT, a single `GRAM_AST_RAW` arena node
    and GIR node with zero children and exact byte span `[src_start, src_length]`).

    Parameters:
        target (Combinator): Stopping combinator condition.
        consume_target (bool): Whether to consume and include `target` within the raw capture.
        balance_delimiters (tuple[Token | str, Token | str] | None): Optional pair of opening and
            closing delimiters (e.g. `(Token.LBRACE, Token.RBRACE)`). If provided, nesting depth
            is tracked so that `target` is only matched when nesting depth is 0.
        max_tokens (int | None): Optional cap on the number of tokens captured.
    """

    combinator_kind: ClassVar[CombinatorKind] = CombinatorKind.CAPTURE_RAW
    header_class: bool = True

    def __init__(
        self,
        target: Combinator,
        *,
        consume_target: bool = False,
        balance_delimiters: tuple[Token | str, Token | str] | None = None,
        max_tokens: int | None = None,
    ) -> None:
        """
        Initialize the `CaptureRaw` combinator.

        Args:
            target (Combinator): Stopping combinator condition.
            consume_target (bool): Whether to consume and include `target` when matched.
            balance_delimiters (tuple[Token | str, Token | str] | None): Delimiters to balance.
            max_tokens (int | None): Maximum number of tokens to capture.
        """
        super().__init__()
        self.target: Combinator = target
        self.consume_target: bool = consume_target
        self.balance_delimiters: tuple[Token | str, Token | str] | None = balance_delimiters
        self.max_tokens: int | None = max_tokens

    @staticmethod
    def _matches_delim(tok: TokenType, delim: Token | str) -> bool:
        if isinstance(delim, Token):
            return tok.token == delim
        if isinstance(delim, str):
            if tok.value is not None and str(tok.value) == delim:
                return True
            if getattr(tok.token, "value", None) == delim:
                return True
            if getattr(tok.token, "name", None) == delim:
                return True
        return False

    def parse(self, analyzer: ASTAnalyzer) -> RawNode | None:
        """
        Capture tokens into a `RawNode` until `self.target` matches at balanced depth 0.
        """
        parser = analyzer.parser
        father = parser.node(
            "ProcessingCaptureRaw", "Procesando captura de bloque en crudo", set_target=True
        )
        initial_checkpoint = parser.savepoint("CAPTURE_RAW-Init")
        consumed: list[TokenType] = []
        depth = 0
        open_delim = self.balance_delimiters[0] if self.balance_delimiters else None
        close_delim = self.balance_delimiters[1] if self.balance_delimiters else None

        try:
            while not parser.is_eof():
                if depth == 0:
                    chk = parser.savepoint("CAPTURE_RAW-Probe")
                    try:
                        with analyzer.failure_scope() as target_scope:
                            target_res = analyzer.visitor(self.target)
                    except BaseException:
                        parser.restore(chk)
                        raise

                    if target_res is not None:
                        if self.consume_target:
                            candidate = target_scope.candidate
                            if candidate is not None and candidate[0] > parser.pos:
                                analyzer.stage_failure(candidate[1], weight=candidate[0])
                            target_toks = parser.tokens[chk.pos:parser.pos]
                            consumed.extend(target_toks)
                        else:
                            parser.restore(chk)

                        source_text = getattr(parser, "source", None)
                        if source_text and consumed:
                            raw_text = self._slice_source(source_text, consumed)
                        else:
                            raw_text = self._tokens_to_string(consumed)
                        father.note(
                            f"CaptureRaw({self.target!r}) capturó {len(consumed)} tokens en crudo.",
                            "success",
                        )
                        return RawNode(consumed, raw_text)

                    # Target did not match at depth 0
                    parser.restore(chk)

                non_layout_count = sum(
                    1 for t in consumed if t.token not in (Token.NEWLINE, Token.INDENT, Token.DEDENT, Token.EOF)
                )
                if self.max_tokens is not None and non_layout_count >= self.max_tokens:
                    break

                tok = parser.consume()
                if tok is None:
                    break
                consumed.append(tok)

                # Update delimiter balancing
                if open_delim is not None and self._matches_delim(tok, open_delim):
                    depth += 1
                elif close_delim is not None and self._matches_delim(tok, close_delim):
                    if depth > 0:
                        depth -= 1

            # Reached EOF or max_tokens without matching target at depth 0
            failed_pos = parser.pos
            parser.restore(initial_checkpoint)
            father.note(
                f"CaptureRaw({self.target!r}) alcanzó el final o límite sin cerrar el bloque.",
                "error",
            )
            analyzer.report_error(
                errors.GrammarError(
                    "CaptureRawTargetNotFound",
                    errors.GRAMMAR_COMBINATOR_FAILED,
                    f"CaptureRaw({self.target!r}) no encontró el combinador de cierre esperado.",
                    "Asegúrese de cerrar el bloque en crudo con el delimitador correspondiente.",
                ),
                pos=failed_pos,
            )
            return None
        finally:
            parser.down()

    @staticmethod
    def _slice_source(source_text: str, tokens: Sequence[TokenType]) -> str:
        layout_kinds = {Token.NEWLINE, Token.INDENT, Token.DEDENT, Token.EOF}
        content_toks = [t for t in tokens if t.token not in layout_kinds]
        if not content_toks:
            return ""
        first_tok = content_toks[0]
        last_tok = content_toks[-1]
        lines = source_text.splitlines(keepends=True)
        if not lines:
            return ""
        first_line_idx = max(0, first_tok.line - 1)
        start_char = sum(len(lines[i]) for i in range(min(first_line_idx, len(lines)))) + first_tok.col

        last_line_idx = max(0, last_tok.line - 1)
        last_val_len = (
            len(str(last_tok.value))
            if last_tok.value is not None
            else len(getattr(last_tok.token, "name", ""))
        )
        end_char = sum(len(lines[i]) for i in range(min(last_line_idx, len(lines)))) + last_tok.col + last_val_len
        return source_text[start_char:end_char]

    @staticmethod
    def _tokens_to_string(tokens: Sequence[TokenType]) -> str:
        layout_kinds = {Token.NEWLINE, Token.INDENT, Token.DEDENT, Token.EOF}
        out: list[str] = []
        prev_line: int | None = None
        prev_end_col: int = 0

        for t in tokens:
            if t.token in layout_kinds:
                continue
            if t.value is not None:
                tok_str = str(t.value)
            elif getattr(t.token, "value", None) is not None:
                tok_str = str(t.token.value)
            elif getattr(t.token, "name", None) is not None:
                tok_str = str(t.token.name)
            else:
                continue

            if prev_line is not None:
                if t.line > prev_line:
                    out.append("\n" * (t.line - prev_line))
                    if t.col > 0:
                        out.append(" " * t.col)
                else:
                    gap = t.col - prev_end_col
                    if gap > 0:
                        out.append(" " * gap)

            out.append(tok_str)
            if "\n" in tok_str:
                split_lines = tok_str.split("\n")
                prev_line = t.line + len(split_lines) - 1
                prev_end_col = len(split_lines[-1])
            else:
                prev_line = t.line
                prev_end_col = t.col + len(tok_str)

        return "".join(out)

    def __repr__(self) -> str:
        return (
            f"CaptureRaw({self.target!r}, "
            f"consume_target={self.consume_target}, "
            f"balance_delimiters={self.balance_delimiters!r}, "
            f"max_tokens={self.max_tokens})"
        )


__all__ = ["CaptureRaw", "RawNode"]
