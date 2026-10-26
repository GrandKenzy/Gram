# Plan de rendimiento de Gram

Este plan pertenece exclusivamente a Gram. Busca mejorar el motor genérico de
lexado, parsing, backtracking y diagnóstico sin introducir reglas, tokens ni
suposiciones propias de ningún lenguaje consumidor.

## Objetivos

1. Reducir el coste de errores especulativos, especialmente la resolución
   repetida de rutas de origen.
2. Permitir elegir el nivel de telemetría del parser sin romper el valor
   histórico por defecto.
3. Reducir las copias realizadas en cada checkpoint del raytracing.
4. Mantener pruebas de regresión y un benchmark reproducible con una gramática
   mínima y genérica.

## Implementación

- `Error.origin_error` usa una caché acotada por nombre de archivo y directorio
  de trabajo.
- `Parser.parse(..., trace=...)` y `Session.parse(..., trace=...)` aceptan
  `off`, `basic` o `detailed`; el valor predeterminado continúa siendo
  `basic` para conservar compatibilidad.
- `RayTracing` guarda referencias, longitudes y rutas inmutables en los
  checkpoints. La copia de listas se realiza solamente al restaurar.
- `benchmarks/parser_scaling.py` mide declaraciones genéricas de Gram en
  varios tamaños y niveles de trazado.
- `tests/test_performance_features.py` cubre modos de trazado, forwarding de
  sesiones, restauración de snapshots y caché de rutas.

## Siguiente fase

Después de medir esta base, revisar los puntos calientes restantes con
`cProfile` y optimizar solamente cambios respaldados por perfiles. Cualquier
optimización debe conservar la semántica pública de combinadores, diagnósticos,
backtracking y sesiones.
