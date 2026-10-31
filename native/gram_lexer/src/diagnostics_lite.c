#include "../include/gram_diagnostics_lite.h"
#include <string.h>

static void gram_diag_null_emit(void *context, const GramDiagnostic *diagnostic) {
    (void)context;
    (void)diagnostic;
}

GramDiagSink gram_diag_null_sink(void) {
    GramDiagSink sink;
    sink.context = NULL;
    sink.emit = gram_diag_null_emit;
    return sink;
}

GramDiagSeverity gram_diag_resolve_severity(
    uint32_t code,
    GramDiagSeverity default_severity,
    const GramDiagSeverityOverride *overrides,
    uint32_t override_count
) {
    if (overrides != NULL && override_count > 0) {
        for (uint32_t i = 0; i < override_count; ++i) {
            if (overrides[i].code == code) {
                return overrides[i].severity;
            }
        }
    }
    return default_severity;
}

int gram_diag_should_halt(GramDiagSeverity severity, GramErrorPolicy policy) {
    if (policy == GRAM_ERROR_POLICY_STOP_ON_ERROR) {
        return (severity >= GRAM_DIAG_ERROR) ? 1 : 0;
    }
    if (policy == GRAM_ERROR_POLICY_STOP_ON_FATAL) {
        return (severity >= GRAM_DIAG_FATAL) ? 1 : 0;
    }
    return 0;
}

static void gram_diag_buffer_emit_cb(void *context, const GramDiagnostic *diagnostic) {
    if (context == NULL || diagnostic == NULL) {
        return;
    }
    GramDiagBuffer *buffer = (GramDiagBuffer *)context;

    GramDiagSeverity effective_severity = gram_diag_resolve_severity(
        diagnostic->code,
        diagnostic->severity,
        buffer->overrides,
        buffer->override_count
    );

    if (effective_severity == GRAM_DIAG_ERROR) {
        buffer->error_count += 1;
    } else if (effective_severity == GRAM_DIAG_FATAL) {
        buffer->fatal_count += 1;
    }

    if (gram_diag_should_halt(effective_severity, buffer->policy)) {
        buffer->halted = 1;
    }

    if (buffer->max_diagnostics > 0 && buffer->total_emitted >= buffer->max_diagnostics) {
        buffer->total_emitted += 1;
        buffer->dropped_count += 1;
        return;
    }

    buffer->total_emitted += 1;

    GramDiagnostic record = *diagnostic;
    record.severity = effective_severity;

    if (buffer->message_arena != NULL && record.message != NULL && record.message_length > 0) {
        uint32_t needed = record.message_length + 1u;
        if (buffer->message_arena_used + needed <= buffer->message_arena_capacity) {
            char *dest = buffer->message_arena + buffer->message_arena_used;
            memcpy(dest, record.message, record.message_length);
            dest[record.message_length] = '\0';
            record.message = dest;
            buffer->message_arena_used += needed;
        }
    }

    if (buffer->items != NULL && buffer->count < buffer->capacity) {
        buffer->items[buffer->count] = record;
        buffer->count += 1;
    } else {
        buffer->dropped_count += 1;
    }

    if (buffer->user_sink.emit != NULL) {
        buffer->user_sink.emit(buffer->user_sink.context, &record);
    }
}

void gram_diag_buffer_init(
    GramDiagBuffer *buffer,
    GramDiagnostic *storage,
    uint32_t capacity,
    GramErrorPolicy policy
) {
    if (buffer == NULL) {
        return;
    }
    memset(buffer, 0, sizeof(GramDiagBuffer));
    buffer->items = storage;
    buffer->capacity = capacity;
    buffer->policy = policy;
}

void gram_diag_buffer_reset(GramDiagBuffer *buffer) {
    if (buffer == NULL) {
        return;
    }
    buffer->count = 0;
    buffer->total_emitted = 0;
    buffer->dropped_count = 0;
    buffer->halted = 0;
    buffer->error_count = 0;
    buffer->fatal_count = 0;
    buffer->message_arena_used = 0;
}

void gram_diag_buffer_set_message_arena(
    GramDiagBuffer *buffer,
    char *arena,
    uint32_t capacity
) {
    if (buffer == NULL) {
        return;
    }
    buffer->message_arena = arena;
    buffer->message_arena_capacity = capacity;
    buffer->message_arena_used = 0;
}

void gram_diag_buffer_set_max_limit(
    GramDiagBuffer *buffer,
    uint32_t max_diagnostics
) {
    if (buffer == NULL) {
        return;
    }
    buffer->max_diagnostics = max_diagnostics;
}

void gram_diag_buffer_set_overrides(
    GramDiagBuffer *buffer,
    const GramDiagSeverityOverride *overrides,
    uint32_t override_count
) {
    if (buffer == NULL) {
        return;
    }
    buffer->overrides = overrides;
    buffer->override_count = override_count;
}

void gram_diag_buffer_set_user_sink(
    GramDiagBuffer *buffer,
    GramDiagSink user_sink
) {
    if (buffer == NULL) {
        return;
    }
    buffer->user_sink = user_sink;
}

GramDiagSink gram_diag_buffer_as_sink(GramDiagBuffer *buffer) {
    GramDiagSink sink;
    sink.context = buffer;
    sink.emit = (buffer != NULL) ? gram_diag_buffer_emit_cb : gram_diag_null_emit;
    return sink;
}

int gram_diag_sink_is_halted(const GramDiagSink *sink) {
    if (sink != NULL && sink->emit == gram_diag_buffer_emit_cb && sink->context != NULL) {
        const GramDiagBuffer *buffer = (const GramDiagBuffer *)sink->context;
        return (int)buffer->halted;
    }
    return -1;
}

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
) {
    if (sink == NULL || sink->emit == NULL) {
        return;
    }
    GramDiagnostic diag;
    diag.code = code;
    diag.severity = severity;
    diag.start = start;
    diag.end = end;
    diag.line = line;
    diag.column = column;
    diag.message = message;
    diag.message_length = message_length;
    sink->emit(sink->context, &diag);
}
