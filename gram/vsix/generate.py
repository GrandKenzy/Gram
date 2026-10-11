"""
Módulo Generador de Sintaxis TextMate, Temas, LSP y Extensiones VSIX (`gram.vsix.generate`).
=============================================================================================
Genera todos los artefactos requeridos por Visual Studio Code:
  1. Gramáticas TextMate (`.tmLanguage.json`).
  2. Temas cromáticos (`.json`) con resolución de colores nativos y de plugins.
  3. Configuración de lenguaje (`language-configuration.json`).
  4. Fragmentos de código y autocompletado (`snippets/snippets.json`).
  5. Cliente LSP en JavaScript (`client/extension.js`) para activar diagnósticos y completions.
  6. Configuración de compilador y comandos de compilación/ejecución (`package.json`).
  7. Icono oficial de extensión (`icon.png`).
  8. Empaquetado OPC compatible con el estándar VSIX (`.vsix`).
"""
from __future__ import annotations

import base64
import json
import os
import re
import shutil
import zipfile
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape, quoteattr

from gram import config
from gram.vsix.extract import SyntaxMetadata, extract_metadata
from gram.vsix.configuration import LanguageConfiguration

# Identificador fijo universal de Gram VSIX
GRAM_PUBLISHER = "gram"
GRAM_EXTENSION_NAME = "gram-language-support"
GRAM_FULL_ID = f"{GRAM_PUBLISHER}.{GRAM_EXTENSION_NAME}"


def _token_regex(token_name: str, metadata: SyntaxMetadata) -> str | None:
    from gram.core.lexer.tokens import MAP_SYMBOLS, Token

    fixed_patterns = {
        "IDENT": r"[A-Za-z_][A-Za-z0-9_]*",
        "KEYWORD": _alternation(metadata.keywords),
        "STRING": r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'',
        "CHAR": r"'(?:\\.|[^'\\])'",
        "NUMBER": r"(?:0[xX][0-9A-Fa-f]+|[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?)",
        "BOOL": r"(?:true|false|True|False)",
        "NULL": r"(?:null|Null|None|none)",
    }
    if token_name in fixed_patterns:
        return fixed_patterns[token_name]

    try:
        token = Token[token_name]
    except KeyError:
        return None
    symbols = [symbol for symbol, symbol_token in MAP_SYMBOLS.items() if symbol_token == token]
    if symbols:
        return _alternation(symbols)
    return None


def _alternation(values: Any) -> str:
    choices = sorted({str(value) for value in values if str(value)}, key=len, reverse=True)
    if not choices:
        return r"(?!)"
    return "(?:" + "|".join(re.escape(value) for value in choices) + ")"


def _non_capturing_groups(pattern: str) -> str:
    """Keep user regex grouping from shifting TextMate capture numbers."""
    result: list[str] = []
    escaped = False
    in_character_class = False
    for index, char in enumerate(pattern):
        if escaped:
            result.append(char)
            escaped = False
        elif char == "\\":
            result.append(char)
            escaped = True
        elif char == "[" and not in_character_class:
            in_character_class = True
            result.append(char)
        elif char == "]" and in_character_class:
            in_character_class = False
            result.append(char)
        elif char == "(" and not in_character_class and pattern[index + 1:index + 2] != "?":
            result.append("(?:")
        else:
            result.append(char)
    return "".join(result)


def _comment_scope(language_id: str, token: str | None = None) -> str:
    token = token if token is not None else config.LEXER_COMMENT_TOKEN
    token_scope = {"#": "number-sign", ";": "semicolon"}.get(token, "punctuation")
    return f"comment.line.{token_scope}.{language_id}"


def _terminal_scope(combinator: Any, language_id: str) -> str:
    from gram.core.combinators import MatchGroup, MatchKeyword, MatchSeqSymbol, MatchToken

    if isinstance(combinator, MatchKeyword):
        name = re.sub(r"[^a-zA-Z0-9_]", "_", combinator.keyword).lower()
        return f"keyword.other.{name}.{language_id}"
    if isinstance(combinator, MatchGroup):
        name = re.sub(r"[^a-zA-Z0-9_]", "_", combinator.group).lower()
        return f"keyword.other.{name}.{language_id}"
    if isinstance(combinator, MatchToken):
        token_scopes = {
            "STRING": "string.quoted",
            "CHAR": "string.quoted.single",
            "NUMBER": "constant.numeric",
            "INT": "constant.numeric",
            "FLOAT": "constant.numeric",
            "BOOL": "constant.language",
            "NULL": "constant.language",
            "IDENT": "variable.other",
        }
        return f"{token_scopes.get(combinator.token_name, 'source')}.{language_id}"
    if isinstance(combinator, MatchSeqSymbol):
        return f"keyword.operator.{language_id}"
    return f"source.{language_id}"


