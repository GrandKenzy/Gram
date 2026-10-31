"""
Tests for Optional C AOT GIR Tree Walker (`tests/test_gir_c_walker.py`).
======================================================================
Verifies generation of `gram_ir_walker.h` / `gram_ir_walker.c` via
`emit_walker=True`, C compilation with GCC, preorder/postorder traversal,
subtree pruning with `GRAM_IR_WALK_PRUNE`, early termination with
`GRAM_IR_WALK_STOP`, and query helper functions.
"""
from __future__ import annotations

import pathlib
import shutil
import subprocess
import tempfile
import unittest

from gram import sessions
from gram.core.combinators import MatchKeyword, MatchToken, RuleItem, Seq
from gram.core.lexer import Token


class TestGirCWalker(unittest.TestCase):
    def test_walker_requires_driver_validation(self) -> None:
        """Verify that emit_walker=True without emit_driver raises GrammarCompilerError."""
        from gram.core.parser.c_generator import GrammarCompilerError

        session = sessions.Session("NoDriverWalkerSession", "Some")

        class SimpleRule(RuleItem):
            rule = MatchKeyword("x")

        session.entrypoint = SimpleRule

        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(GrammarCompilerError):
                session.export_c_parser(tmp, emit_driver=False, emit_walker=True)

    def test_c_walker_compilation_and_traversal(self) -> None:
        """Export parser with emit_walker=True, compile a test harness in C, and run traversal."""
        if shutil.which("gcc") is None:
            self.skipTest("GCC is required to compile and verify native C GIR walker")

        class InnerRule(RuleItem):
            nodeable = True
            entrypoint = Seq(
                MatchKeyword("fn"),
                MatchToken(Token.IDENT),
                MatchToken(Token.NUMBER),
                MatchKeyword("end"),
            )
            rule = entrypoint

        session = sessions.Session("CWalkerSession", "Some")
        session.add_keyword("fn")
        session.add_keyword("end")
        session.entrypoint = InnerRule

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
            out_dir = pathlib.Path(tmp_dir)
            manifest = session.export_c_parser(
                out_dir,
                emit_driver=True,
                emit_cli=False,
                emit_walker=True,
            )

            # 1. Verify files exist in manifest
            self.assertTrue(manifest.get("walker"))
            self.assertTrue((out_dir / "gram_ir_walker.h").exists())
            self.assertTrue((out_dir / "gram_ir_walker.c").exists())

            # 2. Write a comprehensive C verification harness
            c_test_source = r"""
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>

#include "gram_driver.h"
#include "gram_ir.h"
#include "gram_ir_walker.h"

typedef struct {
    int enter_count;
    int leave_count;
    int max_depth;
} WalkStats;

static GramIrWalkAction stats_cb(
    const GramIrView *view,
    uint32_t node_idx,
    uint32_t depth,
    bool is_enter,
    void *user_data
) {
    (void)view;
    (void)node_idx;
    WalkStats *st = (WalkStats *)user_data;
    if (is_enter) {
        st->enter_count++;
        if ((int)depth > st->max_depth) st->max_depth = (int)depth;
    } else {
        st->leave_count++;
    }
    return GRAM_IR_WALK_CONTINUE;
}

typedef struct {
    const char *prune_target;
    uint32_t prune_target_idx;
    int target_entered;
    int target_left;
    int visited_under_target;
} PruneTest;

static GramIrWalkAction prune_cb(
    const GramIrView *view,
    uint32_t node_idx,
    uint32_t depth,
    bool is_enter,
    void *user_data
) {
    (void)depth;
    PruneTest *pt = (PruneTest *)user_data;
    const char *name = gram_ir_node_name(view, node_idx);
    if (is_enter) {
        if (pt->prune_target_idx != 0) {
            pt->visited_under_target++;
        }
        if (strcmp(name, pt->prune_target) == 0) {
            pt->prune_target_idx = node_idx;
            pt->target_entered++;
            return GRAM_IR_WALK_PRUNE;
        }
    } else {
        if (node_idx == pt->prune_target_idx) {
            pt->target_left++;
            pt->prune_target_idx = 0;
        }
    }
    return GRAM_IR_WALK_CONTINUE;
}

typedef struct {
    int stop_at;
    int enters;
} StopTest;

static GramIrWalkAction stop_cb(
    const GramIrView *view,
    uint32_t node_idx,
    uint32_t depth,
    bool is_enter,
    void *user_data
) {
    (void)view;
    (void)node_idx;
    (void)depth;
    StopTest *st = (StopTest *)user_data;
    if (is_enter) {
        st->enters++;
        if (st->enters == st->stop_at) {
            return GRAM_IR_WALK_STOP;
        }
    }
    return GRAM_IR_WALK_CONTINUE;
}

int main(int argc, char **argv) {
    if (argc < 2) return 1;
    const char *src_path = argv[1];

    GramIrBlob blob = { NULL, 0 };
    GramDriverError err;
    memset(&err, 0, sizeof(err));

    GramDriverStatus dst = gram_compile_file_to_ir(src_path, &blob, &err);
    if (dst != GRAM_DRIVER_OK) {
        fprintf(stderr, "Failed to compile %s to IR: %s\n", src_path, err.message);
        return 2;
    }

    GramIrView view;
    GramIrStatus ist = gram_ir_view_init(&view, blob.data, blob.size);
    assert(ist == GRAM_IR_OK);
    assert(view.header->root_index > 0);

    /* Test 1: Full traversal stats */
    WalkStats st = { 0, 0, 0 };
    ist = gram_ir_walk(&view, 0, stats_cb, &st);
    assert(ist == GRAM_IR_OK);
    assert(st.enter_count > 0);
    assert(st.enter_count == st.leave_count);
    assert(st.max_depth >= 2);

    /* Test 2: Pruning children of InnerRule */
    PruneTest pt = { "InnerRule", 0, 0, 0, 0 };
    ist = gram_ir_walk(&view, 0, prune_cb, &pt);
    assert(ist == GRAM_IR_OK);
    assert(pt.target_entered == 1);
    assert(pt.target_left == 1);
    assert(pt.visited_under_target == 0); /* Descendants were never visited */

    /* Test 2b: Early abortion with GRAM_IR_WALK_STOP */
    StopTest st_stop = { 2, 0 };
    ist = gram_ir_walk(&view, 0, stop_cb, &st_stop);
    assert(ist == GRAM_IR_OK);
    assert(st_stop.enters == 2);

    /* Test 3: Search helpers */
    uint32_t ident_idx = gram_ir_find_first(&view, 0, "IDENT");
    assert(ident_idx > 0);
    const char *ident_name = gram_ir_node_name(&view, ident_idx);
    assert(strcmp(ident_name, "IDENT") == 0);
    uint32_t text_len = 0;
    const char *ident_text = gram_ir_node_text(&view, ident_idx, &text_len);
    assert(text_len > 0);
    assert(strcmp(ident_text, "calc") == 0);

    /* Test 4: Child navigation */
    uint32_t rule_idx = gram_ir_find_first(&view, 0, "InnerRule");
    assert(rule_idx > 0);
    uint32_t c0 = gram_ir_node_child_at(&view, rule_idx, 0);
    assert(c0 > 0);
    assert(strcmp(gram_ir_node_name(&view, c0), "KEYWORD") == 0);
    uint32_t c1 = gram_ir_node_child_at(&view, rule_idx, 1);
    assert(c1 == ident_idx);

    /* Test 5: Span bounds validation against source_size */
    uint8_t *corrupt_buf = (uint8_t *)malloc(blob.size);
    assert(corrupt_buf != NULL);
    memcpy(corrupt_buf, blob.data, blob.size);
    const GramIrHeader *orig_h = (const GramIrHeader *)corrupt_buf;
    GramIrNode *corrupt_nodes = (GramIrNode *)(corrupt_buf + orig_h->nodes_offset);
    corrupt_nodes[1].src_length = (uint32_t)orig_h->source_size + 100u;
    GramIrView bad_view;
    GramIrStatus bad_st = gram_ir_view_init(&bad_view, corrupt_buf, blob.size);
    assert(bad_st == GRAM_IR_ERR_FORMAT);
    free(corrupt_buf);

    gram_ir_view_free(&view);
    gram_ir_blob_free(&blob);
    printf("ALL_C_WALKER_TESTS_PASSED\n");
    return 0;
}
"""
            test_c_file = out_dir / "test_walker.c"
            test_c_file.write_text(c_test_source, encoding="utf-8")

            # 3. Compile test harness
            proj_root = pathlib.Path(__file__).resolve().parent.parent
            native_inc = proj_root / "native" / "gram_lexer" / "include"
            native_src = proj_root / "native" / "gram_lexer" / "src"

            sources = [
                "gram_ast.c", "gram_parser.c", "gram_ir.c", "gram_driver.c",
                "gram_ir_walker.c",
                "gram_lexer_keywords.c", "gram_lexer_symbols.c", "gram_lexer_groups.c",
            ]
            common = [str(out_dir / name) for name in sources] + [
                str(native_src / name)
                for name in (
                    "lexer.c", "indentation.c", "numbers.c", "strings.c",
                    "symbols.c", "utf8.c", "diagnostics_lite.c",
                )
            ]
            test_exe = out_dir / "test_walker.exe"
            flags = [
                "gcc", "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
                f"-I{native_inc}", f"-I{native_src}", f"-I{out_dir}",
                str(test_c_file), *common, "-o", str(test_exe),
            ]
            subprocess.run(flags, check=True, capture_output=True, text=True)

            # 4. Run C walker harness
            src_file = out_dir / "test.src"
            src_file.write_text("fn calc 42 end", encoding="utf-8")
            res = subprocess.run([str(test_exe), str(src_file)], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, f"C walker test failed: {res.stderr}\n{res.stdout}")
            self.assertIn("ALL_C_WALKER_TESTS_PASSED", res.stdout)


if __name__ == "__main__":
    unittest.main()
