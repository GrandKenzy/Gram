# CJSON (C-Style JSON con Gram)

CJSON es una variante de JSON enriquecida creada con el motor léxico y sintáctico de **Gram**. Permite:
1. **Comentarios de una línea con `//`** (estilo C).
2. **Definición de variables** numéricas (`int`, `float`) y cadenas de texto (`string`).
3. **Cálculos y expresiones** aritméticas (`+`, `-`, `*`, `/`, `%`, `**`, `//`) y concatenación de cadenas.
4. **Herencia y extensión** modular de otros archivos JSON mediante la directiva `extend: "ruta.json"`.

---

## Ejecución Rápida

```bash
# Compilar el archivo de ejemplo sample.cjson
python examples/cjson/main.py

# O compilar cualquier archivo .cjson / .sjson
python examples/cjson/main.py mi_archivo.cjson
```

---

## Ejemplo de Documento `.cjson`

```cjson
// Variables globales
let base_port = 8000
let host = "gram.dev"

{
    // Extender configuración base
    extend: "base_config.json",

    // Variables locales
    let offset = 80,

    // Expresiones evaluadas en tiempo de compilación
    "url": "https://" + host,
    "port": base_port + offset,
    "workers": (100 / 2) + 10
}
```
