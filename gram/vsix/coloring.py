"""
AST and Token Coloring Engine (`gram.vsix.coloring`).
=====================================================
Resolves token colors and TextMate scopes by projecting `RuleItem.colors`
maps onto the generated AST, supporting child-over-parent precedence,
lexer fallback, ANSI TrueColor preview, and editor export.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from gram.core.ast.nodes import ASTNode, ASTRef
from gram.core.combinators.base import RuleItem
from gram.core.combinators.expressions import ASTBinaryOp, ASTUnaryOp
from gram.core.lexer import words
from gram.core.lexer.tokens import Token, TokenType
from gram.core.rules.codes import code_manager


@dataclass(slots=True)
class ColoredToken:
    """
    Associates a matched token occurrence with its resolved color or scope.

    Attributes:
        token (TokenType): The concrete lexical token.
        color (str): Hex color (e.g., '#FF79C6') or TextMate scope (e.g., 'keyword.control').
        rule_name (str): Name of the rule assigning the color.
        token_index (int | str): Token index or selector key within the rule.
    """

    token: TokenType
    color: str
    rule_name: str
    token_index: int | str

    @property
    def is_hex(self) -> bool:
        """Return True if color is a valid hexadecimal color string."""
        raw = self.color.lstrip("#")
        return len(raw) in (3, 6, 8) and all(c in "0123456789abcdefABCDEF" for c in raw)

    @property
    def is_scope(self) -> bool:
        """Return True if color is a dot-separated TextMate scope selector."""
        return not self.is_hex and "." in self.color


class TokenSelector:
    """Resolves selector keys against a list of sequential lexical tokens."""

    @classmethod
    def resolve_indices(
        cls,
        key: int | str,
        tokens: list[TokenType],
    ) -> list[int]:
        """
        Map a selector key to matching zero-based indices in `tokens`.

        Supported key formats:
        - int: Positional index (e.g. 0, 1, -1).
        - Numeric string: Stringified index (e.g. "0", "-1").
        - Anchors: "@TOKEN_NAME" or "@TOKEN_NAME:±offset" (e.g. "@IDENT", "@ASSIGN:1").
        - Direct name/value: Matches token name, literal lexeme, or keyword group.
        """
        total = len(tokens)
        if total == 0:
            return []

        if isinstance(key, int):
            actual = key if key >= 0 else total + key
            return [actual] if 0 <= actual < total else []

        if not isinstance(key, str):
            return []

        raw = key.strip()
        if not raw:
            return []

        if raw.lstrip("-").isdigit():
            idx = int(raw)
            actual = idx if idx >= 0 else total + idx
            return [actual] if 0 <= actual < total else []

        if raw.startswith("@"):
            body = raw[1:]
            offset = 0
            if ":" in body:
                target_str, off_str = body.split(":", 1)
                try:
                    offset = int(off_str)
                except ValueError:
                    return []
            else:
                target_str = body

            matches: list[int] = []
            for i, tok in enumerate(tokens):
                tok_name = getattr(tok.token, "name", "")
                tok_val = str(tok.value)
                if tok_name == target_str or tok_val == target_str:
                    dest = i + offset
                    if 0 <= dest < total:
                        matches.append(dest)
            return matches

        matches = []
        for i, tok in enumerate(tokens):
            tok_name = getattr(tok.token, "name", "")
            tok_val = str(tok.value)
            if raw in (tok_name, tok_val):
                matches.append(i)
                continue

            if tok.token == Token.KEYWORD:
                kw_obj = words.get_keyword(tok_val)
                if kw_obj is not None and kw_obj.group == raw:
                    matches.append(i)

        return matches


class ASTColorResolver:
    """
    Modular engine to traverse AST trees and project rule color definitions
    onto concrete tokens with fallback to keyword registries.
    """

    def __init__(self, rule_lookup: dict[str, type[RuleItem]] | None = None) -> None:
        self.rule_lookup = rule_lookup if rule_lookup is not None else self._build_rule_lookup()

    @staticmethod
    def _build_rule_lookup() -> dict[str, type[RuleItem]]:
        """Construct lookup dictionary mapping rule names to RuleItem classes."""
        lookup: dict[str, type[RuleItem]] = {}
        for rule_cls in code_manager.rules.values():
            if isinstance(rule_cls, type) and issubclass(rule_cls, RuleItem):
                r_name = getattr(rule_cls, "name", "") or rule_cls.__name__
                lookup[r_name] = rule_cls
                lookup[rule_cls.__name__] = rule_cls
        return lookup

    @classmethod
    def collect_tokens(cls, node: Any) -> list[TokenType]:
        """Flatten all TokenType instances inside node hierarchy in source order."""
        tokens: list[TokenType] = []

        def _walk(item: Any) -> None:
            if item is None:
                return
            if isinstance(item, TokenType):
                tokens.append(item)
                return
            if isinstance(item, (list, tuple)):
                for sub in item:
                    _walk(sub)
                return
            if isinstance(item, ASTRef):
                _walk(item.nodes)
                return
            if isinstance(item, ASTBinaryOp):
                _walk(item.left)
                tokens.append(item.operator)
                _walk(item.right)
                return
            if isinstance(item, ASTUnaryOp):
                tokens.append(item.operator)
                _walk(item.operand)
                return
            if isinstance(item, ASTNode):
                tok = getattr(item, "token", None)
                if isinstance(tok, TokenType):
                    tokens.append(tok)

        _walk(node)
        return tokens

    def resolve(
        self,
        ast_roots: list[Any] | Any,
        *,
        child_overrides_parent: bool = True,
    ) -> list[ColoredToken]:
        """
        Traverse the AST, project rule color maps, and return mapped ColoredToken items.
        """
        color_map: dict[tuple[int, int, int], ColoredToken] = {}

        def _apply_rule(ref_node: ASTRef) -> None:
            rule_cls = self.rule_lookup.get(ref_node.name)
            flat_tokens = self.collect_tokens(ref_node)

            if rule_cls is not None and isinstance(rule_cls.colors, dict):
                for key, color_spec in rule_cls.colors.items():
                    if not isinstance(color_spec, str) or not color_spec:
                        continue
                    for idx in TokenSelector.resolve_indices(key, flat_tokens):
                        tok = flat_tokens[idx]
                        tok_key = (tok.line, tok.col, id(tok))
                        if child_overrides_parent or tok_key not in color_map:
                            color_map[tok_key] = ColoredToken(
                                token=tok,
                                color=color_spec,
                                rule_name=ref_node.name,
                                token_index=key,
                            )

            def _scan(items: Any) -> None:
                if isinstance(items, ASTRef):
                    _apply_rule(items)
                elif isinstance(items, (list, tuple)):
                    for sub in items:
                        _scan(sub)
                elif isinstance(items, ASTBinaryOp):
                    _scan(items.left)
                    _scan(items.right)
                elif isinstance(items, ASTUnaryOp):
                    _scan(items.operand)

            _scan(ref_node.nodes)

        roots = ast_roots if isinstance(ast_roots, (list, tuple)) else [ast_roots]
        for root in roots:
            if isinstance(root, ASTRef):
                _apply_rule(root)
            elif isinstance(root, (list, tuple)):
                for item in root:
                    if isinstance(item, ASTRef):
                        _apply_rule(item)

        all_tokens = self.collect_tokens(roots)
        for idx, tok in enumerate(all_tokens):
            tok_key = (tok.line, tok.col, id(tok))
            if tok_key not in color_map and tok.token == Token.KEYWORD:
                kw_obj = words.get_keyword(str(tok.value))
                if kw_obj is not None and getattr(kw_obj, "hex_color", None):
                    color_map[tok_key] = ColoredToken(
                        token=tok,
                        color=kw_obj.hex_color,
                        rule_name="LexerKeyword",
                        token_index=idx,
                    )

        return list(color_map.values())

    @staticmethod
    def hex_to_ansi(hex_color: str) -> str:
        """Convert a hex color string into a 24-bit ANSI TrueColor escape code."""
        clean = hex_color.lstrip("#")
        if len(clean) == 3:
            clean = "".join(c * 2 for c in clean)
        if len(clean) != 6:
            return ""
        try:
            r = int(clean[0:2], 16)
            g = int(clean[2:4], 16)
            b = int(clean[4:6], 16)
            return f"\033[38;2;{r};{g};{b}m"
        except ValueError:
            return ""

    def preview(self, source_code: str, ast_roots: list[Any] | Any) -> str:
        """Render source_code with 24-bit ANSI escape codes using resolved hex colors."""
        colored = self.resolve(ast_roots)
        lines = source_code.splitlines(keepends=True)
        if not lines:
            return ""

        by_line: dict[int, list[ColoredToken]] = {}
        for ct in colored:
            if ct.is_hex:
                by_line.setdefault(ct.token.line, []).append(ct)

        reset = "\033[0m"
        output_lines: list[str] = []

        for line_idx, raw_line in enumerate(lines, start=1):
            line_tokens = by_line.get(line_idx, [])
            if not line_tokens:
                output_lines.append(raw_line)
                continue

            line_tokens.sort(key=lambda c: c.token.col, reverse=True)
            modified = raw_line
            for ct in line_tokens:
                col = ct.token.col
                lexeme = str(ct.token.value)
                length = len(lexeme)
                ansi_code = self.hex_to_ansi(ct.color)
                if ansi_code and col + length <= len(modified):
                    modified = (
                        modified[:col]
                        + f"{ansi_code}{modified[col : col + length]}{reset}"
                        + modified[col + length :]
                    )
            output_lines.append(modified)

        return "".join(output_lines)


def collect_node_tokens(node: Any) -> list[TokenType]:
    """Convenience wrapper for ASTColorResolver.collect_tokens."""
    return ASTColorResolver.collect_tokens(node)


def resolve_ast_colors(
    ast_roots: list[Any] | Any,
    *,
    child_overrides_parent: bool = True,
) -> list[ColoredToken]:
    """Convenience wrapper for ASTColorResolver().resolve."""
    return ASTColorResolver().resolve(
        ast_roots,
        child_overrides_parent=child_overrides_parent,
    )


def preview_colored_source(source_code: str, ast_roots: list[Any] | Any) -> str:
    """Convenience wrapper for ASTColorResolver().preview."""
    return ASTColorResolver().preview(source_code, ast_roots)


__all__ = [
    "ASTColorResolver",
    "ColoredToken",
    "TokenSelector",
    "collect_node_tokens",
    "preview_colored_source",
    "resolve_ast_colors",
]
