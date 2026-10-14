"""
Centralized Formal Error Catalog and Classes (`gram.errors`).
=============================================================
Defines Gram's domain-specific exception classes (`LexerError`, `ParserError`,
`ASTError`, `GrammarError`, `SemanticError`, `CompilationError`, `PluginError`,
`SystemError`), all `CODE_*` OSGDC dimension tokens, and all formal `CodeError`
definitions prefixed by their corresponding error class.

OSGDC 5-Dimension Standard:
  [O] Origin:        Native=1, Plugin=2, Unknown=0
  [S] Scope:         Lexer=1, Parser=2, Grammar=3, Semantic=4, Compilation=5, Unknown=0
  [G] Gravity:       Minor=0, Implementation=1, Obsolete=2, Internal=3, Fatal=4
  [D] Documentation: Documented=0, Documented & Traceable=1, Not Documented=2
  [C] Condition:     Usable=0, Requires Repair=1, Should Repair=2
"""
from __future__ import annotations

import sys

from gram.utilities.error import CodeError, Codes, Error, set_map_codes

# ==============================================================================
# GRAM DOMAIN ERROR CLASSES
# ==============================================================================

class LexerError(Error):
    """Structured exception for errors occurring during lexical analysis."""


class ParserError(Error):
    """Structured exception for errors occurring during syntactic parsing."""


class ASTError(Error):
    """Structured exception for errors occurring during AST construction or validation."""


class GrammarError(Error):
    """Structured exception for errors in grammar rules and combinators."""


class SemanticError(Error):
    """Structured exception for errors occurring during semantic analysis."""


class CompilationError(Error):
    """Structured exception for errors in DSL compilation and specifications."""


class PluginError(Error):
    """Structured exception for errors in plugin manifests and lifecycle."""


class SystemError(Error):
    """Structured exception for generic or unclassified system errors."""


# ==============================================================================
# OSGDC DIMENSION MAP INITIALIZATION
# ==============================================================================
# O: max 2, S: max 5, G: max 4, D: max 2, C: max 2
set_map_codes(
    origin=[2],
    scope=[5],
    gravity=[4],
    documentation=[2],
    condition=[2],
)

# ==============================================================================
# WILDCARD / DEFAULT CODE
# ==============================================================================

CODE_UNKNOWN: Codes = Codes('unknown', 0, 'default')
"""Default wildcard code token for omitted OSGDC positions."""


# ==============================================================================
# OSGDC DIMENSION CODES (PREFIX: CODE_*)
# ==============================================================================

# ------------------------------------------------------------------------------
# 1. ORIGIN (O): Emitting component origin
# ------------------------------------------------------------------------------
CODE_UNKNOWN_ORIGIN: Codes = Codes('unknown', 0, 'origin')
"""Undetermined or untraceable origin (O = 0)."""

CODE_NATIVE_ERROR: Codes = Codes('native', 1, 'origin')
"""Error originating in Gram's native core components (O = 1)."""

CODE_PLUGIN_ERROR: Codes = Codes('plugin', 2, 'origin')
"""Error originating inside an external plugin or extension (O = 2)."""

# ------------------------------------------------------------------------------
# 2. SCOPE (S): Subsystem or processing pipeline stage
# ------------------------------------------------------------------------------
CODE_UNKNOWN_SCOPE: Codes = Codes('unknown', 0, 'scope')
"""Unspecified or generic subsystem scope (S = 0)."""

CODE_LEXER_ERROR: Codes = Codes('lexer', 1, 'scope')
"""Lexical phase: character scanning, keywords, numbers, and strings (S = 1)."""

CODE_PARSER_ERROR: Codes = Codes('parser', 2, 'scope')
"""Syntactic parsing phase: unexpected tokens, premature EOF, cursor state (S = 2)."""

CODE_GRAMMAR_ERROR: Codes = Codes('grammar', 3, 'scope')
"""Grammar rule definitions, combinators, and AST construction (S = 3)."""

CODE_SEMANTIC_ERROR: Codes = Codes('semantic', 4, 'scope')
"""Semantic analysis phase: type compatibility, scoping, and symbols (S = 4)."""

CODE_COMPILATION_ERROR: Codes = Codes('compilation', 5, 'scope')
"""Compilation phase, module inclusions, and GramLang DSL (S = 5)."""

# ------------------------------------------------------------------------------
# 3. GRAVITY (G): Functional impact on execution
# ------------------------------------------------------------------------------
CODE_MINOR: Codes = Codes('minor', 0, 'gravity')
"""Minor warning or non-blocking issue that does not halt analysis (G = 0)."""

CODE_IMPLEMENTATION_ERROR: Codes = Codes('implementation error', 1, 'gravity')
"""Feature, combinator, or capability not yet implemented (G = 1)."""

CODE_OBSOLETE_ERROR: Codes = Codes('obsolete error', 2, 'gravity')
"""Deprecated or obsolete syntax, function, or component (G = 2)."""

CODE_INTERNAL: Codes = Codes('internal', 3, 'gravity')
"""Internal state inconsistency within the framework engine (G = 3)."""

CODE_FATAL: Codes = Codes('fatal', 4, 'gravity')
"""Critical error that immediately aborts analysis of the active branch (G = 4)."""

# ------------------------------------------------------------------------------
# 4. DOCUMENTATION (D): Documentation and traceability level
# ------------------------------------------------------------------------------
CODE_DOCUMENTED: Codes = Codes('documented', 0, 'documentation')
"""Formally cataloged error with a standard description entry (D = 0)."""

