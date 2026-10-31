# Installation Guide

Gram is a 100% pure-Python framework with zero external C or third-party runtime dependencies (requiring **Python 3.12+**).

Because Gram does not rely on PyPI packaging metadata (`pyproject.toml` / `setup.py`), it is designed to be installed and isolated via **[VNMA (Vendor Manager)](https://github.com/GrandKenzy/vnma)** or consumed directly via **Git** and `PYTHONPATH`.

---

## 1. Installing with VNMA (Recommended)

**[VNMA](https://github.com/GrandKenzy/vnma)** vendors dependencies directly into a local `vendor/` directory inside your project, providing hermetic `sys.path` isolation, lockfile reproducibility (`vnma.lock`), and automatic IDE path configuration for VS Code and PyCharm without duplicating full Python virtual environments.

> [!NOTE]
> Gram includes optional vendor metadata at the root of its repository (`name = "gram-framework3.0.0"`, `packname = "gram"`, `modules = ["gram"]`). When a host project uses VNMA, it can import `gram` directly (`import gram` or `from gram import lexer, parser, combinators`).
>
> Any questions, CLI usage details, or troubleshooting regarding **VNMA** itself belong to the official VNMA documentation: **[https://github.com/GrandKenzy/vnma](https://github.com/GrandKenzy/vnma)**.

### A. Configuring `vnma.toml` in Your Project

In your project's root `vnma.toml`, declare Gram under `[dependencies]` only if that host project already uses VNMA. You can install Gram from a remote GitHub branch, pin it to the immutable `v3.0.0` release tag, or link a local clone for real-time editable development:

```toml
[project]
name = "my-compiler"
version = "0.1.0"

[dependencies]

# Option 1: From GitHub (pinned to the v3.0.0 stable tag - recommended for reproducible builds)
gram-framework = { git = "https://github.com/GrandKenzy/Gram.git", tag = "v3.0.0" }

# Option 2: From GitHub (tracking the main branch)
# gramv2.0.0b = { git = "https://github.com/GrandKenzy/Gram.git", branch = "main" }

# Option 3: From a local directory (requires cloning Gram locally; reflects changes in real time)
# gram = { path = "~/Desktop/Gram", editable = true }

[dev-dependencies]

[tool.vnma]
vendor_dir = "vendor"
ide_integration = ["vscode", "pycharm"]
```

### B. Installing and Running via VNMA CLI

Once `vnma.toml` is configured, run:

```bash
# Resolve and vendor dependencies into ./vendor and generate vnma.lock:
vnma install
```

Or use `vnma` CLI commands directly:

```bash
# Install directly from the GitHub repository (main branch or v3.0.0 tag):
vnma install git+https://github.com/GrandKenzy/Gram.git@v3.0.0

# Or create a zero-copy live development link to a local Gram clone:
vnma link "~/Desktop/Gram"
```

Execute your compiler or script inside the isolated VNMA runtime:

```bash
vnma run main.py
```

---

## 2. Installing via Git and Release Tags (Manual)

If you are not using VNMA, you can clone the repository directly from GitHub and check out a specific release tag.

### A. Clone the Repository and Checkout a Tag

```bash
# Clone the repository:
git clone https://github.com/GrandKenzy/Gram.git
cd Gram

# List available release tags:
git tag -l

# Checkout the v3.0.0 stable release tag:
git checkout v3.0.0
```

Alternatively, clone the `v3.0.0` tag directly in a single step:

```bash
git clone --branch v3.0.0 --depth 1 https://github.com/GrandKenzy/Gram.git
```

### B. Expose `gram` on `PYTHONPATH`

Add the cloned `Gram` directory to your `PYTHONPATH` before running your Python scripts:

**PowerShell (Windows):**
```powershell
$env:PYTHONPATH = "C:\path\to\Gram"
python -m gram
```

**Bash (Linux / macOS):**
```bash
export PYTHONPATH="/path/to/Gram"
python3 -m gram
```

### C. Verify the Installation

Running `python -m gram` (or checking `gram.version()` in Python) prints the installed version:

```text
Gram Framework v3.0.0
```

```python
import gram

print(gram.__version__)       # "3.0.0"
print(gram.__version_info__)  # (3, 0, 0, 'final', 0)
```