def _rule_regex(
    combinator: Any,
    metadata: SyntaxMetadata,
    colors: dict[int, str],
    rule_name: str,
    language_id: str,
    captures: dict[str, dict[str, str]],
    state: dict[str, int],
) -> str | None:
    from gram.core.combinators import Alt, Many, MatchGroup, MatchKeyword, MatchSeqSymbol, MatchToken, Opt, Seq, Some

    if isinstance(combinator, Seq):
        parts: list[str] = []
        for child in combinator.combinators:
            part = _rule_regex(child, metadata, colors, rule_name, language_id, captures, state)
            if part is None:
                return None
            parts.append(part)
        return r"[ \t]*".join(parts)

    if isinstance(combinator, Alt):
        start_index = state["token_index"]
        end_index = start_index
        parts: list[str] = []
        for child in combinator.combinators:
            branch_state = {
                "token_index": start_index,
                "capture_index": state["capture_index"],
            }
            part = _rule_regex(
                child, metadata, colors, rule_name, language_id, captures, branch_state
            )
            if part is None:
                return None
            parts.append(part)
            end_index = max(end_index, branch_state["token_index"])
            state["capture_index"] = branch_state["capture_index"]
        state["token_index"] = end_index
        return "(?:" + "|".join(parts) + ")"

    if isinstance(combinator, (Opt, Many, Some)):
        child = _rule_regex(
            combinator.combinator,
            metadata,
            colors,
            rule_name,
            language_id,
            captures,
            state,
        )
        if child is None:
            return None
        quantifier = "?" if isinstance(combinator, Opt) else ("+" if isinstance(combinator, Some) else "*")
        return f"(?:{child}){quantifier}"

    regex: str | None = None
    if isinstance(combinator, MatchKeyword):
        regex = rf"(?<![\w]){re.escape(combinator.keyword)}(?![\w])"
    elif isinstance(combinator, MatchGroup):
        group = metadata.word_groups.get(combinator.group, [])
        if combinator.only is not None:
            group = [word for word in group if word in combinator.only]
        group = [word for word in group if word not in combinator.exclude]
        regex = rf"(?<![\w]){_alternation(group)}(?![\w])"
    elif isinstance(combinator, MatchToken):
        regex = _token_regex(combinator.token_name, metadata)
        if combinator.token_name in {"IDENT", "KEYWORD", "BOOL", "NULL"} and regex:
            regex = rf"(?<![\w]){regex}(?![\w])"
    elif isinstance(combinator, MatchSeqSymbol):
        raw = combinator.pattern if combinator.is_pattern else re.escape(combinator.pattern)
        raw = _non_capturing_groups(raw)
        regex = f"(?:{raw})" if combinator.case_sensitive else f"(?i:{raw})"

    if regex is None:
        return None

    token_index = state["token_index"]
    state["token_index"] += 1
    capture_index = state["capture_index"]
    state["capture_index"] += 1
    captures[str(capture_index)] = {
        "name": (
            (
                f"entity.name.rule.{language_id}."
                f"{re.sub(r'[^a-zA-Z0-9_]', '_', rule_name).lower()}.token.{token_index}"
            )
            if token_index in colors
            else _terminal_scope(combinator, language_id)
        )
    }
    return f"({regex})"


def _rule_scope(rule_scope: str, rule_name: str, language_id: str) -> str:
    default_scope = f"entity.name.rule.gram.{re.sub(r'[^a-zA-Z0-9_]', '_', rule_name).lower()}"
    if not rule_scope or rule_scope == default_scope:
        return f"entity.name.rule.{language_id}.{re.sub(r'[^a-zA-Z0-9_]', '_', rule_name).lower()}"
    if rule_scope.startswith("entity.name.rule.gram."):
        return rule_scope.replace("entity.name.rule.gram.", f"entity.name.rule.{language_id}.", 1)
    return rule_scope


