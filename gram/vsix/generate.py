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

from gram.vsix.extract import SyntaxMetadata, extract_metadata

# Identificador fijo universal de Gram VSIX
GRAM_PUBLISHER = "gram"
GRAM_EXTENSION_NAME = "gram-language-support"
GRAM_FULL_ID = f"{GRAM_PUBLISHER}.{GRAM_EXTENSION_NAME}"


def generate_textmate_grammar(
    metadata: SyntaxMetadata,
    scope_name: str = "source.gram",
    language_id: str = "gram",
) -> dict[str, Any]:
    """Construye la gramática sintáctica TextMate oficial a partir de los metadatos de Gram."""
    patterns: list[dict[str, Any]] = []

    # 1. Comentarios de línea (# ... y ; ...)
    patterns.append({
        "name": f"comment.line.number-sign.{language_id}",
        "match": r"(#|;).*$",
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
            rule_scope = r_meta.scope or f"entity.name.rule.{language_id}.{re.sub(r'[^a-zA-Z0-9_]', '_', r_name).lower()}"
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
        "name": "Gram",
        "scopeName": scope_name,
        "patterns": patterns,
    }


def generate_theme(
    metadata: SyntaxMetadata,
    theme_name: str = "Gram Theme",
    language_id: str = "gram",
) -> dict[str, Any]:
    """Genera un tema de color VS Code completo correlacionando definiciones de color con scopes."""
    token_colors: list[dict[str, Any]] = [
        {
            "name": "Gram Comments",
            "scope": [f"comment.line.number-sign.{language_id}"],
            "settings": {"foreground": "#6A9955", "fontStyle": "italic"},
        },
        {
            "name": "Gram Strings",
            "scope": [
                f"string.quoted.double.{language_id}",
                f"string.quoted.single.{language_id}",
                f"string.quoted.triple.double.{language_id}",
                f"string.quoted.triple.single.{language_id}",
            ],
            "settings": {"foreground": "#CE9178"},
        },
        {
            "name": "Gram Numbers",
            "scope": [
                f"constant.numeric.hex.{language_id}",
                f"constant.numeric.float.{language_id}",
                f"constant.numeric.integer.{language_id}",
            ],
            "settings": {"foreground": "#B5CEA8"},
        },
        {
            "name": "Gram Constants",
            "scope": [f"constant.language.{language_id}"],
            "settings": {"foreground": "#569CD6"},
        },
        {
            "name": "Gram Operators",
            "scope": [f"keyword.operator.{language_id}"],
            "settings": {"foreground": "#D4D4D4"},
        },
        {
            "name": "Gram Punctuation",
            "scope": [f"punctuation.separator.{language_id}"],
            "settings": {"foreground": "#D4D4D4"},
        },
        {
            "name": "Gram Rules",
            "scope": [f"entity.name.type.rule.{language_id}"],
            "settings": {"foreground": "#4EC9B0", "fontStyle": "bold"},
        },
    ]

    # 1. Colores declarados por plugins (PluginColors)
    for cat_name, c_def in metadata.colors.items():
        token_colors.append({
            "name": f"Gram Category: {cat_name}",
            "scope": [
                f"source.{language_id}.{cat_name.lower()}",
                f"keyword.other.{cat_name.lower()}.{language_id}",
                f"entity.name.{cat_name.lower()}.{language_id}",
            ],
            "settings": {
                "foreground": c_def.hex,
            },
        })

    # 2. Palabras clave con color hexadecimal explícito
    for kw_name, kw_meta in metadata.keywords.items():
        if kw_meta.hex_color and kw_meta.hex_color.upper() != "#FFFFFF":
            token_colors.append({
                "name": f"Gram Keyword: {kw_name}",
                "scope": [f"keyword.other.{kw_name.lower()}.{language_id}"],
                "settings": {
                    "foreground": kw_meta.hex_color,
                },
            })

    # 3. Reglas sintácticas con color individual
    for r_name, r_meta in metadata.rules.items():
        if r_meta.color and r_meta.color.upper() != "#FFFFFF":
            rule_scope = r_meta.scope or f"entity.name.rule.{language_id}.{re.sub(r'[^a-zA-Z0-9_]', '_', r_name).lower()}"
            token_colors.append({
                "name": f"Gram Rule: {r_name}",
                "scope": [rule_scope],
                "settings": {
                    "foreground": r_meta.color,
                    "fontStyle": "bold" if r_meta.is_structural else "normal",
                },
            })

    return {
        "name": theme_name,
        "type": "dark",
        "colors": {
            "editor.background": "#1E1E1E",
            "editor.foreground": "#D4D4D4",
        },
        "tokenColors": token_colors,
    }


def generate_language_configuration() -> dict[str, Any]:
    """Genera la configuración del lenguaje para delimitadores, llaves y auto-cierre."""
    return {
        "comments": {
            "lineComment": "#",
            "blockComment": ["/*", "*/"],
        },
        "brackets": [
            ["{", "}"],
            ["[", "]"],
            ["(", ")"],
        ],
        "autoClosingPairs": [
            {"open": "{", "close": "}"},
            {"open": "[", "close": "]"},
            {"open": "(", "close": ")"},
            {"open": '"', "close": '"', "notIn": ["string"]},
            {"open": "'", "close": "'", "notIn": ["string", "comment"]},
        ],
        "surroundingPairs": [
            ["{", "}"],
            ["[", "]"],
            ["(", ")"],
            ['"', '"'],
            ["'", "'"],
        ],
    }


def generate_snippets(metadata: SyntaxMetadata) -> dict[str, Any]:
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
    }

    # Agregar snippets para reglas de usuario
    for r_name, r_meta in metadata.rules.items():
        if r_meta.code >= 100:
            snippets[f"Rule: {r_name}"] = {
                "prefix": r_name.lower(),
                "body": [r_name],
                "description": r_meta.description or f"Regla sintáctica {r_name}",
            }
        if r_meta.suggestions and isinstance(r_meta.suggestions, dict):
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
) -> dict[str, Any]:
    """Construye el manifiesto package.json de la extensión de VS Code con comandos y compilador."""
    if metadata is not None:
        if file_extensions is None:
            file_extensions = metadata.file_extensions
        if not compiler_path:
            compiler_path = metadata.compiler_path
        if compiler_args is None:
            compiler_args = metadata.compiler_args

    exts = file_extensions or [".gram", ".glang", ".g"]
    args_list = compiler_args or []

    return {
        "name": ext_id,
        "displayName": ext_name,
        "description": "Soporte de lenguaje oficial para Gram Framework, GLang DSL, temas y Language Server Protocol.",
        "version": version,
        "publisher": publisher,
        "icon": "icon.png",
        "engines": {
            "vscode": "^1.70.0",
        },
        "main": "./client/extension.js",
        "activationEvents": [
            "onLanguage:gram",
            "onLanguage:glang",
            "workspaceContains:**/*.gram",
            "workspaceContains:**/*.glang",
            "onCommand:gram.compile",
            "onCommand:gram.run",
        ],
        "categories": [
            "Programming Languages",
            "Themes",
            "Snippets",
            "Linters",
        ],
        "contributes": {
            "languages": [
                {
                    "id": language_id,
                    "aliases": ["Gram", "gram", "glang"],
                    "extensions": exts,
                    "configuration": "./language-configuration.json",
                }
            ],
            "grammars": [
                {
                    "language": language_id,
                    "scopeName": scope_name,
                    "path": "./syntaxes/gram.tmLanguage.json",
                }
            ],
            "themes": [
                {
                    "label": theme_label,
                    "uiTheme": "vs-dark",
                    "path": "./themes/gram-theme.json",
                }
            ],
            "snippets": [
                {
                    "language": language_id,
                    "path": "./snippets/snippets.json",
                }
            ],
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
        },
    }


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
) -> Path:
    """Construye la estructura física completa de la extensión de VS Code lista para empaquetar o usar."""
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
    client_dir = out / "client"
    client_dir.mkdir(parents=True, exist_ok=True)

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
    )
    (out / "package.json").write_text(
        json.dumps(pkg_data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # 2. language-configuration.json
    lang_cfg = generate_language_configuration()
    (out / "language-configuration.json").write_text(
        json.dumps(lang_cfg, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # 3. syntaxes/gram.tmLanguage.json
    tm_grammar = generate_textmate_grammar(meta)
    (syntaxes_dir / "gram.tmLanguage.json").write_text(
        json.dumps(tm_grammar, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # 4. themes/gram-theme.json
    theme_cfg = generate_theme(meta, theme_name=theme_name)
    (themes_dir / "gram-theme.json").write_text(
        json.dumps(theme_cfg, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # 5. snippets/snippets.json
    snippets_cfg = generate_snippets(meta)
    (snippets_dir / "snippets.json").write_text(
        json.dumps(snippets_cfg, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # 6. client/extension.js (LSP client)
    (client_dir / "extension.js").write_text(
        generate_lsp_client_js(),
        encoding="utf-8",
    )

    # 7. icon.png
    generate_icon_png(out / "icon.png")

    # 8. README.md explicativo
    readme_lines = [
        f"# {ext_name}",
        "",
        "Extensión oficial de soporte de lenguaje para **Gram Framework** y **GLang**.",
        "",
        "## Capacidades Incluidas",
        "- **Resaltado de sintaxis TextMate:** palabras clave, literales, operadores y reglas.",
        "- **Esquema de color y temas:** paleta adaptativa vinculada a las reglas y plugins de Gram.",
        "- **Language Server Protocol (LSP):** marcado de errores en tiempo real, diagnósticos y hover.",
        "- **Autocompletado inteligente:** sugerencias declaradas en `RuleItem.suggestions` y palabras reservadas.",
        "- **Integración con compilador:** comandos para compilar y ejecutar código Gram directamente.",
        "",
        f"- **Palabras clave registradas:** {len(meta.keywords)}",
        f"- **Reglas sintácticas reconocidas:** {len(meta.rules)}",
        f"- **Extensiones de archivo soportadas:** {', '.join(meta.file_extensions)}",
        "",
    ]
    (out / "README.md").write_text("\n".join(readme_lines) + "\n", encoding="utf-8")

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
  <Default Extension="md" ContentType="text/markdown" />
  <Default Extension="vsixmanifest" ContentType="text/xml" />
</Types>
"""

    vsix_manifest_xml = f"""<?xml version="1.0" encoding="utf-8"?>
<PackageManifest Version="2.0.0" xmlns="http://schemas.microsoft.com/developer/vsx-schema/2011" xmlns:d="http://schemas.microsoft.com/developer/vsx-schema-design/2011">
  <Metadata>
    <Identity Id="{ext_id}" Version="{version}" Publisher="{publisher}" Language="en-US" />
    <DisplayName>{display_name}</DisplayName>
    <Description xml:space="preserve">{description}</Description>
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