CODE_DOCUMENTED_AND_TRACEABLE: Codes = Codes('documented and traceable', 1, 'documentation')
"""Formally documented error with full trace and repair suggestions (D = 1)."""

CODE_NOT_DOCUMENTED: Codes = Codes('not documented', 2, 'documentation')
"""Ad-hoc error without official technical documentation assigned (D = 2)."""

# ------------------------------------------------------------------------------
# 5. CONDITION (C): Usability of the resulting artifact and repairability
# ------------------------------------------------------------------------------
CODE_USABLE: Codes = Codes('usable', 0, 'condition')
"""Generated artifact or token is operable and analysis may continue (C = 0)."""

CODE_REQUIRES_REPAIR: Codes = Codes('requires repair', 1, 'condition')
"""Analyzed source contains a defect that must be repaired by the user (C = 1)."""

CODE_SHOULD_REPAIR: Codes = Codes('should repair', 2, 'condition')
"""Repair is strongly recommended to prevent future inconsistencies (C = 2)."""


# ==============================================================================
# 1. LEXER ERRORS (Class: LexerError -> Prefix: LEXER_*)
# ==============================================================================

LEXER_EMPTY_KEYWORDS: CodeError = CodeError(
    (
        CODE_NATIVE_ERROR,
        CODE_LEXER_ERROR,
        CODE_MINOR,
        CODE_DOCUMENTED_AND_TRACEABLE,
        CODE_USABLE,
    ),
    'Gram.Lexer.EmptyKeywords',
)
"""Raised when the lexer is initialized without any registered keywords (S-11010)."""

LEXER_KEYWORD_ALREADY_EXISTS: CodeError = CodeError(
    (
        CODE_NATIVE_ERROR,
        CODE_LEXER_ERROR,
        CODE_MINOR,
        CODE_DOCUMENTED_AND_TRACEABLE,
        CODE_USABLE,
    ),
    'Gram.Lexer.KeywordAlreadyExists',
)
"""Raised when attempting to register a keyword that already exists in the lexer table (S-11010)."""

LEXER_KEYWORD_NOT_FOUND: CodeError = CodeError(
    (
        CODE_NATIVE_ERROR,
        CODE_LEXER_ERROR,
        CODE_MINOR,
        CODE_DOCUMENTED_AND_TRACEABLE,
        CODE_USABLE,
    ),
    'Gram.Lexer.KeywordNotFound',
)
"""Raised when a requested keyword is not found in the lexer catalog (S-11010)."""

LEXER_GROUP_NOT_FOUND: CodeError = CodeError(
    (
        CODE_NATIVE_ERROR,
        CODE_LEXER_ERROR,
        CODE_MINOR,
        CODE_DOCUMENTED_AND_TRACEABLE,
        CODE_USABLE,
    ),
    'Gram.Lexer.GroupNotFound',
)
"""Raised when referencing a lexical group that does not exist (S-11010)."""

LEXER_KEYWORD_INVALID_NAME: CodeError = CodeError(
    (
        CODE_NATIVE_ERROR,
        CODE_LEXER_ERROR,
        CODE_MINOR,
        CODE_DOCUMENTED_AND_TRACEABLE,
        CODE_USABLE,
    ),
    'Gram.Lexer.InvalidKeywordName',
)
"""Raised when a keyword identifier violates lexical naming rules (S-11010)."""

LEXER_UNEXPECTED_CHARACTER: CodeError = CodeError(
    (
        CODE_NATIVE_ERROR,
        CODE_LEXER_ERROR,
        CODE_FATAL,
        CODE_DOCUMENTED_AND_TRACEABLE,
        CODE_REQUIRES_REPAIR,
    ),
    'Gram.Lexer.UnexpectedCharacter',
)
"""Raised when the lexer encounters an unrecognized character (S-11411)."""

LEXER_UNCLOSED_STRING: CodeError = CodeError(
    (
        CODE_NATIVE_ERROR,
        CODE_LEXER_ERROR,
        CODE_FATAL,
        CODE_DOCUMENTED_AND_TRACEABLE,
        CODE_REQUIRES_REPAIR,
    ),
    'Gram.Lexer.UnclosedString',
)
"""Raised when a string literal is left unclosed before EOL or EOF (S-11411)."""

LEXER_INDENTATION_MISMATCH: CodeError = CodeError(
    (
        CODE_NATIVE_ERROR,
        CODE_LEXER_ERROR,
        CODE_FATAL,
        CODE_DOCUMENTED_AND_TRACEABLE,
        CODE_REQUIRES_REPAIR,
    ),
    'Gram.Lexer.IndentationMismatch',
)
"""Raised when indentation levels do not match the active block stack (S-11411)."""

LEXER_INVALID_NUMBER: CodeError = CodeError(
    (
        CODE_NATIVE_ERROR,
        CODE_LEXER_ERROR,
        CODE_FATAL,
        CODE_DOCUMENTED_AND_TRACEABLE,
        CODE_REQUIRES_REPAIR,
    ),
    'Gram.Lexer.InvalidNumber',
)
"""Raised when a numeric literal is malformed (S-11411)."""

LEXER_WORDGROUP_ALREADY_EXISTS: CodeError = CodeError(
    (
        CODE_NATIVE_ERROR,
        CODE_LEXER_ERROR,
        CODE_MINOR,
        CODE_DOCUMENTED_AND_TRACEABLE,
        CODE_USABLE,
    ),
    'Gram.Lexer.WordGroupAlreadyExists',
)
"""Raised when creating a word group whose name is already registered (S-11010)."""