def generate_textmate_grammar(
    metadata: SyntaxMetadata,
    scope_name: str = "source.gram",
    language_id: str = "gram",
    grammar_name: str = "Gram",
    line_comment_token: str | None = None,
    additional_patterns: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a TextMate grammar from language metadata and RuleItem combinators."""
    patterns: list[dict[str, Any]] = []

    # 1. Comentarios de línea (# ... y ; ...)
    comment_token = line_comment_token if line_comment_token is not None else config.LEXER_COMMENT_TOKEN
    patterns.append({
        "name": _comment_scope(language_id, comment_token),
        "match": rf"{re.escape(comment_token)}.*$",
    })

    # 2. Cadenas de texto multilínea (docstrings triples comillas)
    patterns.append({
        "name": f"string.quoted.triple.double.{language_id}",
        "begin": r'"""',
        "end": r'"""',
        "patterns": [
            {"name": f"constant.character.escape.{language_id}", "match": r"\\."}
        ],
    })
    patterns.append({
        "name": f"string.quoted.triple.single.{language_id}",
        "begin": r"'''",
        "end": r"'''",
        "patterns": [
            {"name": f"constant.character.escape.{language_id}", "match": r"\\."}
        ],
    })

    # 3. Cadenas de texto simples y dobles
    patterns.append({
        "name": f"string.quoted.double.{language_id}",
        "begin": r'"',
        "end": r'"',
        "patterns": [
            {"name": f"constant.character.escape.{language_id}", "match": r'\\.'}
        ],
    })
    patterns.append({
        "name": f"string.quoted.single.{language_id}",
        "begin": r"'",
        "end": r"'",
        "patterns": [
            {"name": f"constant.character.escape.{language_id}", "match": r"\\."}
        ],
    })

    # 4. Números (Hexadecimales, Flotantes y Enteros)
    patterns.append({
        "name": f"constant.numeric.hex.{language_id}",
        "match": r"\b0[xX][0-9a-fA-F]+\b",
    })
    patterns.append({
        "name": f"constant.numeric.float.{language_id}",
        "match": r"\b[0-9]+\.[0-9]+([eE][+-]?[0-9]+)?\b",
    })
    patterns.append({
        "name": f"constant.numeric.integer.{language_id}",
        "match": r"\b[0-9]+\b",
    })

    # 5. Constantes booleanas y nulas
    patterns.append({
        "name": f"constant.language.{language_id}",
        "match": r"\b(True|False|None|true|false|null)\b",
    })
    patterns.extend(additional_patterns or [])

    for rule_name, rule in metadata.rules.items():
        if not rule.grammar or not rule.colors:
            continue
        rule_scope = _rule_scope(rule.scope, rule_name, language_id)
        captures: dict[str, dict[str, str]] = {}
        expression = _rule_regex(
            rule.grammar,
            metadata,
            rule.colors,
            rule_name,
            language_id,
            captures,
            {"token_index": 0, "capture_index": 1},
        )
        if expression and captures:
            pattern = {
                "match": expression,
                "captures": captures,
            }
            if rule.color and rule.color.upper() != "#FFFFFF":
                pattern["name"] = rule_scope
            patterns.append(pattern)

    # 6. Palabras clave (Keywords) registradas
    if metadata.keywords:
        for kw_name, kw_meta in metadata.keywords.items():
            clean_kw = re.escape(kw_name)
            patterns.append({
                "name": f"keyword.other.{kw_name.lower()}.{language_id}",
                "match": rf"\b{clean_kw}\b",
            })
    else:
        patterns.append({
            "name": f"keyword.control.{language_id}",
            "match": r"\b(define|include|Keyword|Seq|Alt|Many|Some|Opt|Separator|reference|tokens|words)\b",
        })

    # 7. Reglas sintácticas de Gram (RuleItem names)
    if metadata.rules:
        for r_name, r_meta in metadata.rules.items():
            rule_scope = _rule_scope(r_meta.scope, r_name, language_id)
            patterns.append({
                "name": rule_scope,
                "match": rf"\b{re.escape(r_name)}\b",
            })
        sorted_rule_names = sorted(metadata.rules.keys(), key=len, reverse=True)
        rule_pattern = r"\b(" + "|".join(re.escape(r) for r in sorted_rule_names) + r")\b"
        patterns.append({
            "name": f"entity.name.type.rule.{language_id}",
            "match": rule_pattern,
        })

    # 8. Operadores y Símbolos
    patterns.append({
        "name": f"keyword.operator.{language_id}",
        "match": r"(\+\+|--|\*\*|//|\+=|-=|\*=|/=|%=|\*\*=|//=|\band\b|\bor\b|\bnot\b|==|!=|<=|>=|<|>|=|:=|\+|-|\*|/|%|\||\^|&|~)",
    })
    patterns.append({
        "name": f"punctuation.separator.{language_id}",
        "match": r"([\{\}\(\)\[\],:;\.])",
    })

    return {
        "$schema": "https://raw.githubusercontent.com/martinring/tmlanguage/master/tmlanguage.json",
        "name": grammar_name,
        "scopeName": scope_name,
        "patterns": patterns,
    }


