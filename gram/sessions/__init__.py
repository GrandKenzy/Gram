from typing import Any, Literal

from gram import config
from gram.core.combinators import RuleItem
from gram.core.lexer import Lexer, TokenType, words, tokens
from gram.core.parser import Parser

_MODES = frozenset(('Many', 'Some'))


def _replace(target: dict, items) -> None:
    """Replace the contents of `target` in place with `items`, keeping the object identity."""
    target.clear()
    target.update(items)


class Session:
    """Isolated lexer/parser state.

    `init` snapshots the global state that was active before the session.
    `migrate` stores the session's own state and restores that snapshot.
    `load` re-applies the session's own state.

    Snapshots are kept as tuples of items to stay small. The global
    registries remain dictionaries and are always modified in place.
    """

    __slots__ = (
        'name', 'mode', 'words', 'group', 'last_config', 'config',
        'entrypoint', 'map_symbs_copy', 'map_symbols',
    )

    def __init__(self, name: str, mode: Literal['Many', 'Some'], entrypoint: type[RuleItem] | None = None):
        if mode not in _MODES:
            raise ValueError("mode must be 'Many' or 'Some'")

        self.name = name
        self.mode = mode
        self.entrypoint: type[RuleItem] | None = entrypoint
        self.words: tuple[tuple[str, words.Keyword], ...] = ()
        self.group: tuple[tuple[str, Any], ...] | None = None
        self.config: dict[str, Any] = {}
        self.last_config: dict[str, Any] | None = None
        self.map_symbols: tuple[tuple[str, tokens.Token], ...] = ()
        self.map_symbs_copy: tuple[tuple[str, tokens.Token], ...] | None = None

    def clear_global(self) -> None:
        """Clear all globally registered words."""
        words.clear_all()

    def init(self) -> None:
        """Snapshot the current global config and symbols so they can be restored later."""
        self.last_config = config.save()  # type: ignore
        self.map_symbs_copy = tuple(tokens.MAP_SYMBOLS.items())

    def migrate(self) -> None:
        """Store this session's state and restore the snapshot taken by `init`."""
        self.words = tuple(words.MAP_KEYWORDS.items())
        self.group = tuple(words.groups._groups.items())
        self.config = config.save()  # type: ignore
        self.map_symbols = tuple(tokens.MAP_SYMBOLS.items())

        if self.last_config is not None:
            config.reset_to_defaults()
            config.load(self.last_config)
            self.last_config = None

        if self.map_symbs_copy is not None:
            _replace(tokens.MAP_SYMBOLS, self.map_symbs_copy)
            self.map_symbs_copy = None

    def load(self) -> None:
        """Apply this session's stored state to the global registries."""
        if self.group is None:
            raise RuntimeError('migrate() must be called before load()')
        _replace(words.MAP_KEYWORDS, self.words)
        _replace(words.groups._groups, self.group)
        _replace(tokens.MAP_SYMBOLS, self.map_symbols)
        config.load(self.config)

    def tokenize(self, source: list[str] | str, name: str):
        """Tokenize `source` and return the resulting tokens."""
        return Lexer(source, name).process()

    def parse(self, tokens: list[TokenType], name: str, entrypoint: type[RuleItem] | None = None):
        """Parse `tokens` using `entrypoint`, or the session entrypoint when omitted."""
        entry = entrypoint or self.entrypoint
        if not entry:
            raise RuntimeError('No se especificó una entrada')
        return Parser(tokens, name).parse(entry, self.mode)  # type: ignore