LEXER_WORDGROUP_NOT_FOUND: CodeError = CodeError(
    (
        CODE_NATIVE_ERROR,
        CODE_LEXER_ERROR,
        CODE_MINOR,
        CODE_DOCUMENTED_AND_TRACEABLE,
        CODE_USABLE,
    ),
    'Gram.Lexer.WordGroupNotFound',
)
"""Raised when referencing a word group that does not exist (S-11010)."""

LEXER_WORDGROUP_KEYWORD_NOT_REGISTERED: CodeError = CodeError(
    (
        CODE_NATIVE_ERROR,
        CODE_LEXER_ERROR,
        CODE_MINOR,
        CODE_DOCUMENTED_AND_TRACEABLE,
        CODE_USABLE,
    ),
    'Gram.Lexer.KeywordNotRegistered',
)
"""Raised when adding an unregistered keyword to a word group (S-11010)."""

LEXER_FILE_NOT_FOUND: CodeError = CodeError(
    (
        CODE_NATIVE_ERROR,
        CODE_LEXER_ERROR,
        CODE_MINOR,
        CODE_DOCUMENTED_AND_TRACEABLE,
        CODE_USABLE,
    ),
    'Gram.Lexer.FileNotFound',
)
"""Raised when the source file passed to the lexer cannot be found (S-11010)."""


# ==============================================================================
# 2. PARSER ENGINE ERRORS (Class: ParserError -> Prefix: PARSER_*)
# ==============================================================================

PARSER_UNEXPECTED_TOKEN: CodeError = CodeError(
    (
        CODE_NATIVE_ERROR,
        CODE_PARSER_ERROR,
        CODE_FATAL,
        CODE_DOCUMENTED_AND_TRACEABLE,
        CODE_REQUIRES_REPAIR,
    ),
    'Gram.Parser.UnexpectedToken',
)
"""Raised when the parser encounters a token that does not match the expected rule (S-12411)."""

PARSER_EARLY_EOF: CodeError = CodeError(
    (
        CODE_NATIVE_ERROR,
        CODE_PARSER_ERROR,
        CODE_FATAL,
        CODE_DOCUMENTED_AND_TRACEABLE,
        CODE_REQUIRES_REPAIR,
    ),
    'Gram.Parser.EarlyEOF',
)
"""Raised when the token stream reaches EOF while evaluating a mandatory rule (S-12411)."""

PARSER_NOT_STARTED: CodeError = CodeError(
    (
        CODE_NATIVE_ERROR,
        CODE_PARSER_ERROR,
        CODE_INTERNAL,
        CODE_DOCUMENTED_AND_TRACEABLE,
        CODE_REQUIRES_REPAIR,
    ),
    'Gram.Parser.NotStarted',
)
"""Raised when attempting to consume tokens on an uninitialized parser (S-12311)."""

PARSER_SYNTAX_ERROR: CodeError = CodeError(
    (
        CODE_NATIVE_ERROR,
        CODE_PARSER_ERROR,
        CODE_MINOR,
        CODE_DOCUMENTED,
        CODE_USABLE,
    ),
    'Gram.Parser.SyntaxError',
)
"""Raised on general syntactic mismatches during parsing (S-12000)."""


# ==============================================================================
# 3. GRAMMAR & COMBINATOR ERRORS (Class: GrammarError -> Prefix: GRAMMAR_*)
# ==============================================================================

GRAMMAR_ANY_NOT_IMPLEMENTED: CodeError = CodeError(
    (
        CODE_NATIVE_ERROR,
        CODE_GRAMMAR_ERROR,
        CODE_IMPLEMENTATION_ERROR,
        CODE_DOCUMENTED,
        CODE_SHOULD_REPAIR,
    ),
    'Gram.Combinator.NotImplemented',
)
"""Raised when invoking an unimplemented combinator or experimental feature (S-13102)."""

GRAMMAR_COMBINATOR_FAILED: CodeError = CodeError(
    (
        CODE_NATIVE_ERROR,
        CODE_GRAMMAR_ERROR,
        CODE_MINOR,
        CODE_DOCUMENTED_AND_TRACEABLE,
        CODE_USABLE,
    ),
    'Gram.Combinator.Failed',
)
"""Raised on a non-fatal recoverable failure during combinator matching (S-13010)."""

GRAMMAR_TOKENIZE_EMPTY_COMBINATORS: CodeError = CodeError(
    (
        CODE_NATIVE_ERROR,
        CODE_GRAMMAR_ERROR,
        CODE_FATAL,
        CODE_DOCUMENTED_AND_TRACEABLE,
        CODE_REQUIRES_REPAIR,
    ),
    'Gram.Combinator.TokenizeEmpty',
)
"""Raised when a Tokenize combinator is instantiated without child combinators (S-13411)."""

GRAMMAR_RULE_NOT_FOUND: CodeError = CodeError(
    (
        CODE_NATIVE_ERROR,
        CODE_GRAMMAR_ERROR,
        CODE_FATAL,
        CODE_DOCUMENTED_AND_TRACEABLE,
        CODE_REQUIRES_REPAIR,
    ),
    'Gram.Grammar.RuleNotFound',
)
"""Raised when a grammar rule reference (`Ref`) cannot be resolved (S-13411)."""

GRAMMAR_DUPLICATE_RULE: CodeError = CodeError(
    (
        CODE_NATIVE_ERROR,
        CODE_GRAMMAR_ERROR,
        CODE_FATAL,
        CODE_DOCUMENTED_AND_TRACEABLE,
        CODE_REQUIRES_REPAIR,
    ),
    'Gram.Grammar.DuplicateRule',
)
"""Raised when registering a grammar rule with an ID or name that already exists (S-13411)."""

