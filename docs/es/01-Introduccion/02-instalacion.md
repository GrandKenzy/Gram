# Guía de Instalación

Gram es un framework desarrollado 100% en Python puro, sin librerías externas de C ni dependencias de terceros en tiempo de ejecución (requiere **Python 3.12+**).

Al no requerir metadatos de empaquetado PyPI (`pyproject.toml` / `setup.py`), Gram está diseñado para gestionarse y aislarse mediante **[VNMA (Vendor Manager)](https://github.com/GrandKenzy/vnma)** o consumirse directamente mediante **Git** y `PYTHONPATH`.

---

## 1. Instalación con VNMA (Recomendado)

**[VNMA](https://github.com/GrandKenzy/vnma)** descarga y aloja las dependencias directamente dentro de la carpeta local `vendor/` de tu proyecto, proporcionando aislamiento hermético en `sys.path`, reproducibilidad estricta mediante archivo de bloqueo (`vnma.lock`) y configuración automática de rutas para editores como VS Code y PyCharm sin necesidad de duplicar entornos virtuales enteros (`venv`).

> [!NOTE]
> Gram incluye metadata opcional de vendor en la raíz del repositorio (`name = "gram-framework3.0.0"`, `packname = "gram"`, `modules = ["gram"]`). Si un proyecto host usa VNMA, puede importar `gram` directamente (`import gram` o `from gram import lexer, parser, combinators`).
>
> Para cualquier consulta, comandos del CLI o especificaciones avanzadas sobre **VNMA**, consulta la documentación oficial y su repositorio: **[https://github.com/GrandKenzy/vnma](https://github.com/GrandKenzy/vnma)**.

### A. Configuración en `vnma.toml`

En el archivo `vnma.toml` de la raíz de tu proyecto, declara Gram bajo `[dependencies]` solo si ese proyecto host ya usa VNMA. Puedes instalar Gram desde una rama remota de GitHub, fijarlo al tag estable `v3.0.0` o vincular una copia local para desarrollo editable en tiempo real:

```toml
[project]
name = "mi-compilador"
version = "0.1.0"

[dependencies]

# Opción 1: Desde GitHub fijado al tag estable v3.0.0 (recomendado para builds reproducibles)
gram-framework = { git = "https://github.com/GrandKenzy/Gram.git", tag = "v3.0.0" }

# Opción 2: Desde GitHub siguiendo la rama principal
# gramv2.0.0b = { git = "https://github.com/GrandKenzy/Gram.git", branch = "main" }

# Opción 3: Desde una ruta local (refleja cambios en vivo al editar Gram)
# gram = { path = "~/Desktop/Gram", editable = true }

[dev-dependencies]

[tool.vnma]
vendor_dir = "vendor"
ide_integration = ["vscode", "pycharm"]
```

### B. Comandos del CLI de VNMA

Una vez configurado `vnma.toml`, ejecuta:

```bash
# Descarga e instala las dependencias en ./vendor y genera vnma.lock:
vnma install
```

O instala directamente desde la línea de comandos de VNMA:

```bash
# Instala desde GitHub en una sola orden:
vnma install git+https://github.com/GrandKenzy/Gram.git@v3.0.0

# O crea un enlace editable de copia cero hacia tu clon local:
vnma link "~/Desktop/Gram"
```

Ejecuta tu código dentro del entorno gestionado por VNMA:

```bash
vnma run main.py
```

---

## 2. Instalación Manual con Git y Tags de Lanzamiento

Si prefieres no utilizar VNMA, puedes clonar el repositorio directamente desde GitHub y situarte en el tag deseado.

### A. Clonar y cambiar al tag

```bash
# Clonar el repositorio:
git clone https://github.com/GrandKenzy/Gram.git
cd Gram

# Ver los tags disponibles:
git tag -l

# Cambiar al tag estable v3.0.0:
git checkout v3.0.0
```

O clonar directamente el tag en un solo comando:

```bash
git clone --branch v3.0.0 --depth 1 https://github.com/GrandKenzy/Gram.git
```

### B. Añadir Gram a `PYTHONPATH`

Agrega el directorio raíz de Gram a tu variable de entorno `PYTHONPATH`:

**PowerShell (Windows):**
```powershell
$env:PYTHONPATH = "C:\ruta\hacia\Gram"
python -m gram
```

**Bash (Linux / macOS):**
```bash
export PYTHONPATH="/ruta/hacia/Gram"
python3 -m gram
```

### C. Verificar la Instalación

Ejecutar `python -m gram` (o consultar `gram.version()` desde Python) imprime la versión activa:

```text
Gram Framework v3.0.0
```

```python
import gram

print(gram.__version__)       # "3.0.0"
print(gram.__version_info__)  # (3, 0, 0, 'final', 0)
```
