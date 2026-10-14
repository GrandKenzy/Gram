"""
Language Server Protocol JSON-RPC Server (`gram.vsix.lsp.server`).
==================================================================
Implements a pure Python, zero-dependency JSON-RPC 2.0 server over stdio,
handling LSP lifecycle methods (`initialize`, `didOpen`, `didChange`,
`completion`, `hover`, `inlayHint`, `publishDiagnostics`).
"""
from __future__ import annotations

import argparse
import importlib
import importlib.util
import io
import json
from pathlib import Path
import sys
from typing import Any, BinaryIO

from gram.core.combinators.base import RuleItem
from gram.vsix.lsp.state import LSPState


class JSONRPCProtocol:
    """Handles encoding and decoding of standard LSP Content-Length frames."""

    @staticmethod
    def read_message(stream: BinaryIO) -> dict[str, Any] | None:
        """Read and decode a single Content-Length delimited JSON-RPC frame."""
        content_length: int | None = None

        while True:
            line = stream.readline()
            if not line:
                return None

            decoded = line.decode("latin1").strip()
            if not decoded:
                break

            if decoded.lower().startswith("content-length:"):
                parts = decoded.split(":", 1)
                try:
                    content_length = int(parts[1].strip())
                except ValueError:
                    content_length = None

        if content_length is None:
            return None

        body_bytes = stream.read(content_length)
        if len(body_bytes) < content_length:
            return None

        return json.loads(body_bytes.decode("utf-8"))

    @staticmethod
    def write_message(stream: BinaryIO, payload: dict[str, Any]) -> None:
        """Encode and transmit a single Content-Length delimited JSON-RPC frame."""
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("latin1")
        stream.write(header)
        stream.write(body)
        stream.flush()


def load_entrypoint(
    entrypoint_spec: str,
    workspace_dir: str | Path | None = None,
) -> type[RuleItem] | None:
    """
    Dynamically load a RuleItem subclass from an entrypoint specification.

    Accepts formats:
        - "module:ClassName"
        - "path/to/file.py:ClassName"
        - "module" (discovers primary RuleItem)
        - "path/to/file.py" (discovers primary RuleItem)
    """
    if workspace_dir is not None:
        ws_path = str(Path(workspace_dir).resolve())
        if ws_path not in sys.path:
            sys.path.insert(0, ws_path)

    if ":" in entrypoint_spec:
        mod_part, cls_part = entrypoint_spec.split(":", 1)
        cls_part = cls_part.strip()
    else:
        mod_part, cls_part = entrypoint_spec.strip(), None

    mod_part = mod_part.strip()
    target_module = None

    if mod_part.endswith(".py") or Path(mod_part).exists():
        py_file = Path(mod_part).resolve()
        parent_dir = str(py_file.parent)
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)
        module_name = py_file.stem
        spec = importlib.util.spec_from_file_location(module_name, py_file)
        if spec is not None and spec.loader is not None:
            target_module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = target_module
            spec.loader.exec_module(target_module)
    else:
        try:
            target_module = importlib.import_module(mod_part)
        except Exception:
            target_module = None

    if target_module is None:
        return None

    if cls_part:
        candidate = getattr(target_module, cls_part, None)
        if isinstance(candidate, type) and issubclass(candidate, RuleItem):
            return candidate

    candidates: list[type[RuleItem]] = []
    for attr_name in dir(target_module):
        val = getattr(target_module, attr_name)
        if isinstance(val, type) and issubclass(val, RuleItem) and val is not RuleItem:
            candidates.append(val)

    for preferred in ["PROGRAM", "ENTRYPOINT", "MAIN", "ROOT"]:
        for c in candidates:
            if c.__name__ == preferred:
                return c

    return candidates[-1] if candidates else None


def discover_workspace_entrypoint(workspace_dir: str | Path) -> type[RuleItem] | None:
    """Scan workspace directory for candidate Gram grammar entrypoints."""
    ws_path = Path(workspace_dir).resolve()
    if not ws_path.exists() or not ws_path.is_dir():
        return None

    if str(ws_path) not in sys.path:
        sys.path.insert(0, str(ws_path))

    discovery_names = ["prueba.py", "grammar.py", "main.py", "lang.py", "compiler.py", "rules.py"]
    for fname in discovery_names:
        target = ws_path / fname
        if target.exists():
            ep = load_entrypoint(str(target), ws_path)
            if ep is not None:
                return ep

    return None