GRAMMAR_RULE_PROTECTED_ID: CodeError = CodeError(
    (
        CODE_NATIVE_ERROR,
        CODE_GRAMMAR_ERROR,
        CODE_FATAL,
        CODE_DOCUMENTED_AND_TRACEABLE,
        CODE_REQUIRES_REPAIR,
    ),
    'Gram.Grammar.ProtectedRuleId',
)
"""Raised when attempting to override a protected core rule ID (0-20) (S-13411)."""

GRAMMAR_COMBINATOR_UNSUPPORTED: CodeError = CodeError(
    (
        CODE_NATIVE_ERROR,
        CODE_GRAMMAR_ERROR,
        CODE_FATAL,
        CODE_DOCUMENTED_AND_TRACEABLE,
        CODE_REQUIRES_REPAIR,
    ),
    'Gram.Combinator.Unsupported',
)
"""Raised when an unsupported combinator operation is invoked (S-13411)."""


# ==============================================================================
# 4. AST ERRORS (Class: ASTError -> Prefix: AST_*)
# ==============================================================================

AST_PROGRAM_RULE_NOT_FOUND: CodeError = CodeError(
    (
        CODE_NATIVE_ERROR,
        CODE_GRAMMAR_ERROR,
        CODE_FATAL,
        CODE_DOCUMENTED_AND_TRACEABLE,
        CODE_REQUIRES_REPAIR,
    ),
    'Gram.AST.ProgramRuleNotFound',
)
"""Raised when the root program entrypoint rule is missing when building the AST (S-13411)."""

AST_PROGRAM_INVALID_COMBINATOR: CodeError = CodeError(
    (
        CODE_NATIVE_ERROR,
        CODE_GRAMMAR_ERROR,
        CODE_MINOR,
        CODE_DOCUMENTED_AND_TRACEABLE,
        CODE_USABLE,
    ),
    'Gram.AST.ProgramInvalidCombinator',
)
"""Raised when the entrypoint rule uses an invalid combinator for AST generation (S-13010)."""

AST_DECLARATION_RULE_NOT_FOUND: CodeError = CodeError(
    (
        CODE_NATIVE_ERROR,
        CODE_GRAMMAR_ERROR,
        CODE_FATAL,
        CODE_DOCUMENTED_AND_TRACEABLE,
        CODE_REQUIRES_REPAIR,
    ),
    'Gram.AST.DeclarationRuleNotFound',
)
"""Raised when a required declaration rule is missing in the AST grammar catalog (S-13411)."""

AST_DECLARATOR_INVALID_TYPE: CodeError = CodeError(
    (
        CODE_NATIVE_ERROR,
        CODE_GRAMMAR_ERROR,
        CODE_FATAL,
        CODE_DOCUMENTED_AND_TRACEABLE,
        CODE_REQUIRES_REPAIR,
    ),
    'Gram.AST.DeclaratorInvalidType',
)
"""Raised when an AST declarator evaluates an unsupported type (S-13411)."""

AST_DECLARATOR_INVALID_ELEMENT: CodeError = CodeError(
    (
        CODE_NATIVE_ERROR,
        CODE_GRAMMAR_ERROR,
        CODE_FATAL,
        CODE_DOCUMENTED_AND_TRACEABLE,
        CODE_REQUIRES_REPAIR,
    ),
    'Gram.AST.DeclaratorInvalidElement',
)
"""Raised when an AST declarator contains an invalid child element (S-13411)."""


# ==============================================================================
# 5. SEMANTIC ERRORS (Class: SemanticError -> Prefix: SEMANTIC_*)
# ==============================================================================

SEMANTIC_TYPE_MISMATCH: CodeError = CodeError(
    (
        CODE_NATIVE_ERROR,
        CODE_SEMANTIC_ERROR,
        CODE_FATAL,
        CODE_DOCUMENTED_AND_TRACEABLE,
        CODE_REQUIRES_REPAIR,
    ),
    'Gram.Semantic.TypeMismatch',
)
"""Raised on incompatible type mismatches in expressions or assignments (S-14411)."""

SEMANTIC_UNDEFINED_SYMBOL: CodeError = CodeError(
    (
        CODE_NATIVE_ERROR,
        CODE_SEMANTIC_ERROR,
        CODE_FATAL,
        CODE_DOCUMENTED_AND_TRACEABLE,
        CODE_REQUIRES_REPAIR,
    ),
    'Gram.Semantic.UndefinedSymbol',
)
"""Raised when referencing an undeclared identifier, rule, or symbol (S-14411)."""

SEMANTIC_DUPLICATE_SYMBOL: CodeError = CodeError(
    (
        CODE_NATIVE_ERROR,
        CODE_SEMANTIC_ERROR,
        CODE_FATAL,
        CODE_DOCUMENTED_AND_TRACEABLE,
        CODE_REQUIRES_REPAIR,
    ),
    'Gram.Semantic.DuplicateSymbol',
)
"""Raised when redeclaring an existing symbol within the same lexical scope (S-14411)."""

SEMANTIC_INVALID_OPERATION: CodeError = CodeError(
    (
        CODE_NATIVE_ERROR,
        CODE_SEMANTIC_ERROR,
        CODE_FATAL,
        CODE_DOCUMENTED_AND_TRACEABLE,
        CODE_REQUIRES_REPAIR,
    ),
    'Gram.Semantic.InvalidOperation',
)
"""Raised when attempting an unsupported operation between operand types (S-14411)."""

