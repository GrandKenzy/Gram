"""
Compilador y Evaluador de SJSON (`gram.sjson.compiler`).
========================================================
Convierte documentos SJSON (JSON con variables, cálculos, comentarios '//'
y directivas de extensión 'extend') en estructuras Python nativas y
documentos JSON estándar (RFC 8259).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gram.core.lexer import Lexer, Token, words
from gram.core.lexer.tokens import TokenType
from gram.sjson.errors import (
    SJSONCalculationError,
    SJSONError,
    SJSONExtendError,
    SJSONVariableError,
)


def ensure_sjson_keywords() -> None:
    """Registra las palabras clave necesarias para SJSON en el lexer de Gram."""
    keywords_config = {
        "let": "#C586C0",
        "var": "#C586C0",
        "extend": "#DCDCAA",
        "true": "#569CD6",
        "false": "#569CD6",
        "null": "#569CD6",
    }
    for kw, color in keywords_config.items():
        if not words.keyword_exists(kw):
            words.add_keyword(kw, hex_color=color, allow_override=True)


class Scope:
    """Entorno léxico jerárquico para almacenar variables numéricas y strings."""

    def __init__(self, parent: Scope | None = None) -> None:
        self.parent = parent
        self.vars: dict[str, int | float | str] = {}

    def set(self, name: str, value: int | float | str, line: int | None = None, col: int | None = None) -> None:
        # Validación estricta: sólo int, float o str (excluyendo explícitamente bool)
        if isinstance(value, bool) or not isinstance(value, (int, float, str)):
            raise SJSONVariableError(
                f"Solo se permiten variables numéricas (int, float) y strings. "
                f"Se intentó asignar el tipo '{type(value).__name__}' ({repr(value)}) a la variable '{name}'.",
                line=line,
                col=col,
            )
        self.vars[name] = value

    def get(self, name: str, line: int | None = None, col: int | None = None) -> int | float | str:
        if name in self.vars:
            return self.vars[name]
        if self.parent is not None:
            return self.parent.get(name, line=line, col=col)
        raise SJSONVariableError(f"Variable '{name}' no definida.", line=line, col=col)

    def __contains__(self, name: str) -> bool:
        return name in self.vars or (self.parent is not None and name in self.parent)


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Combina recursivamente dos diccionarios, dando prioridad a las claves del hijo."""
    merged = dict(base)
    for k, v in override.items():
        if k in merged and isinstance(merged[k], dict) and isinstance(v, dict):
            merged[k] = deep_merge(merged[k], v)
        else:
            merged[k] = v
    return merged


