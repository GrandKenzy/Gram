"""
VSIX Packaging and Local Deployment Controller (`gram.vsix.packer`).
=====================================================================
Builds standalone Open Packaging Conventions (OPC) `.vsix` archive files
without external Node.js dependencies, deploys them directly to the user's
VS Code extensions directory, and provides the `up()` lifecycle launcher.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import zipfile
from pathlib import Path
from typing import Any

from gram.vsix.info import get_package_info


def find_vscode_cli() -> str | None:
    """Locate the `code` executable in PATH or standard installation directories."""
    cli = shutil.which("code")
    if cli:
        return cli

    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        candidates = [
            Path(local_app_data) / "Programs" / "Microsoft VS Code" / "bin" / "code.cmd",
            Path("C:/Program Files/Microsoft VS Code/bin/code.cmd"),
            Path("C:/Program Files (x86)/Microsoft VS Code/bin/code.cmd"),
        ]
        for candidate in candidates:
            if candidate.exists():
                return str(candidate)

    return None


def get_vscode_extensions_dir() -> Path:
    """Return user's standard VS Code extensions directory path."""
    return Path.home() / ".vscode" / "extensions"


def pack_vsix(
    extension_dir: Path | str = "./vscode_extension",
    output_path: Path | str | None = None,
) -> Path:
    """
    Assemble and compress a standard `.vsix` extension package without Node.js.

    Args:
        extension_dir (Path | str): Source directory containing `package.json`.
        output_path (Path | str | None): Target path for the `.vsix` bundle.

    Returns:
        Path: Absolute path of the generated `.vsix` file.
    """
    src_dir = Path(extension_dir).resolve()
    pkg_file = src_dir / "package.json"
    if not pkg_file.exists():
        raise FileNotFoundError(f"Missing package.json in extension directory: {src_dir}")

    with open(pkg_file, "r", encoding="utf-8") as f:
        pkg_manifest = json.load(f)

    name = pkg_manifest.get("name", "extension")
    version = pkg_manifest.get("version", "0.1.0")
    publisher = pkg_manifest.get("publisher", "publisher")
    display_name = pkg_manifest.get("displayName", name)
    description = pkg_manifest.get("description", "")

    content_types_xml = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
        '  <Default Extension="json" ContentType="application/json" />\n'
        '  <Default Extension="vsixmanifest" ContentType="text/xml" />\n'
        "</Types>"
    )

    vsix_manifest_xml = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<PackageManifest Version="2.0.0" xmlns="http://schemas.microsoft.com/developer/vsx-schema/2011" '
        'xmlns:d="http://schemas.microsoft.com/developer/vsx-schema-design/2011">\n'
        "  <Metadata>\n"
        f'    <Identity Id="{name}" Version="{version}" Publisher="{publisher}" />\n'
        f"    <DisplayName>{display_name}</DisplayName>\n"
        f'    <Description xml:space="preserve">{description}</Description>\n'
        "    <Categories>Programming Languages,Snippets</Categories>\n"
        "  </Metadata>\n"
        "  <Installation>\n"
        '    <InstallationTarget Id="Microsoft.VisualStudio.Code" />\n'
        "  </Installation>\n"
        "  <Dependencies />\n"
        "  <Assets>\n"
        '    <Asset Type="Microsoft.VisualStudio.Code.Manifest" Path="extension/package.json" Addressable="true" />\n'
        "  </Assets>\n"
        "</PackageManifest>"
    )

    if output_path is None:
        target_file = src_dir.parent / f"{name}-{version}.vsix"
    else:
        target_file = Path(output_path).resolve()

    with zipfile.ZipFile(target_file, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types_xml)
        zf.writestr("extension.vsixmanifest", vsix_manifest_xml)

        for item in src_dir.rglob("*"):
            if item.is_file():
                rel_path = item.relative_to(src_dir)
                zf.write(item, f"extension/{rel_path.as_posix()}")

    return target_file


def install_extension(
    extension_dir: Path | str = "./vscode_extension",
    vsix_file: Path | str | None = None,
    *,
    force: bool = True,
) -> dict[str, Any]:
    """
    Install extension into VS Code via CLI and user extensions directory sync.
    """
    src_dir = Path(extension_dir).resolve()
    pkg_file = src_dir / "package.json"
    if not pkg_file.exists():
        raise FileNotFoundError(f"Missing package.json in {src_dir}")

    with open(pkg_file, "r", encoding="utf-8") as f:
        pkg_manifest = json.load(f)

    name = pkg_manifest.get("name", "extension")
    version = pkg_manifest.get("version", "0.1.0")
    publisher = pkg_manifest.get("publisher", "publisher")

    target_ext_dir = get_vscode_extensions_dir() / f"{publisher}.{name}-{version}"
    target_ext_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src_dir, target_ext_dir, dirs_exist_ok=True)

    cli_result = None
    code_bin = find_vscode_cli()
    if code_bin and vsix_file and Path(vsix_file).exists():
        cmd = [code_bin, "--install-extension", str(Path(vsix_file).resolve())]
        if force:
            cmd.append("--force")
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            cli_result = {"returncode": res.returncode, "stdout": res.stdout, "stderr": res.stderr}
        except Exception as e:
            cli_result = {"error": str(e)}

    return {
        "installed": True,
        "extension_id": f"{publisher}.{name}",
        "version": version,
        "direct_path": target_ext_dir,
        "cli_result": cli_result,
    }


def launch_vscode(target_file: Path | str | None = None) -> bool:
    """Open VS Code focusing on target_file if code executable is available."""
    code_bin = find_vscode_cli()
    if not code_bin:
        return False

    cmd = [code_bin]
    if target_file is not None and Path(target_file).exists():
        cmd.append(str(Path(target_file).resolve()))

    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False


def up(
    target: Any = "./vscode_extension",
    *,
    install: bool = True,
    launch: bool = False,
    target_file: Path | str | None = None,
    pack: bool = True,
) -> dict[str, Any]:
    """
    Convenience deployment command to package, install, and preview the VS Code extension.

    Args:
        target: Path to extension directory or VSIXGenerator instance.
        install: If True, registers the extension in VS Code.
        launch: If True, opens VS Code with target_file.
        target_file: Sample code file to open for testing.
        pack: If True, compiles the .vsix archive package.

    Returns:
        dict[str, Any]: Details of the build, package, and installation status.
    """
    from gram.vsix.generator import VSIXGenerator

    if isinstance(target, VSIXGenerator):
        gen_paths = target.export("./vscode_extension")
        ext_dir = Path("./vscode_extension").resolve()
    elif hasattr(target, "items") and "meta" in target and "rules" in target:
        generator = VSIXGenerator(target)
        gen_paths = generator.export("./vscode_extension")
        ext_dir = Path("./vscode_extension").resolve()
    else:
        ext_dir = Path(target).resolve()

    vsix_path = None
    if pack:
        vsix_path = pack_vsix(ext_dir)

    install_info = None
    if install:
        install_info = install_extension(ext_dir, vsix_path)

    launched = False
    if launch:
        launched = launch_vscode(target_file)

    return {
        "extension_dir": ext_dir,
        "vsix_file": vsix_path,
        "install_info": install_info,
        "launched": launched,
    }


__all__ = [
    "find_vscode_cli",
    "get_vscode_extensions_dir",
    "install_extension",
    "launch_vscode",
    "pack_vsix",
    "up",
]
