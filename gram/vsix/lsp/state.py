"""
Language Server Protocol State and Document Controller (`gram.vsix.lsp.state`).
================================================================================
Manages in-memory document buffers, isolated parsing sessions, non-invasive
error interception via `Diagnostics.hook_errors`, and LSP language query providers.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from gram import config
from gram.core import lexer, parser
from gram.core.combinators.base import RuleItem
from gram.core.lexer.tokens import Token, TokenType
from gram.utilities import Diagnostics, ErrorAction, error
from gram.vsix.core import VSIXAnalyzer


@dataclass
class DocumentSession:
    """Encapsulates the synchronized analysis state of an open document."""

    uri: str
    text: str
    version: int = 1
    tokens: list[TokenType] = field(default_factory=list)
    ast_roots: list[Any] | None = None
    errors: list[error.Error] = field(default_factory=list)
    diagnostics: list[dict[str, Any]] = field(default_factory=list)


class LSPState:
    """
    Decoupled state orchestrator for Language Server operations.

    Tracks active documents, invokes Gram compilers under non-invasive
    error interception, and formats LSP diagnostic and telemetry responses.
    """

    def __init__(self, entrypoint: type[RuleItem] | None = None) -> None:
        self.entrypoint: type[RuleItem] | None = entrypoint
        self.documents: dict[str, DocumentSession] = {}
        self.analysis_cache: dict[str, Any] = {}
        if entrypoint is not None:
            self._refresh_analysis_cache(entrypoint)

    def _refresh_analysis_cache(self, entrypoint: type[RuleItem]) -> None:
        """Run VSIXAnalyzer to populate editor completion and hover catalogs."""
        analyzer = VSIXAnalyzer(output="default")
        self.analysis_cache = analyzer.process(entrypoint)

    def set_entrypoint(self, entrypoint: type[RuleItem]) -> None:
        """Assign root grammar entrypoint and refresh language metadata."""
        self.entrypoint = entrypoint
        self._refresh_analysis_cache(entrypoint)

    def open_document(self, uri: str, text: str, version: int = 1) -> DocumentSession:
        """Register a newly opened document buffer."""
        session = DocumentSession(uri=uri, text=text, version=version)
        self.documents[uri] = session
        return session

    def change_document(
        self,
        uri: str,
        text: str,
        version: int | None = None,
    ) -> DocumentSession:
        """Update the in-memory text buffer of an active document."""
        session = self.documents.get(uri)
        if session is None:
            new_version = version if version is not None else 1
            session = DocumentSession(uri=uri, text=text, version=new_version)
            self.documents[uri] = session
            return session

        session.text = text
        if version is not None:
            session.version = version
        else:
            session.version += 1
        return session

    def close_document(self, uri: str) -> None:
        """Remove a closed document from the active session catalog."""
        self.documents.pop(uri, None)

    def get_document(self, uri: str) -> str | None:
        """Retrieve the current in-memory text of a document."""
        session = self.documents.get(uri)
        return session.text if session is not None else None

    def get_session(self, uri: str) -> DocumentSession | None:
        """Retrieve the analysis session for a document URI."""
        return self.documents.get(uri)

    @staticmethod
    def _extract_position(err: error.Error) -> tuple[int, int]:
        """
        Extract zero-based (line, character) coordinate from error cautions.
        """
        line = 0
        col = 0
        text = " ".join(err.caution)

        line_match = re.search(r"(?:l[ií]nea|Line:?)\s*(\d+)", text, re.IGNORECASE)
        col_match = re.search(r"(?:columna|Col:?)\s*(\d+)", text, re.IGNORECASE)

        if line_match:
            try:
                parsed_line = int(line_match.group(1))
                line = max(0, parsed_line - 1 if parsed_line > 0 else 0)
            except ValueError:
                line = 0

        if col_match:
            try:
                col = max(0, int(col_match.group(1)))
            except ValueError:
                col = 0

        return line, col

    def _format_lsp_diagnostic(
        self,
        err: error.Error,
        lines: list[str],
    ) -> dict[str, Any]:
        """Convert a Gram error object into a standard LSP Diagnostic dictionary."""
        line_idx, col_idx = self._extract_position(err)

        line_str = lines[line_idx] if 0 <= line_idx < len(lines) else ""
        end_col = col_idx + 1

        if col_idx < len(line_str):
            remainder = line_str[col_idx:]
            word_match = re.match(r"[a-zA-Z0-9_]+|[^\s]", remainder)
            if word_match:
                end_col = col_idx + len(word_match.group(0))

        message = err.caution[0] if err.caution else err.name
        if len(err.caution) > 1 and err.caution[1]:
            message = f"{message} ({err.caution[1]})"

        return {
            "range": {
                "start": {"line": line_idx, "character": col_idx},
                "end": {"line": line_idx, "character": max(col_idx + 1, end_col)},
            },
            "severity": 1,
            "code": getattr(err.code, "code", str(err.name)),
            "source": "gram",
            "message": message,
        }

    def analyze(
        self,
        uri: str,
        entrypoint: type[RuleItem] | None = None,
    ) -> DocumentSession:
        """
        Execute isolated lexical and syntactic analysis using non-invasive hooks.
        """
        session = self.documents.get(uri)
        if session is None:
            session = DocumentSession(uri=uri, text="")
            self.documents[uri] = session

        active_entrypoint = entrypoint or self.entrypoint
        if active_entrypoint is not None and not self.analysis_cache:
            self._refresh_analysis_cache(active_entrypoint)

        intercepted_errors: list[error.Error] = []

        def _lsp_error_hook(sender: Any, err: error.Error) -> str:
            intercepted_errors.append(err)
            return ErrorAction.SUPPRESS_RAISE

        prev_exit_on_error = config.ERROR_EXIT_ON_ERROR
        config.ERROR_EXIT_ON_ERROR = False

        try:
            with Diagnostics.hook_errors(_lsp_error_hook):
                lex = lexer.Lexer(session.text)
                tokens = lex.process()
                session.tokens = tokens

                ast_roots = None
                if active_entrypoint is not None:
                    parse_engine = parser.Parser(tokens)
                    ast_roots = parse_engine.parse(active_entrypoint)

                session.ast_roots = ast_roots
        finally:
            config.ERROR_EXIT_ON_ERROR = prev_exit_on_error

        session.errors = intercepted_errors

        lines = session.text.splitlines()
        diagnostics = [
            self._format_lsp_diagnostic(err, lines)
            for err in intercepted_errors
        ]
        session.diagnostics = diagnostics

        return session

    def get_completions(
        self,
        uri: str,
        line: int,
        character: int,
        current_line: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return completion items based on language metadata and cursor position."""
        session = self.documents.get(uri)
        line_text = ""
        if current_line is not None:
            line_text = current_line
        elif session and session.text:
            lines = session.text.splitlines()
            if 0 <= line < len(lines):
                line_text = lines[line]

        prefix = line_text[:character]
        import_match = re.search(r"\bimport\s+([a-zA-Z0-9_]*)$", prefix)

        completions_list: list[dict[str, Any]] = []

        if import_match:
            query = import_match.group(1)
            start_col = character - len(query)
            range_dict = {
                "start": {"line": line, "character": start_col},
                "end": {"line": line, "character": character},
            }

            module_suggestions: list[str] = []
            rules_dict = self.analysis_cache.get("rules", {})
            for r_name, r_info in rules_dict.items():
                if "import" in r_name.lower():
                    for k, sug_list in r_info.get("suggestions", {}).items():
                        module_suggestions.extend(sug_list)

            cached_items = self.analysis_cache.get("indexes", {}).get("completions", [])
            for c in cached_items:
                if c.get("rule") == "IMPORT_DECL" and c.get("kind") == "Value":
                    module_suggestions.append(c.get("label", ""))

            if not module_suggestions:
                module_suggestions = [
                    "compiler", "core", "http", "json", "math", "os", "parser", "sys", "utilities", "vsix"
                ]

            seen: set[str] = set()
            for idx, mod in enumerate(module_suggestions):
                if not mod or mod in seen:
                    continue
                seen.add(mod)
                completions_list.append({
                    "label": mod,
                    "kind": 9,
                    "detail": "module",
                    "documentation": f"Import module '{mod}'.",
                    "insertText": mod,
                    "sortText": f"{idx:03d}_{mod}",
                    "range": range_dict,
                })

            return completions_list

        word_match = re.search(r"([a-zA-Z0-9_]+)$", prefix)
        typed_word = word_match.group(1) if word_match else ""
        start_col = character - len(typed_word)
        range_dict = {
            "start": {"line": line, "character": start_col},
            "end": {"line": line, "character": character},
        }

        cached_completions = self.analysis_cache.get("indexes", {}).get("completions", [])
        for idx, item in enumerate(cached_completions):
            kind_str = item.get("kind", "Keyword")
            kind_val = 14 if kind_str == "Keyword" else 15 if kind_str == "Snippet" else 12

            completions_list.append({
                "label": item.get("label", ""),
                "kind": kind_val,
                "detail": item.get("detail") or item.get("rule") or "",
                "documentation": item.get("documentation", ""),
                "insertText": item.get("label", ""),
                "sortText": f"{idx:03d}_{item.get('label', '')}",
                "range": range_dict,
            })

        return completions_list

    def get_hover(
        self,
        uri: str,
        line: int,
        character: int,
    ) -> dict[str, Any] | None:
        """Find the token under the cursor and return its documentation hover."""
        session = self.documents.get(uri)
        if session is None or not session.tokens:
            return None

        target_token: TokenType | None = None
        target_line_0 = 0
        for tok in session.tokens:
            tok_line_0 = tok.line - 1 if tok.line > 0 else 0
            if tok_line_0 == line:
                val_len = len(str(tok.value))
                if tok.col <= character <= tok.col + val_len:
                    target_token = tok
                    target_line_0 = tok_line_0
                    break

        if target_token is None:
            return None

        lexeme = str(target_token.value)
        hovers_index = self.analysis_cache.get("indexes", {}).get("hovers", {})

        hover_info = hovers_index.get(lexeme)
        if hover_info is None:
            for h_name, h_data in hovers_index.items():
                if h_name.lower() == lexeme.lower():
                    hover_info = h_data
                    break

        if hover_info is None:
            return None

        desc = hover_info.get("description", "")
        doc = hover_info.get("documentation", "")
        group = hover_info.get("group", "")
        kind = hover_info.get("kind", "Keyword")

        contents: list[str] = [f"**{kind}** `{lexeme}`"]
        if group:
            contents.append(f"*Group:* `{group}`")
        if desc:
            contents.append(desc)
        if doc:
            contents.append(doc)

        return {
            "contents": {
                "kind": "markdown",
                "value": "\n\n".join(contents),
            },
            "range": {
                "start": {"line": target_line_0, "character": target_token.col},
                "end": {"line": target_line_0, "character": target_token.col + len(lexeme)},
            },
        }

    def get_inlay_hints(self, uri: str) -> list[dict[str, Any]]:
        """Return parameter and type hints for the requested document."""
        session = self.documents.get(uri)
        if session is None or not session.tokens:
            return []

        hints_index = self.analysis_cache.get("indexes", {}).get("inlay_hints", [])
        hints_result: list[dict[str, Any]] = []

        for item in hints_index:
            r_name = item.get("rule", "")
            text = item.get("text", "")
            kind = 1 if item.get("kind") == "Type" else 2

            for tok in session.tokens:
                tok_line_0 = tok.line - 1 if tok.line > 0 else 0
                if tok.token == Token.KEYWORD and str(tok.value).lower() in r_name.lower():
                    hints_result.append({
                        "position": {"line": tok_line_0, "character": tok.col + len(str(tok.value))},
                        "label": f": {text.splitlines()[0]}",
                        "kind": kind,
                        "paddingLeft": True,
                    })

        return hints_result


__all__ = ["DocumentSession", "LSPState"]