SEMANTIC_SCOPE_VIOLATION: CodeError = CodeError(
    (
        CODE_NATIVE_ERROR,
        CODE_SEMANTIC_ERROR,
        CODE_FATAL,
        CODE_DOCUMENTED_AND_TRACEABLE,
        CODE_REQUIRES_REPAIR,
    ),
    'Gram.Semantic.ScopeViolation',
)
"""Raised when accessing a symbol outside its legal visibility scope (S-14411)."""

SEMANTIC_IMMUTABILITY_VIOLATION: CodeError = CodeError(
    (
        CODE_NATIVE_ERROR,
        CODE_SEMANTIC_ERROR,
        CODE_FATAL,
        CODE_DOCUMENTED_AND_TRACEABLE,
        CODE_REQUIRES_REPAIR,
    ),
    'Gram.Semantic.ImmutabilityViolation',
)
"""Raised when attempting to mutate or reassign an immutable semantic symbol (S-14411)."""


# ==============================================================================
# 6. COMPILATION & DSL ERRORS (Class: CompilationError -> Prefix: COMPILATION_*)
# ==============================================================================

COMPILATION_DSL_SYNTAX_ERROR: CodeError = CodeError(
    (
        CODE_NATIVE_ERROR,
        CODE_COMPILATION_ERROR,
        CODE_FATAL,
        CODE_DOCUMENTED_AND_TRACEABLE,
        CODE_REQUIRES_REPAIR,
    ),
    'Gram.DSL.SyntaxError',
)
"""Raised on syntax errors while parsing GramLang DSL specifications (S-15411)."""

COMPILATION_DSL_INCLUDE_NOT_FOUND: CodeError = CodeError(
    (
        CODE_NATIVE_ERROR,
        CODE_COMPILATION_ERROR,
        CODE_FATAL,
        CODE_DOCUMENTED_AND_TRACEABLE,
        CODE_REQUIRES_REPAIR,
    ),
    'Gram.DSL.IncludeNotFound',
)
"""Raised when a file or module referenced by an `include` directive is not found (S-15411)."""

COMPILATION_GLANG_INCLUDE_PLUGIN_NOT_LOADED: CodeError = CodeError(
    (
        CODE_NATIVE_ERROR,
        CODE_COMPILATION_ERROR,
        CODE_FATAL,
        CODE_DOCUMENTED_AND_TRACEABLE,
        CODE_REQUIRES_REPAIR,
    ),
    'Gram.DSL.IncludePluginNotLoaded',
)
"""Raised when including rules from a plugin that is not loaded (S-15411)."""

COMPILATION_GLANG_IMMUTABILITY_VIOLATION: CodeError = CodeError(
    (
        CODE_NATIVE_ERROR,
        CODE_COMPILATION_ERROR,
        CODE_FATAL,
        CODE_DOCUMENTED_AND_TRACEABLE,
        CODE_REQUIRES_REPAIR,
    ),
    'Gram.DSL.ImmutabilityViolation',
)
"""Raised when attempting to mutate an immutable DSL definition during compilation (S-15411)."""


# ==============================================================================
# 7. PLUGIN & MANIFEST ERRORS (Class: PluginError -> Prefix: PLUGIN_*)
# ==============================================================================

PLUGIN_MANIFEST_NOT_FOUND: CodeError = CodeError(
    (
        CODE_PLUGIN_ERROR,
        CODE_GRAMMAR_ERROR,
        CODE_FATAL,
        CODE_DOCUMENTED_AND_TRACEABLE,
        CODE_REQUIRES_REPAIR,
    ),
    'Gram.Plugin.ManifestNotFound',
)
"""Raised when `manifest.json` is missing from the plugin root directory (S-23411)."""

PLUGIN_MANIFEST_INVALID: CodeError = CodeError(
    (
        CODE_PLUGIN_ERROR,
        CODE_GRAMMAR_ERROR,
        CODE_FATAL,
        CODE_DOCUMENTED_AND_TRACEABLE,
        CODE_REQUIRES_REPAIR,
    ),
    'Gram.Plugin.ManifestInvalid',
)
"""Raised when a plugin manifest contains malformed JSON or missing required fields (S-23411)."""

PLUGIN_FOLDER_MISMATCH: CodeError = CodeError(
    (
        CODE_PLUGIN_ERROR,
        CODE_GRAMMAR_ERROR,
        CODE_FATAL,
        CODE_DOCUMENTED_AND_TRACEABLE,
        CODE_REQUIRES_REPAIR,
    ),
    'Gram.Plugin.FolderMismatch',
)
"""Raised when the plugin folder name does not match the manifest `name` field (S-23411)."""

PLUGIN_INCOMPATIBLE_GRAM_VERSION: CodeError = CodeError(
    (
        CODE_PLUGIN_ERROR,
        CODE_GRAMMAR_ERROR,
        CODE_FATAL,
        CODE_DOCUMENTED_AND_TRACEABLE,
        CODE_REQUIRES_REPAIR,
    ),
    'Gram.Plugin.IncompatibleGramVersion',
)
"""Raised when the installed Gram version does not satisfy the plugin's `gram_version` (S-23411)."""

PLUGIN_VENV_DISALLOWED: CodeError = CodeError(
    (
        CODE_PLUGIN_ERROR,
        CODE_GRAMMAR_ERROR,
        CODE_FATAL,
        CODE_DOCUMENTED_AND_TRACEABLE,
        CODE_REQUIRES_REPAIR,
    ),
    'Gram.Plugin.VenvDisallowed',
)
"""Raised when attempting to install plugin dependencies outside a virtual environment (S-23411)."""

