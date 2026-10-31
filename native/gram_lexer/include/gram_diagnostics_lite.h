#ifndef GRAM_DIAGNOSTICS_LITE_H
#define GRAM_DIAGNOSTICS_LITE_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * Severity levels for DiagnosticsLite.
 */
typedef enum {
    GRAM_DIAG_DEBUG  = 0,
    GRAM_DIAG_ADVICE = 1,
    GRAM_DIAG_WARN   = 2,
    GRAM_DIAG_ERROR  = 3,
    GRAM_DIAG_FATAL  = 4
} GramDiagSeverity;

/**
 * Execution control policies when diagnostics are emitted.
 */
typedef enum {
    GRAM_ERROR_POLICY_RECOVER       = 0,
    GRAM_ERROR_POLICY_STOP_ON_ERROR = 1,
    GRAM_ERROR_POLICY_STOP_ON_FATAL = 2
} GramErrorPolicy;

/**
 * Built-in lexical diagnostic codes (OSGDC-aligned).
 * Consumers may also define custom codes >= 1000 without inheritance.
 */
typedef enum {
    GRAM_DIAG_CODE_NONE                             = 0,
    GRAM_DIAG_CODE_EMPTY_KEYWORDS                   = 1,  /* S-11010 Gram.Lexer.EmptyKeywords */
    GRAM_DIAG_CODE_KEYWORD_ALREADY_EXISTS           = 2,  /* S-11010 Gram.Lexer.KeywordAlreadyExists */
    GRAM_DIAG_CODE_KEYWORD_NOT_FOUND                = 3,  /* S-11010 Gram.Lexer.KeywordNotFound */
    GRAM_DIAG_CODE_GROUP_NOT_FOUND                  = 4,  /* S-11010 Gram.Lexer.GroupNotFound */
    GRAM_DIAG_CODE_KEYWORD_INVALID_NAME             = 5,  /* S-11010 Gram.Lexer.InvalidKeywordName */
    GRAM_DIAG_CODE_UNEXPECTED_CHARACTER             = 6,  /* S-11411 Gram.Lexer.UnexpectedCharacter */
    GRAM_DIAG_CODE_UNCLOSED_STRING                  = 7,  /* S-11411 Gram.Lexer.UnclosedString */
    GRAM_DIAG_CODE_INDENTATION_MISMATCH             = 8,  /* S-11411 Gram.Lexer.IndentationMismatch */
    GRAM_DIAG_CODE_INVALID_NUMBER                   = 9,  /* S-11411 Gram.Lexer.InvalidNumber */
    GRAM_DIAG_CODE_WORDGROUP_ALREADY_EXISTS         = 10, /* S-11010 Gram.Lexer.WordGroupAlreadyExists */
    GRAM_DIAG_CODE_WORDGROUP_NOT_FOUND              = 11, /* S-11010 Gram.Lexer.WordGroupNotFound */
    GRAM_DIAG_CODE_WORDGROUP_KEYWORD_NOT_REGISTERED = 12, /* S-11010 Gram.Lexer.KeywordNotRegistered */
    GRAM_DIAG_CODE_FILE_NOT_FOUND                   = 13, /* S-11010 Gram.Lexer.FileNotFound */
    GRAM_DIAG_CODE_INVALID_UTF8                     = 14, /* S-11411 Invalid or truncated UTF-8 sequence */
    GRAM_DIAG_CODE_INVALID_COMMENT_SYMBOL           = 15, /* S-11411 Invalid comment symbol configured */
    GRAM_DIAG_CODE_CUSTOM_BASE                      = 1000
} GramDiagCode;

/**
 * Flat diagnostic record.
 * The sink does not own `message`; it is valid for the duration of the callback,
 * or copied into a caller-provided arena if using GramDiagBuffer with an arena.
 */
typedef struct {
    uint32_t code;
    GramDiagSeverity severity;
    uint32_t start;
    uint32_t end;
    uint32_t line;
    uint32_t column;
    const char *message;
    uint32_t message_length;
} GramDiagnostic;

