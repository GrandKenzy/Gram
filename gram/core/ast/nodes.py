"""
Abstract Syntax Tree Nodes (`gram.core.ast.nodes`).
===================================================
Defines the hierarchy of `ASTNode` classes representing terminal tokens
(strings, numbers, identifiers, symbols, keywords) and composite rule
references (`ASTRef`) produced during syntactic analysis.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from gram.core.lexer.tokens import TokenType


class ASTNode:
    """Base class for all nodes in the Gram Abstract Syntax Tree."""
    __slots__ = ()
    
    def __repr__(self) -> str:
        return self.__class__.__name__

    def __eq__(self, value: object) -> bool:
        return self.__class__.__name__ == value

class ASTTokenNode(ASTNode):
    """Base class for terminal AST nodes backed by a single lexed token."""
    __slots__ = ('token',)

    def __init__(self, token: TokenType) -> None:
        """
        Initialize the terminal node with its corresponding lexer token.

        Args:
            token (TokenType): The lexed token instance.
        """
        self.token: TokenType = token

    def __repr__(self) -> str:
        return self.token.token.name
    
    def __eq__(self, value: object) -> bool:
        return self.token.token.name == value




class LiteralString(ASTTokenNode):
    """AST node representing a string or docstring literal."""
    __slots__ = ()


class LiteralNumber(ASTTokenNode):
    """AST node representing a numeric literal."""
    __slots__ = ()


class Identifier(ASTTokenNode):
    """AST node representing a user-defined identifier."""
    __slots__ = ()


class LiteralSymbol(ASTTokenNode):
    """AST node representing an operator, delimiter, or punctuation symbol."""
    __slots__ = ()


class ASTKeyword(ASTTokenNode):
    """AST node representing a reserved language keyword."""
    __slots__ = ()



class ASTRef(ASTNode):
    """AST node representing a named grammar rule reference and its child nodes."""
    __slots__ = ('name', 'nodes')

    def __init__(self, name: str, nodes: list[ASTNode]) -> None:
        """
        Initialize a composite rule reference node.

        Args:
            name (str): Identifier of the matched grammar rule.
            nodes (list[ASTNode]): Child AST nodes matched under this rule.
        """
        self.name: str = name
        self.nodes: list[ASTNode] = nodes

    def __repr__(self) -> str:
        return f'AstRef(nodes={len(self.nodes)}, name={self.name})'


class ArrayNode(ASTNode):
    """AST node representing a delimited sequence of elements (e.g. matched by Separator)."""
    __slots__ = ('items', 'trailing')

    def __init__(self, items: Sequence[Any], trailing: bool = False) -> None:
        """
        Initialize an ArrayNode.

        Args:
            items (Sequence[Any]): Child elements in the sequence.
            trailing (bool): Whether a trailing separator was present.
        """
        self.items: tuple[Any, ...] = tuple(items)
        self.trailing: bool = trailing

    def __len__(self) -> int:
        return len(self.items)

    def __iter__(self):
        return iter(self.items)

    def __getitem__(self, idx: int) -> Any:
        return self.items[idx]

    def __bool__(self) -> bool:
        return len(self.items) > 0

    def __repr__(self) -> str:
        return f"ArrayNode(items={list(self.items)!r}, trailing={self.trailing})"


class RawNode(ASTNode):
    """
    AST node representing an unparsed, opaque raw block of code or text
    (e.g., inline assembler, shader payloads, embedded DSL snippets).
    """
    __slots__ = ('tokens', 'text')

    def __init__(self, tokens: Sequence[TokenType], text: str = "") -> None:
        """
        Initialize a RawNode with the captured tokens and verbatim text.

        Args:
            tokens (Sequence[TokenType]): Tokens captured within the raw block.
            text (str): Verbatim or formatted source text of the raw block.
        """
        self.tokens: tuple[TokenType, ...] = tuple(tokens)
        self.text: str = text

    @property
    def line(self) -> int:
        """1-based starting line of the raw block (0 if empty)."""
        return self.tokens[0].line if self.tokens else 0

    @property
    def col(self) -> int:
        """0-based starting column of the raw block (0 if empty)."""
        return self.tokens[0].col if self.tokens else 0

    @property
    def end_line(self) -> int:
        """1-based ending line of the raw block (0 if empty)."""
        return self.tokens[-1].line if self.tokens else 0

    @property
    def end_col(self) -> int:
        """0-based ending column of the raw block (0 if empty)."""
        return self.tokens[-1].long() if self.tokens else 0

    def __len__(self) -> int:
        return len(self.tokens)

    def __iter__(self):
        return iter(self.tokens)

    def __getitem__(self, idx: int) -> TokenType:
        return self.tokens[idx]

    def __bool__(self) -> bool:
        return True

    def __repr__(self) -> str:
        return f"RawNode(tokens={len(self.tokens)}, text={self.text!r})"

    def __eq__(self, value: object) -> bool:
        if isinstance(value, RawNode):
            return self.tokens == value.tokens and self.text == value.text
        return False


__all__ = [
    'ArrayNode',
    'ASTKeyword',
    'ASTNode',
    'ASTRef',
    'ASTTokenNode',
    'Identifier',
    'LiteralNumber',
    'LiteralString',
    'LiteralSymbol',
    'RawNode',
]