PLUGIN_DEPENDENCY_NOT_FOUND: CodeError = CodeError(
    (
        CODE_PLUGIN_ERROR,
        CODE_GRAMMAR_ERROR,
        CODE_FATAL,
        CODE_DOCUMENTED_AND_TRACEABLE,
        CODE_REQUIRES_REPAIR,
    ),
    'Gram.Plugin.DependencyNotFound',
)
"""Raised when a required external plugin dependency is not installed (S-23411)."""

PLUGIN_DEPENDENCY_VERSION_MISMATCH: CodeError = CodeError(
    (
        CODE_PLUGIN_ERROR,
        CODE_GRAMMAR_ERROR,
        CODE_FATAL,
        CODE_DOCUMENTED_AND_TRACEABLE,
        CODE_REQUIRES_REPAIR,
    ),
    'Gram.Plugin.DependencyVersionMismatch',
)
"""Raised when an installed dependency version violates plugin constraints (S-23411)."""

PLUGIN_CAPABILITY_MISSING: CodeError = CodeError(
    (
        CODE_PLUGIN_ERROR,
        CODE_GRAMMAR_ERROR,
        CODE_FATAL,
        CODE_DOCUMENTED_AND_TRACEABLE,
        CODE_REQUIRES_REPAIR,
    ),
    'Gram.Plugin.CapabilityMissing',
)
"""Raised when a plugin performs an operation without declaring the required capability (S-23411)."""

PLUGIN_MAIN_NOT_FOUND: CodeError = CodeError(
    (
        CODE_PLUGIN_ERROR,
        CODE_GRAMMAR_ERROR,
        CODE_FATAL,
        CODE_DOCUMENTED_AND_TRACEABLE,
        CODE_REQUIRES_REPAIR,
    ),
    'Gram.Plugin.MainNotFound',
)
"""Raised when the main entrypoint file declared in the manifest does not exist (S-23411)."""

PLUGIN_LOADED_ERROR: CodeError = CodeError(
    (
        CODE_PLUGIN_ERROR,
        CODE_GRAMMAR_ERROR,
        CODE_FATAL,
        CODE_DOCUMENTED_AND_TRACEABLE,
        CODE_REQUIRES_REPAIR,
    ),
    'Gram.Plugin.LoadedError',
)
"""Raised when an unhandled exception occurs while importing or loading a plugin (S-23411)."""

PLUGIN_PROCESSED_ERROR: CodeError = CodeError(
    (
        CODE_PLUGIN_ERROR,
        CODE_GRAMMAR_ERROR,
        CODE_FATAL,
        CODE_DOCUMENTED_AND_TRACEABLE,
        CODE_REQUIRES_REPAIR,
    ),
    'Gram.Plugin.ProcessedError',
)
"""Raised when an error occurs during a plugin's rule processing cycle (S-23411)."""

PLUGIN_CONFIG_MUTATION_DENIED: CodeError = CodeError(
    (
        CODE_PLUGIN_ERROR,
        CODE_GRAMMAR_ERROR,
        CODE_FATAL,
        CODE_DOCUMENTED_AND_TRACEABLE,
        CODE_REQUIRES_REPAIR,
    ),
    'Gram.Plugin.ConfigMutationDenied',
)
"""Raised when a plugin attempts to modify protected Gram configuration settings (S-23411)."""

PLUGIN_CONFIG_REQUIREMENT_FAILED: CodeError = CodeError(
    (
        CODE_PLUGIN_ERROR,
        CODE_GRAMMAR_ERROR,
        CODE_FATAL,
        CODE_DOCUMENTED_AND_TRACEABLE,
        CODE_REQUIRES_REPAIR,
    ),
    'Gram.Plugin.ConfigRequirementFailed',
)
"""Raised when active configuration does not meet the plugin's `required_config` (S-23411)."""

PLUGIN_DUPLICATE_FOUND: CodeError = CodeError(
    (
        CODE_PLUGIN_ERROR,
        CODE_GRAMMAR_ERROR,
        CODE_MINOR,
        CODE_DOCUMENTED_AND_TRACEABLE,
        CODE_USABLE,
    ),
    'Gram.Plugin.DuplicateFound',
)
"""Raised when a duplicate plugin is discovered and ignored (S-23010)."""

PLUGIN_VERSION_MISMATCH_USE_INSTALL: CodeError = CodeError(
    (
        CODE_PLUGIN_ERROR,
        CODE_GRAMMAR_ERROR,
        CODE_FATAL,
        CODE_DOCUMENTED_AND_TRACEABLE,
        CODE_REQUIRES_REPAIR,
    ),
    'Gram.Plugin.VersionMismatchUseInstall',
)
"""Raised on plugin version mismatch requiring re-installation via the CLI (S-23411)."""

PLUGIN_PROTECTED_VIOLATION: CodeError = CodeError(
    (
        CODE_PLUGIN_ERROR,
        CODE_GRAMMAR_ERROR,
        CODE_FATAL,
        CODE_DOCUMENTED_AND_TRACEABLE,
        CODE_REQUIRES_REPAIR,
    ),
    'Gram.Plugin.ProtectedViolation',
)
"""Raised when attempting to modify or override a protected system plugin (S-23411)."""

PLUGIN_SYNTAX_ERROR: CodeError = CodeError(
    (
        CODE_PLUGIN_ERROR,
        CODE_GRAMMAR_ERROR,
        CODE_FATAL,
        CODE_DOCUMENTED_AND_TRACEABLE,
        CODE_REQUIRES_REPAIR,
    ),
    'Gram.Plugin.SyntaxError',
)
"""Raised when a plugin rule or combinator contains syntax errors (S-23411)."""