def generate_theme(
    metadata: SyntaxMetadata,
    theme_name: str = "Gram Theme",
    language_id: str = "gram",
    line_comment_token: str | None = None,
    editor_colors: dict[str, str] | None = None,
    additional_token_colors: list[dict[str, Any]] | None = None,
    include_default_token_colors: bool = True,
    token_label_prefix: str = "Gram",
) -> dict[str, Any]:
    """Genera un tema de color VS Code completo correlacionando definiciones de color con scopes."""
    token_colors: list[dict[str, Any]] = [
        {
            "name": f"{token_label_prefix} Comments",
            "scope": [_comment_scope(language_id, line_comment_token)],
            "settings": {"foreground": "#6A9955", "fontStyle": "italic"},
        },
        {
            "name": f"{token_label_prefix} Strings",
            "scope": [
                f"string.quoted.double.{language_id}",
                f"string.quoted.single.{language_id}",
                f"string.quoted.triple.double.{language_id}",
                f"string.quoted.triple.single.{language_id}",
            ],
            "settings": {"foreground": "#CE9178"},
        },
        {
            "name": f"{token_label_prefix} Numbers",
            "scope": [
                f"constant.numeric.hex.{language_id}",
                f"constant.numeric.float.{language_id}",
                f"constant.numeric.integer.{language_id}",
            ],
            "settings": {"foreground": "#B5CEA8"},
        },
        {
            "name": f"{token_label_prefix} Constants",
            "scope": [f"constant.language.{language_id}"],
            "settings": {"foreground": "#569CD6"},
        },
        {
            "name": f"{token_label_prefix} Operators",
            "scope": [f"keyword.operator.{language_id}"],
            "settings": {"foreground": "#D4D4D4"},
        },
        {
            "name": f"{token_label_prefix} Punctuation",
            "scope": [f"punctuation.separator.{language_id}"],
            "settings": {"foreground": "#D4D4D4"},
        },
        {
            "name": f"{token_label_prefix} Rules",
            "scope": [f"entity.name.type.rule.{language_id}"],
            "settings": {"foreground": "#4EC9B0", "fontStyle": "bold"},
        },
    ] if include_default_token_colors else []

    # 1. Colores declarados por plugins (PluginColors)
    for cat_name, c_def in metadata.colors.items():
        token_colors.append({
            "name": f"{token_label_prefix} Category: {cat_name}",
            "scope": [
                f"source.{language_id}.{cat_name.lower()}",
                f"keyword.other.{cat_name.lower()}.{language_id}",
                f"entity.name.{cat_name.lower()}.{language_id}",
            ],
            "settings": {
                "foreground": c_def.hex,
            },
        })

    for group_name, words in metadata.word_groups.items():
        group_colors = {
            metadata.keywords[word].hex_color
            for word in words
            if word in metadata.keywords
            and metadata.keywords[word].hex_color
            and metadata.keywords[word].hex_color.upper() != "#FFFFFF"
        }
        if len(group_colors) == 1:
            token_colors.append({
                "name": f"{token_label_prefix} Keyword Group: {group_name}",
                "scope": [
                    "keyword.other."
                    f"{re.sub(r'[^a-zA-Z0-9_]', '_', group_name).lower()}."
                    f"{language_id}"
                ],
                "settings": {"foreground": next(iter(group_colors))},
            })

    # 2. Palabras clave con color hexadecimal explícito
    for kw_name, kw_meta in metadata.keywords.items():
        if kw_meta.hex_color and kw_meta.hex_color.upper() != "#FFFFFF":
            token_colors.append({
                "name": f"{token_label_prefix} Keyword: {kw_name}",
                "scope": [f"keyword.other.{kw_name.lower()}.{language_id}"],
                "settings": {
                    "foreground": kw_meta.hex_color,
                },
            })

    # 3. Reglas sintácticas con color individual
    for r_name, r_meta in metadata.rules.items():
        rule_scope = _rule_scope(r_meta.scope, r_name, language_id)
        if r_meta.color and r_meta.color.upper() != "#FFFFFF":
            token_colors.append({
                "name": f"{token_label_prefix} Rule: {r_name}",
                "scope": [rule_scope],
                "settings": {
                    "foreground": r_meta.color,
                    "fontStyle": "bold" if r_meta.is_structural else "normal",
                },
            })
        for token_index, color in r_meta.colors.items():
            token_colors.append({
                "name": f"{token_label_prefix} Rule Token: {r_name}[{token_index}]",
                "scope": [
                    f"entity.name.rule.{language_id}."
                    f"{re.sub(r'[^a-zA-Z0-9_]', '_', r_name).lower()}.token.{token_index}"
                ],
                "settings": {"foreground": color},
            })

    return {
        "name": theme_name,
        "type": "dark",
        "colors": {
            "editor.background": "#1E1E1E",
            "editor.foreground": "#D4D4D4",
            **(editor_colors or {}),
        },
        "tokenColors": token_colors + (additional_token_colors or []),
    }


def generate_language_configuration(
    metadata: SyntaxMetadata | None = None,
    configuration: LanguageConfiguration | None = None,
) -> dict[str, Any]:
    """Generate configuration with token-derived defaults and explicit overrides."""
    return (configuration or LanguageConfiguration()).build(metadata)


def generate_snippets(
    metadata: SyntaxMetadata,
    include_defaults: bool = True,
    include_rule_snippets: bool = True,
) -> dict[str, Any]:
    """Genera fragmentos de código para autocompletado y plantillas en VS Code."""
    snippets: dict[str, Any] = {
        "Define Rule": {
            "prefix": "defrule",
            "body": [
                "define ${1:MY_RULE} ${2:1000}",
                "${1:MY_RULE} ${3|Seq,Alt,Many,Some|}:",
                "    ${0:tokens.IDENT}",
            ],
            "description": "Declara una nueva regla sintáctica en GLang.",
        },
        "Program Entrypoint": {
            "prefix": "entry",
            "body": [
                "[0]:",
                "    reference ${1:MY_RULE}",
            ],
            "description": "Define el punto de entrada principal del programa.",
        },
        "Keyword Block": {
            "prefix": "keyword",
            "body": [
                'Keyword "${1:my_keyword}":',
                '    color: ${2:#08D453}',
                '    description: "${3:Descripción}"',
                '    group: "${4:GENERAL}"',
            ],
            "description": "Declara una palabra clave personalizada con color y descripción.",
        },
        "Separator Sequence": {
            "prefix": "sep",
            "body": [
                'Separator sep "${1:,}":',
                "    ${0:tokens.IDENT}",
            ],
            "description": "Crea una secuencia delimitada por separador.",
        },
    } if include_defaults else {}

    snippets.update({name: dict(value) for name, value in metadata.snippets.items()})

    # Agregar snippets para reglas de usuario
    for r_name, r_meta in metadata.rules.items():
        if include_rule_snippets and r_meta.code >= 100:
            snippets[f"Rule: {r_name}"] = {
                "prefix": r_name.lower(),
                "body": [r_name],
                "description": r_meta.description or f"Regla sintáctica {r_name}",
            }
        if (
            r_meta.suggestions_autocomplete
            and r_meta.suggestions
            and isinstance(r_meta.suggestions, dict)
        ):
            for sug_key, sug_val in r_meta.suggestions.items():
                if isinstance(sug_val, dict) and "body" in sug_val:
                    prefix = sug_val.get("prefix", sug_key)
                    body = sug_val["body"]
                    desc = sug_val.get("description", f"Snippet {sug_key}")
                    snippets[sug_key] = {
                        "prefix": prefix,
                        "body": body if isinstance(body, list) else [body],
                        "description": desc,
                    }

    return snippets