class LSPServer:
    """
    Standard Language Server Protocol dispatch server communicating over stdio.
    """

    def __init__(
        self,
        entrypoint: type[RuleItem] | None = None,
        lsp_state: LSPState | None = None,
    ) -> None:
        self.state = lsp_state if lsp_state is not None else LSPState(entrypoint)
        self.is_running = False

    def handle_request(self, request: dict[str, Any], out_stream: BinaryIO) -> None:
        """Dispatch an incoming JSON-RPC request or notification."""
        req_id = request.get("id")
        method = request.get("method", "")
        params = request.get("params", {})

        if method == "initialize":
            root_uri = params.get("rootUri")
            ws_folders = params.get("workspaceFolders", [])
            workspace_path = None
            if root_uri and root_uri.startswith("file://"):
                from urllib.parse import unquote, urlparse
                parsed = urlparse(root_uri)
                workspace_path = unquote(parsed.path)
                if sys.platform == "win32" and workspace_path.startswith("/"):
                    workspace_path = workspace_path[1:]
            elif ws_folders and len(ws_folders) > 0:
                first_uri = ws_folders[0].get("uri", "")
                if first_uri.startswith("file://"):
                    from urllib.parse import unquote, urlparse
                    parsed = urlparse(first_uri)
                    workspace_path = unquote(parsed.path)
                    if sys.platform == "win32" and workspace_path.startswith("/"):
                        workspace_path = workspace_path[1:]

            init_options = params.get("initializationOptions", {})
            entrypoint_spec = init_options.get("entrypoint")

            if entrypoint_spec:
                ep = load_entrypoint(entrypoint_spec, workspace_path)
                if ep is not None:
                    self.state.set_entrypoint(ep)
            elif self.state.entrypoint is None and workspace_path:
                ep = discover_workspace_entrypoint(workspace_path)
                if ep is not None:
                    self.state.set_entrypoint(ep)

            capabilities = {
                "textDocumentSync": 1,
                "completionProvider": {
                    "resolveProvider": False,
                    "triggerCharacters": [".", " ", ":", "(", ")"],
                },
                "hoverProvider": True,
                "inlayHintProvider": True,
            }
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "capabilities": capabilities,
                    "serverInfo": {
                        "name": "gram-language-server",
                        "version": "0.2.0",
                    },
                },
            }
            JSONRPCProtocol.write_message(out_stream, response)
            return

        if method == "initialized":
            return

        if method == "shutdown":
            response = {"jsonrpc": "2.0", "id": req_id, "result": None}
            JSONRPCProtocol.write_message(out_stream, response)
            return

        if method == "exit":
            self.is_running = False
            return

        if method == "textDocument/didOpen":
            doc = params.get("textDocument", {})
            uri = doc.get("uri", "")
            text = doc.get("text", "")
            version = doc.get("version", 1)

            session = self.state.open_document(uri, text, version)
            session = self.state.analyze(uri)
            self._publish_diagnostics(out_stream, uri, session.diagnostics, session.version)
            return

        if method == "textDocument/didChange":
            doc = params.get("textDocument", {})
            uri = doc.get("uri", "")
            version = doc.get("version")
            changes = params.get("contentChanges", [])

            if changes:
                new_text = changes[-1].get("text", "")
                session = self.state.change_document(uri, new_text, version)
                session = self.state.analyze(uri)
                self._publish_diagnostics(out_stream, uri, session.diagnostics, session.version)
            return

        if method == "textDocument/didClose":
            doc = params.get("textDocument", {})
            uri = doc.get("uri", "")
            self.state.close_document(uri)
            return

        if method == "textDocument/completion":
            doc = params.get("textDocument", {})
            uri = doc.get("uri", "")
            pos = params.get("position", {})
            line = pos.get("line", 0)
            character = pos.get("character", 0)
            current_line = params.get("currentLine")

            completions = self.state.get_completions(uri, line, character, current_line=current_line)
            response = {"jsonrpc": "2.0", "id": req_id, "result": completions}
            JSONRPCProtocol.write_message(out_stream, response)
            return

        if method == "textDocument/hover":
            doc = params.get("textDocument", {})
            uri = doc.get("uri", "")
            pos = params.get("position", {})
            line = pos.get("line", 0)
            character = pos.get("character", 0)

            hover_data = self.state.get_hover(uri, line, character)
            response = {"jsonrpc": "2.0", "id": req_id, "result": hover_data}
            JSONRPCProtocol.write_message(out_stream, response)
            return

        if method == "textDocument/inlayHint":
            doc = params.get("textDocument", {})
            uri = doc.get("uri", "")

            hints_data = self.state.get_inlay_hints(uri)
            response = {"jsonrpc": "2.0", "id": req_id, "result": hints_data}
            JSONRPCProtocol.write_message(out_stream, response)
            return

        if req_id is not None:
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}",
                },
            }
            JSONRPCProtocol.write_message(out_stream, response)

    @staticmethod
    def _publish_diagnostics(
        out_stream: BinaryIO,
        uri: str,
        diagnostics: list[dict[str, Any]],
        version: int | None = None,
    ) -> None:
        """Transmit textDocument/publishDiagnostics notification to the client."""
        params: dict[str, Any] = {
            "uri": uri,
            "diagnostics": diagnostics,
        }
        if version is not None:
            params["version"] = version

        notification = {
            "jsonrpc": "2.0",
            "method": "textDocument/publishDiagnostics",
            "params": params,
        }
        JSONRPCProtocol.write_message(out_stream, notification)

    def serve(
        self,
        in_stream: BinaryIO | None = None,
        out_stream: BinaryIO | None = None,
    ) -> None:
        """Run the blocking JSON-RPC message processing loop."""
        input_channel = in_stream if in_stream is not None else sys.stdin.buffer
        output_channel = out_stream if out_stream is not None else sys.stdout.buffer

        self.is_running = True
        while self.is_running:
            try:
                message = JSONRPCProtocol.read_message(input_channel)
                if message is None:
                    break
                self.handle_request(message, output_channel)
            except Exception as e:
                err_response = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": -32603,
                        "message": f"Internal server error: {e}",
                    },
                }
                JSONRPCProtocol.write_message(output_channel, err_response)


def start_server(entrypoint: type[RuleItem] | None = None) -> None:
    """Launch the Language Server loop using standard process streams."""
    parser_args = argparse.ArgumentParser(description="Gram LSP Server")
    parser_args.add_argument("--entrypoint", "-e", type=str, default=None, help="Entrypoint grammar (module:Class)")
    parser_args.add_argument("--workspace", "-w", type=str, default=None, help="Workspace root directory")
    args, _ = parser_args.parse_known_args()

    resolved_entrypoint = entrypoint
    if resolved_entrypoint is None and args.entrypoint:
        resolved_entrypoint = load_entrypoint(args.entrypoint, args.workspace)

    if resolved_entrypoint is None and args.workspace:
        resolved_entrypoint = discover_workspace_entrypoint(args.workspace)

    server = LSPServer(entrypoint=resolved_entrypoint)
    server.serve()


if __name__ == "__main__":
    start_server()
