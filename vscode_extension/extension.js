const vscode = require('vscode');
const { spawn } = require('child_process');
const path = require('path');

const LANGUAGE_ID = "gram";
const DEFAULT_ENTRYPOINT = "prueba:PROGRAM";

let serverProcess = null;
let diagnosticCollection = null;
let outputChannel = null;
let messageId = 0;
const pendingRequests = new Map();
let incomingBuffer = Buffer.alloc(0);

function log(msg) {
    if (outputChannel) {
        outputChannel.appendLine(msg);
    }
}

function send(msg) {
    if (!serverProcess || !serverProcess.stdin || !serverProcess.stdin.writable) {
        return;
    }
    const body = Buffer.from(JSON.stringify(msg), 'utf8');
    const header = Buffer.from('Content-Length: ' + body.length + '\r\n\r\n', 'ascii');
    serverProcess.stdin.write(Buffer.concat([header, body]));
}

function sendRequest(method, params) {
    return new Promise((resolve, reject) => {
        const id = ++messageId;
        pendingRequests.set(id, { resolve, reject });
        send({ jsonrpc: '2.0', id, method, params });
    });
}

function sendNotification(method, params) {
    send({ jsonrpc: '2.0', method, params });
}

function handleMessage(message) {
    if (message.id !== undefined && pendingRequests.has(message.id)) {
        const entry = pendingRequests.get(message.id);
        pendingRequests.delete(message.id);
        if (message.error) {
            log('[Gram LSP Error] ' + (message.error.message || JSON.stringify(message.error)));
            entry.reject(message.error);
        } else {
            entry.resolve(message.result);
        }
        return;
    }

    if (message.method === 'textDocument/publishDiagnostics') {
        const params = message.params || {};
        const uri = vscode.Uri.parse(params.uri);
        const rawDiagnostics = params.diagnostics || [];
        log('[Gram LSP] Published ' + rawDiagnostics.length + ' diagnostic(s) for ' + params.uri);
        const diagnostics = rawDiagnostics.map(d => {
            const start = new vscode.Position(d.range.start.line, d.range.start.character);
            const end = new vscode.Position(d.range.end.line, d.range.end.character);
            const range = new vscode.Range(start, end);
            let severity = vscode.DiagnosticSeverity.Error;
            if (d.severity === 2) severity = vscode.DiagnosticSeverity.Warning;
            else if (d.severity === 3) severity = vscode.DiagnosticSeverity.Information;
            else if (d.severity === 4) severity = vscode.DiagnosticSeverity.Hint;
            return new vscode.Diagnostic(range, d.message, severity);
        });
        if (diagnosticCollection) {
            diagnosticCollection.set(uri, diagnostics);
        }
    }
}

function handleData(chunk) {
    incomingBuffer = Buffer.concat([incomingBuffer, chunk]);
    while (true) {
        const headerEnd = incomingBuffer.indexOf('\r\n\r\n');
        if (headerEnd === -1) {
            break;
        }
        const headerStr = incomingBuffer.slice(0, headerEnd).toString('ascii');
        const match = headerStr.match(/content-length:\s*(\d+)/i);
        if (!match) {
            incomingBuffer = incomingBuffer.slice(headerEnd + 4);
            continue;
        }
        const contentLength = parseInt(match[1], 10);
        const bodyStart = headerEnd + 4;
        const bodyEnd = bodyStart + contentLength;
        if (incomingBuffer.length < bodyEnd) {
            break;
        }
        const bodyBuffer = incomingBuffer.slice(bodyStart, bodyEnd);
        incomingBuffer = incomingBuffer.slice(bodyEnd);
        try {
            const message = JSON.parse(bodyBuffer.toString('utf8'));
            handleMessage(message);
        } catch (err) {
            log('[Gram LSP Frame Error] Failed to parse message: ' + err);
        }
    }
}