class SJSONCompiler:
    """
    Analizador sintáctico y evaluador de SJSON.
    Procesa el flujo de tokens generado por Lexer(comment_token='//').
    """

    def __init__(
        self,
        source: str,
        base_dir: Path | str | None = None,
        source_name: str | None = None,
        visited_paths: set[Path] | None = None,
    ) -> None:
        self.source = source
        self.base_dir = Path(base_dir).resolve() if base_dir else Path.cwd()
        self.source_name = source_name or "<sjson>"
        self.visited_paths = set(visited_paths) if visited_paths else set()

        ensure_sjson_keywords()
        lexer = Lexer(source, comment_token="//")
        raw_tokens = lexer.process()

        # Filtrar ruido no estructural de formato
        ignored = {Token.INDENT, Token.DEDENT, Token.NEWLINE, Token.COMMENT, Token.EOF}
        self.tokens: list[TokenType] = [t for t in raw_tokens if t.token not in ignored]
        self.pos: int = 0
        self.root_scope: Scope = Scope()

    # --------------------------------------------------------------------------
    # Navegación del flujo de tokens
    # --------------------------------------------------------------------------

    def peek(self) -> TokenType | None:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def previous(self) -> TokenType:
        return self.tokens[self.pos - 1]

    def is_at_end(self) -> bool:
        return self.pos >= len(self.tokens)

    def advance(self) -> TokenType:
        if not self.is_at_end():
            self.pos += 1
        return self.tokens[self.pos - 1]

    def match(self, *expected_tokens: Token) -> bool:
        cur = self.peek()
        if cur and cur.token in expected_tokens:
            self.advance()
            return True
        return False

    def check(self, *expected_tokens: Token) -> bool:
        cur = self.peek()
        return bool(cur and cur.token in expected_tokens)

    def check_keyword(self, name: str) -> bool:
        cur = self.peek()
        if not cur:
            return False
        return (cur.token in (Token.KEYWORD, Token.IDENT)) and str(cur.value) == name

    def match_keyword(self, name: str) -> bool:
        if self.check_keyword(name):
            self.advance()
            return True
        return False

    def consume(self, expected: Token, message: str) -> TokenType:
        cur = self.peek()
        if cur and cur.token == expected:
            return self.advance()
        line = cur.line + 1 if cur else None
        col = cur.col + 1 if cur else None
        raise SJSONError(message, line=line, col=col, source_file=self.source_name)

    # --------------------------------------------------------------------------
    # Compilación principal
    # --------------------------------------------------------------------------

    def compile(self) -> Any:
        """Parsea el documento completo y retorna la estructura Python resultante."""
        if not self.tokens:
            return {}

        # 1. Procesar declaraciones de variables a nivel raíz (let / var)
        while not self.is_at_end():
            if self.check_keyword("let") or self.check_keyword("var"):
                self.parse_var_declaration(self.root_scope)
                # Separador opcional ';' o ','
                self.match(Token.SEMICOLON, Token.COMMA)
            else:
                break

        if self.is_at_end():
            return {}

        # 2. Parsear el valor JSON raíz (objeto, array o primitivo)
        result = self.parse_value(self.root_scope)

        # Si aún quedan declaraciones de variables u otros tokens
        if not self.is_at_end():
            cur = self.peek()
            line = cur.line + 1 if cur else None
            col = cur.col + 1 if cur else None
            raise SJSONError(
                f"Token inesperado '{cur.value if cur else ''}' después del valor JSON principal.",
                line=line,
                col=col,
                source_file=self.source_name,
            )

        return result

    # --------------------------------------------------------------------------
    # Declaración de variables
    # --------------------------------------------------------------------------

    def parse_var_declaration(self, scope: Scope) -> None:
        decl_token = self.advance()  # 'let' o 'var'
        var_line = decl_token.line + 1
        var_col = decl_token.col + 1

        name_token = self.peek()
        if not name_token or name_token.token not in (Token.IDENT, Token.STRING):
            raise SJSONVariableError(
                "Se esperaba el nombre de la variable después de 'let' o 'var'.",
                line=var_line,
                col=var_col,
                source_file=self.source_name,
            )
        self.advance()
        var_name = self._strip_quotes(str(name_token.value))

        self.consume(Token.ASSIGN, f"Se esperaba '=' en la declaración de variable '{var_name}'.")

        # Evaluar la expresión asignada en el scope actual
        val = self.parse_expression(scope)

        # Almacenar con validación estricta (números y strings solamente)
        scope.set(var_name, val, line=var_line, col=var_col)

    # --------------------------------------------------------------------------
    # Valores JSON y Estructuras
    # --------------------------------------------------------------------------

    def parse_value(self, scope: Scope) -> Any:
        cur = self.peek()
        if not cur:
            raise SJSONError("Fin inesperado de archivo mientras se esperaba un valor.", source_file=self.source_name)

        if cur.token == Token.LBRACE:
            return self.parse_object(scope)
        elif cur.token == Token.LBRACKET:
            return self.parse_array(scope)
        elif cur.token == Token.BOOL:
            self.advance()
            return bool(cur.value)
        elif cur.token == Token.NULL:
            self.advance()
            return None
        elif self.check_keyword("true"):
            self.advance()
            return True
        elif self.check_keyword("false"):
            self.advance()
            return False
        elif self.check_keyword("null"):
            self.advance()
            return None

        # Si no es objeto ni array ni literal nulo/booleano puro, evaluar como expresión/cálculo
        return self.parse_expression(scope)

    def parse_object(self, scope: Scope) -> dict[str, Any]:
        lbrace = self.consume(Token.LBRACE, "Se esperaba '{' al inicio del objeto.")
        obj_scope = Scope(parent=scope)
        result: dict[str, Any] = {}
        extend_target: str | None = None

        while not self.is_at_end() and not self.check(Token.RBRACE):
            # 1. Variables locales dentro del objeto
            if self.check_keyword("let") or self.check_keyword("var"):
                self.parse_var_declaration(obj_scope)
                self.match(Token.SEMICOLON, Token.COMMA)
                continue

            # 2. Clave del par clave: valor
            key_token = self.peek()
            if not key_token or key_token.token not in (Token.STRING, Token.IDENT, Token.KEYWORD):
                raise SJSONError(
                    f"Clave de objeto inválida: se esperaba cadena o identificador, pero se encontró '{key_token.value if key_token else ''}'.",
                    line=key_token.line + 1 if key_token else None,
                    col=key_token.col + 1 if key_token else None,
                    source_file=self.source_name,
                )
            self.advance()
            key_name = self._strip_quotes(str(key_token.value))

            self.consume(Token.COLON, f"Se esperaba ':' después de la clave '{key_name}'.")

            # 3. Valor del par
            val = self.parse_value(obj_scope)

            # Si la clave es 'extend', registrarla para importar y NO conservarla en el JSON final
            if key_name == "extend":
                if not isinstance(val, str):
                    raise SJSONExtendError(
                        f"La directiva 'extend' debe especificar una ruta como string, pero se obtuvo {type(val).__name__} ({repr(val)}).",
                        line=key_token.line + 1,
                        col=key_token.col + 1,
                        source_file=self.source_name,
                    )
                extend_target = val
            else:
                result[key_name] = val

            # Delimitador entre pares: coma opcional (soporta trailing comma)
            if not self.match(Token.COMMA):
                self.match(Token.SEMICOLON)
                if not self.check(Token.RBRACE):
                    break

        self.consume(Token.RBRACE, "Se esperaba '}' al cerrar el objeto.")

        # 4. Procesar herencia/importación extend si se especificó
        if extend_target is not None:
            base_dict = self._resolve_extend(extend_target, line=lbrace.line + 1, col=lbrace.col + 1)
            result = deep_merge(base_dict, result)

        return result

    def parse_array(self, scope: Scope) -> list[Any]:
        self.consume(Token.LBRACKET, "Se esperaba '[' al inicio del arreglo.")
        result: list[Any] = []

        while not self.is_at_end() and not self.check(Token.RBRACKET):
            val = self.parse_value(scope)
            result.append(val)

            # Delimitador entre elementos: coma con soporte para trailing comma
            if not self.match(Token.COMMA):
                if not self.check(Token.RBRACKET):
                    break

        self.consume(Token.RBRACKET, "Se esperaba ']' al cerrar el arreglo.")
        return result

    # --------------------------------------------------------------------------
    # Evaluación de Expresiones y Cálculos (+, -, *, /, %, agrupación)
    # --------------------------------------------------------------------------

    def parse_expression(self, scope: Scope) -> Any:
        return self._parse_additive(scope)

    def _parse_additive(self, scope: Scope) -> Any:
        left = self._parse_multiplicative(scope)

        while self.match(Token.PLUS, Token.MINUS):
            op_tok = self.previous()
            op = op_tok.token
            line = op_tok.line + 1
            col = op_tok.col + 1
            right = self._parse_multiplicative(scope)

            if op == Token.PLUS:
                # Concatenación de cadenas si al menos un operando es string
                if isinstance(left, str) or isinstance(right, str):
                    left = str(left) + str(right)
                elif isinstance(left, (int, float)) and isinstance(right, (int, float)):
                    res = left + right
                    left = int(res) if isinstance(res, float) and res.is_integer() else res
                else:
                    raise SJSONCalculationError(
                        f"No se puede sumar {type(left).__name__} ({repr(left)}) y {type(right).__name__} ({repr(right)}).",
                        line=line,
                        col=col,
                        source_file=self.source_name,
                    )
            elif op == Token.MINUS:
                if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                    res = left - right
                    left = int(res) if isinstance(res, float) and res.is_integer() else res
                else:
                    raise SJSONCalculationError(
                        f"La resta '-' solo se permite entre números, no entre {type(left).__name__} y {type(right).__name__}.",
                        line=line,
                        col=col,
                        source_file=self.source_name,
                    )

        return left

    def _parse_multiplicative(self, scope: Scope) -> Any:
        left = self._parse_unary(scope)

        while self.match(Token.STAR, Token.SLASH, Token.PERCENT):
            op_tok = self.previous()
            op = op_tok.token
            line = op_tok.line + 1
            col = op_tok.col + 1
            right = self._parse_unary(scope)

            if op == Token.STAR:
                if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                    res = left * right
                    left = int(res) if isinstance(res, float) and res.is_integer() else res
                elif isinstance(left, str) and isinstance(right, int):
                    left = left * right
                elif isinstance(left, int) and isinstance(right, str):
                    left = left * right
                else:
                    raise SJSONCalculationError(
                        f"No se puede multiplicar {type(left).__name__} y {type(right).__name__}.",
                        line=line,
                        col=col,
                        source_file=self.source_name,
                    )

            elif op == Token.SLASH:
                if not (isinstance(left, (int, float)) and isinstance(right, (int, float))):
                    raise SJSONCalculationError(
                        f"La división '/' requiere operandos numéricos, se obtuvo {type(left).__name__} y {type(right).__name__}.",
                        line=line,
                        col=col,
                        source_file=self.source_name,
                    )
                if right == 0:
                    raise SJSONCalculationError("División por cero en cálculo SJSON.", line=line, col=col, source_file=self.source_name)
                res = left / right
                left = int(res) if res.is_integer() else res

            elif op == Token.PERCENT:
                if not (isinstance(left, (int, float)) and isinstance(right, (int, float))):
                    raise SJSONCalculationError(
                        f"El módulo '%' requiere operandos numéricos, se obtuvo {type(left).__name__} y {type(right).__name__}.",
                        line=line,
                        col=col,
                        source_file=self.source_name,
                    )
                if right == 0:
                    raise SJSONCalculationError("Módulo por cero en cálculo SJSON.", line=line, col=col, source_file=self.source_name)
                res = left % right
                left = int(res) if isinstance(res, float) and res.is_integer() else res

        return left

    def _parse_unary(self, scope: Scope) -> Any:
        if self.match(Token.MINUS):
            op_tok = self.previous()
            line = op_tok.line + 1
            col = op_tok.col + 1
            val = self._parse_unary(scope)
            if not isinstance(val, (int, float)):
                raise SJSONCalculationError(f"No se puede aplicar '-' unario a {type(val).__name__} ({repr(val)}).", line=line, col=col, source_file=self.source_name)
            return -val

        if self.match(Token.PLUS):
            op_tok = self.previous()
            line = op_tok.line + 1
            col = op_tok.col + 1
            val = self._parse_unary(scope)
            if not isinstance(val, (int, float)):
                raise SJSONCalculationError(f"No se puede aplicar '+' unario a {type(val).__name__} ({repr(val)}).", line=line, col=col, source_file=self.source_name)
            return +val

        return self._parse_primary(scope)

    def _parse_primary(self, scope: Scope) -> Any:
        cur = self.peek()
        if not cur:
            raise SJSONError("Se esperaba una expresión o valor pero se alcanzó el fin de archivo.", source_file=self.source_name)

        line = cur.line + 1
        col = cur.col + 1

        # Literales numéricos
        if self.match(Token.NUMBER):
            val_str = str(cur.value)
            return float(val_str) if "." in val_str or "e" in val_str.lower() else int(val_str)

        # Literales de cadena
        if self.match(Token.STRING):
            return self._strip_quotes(str(cur.value))

        # Booleanos y Null
        if self.match(Token.BOOL):
            return bool(cur.value)
        if self.match(Token.NULL):
            return None
        if self.check_keyword("true"):
            self.advance()
            return True
        if self.check_keyword("false"):
            self.advance()
            return False
        if self.check_keyword("null"):
            self.advance()
            return None

        # Identificadores (referencias a variables)
        if self.match(Token.IDENT):
            name = str(cur.value)
            return scope.get(name, line=line, col=col)

        # Paréntesis agrupadores '(' expr ')'
        if self.match(Token.LPAREN):
            val = self.parse_expression(scope)
            self.consume(Token.RPAREN, "Se esperaba ')' para cerrar la expresión agrupada.")
            return val

        # Objetos o Arrays embebidos dentro de expresiones
        if cur.token == Token.LBRACE:
            return self.parse_object(scope)
        if cur.token == Token.LBRACKET:
            return self.parse_array(scope)

        self.advance()
        raise SJSONError(
            f"Símbolo o expresión inesperada: '{cur.value}' ({cur.token}).",
            line=line,
            col=col,
            source_file=self.source_name,
        )

    # --------------------------------------------------------------------------
    # Resolución de herencia 'extend'
    # --------------------------------------------------------------------------

    def _resolve_extend(self, rel_path_str: str, line: int, col: int) -> dict[str, Any]:
        target_path = (self.base_dir / rel_path_str).resolve()
        if not target_path.exists():
            raise SJSONExtendError(
                f"No se encontró el archivo referenciado en extend: '{rel_path_str}' (resuelto a: '{target_path}').",
                line=line,
                col=col,
                source_file=self.source_name,
            )

        if target_path in self.visited_paths:
            cycle = " -> ".join(str(p) for p in list(self.visited_paths) + [target_path])
            raise SJSONExtendError(
                f"Dependencia circular detectada en directiva 'extend': {cycle}",
                line=line,
                col=col,
                source_file=self.source_name,
            )

        content = target_path.read_text(encoding="utf-8-sig")

        # Si es un archivo .json puro, intentar primero json estándar o el compilador SJSON
        new_visited = self.visited_paths | {target_path}
        sub_compiler = SJSONCompiler(
            source=content,
            base_dir=target_path.parent,
            source_name=str(target_path),
            visited_paths=new_visited,
        )
        data = sub_compiler.compile()

        if not isinstance(data, dict):
            raise SJSONExtendError(
                f"El archivo extendido '{target_path.name}' debe contener un objeto JSON (dict), pero se obtuvo {type(data).__name__}.",
                line=line,
                col=col,
                source_file=self.source_name,
            )

        return data

    @staticmethod
    def _strip_quotes(text: str) -> str:
        if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
            return text[1:-1]
        return text


