"""
Analizador y Enrutador de Comandos CLI de Plugins (`gram.plugins.manager.commands_parser`).
========================================================================================
Permite que los plugins extiendan dinámicamente la herramienta de línea de comandos de Gram
definiendo comandos en la carpeta `commands/commands.json` y ejecutables en `commands/*.py`.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from gram import config


def parse_struct_to_argparse(parser: argparse.ArgumentParser, struct_str: str) -> None:
    """
    Traduce una cadena descriptiva `struct` (ej. "%file% [--out %out%]")
    a parámetros formales de argparse.
    """
    if not struct_str or not struct_str.strip():
        return

    # 1. Detectar banderas y opciones entre corchetes, ej: [--shout] o [--out %out%]
    optionals = re.findall(r'\[(.*?)\]', struct_str)

    # 2. Remover las opciones para aislar los argumentos posicionales
    pos_str = re.sub(r'\[.*?\]', '', struct_str)
    positionals = re.findall(r'%(\w+)%', pos_str)

    for pos in positionals:
        parser.add_argument(pos, help=f"Parámetro posicional: {pos}")

    for opt in optionals:
        opt = opt.strip()
        # Caso con valor: --flag %nombre%
        match_val = re.search(r'(--?\w+)\s+%(\w+)%', opt)
        if match_val:
            flag, var_name = match_val.groups()
            parser.add_argument(flag, dest=var_name, default=None, help=f"Opción {flag}")
        else:
            # Caso flag booleano: --flag
            match_flag = re.match(r'(--?\w+)', opt)
            if match_flag:
                flag = match_flag.group(1)
                var_name = flag.lstrip('-').replace('-', '_')
                parser.add_argument(flag, dest=var_name, action='store_true', help=f"Flag {flag}")


def load_plugin_commands(main_subparsers: argparse._SubParsersAction) -> None:
    """
    Descubre y registra los comandos de plugins en el subparser principal de la CLI de Gram.
    """
    allow_cmds = getattr(config, "PLUGIN_DEFINE_COMMANDS", True) or getattr(
        config, "PLUGINS_ALLOW_ALL_PLUGINS", False
    )
    if not allow_cmds:
        return

    from gram.plugins.manager.core import get_plugins_dir
    plugins_dir = get_plugins_dir()
    if not plugins_dir.exists():
        return

    for plugin_folder in plugins_dir.iterdir():
        if not plugin_folder.is_dir():
            continue

        commands_json = plugin_folder / "commands" / "commands.json"
        if not commands_json.exists():
            continue

        try:
            data = json.loads(commands_json.read_text(encoding="utf-8-sig"))
            cli_name = data.get("cli_name") or data.get("cli_def_name") or plugin_folder.name
            commands = data.get("commands", {})

            if not commands:
                commands = {
                    k: v for k, v in data.items()
                    if k not in ("cli_name", "cli_def_name") and isinstance(v, dict)
                }

            if not cli_name or not commands:
                continue

            if cli_name in main_subparsers.choices:
                plugin_parser = main_subparsers.choices[cli_name]
            else:
                plugin_parser = main_subparsers.add_parser(
                    cli_name,
                    help=f"Comandos expuestos por el plugin '{plugin_folder.name}'",
                )

            subparsers_actions = [
                a for a in plugin_parser._actions
                if isinstance(a, argparse._SubParsersAction)
            ]
            if subparsers_actions:
                subparsers = subparsers_actions[0]
            else:
                subparsers = plugin_parser.add_subparsers(
                    dest="plugin_subcommand",
                    help="Subcomandos del plugin",
                )

            for cmd_name, cmd_info in commands.items():
                if not isinstance(cmd_info, dict):
                    continue

                desc = cmd_info.get("desc", f"Comando {cmd_name}")
                struct = cmd_info.get("struct", "")

                cmd_parser = subparsers.add_parser(cmd_name, help=desc)
                parse_struct_to_argparse(cmd_parser, struct)

        except Exception:
            pass


__all__ = [
    "parse_struct_to_argparse",
    "load_plugin_commands",
]
