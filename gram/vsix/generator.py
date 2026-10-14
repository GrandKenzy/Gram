"""
VS Code Extension and VSIX Manifest Generator (`gram.vsix.generator`).
======================================================================
Transforms canonical metadata from `VSIXAnalyzer` into valid VS Code extension
artifacts: `package.json`, `language-configuration.json`, TextMate grammar
`syntaxes/<lang>.tmLanguage.json`, and editor snippets `snippets/snippets.json`.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gram.vsix.info import PackageInfo, get_package_info


class VSIXGenerator:
    """
    Constructs and exports VS Code language package files from VSIXAnalyzer data.
    """

    def __init__(
        self,
        analysis_data: dict[str, Any],
        package_info: PackageInfo | None = None,
        *,
        language_id: str | None = None,
        language_name: str | None = None,
        file_extensions: list[str] | None = None,
        scope_name: str | None = None,
        publisher: str | None = None,
        version: str | None = None,
        description: str | None = None,
    ) -> None:
        self.data = analysis_data
        base_pkg = package_info if package_info is not None else get_package_info()
        self.package_info = base_pkg

        if language_id is not None:
            self.package_info.language_id = language_id.lower().strip()
        if language_name is not None:
            self.package_info.language_name = language_name
        if file_extensions is not None:
            self.package_info.file_extensions = file_extensions
        if scope_name is not None:
            self.package_info.scope_name = scope_name
        if publisher is not None:
            self.package_info.publisher = publisher
        if version is not None:
            self.package_info.version = version
        if description is not None:
            self.package_info.description = description

        self.language_id = self.package_info.language_id
        self.language_name = self.package_info.language_name
        self.file_extensions = self.package_info.file_extensions
        self.scope_name = self.package_info.scope_name
        self.publisher = self.package_info.publisher
        self.version = self.package_info.version
        self.description = self.package_info.description

    def build_manifest(self) -> dict[str, Any]:
        """Generate VS Code extension manifest (package.json)."""
        return self.package_info.to_manifest()

    def build_language_configuration(self) -> dict[str, Any]:
        """Generate language-configuration.json with brackets, comments, and indent rules."""
        meta = self.data.get("meta", {})
        comment_tok = meta.get("comment_token") or ";"

        indent_openers = ["block", "def", "func", "if", "for", "while"]
        indent_closers = ["end", "elif", "else"]

        lexicon_kws = self.data.get("lexicon", {}).get("keywords", {})
        if "block" in lexicon_kws and "end" in lexicon_kws:
            increase_pattern = r"^\s*(block|.*:)\s*$"
            decrease_pattern = r"^\s*(end)\b.*$"
        else:
            increase_pattern = r"^.*:\s*$"
            decrease_pattern = r"^\s*(end|else|elif)\b.*$"

        return {
            "comments": {
                "lineComment": comment_tok
            },
            "brackets": [
                ["{", "}"],
                ["[", "]"],
                ["(", ")"]
            ],
            "autoClosingPairs": [
                {"open": "{", "close": "}"},
                {"open": "[", "close": "]"},
                {"open": "(", "close": ")"},
                {"open": "\"", "close": "\""},
                {"open": "'", "close": "'"}
            ],
            "surroundingPairs": [
                {"open": "{", "close": "}"},
                {"open": "[", "close": "]"},
                {"open": "(", "close": ")"},
                {"open": "\"", "close": "\""},
                {"open": "'", "close": "'"}
            ],
            "indentationRules": {
                "increaseIndentPattern": increase_pattern,
                "decreaseIndentPattern": decrease_pattern
            }
        }

    def build_tm_grammar(self) -> dict[str, Any]:
        """Generate TextMate syntax grammar (syntaxes/<lang>.tmLanguage.json)."""
        meta = self.data.get("meta", {})
        comment_tok = meta.get("comment_token") or ";"
        lexicon = self.data.get("lexicon", {})
        groups = lexicon.get("groups", {})
        keywords_dict = lexicon.get("keywords", {})
        colors_index = self.data.get("indexes", {}).get("colors", {})

        scope_override_by_keyword: dict[str, str] = {}
        for rule_name, color_map in colors_index.items():
            for key, scope_or_hex in color_map.items():
                if isinstance(scope_or_hex, str) and "." in scope_or_hex and not scope_or_hex.startswith("#"):
                    scope_override_by_keyword[str(key)] = scope_or_hex

        repo: dict[str, Any] = {
            "comments": {
                "patterns": [
                    {
                        "name": f"comment.line.semicolon.{self.language_id}",
                        "match": f"{comment_tok}.*$"
                    }
                ]
            },
            "strings": {
                "patterns": [
                    {
                        "name": f"string.quoted.double.{self.language_id}",
                        "begin": "\"",
                        "end": "\"",
                        "patterns": [
                            {"name": f"constant.character.escape.{self.language_id}", "match": r"\\."}
                        ]
                    },
                    {
                        "name": f"string.quoted.single.{self.language_id}",
                        "begin": "'",
                        "end": "'",
                        "patterns": [
                            {"name": f"constant.character.escape.{self.language_id}", "match": r"\\."}
                        ]
                    }
                ]
            },
            "numbers": {
                "patterns": [
                    {
                        "name": f"constant.numeric.{self.language_id}",
                        "match": r"\b\d+(\.\d+)?\b"
                    }
                ]
            }
        }

        keyword_patterns: list[dict[str, str]] = []

        for kw_name, kw_info in keywords_dict.items():
            if kw_name in scope_override_by_keyword:
                kw_scope = scope_override_by_keyword[kw_name]
            else:
                kw_group = kw_info.get("group", "")
                if kw_group in scope_override_by_keyword:
                    kw_scope = scope_override_by_keyword[kw_group]
                elif kw_group == "types":
                    kw_scope = f"storage.type.{self.language_id}"
                elif kw_name in ("return", "yield", "break", "continue"):
                    kw_scope = f"keyword.control.flow.{self.language_id}"
                elif kw_name in ("import", "from", "export", "as"):
                    kw_scope = f"keyword.control.import.{self.language_id}"
                elif kw_name in ("block", "end", "namespace", "module"):
                    kw_scope = f"keyword.control.block.{self.language_id}"
                else:
                    kw_scope = f"keyword.other.{self.language_id}"

            keyword_patterns.append({
                "name": kw_scope,
                "match": rf"\b{kw_name}\b"
            })

        repo["keywords"] = {"patterns": keyword_patterns}

        root_patterns = [
            {"include": "#comments"},
            {"include": "#strings"},
            {"include": "#numbers"},
            {"include": "#keywords"}
        ]

        return {
            "$schema": "https://raw.githubusercontent.com/martinring/tmlanguage/master/tmlanguage.json",
            "name": self.language_name,
            "scopeName": self.scope_name,
            "patterns": root_patterns,
            "repository": repo
        }

    def build_snippets(self) -> dict[str, Any]:
        """Generate VS Code snippet dictionary for snippets/snippets.json."""
        snippets: dict[str, Any] = {}
        rules_dict = self.data.get("rules", {})

        for r_name, r_info in rules_dict.items():
            hints = r_info.get("hints", {})
            desc = r_info.get("description", "")
            for idx, h_text in hints.items():
                clean_lines = [line.strip() for line in h_text.splitlines() if line.strip()]
                if not clean_lines:
                    continue
                first_token = clean_lines[0].split()[0] if clean_lines[0].split() else r_name
                prefix = first_token.lower()
                snippets[f"{r_name} Snippet"] = {
                    "prefix": prefix,
                    "body": h_text.splitlines(),
                    "description": desc or f"Insert {r_name} declaration syntax."
                }

        completions = self.data.get("indexes", {}).get("completions", [])
        for comp in completions:
            label = comp.get("label", "")
            kind = comp.get("kind", "")
            rule = comp.get("rule", "")
            doc = comp.get("documentation", "")
            if kind == "Snippet" and label and f"{rule}_{label}" not in snippets:
                snippets[f"Keyword {label}"] = {
                    "prefix": label,
                    "body": [f"{label} "],
                    "description": doc or f"Insert {label} keyword."
                }

        return snippets

    def build_client_script(self) -> str:
        """Generate vanilla JavaScript client entrypoint (extension.js) for VS Code."""
        lang_id = json.dumps(self.language_id)
        meta = self.data.get("meta", {})
        ep_mod = meta.get("entrypoint_module", "prueba")
        ep_cls = meta.get("entrypoint_class") or meta.get("entrypoint") or "PROGRAM"
        default_ep = json.dumps(f"{ep_mod}:{ep_cls}")
        channel_name = json.dumps(f"{self.language_name} Language Server")

        return f'''const vscode = require('vscode');
const {{ spawn }} = require('child_process');
const path = require('path');

const LANGUAGE_ID = {lang_id};
const DEFAULT_ENTRYPOINT = {default_ep};

let serverProcess = null;
let diagnosticCollection = null;
let outputChannel = null;
let messageId = 0;
const pendingRequests = new Map();
let incomingBuffer = Buffer.alloc(0);

function log(msg) {{
    if (outputChannel) {{
        outputChannel.appendLine(msg);
    }}
}}

function send(msg) {{
    if (!serverProcess || !serverProcess.stdin || !serverProcess.stdin.writable) {{
        return;
    }}
    const body = Buffer.from(JSON.stringify(msg), 'utf8');
    const header = Buffer.from('Content-Length: ' + body.length + '\\r\\n\\r\\n', 'ascii');
    serverProcess.stdin.write(Buffer.concat([header, body]));
}}

function sendRequest(method, params) {{
    return new Promise((resolve, reject) => {{
        const id = ++messageId;
        pendingRequests.set(id, {{ resolve, reject }});
        send({{ jsonrpc: '2.0', id, method, params }});
    }});
}}

function sendNotification(method, params) {{
    send({{ jsonrpc: '2.0', method, params }});
}}

function handleMessage(message) {{
    if (message.id !== undefined && pendingRequests.has(message.id)) {{
        const entry = pendingRequests.get(message.id);
        pendingRequests.delete(message.id);
        if (message.error) {{
            log('[Gram LSP Error] ' + (message.error.message || JSON.stringify(message.error)));
            entry.reject(message.error);
        }} else {{
            entry.resolve(message.result);
        }}
        return;
    }}

    if (message.method === 'textDocument/publishDiagnostics') {{
        const params = message.params || {{}};
        const uri = vscode.Uri.parse(params.uri);
        const rawDiagnostics = params.diagnostics || [];
        log('[Gram LSP] Published ' + rawDiagnostics.length + ' diagnostic(s) for ' + params.uri);
        const diagnostics = rawDiagnostics.map(d => {{
            const start = new vscode.Position(d.range.start.line, d.range.start.character);
            const end = new vscode.Position(d.range.end.line, d.range.end.character);
            const range = new vscode.Range(start, end);
            let severity = vscode.DiagnosticSeverity.Error;
            if (d.severity === 2) severity = vscode.DiagnosticSeverity.Warning;
            else if (d.severity === 3) severity = vscode.DiagnosticSeverity.Information;
            else if (d.severity === 4) severity = vscode.DiagnosticSeverity.Hint;
            return new vscode.Diagnostic(range, d.message, severity);
        }});
        if (diagnosticCollection) {{
            diagnosticCollection.set(uri, diagnostics);
        }}
    }}
}}

function handleData(chunk) {{
    incomingBuffer = Buffer.concat([incomingBuffer, chunk]);
    while (true) {{
        const headerEnd = incomingBuffer.indexOf('\\r\\n\\r\\n');
        if (headerEnd === -1) {{
            break;
        }}
        const headerStr = incomingBuffer.slice(0, headerEnd).toString('ascii');
        const match = headerStr.match(/content-length:\\s*(\\d+)/i);
        if (!match) {{
            incomingBuffer = incomingBuffer.slice(headerEnd + 4);
            continue;
        }}
        const contentLength = parseInt(match[1], 10);
        const bodyStart = headerEnd + 4;
        const bodyEnd = bodyStart + contentLength;
        if (incomingBuffer.length < bodyEnd) {{
            break;
        }}
        const bodyBuffer = incomingBuffer.slice(bodyStart, bodyEnd);
        incomingBuffer = incomingBuffer.slice(bodyEnd);
        try {{
            const message = JSON.parse(bodyBuffer.toString('utf8'));
            handleMessage(message);
        }} catch (err) {{
            log('[Gram LSP Frame Error] Failed to parse message: ' + err);
        }}
    }}
}}

function startServerProcess(context) {{
    const config = vscode.workspace.getConfiguration(LANGUAGE_ID);
    const pythonCmd = config.get('pythonPath') || 'python';
    const entrypoint = config.get('entrypoint') || DEFAULT_ENTRYPOINT;
    const wsFolders = vscode.workspace.workspaceFolders;
    const wsPath = wsFolders && wsFolders.length > 0 ? wsFolders[0].uri.fsPath : null;

    const env = Object.assign({{}}, process.env);
    if (wsPath) {{
        env.PYTHONPATH = env.PYTHONPATH ? (wsPath + path.delimiter + env.PYTHONPATH) : wsPath;
    }}

    const args = ['-u', '-m', 'gram.vsix.lsp.server'];
    if (entrypoint) {{
        args.push('--entrypoint', entrypoint);
    }}
    if (wsPath) {{
        args.push('--workspace', wsPath);
    }}

    log('[Gram LSP] Spawning: ' + pythonCmd + ' ' + args.join(' '));
    log('[Gram LSP] Workspace directory: ' + (wsPath || process.cwd()));

    try {{
        serverProcess = spawn(pythonCmd, args, {{
            cwd: wsPath || undefined,
            env: env,
            stdio: ['pipe', 'pipe', 'pipe']
        }});
    }} catch (e) {{
        log('[Gram LSP Launch Error]: ' + e);
        return;
    }}

    if (serverProcess.stdout) {{
        serverProcess.stdout.on('data', handleData);
    }}
    if (serverProcess.stderr) {{
        serverProcess.stderr.on('data', data => {{
            log('[Gram LSP Server Stderr]: ' + data.toString().trim());
        }});
    }}
    serverProcess.on('error', err => {{
        log('[Gram LSP Process Error]: ' + err);
    }});
    serverProcess.on('close', code => {{
        log('[Gram LSP Process Closed]: code ' + code);
    }});

    sendRequest('initialize', {{
        processId: process.pid,
        rootUri: wsPath ? vscode.Uri.file(wsPath).toString() : null,
        initializationOptions: {{
            entrypoint: entrypoint
        }},
        capabilities: {{}}
    }}).then(() => {{
        log('[Gram LSP] Initialized successfully.');
        sendNotification('initialized', {{}});
        vscode.workspace.textDocuments.forEach(doc => {{
            if (doc.languageId === LANGUAGE_ID) {{
                sendNotification('textDocument/didOpen', {{
                    textDocument: {{
                        uri: doc.uri.toString(),
                        languageId: doc.languageId,
                        version: doc.version,
                        text: doc.getText()
                    }}
                }});
            }}
        }});
    }}).catch(err => {{
        log('[Gram LSP Initialize Failed]: ' + (err.message || JSON.stringify(err)));
    }});
}}

function activate(context) {{
    outputChannel = vscode.window.createOutputChannel({channel_name});
    context.subscriptions.push(outputChannel);
    log('[Gram LSP] Activating extension for language ' + LANGUAGE_ID);

    diagnosticCollection = vscode.languages.createDiagnosticCollection(LANGUAGE_ID);
    context.subscriptions.push(diagnosticCollection);

    startServerProcess(context);

    context.subscriptions.push(
        vscode.commands.registerCommand(LANGUAGE_ID + '.restartServer', () => {{
            log('[Gram LSP] Restarting Language Server...');
            deactivate();
            startServerProcess(context);
        }})
    );

    context.subscriptions.push(
        vscode.workspace.onDidOpenTextDocument(doc => {{
            if (doc.languageId !== LANGUAGE_ID) return;
            sendNotification('textDocument/didOpen', {{
                textDocument: {{
                    uri: doc.uri.toString(),
                    languageId: doc.languageId,
                    version: doc.version,
                    text: doc.getText()
                }}
            }});
        }}),
        vscode.workspace.onDidChangeTextDocument(event => {{
            if (event.document.languageId !== LANGUAGE_ID) return;
            sendNotification('textDocument/didChange', {{
                textDocument: {{
                    uri: event.document.uri.toString(),
                    version: event.document.version
                }},
                contentChanges: [
                    {{ text: event.document.getText() }}
                ]
            }});
        }}),
        vscode.workspace.onDidCloseTextDocument(doc => {{
            if (doc.languageId !== LANGUAGE_ID) return;
            if (diagnosticCollection) {{
                diagnosticCollection.delete(doc.uri);
            }}
            sendNotification('textDocument/didClose', {{
                textDocument: {{ uri: doc.uri.toString() }}
            }});
        }})
    );

    context.subscriptions.push(
        vscode.languages.registerCompletionItemProvider(
            {{ language: LANGUAGE_ID }},
            {{
                async provideCompletionItems(document, position) {{
                    try {{
                        const lineText = document.lineAt(position.line).text;
                        const result = await sendRequest('textDocument/completion', {{
                            textDocument: {{ uri: document.uri.toString() }},
                            position: {{ line: position.line, character: position.character }},
                            currentLine: lineText
                        }});
                        if (!Array.isArray(result)) return [];
                        return result.map(item => {{
                            const completion = new vscode.CompletionItem(item.label);
                            if (item.kind !== undefined) completion.kind = item.kind;
                            if (item.detail) completion.detail = item.detail;
                            if (item.documentation) {{
                                if (typeof item.documentation === 'string') {{
                                    completion.documentation = new vscode.MarkdownString(item.documentation);
                                }} else if (item.documentation && item.documentation.value) {{
                                    completion.documentation = new vscode.MarkdownString(item.documentation.value);
                                }}
                            }}
                            if (item.insertText) completion.insertText = item.insertText;
                            if (item.sortText) completion.sortText = item.sortText;
                            if (item.filterText) completion.filterText = item.filterText;
                            if (item.range) {{
                                completion.range = new vscode.Range(
                                    item.range.start.line,
                                    item.range.start.character,
                                    item.range.end.line,
                                    item.range.end.character
                                );
                            }}
                            return completion;
                        }});
                    }} catch (e) {{
                        return [];
                    }}
                }}
            }},
            '.', ' ', ':', '(', ')'
        )
    );

    context.subscriptions.push(
        vscode.languages.registerHoverProvider(
            {{ language: LANGUAGE_ID }},
            {{
                async provideHover(document, position) {{
                    try {{
                        const result = await sendRequest('textDocument/hover', {{
                            textDocument: {{ uri: document.uri.toString() }},
                            position: {{ line: position.line, character: position.character }}
                        }});
                        if (!result || !result.contents) return null;
                        const contentValue = typeof result.contents === 'string'
                            ? result.contents
                            : (result.contents.value || '');
                        const md = new vscode.MarkdownString(contentValue);
                        let range = undefined;
                        if (result.range) {{
                            range = new vscode.Range(
                                result.range.start.line,
                                result.range.start.character,
                                result.range.end.line,
                                result.range.end.character
                            );
                        }}
                        return new vscode.Hover(md, range);
                    }} catch (e) {{
                        return null;
                    }}
                }}
            }}
        )
    );

    context.subscriptions.push(
        vscode.languages.registerInlayHintsProvider(
            {{ language: LANGUAGE_ID }},
            {{
                async provideInlayHints(document, range) {{
                    try {{
                        const result = await sendRequest('textDocument/inlayHint', {{
                            textDocument: {{ uri: document.uri.toString() }},
                            range: {{
                                start: {{ line: range.start.line, character: range.start.character }},
                                end: {{ line: range.end.line, character: range.end.character }}
                            }}
                        }});
                        if (!Array.isArray(result)) return [];
                        return result.map(hint => {{
                            const pos = new vscode.Position(hint.position.line, hint.position.character);
                            const label = typeof hint.label === 'string' ? hint.label : (hint.label.value || '');
                            const inlay = new vscode.InlayHint(pos, label, hint.kind || 1);
                            if (hint.paddingLeft) inlay.paddingLeft = true;
                            if (hint.paddingRight) inlay.paddingRight = true;
                            return inlay;
                        }});
                    }} catch (e) {{
                        return [];
                    }}
                }}
            }}
        )
    );
}}

function deactivate() {{
    if (serverProcess) {{
        sendNotification('exit', {{}});
        serverProcess.kill();
        serverProcess = null;
    }}
}}

module.exports = {{
    activate,
    deactivate
}};
'''

    def export(self, output_dir: Path | str) -> dict[str, Path]:
        """
        Generate and persist all VS Code extension artifacts to output_dir.

        Returns:
            dict[str, Path]: Mapping of artifact keys to output Path locations.
        """
        base_path = Path(output_dir).resolve()
        syntaxes_dir = base_path / "syntaxes"
        snippets_dir = base_path / "snippets"

        syntaxes_dir.mkdir(parents=True, exist_ok=True)
        snippets_dir.mkdir(parents=True, exist_ok=True)

        manifest_file = base_path / "package.json"
        config_file = base_path / "language-configuration.json"
        grammar_file = syntaxes_dir / f"{self.language_id}.tmLanguage.json"
        snippets_file = snippets_dir / "snippets.json"
        client_file = base_path / "extension.js"

        manifest_data = self.build_manifest()
        config_data = self.build_language_configuration()
        grammar_data = self.build_tm_grammar()
        snippets_data = self.build_snippets()
        client_code = self.build_client_script()

        manifest_file.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")
        config_file.write_text(json.dumps(config_data, indent=2), encoding="utf-8")
        grammar_file.write_text(json.dumps(grammar_data, indent=2), encoding="utf-8")
        snippets_file.write_text(json.dumps(snippets_data, indent=2), encoding="utf-8")
        client_file.write_text(client_code, encoding="utf-8")

        return {
            "manifest": manifest_file,
            "config": config_file,
            "grammar": grammar_file,
            "snippets": snippets_file,
            "client": client_file,
        }


__all__ = ["VSIXGenerator"]
