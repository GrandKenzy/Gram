# SJSON (Super JSON con Gram Framework)

**SJSON (Super JSON)** es un superconjunto enriquecido de JSON implementado con el motor de combinadores y análisis sintáctico de **Gram**.

Combina la legibilidad y universalidad de JSON con capacidades avanzadas de preprocesamiento, compilando de forma determinista a JSON estándar compatible con cualquier analizador JSON (RFC 8259).

---

## Características de SJSON

1. **Variables Numéricas y Cadenas Exclusivamente:**
   Permite definir constantes reutilizables con `let` o `var` (solo tipos `int`, `float` y `string`).
   ```sjson
   let port = 8080
   let host = "gram.dev"
   ```

2. **Cálculos y Expresiones Aritméticas:**
   Evaluación en tiempo de compilación con precedencia de operadores (`+`, `-`, `*`, `/`, `%`, unarios, paréntesis y concatenación de strings):
   ```sjson
   "timeout_ms": 15 * 1000,
   "endpoint": "https://" + host + "/api"
   ```

3. **Comentarios de una Línea con `//`:**
   Permite documentar cualquier parte de la configuración sin alterar el JSON resultante.

4. **Herencia y Composición con `{ extend: "ruta.json" }`:**
   Importa y fusiona recursivamente configuraciones base de archivos JSON o SJSON externos:
   ```sjson
   {
       extend: "base_config.json",
       "override_key": 42
   }
   ```

---

## Ejecución Rápida

```bash
# Compilar el archivo de ejemplo sample.sjson
python examples/sjson/main.py

# O compilar cualquier archivo .sjson externo
python examples/sjson/main.py ruta/a/tu_archivo.sjson
```

O mediante la CLI de SJSON:

```bash
python -m sjson compile examples/sjson/sample.sjson
```

---

## Ejemplo de Documento `sample.sjson`

```sjson
// Variables globales
let base_port = 8000
let host = "gram.dev"

{
    // Extender configuración base
    extend: "base_config.json",

    // Variables locales
    let offset = 80,

    // Expresiones evaluadas en compilación
    "service_url": "https://" + host,
    "port": base_port + offset,
    "max_workers": (100 / 2) + 10
}
```

Al compilarse, devuelve un JSON estándar:

```json
{
  "service_url": "https://gram.dev",
  "port": 8080,
  "max_workers": 60
}
```