PLUGIN_DUPLICATE_DEPENDENCY: CodeError = CodeError(
    (
        CODE_PLUGIN_ERROR,
        CODE_GRAMMAR_ERROR,
        CODE_FATAL,
        CODE_DOCUMENTED_AND_TRACEABLE,
        CODE_REQUIRES_REPAIR,
    ),
    'Gram.Plugin.DuplicateDependency',
)
"""Raised when a plugin declares duplicate or conflicting dependencies (S-23411)."""

PLUGIN_REQUIREMENT_FILE_MISSING: CodeError = CodeError(
    (
        CODE_PLUGIN_ERROR,
        CODE_GRAMMAR_ERROR,
        CODE_FATAL,
        CODE_DOCUMENTED_AND_TRACEABLE,
        CODE_REQUIRES_REPAIR,
    ),
    'Gram.Plugin.RequirementFileMissing',
)
"""Raised when the `requirements.txt` file declared in the manifest is missing (S-23411)."""

PLUGIN_VALIDATION_FAILED: CodeError = CodeError(
    (
        CODE_PLUGIN_ERROR,
        CODE_GRAMMAR_ERROR,
        CODE_FATAL,
        CODE_DOCUMENTED_AND_TRACEABLE,
        CODE_REQUIRES_REPAIR,
    ),
    'Gram.Plugin.ValidationFailed',
)
"""Raised when structural or security validation of a plugin fails (S-23411)."""

PLUGIN_NOT_FOUND: CodeError = CodeError(
    (
        CODE_PLUGIN_ERROR,
        CODE_GRAMMAR_ERROR,
        CODE_FATAL,
        CODE_DOCUMENTED_AND_TRACEABLE,
        CODE_REQUIRES_REPAIR,
    ),
    'Gram.Plugin.NotFound',
)
"""Raised when a requested plugin cannot be found in active search paths (S-23411)."""


# ==============================================================================
# 8. SYSTEM / GENERIC ERRORS (Class: SystemError -> Prefix: SYSTEM_*)
# ==============================================================================

SYSTEM_UNKNOWN_ERROR: CodeError = CodeError(
    (
        CODE_UNKNOWN_ORIGIN,
        CODE_UNKNOWN_SCOPE,
        CODE_MINOR,
        CODE_NOT_DOCUMENTED,
        CODE_USABLE,
    ),
    'Gram.System.UnknownError',
)
"""Generic fallback error for unclassified failures lacking formal specification (S-00020)."""


# ==============================================================================
# CATALOG QUERY FUNCTIONS
# ==============================================================================

def all_errors() -> list[CodeError]:
    """
    Return a deduplicated list of all `CodeError` instances defined in the catalog.
    """
    current_module = sys.modules[__name__]
    seen_ids: set[int] = set()
    result: list[CodeError] = []
    for item in current_module.__dict__.values():
        if isinstance(item, CodeError) and id(item) not in seen_ids:
            seen_ids.add(id(item))
            result.append(item)
    return result


def get_error_by_code(
    code: int | tuple[int | str, ...] | str | CodeError,
) -> CodeError | None:
    """
    Look up an error in the official catalog by numeric code, OSGDC tuple,
    formatted string, or `CodeError` instance.
    """
    if isinstance(code, CodeError):
        for err in all_errors():
            if err == code:
                return err
        return None

    target_digits: str | None = None

    if isinstance(code, int):
        target_digits = f'{code:05d}'
    elif isinstance(code, tuple):
        target_digits = ''.join(str(item) for item in code)
    elif isinstance(code, str):
        clean = code.strip()
        if '-' in clean:
            after_dash = clean.split('-', 1)[1].strip()
            target_digits = after_dash.split()[0].split('·')[0].strip()
        else:
            target_digits = clean.split()[0].split('·')[0].strip()

    if target_digits is not None:
        for err in all_errors():
            if err.code_string == target_digits:
                return err

    return None


def get_error_by_name(name: str) -> CodeError | None:
    """
    Search the catalog for an error by its canonical qualified name
    (exact match first, followed by case-insensitive suffix match).
    """
    name_clean = name.strip()
    name_lower = name_clean.lower()
    catalog = all_errors()

    for err in catalog:
        if err.name == name_clean:
            return err

    for err in catalog:
        err_lower = err.name.lower()
        if err_lower == name_lower or err_lower.endswith(f'.{name_lower}'):
            return err

    return None


def get_errors_by_scope(scope: Codes | str | int) -> list[CodeError]:
    """Filter and return all catalog errors belonging to a specific OSGDC scope."""
    if isinstance(scope, Codes):
        target_val = scope.value_str
    elif isinstance(scope, int):
        target_val = str(scope)
    elif isinstance(scope, str):
        scope_map = {
            'unknown': '0',
            'lexer': '1',
            'parser': '2',
            'grammar': '3',
            'semantic': '4',
            'compilation': '5',
        }
        target_val = scope_map.get(scope.lower(), scope)
    else:
        return []

    return [
        err
        for err in all_errors()
        if len(err.code_string) >= 2 and err.code_string[1] == target_val
    ]


def get_errors_by_origin(origin: Codes | str | int) -> list[CodeError]:
    """Filter and return all catalog errors belonging to a specific OSGDC origin."""
    if isinstance(origin, Codes):
        target_val = origin.value_str
    elif isinstance(origin, int):
        target_val = str(origin)
    elif isinstance(origin, str):
        origin_map = {
            'unknown': '0',
            'native': '1',
            'plugin': '2',
        }
        target_val = origin_map.get(origin.lower(), origin)
    else:
        return []

    return [
        err
        for err in all_errors()
        if len(err.code_string) >= 1 and err.code_string[0] == target_val
    ]