# ==============================================================================
# FACHADA PÚBLICA DE ALTO NIVEL
# ==============================================================================

def parse(source_code: str, base_dir: Path | str | None = None) -> Any:
    """
    Analiza y evalúa código fuente SJSON devolviendo la estructura nativa de Python.
    """
    compiler = SJSONCompiler(source_code, base_dir=base_dir)
    return compiler.compile()


def compile(
    source_code: str,
    base_dir: Path | str | None = None,
    indent: int = 4,
) -> str:
    """
    Compila código fuente SJSON produciendo una cadena JSON común y corriente (RFC 8259).
    """
    data = parse(source_code, base_dir=base_dir)
    return json.dumps(data, indent=int(indent), ensure_ascii=False)


def compile_file(
    input_file: Path | str,
    output_file: Path | str | None = None,
    indent: int = 4,
) -> Path:
    """
    Lee un archivo .sjson, compila sus variables, cálculos y herencia, y escribe
    un archivo .json estándar listo para producción.
    """
    in_path = Path(input_file).resolve()
    if not in_path.exists():
        raise FileNotFoundError(f"Archivo SJSON no encontrado: {in_path}")

    source = in_path.read_text(encoding="utf-8-sig")
    compiled_json = compile(source, base_dir=in_path.parent, indent=indent)

    if output_file is None:
        if in_path.suffix.lower() == ".sjson":
            out_path = in_path.with_suffix(".json")
        else:
            out_path = in_path.parent / f"{in_path.name}.json"
    else:
        out_path = Path(output_file).resolve()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(compiled_json + "\n", encoding="utf-8")
    return out_path