function startServerProcess(context) {
    const config = vscode.workspace.getConfiguration(LANGUAGE_ID);
    const pythonCmd = config.get('pythonPath') || 'python';
    const entrypoint = config.get('entrypoint') || DEFAULT_ENTRYPOINT;
    const wsFolders = vscode.workspace.workspaceFolders;
    const wsPath = wsFolders && wsFolders.length > 0 ? wsFolders[0].uri.fsPath : null;

    const env = Object.assign({}, process.env);
    if (wsPath) {
        env.PYTHONPATH = env.PYTHONPATH ? (wsPath + path.delimiter + env.PYTHONPATH) : wsPath;
    }

    const args = ['-u', '-m', 'gram.vsix.lsp.server'];
    if (entrypoint) {
        args.push('--entrypoint', entrypoint);
    }
    if (wsPath) {
        args.push('--workspace', wsPath);
    }

    log('[Gram LSP] Spawning: ' + pythonCmd + ' ' + args.join(' '));
    log('[Gram LSP] Workspace directory: ' + (wsPath || process.cwd()));

    try {
        serverProcess = spawn(pythonCmd, args, {
            cwd: wsPath || undefined,
            env: env,
            stdio: ['pipe', 'pipe', 'pipe']
        });
    } catch (e) {
        log('[Gram LSP Launch Error]: ' + e);
        return;
    }

    if (serverProcess.stdout) {
        serverProcess.stdout.on('data', handleData);
    }
    if (serverProcess.stderr) {
        serverProcess.stderr.on('data', data => {
            log('[Gram LSP Server Stderr]: ' + data.toString().trim());
        });
    }
    serverProcess.on('error', err => {
        log('[Gram LSP Process Error]: ' + err);
    });
    serverProcess.on('close', code => {
        log('[Gram LSP Process Closed]: code ' + code);
    });

    sendRequest('initialize', {
        processId: process.pid,
        rootUri: wsPath ? vscode.Uri.file(wsPath).toString() : null,
        initializationOptions: {
            entrypoint: entrypoint
        },
        capabilities: {}
    }).then(() => {
        log('[Gram LSP] Initialized successfully.');
        sendNotification('initialized', {});
        vscode.workspace.textDocuments.forEach(doc => {
            if (doc.languageId === LANGUAGE_ID) {
                sendNotification('textDocument/didOpen', {
                    textDocument: {
                        uri: doc.uri.toString(),
                        languageId: doc.languageId,
                        version: doc.version,
                        text: doc.getText()
                    }
                });
            }
        });
    }).catch(err => {
        log('[Gram LSP Initialize Failed]: ' + (err.message || JSON.stringify(err)));
    });
}

