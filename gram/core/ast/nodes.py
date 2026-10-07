"""
Abstract Syntax Tree Nodes and Structures (`gram.core.ast.nodes`).
==================================================================
EN:
    Defines the fundamental `ASTNode` class, the root program node `ASTProgram`,
    and comprehensive visualization, hierarchical search, and serialization tools (.txt and .json).

ES:
    Define la clase fundamental `ASTNode`, el nodo raíz del programa `ASTProgram`,
    y herramientas de visualización, búsqueda jerárquica y serialización (.txt y .json).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator, Self

from gram.core.lexer.tokens import CustomToken, Token, TokenType


class Identifier(str):
    """String-compatible AST value that preserves identifier semantics."""

    def __new__(cls, name: str) -> Self:
        return super().__new__(cls, name)

    @property
    def name(self) -> str:
        return str(self)

    def __repr__(self) -> str:
        return f"Identifier({super().__repr__()})"


@dataclass
class ASTNode:
    """
    EN:
        Represents a core node within the Abstract Syntax Tree (AST).
        Stores the generating grammatical rule, its code, hierarchy/indentation
        level, consumed tokens, and child nodes.

    ES:
        Representa un nodo fundamental dentro del Árbol de Sintaxis Abstracta (AST).
        Almacena la regla gramatical que lo originó, su código, el nivel jerárquico
        o de indentación, los tokens consumidos y sus nodos hijos.
    """

    name: str
    rule: Any = None
    code: int = 0
    level: int = 0
    tokens: list[TokenType] = field(default_factory=list)
    children: list[ASTNode] = field(default_factory=list)
    parent: ASTNode | None = None
    attributes: dict[str, Any] = field(default_factory=dict)

    @property
    def is_block(self) -> bool:
        """
        EN: Indicates whether the node represents a block containing child nodes.
        ES: Indica si el nodo representa un bloque que contiene nodos hijos.
        """
        return len(self.children) > 0

    @property
    def body(self) -> list[ASTNode]:
        """
        EN: Alias to access the list of child nodes forming the block body.
        ES: Alias para acceder a los nodos hijos que componen el cuerpo del bloque.
        """
        return self.children

    @property
    def has_children(self) -> bool:
        """
        EN: Determines whether the node possesses immediate child descendants.
        ES: Determina si el nodo posee hijos descendientes inmediatos.
        """
        return bool(self.children)

    @property
    def child_count(self) -> int:
        """
        EN: Number of immediate child nodes.
        ES: Cantidad de nodos hijos directos.
        """
        return len(self.children)

    @property
    def depth(self) -> int:
        """
        EN: Depth of this node relative to the hierarchy root (0 for the root).
        ES: Profundidad del nodo respecto a la raíz del árbol (0 para la raíz).
        """
        d = 0
        curr = self.parent
        while curr is not None:
            d += 1
            curr = curr.parent
        return d

    @property
    def root(self) -> ASTNode:
        """
        EN: Root node at the top of the genealogical hierarchy.
        ES: Nodo raíz en la cúspide de la jerarquía genealógica.
        """
        curr = self
        while curr.parent is not None:
            curr = curr.parent
        return curr

    @property
    def siblings(self) -> list[ASTNode]:
        """
        EN: List of sibling nodes belonging to the same parent (excluding this node).
        ES: Lista de nodos hermanos (excluyendo a este nodo).
        """
        if self.parent is None:
            return []
        return [c for c in self.parent.children if c is not self]

    @property
    def index_in_parent(self) -> int:
        """
        EN: Ordinal index within the parent's children list (-1 if orphaned).
        ES: Índice del nodo dentro de la lista de hijos del padre (-1 si no tiene padre).
        """
        if self.parent is None:
            return -1
        try:
            return self.parent.children.index(self)
        except ValueError:
            return -1

    @property
    def values(self) -> list[Any]:
        """
        EN: Extracts all semantic literal and identifier values from the node's tokens.
        ES: Extrae y devuelve todos los valores semánticos literales e identificadores del nodo.
        """
        structural_keywords = {
            "DECLARE",
            "RULE",
            "Keyword",
            "Token",
            "Seq",
            "Alt",
            "Opt",
            "Many",
            "Some",
            "New",
            "SeqSym",
        }
        result: list[Any] = []
        for t in self.tokens:
            if t.token == Token.IDENT:
                result.append(Identifier(str(t.value)))
            elif t.token in (Token.STRING, Token.NUMBER, Token.BOOL, Token.CHAR):
                result.append(t.value)
            elif t.token == Token.KEYWORD and str(t.value) not in structural_keywords:
                result.append(t.value)
            elif (
                isinstance(t.token, CustomToken)
                or getattr(t.token, "name", "") == "CustomToken"
                or str(getattr(t.token, "name", "")).startswith("Custom")
            ):
                result.append(t.value)
        return result

    @property
    def value(self) -> Any | None:
        """
        EN: Returns the primary semantic value (first identifier or literal) of the node.
        ES: Devuelve el valor semántico principal (primer identificador o literal) del nodo.
        """
        vals = self.values
        return vals[0] if vals else None

    @property
    def identifiers(self) -> list[str]:
        """
        EN: Returns the list of identifier names (Token.IDENT) in the node.
        ES: Devuelve la lista de nombres de identificadores (Token.IDENT) en el nodo.
        """
        return [
            str(t.value)
            for t in self.tokens
            if t.token == Token.IDENT
        ]

    @property
    def strings(self) -> list[str]:
        """
        EN: Returns the list of string literal values (Token.STRING) in the node.
        ES: Devuelve la lista de literales de cadena (Token.STRING) en el nodo.
        """
        return [str(t.value) for t in self.tokens if t.token == Token.STRING]

    @property
    def numbers(self) -> list[int | float]:
        """
        EN: Returns the list of numeric values (Token.NUMBER) in the node.
        ES: Devuelve la lista de valores numéricos (Token.NUMBER) en el nodo.
        """
        return [t.value for t in self.tokens if t.token == Token.NUMBER]

    @property
    def keywords(self) -> list[str]:
        """
        EN: Returns the list of reserved keywords (Token.KEYWORD) in the node.
        ES: Devuelve la lista de palabras reservadas (Token.KEYWORD) en el nodo.
        """
        return [str(t.value) for t in self.tokens if t.token == Token.KEYWORD]

    def set_level(self, new_level: int) -> None:
        """
        EN: Updates this node's level and recursively adjusts all child descendants.
        ES: Actualiza el nivel de este nodo y ajusta recursivamente el de sus descendientes.

        Args:
            new_level (int): New hierarchical indentation level assigned.
        """
        self.level = new_level
        for child in self.children:
            if child.level <= self.level:
                child.set_level(self.level + 1)

    def add_child(self, child: ASTNode) -> None:
        """
        EN: Adds a child node, sets this node as parent, and ensures child.level > parent.level.
        ES: Añade un nodo hijo a este bloque y establece este nodo como su padre.

        Args:
            child (ASTNode): Child node to incorporate into the block body.
        """
        child.parent = self
        if child.level <= self.level:
            child.set_level(self.level + 1)
        self.children.append(child)

    def remove_child(self, child: ASTNode) -> None:
        """
        EN: Removes a child node and detaches its parent reference.
        ES: Elimina un nodo hijo y desvincula la referencia a su padre.

        Args:
            child (ASTNode): Child node to detach from this block.
        """
        if child in self.children:
            self.children.remove(child)
            child.parent = None

    def by_level(self, level: int) -> list[ASTNode]:
        """
        EN: Searches and returns all descendant nodes at the specified hierarchy level.
        ES: Busca y retorna todos los nodos descendientes que pertenezcan al nivel indicado.

        Args:
            level (int): Hierarchical indentation level to match.

        Returns:
            list[ASTNode]: Collection of matching nodes.
        """
        found: list[ASTNode] = []
        if self.level == level:
            found.append(self)
        for child in self.children:
            found.extend(child.by_level(level))
        return found

    def find(self, rule_name: str) -> list[ASTNode]:
        """
        EN: Recursively searches all descendant nodes whose rule name matches rule_name.
        ES: Busca recursivamente todos los nodos descendientes cuyo nombre coincida con rule_name.

        Args:
            rule_name (str): Target rule name to search.

        Returns:
            list[ASTNode]: Matching nodes found.
        """
        found: list[ASTNode] = []
        if self.name == rule_name:
            found.append(self)
        for child in self.children:
            found.extend(child.find(rule_name))
        return found

    def find_first(self, rule_name: str) -> ASTNode | None:
        """
        EN: Finds the first descendant node matching the specified rule name.
        ES: Encuentra el primer nodo descendiente que coincida con el nombre de regla dado.

        Args:
            rule_name (str): Target rule name.

        Returns:
            ASTNode | None: First matching node, or None if not found.
        """
        if self.name == rule_name:
            return self
        for child in self.children:
            match = child.find_first(rule_name)
            if match is not None:
                return match
        return None

    def walk(
        self,
        level: int | str | None = None,
        order: str = "pre",
    ) -> Iterator[ASTNode]:
        """
        EN: Traverses the complete subtree rooted at this node.
        ES: Recorre el subárbol completo partiendo de este nodo.

        Args:
            level (int | None): If specified, only yields nodes at this exact level.
                               If a string is passed positionally, it is treated as
                               the legacy order argument.
            order (str): Traversal order ('pre' for pre-order, 'post' for post-order).

        Yields:
            ASTNode: Each visited node in the tree.
        """
        if isinstance(level, str):
            order = level
            level = None

        if order == "post":
            for child in self.children:
                yield from child.walk(level=level, order=order)
            if level is None or self.level == level:
                yield self
        else:
            if level is None or self.level == level:
                yield self
            for child in self.children:
                yield from child.walk(level=level, order=order)

    def to_dict(self) -> dict[str, Any]:
        """
        EN: Generates a JSON-serializable standard dictionary representation of the node.
        ES: Genera una representación jerárquica en diccionario estándar serializable.

        Returns:
            dict[str, Any]: Dictionary structure with name, code, level, values, tokens, and children.
        """
        return {
            "name": self.name,
            "code": self.code,
            "level": self.level,
            "is_block": self.is_block,
            "value": self.value,
            "values": self.values,
            "identifiers": self.identifiers,
            "strings": self.strings,
            "numbers": self.numbers,
            "keywords": self.keywords,
            "attributes": self.attributes,
            "tokens": [
                {
                    "token": getattr(getattr(t, "token", None), "name", str(getattr(t, "token", ""))),
                    "value": t.value,
                    "line": t.line,
                    "col": t.col,
                }
                for t in self.tokens
            ],
            "children": [child.to_dict() for child in self.children],
        }

    def format(
        self,
        indent: int = 0,
        prefix: str = "",
        is_last: bool = True,
        ascii_only: bool = False,
    ) -> str:
        """
        EN: Recursively formats the node and its children into a visual Unicode/ASCII tree.
        ES: Formatea el nodo y sus hijos recursivamente en una representación visual de árbol.

        Args:
            indent (int): Current indentation depth.
            prefix (str): Visual connection line prefix.
            is_last (bool): Whether this node is the last among its siblings.
            ascii_only (bool): If True, uses pure ASCII characters (+--, \\--, |). Defaults to False.

        Returns:
            str: Human-readable tree representation.
        """
        connector = ("\\-- " if is_last else "+-- ") if ascii_only else ("└── " if is_last else "├── ")
        block_tag = " [BLOCK]" if self.is_block else ""
        val_tag = f" -> values={self.values!r}" if self.values else ""
        line = f"{prefix}{connector}[L{self.level}] {self.name} (code={self.code}){block_tag}{val_tag}"

        child_prefix = prefix + ("    " if is_last else ("|   " if ascii_only else "│   "))
        children_lines: list[str] = []
        for i, child in enumerate(self.children):
            last = i == len(self.children) - 1
            children_lines.append(child.format(indent + 1, child_prefix, last, ascii_only=ascii_only))

        if children_lines:
            return line + "\n" + "\n".join(children_lines)
        return line

    def __iter__(self) -> Iterator[ASTNode]:
        """
        EN: Allows iterating directly over the child nodes of this block.
        ES: Permite iterar directamente sobre los hijos del nodo.
        """
        return iter(self.children)

    def __len__(self) -> int:
        """
        EN: Returns the total count of direct child nodes.
        ES: Devuelve la cantidad de nodos hijos directos.
        """
        return len(self.children)

    def __bool__(self) -> bool:
        """
        EN: An AST node always evaluates to True in boolean contexts.
        ES: Un nodo AST siempre se evalúa como True en contextos booleanos.
        """
        return True

    def __getitem__(self, item: int | str) -> Any:
        """
        EN: Access children by integer index, attributes by key, or find child by rule name.
        ES: Permite acceder a los hijos por índice entero o a atributos/hijos por nombre de cadena.
        """
        if isinstance(item, int):
            return self.children[item]
        if item in self.attributes:
            return self.attributes[item]
        child = self.find_first(item)
        if child is not None:
            return child
        raise KeyError(f"No se encontró el elemento '{item}' en {self.name}")

    def __repr__(self) -> str:
        vals_part = f", values={self.values!r}" if self.values else ""
        children_part = f", children={len(self.children)}" if self.children else ""
        return f"ASTNode(name={self.name!r}, level={self.level}{vals_part}{children_part})"

    @classmethod
    def from_rule_result(
        cls,
        rule: Any,
        result: Any,
        level: int = 0,
    ) -> Self:
        """
        EN: Factory method building an ASTNode from parser and combinator execution outputs.
        ES: Construye un ASTNode extrayendo automáticamente tokens y nodos hijos a partir del resultado de combinadores.

        Args:
            rule: RuleItem definition or rule class.
            result: Raw combinator output (token, list, ItemResult, or subnodes).
            level (int): Indentation level where the rule started.

        Returns:
            ASTNode: Fully structured and hierarchically linked AST node.
        """
        name = getattr(rule, "name", str(rule))
        code = getattr(rule, "code", 0)

        node = cls(
            name=name,
            rule=rule,
            code=code,
            level=level,
        )

        tokens: list[TokenType] = []
        children: list[ASTNode] = []

        def collect(item: Any) -> None:
            if item is None:
                return
            if isinstance(item, ASTNode):
                # Descartar nodos hijos vacíos (reglas opcionales no coincidentes)
                if not item.tokens and not item.children and not getattr(item, "is_block", False):
                    return
                children.append(item)
            elif isinstance(item, TokenType):
                tokens.append(item)
            elif getattr(item, "_is_item_result", False):
                # ItemResult: each Item() is converted to a grouped child ASTNode
                item_node = ASTNode(
                    name="ITEM",
                    rule=rule,
                    code=code,
                    level=level + 1,
                )
                item_tokens: list[TokenType] = []
                item_children: list[ASTNode] = []
                for sub in item:
                    if isinstance(sub, ASTNode):
                        item_children.append(sub)
                    elif isinstance(sub, TokenType):
                        item_tokens.append(sub)
                    elif getattr(sub, "_is_item_result", False):
                        collect(sub)
                    elif isinstance(sub, (list, tuple)):
                        for deep in sub:
                            collect(deep)
                item_node.tokens = item_tokens
                for child_node in item_children:
                    item_node.add_child(child_node)
                children.append(item_node)
            elif isinstance(item, (list, tuple)):
                for sub in item:
                    collect(sub)
            elif hasattr(item, "matched") and hasattr(item, "value"):
                if item.matched and item.value is not None:
                    collect(item.value)

        collect(result)

        node.tokens = tokens
        for child in children:
            node.add_child(child)

        return node


class ASTProgram:
    """
    EN:
        Root program node representing the completely parsed AST.
        Provides a structured interface to inspect code by indentation levels,
        access hierarchical blocks, and export formatted visual or JSON trees.

    ES:
        Nodo raíz que representa el programa analizado completo.
        Ofrece una interfaz estructurada para consultar el código por niveles de indentación,
        acceder a bloques jerárquicos y exportar árboles visuales o JSON.
    """

    def __init__(
        self,
        body: list[ASTNode] | None = None,
        comments: list[TokenType] | None = None,
    ) -> None:
        """
        EN: Initializes the AST program with root statements and extracted comments.
        ES: Inicializa el programa AST con sentencias raíz y comentarios extraídos.

        Args:
            body: Top-level program statement nodes.
            comments: Comment tokens extracted during parsing.
        """
        self.body: list[ASTNode] = body or []
        self.comments: list[TokenType] = comments or []

    @property
    def declarations(self) -> list[ASTNode]:
        """
        EN: Top-level level-0 statements of the program.
        ES: Declaraciones principales de nivel 0 del programa.
        """
        return self.body

    def prune_empty(self) -> ASTProgram:
        """
        EN: Recursively removes empty leaf nodes that contain no tokens, values, or children.
        ES: Elimina recursivamente nodos hoja vacíos que no contienen tokens, valores ni hijos.
        """
        def _prune(node: ASTNode) -> bool:
            node.children = [c for c in node.children if _prune(c)]
            return bool(node.tokens or node.children or getattr(node, "is_block", False))

        self.body = [n for n in self.body if _prune(n)]
        return self

    def by_level(self, level: int, recursive: bool = True) -> list[ASTNode]:
        """
        EN: Returns all nodes belonging exactly to the indicated indentation level.
        ES: Retorna todos los nodos que pertenezcan exactamente al nivel indicado.

        Args:
            level (int): Indentation level to query (0, 1, 2, ...).
            recursive (bool): If True, also searches inside nested block children. Defaults to True.

        Returns:
            list[ASTNode]: Nodes belonging to that level.
        """
        result: list[ASTNode] = []
        if recursive:
            for node in self.body:
                result.extend(node.by_level(level))
        else:
            result = [node for node in self.body if node.level == level]
        return result

    def levels(self) -> dict[int, list[ASTNode]]:
        """
        EN: Groups all AST nodes in a dictionary indexed by indentation level.
        ES: Agrupa todos los nodos del AST en un diccionario indexado por nivel de indentación.

        Returns:
            dict[int, list[ASTNode]]: Dictionary mapping level (int) to node lists.
        """
        grouped: dict[int, list[ASTNode]] = {}
        for node in self.walk():
            grouped.setdefault(node.level, []).append(node)
        return dict(sorted(grouped.items()))

    def blocks(self) -> list[ASTNode]:
        """
        EN: Filters and returns all AST nodes that constitute blocks (have children).
        ES: Filtra y devuelve todos los nodos del AST que constituyan bloques (tienen hijos).

        Returns:
            list[ASTNode]: List of nodes containing child blocks.
        """
        return [node for node in self.walk() if node.is_block]

    def find(self, rule_name: str) -> list[ASTNode]:
        """
        EN: Searches all nodes at any level in the program matching rule_name.
        ES: Busca todos los nodos en cualquier nivel del programa que coincidan con rule_name.

        Args:
            rule_name (str): Name of the rule to search for.

        Returns:
            list[ASTNode]: Collection of matching nodes.
        """
        result: list[ASTNode] = []
        for node in self.body:
            result.extend(node.find(rule_name))
        return result

    def find_first(self, rule_name: str) -> ASTNode | None:
        """
        EN: Finds the first node in the program matching the given rule name.
        ES: Encuentra el primer nodo en el programa que coincida con el nombre dado.

        Args:
            rule_name (str): Rule name to locate.

        Returns:
            ASTNode | None: First node found, or None if not present.
        """
        for node in self.body:
            match = node.find_first(rule_name)
            if match is not None:
                return match
        return None

    @property
    def total_nodes(self) -> int:
        """
        EN: Total count of nodes across the entire abstract syntax tree.
        ES: Cantidad total de nodos en todo el árbol sintáctico.
        """
        return len(list(self.walk()))

    @property
    def max_depth(self) -> int:
        """
        EN: Maximum indentation or hierarchy depth level reached in the program.
        ES: Nivel máximo de profundidad o indentación alcanzado en el programa.
        """
        lvls = self.levels()
        return max(lvls.keys()) if lvls else 0

    @property
    def stats(self) -> dict[str, Any]:
        """
        EN: Returns a statistical summary dictionary of the program dimensions.
        ES: Resumen estadístico de las dimensiones del programa.
        """
        return {
            "total_declarations": len(self.body),
            "total_nodes": self.total_nodes,
            "total_blocks": len(self.blocks()),
            "total_comments": len(self.comments),
            "max_depth": self.max_depth,
            "levels": list(self.levels().keys()),
        }

    def walk(
        self,
        level: int | str | None = None,
        order: str = "pre",
    ) -> Iterator[ASTNode]:
        """
        EN: Traverses all nodes in the complete program tree.
        ES: Recorre la totalidad de los nodos del árbol del programa.

        Args:
            level (int | None): If specified, yields only nodes at this exact level.
                               If a string is passed positionally, it is treated as
                               the legacy order argument.
            order (str): Traversal order ('pre' or 'post'). Defaults to 'pre'.

        Yields:
            ASTNode: Each visited node.
        """
        if isinstance(level, str):
            order = level
            level = None

        for node in self.body:
            yield from node.walk(level=level, order=order)

    def to_dict(self) -> dict[str, Any]:
        """
        EN: Generates a complete serializable dictionary representation of the program.
        ES: Genera un diccionario completo y serializable del programa y sus niveles.

        Returns:
            dict[str, Any]: Structured dictionary representation.
        """
        return {
            "type": "Program",
            "total_statements": len(self.body),
            "levels": {
                lvl: [n.name for n in nodes]
                for lvl, nodes in self.levels().items()
            },
            "body": [node.to_dict() for node in self.body],
            "comments": [
                {
                    "value": c.value,
                    "line": c.line,
                    "col": c.col,
                }
                for c in self.comments
            ],
        }

    def dump(self, ascii_only: bool | None = None) -> str:
        """
        EN: Returns a clear, formatted textual hierarchy dump of the entire syntax tree.
        ES: Devuelve una visualización formateada y clara del árbol sintáctico completo.

        Args:
            ascii_only (bool | None): If True, uses pure ASCII connectors (+--, \\--, |).
                                      If None, auto-detects console encoding capabilities.

        Returns:
            str: Tree representation with levels and statements.
        """
        if ascii_only is None:
            try:
                encoding = getattr(sys.stdout, "encoding", "utf-8") or "utf-8"
                "├──".encode(encoding)
                ascii_only = False
            except Exception:
                ascii_only = True

        lvls = list(self.levels().keys())
        header = f"<ASTProgram statements={len(self.body)}, levels={lvls}, comments={len(self.comments)}>:"
        if not self.body:
            return header + "\n    (vacío)"

        nodes_str: list[str] = []
        for i, node in enumerate(self.body):
            is_last = i == len(self.body) - 1
            nodes_str.append(node.format(indent=0, prefix="", is_last=is_last, ascii_only=ascii_only))

        return header + "\n" + "\n".join(nodes_str)

    def __iter__(self) -> Iterator[ASTNode]:
        """
        EN: Iterates directly over top-level root statements.
        ES: Permite iterar directamente sobre las sentencias de nivel superior.
        """
        return iter(self.body)

    def __len__(self) -> int:
        """
        EN: Total count of top-level root statements in the program.
        ES: Cantidad de sentencias principales del programa.
        """
        return len(self.body)

    def __bool__(self) -> bool:
        """
        EN: An ASTProgram always evaluates to True in boolean contexts.
        ES: Un programa AST siempre se evalúa como True en contextos booleanos.
        """
        return True

    def __getitem__(self, item: int | str) -> Any:
        """
        EN: Indexes program statements by integer position or searches by rule name string.
        ES: Permite indexar el programa por posición o buscar por nombre de regla.
        """
        if isinstance(item, int):
            return self.body[item]
        match = self.find_first(item)
        if match is not None:
            return match
        raise KeyError(f"No se encontró ninguna regla '{item}' en el programa")

    def __repr__(self) -> str:
        return (
            f"ASTProgram(statements={len(self.body)}, "
            f"blocks={len(self.blocks())}, "
            f"levels={list(self.levels().keys())})"
        )

    def generate_decorated_tree(self) -> str:
        """
        EN: Generates a richly decorated visual report of the entire AST,
            including level indicators, blocks, values, global statistics, and comments.
        ES: Genera una representación decorada del árbol AST completo, incluyendo
            indicadores visuales de nivel, bloques, valores, estadísticas globales y comentarios.

        Returns:
            str: Multi-line decorated tree formatted for text file or console output.
        """
        sep_double = "═" * 60
        sep_single = "─" * 60
        all_nodes = list(self.walk())
        blocks_list = self.blocks()
        lvls = list(self.levels().keys())

        lines: list[str] = [
            sep_double,
            "  ÁRBOL DE SINTAXIS ABSTRACTA (AST) - REPORTE DECORADO",
            sep_double,
            f"  • Sentencias raíz  : {len(self.body)}",
            f"  • Nodos totales    : {len(all_nodes)}",
            f"  • Bloques activos  : {len(blocks_list)}",
            f"  • Niveles de indent: {lvls}",
            f"  • Comentarios      : {len(self.comments)}",
            sep_single,
            f"<ASTProgram statements={len(self.body)}, levels={lvls}, comments={len(self.comments)}>:",
        ]

        if not self.body:
            lines.append("    (árbol vacío)")
        else:
            for i, node in enumerate(self.body):
                is_last = i == len(self.body) - 1
                lines.append(node.format(indent=0, prefix="", is_last=is_last))

        lines.extend([
            sep_single,
            "  DESGLOSE ESTRUCTURAL POR NIVELES Y BLOQUES",
            sep_single,
        ])

        for lvl in lvls:
            nodes_at_lvl = self.by_level(lvl)
            lines.append(f"  [Nivel {lvl}] ({len(nodes_at_lvl)} nodos):")
            for n in nodes_at_lvl:
                val_str = f" -> valores={n.values}" if n.values else ""
                lines.append(f"    • {n.name} (code={n.code}){val_str}")

        if blocks_list:
            lines.append("")
            lines.append("  BLOQUES JERÁRQUICOS:")
            for b in blocks_list:
                ident = repr(b.value) if b.value is not None else "None"
                lines.append(f"    └── Bloque [L{b.level}] {b.name} (identificador={ident}, hijos={len(b.children)}):")
                for ch in b.children:
                    val_str = f" -> valores={ch.values}" if ch.values else ""
                    lines.append(f"        └── [L{ch.level}] {ch.name} (code={ch.code}){val_str}")

        if self.comments:
            lines.append("")
            lines.append("  COMENTARIOS:")
            for c in self.comments:
                lines.append(f"    • L{c.line}:C{c.col} -> {c.value!r}")

        lines.append(sep_double)
        return "\n".join(lines)

    def generate_json_tree(self) -> dict[str, Any]:
        """
        EN: Serializes the AST structure into a hierarchical, metadata-rich JSON dictionary.
        ES: Serializa la estructura del AST en un formato JSON jerárquico y estructurado.

        Returns:
            dict[str, Any]: Complete JSON-compatible tree dictionary with metadata and node structure.
        """
        all_nodes = list(self.walk())
        blocks_list = self.blocks()
        lvls = list(self.levels().keys())

        return {
            "type": "ASTProgram",
            "version": "1.0",
            "metadata": {
                "total_statements": len(self.body),
                "total_nodes": len(all_nodes),
                "total_blocks": len(blocks_list),
                "levels": lvls,
                "comments_count": len(self.comments),
            },
            "levels_summary": {
                str(lvl): [
                    {
                        "name": n.name,
                        "code": n.code,
                        "level": n.level,
                        "values": n.values,
                    }
                    for n in self.by_level(lvl)
                ]
                for lvl in lvls
            },
            "body": [node.to_dict() for node in self.body],
            "comments": [
                {
                    "value": c.value,
                    "line": c.line,
                    "col": c.col,
                }
                for c in self.comments
            ],
        }

    def generate_file_tree(
        self,
        output_path: str | Path | None = None,
        encoding: str = "utf-8",
    ) -> str | dict[str, Any]:
        """
        EN: Generates and writes AST representation based on destination file extension:
            - If .txt (or None): generates the decorated visual tree report.
            - If .json: serializes and writes structured JSON.
        ES: Genera y procesa una representación del AST según la extensión del archivo destino:
            - Si es .txt (o None): genera el reporte de árbol decorado.
            - Si es .json: lo serializa y procesa en formato JSON estructurado.

        Args:
            output_path: Destination file path (.txt or .json).
            encoding (str): Target text encoding. Defaults to 'utf-8'.

        Returns:
            str | dict[str, Any]: Generated string content or structured dictionary.
        """
        if output_path is None:
            return self.generate_decorated_tree()

        path = Path(output_path)
        ext = path.suffix.lower()

        if ext == ".json":
            data = self.generate_json_tree()
            json_text = json.dumps(data, indent=2, ensure_ascii=False)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json_text, encoding=encoding)
            return data
        else:
            content = self.generate_decorated_tree()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding=encoding)
            return content


def generate_file_tree(
    target: ASTProgram | str | Path,
    output_path: str | Path | None = None,
    encoding: str = "utf-8",
) -> str | dict[str, Any]:
    """
    EN: Versatile utility function generating file tree reports from an ASTProgram instance or source path.
    ES: Función de utilidad versátil para generar el árbol de archivos a partir de un ASTProgram o ruta.

    Args:
        target: ASTProgram instance or path to source code.
        output_path: Destination file path (.txt or .json).
        encoding (str): File encoding. Defaults to 'utf-8'.

    Returns:
        str | dict[str, Any]: Generated text content or processed serialized data.
    """
    if isinstance(target, (str, Path)) and isinstance(output_path, ASTProgram):
        target, output_path = output_path, target

    if not isinstance(target, ASTProgram):
        raise TypeError(f"Se esperaba un ASTProgram, pero se recibió {type(target).__name__}")

    return target.generate_file_tree(output_path, encoding=encoding)


__all__ = [
    "Identifier",
    "ASTNode",
    "ASTProgram",
    "generate_file_tree",
]