__all__ = [
    'AST_DECLARATION_RULE_NOT_FOUND',
    'AST_DECLARATOR_INVALID_ELEMENT',
    'AST_DECLARATOR_INVALID_TYPE',
    'AST_PROGRAM_INVALID_COMBINATOR',
    # AST Catalog (AST_*)
    'AST_PROGRAM_RULE_NOT_FOUND',
    'CODE_COMPILATION_ERROR',
    'CODE_DOCUMENTED',
    'CODE_DOCUMENTED_AND_TRACEABLE',
    'CODE_FATAL',
    'CODE_GRAMMAR_ERROR',
    'CODE_IMPLEMENTATION_ERROR',
    'CODE_INTERNAL',
    'CODE_LEXER_ERROR',
    'CODE_MINOR',
    'CODE_NATIVE_ERROR',
    'CODE_NOT_DOCUMENTED',
    'CODE_OBSOLETE_ERROR',
    'CODE_PARSER_ERROR',
    'CODE_PLUGIN_ERROR',
    'CODE_REQUIRES_REPAIR',
    'CODE_SEMANTIC_ERROR',
    'CODE_SHOULD_REPAIR',
    # OSGDC Dimension Codes (CODE_*)
    'CODE_UNKNOWN',
    'CODE_UNKNOWN_ORIGIN',
    'CODE_UNKNOWN_SCOPE',
    'CODE_USABLE',
    'COMPILATION_DSL_INCLUDE_NOT_FOUND',
    # Compilation & DSL Catalog (COMPILATION_*)
    'COMPILATION_DSL_SYNTAX_ERROR',
    'COMPILATION_GLANG_IMMUTABILITY_VIOLATION',
    'COMPILATION_GLANG_INCLUDE_PLUGIN_NOT_LOADED',
    # Grammar & Combinator Catalog (GRAMMAR_*)
    'GRAMMAR_ANY_NOT_IMPLEMENTED',
    'GRAMMAR_COMBINATOR_FAILED',
    'GRAMMAR_COMBINATOR_UNSUPPORTED',
    'GRAMMAR_DUPLICATE_RULE',
    'GRAMMAR_RULE_NOT_FOUND',
    'GRAMMAR_RULE_PROTECTED_ID',
    'GRAMMAR_TOKENIZE_EMPTY_COMBINATORS',
    # Lexer Catalog (LEXER_*)
    'LEXER_EMPTY_KEYWORDS',
    'LEXER_FILE_NOT_FOUND',
    'LEXER_GROUP_NOT_FOUND',
    'LEXER_INDENTATION_MISMATCH',
    'LEXER_INVALID_NUMBER',
    'LEXER_KEYWORD_ALREADY_EXISTS',
    'LEXER_KEYWORD_INVALID_NAME',
    'LEXER_KEYWORD_NOT_FOUND',
    'LEXER_UNCLOSED_STRING',
    'LEXER_UNEXPECTED_CHARACTER',
    'LEXER_WORDGROUP_ALREADY_EXISTS',
    'LEXER_WORDGROUP_KEYWORD_NOT_REGISTERED',
    'LEXER_WORDGROUP_NOT_FOUND',
    'PARSER_EARLY_EOF',
    'PARSER_NOT_STARTED',
    'PARSER_SYNTAX_ERROR',
    # Parser Catalog (PARSER_*)
    'PARSER_UNEXPECTED_TOKEN',
    'PLUGIN_CAPABILITY_MISSING',
    'PLUGIN_CONFIG_MUTATION_DENIED',
    'PLUGIN_CONFIG_REQUIREMENT_FAILED',
    'PLUGIN_DEPENDENCY_NOT_FOUND',
    'PLUGIN_DEPENDENCY_VERSION_MISMATCH',
    'PLUGIN_DUPLICATE_DEPENDENCY',
    'PLUGIN_DUPLICATE_FOUND',
    'PLUGIN_FOLDER_MISMATCH',
    'PLUGIN_INCOMPATIBLE_GRAM_VERSION',
    'PLUGIN_LOADED_ERROR',
    'PLUGIN_MAIN_NOT_FOUND',
    'PLUGIN_MANIFEST_INVALID',
    # Plugin Catalog (PLUGIN_*)
    'PLUGIN_MANIFEST_NOT_FOUND',
    'PLUGIN_NOT_FOUND',
    'PLUGIN_PROCESSED_ERROR',
    'PLUGIN_PROTECTED_VIOLATION',
    'PLUGIN_REQUIREMENT_FILE_MISSING',
    'PLUGIN_SYNTAX_ERROR',
    'PLUGIN_VALIDATION_FAILED',
    'PLUGIN_VENV_DISALLOWED',
    'PLUGIN_VERSION_MISMATCH_USE_INSTALL',
    'SEMANTIC_DUPLICATE_SYMBOL',
    'SEMANTIC_IMMUTABILITY_VIOLATION',
    'SEMANTIC_INVALID_OPERATION',
    'SEMANTIC_SCOPE_VIOLATION',
    # Semantic Catalog (SEMANTIC_*)
    'SEMANTIC_TYPE_MISMATCH',
    'SEMANTIC_UNDEFINED_SYMBOL',
    # System Catalog (SYSTEM_*)
    'SYSTEM_UNKNOWN_ERROR',
    'ASTError',
    'CompilationError',
    # Domain Exception Classes
    'Error',
    'GrammarError',
    'LexerError',
    'ParserError',
    'PluginError',
    'SemanticError',
    'SystemError',
    # Query Functions
    'all_errors',
    'get_error_by_code',
    'get_error_by_name',
    'get_errors_by_origin',
    'get_errors_by_scope',
]