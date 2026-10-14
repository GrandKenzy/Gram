"""
VSIX Package Information and Manifest Registry (`gram.vsix.info`).
==================================================================
Provides declarative registry functions (`declare_info`, `set_package`,
`set_language`, `set_author`, `set_repository`, `set_meta`) for defining
VS Code extension metadata and manifest attributes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PackageInfo:
    """Configuration container for VS Code extension manifest attributes."""

    name: str = "gram-language"
    display_name: str = "Gram Language Support"
    description: str = "Language support for Gram DSL"
    version: str = "0.1.0"
    publisher: str = "gram-dsl"
    author: str | dict[str, str] = ""
    license: str = "MIT"
    repository: str | dict[str, str] = ""
    homepage: str = ""
    icon: str = ""
    keywords: list[str] = field(default_factory=lambda: ["gram", "dsl", "grammar", "compiler"])
    categories: list[str] = field(default_factory=lambda: ["Programming Languages", "Snippets"])
    vscode_engine: str = "^1.75.0"

    language_id: str = "gram"
    language_name: str = "Gram"
    file_extensions: list[str] = field(default_factory=lambda: [".gram", ".g"])
    aliases: list[str] = field(default_factory=lambda: ["Gram", "gram"])
    scope_name: str = "source.gram"
    entrypoint: str = "prueba:PROGRAM"

    def to_manifest(self) -> dict[str, Any]:
        """Convert container to VS Code package.json dictionary format."""
        manifest: dict[str, Any] = {
            "name": self.name.lower().strip().replace(" ", "-"),
            "displayName": self.display_name,
            "description": self.description,
            "version": self.version,
            "publisher": self.publisher,
            "main": "./extension.js",
            "activationEvents": [
                f"onLanguage:{self.language_id}"
            ],
            "engines": {
                "vscode": self.vscode_engine
            },
            "categories": self.categories,
            "contributes": {
                "languages": [
                    {
                        "id": self.language_id,
                        "aliases": self.aliases,
                        "extensions": self.file_extensions,
                        "configuration": "./language-configuration.json"
                    }
                ],
                "grammars": [
                    {
                        "language": self.language_id,
                        "scopeName": self.scope_name,
                        "path": f"./syntaxes/{self.language_id}.tmLanguage.json"
                    }
                ],
                "snippets": [
                    {
                        "language": self.language_id,
                        "path": "./snippets/snippets.json"
                    }
                ],
                "commands": [
                    {
                        "command": f"{self.language_id}.restartServer",
                        "title": f"{self.language_name}: Restart Language Server"
                    }
                ],
                "configuration": {
                    "title": self.display_name,
                    "properties": {
                        f"{self.language_id}.pythonPath": {
                            "type": "string",
                            "default": "python",
                            "description": f"Path to Python executable used for {self.display_name} Language Server."
                        },
                        f"{self.language_id}.entrypoint": {
                            "type": "string",
                            "default": self.entrypoint,
                            "description": f"Grammar entrypoint (module:Class) used by {self.display_name} Language Server."
                        }
                    }
                }
            }
        }

        if self.author:
            manifest["author"] = self.author
        if self.license:
            manifest["license"] = self.license
        if self.repository:
            if isinstance(self.repository, str):
                manifest["repository"] = {"type": "git", "url": self.repository}
            else:
                manifest["repository"] = self.repository
        if self.homepage:
            manifest["homepage"] = self.homepage
        if self.icon:
            manifest["icon"] = self.icon
        if self.keywords:
            manifest["keywords"] = self.keywords

        return manifest


_GLOBAL_PACKAGE_INFO: PackageInfo = PackageInfo()


def get_package_info() -> PackageInfo:
    """Return the global active PackageInfo instance."""
    return _GLOBAL_PACKAGE_INFO


def reset_package_info() -> PackageInfo:
    """Reset global PackageInfo to default state."""
    global _GLOBAL_PACKAGE_INFO
    _GLOBAL_PACKAGE_INFO = PackageInfo()
    return _GLOBAL_PACKAGE_INFO


def set_package(
    name: str,
    *,
    display_name: str | None = None,
    version: str = "0.1.0",
    publisher: str = "gram-dsl",
    description: str = "",
) -> PackageInfo:
    """Configure core package identification attributes."""
    pkg = get_package_info()
    pkg.name = name
    pkg.display_name = display_name or name.replace("-", " ").title()
    pkg.version = version
    pkg.publisher = publisher
    if description:
        pkg.description = description
    return pkg


def set_language(
    id: str,
    *,
    name: str | None = None,
    extensions: list[str] | None = None,
    aliases: list[str] | None = None,
    scope_name: str | None = None,
) -> PackageInfo:
    """Configure primary programming language identification."""
    pkg = get_package_info()
    clean_id = id.lower().strip()
    pkg.language_id = clean_id
    pkg.language_name = name or clean_id.capitalize()
    pkg.file_extensions = extensions if extensions is not None else [f".{clean_id}"]
    pkg.aliases = aliases if aliases is not None else [pkg.language_name, clean_id]
    pkg.scope_name = scope_name or f"source.{clean_id}"
    return pkg


def set_author(
    name: str,
    *,
    email: str = "",
    url: str = "",
) -> PackageInfo:
    """Configure package author metadata."""
    pkg = get_package_info()
    if email or url:
        author_dict = {"name": name}
        if email:
            author_dict["email"] = email
        if url:
            author_dict["url"] = url
        pkg.author = author_dict
    else:
        pkg.author = name
    return pkg


def set_repository(
    url: str,
    *,
    repo_type: str = "git",
) -> PackageInfo:
    """Configure VCS repository location."""
    pkg = get_package_info()
    pkg.repository = {"type": repo_type, "url": url}
    return pkg


def set_meta(
    *,
    license: str = "",
    homepage: str = "",
    icon: str = "",
    keywords: list[str] | None = None,
    categories: list[str] | None = None,
    vscode_engine: str = "",
) -> PackageInfo:
    """Configure auxiliary package metadata."""
    pkg = get_package_info()
    if license:
        pkg.license = license
    if homepage:
        pkg.homepage = homepage
    if icon:
        pkg.icon = icon
    if keywords is not None:
        pkg.keywords = keywords
    if categories is not None:
        pkg.categories = categories
    if vscode_engine:
        pkg.vscode_engine = vscode_engine
    return pkg


def declare_info(
    name: str | None = None,
    *,
    display_name: str | None = None,
    description: str | None = None,
    version: str | None = None,
    publisher: str | None = None,
    author: str | dict[str, str] | None = None,
    license: str | None = None,
    repository: str | dict[str, str] | None = None,
    homepage: str | None = None,
    icon: str | None = None,
    keywords: list[str] | None = None,
    categories: list[str] | None = None,
    language_id: str | None = None,
    language_name: str | None = None,
    file_extensions: list[str] | None = None,
    aliases: list[str] | None = None,
    scope_name: str | None = None,
    vscode_engine: str | None = None,
) -> PackageInfo:
    """
    Comprehensive declarative entry point to define all package attributes.
    """
    pkg = get_package_info()
    if name is not None:
        pkg.name = name
    if display_name is not None:
        pkg.display_name = display_name
    if description is not None:
        pkg.description = description
    if version is not None:
        pkg.version = version
    if publisher is not None:
        pkg.publisher = publisher
    if author is not None:
        pkg.author = author
    if license is not None:
        pkg.license = license
    if repository is not None:
        pkg.repository = repository
    if homepage is not None:
        pkg.homepage = homepage
    if icon is not None:
        pkg.icon = icon
    if keywords is not None:
        pkg.keywords = keywords
    if categories is not None:
        pkg.categories = categories
    if language_id is not None:
        pkg.language_id = language_id.lower().strip()
    if language_name is not None:
        pkg.language_name = language_name
    if file_extensions is not None:
        pkg.file_extensions = file_extensions
    if aliases is not None:
        pkg.aliases = aliases
    if scope_name is not None:
        pkg.scope_name = scope_name
    if vscode_engine is not None:
        pkg.vscode_engine = vscode_engine

    return pkg


__all__ = [
    "PackageInfo",
    "declare_info",
    "get_package_info",
    "reset_package_info",
    "set_author",
    "set_language",
    "set_meta",
    "set_package",
    "set_repository",
]