function activate(context) {
    outputChannel = vscode.window.createOutputChannel("Gram Language Server");
    context.subscriptions.push(outputChannel);
    log('[Gram LSP] Activating extension for language ' + LANGUAGE_ID);

    diagnosticCollection = vscode.languages.createDiagnosticCollection(LANGUAGE_ID);
    context.subscriptions.push(diagnosticCollection);

    startServerProcess(context);

    context.subscriptions.push(
        vscode.commands.registerCommand(LANGUAGE_ID + '.restartServer', () => {
            log('[Gram LSP] Restarting Language Server...');
            deactivate();
            startServerProcess(context);
        })
    );

    context.subscriptions.push(
        vscode.workspace.onDidOpenTextDocument(doc => {
            if (doc.languageId !== LANGUAGE_ID) return;
            sendNotification('textDocument/didOpen', {
                textDocument: {
                    uri: doc.uri.toString(),
                    languageId: doc.languageId,
                    version: doc.version,
                    text: doc.getText()
                }
            });
        }),
        vscode.workspace.onDidChangeTextDocument(event => {
            if (event.document.languageId !== LANGUAGE_ID) return;
            sendNotification('textDocument/didChange', {
                textDocument: {
                    uri: event.document.uri.toString(),
                    version: event.document.version
                },
                contentChanges: [
                    { text: event.document.getText() }
                ]
            });
        }),
        vscode.workspace.onDidCloseTextDocument(doc => {
            if (doc.languageId !== LANGUAGE_ID) return;
            if (diagnosticCollection) {
                diagnosticCollection.delete(doc.uri);
            }
            sendNotification('textDocument/didClose', {
                textDocument: { uri: doc.uri.toString() }
            });
        })
    );

    context.subscriptions.push(
        vscode.languages.registerCompletionItemProvider(
            { language: LANGUAGE_ID },
            {
                async provideCompletionItems(document, position) {
                    try {
                        const lineText = document.lineAt(position.line).text;
                        const result = await sendRequest('textDocument/completion', {
                            textDocument: { uri: document.uri.toString() },
                            position: { line: position.line, character: position.character },
                            currentLine: lineText
                        });
                        if (!Array.isArray(result)) return [];
                        return result.map(item => {
                            const completion = new vscode.CompletionItem(item.label);
                            if (item.kind !== undefined) completion.kind = item.kind;
                            if (item.detail) completion.detail = item.detail;
                            if (item.documentation) {
                                if (typeof item.documentation === 'string') {
                                    completion.documentation = new vscode.MarkdownString(item.documentation);
                                } else if (item.documentation && item.documentation.value) {
                                    completion.documentation = new vscode.MarkdownString(item.documentation.value);
                                }
                            }
                            if (item.insertText) completion.insertText = item.insertText;
                            if (item.sortText) completion.sortText = item.sortText;
                            if (item.filterText) completion.filterText = item.filterText;
                            if (item.range) {
                                completion.range = new vscode.Range(
                                    item.range.start.line,
                                    item.range.start.character,
                                    item.range.end.line,
                                    item.range.end.character
                                );
                            }
                            return completion;
                        });
                    } catch (e) {
                        return [];
                    }
                }
            },
            '.', ' ', ':', '(', ')'
        )
    );

    context.subscriptions.push(
        vscode.languages.registerHoverProvider(
            { language: LANGUAGE_ID },
            {
                async provideHover(document, position) {
                    try {
                        const result = await sendRequest('textDocument/hover', {
                            textDocument: { uri: document.uri.toString() },
                            position: { line: position.line, character: position.character }
                        });
                        if (!result || !result.contents) return null;
                        const contentValue = typeof result.contents === 'string'
                            ? result.contents
                            : (result.contents.value || '');
                        const md = new vscode.MarkdownString(contentValue);
                        let range = undefined;
                        if (result.range) {
                            range = new vscode.Range(
                                result.range.start.line,
                                result.range.start.character,
                                result.range.end.line,
                                result.range.end.character
                            );
                        }
                        return new vscode.Hover(md, range);
                    } catch (e) {
                        return null;
                    }
                }
            }
        )
    );

    context.subscriptions.push(
        vscode.languages.registerInlayHintsProvider(
            { language: LANGUAGE_ID },
            {
                async provideInlayHints(document, range) {
                    try {
                        const result = await sendRequest('textDocument/inlayHint', {
                            textDocument: { uri: document.uri.toString() },
                            range: {
                                start: { line: range.start.line, character: range.start.character },
                                end: { line: range.end.line, character: range.end.character }
                            }
                        });
                        if (!Array.isArray(result)) return [];
                        return result.map(hint => {
                            const pos = new vscode.Position(hint.position.line, hint.position.character);
                            const label = typeof hint.label === 'string' ? hint.label : (hint.label.value || '');
                            const inlay = new vscode.InlayHint(pos, label, hint.kind || 1);
                            if (hint.paddingLeft) inlay.paddingLeft = true;
                            if (hint.paddingRight) inlay.paddingRight = true;
                            return inlay;
                        });
                    } catch (e) {
                        return [];
                    }
                }
            }
        )
    );
}

function deactivate() {
    if (serverProcess) {
        sendNotification('exit', {});
        serverProcess.kill();
        serverProcess = null;
    }
}

module.exports = {
    activate,
    deactivate
};
