"""
Ahead-Of-Time (AOT) C Parser and AST Generator (`gram.core.parser.c_generator`).
================================================================================
Translates a Gram `Session` grammar graph and entrypoint into standalone,
deterministic, high-performance C translation units (`gram_ast.h`, `gram_ast.c`,
`gram_parser.h`, `gram_parser.c`, and a JSON manifest).

Architecture:
- Contiguous AST Node Arena with O(1) rollback on backtrack.
- Topologically resolved recursive-descent routines for every reachable `RuleItem`.
- Predictive C `switch` dispatch for `Alt` combinators (token kind + keyword first-char jump tables).
- Scoped compound statements for combinator evaluations without variable collisions.
- Strict semantic rejection of external or uncompilable combinators.
- Precedence climbing (Pratt) loops for `DualExpr`, `ArithmeticExpr`, `ConditionalExpr`.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from gram import errors
from gram.core.parser import c_driver
from gram.core.combinators.alternative import Alt
from gram.core.combinators.base import Combinator, RuleItem
from gram.core.combinators.enclosed import Enclosed
from gram.core.combinators.expressions import (
    ARITHMETIC_BINARY_OPS,
    ARITHMETIC_UNARY_OPS,
    CONDITIONAL_BINARY_OPS,
    CONDITIONAL_UNARY_OPS,
    DUAL_BINARY_OPS,
    DUAL_UNARY_OPS,
    ArithmeticExpr,
    BaseExpr,
    ConditionalExpr,
    DualExpr,
)
from gram.core.combinators.item import Item, Literal
from gram.core.combinators.kinds import (
    CombinatorKind,
    get_combinator_kind,
    is_compilable_combinator,
)
from gram.core.combinators.many import Many
from gram.core.combinators.match import (
    MatchGroup,
    MatchKeyword,
    MatchSeqSymbol,
    MatchToken,
)
from gram.core.combinators.negation import Not
from gram.core.combinators.optional import Opt
from gram.core.combinators.peek import Peek
from gram.core.combinators.reference import Ref
from gram.core.combinators.same_line import SameLine
from gram.core.combinators.separator import Separator
from gram.core.combinators.sequence import Seq
from gram.core.combinators.some import Some
from gram.core.lexer.tokens import Token

if TYPE_CHECKING:
    from gram.sessions import Session


C_PARSER_ABI_MAJOR = 1
C_PARSER_ABI_MINOR = 0
C_PARSER_ABI_VERSION = f"{C_PARSER_ABI_MAJOR}.{C_PARSER_ABI_MINOR}"


def _sanitize_c_ident(name: str) -> str:
    """Convert an arbitrary rule or symbol name into a valid C identifier."""
    cleaned = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    if cleaned and cleaned[0].isdigit():
        cleaned = f"_{cleaned}"
    return cleaned or "_unnamed"


class GrammarCompilerError(errors.GrammarError):
    """Raised when a grammar cannot be compiled into deterministic C."""


class CParserGenerator:
    """
    Traverses the grammar graph of a `Session` and generates complete,
    zero-dependency C99/C11 parser and AST compilation units.
    """

    def __init__(self, session: Session) -> None:
        self.session = session
        self.entrypoint = session.entrypoint
        if self.entrypoint is None:
            raise GrammarCompilerError(
                "MissingEntrypoint",
                errors.GRAMMAR_COMBINATOR_FAILED,
                f"Session '{session.name}' no tiene configurado un entrypoint.",
                "Asigne session.entrypoint antes de exportar el parser C.",
            )

        self.rules: list[type[RuleItem]] = []
        self.rule_ids: dict[type[RuleItem], int] = {}
        self.rule_names: dict[type[RuleItem], str] = {}
        self.expr_comb_ids: dict[int, int] = {}
        self.expr_combs: list[BaseExpr] = []
        self._visited_combs: set[int] = set()
        self.groups_used: set[str] = set()

    def crawl(self) -> None:
        """Crawl and validate the entire grammar graph starting from entrypoint."""
        if isinstance(self.entrypoint, type) and issubclass(self.entrypoint, RuleItem):
            self._register_rule(self.entrypoint)
        elif isinstance(self.entrypoint, Combinator):
            self._crawl_combinator(self.entrypoint, "entrypoint")
        else:
            raise GrammarCompilerError(
                "InvalidEntrypointType",
                errors.GRAMMAR_COMBINATOR_UNSUPPORTED,
                f"Tipo de entrypoint no soportado: {type(self.entrypoint).__name__}.",
                "El entrypoint debe ser una regla RuleItem o una instancia de Combinator.",
            )

        # Iteratively crawl rules until transitive closure is reached
        idx = 0
        while idx < len(self.rules):
            rule_cls = self.rules[idx]
            rule_comb = getattr(rule_cls, "rule", None) or getattr(rule_cls, "entrypoint", None)
            if rule_comb is not None:
                self._crawl_combinator(rule_comb, f"{rule_cls.__name__}.rule")
            for attr_name, attr_val in rule_cls.__dict__.items():
                if isinstance(attr_val, Combinator):
                    self._crawl_combinator(attr_val, f"{rule_cls.__name__}.{attr_name}")
            idx += 1

    def _register_rule(self, rule_cls: type[RuleItem]) -> int:
        if rule_cls in self.rule_ids:
            return self.rule_ids[rule_cls]
        rid = len(self.rules)
        self.rules.append(rule_cls)
        self.rule_ids[rule_cls] = rid
        self.rule_names[rule_cls] = _sanitize_c_ident(rule_cls.__name__)
        return rid

    def _crawl_combinator(self, comb: Combinator, context_path: str) -> None:
        if comb is None:
            return
        cid = id(comb)
        if cid in self._visited_combs:
            return
        self._visited_combs.add(cid)

        # 1. Strict semantic verification: reject external/uncompilable combinators
        if not is_compilable_combinator(comb):
            kind = get_combinator_kind(comb)
            raise GrammarCompilerError(
                "NonCompilableCombinator",
                errors.GRAMMAR_COMBINATOR_UNSUPPORTED,
                f"El combinador '{type(comb).__name__}' en '{context_path}' no está soportado para compilación en C "
                f"(kind={kind}).",
                "Utilice únicamente combinadores sintácticos estándar de Gram.",
            )

        if isinstance(comb, MatchGroup):
            self.groups_used.add(comb.group)

        # 2. Recursive graph exploration
        if isinstance(comb, Ref):
            target = comb.rule
            if isinstance(target, type) and issubclass(target, RuleItem):
                self._register_rule(target)
            elif isinstance(target, Combinator):
                self._crawl_combinator(target, f"{context_path}.Ref")
        elif isinstance(comb, (Seq, Alt, Item)):
            children = getattr(comb, "combinators", ()) or getattr(comb, "matchs", ())
            for i, child in enumerate(children):
                self._crawl_combinator(child, f"{context_path}[{i}]")
        elif isinstance(comb, (Opt, Many, Some, SameLine, Peek, Not)):
            child = getattr(comb, "combinator", None)
            if child is not None:
                self._crawl_combinator(child, f"{context_path}.{type(comb).__name__}")
        elif isinstance(comb, Enclosed):
            self._crawl_combinator(comb.content, f"{context_path}.Enclosed")
        elif isinstance(comb, Separator):
            for i, v in enumerate(comb.values):
                self._crawl_combinator(v, f"{context_path}.values[{i}]")
            self._crawl_combinator(comb.sep, f"{context_path}.sep")
        elif isinstance(comb, BaseExpr):
            if cid not in self.expr_comb_ids:
                eid = len(self.expr_combs)
                self.expr_comb_ids[cid] = eid
                self.expr_combs.append(comb)
            for i, r in enumerate(getattr(comb, "_ref_values", ())):
                self._crawl_combinator(r, f"{context_path}._ref_values[{i}]")

    def _get_group_keywords(self, grp_name: str) -> list[str]:
        try:
            grp = self.session.get_group(grp_name)
            if grp and hasattr(grp, "values"):
                return list(grp.values)
        except Exception:
            pass
        kws = []
        all_kws = getattr(self.session, "keywords", {})
        for kw, kw_obj in all_kws.items():
            g = getattr(kw_obj, "group", None)
            gname = getattr(g, "name", g) if g else None
            if gname == grp_name:
                kws.append(kw)
        return kws

    def generate_ast_header(self) -> str:
        """Generate `gram_ast.h` containing AST node definitions and arena interface."""
        lines = [
            "/* Auto-generated by Gram Framework. Do not edit manually. */",
            "#ifndef GRAM_AST_H",
            "#define GRAM_AST_H",
            "",
            "#include <stdint.h>",
            "#include <stddef.h>",
            "#include <stdbool.h>",
            "",
            "#ifdef __cplusplus",
            'extern "C" {',
            "#endif",
            "",
            "typedef enum {",
            "    GRAM_AST_NONE = 0,",
            "    GRAM_AST_TERMINAL_TOKEN,",
            "    GRAM_AST_TERMINAL_KEYWORD,",
            "    GRAM_AST_TERMINAL_GROUP,",
            "    GRAM_AST_TERMINAL_SYMBOL,",
            "    GRAM_AST_TERMINAL_LITERAL,",
            "    GRAM_AST_EXPR_BINARY,",
            "    GRAM_AST_EXPR_UNARY,",
            "    GRAM_AST_ARRAY,",
        ]

        # Rule node kinds
        for rule_cls in self.rules:
            rname = self.rule_names[rule_cls]
            lines.append(f"    GRAM_AST_RULE_{rname.upper()},")

        lines.extend([
            "} GramAstKind;",
            "",
            "typedef struct {",
            "    uint16_t kind;          /* GramAstKind */",
            "    uint16_t rule_id;       /* Numeric Rule ID (operator token kind for EXPR_* nodes) */",
            "    uint32_t token_start;   /* Initial token index in token stream */",
            "    uint32_t token_count;   /* Number of tokens covered */",
            "    uint32_t first_child;   /* 1-based index in arena (0 = none) */",
            "    uint32_t last_child;    /* 1-based index of the last child (O(1) append) */",
            "    uint32_t next_sibling;  /* 1-based index to next sibling (0 = none) */",
            "} GramAstNode;",
            "",
            "/* Undo record for one child attachment, replayed in reverse on parser rollback. */",
            "typedef struct {",
            "    uint32_t parent;",
            "    uint32_t prev_last;     /* Parent's last_child before the attachment */",
            "} GramAstUndo;",
            "",
            "typedef struct {",
            "    GramAstNode *nodes;     /* Contiguous node storage (1-indexed, node 0 unused) */",
            "    size_t count;           /* Number of active nodes allocated (count - 1 actual nodes) */",
            "    size_t capacity;        /* Total node capacity */",
            "    GramAstUndo *undo;      /* Attachment log enabling transactional rollback */",
            "    size_t undo_count;",
            "    size_t undo_capacity;",
            "} GramAstArena;",
            "",
            "bool gram_ast_arena_init(GramAstArena *arena, size_t initial_cap);",
            "void gram_ast_arena_reset(GramAstArena *arena);",
            "void gram_ast_arena_free(GramAstArena *arena);",
            "uint32_t gram_ast_arena_alloc(GramAstArena *arena, uint16_t kind, uint16_t rule_id, uint32_t tok_start);",
            "void gram_ast_add_child(GramAstArena *arena, uint32_t parent_idx, uint32_t child_idx);",
            "const char* gram_ast_kind_name(GramAstKind kind);",
            "",
            "#ifdef __cplusplus",
            "}",
            "#endif",
            "",
            "#endif /* GRAM_AST_H */",
            "",
        ])
        return "\n".join(lines)

    def generate_ast_source(self) -> str:
        """Generate `gram_ast.c` implementing arena management."""
        lines = [
            '/* Auto-generated by Gram Framework. Do not edit manually. */',
            '#include "gram_ast.h"',
            '#include <stdlib.h>',
            '#include <string.h>',
            '',
            'bool gram_ast_arena_init(GramAstArena *arena, size_t initial_cap) {',
            '    if (!arena) return false;',
            '    if (initial_cap < 16) initial_cap = 1024;',
            '    arena->nodes = (GramAstNode*)malloc(initial_cap * sizeof(GramAstNode));',
            '    arena->undo_capacity = 256;',
            '    arena->undo = (GramAstUndo*)malloc(arena->undo_capacity * sizeof(GramAstUndo));',
            '    if (!arena->nodes || !arena->undo) {',
            '        free(arena->nodes);',
            '        free(arena->undo);',
            '        arena->nodes = NULL;',
            '        arena->undo = NULL;',
            '        arena->count = 0;',
            '        arena->capacity = 0;',
            '        arena->undo_count = 0;',
            '        arena->undo_capacity = 0;',
            '        return false;',
            '    }',
            '    arena->capacity = initial_cap;',
            '    arena->count = 1; /* Index 0 is reserved as null/sentinel */',
            '    arena->undo_count = 0;',
            '    memset(&arena->nodes[0], 0, sizeof(GramAstNode));',
            '    return true;',
            '}',
            '',
            'void gram_ast_arena_reset(GramAstArena *arena) {',
            '    if (!arena || !arena->nodes) return;',
            '    arena->count = 1;',
            '    arena->undo_count = 0;',
            '}',
            '',
            'void gram_ast_arena_free(GramAstArena *arena) {',
            '    if (!arena) return;',
            '    free(arena->nodes);',
            '    free(arena->undo);',
            '    arena->nodes = NULL;',
            '    arena->undo = NULL;',
            '    arena->count = 0;',
            '    arena->capacity = 0;',
            '    arena->undo_count = 0;',
            '    arena->undo_capacity = 0;',
            '}',
            '',
            'uint32_t gram_ast_arena_alloc(GramAstArena *arena, uint16_t kind, uint16_t rule_id, uint32_t tok_start) {',
            '    if (!arena || !arena->nodes) return 0;',
            '    if (arena->count >= arena->capacity) {',
            '        size_t new_cap = arena->capacity * 2;',
            '        GramAstNode *new_nodes = (GramAstNode*)realloc(arena->nodes, new_cap * sizeof(GramAstNode));',
            '        if (!new_nodes) return 0;',
            '        arena->nodes = new_nodes;',
            '        arena->capacity = new_cap;',
            '    }',
            '    uint32_t idx = (uint32_t)arena->count++;',
            '    GramAstNode *node = &arena->nodes[idx];',
            '    node->kind = kind;',
            '    node->rule_id = rule_id;',
            '    node->token_start = tok_start;',
            '    node->token_count = 0;',
            '    node->first_child = 0;',
            '    node->last_child = 0;',
            '    node->next_sibling = 0;',
            '    return idx;',
            '}',
            '',
            '/* O(1) append. Every attachment is logged so gram_parser_restore can unlink it exactly. */',
            'void gram_ast_add_child(GramAstArena *arena, uint32_t parent_idx, uint32_t child_idx) {',
            '    if (!arena || !parent_idx || !child_idx || parent_idx == child_idx) return;',
            '    if (parent_idx >= arena->count || child_idx >= arena->count) return;',
            '    if (arena->nodes[parent_idx].last_child == child_idx) return;',
            '    if (arena->undo_count == arena->undo_capacity) {',
            '        size_t new_cap = arena->undo_capacity * 2;',
            '        GramAstUndo *grown = (GramAstUndo*)realloc(arena->undo, new_cap * sizeof(GramAstUndo));',
            '        if (!grown) return;',
            '        arena->undo = grown;',
            '        arena->undo_capacity = new_cap;',
            '    }',
            '    GramAstNode *parent = &arena->nodes[parent_idx];',
            '    arena->undo[arena->undo_count].parent = parent_idx;',
            '    arena->undo[arena->undo_count].prev_last = parent->last_child;',
            '    arena->undo_count++;',
            '    if (parent->last_child == 0) {',
            '        parent->first_child = child_idx;',
            '    } else {',
            '        arena->nodes[parent->last_child].next_sibling = child_idx;',
            '    }',
            '    parent->last_child = child_idx;',
            '    arena->nodes[child_idx].next_sibling = 0;',
            '}',
            '',
            'const char* gram_ast_kind_name(GramAstKind kind) {',
            '    switch (kind) {',
            '        case GRAM_AST_NONE: return "NONE";',
            '        case GRAM_AST_TERMINAL_TOKEN: return "TERMINAL_TOKEN";',
            '        case GRAM_AST_TERMINAL_KEYWORD: return "TERMINAL_KEYWORD";',
            '        case GRAM_AST_TERMINAL_GROUP: return "TERMINAL_GROUP";',
            '        case GRAM_AST_TERMINAL_SYMBOL: return "TERMINAL_SYMBOL";',
            '        case GRAM_AST_TERMINAL_LITERAL: return "TERMINAL_LITERAL";',
            '        case GRAM_AST_EXPR_BINARY: return "EXPR_BINARY";',
            '        case GRAM_AST_EXPR_UNARY: return "EXPR_UNARY";',
            '        case GRAM_AST_ARRAY: return "ARRAY";',
        ]

        for rule_cls in self.rules:
            rname = self.rule_names[rule_cls]
            lines.append(f'        case GRAM_AST_RULE_{rname.upper()}: return "{rname}";')

        lines.extend([
            '        default: return "UNKNOWN";',
            '    }',
            '}',
            '',
        ])
        return "\n".join(lines)

    def generate_parser_header(self) -> str:
        """Generate `gram_parser.h` declaring parser state and entrypoints."""
        lines = [
            "/* Auto-generated by Gram Framework. Do not edit manually. */",
            "#ifndef GRAM_PARSER_H",
            "#define GRAM_PARSER_H",
            "",
            '#include "gram_lexer.h"',
            '#include "gram_ast.h"',
            '#include "gram_diagnostics_lite.h"',
            "",
            "#ifdef __cplusplus",
            'extern "C" {',
            "#endif",
            "",
            "typedef struct {",
            "    const GramToken *tokens;",
            "    size_t token_count;",
            "    size_t cursor;",
            "    size_t farthest;        /* Farthest cursor reached before any rollback (error reporting) */",
            "    uint32_t bracket_depth;",
            "    const char *source;",
            "    size_t source_len;",
            "    GramAstArena *arena;",
            "    GramDiagSink diag;",
            "} GramParser;",
            "",
            "typedef struct {",
            "    size_t cursor;",
            "    size_t arena_count;",
            "    size_t undo_count;",
            "    uint32_t bracket_depth;",
            "} GramParserCheckpoint;",
            "",
            "static inline GramParserCheckpoint gram_parser_save(const GramParser *p) {",
            "    GramParserCheckpoint cp;",
            "    cp.cursor = p->cursor;",
            "    cp.arena_count = p->arena ? p->arena->count : 0;",
            "    cp.undo_count = p->arena ? p->arena->undo_count : 0;",
            "    cp.bracket_depth = p->bracket_depth;",
            "    return cp;",
            "}",
            "",
            "static inline void gram_parser_restore(GramParser *p, GramParserCheckpoint cp) {",
            "    if (p->cursor > p->farthest) p->farthest = p->cursor;",
            "    p->cursor = cp.cursor;",
            "    p->bracket_depth = cp.bracket_depth;",
            "    if (p->arena) {",
            "        GramAstArena *a = p->arena;",
            "        while (a->undo_count > cp.undo_count) {",
            "            GramAstUndo u = a->undo[--a->undo_count];",
            "            GramAstNode *pn = &a->nodes[u.parent];",
            "            if (u.prev_last == 0) pn->first_child = 0; else a->nodes[u.prev_last].next_sibling = 0;",
            "            pn->last_child = u.prev_last;",
            "        }",
            "        if (a->count > cp.arena_count) a->count = cp.arena_count;",
            "    }",
            "}",
            "",
            "void gram_parser_init(GramParser *p, const GramToken *tokens, size_t count, const char *source, size_t source_len, GramAstArena *arena, GramDiagSink diag);",
            "bool gram_parse_entrypoint(GramParser *p, uint32_t *out_root);",
            "",
        ]

        # Rule prototypes
        for rule_cls in self.rules:
            rname = self.rule_names[rule_cls]
            lines.append(f"bool gram_parse_rule_{rname}(GramParser *p, uint32_t *out_node);")

        lines.extend([
            "",
            "#ifdef __cplusplus",
            "}",
            "#endif",
            "",
            "#endif /* GRAM_PARSER_H */",
            "",
        ])
        return "\n".join(lines)

    def generate_parser_source(self) -> str:
        """Generate `gram_parser.c` containing complete parsing logic."""
        lines = [
            '/* Auto-generated by Gram Framework. Do not edit manually. */',
            '#include "gram_parser.h"',
            '#include "gram_lexer_tokens.h"',
            '#include <string.h>',
            '#include <stdlib.h>',
            '',
            'void gram_parser_init(GramParser *p, const GramToken *tokens, size_t count, const char *source, size_t source_len, GramAstArena *arena, GramDiagSink diag) {',
            '    p->tokens = tokens;',
            '    p->token_count = count;',
            '    p->cursor = 0;',
            '    p->farthest = 0;',
            '    p->bracket_depth = 0;',
            '    p->source = source;',
            '    p->source_len = source_len;',
            '    p->arena = arena;',
            '    p->diag = diag;',
            '}',
            '',
            'static inline void gram_parser_skip_whitespace(GramParser *p) {',
            '    while (p->cursor < p->token_count) {',
            '        uint32_t k = p->tokens[p->cursor].kind;',
            '        if (k == GRAM_TOKEN_COMMENT) {',
            '            p->cursor++;',
            '        } else if (p->bracket_depth > 0 && (k == GRAM_TOKEN_NEWLINE || k == GRAM_TOKEN_INDENT || k == GRAM_TOKEN_DEDENT)) {',
            '            p->cursor++;',
            '        } else {',
            '            break;',
            '        }',
            '    }',
            '}',
            '',
            'static inline const GramToken* gram_parser_peek(GramParser *p) {',
            '    gram_parser_skip_whitespace(p);',
            '    if (p->cursor < p->token_count) {',
            '        return &p->tokens[p->cursor];',
            '    }',
            '    return NULL;',
            '}',
            '',
            'static inline bool gram_match_token_kind(GramParser *p, uint32_t expected_kind, uint32_t *out_node) {',
            '    gram_parser_skip_whitespace(p);',
            '    if (p->cursor < p->token_count && p->tokens[p->cursor].kind == expected_kind) {',
            '        uint32_t tok_idx = (uint32_t)p->cursor++;',
            '        if (out_node && p->arena) {',
            '            uint32_t n = gram_ast_arena_alloc(p->arena, GRAM_AST_TERMINAL_TOKEN, 0, tok_idx);',
            '            if (n) {',
            '                p->arena->nodes[n].token_count = 1;',
            '                *out_node = n;',
            '            }',
            '        }',
            '        return true;',
            '    }',
            '    return false;',
            '}',
            '',
            'static inline bool gram_match_keyword_str(GramParser *p, const char *kw, size_t kw_len, uint32_t *out_node) {',
            '    gram_parser_skip_whitespace(p);',
            '    if (p->cursor < p->token_count && p->tokens[p->cursor].kind == GRAM_TOKEN_KEYWORD) {',
            '        const GramToken *tok = &p->tokens[p->cursor];',
            '        if (tok->length == kw_len && memcmp(p->source + tok->start, kw, kw_len) == 0) {',
            '            uint32_t tok_idx = (uint32_t)p->cursor++;',
            '            if (out_node && p->arena) {',
            '                uint32_t n = gram_ast_arena_alloc(p->arena, GRAM_AST_TERMINAL_KEYWORD, 0, tok_idx);',
            '                if (n) {',
            '                    p->arena->nodes[n].token_count = 1;',
            '                    *out_node = n;',
            '                }',
            '            }',
            '            return true;',
            '        }',
            '    }',
            '    return false;',
            '}',
            '',
            'static inline bool gram_match_symbol_str(GramParser *p, const char *sym, size_t sym_len, uint32_t *out_node) {',
            '    gram_parser_skip_whitespace(p);',
            '    if (p->cursor < p->token_count) {',
            '        const GramToken *tok = &p->tokens[p->cursor];',
            '        if (tok->length == sym_len && memcmp(p->source + tok->start, sym, sym_len) == 0) {',
            '            uint32_t tok_idx = (uint32_t)p->cursor++;',
            '            if (out_node && p->arena) {',
            '                uint32_t n = gram_ast_arena_alloc(p->arena, GRAM_AST_TERMINAL_SYMBOL, 0, tok_idx);',
            '                if (n) {',
            '                    p->arena->nodes[n].token_count = 1;',
            '                    *out_node = n;',
            '                }',
            '            }',
            '            return true;',
            '        }',
            '    }',
            '    return false;',
            '}',
            '',
            '/* Forward declarations and matching routines for keyword groups */',
        ]

        for grp_name in sorted(self.groups_used):
            gident = _sanitize_c_ident(grp_name)
            kws = self._get_group_keywords(grp_name)
            lines.append(f"static inline bool gram_match_group_{gident}(GramParser *p, uint32_t *out_node) {{")
            lines.append("    gram_parser_skip_whitespace(p);")
            lines.append("    if (p->cursor >= p->token_count) return false;")
            lines.append("    const GramToken *tok = &p->tokens[p->cursor];")
            lines.append("    if (tok->kind != GRAM_TOKEN_KEYWORD) return false;")
            lines.append("    const char *kw = p->source + tok->start;")
            lines.append("    size_t len = tok->length;")
            lines.append("    bool matched = false;")
            for kw in kws:
                lines.append(f'    if (!matched && len == {len(kw)}u && memcmp(kw, "{kw}", {len(kw)}u) == 0) matched = true;')
            lines.append("    if (matched) {")
            lines.append("        uint32_t tok_idx = (uint32_t)p->cursor++;")
            lines.append("        if (out_node && p->arena) {")
            lines.append("            uint32_t n = gram_ast_arena_alloc(p->arena, GRAM_AST_TERMINAL_GROUP, 0, tok_idx);")
            lines.append("            if (n) { p->arena->nodes[n].token_count = 1; *out_node = n; }")
            lines.append("        }")
            lines.append("        return true;")
            lines.append("    }")
            lines.append("    return false;")
            lines.append("}")
            lines.append("")

        for eid, _ in enumerate(self.expr_combs):
            lines.append(f"static bool gram_parse_expr_{eid}(GramParser *p, int min_bp, uint32_t *out_node);")

        lines.append("")

        # Generate rule functions
        for rule_cls in self.rules:
            rname = self.rule_names[rule_cls]
            rid = self.rule_ids[rule_cls]
            nodeable = getattr(rule_cls, "nodeable", True)
            rule_comb = getattr(rule_cls, "rule", None) or getattr(rule_cls, "entrypoint", None)

            lines.append(f"bool gram_parse_rule_{rname}(GramParser *p, uint32_t *out_node) {{")
            lines.append("    GramParserCheckpoint cp = gram_parser_save(p);")
            if nodeable:
                # NOTA: se salta el espacio ignorable antes de fijar token_start para que
                # el span del nodo (y el IR) empiece en el primer token real de la regla.
                lines.append("    gram_parser_skip_whitespace(p);")
                lines.append("    uint32_t start_tok = (uint32_t)p->cursor;")
            lines.append("    bool ok = true;")
            if nodeable:
                lines.append(f"    uint32_t rule_ast = gram_ast_arena_alloc(p->arena, GRAM_AST_RULE_{rname.upper()}, {rid}, start_tok);")
                lines.append("    uint32_t *child_target = &rule_ast;")
            else:
                lines.append("    uint32_t *child_target = out_node;")
            lines.append("    (void)child_target;")

            if rule_comb is not None:
                comb_code = self._compile_combinator(rule_comb, "child_target", 1)
                lines.append(comb_code)

            lines.append("    if (!ok) {")
            lines.append("        gram_parser_restore(p, cp);")
            lines.append("        return false;")
            lines.append("    }")
            if nodeable:
                lines.append("    if (rule_ast && p->arena) {")
                lines.append("        p->arena->nodes[rule_ast].token_count = (uint32_t)(p->cursor - start_tok);")
                lines.append("        if (out_node) *out_node = rule_ast;")
                lines.append("    }")
            lines.append("    return true;")
            lines.append("}")
            lines.append("")

        # Generate Pratt expression loops
        for eid, expr_comb in enumerate(self.expr_combs):
            lines.append(self._generate_pratt_expression_function(eid, expr_comb))

        # Generate entrypoint function
        lines.append("bool gram_parse_entrypoint(GramParser *p, uint32_t *out_root) {")
        lines.append("    if (!p) return false;")
        lines.append("    uint32_t root_node = 0;")
        lines.append("    if (p->arena) {")
        lines.append("        root_node = gram_ast_arena_alloc(p->arena, GRAM_AST_ARRAY, 0, 0);")
        lines.append("    }")

        mode = getattr(self.session, "mode", "Single")
        entry_target = self.entrypoint
        if isinstance(entry_target, type) and issubclass(entry_target, RuleItem):
            # NOTA: un entrypoint `nodeable = False` inserta sus hijos directamente en la raíz.
            entry_out = "&item_node" if getattr(entry_target, "nodeable", True) else "&root_node"
            call_code = f"gram_parse_rule_{self.rule_names[entry_target]}(p, {entry_out})"
        else:
            call_code = self._compile_combinator_as_expr(entry_target, "&item_node")

        if mode == "Many":
            lines.extend([
                "    while (p->cursor < p->token_count) {",
                "        const GramToken *tok = gram_parser_peek(p);",
                "        if (!tok || tok->kind == GRAM_TOKEN_EOF) break;",
                "        GramParserCheckpoint cp = gram_parser_save(p);",
                "        size_t prev_cursor = p->cursor;",
                "        uint32_t item_node = 0;",
                f"        if (!({call_code}) || p->cursor == prev_cursor) {{",
                "            gram_parser_restore(p, cp);",
                "            break;",
                "        }",
                "        if (item_node && root_node && p->arena) {",
                "            gram_ast_add_child(p->arena, root_node, item_node);",
                "        }",
                "    }",
            ])
        else:
            lines.extend([
                "    uint32_t item_node = 0;",
                f"    if (!({call_code})) return false;",
                "    if (item_node && root_node && p->arena) {",
                "        gram_ast_add_child(p->arena, root_node, item_node);",
                "    }",
            ])

        lines.extend([
            "    if (root_node && p->arena) p->arena->nodes[root_node].token_count = (uint32_t)p->cursor;",
            "    if (out_root) *out_root = root_node;",
            "    return true;",
            "}",
            "",
        ])
        return "\n".join(lines)

    def _compute_first_set(
        self,
        comb: Combinator,
        visited_rules: frozenset[type[RuleItem]] = frozenset(),
    ) -> tuple[bool, set[str] | None, set[str] | None]:
        """
        Compute static first-set profile `(nullable, token_kinds, keyword_set)` for `comb`.

        - `nullable`: True if `comb` can succeed without consuming any token.
        - `token_kinds`: Set of `Token.name` strings that the first consumed token can be,
          or `None` if unknown/unbounded.
        - `keyword_set`: When `"KEYWORD"` is in `token_kinds`, the set of exact keyword
          strings that can start `comb` as a `KEYWORD`, or `None` if arbitrary keywords
          are possible.
        """
        if isinstance(comb, MatchToken):
            tok = getattr(comb, "token", None)
            tname = tok.name if isinstance(tok, Token) else str(tok)
            return (False, {tname}, None if tname == "KEYWORD" else set())

        if isinstance(comb, MatchKeyword):
            return (False, {"KEYWORD"}, {comb.keyword})

        if isinstance(comb, MatchGroup):
            kws = set(self._get_group_keywords(comb.group))
            return (False, {"KEYWORD"}, kws if kws else None)

        if isinstance(comb, Enclosed):
            ot = getattr(comb, "open_token", getattr(comb, "open", None))
            open_tok = ot.name if isinstance(ot, Token) else str(ot)
            return (False, {open_tok}, None if open_tok == "KEYWORD" else set())

        if isinstance(comb, (SameLine, Some)):
            return self._compute_first_set(comb.combinator, visited_rules)

        if isinstance(comb, (Opt, Many)):
            _, c_toks, c_kws = self._compute_first_set(comb.combinator, visited_rules)
            return (True, c_toks, c_kws)

        if isinstance(comb, Separator):
            val_comb = comb.values[0] if len(comb.values) == 1 else Alt(*comb.values)
            v_null, v_toks, v_kws = self._compute_first_set(val_comb, visited_rules)
            return ((comb.min <= 0) or v_null, v_toks, v_kws)

        if isinstance(comb, (Seq, Item)):
            children = getattr(comb, "combinators", ()) or getattr(comb, "matchs", ())
            acc_toks: set[str] = set()
            acc_kws: set[str] | None = set()
            all_nullable = True
            for child in children:
                c_null, c_toks, c_kws = self._compute_first_set(child, visited_rules)
                if c_toks is None:
                    return (False, None, None)
                acc_toks |= c_toks
                if "KEYWORD" in c_toks:
                    if c_kws is None or acc_kws is None:
                        acc_kws = None
                    else:
                        acc_kws |= c_kws
                if not c_null:
                    all_nullable = False
                    break
            return (all_nullable, acc_toks, acc_kws)

        if isinstance(comb, Alt):
            children = getattr(comb, "combinators", ())
            acc_toks = set()
            acc_kws = set()
            any_nullable = False
            for child in children:
                c_null, c_toks, c_kws = self._compute_first_set(child, visited_rules)
                if c_null:
                    any_nullable = True
                if c_toks is None:
                    return (any_nullable, None, None)
                acc_toks |= c_toks
                if "KEYWORD" in c_toks:
                    if c_kws is None or acc_kws is None:
                        acc_kws = None
                    else:
                        acc_kws |= c_kws
            return (any_nullable, acc_toks, acc_kws)

        if isinstance(comb, Ref):
            target = comb.rule
            if not (isinstance(target, type) and issubclass(target, RuleItem)):
                return (True, None, None)
            if target in visited_rules:
                return (True, None, None)
            rule_comb = getattr(target, "rule", None) or getattr(target, "entrypoint", None)
            if rule_comb is None:
                return (True, None, None)
            return self._compute_first_set(rule_comb, visited_rules | {target})

        if isinstance(comb, BaseExpr):
            acc_toks = {"LPAREN"}
            acc_kws = set()
            for t in getattr(comb, "unary_ops", {}):
                if isinstance(t, Token):
                    acc_toks.add(t.name)
            for t in getattr(comb, "_token_values", ()):
                if isinstance(t, Token):
                    acc_toks.add(t.name)
            for r in getattr(comb, "_ref_values", ()):
                _, r_toks, r_kws = self._compute_first_set(r, visited_rules)
                if r_toks is None:
                    return (False, None, None)
                acc_toks |= r_toks
                if "KEYWORD" in r_toks:
                    if r_kws is None or acc_kws is None:
                        acc_kws = None
                    else:
                        acc_kws |= r_kws
            return (False, acc_toks, acc_kws)

        return (True, None, None)

    def _emit_alt_branch_trials(
        self,
        children: tuple[Combinator, ...],
        cand_indices: list[int] | tuple[int, ...],
        parent_node_var: str,
        indent: int,
    ) -> str:
        """Emit PEG ordered-choice branch trial blocks for a subset of `Alt` branch indices."""
        pfx = "    " * indent
        out: list[str] = []
        for idx in cand_indices:
            child = children[idx]
            out.append(f"{pfx}if (!ok) {{")
            out.append(f"{pfx}    GramParserCheckpoint alt_cp_{indent}_{idx} = gram_parser_save(p);")
            out.append(self._compile_combinator(child, parent_node_var, indent + 1))
            out.append(f"{pfx}    if (!ok) gram_parser_restore(p, alt_cp_{indent}_{idx});")
            out.append(f"{pfx}}}")
        return "\n".join(out)

    def _compile_alt_optimized(
        self,
        comb: Alt,
        parent_node_var: str,
        indent: int,
    ) -> str:
        """Compile an `Alt` combinator using predictive C `switch` dispatch when branches partition by lookahead."""
        pfx = "    " * indent
        children = tuple(getattr(comb, "combinators", ()))
        if not children:
            return f"{pfx}ok = false;"

        profiles = [self._compute_first_set(c) for c in children]
        all_indices = list(range(len(children)))

        # Only use predictive switch when >= 2 branches, none is nullable, and at least one has known first tokens
        can_switch = (
            len(children) >= 2
            and all(not p[0] for p in profiles)
            and any(p[1] is not None for p in profiles)
        )

        if not can_switch:
            return f"{pfx}ok = false;\n" + self._emit_alt_branch_trials(
                children, all_indices, parent_node_var, indent
            )

        opaque_indices = [i for i, (_, b_toks, _) in enumerate(profiles) if b_toks is None]
        known_tokens: set[str] = set()
        for _, b_toks, _ in profiles:
            if b_toks is not None:
                known_tokens |= b_toks

        token_to_cands: dict[str, tuple[int, ...]] = {}
        for tname in sorted(known_tokens):
            cands = [
                i
                for i, (_, b_toks, _) in enumerate(profiles)
                if b_toks is None or tname in b_toks
            ]
            token_to_cands[tname] = tuple(cands)

        # Check if KEYWORD case can be further partitioned by first character
        kw_cands = token_to_cands.get("KEYWORD", ())
        kw_char_groups: dict[tuple[int, ...], list[str]] = {}
        opaque_kw_cands: tuple[int, ...] = ()
        use_kw_char_switch = False

        if len(kw_cands) >= 2 and any(profiles[i][2] is not None for i in kw_cands):
            opaque_kw_cands = tuple(
                i for i in kw_cands if profiles[i][1] is None or profiles[i][2] is None
            )
            first_chars = sorted(
                {
                    kw[0]
                    for i in kw_cands
                    if profiles[i][2] is not None
                    for kw in (profiles[i][2] or ())
                    if kw
                }
            )
            char_to_cands: dict[str, tuple[int, ...]] = {}
            for ch in first_chars:
                ch_cands = tuple(
                    i
                    for i in kw_cands
                    if i in opaque_kw_cands
                    or any(kw.startswith(ch) for kw in (profiles[i][2] or ()))
                )
                char_to_cands[ch] = ch_cands

            if any(len(c) < len(kw_cands) for c in char_to_cands.values()):
                use_kw_char_switch = True
                for ch, cands in char_to_cands.items():
                    kw_char_groups.setdefault(cands, []).append(ch)

        # Verify that switching actually narrows branches or dispatches across multiple token kinds
        narrows_any = (
            len(known_tokens) >= 2
            or any(len(c) < len(children) for c in token_to_cands.values())
            or use_kw_char_switch
        )
        if not narrows_any:
            return f"{pfx}ok = false;\n" + self._emit_alt_branch_trials(
                children, all_indices, parent_node_var, indent
            )

        # Group non-KEYWORD (or non-char-switched KEYWORD) tokens by identical candidate tuple
        cands_to_tokens: dict[tuple[int, ...], list[str]] = {}
        for tname, cands in token_to_cands.items():
            if tname == "KEYWORD" and use_kw_char_switch:
                continue
            cands_to_tokens.setdefault(cands, []).append(tname)

        lines = [
            f"{pfx}ok = false;",
            f"{pfx}{{",
            f"{pfx}    const GramToken *alt_tok_{indent} = gram_parser_peek(p);",
            f"{pfx}    if (alt_tok_{indent}) {{",
            f"{pfx}        switch (alt_tok_{indent}->kind) {{",
        ]

        for cands, tnames in cands_to_tokens.items():
            for tname in tnames:
                lines.append(f"{pfx}            case GRAM_TOKEN_{tname}:")
            lines.append(
                self._emit_alt_branch_trials(children, cands, parent_node_var, indent + 4)
            )
            lines.append(f"{pfx}                break;")

        if "KEYWORD" in token_to_cands and use_kw_char_switch:
            lines.append(f"{pfx}            case GRAM_TOKEN_KEYWORD:")
            lines.append(f"{pfx}                if (alt_tok_{indent}->length > 0) {{")
            lines.append(f"{pfx}                    switch (p->source[alt_tok_{indent}->start]) {{")
            for ch_cands, chars in kw_char_groups.items():
                for ch in chars:
                    escaped_ch = f"\\{ch}" if ch in ("'", "\\") else ch
                    lines.append(f"{pfx}                        case '{escaped_ch}':")
                lines.append(
                    self._emit_alt_branch_trials(
                        children, ch_cands, parent_node_var, indent + 7
                    )
                )
                lines.append(f"{pfx}                            break;")
            lines.append(f"{pfx}                        default:")
            if opaque_kw_cands:
                lines.append(
                    self._emit_alt_branch_trials(
                        children, opaque_kw_cands, parent_node_var, indent + 7
                    )
                )
            lines.append(f"{pfx}                            break;")
            lines.append(f"{pfx}                    }}")
            lines.append(f"{pfx}                }}")
            lines.append(f"{pfx}                break;")

        lines.append(f"{pfx}            default:")
        if opaque_indices:
            lines.append(
                self._emit_alt_branch_trials(
                    children, opaque_indices, parent_node_var, indent + 4
                )
            )
        lines.append(f"{pfx}                break;")
        lines.append(f"{pfx}        }}")
        lines.append(f"{pfx}    }}")
        lines.append(f"{pfx}}}")
        return "\n".join(lines)

    def _compile_combinator_as_expr(self, comb: Combinator, out_node_expr: str) -> str:
        """Compile a combinator evaluation into a single boolean C expression where possible."""
        if isinstance(comb, MatchToken):
            tok = getattr(comb, "token", None)
            tname = tok.name if isinstance(tok, Token) else str(tok)
            return f"gram_match_token_kind(p, GRAM_TOKEN_{tname}, {out_node_expr})"
        if isinstance(comb, MatchKeyword):
            kw = comb.keyword
            return f'gram_match_keyword_str(p, "{kw}", {len(kw)}u, {out_node_expr})'
        if isinstance(comb, MatchSeqSymbol):
            sym = getattr(comb, "pattern", None) or getattr(comb, "symbol", None) or ""
            return f'gram_match_symbol_str(p, "{sym}", {len(sym)}u, {out_node_expr})'
        if isinstance(comb, Ref) and isinstance(comb.rule, type) and issubclass(comb.rule, RuleItem):
            return f"gram_parse_rule_{self.rule_names[comb.rule]}(p, {out_node_expr})"
        return "false"

    def _compile_combinator(self, comb: Combinator, parent_node_var: str, indent: int) -> str:
        """Compile a combinator statement tree into C lines with variable `ok`."""
        pfx = "    " * indent
        lines = []

        # Safe child addition helper: no-op if parent_node_var is "NULL"
        def add_child_stmt(child_var: str) -> str:
            if not parent_node_var or parent_node_var == "NULL":
                return ""
            return f"if (ok && {child_var} && {parent_node_var} && *{parent_node_var}) gram_ast_add_child(p->arena, *{parent_node_var}, {child_var});"

        if isinstance(comb, MatchToken):
            tok = getattr(comb, "token", None)
            tname = tok.name if isinstance(tok, Token) else str(tok)
            lines.append(f"{pfx}{{")
            lines.append(f"{pfx}    uint32_t tok_node_{indent} = 0;")
            lines.append(f"{pfx}    ok = gram_match_token_kind(p, GRAM_TOKEN_{tname}, &tok_node_{indent});")
            child_stmt = add_child_stmt(f"tok_node_{indent}")
            if child_stmt:
                lines.append(f"{pfx}    {child_stmt}")
            lines.append(f"{pfx}}}")

        elif isinstance(comb, MatchKeyword):
            kw = comb.keyword
            lines.append(f"{pfx}{{")
            lines.append(f"{pfx}    uint32_t kw_node_{indent} = 0;")
            lines.append(f'{pfx}    ok = gram_match_keyword_str(p, "{kw}", {len(kw)}u, &kw_node_{indent});')
            child_stmt = add_child_stmt(f"kw_node_{indent}")
            if child_stmt:
                lines.append(f"{pfx}    {child_stmt}")
            lines.append(f"{pfx}}}")

        elif isinstance(comb, MatchGroup):
            grp = comb.group
            gident = _sanitize_c_ident(grp)
            lines.append(f"{pfx}{{")
            lines.append(f"{pfx}    uint32_t grp_node_{indent} = 0;")
            lines.append(f"{pfx}    ok = gram_match_group_{gident}(p, &grp_node_{indent});")
            child_stmt = add_child_stmt(f"grp_node_{indent}")
            if child_stmt:
                lines.append(f"{pfx}    {child_stmt}")
            lines.append(f"{pfx}}}")

        elif isinstance(comb, MatchSeqSymbol):
            sym = getattr(comb, "pattern", None) or getattr(comb, "symbol", None) or ""
            lines.append(f"{pfx}{{")
            lines.append(f"{pfx}    uint32_t sym_node_{indent} = 0;")
            lines.append(f'{pfx}    ok = gram_match_symbol_str(p, "{sym}", {len(sym)}u, &sym_node_{indent});')
            child_stmt = add_child_stmt(f"sym_node_{indent}")
            if child_stmt:
                lines.append(f"{pfx}    {child_stmt}")
            lines.append(f"{pfx}}}")

        elif isinstance(comb, Ref):
            target = comb.rule
            if isinstance(target, type) and issubclass(target, RuleItem):
                rname = self.rule_names[target]
                if getattr(target, "nodeable", True):
                    lines.append(f"{pfx}{{")
                    lines.append(f"{pfx}    uint32_t child_node_{indent} = 0;")
                    lines.append(f"{pfx}    ok = gram_parse_rule_{rname}(p, &child_node_{indent});")
                    child_stmt = add_child_stmt(f"child_node_{indent}")
                    if child_stmt:
                        lines.append(f"{pfx}    {child_stmt}")
                    lines.append(f"{pfx}}}")
                else:
                    # NOTA: una regla `nodeable = False` no crea nodo propio; recibe el
                    # destino del padre para insertar sus hijos directamente en él.
                    inline_target = parent_node_var if parent_node_var else "NULL"
                    lines.append(f"{pfx}ok = gram_parse_rule_{rname}(p, {inline_target});")
            else:
                lines.append(f"{pfx}ok = true;")

        elif isinstance(comb, (Seq, Item)):
            children = getattr(comb, "combinators", ()) or getattr(comb, "matchs", ())
            lines.append(f"{pfx}ok = true;")
            for child in children:
                lines.append(f"{pfx}if (ok) {{")
                lines.append(self._compile_combinator(child, parent_node_var, indent + 1))
                lines.append(f"{pfx}}}")

        elif isinstance(comb, Alt):
            lines.append(self._compile_alt_optimized(comb, parent_node_var, indent))

        elif isinstance(comb, Opt):
            inner = comb.combinator
            lines.append(f"{pfx}{{")
            lines.append(f"{pfx}    GramParserCheckpoint opt_cp_{indent} = gram_parser_save(p);")
            lines.append(self._compile_combinator(inner, parent_node_var, indent + 1))
            lines.append(f"{pfx}    if (!ok) gram_parser_restore(p, opt_cp_{indent});")
            lines.append(f"{pfx}    ok = true; /* Opt always succeeds */")
            lines.append(f"{pfx}}}")

        elif isinstance(comb, Many):
            inner = comb.combinator
            lines.append(f"{pfx}while (p->cursor < p->token_count) {{")
            lines.append(f"{pfx}    GramParserCheckpoint many_cp_{indent} = gram_parser_save(p);")
            lines.append(f"{pfx}    size_t prev_cur_{indent} = p->cursor;")
            lines.append(self._compile_combinator(inner, parent_node_var, indent + 1))
            lines.append(f"{pfx}    if (!ok || p->cursor == prev_cur_{indent}) {{")
            lines.append(f"{pfx}        gram_parser_restore(p, many_cp_{indent});")
            lines.append(f"{pfx}        break;")
            lines.append(f"{pfx}    }}")
            lines.append(f"{pfx}}}")
            lines.append(f"{pfx}ok = true;")

        elif isinstance(comb, Some):
            inner = comb.combinator
            lines.append(f"{pfx}ok = false;")
            lines.append(self._compile_combinator(inner, parent_node_var, indent))
            lines.append(f"{pfx}if (ok) {{")
            lines.append(f"{pfx}    while (p->cursor < p->token_count) {{")
            lines.append(f"{pfx}        GramParserCheckpoint some_cp_{indent} = gram_parser_save(p);")
            lines.append(f"{pfx}        size_t prev_cur_{indent} = p->cursor;")
            lines.append(self._compile_combinator(inner, parent_node_var, indent + 2))
            lines.append(f"{pfx}        if (!ok || p->cursor == prev_cur_{indent}) {{")
            lines.append(f"{pfx}            gram_parser_restore(p, some_cp_{indent});")
            lines.append(f"{pfx}            break;")
            lines.append(f"{pfx}        }}")
            lines.append(f"{pfx}    }}")
            lines.append(f"{pfx}    ok = true;")
            lines.append(f"{pfx}}}")

        elif isinstance(comb, SameLine):
            inner = comb.combinator
            lines.append(f"{pfx}ok = true;")
            lines.append(f"{pfx}gram_parser_skip_whitespace(p);")
            lines.append(f"{pfx}if (p->cursor > 0 && p->cursor < p->token_count) {{")
            lines.append(f"{pfx}    size_t prev_idx_{indent} = p->cursor - 1;")
            lines.append(f"{pfx}    while (prev_idx_{indent} > 0 && p->tokens[prev_idx_{indent}].kind == GRAM_TOKEN_COMMENT) prev_idx_{indent}--;")
            lines.append(f"{pfx}    if (p->tokens[p->cursor].line != p->tokens[prev_idx_{indent}].line) ok = false;")
            lines.append(f"{pfx}}}")
            lines.append(f"{pfx}if (ok) {{")
            lines.append(self._compile_combinator(inner, parent_node_var, indent + 1))
            lines.append(f"{pfx}}}")

        elif isinstance(comb, Enclosed):
            ot = getattr(comb, "open_token", getattr(comb, "open", None))
            ct = getattr(comb, "close_token", getattr(comb, "close", None))
            open_tok = ot.name if isinstance(ot, Token) else str(ot)
            close_tok = ct.name if isinstance(ct, Token) else str(ct)
            allow_empty = getattr(comb, "allow_empty", True)
            skip_ws = getattr(comb, "skip_whitespace", True)
            lines.append(f"{pfx}{{")
            lines.append(f"{pfx}    uint32_t open_n_{indent} = 0, close_n_{indent} = 0;")
            lines.append(f"{pfx}    ok = gram_match_token_kind(p, GRAM_TOKEN_{open_tok}, &open_n_{indent});")
            lines.append(f"{pfx}    if (ok) {{")
            if skip_ws:
                lines.append(f"{pfx}        p->bracket_depth++;")
            lines.append(f"{pfx}        const GramToken *enc_peek_{indent} = gram_parser_peek(p);")
            if not allow_empty:
                lines.append(f"{pfx}        size_t enc_start_cur_{indent} = p->cursor;")
            lines.append(f"{pfx}        if (enc_peek_{indent} && enc_peek_{indent}->kind == GRAM_TOKEN_{close_tok}) {{")
            lines.append(f"{pfx}            ok = {'true' if allow_empty else 'false'};")
            lines.append(f"{pfx}        }} else {{")
            lines.append(self._compile_combinator(comb.content, parent_node_var, indent + 3))
            if not allow_empty:
                lines.append(f"{pfx}            if (ok && p->cursor == enc_start_cur_{indent}) ok = false;")
            lines.append(f"{pfx}        }}")
            lines.append(f"{pfx}        if (ok) ok = gram_match_token_kind(p, GRAM_TOKEN_{close_tok}, &close_n_{indent});")
            if skip_ws:
                lines.append(f"{pfx}        if (p->bracket_depth > 0) p->bracket_depth--;")
            lines.append(f"{pfx}    }}")
            lines.append(f"{pfx}}}")

        elif isinstance(comb, Peek):
            inner = comb.combinator
            lines.append(f"{pfx}{{")
            lines.append(f"{pfx}    GramParserCheckpoint peek_cp_{indent} = gram_parser_save(p);")
            lines.append(self._compile_combinator(inner, "NULL", indent + 1))
            lines.append(f"{pfx}    gram_parser_restore(p, peek_cp_{indent});")
            lines.append(f"{pfx}}}")

        elif isinstance(comb, Not):
            inner = comb.combinator
            lines.append(f"{pfx}{{")
            lines.append(f"{pfx}    GramParserCheckpoint not_cp_{indent} = gram_parser_save(p);")
            lines.append(self._compile_combinator(inner, "NULL", indent + 1))
            lines.append(f"{pfx}    gram_parser_restore(p, not_cp_{indent});")
            lines.append(f"{pfx}    ok = !ok;")
            lines.append(f"{pfx}}}")

        elif isinstance(comb, Separator):
            sep_comb = comb.sep
            val_comb = comb.values[0] if len(comb.values) == 1 else Alt(*comb.values)
            arr_var = f"arr_node_{indent}"
            arr_tgt = f"arr_target_{indent}"
            cnt_var = f"sep_cnt_{indent}"
            lines.append(f"{pfx}{{")
            lines.append(f"{pfx}    uint32_t {arr_var} = gram_ast_arena_alloc(p->arena, GRAM_AST_ARRAY, 0, (uint32_t)p->cursor);")
            lines.append(f"{pfx}    uint32_t *{arr_tgt} = &{arr_var};")
            lines.append(f"{pfx}    size_t {cnt_var} = 0;")
            lines.append(f"{pfx}    GramParserCheckpoint sep_first_cp_{indent} = gram_parser_save(p);")
            lines.append(self._compile_combinator(val_comb, arr_tgt, indent + 1))
            lines.append(f"{pfx}    if (ok) {{")
            lines.append(f"{pfx}        {cnt_var}++;")
            lines.append(f"{pfx}        while (p->cursor < p->token_count) {{")
            lines.append(f"{pfx}            GramParserCheckpoint sep_cp_{indent} = gram_parser_save(p);")
            lines.append(self._compile_combinator(sep_comb, "NULL", indent + 3))
            lines.append(f"{pfx}            if (!ok) {{ gram_parser_restore(p, sep_cp_{indent}); break; }}")
            lines.append(self._compile_combinator(val_comb, arr_tgt, indent + 3))
            lines.append(f"{pfx}            if (!ok) {{")
            lines.append(f"{pfx}                if ({'true' if comb.allow_trailing else 'false'}) break;")
            lines.append(f"{pfx}                gram_parser_restore(p, sep_cp_{indent});")
            lines.append(f"{pfx}                break;")
            lines.append(f"{pfx}            }}")
            lines.append(f"{pfx}            {cnt_var}++;")
            lines.append(f"{pfx}        }}")
            lines.append(f"{pfx}    }} else {{")
            lines.append(f"{pfx}        gram_parser_restore(p, sep_first_cp_{indent});")
            lines.append(f"{pfx}    }}")
            if comb.min > 0:
                lines.append(f"{pfx}    ok = ({cnt_var} >= {comb.min}u);")
            else:
                lines.append(f"{pfx}    (void){cnt_var};")
                lines.append(f"{pfx}    ok = true;")
            lines.append(f"{pfx}    if ({arr_var} && p->arena) p->arena->nodes[{arr_var}].token_count = (uint32_t)(p->cursor - p->arena->nodes[{arr_var}].token_start);")
            child_stmt = add_child_stmt(arr_var)
            if child_stmt:
                lines.append(f"{pfx}    {child_stmt}")
            lines.append(f"{pfx}}}")

        elif isinstance(comb, BaseExpr):
            eid = self.expr_comb_ids[id(comb)]
            lines.append(f"{pfx}{{")
            lines.append(f"{pfx}    uint32_t expr_node_{indent} = 0;")
            lines.append(f"{pfx}    ok = gram_parse_expr_{eid}(p, 0, &expr_node_{indent});")
            child_stmt = add_child_stmt(f"expr_node_{indent}")
            if child_stmt:
                lines.append(f"{pfx}    {child_stmt}")
            lines.append(f"{pfx}}}")

        else:
            lines.append(f"{pfx}ok = true;")

        return "\n".join(lines)

    def _emit_expr_ref_atoms(self, ref_vals: tuple[Ref, ...], indent: int = 1) -> list[str]:
        """Emit first-set guarded `Ref` atom checks inside a Pratt expression atom parser."""
        pfx = "    " * indent
        out: list[str] = []
        for i, r in enumerate(ref_vals):
            target = getattr(r, "rule", None)
            if not (isinstance(target, type) and issubclass(target, RuleItem)):
                continue
            rname = self.rule_names[target]
            _, r_toks, _ = self._compute_first_set(r)
            if r_toks is not None and len(r_toks) > 0:
                cond = " || ".join(f"tok->kind == GRAM_TOKEN_{t}" for t in sorted(r_toks))
                out.extend([
                    f"{pfx}/* Ref spec {i}: {rname} */",
                    f"{pfx}if ({cond}) {{",
                    f"{pfx}    uint32_t atom_node = 0;",
                    f"{pfx}    if (gram_parse_rule_{rname}(p, &atom_node)) {{",
                    f"{pfx}        if (out_node) *out_node = atom_node;",
                    f"{pfx}        return true;",
                    f"{pfx}    }}",
                    f"{pfx}    gram_parser_restore(p, cp);",
                    f"{pfx}}}",
                ])
            else:
                out.extend([
                    f"{pfx}/* Ref spec {i}: {rname} */",
                    f"{pfx}{{",
                    f"{pfx}    uint32_t atom_node = 0;",
                    f"{pfx}    if (gram_parse_rule_{rname}(p, &atom_node)) {{",
                    f"{pfx}        if (out_node) *out_node = atom_node;",
                    f"{pfx}        return true;",
                    f"{pfx}    }}",
                    f"{pfx}    gram_parser_restore(p, cp);",
                    f"{pfx}}}",
                ])
        return out

    def _generate_pratt_expression_function(self, eid: int, expr_comb: BaseExpr) -> str:
        """Generate static Pratt precedence climbing parser function for an expression combinator."""
        ref_vals = getattr(expr_comb, "_ref_values", ())
        tok_vals = getattr(expr_comb, "_token_values", frozenset())
        refs_before_grouping = getattr(expr_comb, "refs_before_grouping", False)
        unary_ops = getattr(expr_comb, "unary_ops", {})

        lines = [
            f"static bool gram_parse_expr_{eid}_atom(GramParser *p, uint32_t *out_node) {{",
            "    GramParserCheckpoint cp = gram_parser_save(p);",
            "    const GramToken *tok = gram_parser_peek(p);",
            "    if (!tok) return false;",
        ]

        if refs_before_grouping and ref_vals:
            lines.append("    /* Specialized Ref atoms before parenthesized grouping */")
            lines.append("    if (tok->kind == GRAM_TOKEN_LPAREN) {")
            lines.extend(self._emit_expr_ref_atoms(ref_vals, indent=2))
            lines.append("    }")

        lines.extend([
            "    /* Parenthesized grouping */",
            "    if (tok->kind == GRAM_TOKEN_LPAREN) {",
            "        p->cursor++;",
            "        p->bracket_depth++;",
            "        uint32_t inner = 0;",
            f"        bool grp_ok = gram_parse_expr_{eid}(p, 0, &inner);",
            "        gram_parser_skip_whitespace(p);",
            "        if (p->bracket_depth > 0) p->bracket_depth--;",
            "        if (grp_ok && p->cursor < p->token_count && p->tokens[p->cursor].kind == GRAM_TOKEN_RPAREN) {",
            "            p->cursor++;",
            "            if (out_node) *out_node = inner;",
            "            return true;",
            "        }",
            "        gram_parser_restore(p, cp);",
            "        return false;",
            "    }",
        ])

        if unary_ops:
            lines.extend([
                "    /* Prefix unary operators */",
                "    {",
                "        int unary_rbp = 0;",
                "        switch (tok->kind) {",
            ])
            for tok_enum, rbp in unary_ops.items():
                if isinstance(tok_enum, Token):
                    lines.append(f"            case GRAM_TOKEN_{tok_enum.name}: unary_rbp = {rbp}; break;")
            lines.extend([
                "            default: break;",
                "        }",
                "        if (unary_rbp > 0) {",
                "            uint32_t op_tok_idx = (uint32_t)p->cursor++;",
                "            uint32_t operand = 0;",
                f"            if (gram_parse_expr_{eid}(p, unary_rbp, &operand)) {{",
                "                if (p->arena) {",
                "                    uint32_t u_node = gram_ast_arena_alloc(p->arena, GRAM_AST_EXPR_UNARY, (uint16_t)tok->kind, op_tok_idx);",
                "                    gram_ast_add_child(p->arena, u_node, operand);",
                "                    p->arena->nodes[u_node].token_count = (uint32_t)(p->cursor - op_tok_idx);",
                "                    if (out_node) *out_node = u_node;",
                "                }",
                "                return true;",
                "            }",
                "            gram_parser_restore(p, cp);",
                "            return false;",
                "        }",
                "    }",
            ])

        if ref_vals:
            lines.append("    /* Ref operand atoms */")
            if refs_before_grouping:
                lines.append("    if (tok->kind != GRAM_TOKEN_LPAREN) {")
                lines.extend(self._emit_expr_ref_atoms(ref_vals, indent=2))
                lines.append("    }")
            else:
                lines.extend(self._emit_expr_ref_atoms(ref_vals, indent=1))

        lines.append("    /* Token operand atoms */")
        for tok in sorted(tok_vals, key=lambda t: t.name if isinstance(t, Token) else str(t)):
            tname = tok.name if isinstance(tok, Token) else str(tok)
            lines.extend([
                f"    if (tok->kind == GRAM_TOKEN_{tname}) {{",
                f"        uint32_t tok_idx = (uint32_t)p->cursor++;",
                f"        if (out_node && p->arena) {{",
                f"            uint32_t n = gram_ast_arena_alloc(p->arena, GRAM_AST_TERMINAL_TOKEN, 0, tok_idx);",
                f"            if (n) {{ p->arena->nodes[n].token_count = 1; *out_node = n; }}",
                f"        }}",
                f"        return true;",
                f"    }}",
            ])

        lines.extend([
            "    return false;",
            "}",
            "",
            f"static bool gram_parse_expr_{eid}(GramParser *p, int min_bp, uint32_t *out_node) {{",
            "    uint32_t lhs = 0;",
            f"    if (!gram_parse_expr_{eid}_atom(p, &lhs)) return false;",
            "    while (p->cursor < p->token_count) {",
            "        const GramToken *op_tok = gram_parser_peek(p);",
            "        if (!op_tok) break;",
            "        int lbp = 0, rbp = 0;",
            "        switch (op_tok->kind) {",
        ])

        # Binary operator bindings
        binary_ops = getattr(expr_comb, "binary_ops", DUAL_BINARY_OPS)
        for tok_enum, (l_bp, r_bp) in binary_ops.items():
            if isinstance(tok_enum, Token):
                lines.append(f"            case GRAM_TOKEN_{tok_enum.name}: lbp = {l_bp}; rbp = {r_bp}; break;")

        lines.extend([
            "            default: break;",
            "        }",
            "        if (lbp < min_bp || lbp == 0) break;",
            "        uint32_t op_kind = op_tok->kind;",
            "        p->cursor++; /* Consume operator token */",
            "        uint32_t rhs = 0;",
            f"        if (!gram_parse_expr_{eid}(p, rbp, &rhs)) return false;",
            "        if (p->arena) {",
            "            uint32_t bin_node = gram_ast_arena_alloc(p->arena, GRAM_AST_EXPR_BINARY, (uint16_t)op_kind, p->arena->nodes[lhs].token_start);",
            "            gram_ast_add_child(p->arena, bin_node, lhs);",
            "            gram_ast_add_child(p->arena, bin_node, rhs);",
            "            p->arena->nodes[bin_node].token_count = (uint32_t)(p->cursor - p->arena->nodes[bin_node].token_start);",
            "            lhs = bin_node;",
            "        }",
            "    }",
            "    if (out_node) *out_node = lhs;",
            "    return true;",
            "}",
            "",
        ])
        return "\n".join(lines)


def _export_lexer_tables(session: Session, out_path: Path) -> list[str]:
    """Export the C lexer tables the driver links against and return their file names."""
    try:
        from tools.export_lexer_tables import export_session_tables
    except ImportError:
        # NOTA: `tools/` vive junto al paquete en el repositorio, no dentro de `gram/`.
        repo_root = str(Path(__file__).resolve().parents[3])
        if repo_root not in sys.path:
            sys.path.insert(0, repo_root)
        try:
            from tools.export_lexer_tables import export_session_tables
        except ImportError as exc:
            raise GrammarCompilerError(
                "LexerTablesUnavailable",
                errors.GRAMMAR_COMBINATOR_FAILED,
                "No se pudo importar tools.export_lexer_tables, necesario para el driver C.",
                "Ejecute la exportación desde el repositorio de Gram o use emit_driver=False.",
            ) from exc
    return list(export_session_tables(session, out_path)["files"])


def export_session_c_parser(
    session: Session,
    output_dir: str | Path,
    *,
    emit_driver: bool = True,
    emit_cli: bool = False,
) -> dict[str, Any]:
    """
    Compile a Gram `Session` into standalone C parser and AST translation units.

    Args:
        session: Active `Session` instance with a defined entrypoint.
        output_dir: Destination directory path for generated C files.
        emit_driver: Also emit the unified file opener (`gram_driver.*`), the binary IR
            (`gram_ir.*`) and the lexer tables they link against.
        emit_cli: Also emit `gram_cli.c`, a standalone frontend (requires `emit_driver`).

    Returns:
        Manifest dictionary with content hashes and exported rules.
    """
    if emit_cli and not emit_driver:
        raise GrammarCompilerError(
            "CliRequiresDriver",
            errors.GRAMMAR_COMBINATOR_UNSUPPORTED,
            "emit_cli=True requiere emit_driver=True.",
            "Active emit_driver o desactive emit_cli.",
        )

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    gen = CParserGenerator(session)
    gen.crawl()

    units: dict[str, str] = {
        "gram_ast.h": gen.generate_ast_header(),
        "gram_ast.c": gen.generate_ast_source(),
        "gram_parser.h": gen.generate_parser_header(),
        "gram_parser.c": gen.generate_parser_source(),
    }
    rule_names = [gen.rule_names[r] for r in gen.rules]
    grammar_id = c_driver.grammar_fingerprint(rule_names)

    if emit_driver:
        units["gram_ir.h"] = c_driver.generate_ir_header(grammar_id)
        units["gram_ir.c"] = c_driver.generate_ir_source()
        units["gram_driver.h"] = c_driver.generate_driver_header()
        units["gram_driver.c"] = c_driver.generate_driver_source()
    if emit_cli:
        units["gram_cli.c"] = c_driver.generate_cli_source()

    for name, content in units.items():
        (out_path / name).write_text(content, encoding="utf-8", newline="\n")

    manifest: dict[str, Any] = {
        "abi_version": C_PARSER_ABI_VERSION,
        "session_name": session.name,
        "mode": getattr(session, "mode", "Single"),
        "rule_count": len(gen.rules),
        "rules": rule_names,
        "files": list(units),
        "driver": emit_driver,
    }
    if emit_driver:
        manifest["ir_format"] = f"GIR {c_driver.GIR_VERSION_MAJOR}.{c_driver.GIR_VERSION_MINOR}"
        manifest["grammar_id"] = f"0x{grammar_id:016x}"
        manifest["lexer_files"] = _export_lexer_tables(session, out_path)

    hasher = hashlib.sha256()
    for content in units.values():
        hasher.update(content.encode("utf-8"))
    manifest["content_hash"] = hasher.hexdigest()

    (out_path / "gram_parser_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
        newline="\n",
    )
    return manifest