def generate_lsp_client_js() -> str:
    """Genera el código JavaScript cliente de VS Code para el Language Server Protocol."""
    return """\
// Cliente Language Server Protocol para Gram Framework
const vscode = require('vscode');
const { LanguageClient, TransportKind } = require('vscode-languageclient/node');
const path = require('path');
const cp = require('child_process');

let client;

function activate(context) {
    const config = vscode.workspace.getConfiguration('gram');
    const isLspEnabled = config.get('lsp.enabled', true);

    if (isLspEnabled) {
        // Ejecutar el Language Server nativo en Python vía stdio
        const pythonPath = config.get('lsp.serverPath') || 'python';
        const serverOptions = {
            command: pythonPath,
            args: ['-m', 'gram.vsix.lsp'],
            transport: TransportKind.stdio,
        };

        const clientOptions = {
            documentSelector: [
                { scheme: 'file', language: 'gram' },
                { scheme: 'file', language: 'glang' },
            ],
            synchronize: {
                fileEvents: vscode.workspace.createFileSystemWatcher('**/*.{gram,glang,g}'),
            },
        };

        client = new LanguageClient(
            'gramLanguageServer',
            'Gram Language Server',
            serverOptions,
            clientOptions
        );

        client.start();
    }

    // Registrar comando: Compilar Archivo
    const compileCmd = vscode.commands.registerCommand('gram.compile', () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor) {
            vscode.window.showWarningMessage('No hay ningún archivo abierto para compilar.');
            return;
        }

        const filePath = editor.document.fileName;
        const customCompiler = config.get('compiler.path');
        const customArgs = config.get('compiler.args') || [];

        let cmd = customCompiler ? customCompiler : 'python -m gram.cli glang';
        let fullCmd = `${cmd} "${filePath}" ${customArgs.join(' ')}`;

        const terminal = vscode.window.createTerminal('Gram Compiler');
        terminal.show();
        terminal.sendText(fullCmd);
    });

    // Registrar comando: Ejecutar Archivo
    const runCmd = vscode.commands.registerCommand('gram.run', () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor) {
            vscode.window.showWarningMessage('No hay ningún archivo abierto para ejecutar.');
            return;
        }

        const filePath = editor.document.fileName;
        const terminal = vscode.window.createTerminal('Gram Runner');
        terminal.show();
        terminal.sendText(`python -m gram.cli run "${filePath}" -a`);
    });

    context.subscriptions.push(compileCmd, runCmd);
}

function deactivate() {
    if (!client) {
        return undefined;
    }
    return client.stop();
}

module.exports = {
    activate,
    deactivate,
};
"""


def generate_hover_client_js(metadata: SyntaxMetadata, language_id: str) -> str:
    """Generate a standalone VS Code hover provider from syntax metadata."""
    docs = {
        keyword.name: keyword.description or f"Palabra clave reservada `{keyword.name}`."
        for keyword in metadata.keywords.values()
    }
    docs.update({
        rule.name: rule.description or rule.docs
        for rule in metadata.rules.values()
        if rule.description or rule.docs
    })
    serialized_docs = json.dumps(docs, ensure_ascii=False)
    serialized_language_id = json.dumps(language_id, ensure_ascii=True)
    return f"""\
const vscode = require('vscode');
const documentation = {serialized_docs};
const languageId = {serialized_language_id};

function activate(context) {{
    const selector = {{ language: languageId, scheme: 'file' }};
    const provider = vscode.languages.registerHoverProvider(selector, {{
        provideHover(document, position) {{
            const range = document.getWordRangeAtPosition(
                position,
                /[A-Za-z_][A-Za-z0-9_]*/
            );
            if (!range) {{
                return undefined;
            }}

            const word = document.getText(range);
            const contents = documentation[word];
            if (!contents) {{
                return undefined;
            }}

            return new vscode.Hover(new vscode.MarkdownString(contents), range);
        }},
    }});
    context.subscriptions.push(provider);
}}

function deactivate() {{}}

module.exports = {{ activate, deactivate }};
"""


