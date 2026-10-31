"""Isolated language sessions for lexer configuration and lexicon state."""
from __future__ import annotations

from collections.abc import MutableMapping
from copy import deepcopy
from typing import Any, Literal

from gram import config
from gram.core.combinators import RuleItem
from gram.core.combinators.base import _touch_predictive_epoch
from gram.core.lexer import Lexer, TokenType, tokens, words
from gram.core.parser import ConversionState, Parser
from gram.core.parser.conversions import ConversionTarget

_MODES = frozenset(("Many", "Some"))
_SESSION_CONFIG_KEYS = frozenset(
    key
    for key in config.to_dict()
    if key.startswith(("LEXER_", "PARSER_", "AST_", "ERROR_", "INFO_"))
    or key in {
        "SUPPORT_TRIPLE_DOT",
        "SUPPORT_INDENT",
        "TOKEN_BOOL_TRUE",
        "TOKEN_BOOL_FALSE",
        "TOKEN_NULL",
        "LOG_HIDE_CONSOLE",
    }
)


def _replace(target: dict, items) -> None:
    """Replace a registry in place, preserving its observable identity."""
    target.clear()
    target.update(items)
    if isinstance(target, tokens._MapSymbolsDict):
        tokens._sync_symbol_indexes(target)


def _session_config() -> dict[str, Any]:
    """Capture only configuration owned by a language session."""
    snapshot = config.save()
    return {
        key: deepcopy(value)
        for key, value in snapshot.items()
        if key in _SESSION_CONFIG_KEYS
    }


