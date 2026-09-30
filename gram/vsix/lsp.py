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
import re
import sys
from typing import Any

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
        elif msg_id is not None:
            self.send_response({"jsonrpc": "2.0", "id": msg_id, "result": None})

    def handle_initialize(self, msg_id: Any, params: dict[str, Any]) -> None:
        """Responde a la negociación de capacidades iniciales del cliente."""
        capabilities = {
            "textDocumentSync": 1,  # 1 = Full
            "completionProvider": {
                "resolveProvider": False,
                "triggerCharacters": [".", ":", " ", '"', "'"],
            },
            "hoverProvider": True,
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

        # 1. Sugerencias extraídas de metadatos de Gram
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
                "sortText": f"{idx:04d}",
            })

        # 2. Sugerencias de tokens disponibles
        for tok_name in self.metadata.token_types:
            items.append({
                "label": f"tokens.{tok_name}",
                "kind": 10,  # Property
                "detail": f"Token Gram: {tok_name}",
                "documentation": f"Coincidencia con token léxico `{tok_name}`.",
                "insertText": f"tokens.{tok_name}",
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


def start_lsp_server() -> None:
    """Punto de entrada para ejecutar el servidor LSP sobre la consola estándar."""
    server = GramLanguageServer()
    server.run()


if __name__ == "__main__":
    start_lsp_server()
