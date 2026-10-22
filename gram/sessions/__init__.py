from typing import Any, Literal

from gram import config
from gram.core.combinators import RuleItem
from gram.core.lexer import Lexer, TokenType, words
from gram.core.parser import Parser


class Session:
    def __init__(self, name: str, mode: Literal['Many', 'Some'], entrypoint: type[RuleItem] | None = None):

        if mode not in ('Many', 'Some'):
            raise ValueError("mode must be 'Many' or 'Some'")

        self.name = name
        self.mode = mode
        self.words: dict[str, words.Keyword] = {}
        self.group: words.WordGroupManager | None = None
        self.last_config: dict[str, Any] = {}
        self.config: dict[str, Any] = {}
        self.entrypoint: type[RuleItem] | None = entrypoint

    def clear_global(self):
        words.clear_all()
        
    def init(self):
       self.last_config = config.save() # type: ignore
            
    def migrate(self):
        self.words = words.MAP_KEYWORDS.copy()
        self.group = words.WordGroupManager()
        self.group._groups = words.groups._groups.copy()
        
        self.config = config.save() # type: ignore
        if self.last_config:
            config.reset_to_defaults()
            config.load(self.last_config)
            self.last_config.clear()
            
    def load(self):
        words.MAP_KEYWORDS = self.words
        assert self.group is not None
        words.groups._groups = self.group._groups
        config.load(self.config)
        
    def tokenize(self, source: list[str] | str,  name: str):
        l = Lexer(source, name)
        return l.process()
    
    def parse(self,  tokens: list[TokenType], name: str, entrypoint: type[RuleItem] | None = None):
        p = Parser(tokens, name)
        entry = entrypoint or self.entrypoint
        if not entry:
            raise RuntimeError('No se especificó una entrada')
        else:
            return p.parse(entry, self.mode) # type: ignore
        