class Session:
    """Own the effective lexer state for one language frontend.

    The session stores its lexicon, symbols, and lexer/parser-related settings
    independently from process-wide compatibility registries. Calling
    :meth:`init` routes the loose ``words.add_*`` API to this session;
    :meth:`migrate` stores that state and restores the previous process state;
    :meth:`load` activates the stored state.
    """

    __slots__ = (
        "name",
        "mode",
        "entrypoint",
        "keywords",
        "groups",
        "words",
        "group",
        "config",
        "last_config",
        "symbols",
        "symbol_order",
        "map_symbols",
        "map_symbs_copy",
        "lexer",
        "parser",
        "_restore_keywords",
        "_restore_groups",
        "_restore_config",
        "_restore_symbols",
        "_loaded",
        "_predictive_revision",
    )

    def __init__(
        self,
        name: str,
        mode: Literal["Many", "Some"],
        entrypoint: type[RuleItem] | None = None,
        *,
        ident_underscores: int | None = None,
    ) -> None:
        if mode not in _MODES:
            raise ValueError("mode must be 'Many' or 'Some'")

        self.name = name
        self.mode = mode
        self.entrypoint: type[RuleItem] | None = entrypoint
        self.keywords: dict[str, words.Keyword] = {}
        self.groups: dict[str, words.WordGroup] = {}
        # Kept as observable snapshots for consumers of the previous API.
        self.words: tuple[tuple[str, words.Keyword], ...] = ()
        self.group: tuple[tuple[str, words.WordGroup], ...] | None = None
        self.config: dict[str, Any] = _session_config()
        if ident_underscores is not None:
            self.config["LEXER_IDENT_UNDERSCORES"] = int(ident_underscores)
        self.last_config: dict[str, Any] | None = None
        self.symbols = tokens._MapSymbolsDict(tokens.MAP_SYMBOLS)
        self.symbol_order: list[str] = sorted(self.symbols, key=len, reverse=True)
        self.map_symbols: tuple[tuple[str, tokens.Token], ...] = tuple(tokens.MAP_SYMBOLS.items())
        self.map_symbs_copy: tuple[tuple[str, tokens.Token], ...] | None = None
        self._restore_keywords: tuple[tuple[str, words.Keyword], ...] = ()
        self._restore_groups: tuple[tuple[str, words.WordGroup], ...] = ()
        self._restore_config: dict[str, Any] | None = None
        self._restore_symbols: tuple[tuple[str, tokens.Token], ...] = ()
        self._loaded = False
        self._predictive_revision = 0

        # The lexer is a configured session view; tokenize() creates a fresh
        # cursor while retaining this session as its source of configuration.
        self.lexer = Lexer((), session=self)
        # Parser configuration is intentionally deferred, but expose the
        # pre-created object so both engines have a stable session owner.
        self.parser = Parser([], f"{name}-parser", session=self)

    @property
    def ident_underscores(self) -> int:
        """Return the maximum leading underscores allowed in an identifier (-1 = unlimited, -2 = unlimited if followed by char, 0 = none, k >= 1 = at most k)."""
        return int(self.config.get("LEXER_IDENT_UNDERSCORES", -1))

    @ident_underscores.setter
    def ident_underscores(self, value: int) -> None:
        self.config["LEXER_IDENT_UNDERSCORES"] = int(value)

    def add_group(
        self,
        name: str | words.WordGroup,
        values=None,
        color_group: str = "#FFA500",
        description: str = "",
        *,
        allow_override: bool = False,
    ) -> words.WordGroup:
        """Register a group in this session's isolated lexicon."""
        previous = words.active_session()
        words.bind_session(self)
        try:
            result = words.add_group(
                name,
                values,
                color_group,
                description,
                allow_override=allow_override,
            )
            self._sync_legacy_catalog()
            self._touch_predictive_revision()
            return result
        finally:
            if previous is None:
                words.unbind_session(self)
            else:
                words.bind_session(previous)

    def add_keyword(
        self,
        name: str,
        hex_color: str = "#FFFFFF",
        group: str | words.WordGroup | None = None,
        description: str = "",
        documentation: str = "",
        *,
        color: str | None = None,
        allow_override: bool = False,
    ) -> words.Keyword:
        """Register a keyword in this session's isolated lexicon."""
        previous = words.active_session()
        words.bind_session(self)
        try:
            result = words.add_keyword(
                name,
                hex_color,
                group,
                description,
                documentation,
                color=color,
                allow_override=allow_override,
            )
            self._sync_legacy_catalog()
            self._touch_predictive_revision()
            return result
        finally:
            if previous is None:
                words.unbind_session(self)
            else:
                words.bind_session(previous)

    def get_keyword(self, name: str) -> words.Keyword | None:
        """Return a keyword from this session without changing global state."""
        return self.keywords.get(name)

    def get_group(self, name: str | words.WordGroup) -> words.WordGroup | None:
        """Return a word group from this session without changing global state."""
        group_name = name.name if isinstance(name, words.WordGroup) else str(name)
        return self.groups.get(group_name)

    def group_exists(self, name: str | words.WordGroup) -> bool:
        """Return whether a word group exists in this session."""
        return self.get_group(name) is not None

    def exists_in_group(
        self,
        keyword_name: str | words.Keyword,
        group_name: str | words.WordGroup,
    ) -> bool:
        """Return whether a keyword belongs to a session-owned group."""
        group = self.get_group(group_name)
        if group is None:
            return False
        name = keyword_name.name if isinstance(keyword_name, words.Keyword) else str(keyword_name)
        return group.contains(name)

    def keyword_count(self) -> int:
        """Return the number of keywords owned by the session."""
        return len(self.keywords)

    @property
    def predictive_revision(self) -> int:
        """Return the revision of session-owned predictive inputs."""
        return self._predictive_revision

    def _touch_predictive_revision(self) -> None:
        """Invalidate cached predictive plans that depend on this session."""
        self._predictive_revision += 1
        _touch_predictive_epoch()

    def _sync_legacy_catalog(self) -> None:
        """Keep legacy readers aligned when this session is currently loaded."""
        if self._loaded:
            _replace(words.MAP_KEYWORDS, self.keywords)
            _replace(words._GLOBAL_GROUPS, self.groups)

    def clear_global(self) -> None:
        """Clear this session's lexicon and, before ``init()``, the legacy catalog."""
        self.keywords.clear()
        self.groups.clear()
        if self._restore_config is None:
            words.MAP_KEYWORDS.clear()
            words._GLOBAL_GROUPS.clear()
        self._sync_legacy_catalog()
        self._touch_predictive_revision()

    def init(self) -> None:
        """Prepare isolated storage and route loose registrations to it."""
        self._loaded = False
        self._restore_keywords = tuple(words.MAP_KEYWORDS.items())
        self._restore_groups = tuple(words._GLOBAL_GROUPS.items())
        self._restore_config = config.save()  # type: ignore[assignment]
        self._restore_symbols = tuple(tokens.MAP_SYMBOLS.items())
        self.symbols.clear()
        self.symbols.update(self._restore_symbols)
        tokens._sync_symbol_indexes(self.symbols)
        self.symbol_order[:] = sorted(self.symbols, key=len, reverse=True)
        self.last_config = deepcopy(self._restore_config)
        self.map_symbs_copy = self._restore_symbols
        self._touch_predictive_revision()
        self.config = _session_config()
        words.bind_session(self)

    def migrate(self) -> None:
        """Store session state and restore the state active before ``init``."""
        self._loaded = False
        self.words = tuple(self.keywords.items())
        self.group = tuple(self.groups.items())
        self.config = _session_config()
        self.map_symbols = tuple(tokens.MAP_SYMBOLS.items())
        self.symbols.clear()
        self.symbols.update(self.map_symbols)
        tokens._sync_symbol_indexes(self.symbols)
        self.symbol_order[:] = sorted(self.symbols, key=len, reverse=True)

        words.unbind_session(self)
        _replace(words.MAP_KEYWORDS, self._restore_keywords)
        _replace(words._GLOBAL_GROUPS, self._restore_groups)
        if self._restore_config is not None:
            config.load(self._restore_config)
        _replace(tokens.MAP_SYMBOLS, self._restore_symbols)
        self.last_config = None
        self.map_symbs_copy = None
        self._touch_predictive_revision()

    def load(self) -> None:
        """Activate this session's lexicon, symbols, and owned settings."""
        if self.group is None:
            raise RuntimeError("migrate() must be called before load()")
        _replace(words.MAP_KEYWORDS, self.keywords)
        _replace(words._GLOBAL_GROUPS, self.groups)
        _replace(tokens.MAP_SYMBOLS, self.symbols.items())
        config.load(self.config)
        self._loaded = True
        self._touch_predictive_revision()

    def tokenize(
        self,
        source: list[str] | str,
        name: str,
        *,
        backend: Literal["python", "c"] | None = None,
    ):
        """Tokenize ``source`` with this session's lexer configuration."""
        raw_source = "\n".join(source) if isinstance(source, (list, tuple)) else str(source)
        self.parser.source = raw_source
        return self.lexer.tokenize(source, name, backend=backend)

    def new_conversion_state(self) -> ConversionState:
        """Create an empty detached conversion state for a compilation unit."""
        return ConversionState()

    def parse(
        self,
        tokens: list[TokenType],
        name: str,
        entrypoint: type[RuleItem] | None = None,
        *,
        conversion_state: ConversionState | MutableMapping[str, ConversionTarget] | None = None,
        trace: Literal["off", "basic", "detailed"] = "basic",
    ):
        """Parse tokens through this session's reusable parser and AST view."""
        entry = entrypoint or self.entrypoint
        if not entry:
            raise RuntimeError("No se especificó una entrada")

        state = (
            conversion_state.export()
            if isinstance(conversion_state, ConversionState)
            else dict(conversion_state or {})
        )
        parser = self.parser.reset(tokens, name, conversions=state)
        result = parser.parse(entry, self.mode, trace=trace)  # type: ignore

        parse_errors = list(getattr(parser, "_errors", ()))
        analyzer = parser.analyzer_ast_instance
        parse_errors.extend(getattr(analyzer, "_errors", ()) if analyzer else ())
        succeeded = result is not None and not parse_errors
        if succeeded and isinstance(conversion_state, ConversionState):
            conversion_state.replace(parser.export_conversions())
        elif succeeded and isinstance(conversion_state, MutableMapping):
            conversion_state.clear()
            conversion_state.update(parser.export_conversions())
        return result


    def export_c_parser(
        self,
        output_dir: str | Path,
        *,
        emit_driver: bool = True,
        emit_cli: bool = False,
    ) -> dict[str, Any]:
        """Compile and export this session's grammar graph into standalone C translation units.

        With ``emit_driver`` the output also contains the file opener, the binary IR (GIR)
        and the lexer tables; ``emit_cli`` adds a ready-to-build command-line frontend.
        """
        from gram.core.parser.c_generator import export_session_c_parser
        return export_session_c_parser(self, output_dir, emit_driver=emit_driver, emit_cli=emit_cli)