/**
 * Callback signature for receiving diagnostics.
 */
typedef void (*GramDiagnosticSink)(
    void *context,
    const GramDiagnostic *diagnostic
);

/**
 * Lightweight sink interface.
 */
typedef struct {
    void *context;
    GramDiagnosticSink emit;
} GramDiagSink;

/**
 * Consumer-configurable severity override for any diagnostic code.
 */
typedef struct {
    uint32_t code;
    GramDiagSeverity severity;
} GramDiagSeverityOverride;

/**
 * Caller-owned external buffer and policy controller for DiagnosticsLite.
 * Performs zero heap allocations.
 */
typedef struct {
    GramDiagnostic *items;
    uint32_t capacity;
    uint32_t count;
    uint32_t total_emitted;
    uint32_t dropped_count;
    uint32_t max_diagnostics;
    GramErrorPolicy policy;
    uint8_t halted;
    uint32_t error_count;
    uint32_t fatal_count;
    const GramDiagSeverityOverride *overrides;
    uint32_t override_count;
    GramDiagSink user_sink;
    char *message_arena;
    uint32_t message_arena_capacity;
    uint32_t message_arena_used;
} GramDiagBuffer;

/**
 * Return a no-op null sink.
 */
GramDiagSink gram_diag_null_sink(void);

/**
 * Initialize a caller-owned diagnostic buffer.
 */
void gram_diag_buffer_init(
    GramDiagBuffer *buffer,
    GramDiagnostic *storage,
    uint32_t capacity,
    GramErrorPolicy policy
);

/**
 * Reset counts and state on an existing diagnostic buffer.
 */
void gram_diag_buffer_reset(GramDiagBuffer *buffer);

/**
 * Attach an optional caller-owned character arena to persist message strings.
 */
void gram_diag_buffer_set_message_arena(
    GramDiagBuffer *buffer,
    char *arena,
    uint32_t capacity
);

/**
 * Configure a hard maximum on emitted diagnostics (0 = unlimited up to capacity).
 */
void gram_diag_buffer_set_max_limit(
    GramDiagBuffer *buffer,
    uint32_t max_diagnostics
);

/**
 * Configure per-code severity overrides.
 */
void gram_diag_buffer_set_overrides(
    GramDiagBuffer *buffer,
    const GramDiagSeverityOverride *overrides,
    uint32_t override_count
);

/**
 * Chain an additional user callback sink to a diagnostic buffer.
 */
void gram_diag_buffer_set_user_sink(
    GramDiagBuffer *buffer,
    GramDiagSink user_sink
);

/**
 * Wrap a GramDiagBuffer as a GramDiagSink.
 */
GramDiagSink gram_diag_buffer_as_sink(GramDiagBuffer *buffer);

/**
 * Resolve the effective severity for a code given an override table.
 */
GramDiagSeverity gram_diag_resolve_severity(
    uint32_t code,
    GramDiagSeverity default_severity,
    const GramDiagSeverityOverride *overrides,
    uint32_t override_count
);

/**
 * Return 1 if the given severity and policy require stopping execution, 0 otherwise.
 */
int gram_diag_should_halt(GramDiagSeverity severity, GramErrorPolicy policy);

/**
 * Return 1 if `sink` is backed by a GramDiagBuffer that has entered the halted state,
 * or -1 if `sink` is not a GramDiagBuffer sink.
 */
int gram_diag_sink_is_halted(const GramDiagSink *sink);

/**
 * Emit a diagnostic to a sink (safe if sink or sink->emit is NULL).
 */
void gram_diag_emit(
    const GramDiagSink *sink,
    uint32_t code,
    GramDiagSeverity severity,
    uint32_t start,
    uint32_t end,
    uint32_t line,
    uint32_t column,
    const char *message,
    uint32_t message_length
);

#ifdef __cplusplus
}
#endif

#endif /* GRAM_DIAGNOSTICS_LITE_H */
