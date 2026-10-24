"""Deterministic checkpoint fuzzing against a full-state reference model."""
from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass
import random
import unittest
from unittest.mock import patch

from gram import config
from gram.core.lexer.tokens import Token, TokenType
from gram.core.parser.core import Parser


@dataclass
class _ModelState:
    tokens: list[TokenType]
    touched: set[int]
    storage: dict[str, TokenType]
    tags: dict[int, frozenset[str]]
    pos: int = 0
    vpos: int = 0
    bracket_depth: int = 0

    def copy(self) -> _ModelState:
        # The oracle deliberately copies the entire state, independently of
        # the production checkpoint's sparse representation.
        return _ModelState(
            self.tokens.copy(), self.touched.copy(), self.storage.copy(),
            self.tags.copy(), self.pos, self.vpos, self.bracket_depth,
        )


class TestCheckpointFuzz(unittest.TestCase):
    SEEDS = (0, 1, 7, 23, 42, 99, 127, 257, 1024, 4093, 65537, 20261023)
    STEPS_PER_SEED = 2000

    def assert_model(self, parser: Parser, model: _ModelState, original: tuple) -> None:
        self.assertEqual(
            tuple(map(id, parser.tokens)), tuple(map(id, model.tokens))
        )
        self.assertEqual(
            {key: id(value) for key, value in parser.storage.items()},
            {key: id(value) for key, value in model.storage.items()},
        )
        self.assertEqual(parser.tk_tags, model.tags)
        self.assertEqual(
            (parser.pos, parser.vpos, parser.bracket_depth),
            (model.pos, model.vpos, model.bracket_depth),
        )
        # Originals come from the initial stream and a model-owned touched set,
        # never from production's override map or checkpoint fields.
        self.assertEqual(
            {index: id(token) for index, token in parser._token_overrides.items()},
            {index: id(original[index]) for index in model.touched},
        )

    @patch.multiple(
        config, LEXER_ADD_INFO=False, PARSER_ADD_INFO=False, AST_ADD_INFO=False,
        INFO_INIT=False, INFO_GENERATE_LOGFILE=False,
        INFO_GENERATE_LOGFILE_ON_ERROR=False, ERROR_GENERATE_LOGFILE=False,
        LOG_HIDE_CONSOLE=True, ERROR_HIDE_CONSOLE=True, ERROR_EXIT_ON_ERROR=False,
    )
    def test_randomized_checkpoint_state_matches_full_snapshot_model(self) -> None:
        # Parser alone does not construct ASTAnalyzer or RayTracing.
        for seed in self.SEEDS:
            with self.subTest(seed=seed):
                rng = random.Random(seed)
                original = tuple(
                    TokenType(token=Token.NUMBER, value=index, line=1, col=index)
                    for index in range(32)
                )
                # Include originals and distinct objects with equal field values:
                # comparison must detect identity loss, not merely equal values.
                pool = original + tuple(
                    TokenType(token=Token.NUMBER, value=index, line=1, col=index)
                    for index in range(64)
                )
                parser = Parser(list(original))
                model = _ModelState(list(original), set(), {}, {})
                checkpoints = [(parser.savepoint("initial"), model.copy())]
                counts: Counter[str] = Counter()
                history: deque[str] = deque(maxlen=12)

                for step in range(self.STEPS_PER_SEED):
                    choice = rng.randrange(100)
                    if choice < 35:
                        index = rng.randrange(-2, len(original) + 2)
                        token_index = rng.randrange(len(pool))
                        token = pool[token_index]
                        history.append(f"replace({index}, pool[{token_index}])")
                        counts["replace"] += 1
                        parser.replace_token_at(index, token)
                        if 0 <= index < len(model.tokens):
                            model.tokens[index] = token
                            model.touched.add(index)
                    elif choice < 50:
                        history.append(f"save({len(checkpoints)})")
                        counts["save"] += 1
                        checkpoints.append((parser.savepoint(str(step)), model.copy()))
                    elif choice < 70:
                        index = rng.randrange(len(checkpoints))
                        history.append(f"restore({index})")
                        counts["restore"] += 1
                        checkpoint, saved_model = checkpoints[index]
                        parser.restore(checkpoint)
                        model = saved_model.copy()
                    elif choice < 80:
                        pos = rng.randrange(len(original) + 1)
                        vpos = rng.randrange(len(original) + 1)
                        depth = rng.randrange(6)
                        history.append(f"cursors({pos}, {vpos}, {depth})")
                        counts["cursors"] += 1
                        parser.pos, parser.vpos, parser.bracket_depth = pos, vpos, depth
                        model.pos, model.vpos, model.bracket_depth = pos, vpos, depth
                    elif choice < 90:
                        key = f"slot{rng.randrange(8)}"
                        counts["storage"] += 1
                        if rng.randrange(4) == 0:
                            history.append(f"storage.pop({key})")
                            parser.storage.pop(key, None)
                            model.storage.pop(key, None)
                        else:
                            token_index = rng.randrange(len(pool))
                            token = pool[token_index]
                            history.append(f"storage[{key}]=pool[{token_index}]")
                            parser.storage[key] = token
                            model.storage[key] = token
                    else:
                        index = rng.randrange(len(original))
                        bits = rng.randrange(16)
                        tags = frozenset(f"tag{bit}" for bit in range(4) if bits & 1 << bit)
                        history.append(f"tags[{index}]={sorted(tags)}")
                        counts["tags"] += 1
                        if tags:
                            parser.tk_tags[index] = tags
                            model.tags[index] = tags
                        else:
                            parser.tk_tags.pop(index, None)
                            model.tags.pop(index, None)

                    try:
                        self.assert_model(parser, model, original)
                    except AssertionError as error:
                        self.fail(f"seed={seed}, step={step}, recent={list(history)}\n{error}")

                self.assertTrue(all(counts[name] for name in (
                    "replace", "save", "restore", "cursors", "storage", "tags"
                )))
                # Explicitly revisit both ends twice after arbitrary branch history.
                for index in (0, len(checkpoints) - 1, 0, len(checkpoints) - 1):
                    checkpoint, saved_model = checkpoints[index]
                    parser.restore(checkpoint)
                    self.assert_model(parser, saved_model, original)