def generate_icon_png(target_file: Path | str) -> Path:
    """
    Genera un icono PNG cuadrado oficial de 128x128 con el logo de Gram
    para ser utilizado por la extensión en el catálogo de extensiones.
    """
    p = Path(target_file).resolve()
    p.parent.mkdir(parents=True, exist_ok=True)

    # PNG mínimo válido de 64x64 en tono esmeralda/turquesa Gram (#08D453 / #1E1E1E)
    raw_b64 = (
        "iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHeAAAACXBIWXMAAAsTAAALEwEAmpwYAAAD"
        "JklEQVR4nO2bPWsUURSFzzubRBA1YqGlglgEUQv9B4r4AZaCWFkIiqSNWNgKChb+AfsVllZp"
        "sLOzC2IhWCiCIr6/4p2beffM3Jm7s9mZZHMPXGbuzZzn5T7O3JmZ4Thx4sSJ/4fDofx8vV5v"
        "N5vNfbfb3ff9fn8YhuNwOCyHw+HxcDhcHw6H28PhcL1er6+7ruuHw+HjcDi8HA6Hz5vN5nAc"
        "jhMnTpw4ceLE/4X7/f6z67o33W73ptvtXu12u1e73e6bL1++vOp2u9ftdvu+2+0+7Pf7d5vN"
        "5nE4HG673e5127avhmH42rbtz2EY3vV9/6Xruh8/fvz4ZhiGF4eD/j/g0263+9Lv9x92u937"
        "Xq/3tNvtvvV9//3bt2+v+/3+w263e7/f7z/0+/3X/X7/uuu6D91u96Vpmtdu/pumeeZk4M2b"
        "N6+Hw+F9v99/HQ6HX3d3d++6rnveNM1b13UvhmF40ff91757u7m5+TidTv8JbLfbF4eDfjqZ"
        "TL7tdrtvfd9//fHjx9ehb3Z3dz9Pp9O3/X7/ft/3z3u93pduvruu+9br9b7tdrtXu93uZbfb"
        "ve31er/6/f7zfr9/v9/vvzRN83I4HF4PB/3v0XXdy36//9x13Yuu6170+/1bN9/7/f7Nbreb"
        "bTabb51O58twODw1TfPa80y/33/V6XR+DAf9H8HpdPq5m99ut/uqW6/X+9Tr9T7vdrsv/X7/"
        "o9vt/thut28833S73U+dTuezn4N93/vA4/F4v9/vx8Ph8GA4HP7a7Xbve73e56ZpXvrA/X7/"
        "odfrfW2a5kPfd+/6/f6Hb/k/kRMnTpw4ceLE/4PD4fC53+8/bbfbF6PRaNxsNm8PB/1/wWaz"
        "eT4ej78Oh8Pvx48fvz4cDn/tdrs33W73o9vt/tzv918PB/0v8Xg8fn88Hn/Y7Xa/PB30er2v"
        "u93u03g8/nw8Hv8cDoc/hmF4cTjo/wiG4/H4u2maN7vd7qPT6fxyOOi/g+12+7vrug9t237t"
        "9Xpfuq772O12X/v9/vVw0P8RHA6Hl8Ph8PPdu3evD4fDr1+/fn09HP4G8Q2vVvOaYmMAAAAA"
        "SUVORK5CYII="
    )
    p.write_bytes(base64.b64decode(raw_b64))
    return p


def generate_package_json(
    ext_id: str = GRAM_EXTENSION_NAME,
    ext_name: str = "Gram Language Support",
    version: str = "1.0.0",
    publisher: str = GRAM_PUBLISHER,
    language_id: str = "gram",
    scope_name: str = "source.gram",
    theme_label: str = "Gram Theme",
    file_extensions: list[str] | None = None,
    compiler_path: str = "",
    compiler_args: list[str] | None = None,
    metadata: SyntaxMetadata | None = None,
    extension_description: str | None = None,
    language_aliases: list[str] | None = None,
    grammar_file: str | None = None,
    theme_file: str | None = None,
    include_lsp: bool = True,
    additional_contributions: dict[str, Any] | None = None,
    include_hover: bool = False,
) -> dict[str, Any]:
    """Build a VS Code extension manifest from language-neutral metadata."""
    if metadata is not None:
        if file_extensions is None:
            file_extensions = metadata.file_extensions
        if not compiler_path:
            compiler_path = metadata.compiler_path
        if compiler_args is None:
            compiler_args = metadata.compiler_args

    exts = file_extensions if file_extensions is not None else [".gram", ".glang", ".g"]
    args_list = compiler_args if compiler_args is not None else []
    grammar_file = grammar_file or f"{language_id}.tmLanguage.json"
    theme_file = theme_file or f"{language_id}-theme.json"
    aliases = language_aliases if language_aliases is not None else ["Gram", "gram", "glang"]
    contributes: dict[str, Any] = {
        "languages": [
            {
                "id": language_id,
                "aliases": aliases,
                "extensions": exts,
                "configuration": "./language-configuration.json",
            }
        ],
        "grammars": [
            {
                "language": language_id,
                "scopeName": scope_name,
                "path": f"./syntaxes/{grammar_file}",
            }
        ],
        "themes": [
            {
                "label": theme_label,
                "uiTheme": "vs-dark",
                "path": f"./themes/{theme_file}",
            }
        ],
        "snippets": [
            {
                "language": language_id,
                "path": "./snippets/snippets.json",
            }
        ],
    }
    if include_lsp:
        contributes.update({
            "commands": [
                {
                    "command": "gram.compile",
                    "title": "Gram: Compilar archivo actual",
                    "category": "Gram",
                },
                {
                    "command": "gram.run",
                    "title": "Gram: Ejecutar análisis sintáctico (AST)",
                    "category": "Gram",
                },
            ],
            "configuration": {
                "title": "Gram Language",
                "properties": {
                    "gram.compiler.path": {
                        "type": "string",
                        "default": compiler_path,
                        "description": "Ruta al ejecutable o comando del compilador de Gram a invocar.",
                    },
                    "gram.compiler.args": {
                        "type": "array",
                        "items": {"type": "string"},
                        "default": args_list,
                        "description": "Argumentos adicionales pasados al compilador al procesar archivos.",
                    },
                    "gram.lsp.enabled": {
                        "type": "boolean",
                        "default": True,
                        "description": "Habilita o deshabilita el Language Server Protocol (LSP) nativo de Gram.",
                    },
                    "gram.lsp.serverPath": {
                        "type": "string",
                        "default": "python",
                        "description": "Intérprete de Python utilizado para ejecutar el servidor LSP de Gram.",
                    },
                },
            },
        })

    for key, value in (additional_contributions or {}).items():
        if key in contributes and isinstance(contributes[key], list) and isinstance(value, list):
            contributes[key].extend(value)
        else:
            contributes[key] = value

    package: dict[str, Any] = {
        "name": ext_id,
        "displayName": ext_name,
        "description": extension_description or "Language support for VS Code.",
        "version": version,
        "publisher": publisher,
        "icon": "icon.png",
        "engines": {
            "vscode": "^1.70.0",
        },
        "categories": [
            "Programming Languages",
            "Themes",
            "Snippets",
            "Linters",
        ],
        "contributes": contributes,
    }
    if include_lsp:
        package["main"] = "./client/extension.js"
        package["activationEvents"] = [
            f"onLanguage:{language_id}",
            *[f"workspaceContains:**/*{ext.lstrip('.')}" for ext in exts],
            "onCommand:gram.compile",
            "onCommand:gram.run",
        ]
    elif include_hover:
        package["main"] = "./client/extension.js"
        package["activationEvents"] = [f"onLanguage:{language_id}"]
    return package


