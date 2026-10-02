"""
Servidor de Lenguaje Nativo de Gram — Language Server Protocol (`gram.vsix.lsp`).
================================================================================
Implementa la especificación del protocolo LSP (Language Server Protocol) sobre JSON-RPC
para proveer capacidades de edición inteligente a VS Code y cualquier editor compatible:
  1. Marcado de Errores y Diagnósticos en tiempo real (`textDocument/publishDiagnostics`).
  2. Autocompletado inteligente de tokens, palabras clave y reglas (`textDocument/completion`).
  3. Inspección emergente de documentación y tipos (`textDocument/hover`).
  4. Sincronización continua de documentos (`textDocument/didOpen`, `didChange`, `didSave`).
"""
from __future__ import annotations

import io
import json
from pathlib import Path
import re
import sys
from typing import Any
from urllib.parse import unquote, urlparse

from gram.core.hints import Hints, InlayHintKind, VirtualHint, VirtualHintManager
from gram.core.lexer import Lexer, Token, words
from gram.core.parser import Parser
from gram.utilities import error
from gram.vsix.extract import SyntaxMetadata, extract_metadata


class GramLanguageServer:
    """
    Servidor de lenguaje LSP ligero, determinista y autocontenido para Gram Framework.
    Opera sobre flujos de entrada/salida estándar usando JSON-RPC 2.0.
    """

    def __init__(
        self,
        stream_in: io.TextIOBase | None = None,
        stream_out: io.TextIOBase | None = None,
        metadata: SyntaxMetadata | None = None,
    ) -> None:
        self.stream_in = stream_in or sys.stdin
        self.stream_out = stream_out or sys.stdout
        self.metadata = metadata or extract_metadata()
        self.documents: dict[str, str] = {}
        self.hint_managers: dict[str, VirtualHintManager] = {}
        self.is_running: bool = True

    def run(self) -> None:
        """Bucle principal de procesamiento de mensajes JSON-RPC."""
        while self.is_running:
            try:
                line = self.stream_in.readline()
                if not line:
                    break

                line_str = line.strip()
                if not line_str.startswith("Content-Length:"):
                    continue

                content_length = int(line_str.split(":", 1)[1].strip())
                # Consumir líneas de separación \r\n
                while True:
                    sep = self.stream_in.readline().strip()
                    if not sep:
                        break

                body = self.stream_in.read(content_length)
                if not body:
                    break

                request = json.loads(body)
                self.handle_message(request)
            except (EOFError, KeyboardInterrupt):
                break
            except Exception:
                pass

    def send_response(self, response: dict[str, Any]) -> None:
        """Serializa y envía una respuesta JSON-RPC con cabecera Content-Length."""
        try:
            body = json.dumps(response, ensure_ascii=False)
            body_bytes = body.encode("utf-8")
            header = f"Content-Length: {len(body_bytes)}\r\n\r\n"
            if hasattr(self.stream_out, "buffer"):
                self.stream_out.buffer.write(header.encode("ascii"))
                self.stream_out.buffer.write(body_bytes)
                self.stream_out.buffer.flush()
            else:
                self.stream_out.write(header)
                self.stream_out.write(body)
                self.stream_out.flush()
        except Exception:
            pass

    def send_notification(self, method: str, params: dict[str, Any]) -> None:
        """Envía una notificación unidireccional al cliente LSP."""
        msg = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        }
        self.send_response(msg)

    def handle_message(self, msg: dict[str, Any]) -> None:
        """Despacha las peticiones y notificaciones según el método LSP."""
        method = msg.get("method")
        msg_id = msg.get("id")
        params = msg.get("params", {})

        if method == "initialize":
            self.handle_initialize(msg_id, params)
        elif method == "initialized":
            pass
        elif method == "shutdown":
            self.send_response({"jsonrpc": "2.0", "id": msg_id, "result": None})
        elif method == "exit":
            self.is_running = False
        elif method == "textDocument/didOpen":
            doc = params.get("textDocument", {})
            uri = doc.get("uri", "")
            text = doc.get("text", "")
            self.documents[uri] = text
            self.validate_and_publish_diagnostics(uri, text)
        elif method == "textDocument/didChange":
            doc = params.get("textDocument", {})
            uri = doc.get("uri", "")
            changes = params.get("contentChanges", [])
            if changes:
                text = changes[-1].get("text", "")
                self.documents[uri] = text
                self.validate_and_publish_diagnostics(uri, text)
        elif method == "textDocument/didSave":
            doc = params.get("textDocument", {})
            uri = doc.get("uri", "")
            text = self.documents.get(uri, "")
            if text:
                self.validate_and_publish_diagnostics(uri, text)
        elif method == "textDocument/didClose":
            doc = params.get("textDocument", {})
            uri = doc.get("uri", "")
            self.documents.pop(uri, None)
            self.send_notification("textDocument/publishDiagnostics", {"uri": uri, "diagnostics": []})
        elif method == "textDocument/completion":
            self.handle_completion(msg_id, params)
        elif method == "textDocument/hover":
            self.handle_hover(msg_id, params)
        elif method == "textDocument/inlayHint":
            self.handle_inlay_hint(msg_id, params)
        elif msg_id is not None:
            self.send_response({"jsonrpc": "2.0", "id": msg_id, "result": None})

    def handle_initialize(self, msg_id: Any, params: dict[str, Any]) -> None:
        """Responde a la negociación de capacidades iniciales del cliente."""
        self.workspace_root = (
            params.get("rootUri")
            or params.get("rootPath")
        )
        capabilities = {
            "textDocumentSync": 1,  # 1 = Full
            "completionProvider": {
                "resolveProvider": False,
                "triggerCharacters": [".", ":", " ", '"', "'", "/", "\\"],
            },
            "hoverProvider": True,
            "inlayHintProvider": True,
        }
        res = {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "capabilities": capabilities,
                "serverInfo": {
                    "name": "Gram Language Server",
                    "version": "1.0.0",
                },
            },
        }
        self.send_response(res)

    def validate_and_publish_diagnostics(self, uri: str, text: str) -> None:
        """
        Ejecuta el análisis sintáctico del código fuente y publica diagnósticos de error.
        Soporta archivos .glang mediante el compilador DSL y código general con Lexer/Parser.
        """
        diagnostics: list[dict[str, Any]] = []

        is_glang = uri.endswith(".glang") or "define " in text or "Keyword " in text

        if is_glang:
            try:
                from gram.glang.main import parse_dsl
                parse_dsl(text)
            except error.Error as exc:
                diagnostics.append(self._error_to_diagnostic(exc, text))
            except Exception as exc:
                diagnostics.append({
                    "range": {
                        "start": {"line": 0, "character": 0},
                        "end": {"line": 0, "character": 10},
                    },
                    "severity": 1,  # Error
                    "source": "Gram.GLang",
                    "message": str(exc),
                })
        else:
            try:
                lex = Lexer(text)
                tokens = lex.process()
                p = Parser(tokens)
                from gram.native.rules import DECLARATION, PROGRAM
                from gram.core.combinators import Many, Ref
                base_grammar = {
                    PROGRAM: Many(Ref(DECLARATION)),
                    DECLARATION: DECLARATION.grammar,
                }
                p.parse(base_grammar)
            except error.Error as exc:
                diagnostics.append(self._error_to_diagnostic(exc, text))
            except Exception:
                pass

        self.send_notification("textDocument/publishDiagnostics", {
            "uri": uri,
            "diagnostics": diagnostics,
        })

    def _error_to_diagnostic(self, exc: error.Error, text: str) -> dict[str, Any]:
        """Convierte una excepción de Gram en un objeto Diagnostic de LSP."""
        line = getattr(exc, "line", 0) or 0
        col = getattr(exc, "col", 0) or getattr(exc, "column", 0) or 0
        code = getattr(exc, "code", "GRAM_ERROR")
        msg = getattr(exc, "message", str(exc))

        # LSP usa índices base-0 para líneas y columnas
        lsp_line = max(0, int(line) - 1) if int(line) > 0 else 0
        lsp_col = max(0, int(col) - 1) if int(col) > 0 else 0

        # Determinar longitud del rango a subrayar
        lines = text.splitlines()
        line_len = len(lines[lsp_line]) if 0 <= lsp_line < len(lines) else 10
        end_col = min(line_len, max(lsp_col + 1, lsp_col + 5))

        return {
            "range": {
                "start": {"line": lsp_line, "character": lsp_col},
                "end": {"line": lsp_line, "character": end_col},
            },
            "severity": 1,  # 1 = Error
            "code": str(code),
            "source": "Gram",
            "message": f"[{code}] {msg}",
        }

    def handle_completion(self, msg_id: Any, params: dict[str, Any]) -> None:
        """Retorna la lista de autocompletado para la posición del cursor."""
        items: list[dict[str, Any]] = []

        # 0. Contexto de posición y documento para consultas dinámicas (Query)
        pos = params.get("position", {})
        line_idx = pos.get("line", 0)
        col_idx = pos.get("character", 0)
        uri = params.get("textDocument", {}).get("uri", "")

        doc_text = self.documents.get(uri, "")
        lines = doc_text.splitlines()

        # Determinar directorio base del documento o espacio de trabajo
        doc_dir: Path | None = None
        if uri:
            try:
                parsed_uri = urlparse(uri)
                if parsed_uri.scheme == "file":
                    p_str = unquote(parsed_uri.path)
                    if len(p_str) > 2 and p_str[0] == "/" and p_str[2] == ":":
                        p_str = p_str[1:]
                    doc_dir = Path(p_str).parent
            except Exception:
                pass
        if not doc_dir and getattr(self, "workspace_root", None):
            try:
                parsed_ws = urlparse(str(self.workspace_root))
                ws_path = unquote(parsed_ws.path) if parsed_ws.scheme == "file" else str(self.workspace_root)
                if len(ws_path) > 2 and ws_path[0] == "/" and ws_path[2] == ":":
                    ws_path = ws_path[1:]
                doc_dir = Path(ws_path)
            except Exception:
                pass

        # 1. Ejecución de queries dinámicos configurados en reglas (Query.query_roots)
        if 0 <= line_idx < len(lines):
            line_prefix = lines[line_idx][:col_idx]
            quote_match = re.search(r'["\']([^"\']*)$', line_prefix)
            if quote_match:
                current_token_val = quote_match.group(1)
            else:
                word_match = re.search(r'(\S+)$', line_prefix)
                current_token_val = word_match.group(1) if word_match else ""

            line_words = set(re.findall(r'[a-zA-Z_0-9]+', line_prefix.lower()))

            for r_name, r_meta in self.metadata.rules.items():
                r_queries = getattr(r_meta, "queries", None)
                if not r_queries:
                    continue

                r_clean = r_name.lower().replace("_stmt", "").replace("_rule", "").replace("_decl", "")

                for q in r_queries:
                    triggers = [t.lower() for t in getattr(q, "trigger_keywords", [])]
                    matches = False
                    if triggers:
                        matches = any(t in line_words for t in triggers)
                    else:
                        matches = (r_clean in line_words or r_name.lower() in line_words)

                    if matches and hasattr(q, "execute") and callable(q.execute):
                        q_items = q.execute(token_text=current_token_val, base_dir=doc_dir)
                        for q_idx, item in enumerate(q_items):
                            items.append({
                                "label": item["label"],
                                "kind": item.get("kind", 17),
                                "detail": item.get("detail", ""),
                                "documentation": {
                                    "kind": "markdown",
                                    "value": item.get("documentation", ""),
                                },
                                "insertText": item.get("insertText", item["label"]),
                                "sortText": f"0000_{q_idx:04d}_{item['label']}",
                            })

        # 2. Sugerencias extraídas de metadatos de Gram
        all_sug = self.metadata.get_all_suggestions()
        for idx, sug in enumerate(all_sug):
            kind_map = {
                "Keyword": 14,
                "Class": 7,
                "Snippet": 15,
                "Property": 10,
            }
            items.append({
                "label": sug["label"],
                "kind": kind_map.get(sug.get("kind", "Keyword"), 14),
                "detail": sug.get("detail", ""),
                "documentation": {
                    "kind": "markdown",
                    "value": sug.get("documentation", ""),
                },
                "insertText": sug.get("insertText", sug["label"]),
                "sortText": f"{idx + 1000:04d}",
            })

        # 3. Sugerencias de tokens disponibles
        for tok_name in self.metadata.token_types:
            items.append({
                "label": f"tokens.{tok_name}",
                "kind": 10,  # Property
                "detail": f"Token Gram: {tok_name}",
                "documentation": f"Coincidencia con token léxico `{tok_name}`.",
                "insertText": f"tokens.{tok_name}",
                "sortText": f"9000_{tok_name}",
            })

        res = {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "isIncomplete": False,
                "items": items,
            },
        }
        self.send_response(res)

    def handle_hover(self, msg_id: Any, params: dict[str, Any]) -> None:
        """Retorna información flotante de documentación para el símbolo bajo el cursor."""
        pos = params.get("position", {})
        line_idx = pos.get("line", 0)
        col_idx = pos.get("character", 0)
        uri = params.get("textDocument", {}).get("uri", "")

        doc_text = self.documents.get(uri, "")
        lines = doc_text.splitlines()

        word_under_cursor = ""
        if 0 <= line_idx < len(lines):
            target_line = lines[line_idx]
            for match in re.finditer(r"[a-zA-Z_0-9]+", target_line):
                if match.start() <= col_idx <= match.end():
                    word_under_cursor = match.group(0)
                    break

        markdown_doc = ""
        if word_under_cursor in self.metadata.keywords:
            kw = self.metadata.keywords[word_under_cursor]
            markdown_doc = f"**Gram Keyword:** `{kw.name}`\n\n{kw.description}\n\n*Color:* `{kw.hex_color}` | *Grupo:* `{kw.group or 'General'}`"
        elif word_under_cursor in self.metadata.rules:
            r = self.metadata.rules[word_under_cursor]
            markdown_doc = f"**Gram Rule:** `{r.name}` (código `{r.code}`)\n\n{r.description or r.docs}\n\n*Ámbito:* `{r.scope}`"

        result = None
        if markdown_doc:
            result = {
                "contents": {
                    "kind": "markdown",
                    "value": markdown_doc,
                }
            }

        self.send_response({"jsonrpc": "2.0", "id": msg_id, "result": result})

    def get_hint_manager(self, uri: str) -> VirtualHintManager:
        """Obtiene o crea el VirtualHintManager asignado al documento."""
        if uri not in self.hint_managers:
            self.hint_managers[uri] = VirtualHintManager()
        return self.hint_managers[uri]

    def populate_rule_hints(self, uri: str, text: str, manager: VirtualHintManager) -> None:
        """Calcula dinámicamente las pistas virtuales asociadas a reglas RuleItem con hints."""
        if not text:
            manager.clear()
            return

        rules_with_hints = {
            r_name: r_meta
            for r_name, r_meta in self.metadata.rules.items()
            if getattr(r_meta, "hints", None)
        }
        if not rules_with_hints:
            return

        # Limpiar únicamente pistas calculadas automáticamente por el AST
        ast_ids = [hid for hid in list(manager._hints.keys()) if hid.startswith("ast_")]
        for hid in ast_ids:
            manager.remove_virtual(hid)

        from gram import config

        old_hide = getattr(config, "ERROR_HIDE_CONSOLE", False)
        config.ERROR_HIDE_CONSOLE = True

        try:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                lex = Lexer(text)
                tokens = lex.process()

                from gram.native.rules import DECLARATION, PROGRAM, RULES_BY_NAME
                from gram.core.combinators import Alt, Many, Ref
                from gram.core.ast.nodes import ASTNode

            available_refs = [
                Ref(r) for r in RULES_BY_NAME.values()
                if getattr(r, "grammar", None) is not None and getattr(r, "name", "") != "PROGRAM"
            ]
            decl_comb = Alt(*available_refs) if available_refs else DECLARATION.grammar

            if decl_comb is not None:
                base_grammar = {
                    PROGRAM: Many(Ref(DECLARATION)),
                    DECLARATION: decl_comb,
                }
                for r in RULES_BY_NAME.values():
                    if getattr(r, "grammar", None) is not None:
                        base_grammar[r] = r.grammar

                p = Parser(tokens)
                ast = p.parse(base_grammar)

            def _visit(node: Any) -> None:
                if not isinstance(node, ASTNode):
                    return
                r_name = getattr(node, "name", "")
                r_meta = self.metadata.rules.get(r_name)
                hints_map = getattr(r_meta, "hints", {}) if r_meta else {}
                if not hints_map and hasattr(node, "rule"):
                    hints_map = getattr(node.rule, "hints", {}) or {}

                if hints_map and getattr(node, "tokens", None):
                    for tok_idx, hint_spec in hints_map.items():
                        if 0 <= tok_idx < len(node.tokens):
                            target_tok = node.tokens[tok_idx]
                            proc_res = None
                            if hasattr(hint_spec, "process") and callable(hint_spec.process):
                                proc_res = hint_spec.process(target_tok)
                            elif callable(hint_spec):
                                proc_res = hint_spec(target_tok)

                            if proc_res:
                                lsp_line = max(0, getattr(target_tok, "line", 1) - 1)
                                tok_val = str(getattr(target_tok, "value", "") or "")
                                lsp_col = getattr(target_tok, "col", 0) + len(tok_val)
                                h_kind = getattr(hint_spec, "kind", InlayHintKind.Type)
                                h_p_left = getattr(hint_spec, "padding_left", True)
                                h_p_right = getattr(hint_spec, "padding_right", False)
                                h_desc = getattr(hint_spec, "description", "")
                                manager.insert_virtual(
                                    id=f"ast_{r_name}_{tok_idx}_{target_tok.line}_{target_tok.col}",
                                    line=lsp_line,
                                    character=lsp_col,
                                    text=proc_res,
                                    kind=h_kind,
                                    padding_left=h_p_left,
                                    padding_right=h_p_right,
                                    description=h_desc,
                                )

                for child in getattr(node, "children", []):
                    _visit(child)

            if ast and hasattr(ast, "body"):
                for stmt in ast.body:
                    _visit(stmt)
        except Exception:
            pass
        finally:
            config.ERROR_HIDE_CONSOLE = old_hide

    def handle_inlay_hint(self, msg_id: Any, params: dict[str, Any]) -> None:
        """Retorna las pistas visuales virtuales (Inlay Hints) para el documento y rango dados."""
        uri = params.get("textDocument", {}).get("uri", "")
        range_info = params.get("range", {})
        start_line = range_info.get("start", {}).get("line", 0)
        end_line = range_info.get("end", {}).get("line", 100000)

        manager = self.get_hint_manager(uri)
        doc_text = self.documents.get(uri, "")

        self.populate_rule_hints(uri, doc_text, manager)
        hints = manager.to_lsp_inlay_hints(start_line=start_line, end_line=end_line)
        self.send_response({"jsonrpc": "2.0", "id": msg_id, "result": hints})


def start_lsp_server() -> None:
    """Punto de entrada para ejecutar el servidor LSP sobre la consola estándar."""
    server = GramLanguageServer()
    server.run()


if __name__ == "__main__":
    start_lsp_server()
