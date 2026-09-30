"""
Motor de Análisis Sintáctico de C (`examples.CExample.c_parser`).
================================================================
Construye el AST completo de código fuente en C utilizando el Lexer
y el ASTAnalyzer de Gram Framework.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from gram.core.ast.analyzer import ASTAnalyzer
from gram.core.ast.nodes import ASTNode, ASTProgram
from gram.core.lexer import Lexer, Token, TokenType
from gram.core.parser import Parser
from .grammar import (
    C_FUNC_DECL,
    C_FUNC_DEF,
    C_IF_STMT,
    C_RETURN_STMT,
    C_TYPE,
    C_VAR_DECL,
    C_WHILE_STMT,
    get_c_grammar,
    setup_c_keywords,
)


class CParser:
    """Analizador sintáctico para un subconjunto expresivo del lenguaje C."""

    def __init__(self) -> None:
        setup_c_keywords()
        self.grammar = get_c_grammar()

    def preprocess(self, source: str) -> tuple[str, list[str]]:
        """
        Extrae directivas de preprocesador (#include) y normaliza comentarios de bloque.
        Retorna (código_normalizado, lista_de_includes).
        """
        includes: list[str] = []
        cleaned_lines: list[str] = []

        # 1. Normalizar comentarios de bloque /* ... */ conservando saltos de línea
        def replace_block_comment(match: re.Match) -> str:
            comment_text = match.group(0)
            newlines_count = comment_text.count("\n")
            return "\n" * newlines_count if newlines_count > 0 else " "

        normalized_source = re.sub(r"/\*.*?\*/", replace_block_comment, source, flags=re.DOTALL)

        # 2. Extraer directivas #include preservando líneas vacías
        for line in normalized_source.splitlines():
            stripped = line.strip()
            if stripped.startswith("#include"):
                inc_match = re.search(r'#include\s+([<"][^>"]+[>"])', stripped)
                if inc_match:
                    includes.append(inc_match.group(1))
                else:
                    includes.append(stripped.replace("#include", "").strip())
                cleaned_lines.append("")  # Reemplazar con línea vacía para mantener número de línea
            elif stripped.startswith("#"):
                cleaned_lines.append("")  # Ignorar otras directivas de preprocesador
            else:
                cleaned_lines.append(line)

        return "\n".join(cleaned_lines), includes

    def parse(self, source: str) -> ASTProgram:
        """
        Analiza código fuente en lenguaje C y genera el árbol ASTProgram.
        """
        cleaned_source, includes = self.preprocess(source)

        # Tokenización con Lexer de Gram reconociendo comentarios '//'
        lexer = Lexer(cleaned_source, comment_token="//")
        raw_tokens = lexer.process()

        # En C las llaves { } definen los bloques; descartamos indentaciones cosméticas
        ignored = {Token.INDENT, Token.DEDENT, Token.NEWLINE, Token.COMMENT, Token.EOF}
        filtered_tokens: list[TokenType] = [t for t in raw_tokens if t.token not in ignored]

        if not filtered_tokens:
            ast_empty = ASTProgram()
            setattr(ast_empty, "includes", includes)
            return ast_empty

        # Parsing y construcción del AST con Gram ASTAnalyzer
        parser = Parser(filtered_tokens)
        analyzer = ASTAnalyzer(parser, self.grammar)
        ast = analyzer.process()

        # Adjuntar metadatos de includes extraídos
        setattr(ast, "includes", includes)
        return ast

    def parse_file(self, file_path: str | Path) -> ASTProgram:
        """Lee un archivo fuente .c y lo parsea."""
        path = Path(file_path).resolve()
        source = path.read_text(encoding="utf-8")
        return self.parse(source)

    def extract_symbols(self, ast: ASTProgram) -> dict[str, Any]:
        """
        Extrae un resumen estructurado de las funciones, variables y directivas analizadas.
        """
        functions: list[dict[str, Any]] = []
        variables: list[dict[str, Any]] = []
        statement_types: dict[str, int] = {}

        for decl in ast.body:
            decl_name = getattr(decl, "name", "")
            tokens = getattr(decl, "tokens", [])

            # Funciones (Definiciones o Declaraciones)
            if decl_name in ("C_FUNC_DEF", "C_FUNC_DECL"):
                func_type = "void"
                func_name = "unknown"
                is_def = decl_name == "C_FUNC_DEF"

                # Extraer tipo y nombre de función de sus tokens
                token_vals = [t.value for t in tokens if hasattr(t, "value")]
                if token_vals:
                    func_type = str(token_vals[0])
                    if len(token_vals) > 1:
                        func_name = str(token_vals[1])

                line_no = tokens[0].line if tokens and hasattr(tokens[0], "line") else 1
                functions.append({
                    "name": func_name,
                    "return_type": func_type,
                    "is_definition": is_def,
                    "line": line_no,
                })

            # Variables Globales
            elif decl_name == "C_VAR_DECL":
                var_type = "unknown"
                var_name = "unknown"
                token_vals = [t.value for t in tokens if hasattr(t, "value")]
                if token_vals:
                    var_type = str(token_vals[0])
                    if len(token_vals) > 1:
                        var_name = str(token_vals[1])

                line_no = tokens[0].line if tokens and hasattr(tokens[0], "line") else 1
                variables.append({
                    "name": var_name,
                    "type": var_type,
                    "line": line_no,
                })

            # Conteo de sentencias
            statement_types[decl_name] = statement_types.get(decl_name, 0) + 1

        return {
            "includes": getattr(ast, "includes", []),
            "functions": functions,
            "variables": variables,
            "statements_by_type": statement_types,
            "total_top_level_declarations": len(ast.body),
        }

    def format_tree(self, ast: ASTProgram, ascii_only: bool = False) -> str:
        """
        Formatea el AST en una representación de árbol jerárquica y legible.
        """
        p_root = "+-- " if ascii_only else "├── "
        p_leaf = "\\-- " if ascii_only else "└── "
        p_bar = "|   " if ascii_only else "│   "
        p_space = "    "

        lines: list[str] = [f"ASTProgram (Declaraciones raíz: {len(ast.body)})"]

        includes = getattr(ast, "includes", [])
        if includes:
            lines.append(f"{p_root}Includes de Preprocesador:")
            for inc in includes:
                lines.append(f"{p_bar}{p_root}#include {inc}")

        for i, node in enumerate(ast.body):
            is_last = (i == len(ast.body) - 1)
            prefix = p_leaf if is_last else p_root
            child_prefix = p_space if is_last else p_bar

            try:
                formatted = node.format()
                if ascii_only:
                    formatted = formatted.replace("├──", "+--").replace("└──", "\\--").replace("│", "|")
                formatted_lines = formatted.splitlines()
                lines.append(f"{prefix}{formatted_lines[0]}")
                for fl in formatted_lines[1:]:
                    lines.append(f"{child_prefix}{fl}")
            except Exception:
                tokens_preview = [str(t.value) for t in getattr(node, "tokens", [])[:5]]
                lines.append(f"{prefix}{node.name} -> tokens={tokens_preview}")

        result = "\n".join(lines)
        if ascii_only:
            result = result.replace("├──", "+--").replace("└──", "\\--").replace("│", "|")
        return result


def parse_c(source: str) -> ASTProgram:
    """Función de conveniencia para parsear código C directamente."""
    return CParser().parse(source)


def parse_c_file(file_path: str | Path) -> ASTProgram:
    """Función de conveniencia para parsear un archivo .c."""
    return CParser().parse_file(file_path)


__all__ = [
    "CParser",
    "parse_c",
    "parse_c_file",
]