def build_extension_directory(
    output_dir: Path | str,
    metadata: SyntaxMetadata | None = None,
    ext_id: str = GRAM_EXTENSION_NAME,
    ext_name: str = "Gram Language Support",
    publisher: str = GRAM_PUBLISHER,
    version: str = "1.0.0",
    theme_name: str = "Gram Theme",
    compiler_path: str = "",
    compiler_args: list[str] | None = None,
    custom_extensions: list[str] | None = None,
    language_id: str = "gram",
    scope_name: str = "source.gram",
    grammar_name: str = "Gram",
    grammar_file: str = "gram.tmLanguage.json",
    theme_file: str = "gram-theme.json",
    language_aliases: list[str] | None = None,
    language_configuration: LanguageConfiguration | None = None,
    theme_editor_colors: dict[str, str] | None = None,
    additional_token_colors: list[dict[str, Any]] | None = None,
    include_default_theme_colors: bool = True,
    snippets: dict[str, dict[str, Any]] | None = None,
    include_default_snippets: bool = True,
    include_rule_snippets: bool = True,
    include_lsp: bool = True,
    extension_description: str | None = None,
    additional_contributions: dict[str, Any] | None = None,
    additional_files: dict[str, str | bytes] | None = None,
    readme_content: str | None = None,
    icon_data: bytes | None = None,
    additional_textmate_patterns: list[dict[str, Any]] | None = None,
    token_label_prefix: str = "Gram",
    include_hover: bool = False,
) -> Path:
    """Build a VS Code extension directory from language metadata and caller options."""
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)

    meta = metadata.copy() if metadata is not None else extract_metadata()

    if custom_extensions:
        for ext in custom_extensions:
            clean_ext = ext if ext.startswith(".") else f".{ext}"
            if clean_ext not in meta.file_extensions:
                meta.file_extensions.append(clean_ext)

    effective_compiler = compiler_path or meta.compiler_path
    effective_args = compiler_args if compiler_args is not None else meta.compiler_args

    syntaxes_dir = out / "syntaxes"
    syntaxes_dir.mkdir(parents=True, exist_ok=True)
    themes_dir = out / "themes"
    themes_dir.mkdir(parents=True, exist_ok=True)
    snippets_dir = out / "snippets"
    snippets_dir.mkdir(parents=True, exist_ok=True)
    if include_lsp or include_hover:
        (out / "client").mkdir(parents=True, exist_ok=True)

    # 1. package.json
    pkg_data = generate_package_json(
        ext_id=ext_id,
        ext_name=ext_name,
        version=version,
        publisher=publisher,
        theme_label=theme_name,
        file_extensions=meta.file_extensions,
        compiler_path=effective_compiler,
        compiler_args=effective_args,
        language_id=language_id,
        scope_name=scope_name,
        language_aliases=language_aliases,
        grammar_file=grammar_file,
        theme_file=theme_file,
        metadata=meta,
        extension_description=extension_description,
        include_lsp=include_lsp,
        include_hover=include_hover,
        additional_contributions=additional_contributions,
    )
    (out / "package.json").write_text(
        json.dumps(pkg_data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # 2. language-configuration.json
    lang_cfg = generate_language_configuration(meta, language_configuration)
    (out / "language-configuration.json").write_text(
        json.dumps(lang_cfg, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # 3. TextMate grammar
    tm_grammar = generate_textmate_grammar(
        meta,
        scope_name=scope_name,
        language_id=language_id,
        grammar_name=grammar_name,
        line_comment_token=(
            language_configuration.line_comment_token
            if language_configuration is not None
            else None
        ),
        additional_patterns=additional_textmate_patterns,
    )
    (syntaxes_dir / grammar_file).write_text(
        json.dumps(tm_grammar, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # 4. Color theme
    theme_cfg = generate_theme(
        meta,
        theme_name=theme_name,
        language_id=language_id,
        line_comment_token=(
            language_configuration.line_comment_token
            if language_configuration is not None
            else None
        ),
        editor_colors=theme_editor_colors,
        additional_token_colors=additional_token_colors,
        include_default_token_colors=include_default_theme_colors,
        token_label_prefix=token_label_prefix,
    )
    (themes_dir / theme_file).write_text(
        json.dumps(theme_cfg, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # 5. Snippets
    if snippets:
        meta.snippets.update(snippets)
    snippets_cfg = generate_snippets(
        meta,
        include_defaults=include_default_snippets,
        include_rule_snippets=include_rule_snippets,
    )
    (snippets_dir / "snippets.json").write_text(
        json.dumps(snippets_cfg, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # 6. Optional Gram LSP client
    if include_lsp:
        (out / "client" / "extension.js").write_text(
            generate_lsp_client_js(),
            encoding="utf-8",
        )
    elif include_hover:
        (out / "client" / "extension.js").write_text(
            generate_hover_client_js(meta, language_id),
            encoding="utf-8",
        )

    # 7. Extension icon
    if icon_data is not None:
        (out / "icon.png").write_bytes(icon_data)
    else:
        generate_icon_png(out / "icon.png")

    # 8. Documentation and caller-provided assets
    if readme_content is None:
        readme_content = "\n".join([
            f"# {ext_name}",
            "",
            extension_description or f"Language support for {', '.join(meta.file_extensions)} files.",
            "",
            f"- Language ID: `{language_id}`",
            f"- Keywords: {len(meta.keywords)}",
            f"- Syntax rules: {len(meta.rules)}",
            f"- File extensions: {', '.join(meta.file_extensions)}",
            "",
        ])
    (out / "README.md").write_text(readme_content.rstrip() + "\n", encoding="utf-8")

    for relative_path, content in (additional_files or {}).items():
        asset_path = Path(relative_path)
        if asset_path.is_absolute() or ".." in asset_path.parts:
            raise ValueError(f"Extension asset path must stay inside the output directory: {relative_path}")
        target = out / asset_path
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            target.write_bytes(content)
        else:
            target.write_text(content, encoding="utf-8")

    return out


def package_vsix(
    extension_dir: Path | str,
    output_vsix: Path | str | None = None,
) -> Path:
    """
    Empaqueta el árbol de directorio de una extensión de VS Code en un paquete .vsix estándar.
    Genera internamente los archivos requeridos de Open Packaging Conventions (OPC):
    - `[Content_Types].xml`
    - `extension.vsixmanifest`
    - Contenido bajo la carpeta `extension/`
    """
    ext_dir = Path(extension_dir).resolve()
    pkg_file = ext_dir / "package.json"
    if not pkg_file.exists():
        raise FileNotFoundError(f"No se encontró 'package.json' en {ext_dir}")

    pkg_data = json.loads(pkg_file.read_text(encoding="utf-8"))
    ext_id = pkg_data.get("name", GRAM_EXTENSION_NAME)
    version = pkg_data.get("version", "1.0.0")
    publisher = pkg_data.get("publisher", GRAM_PUBLISHER)
    display_name = pkg_data.get("displayName", "Gram Language Support")
    description = pkg_data.get("description", "Gram Language Support for VS Code")

    if output_vsix is None:
        vsix_target = ext_dir.parent / f"{ext_id}-{version}.vsix"
    else:
        vsix_target = Path(output_vsix).resolve()
        if vsix_target.suffix.lower() != ".vsix":
            vsix_target = vsix_target.with_suffix(".vsix")

    vsix_target.parent.mkdir(parents=True, exist_ok=True)

    content_types_xml = """<?xml version="1.0" encoding="utf-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="json" ContentType="application/json" />
  <Default Extension="js" ContentType="application/javascript" />
  <Default Extension="png" ContentType="image/png" />
  <Default Extension="svg" ContentType="image/svg+xml" />
  <Default Extension="md" ContentType="text/markdown" />
  <Default Extension="vsixmanifest" ContentType="text/xml" />
</Types>
"""

    vsix_manifest_xml = f"""<?xml version="1.0" encoding="utf-8"?>
<PackageManifest Version="2.0.0" xmlns="http://schemas.microsoft.com/developer/vsx-schema/2011" xmlns:d="http://schemas.microsoft.com/developer/vsx-schema-design/2011">
  <Metadata>
    <Identity Id={quoteattr(ext_id)} Version={quoteattr(version)} Publisher={quoteattr(publisher)} Language="en-US" />
    <DisplayName>{escape(display_name)}</DisplayName>
    <Description xml:space="preserve">{escape(description)}</Description>
    <Icon>extension/icon.png</Icon>
    <Categories>Programming Languages,Themes,Snippets,Linters</Categories>
  </Metadata>
  <Installation>
    <InstallationTarget Id="Microsoft.VisualStudio.Code" />
  </Installation>
  <Dependencies />
  <Assets>
    <Asset Type="Microsoft.VisualStudio.Code.Manifest" Path="extension/package.json" Addressable="true" />
    <Asset Type="Microsoft.VisualStudio.Services.Icons.Default" Path="extension/icon.png" Addressable="true" />
  </Assets>
</PackageManifest>
"""

    with zipfile.ZipFile(vsix_target, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types_xml)
        zf.writestr("extension.vsixmanifest", vsix_manifest_xml)

        for root, _, files in os.walk(ext_dir):
            for file in files:
                file_path = Path(root) / file
                rel_path = file_path.relative_to(ext_dir)
                archive_name = f"extension/{rel_path.as_posix()}"
                zf.write(file_path, arcname=archive_name)

    return vsix_target


__all__ = [
    "GRAM_PUBLISHER",
    "GRAM_EXTENSION_NAME",
    "GRAM_FULL_ID",
    "generate_textmate_grammar",
    "generate_theme",
    "generate_language_configuration",
    "generate_snippets",
    "generate_package_json",
    "generate_lsp_client_js",
    "generate_icon_png",
    "build_extension_directory",
    "package_vsix",
]
