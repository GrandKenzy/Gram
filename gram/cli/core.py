"""
Herramienta de Línea de Comandos de Gram (gram.cli).
====================================================
Proporciona la interfaz de consola para:
- Instalar, cargar, actualizar y desinstalar plugins en el catálogo de Gram.
- Validar e inspeccionar plugins sin ejecutar su código en memoria (CacheSystem).
- Gestionar el entorno virtual dedicado de Gram (gram.environment).
- Listar y consultar información técnica de extensiones instaladas.
- Compilar y analizar gramáticas GLANG (.glang).
- Generar, instalar, desinstalar e inspeccionar la extensión VSIX y LSP para VS Code (gram.vsix).
- Ejecutar comandos expuestos por plugins instalados.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Any

import gram
from gram import config, errors
from gram.cachesystem import (
    compute_plugin_tree_hash,
    get_plugin_cache,
    inspect_and_resolve_plugin,
    invalidate_plugin_cache,
    save_plugin_cache,
)
from gram.plugins.manager.core import get_plugins_dir
from gram.plugins.validator import ValidationReport, should_ignore, validate_plugin


def print_banner(title: str) -> None:
    print("=" * 60)
    print(f"Gram CLI — {title}")
    print("=" * 60)


def print_validation_report(report: ValidationReport, action_title: str = "Validación de Plugin") -> None:
    """Muestra un reporte estructurado y visual del análisis del plugin."""
    print("=" * 60)
    print(f"{action_title}: '{report.plugin_name}'")
    print(f"  Ruta origen: {report.source_dir}")
    print("=" * 60)

    # 1. Manifiesto
    if report.manifest:
        v_tag = f"v{report.manifest.version_str}"
        print(f"  * Manifiesto:        [OK] manifest.json válido ({v_tag})")
        if report.uuid:
            print(f"  * UUID:              {report.uuid}")
        print(f"  * Gram requerida:    >={report.manifest.min_engine_str}")
        caps = report.manifest.capabilities
        print(f"  * Capacidades:       load={caps.load} | process={caps.process} | cli={caps.cli}")
    else:
        print("  * Manifiesto:        [X] Falló la lectura o sintaxis de manifest.json")

    # 2. Estructura
    main_ok = (report.source_dir / "main.py").exists()
    init_ok = (report.source_dir / "__init__.py").exists()
    main_tag = "[OK] main.py presente" if main_ok else "[X] falta main.py"
    init_tag = "[OK] __init__.py presente" if init_ok else "[!] falta __init__.py"
    print(f"  * Estructura:        {main_tag} | {init_tag}")

    # 3. Archivos y sintaxis
    py_files = [
        f for root, dirs, files in os.walk(report.source_dir)
        for f in files if f.endswith(".py") and not should_ignore(f)
    ]
    syntax_errs = [i for i in report.errors if i.code == errors.PLUGIN_SYNTAX_ERROR]
    if syntax_errs:
        print(f"  * Código Python:     [X] Errores de sintaxis ({len(syntax_errs)} fallos)")
    else:
        print(f"  * Código Python:     [OK] {len(py_files)} archivos .py analizados")

    # 4. Dependencias
    if report.manifest and report.manifest.requests:
        print(f"  * Dependencias:      {len(report.manifest.requests)} declaradas")
    else:
        print("  * Dependencias:      (Ninguna)")

    # 5. Advertencias y notas
    def _fmt(issue: Any) -> str:
        return issue.format_line() if hasattr(issue, "format_line") else str(getattr(issue, "message", issue))

    if report.warnings:
        print("-" * 60)
        print("Advertencias:")
        for w in report.warnings:
            print(f"  [AVISO] {_fmt(w)}")

    if report.infos:
        print("-" * 60)
        print("Información adicional:")
        for inf in report.infos:
            print(f"  [INFO] {_fmt(inf)}")

    # 6. Errores bloqueantes
    if not report.is_valid:
        print("-" * 60)
        print("[ERROR] Se detectaron incidencias que impiden continuar:")
        for err in report.errors:
            print(f"  [X] {_fmt(err)}")
        print("-" * 60)


# ==============================================================================
# SUBCOMANDOS DE PLUGINS
# ==============================================================================

def cmd_check(args: argparse.Namespace) -> int:
    """Valida un plugin en modo dry-run sin instalar ni modificar nada."""
    source_dir = Path(args.path).resolve()
    report = validate_plugin(source_dir, target_name=args.name, installed_plugins_dir=get_plugins_dir())
    print_validation_report(report, action_title="Verificación de Plugin (--check)")

    if report.is_valid:
        print("\n[OK] El plugin es válido y cumple con todas las políticas de Gram.")
        return 0
    else:
        print("\n[FALLO] La verificación encontró errores críticos.")
        return 1


def cmd_install(args: argparse.Namespace) -> int:
    """
    Instala un plugin en el catálogo de Gram.
    IMPORTANTE: No ejecuta 'load()'. Inspecciona estáticamente, resuelve y almacena
    el hash determinista en el CacheSystem para optimizar futuras actualizaciones.
    """
    source_dir = Path(args.path).resolve()
    plugins_dir = get_plugins_dir()

    report, entry = inspect_and_resolve_plugin(
        source_dir,
        target_name=args.name,
        installed_plugins_dir=plugins_dir,
        use_cache=False,
    )

    print_validation_report(report, action_title="Instalación de Plugin (gram install)")

    if not report.is_valid or not entry:
        print("\n[ABORTADO] La instalación fue cancelada debido a errores en el plugin.")
        return 1

    if getattr(args, "check", False) or getattr(args, "dry_run", False):
        print("\n[OK] Verificación completada (--check). No se realizaron copias.")
        return 0

    target_folder = report.target_folder or report.plugin_name
    target_dir = plugins_dir / target_folder

    if report.is_installed:
        if report.is_protected:
            print(f"[ERROR] El plugin '{report.plugin_name}' está protegido del sistema y no puede sobrescribirse.")
            return 1

        if not args.yes:
            prompt = (
                f"El plugin '{report.plugin_name}' ya existe en el catálogo:\n"
                f"  Destino: {target_dir}\n"
                f"  Versión actual: v{report.installed_version} -> Versión entrante: v{report.incoming_version}\n"
                f"¿Desea sobrescribirlo? [s/N]: "
            )
            try:
                choice = input(prompt).strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\n[INFO] Operación cancelada por el usuario.")
                return 0

            if choice not in ("s", "si", "y", "yes"):
                print("[INFO] Operación cancelada.")
                return 0

        shutil.rmtree(target_dir, ignore_errors=True)

    def _ignore(path: str, names: list[str]) -> set[str]:
        return {n for n in names if should_ignore(n)}

    try:
        shutil.copytree(source_dir, target_dir, ignore=_ignore)
    except OSError as exc:
        print(f"[ERROR] Falló la copia de archivos del plugin: {exc}")
        return 1

    save_plugin_cache(entry)

    print(f"\n[OK] Plugin '{report.plugin_name}' v{entry.version} instalado exitosamente:")
    print(f"     Destino:   {target_dir}")
    print(f"     Tree Hash: {entry.tree_hash}")
    print(f"     Estado:    Registrado en CacheSystem (listo para su uso)")
    return 0


def cmd_load(args: argparse.Namespace) -> int:
    """Carga o instala un plugin en el catálogo."""
    return cmd_install(args)


def cmd_update(args: argparse.Namespace) -> int:
    """
    Actualiza un plugin existente. Utiliza el CacheSystem para saltarse reanálisis
    si los archivos no han cambiado.
    """
    source_dir = Path(args.path).resolve()
    plugins_dir = get_plugins_dir()

    curr_hash, files = compute_plugin_tree_hash(source_dir)

    manifest_file = source_dir / "manifest.json"
    plugin_name = args.name or source_dir.name
    uuid = ""
    if manifest_file.exists():
        try:
            m_data = json.loads(manifest_file.read_text(encoding="utf-8"))
            plugin_name = m_data.get("plugin_name", plugin_name)
            uuid = m_data.get("uuid", "")
        except Exception:
            pass

    cached_entry = get_plugin_cache(plugin_name, uuid)
    if cached_entry and cached_entry.tree_hash == curr_hash:
        print(f"[INFO] El plugin '{plugin_name}' ya está completamente actualizado.")
        print(f"       Tree Hash: {curr_hash}")
        print("       No se detectaron cambios en los archivos (reanálisis omitido por CacheSystem).")
        return 0

    print(f"[INFO] Cambios detectados en '{plugin_name}'. Actualizando catálogo...")
    return cmd_install(args)


def cmd_reload(args: argparse.Namespace) -> int:
    """Sincroniza incrementalmente archivos modificados de un plugin."""
    plugin_path = getattr(args, "path", ".")
    source_dir = Path(plugin_path).resolve()
    if not source_dir.exists() or not source_dir.is_dir():
        print(f"[ERROR] Ruta no válida: {source_dir}")
        return 1

    return cmd_update(args)


def cmd_remove(args: argparse.Namespace) -> int:
    """Desinstala un plugin del catálogo de Gram y limpia su caché."""
    plugins_dir = get_plugins_dir()
    target_dir = plugins_dir / args.plugin_name

    if not target_dir.exists() or not target_dir.is_dir():
        print(f"[ERROR] El plugin '{args.plugin_name}' no se encuentra en: {target_dir}")
        return 1

    if not args.yes:
        try:
            choice = input(f"¿Está seguro de que desea desinstalar '{args.plugin_name}'? [s/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\n[INFO] Cancelado por el usuario.")
            return 0
        if choice not in ("s", "si", "y", "yes"):
            print("[INFO] Operación cancelada.")
            return 0

    try:
        shutil.rmtree(target_dir)
        invalidate_plugin_cache(args.plugin_name)
        print(f"[OK] Plugin '{args.plugin_name}' desinstalado y eliminado de la caché.")
        return 0
    except OSError as exc:
        print(f"[ERROR] No se pudo eliminar el plugin: {exc}")
        return 1


def cmd_list(args: argparse.Namespace) -> int:
    """Lista todos los plugins instalados en el catálogo de Gram."""
    plugins_dir = get_plugins_dir()
    installed = [p for p in plugins_dir.iterdir() if p.is_dir() and not should_ignore(p.name)]

    print_banner(f"Plugins Instalados ({len(installed)} encontrados)")

    if not installed:
        print("  (Ningún plugin instalado en Gram)")
        return 0

    for p in sorted(installed, key=lambda x: x.name):
        file_count = sum(1 for root, _, files in os.walk(p) for f in files if not should_ignore(f))
        has_init = (p / "__init__.py").exists()
        init_tag = "[OK] __init__.py" if has_init else "[!] sin __init__.py"
        m_file = p / "manifest.json"
        ver_tag = ""
        uuid_tag = ""
        if m_file.exists():
            try:
                m_data = json.loads(m_file.read_text(encoding="utf-8"))
                if m_data.get("version"):
                    ver_tag = f" v{'.'.join(str(x) for x in m_data['version']) if isinstance(m_data['version'], list) else m_data['version']}"
                if m_data.get("uuid"):
                    uuid_tag = f" | UUID: {m_data['uuid']}"
            except Exception:
                pass

        cached = get_plugin_cache(p.name)
        cache_tag = "[OK] Cacheado" if cached else "[!] Sin caché"

        print(f"  * {p.name}{ver_tag}")
        print(f"      Archivos: {file_count} | {init_tag}{uuid_tag} | {cache_tag}")
        print(f"      Ruta: {p}")

    print("=" * 60)
    return 0


def cmd_info(args: argparse.Namespace) -> int:
    """Muestra información técnica detallada de un plugin instalado."""
    plugins_dir = get_plugins_dir()
    target_dir = plugins_dir / args.plugin_name
    if not target_dir.exists():
        direct = Path(args.plugin_name).resolve()
        if direct.exists() and direct.is_dir():
            target_dir = direct
        else:
            print(f"[ERROR] Plugin '{args.plugin_name}' no encontrado.")
            return 1

    report = validate_plugin(target_dir, installed_plugins_dir=plugins_dir)
    print_validation_report(report, action_title="Información Técnica del Plugin")

    cached = get_plugin_cache(report.plugin_name, report.uuid)
    if cached:
        print(f"  * Cache Tree Hash:   {cached.tree_hash}")
        print(f"  * Inspeccionado en:  {cached.inspected_at}")
        print(f"  * Archivos en caché: {len(cached.files_hashes)}")
    return 0


# ==============================================================================
# SUBCOMANDO: WATCH (RECARGA EN CALIENTE)
# ==============================================================================

def cmd_watch(args: argparse.Namespace) -> int:
    """Monitorea archivos de plugins en tiempo real y ejecuta recarga en caliente."""
    from gram.core.watcher import PluginWatcher

    target_path = Path(args.path).resolve()
    print_banner("Vigilante en Tiempo Real (Watcher)")
    print(f"  Ruta observada: {target_path}")
    print("  Presione Ctrl+C para detener la vigilancia.\n")

    def _on_reload(plugin: Any, report: Any, entry: Any) -> None:
        short_hash = entry.tree_hash[:16] if entry and entry.tree_hash else ""
        print(f"\n[WATCHER] Recarga en caliente completada para '{plugin.name}' (Hash: {short_hash}...)")

    def _on_error(plugin_name: str, errors_list: list[Any]) -> None:
        print(f"\n[WATCHER ERROR] Error al validar '{plugin_name}':")
        for err in errors_list:
            print(f"  [X] {err}")

    watcher = PluginWatcher(
        paths=target_path,
        on_reload=_on_reload,
        on_error=_on_error,
        debounce_seconds=getattr(args, "debounce", 0.3),
    )

    interval = getattr(args, "interval", 0.5)
    watcher.watch(interval=interval)
    print("\n[INFO] Vigilancia finalizada.")
    return 0


# ==============================================================================
# SUBCOMANDO CLEAN (LIMPIEZA DE TEMPORALES Y CACHÉ)
# ==============================================================================

def cmd_clean(args: argparse.Namespace) -> int:
    """Limpia directorios temporales y archivos de caché de Gram y sus plugins."""
    from gram.environment import clean_cache, clean_data, clean_temp

    clean_all = getattr(args, "all", False)
    do_temp = getattr(args, "temp", False) or clean_all
    do_cache = getattr(args, "cache", False) or clean_all
    do_data = getattr(args, "data", False)
    plugin_name = getattr(args, "plugin", None)

    if not (getattr(args, "temp", False) or getattr(args, "cache", False) or getattr(args, "data", False) or clean_all):
        do_temp = True
        do_cache = True

    print_banner("Limpieza de Archivos y Caché")
    total_cleaned = 0

    if do_temp:
        cnt = clean_temp(plugin_name=plugin_name)
        total_cleaned += cnt
        target_str = f"para '{plugin_name}'" if plugin_name else "globales"
        print(f"  * Temporales eliminados ({target_str}): {cnt} elementos")

    if do_cache:
        cnt = clean_cache(plugin_name=plugin_name)
        total_cleaned += cnt
        target_str = f"para '{plugin_name}'" if plugin_name else "globales"
        print(f"  * Entradas de caché purgadas ({target_str}): {cnt} archivos")

    if do_data and plugin_name:
        ok = clean_data(plugin_name=plugin_name)
        if ok:
            total_cleaned += 1
            print(f"  * Directorio de datos persistentes eliminado para '{plugin_name}'.")

    print(f"[OK] Limpieza completada. Total de elementos purgados: {total_cleaned}")
    return 0


# ==============================================================================
# SUBCOMANDO RUN (ANÁLISIS LÉXICO Y SINTÁCTICO DE ARCHIVO)
# ==============================================================================

def cmd_run(args: argparse.Namespace) -> int:
    """Ejecuta el análisis léxico y sintáctico de un archivo de código fuente."""
    from gram.core.ast.analyzer import ASTAnalyzer
    from gram.core.combinators import Alt, Many, Ref, RuleItem
    from gram.core.lexer import Lexer, words
    from gram.core.parser import Parser
    from gram.native.rules import DECLARATION, ENDLINE, PASS, PROGRAM
    from gram.plugins.manager.core import Plugins

    file_path = Path(args.file).resolve()
    if not file_path.exists() or not file_path.is_file():
        print(f"[ERROR] El archivo especificado no existe o no es accesible: {file_path}")
        return 1

    try:
        source_code = file_path.read_text(encoding="utf-8")
    except Exception as exc:
        print(f"[ERROR] No se pudo leer el archivo: {exc}")
        return 1

    plugin_name = getattr(args, "plugin", None)
    if plugin_name:
        try:
            print(f"[INFO] Cargando plugin '{plugin_name}'...")
            Plugins.load(plugin_name)
            print(f"[OK] Plugin '{plugin_name}' cargado exitosamente.")
        except Exception as exc:
            print(f"[ERROR] Falló la carga del plugin '{plugin_name}': {exc}")
            return 1

    if words.is_empty():
        words.add_keyword("pass", description="Instrucción vacía por defecto", allow_override=True)

    t0 = time.perf_counter()

    try:
        lexer = Lexer(source_code)
        tokens = lexer.process()
    except Exception as exc:
        print(f"[ERROR Léxico] {exc}")
        return 1

    if getattr(args, "tokens_only", False):
        print_banner(f"Tokens Generados ({len(tokens)} tokens)")
        for idx, tok in enumerate(tokens):
            print(f"  [{idx:03d}] {tok}")
        print("=" * 60)
        return 0

    decl_alternatives: list[Any] = [Ref(PASS), Ref(ENDLINE)]
    grammar_dict: dict[Any, Any] = {
        PASS: PASS.grammar,
        ENDLINE: ENDLINE.grammar,
    }

    for p in list(Plugins.registry.values()):
        for r_path in p.get_rules():
            try:
                import importlib.util
                spec = importlib.util.spec_from_file_location(f"rule_{r_path.stem}", str(r_path))
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    for item_name in dir(mod):
                        obj = getattr(mod, item_name)
                        if isinstance(obj, type) and issubclass(obj, RuleItem) and obj is not RuleItem:
                            if getattr(obj, "grammar", None):
                                grammar_dict[obj] = obj.grammar
                                decl_alternatives.append(Ref(obj))
            except Exception:
                pass

    grammar_dict[PROGRAM] = Many(Ref(DECLARATION))
    if len(decl_alternatives) == 1:
        grammar_dict[DECLARATION] = decl_alternatives[0]
    else:
        grammar_dict[DECLARATION] = Alt(*decl_alternatives)

    try:
        parser = Parser(tokens)
        analyzer = ASTAnalyzer(parser=parser, grammar=grammar_dict)
        program = analyzer.process()
    except Exception as exc:
        print(f"[ERROR Sintáctico] {exc}")
        return 1

    elapsed = time.perf_counter() - t0

    if getattr(args, "json", False):
        print(json.dumps(program.to_dict(), indent=2, ensure_ascii=False))
        return 0

    print_banner(f"Resultado de Análisis: '{file_path.name}'")
    print(f"  * Tokens procesados:  {len(tokens)}")
    print(f"  * Sentencias AST:     {len(program)}")
    print(f"  * Comentarios:        {len(program.comments)}")
    print(f"  * Tiempo de proceso:  {elapsed:.4f}s")
    print("=" * 60)

    if getattr(args, "print_ast", False):
        print("\n--- ÁRBOL SINTÁCTICO (AST) ---")
        try:
            tree_str = program.generate_decorated_tree()
        except Exception:
            tree_str = program.dump()
        try:
            print(tree_str)
        except UnicodeEncodeError:
            enc = sys.stdout.encoding or "utf-8"
            print(tree_str.encode(enc, errors="replace").decode(enc))
        print("------------------------------\n")

    return 0


# ==============================================================================
# SUBCOMANDO GLANG (COMPILACIÓN Y ANÁLISIS DE DSL .glang)
# ==============================================================================

def cmd_glang(args: argparse.Namespace) -> int:
    """Gestiona el lenguaje declarativo GLANG (.glang), extensiones y compilación VSIX."""
    import gram.glang as glang
    from gram.glang.vsix import (
        generate_glang_vsix,
        install_glang_vsix,
        uninstall_glang_vsix,
    )

    action = getattr(args, "action", None) or ""
    target = getattr(args, "target", None) or ""
    opt_install = getattr(args, "install_vsix", None)
    opt_uninstall = getattr(args, "uninstall_vsix", None)
    output_path = getattr(args, "output", None)

    # 1. Comprobación de desinstalación: --uninstall vsix o comando 'uninstall vsix'
    if opt_uninstall or action in ("uninstall", "--uninstall"):
        print_banner("GLANG — Desinstalación de Extensión VS Code")
        ok, msg = uninstall_glang_vsix()
        if ok:
            print(f"[OK GLANG] {msg}")
            return 0
        else:
            print(f"[ERROR GLANG] {msg}")
            return 1

    # 2. Comprobación de instalación: --install vsix o comando 'install vsix'
    if opt_install or action in ("install", "--install"):
        print_banner("GLANG — Generación e Instalación de Extensión VS Code")
        try:
            target_vsix = generate_glang_vsix(output_path=output_path, force=True, install_after=True)
            print(f"\n[OK GLANG] Extensión VSIX generada e instalada exitosamente:")
            print(f"           Archivo: {target_vsix}")
            return 0
        except Exception as exc:
            print(f"[ERROR GLANG] Falló la instalación de VSIX: {exc}")
            return 1

    # 3. Comprobación de generación: 'generate vsix'
    if action == "generate" and (target.lower() == "vsix" or not target):
        print_banner("GLANG — Generación de Extensión VSIX para VS Code")
        try:
            target_vsix = generate_glang_vsix(output_path=output_path, force=True, install_after=False)
            print(f"\n[OK GLANG] Paquete VSIX de GLANG compilado exitosamente:")
            print(f"           Ruta: {target_vsix}")
            print(f"           Tamaño: {target_vsix.stat().st_size:,} bytes")
            print("           Para instalarlo en VS Code use: gram glang --install vsix")
            return 0
        except Exception as exc:
            print(f"[ERROR GLANG] Falló la generación de VSIX: {exc}")
            return 1

    # 4. Compilación o análisis de archivo .glang
    file_to_parse = target if action == "compile" else action
    if not file_to_parse:
        print("[ERROR GLANG] Debe especificar un archivo .glang o un comando ('generate vsix', '--install vsix', '--uninstall vsix').")
        return 1

    glang_file = Path(file_to_parse).resolve()
    if not glang_file.is_file():
        print(f"[ERROR] Archivo GLANG no encontrado: {glang_file}")
        return 1

    try:
        compiler = glang.parse_glang_file(glang_file)
        print_banner(f"GLANG — Compilación de Gramática: '{glang_file.name}'")
        print(f"  * Reglas definidas: {len(compiler.grammar)}")
        for rule in compiler.grammar.keys():
            r_name = getattr(rule, "name", str(rule))
            r_code = getattr(rule, "code", "-")
            print(f"      - {r_name} (código: {r_code})")
        print("=" * 60)

        source_path = getattr(args, "source", None)
        if source_path:
            s_file = Path(source_path).resolve()
            if not s_file.is_file():
                print(f"[ERROR] Archivo fuente no encontrado: {s_file}")
                return 1
            ast = compiler.parse_file(s_file)
            print(f"\n[OK] Código fuente analizado exitosamente con la gramática de {glang_file.name}")
            print(f"     Sentencias AST: {len(ast)}")
            if getattr(args, "print_ast", False):
                try:
                    tree_str = ast.generate_decorated_tree()
                except Exception:
                    tree_str = ast.dump()
                try:
                    print(tree_str)
                except UnicodeEncodeError:
                    enc = sys.stdout.encoding or "utf-8"
                    print(tree_str.encode(enc, errors="replace").decode(enc))
        else:
            print("[OK] Gramática GLANG compilada y validada exitosamente.")
        return 0
    except Exception as exc:
        print(f"[ERROR GLANG] {exc}")
        return 1



# ==============================================================================
# SUBCOMANDOS DEL ENTORNO (VENV)
# ==============================================================================

def cmd_env(args: argparse.Namespace) -> int:
    """Administra el entorno virtual dedicado de Gram (gram.environment)."""
    from gram import environment

    subcmd = getattr(args, "env_subcommand", "info")

    if subcmd == "info":
        print_banner("Entorno Virtual Dedicado")
        env_path = environment.get_path()
        created = environment.is_created()
        print(f"  * Ruta del Entorno:  {env_path}")
        print(f"  * Estado:            {'[OK] Creado' if created else '[X] No creado'}")
        print(f"  * Python Ejecutable: {environment.get_python_executable()}")
        print(f"  * Pip Ejecutable:    {environment.get_pip_executable()}")
        print(f"  * Site-Packages:     {environment.get_site_packages()}")
        return 0

    elif subcmd == "create":
        print("[INFO] Creando entorno virtual de Gram...")
        created_path = environment.create(force=getattr(args, "force", False))
        print(f"[OK] Entorno virtual listo en: {created_path}")
        return 0

    elif subcmd == "reset":
        print("[INFO] Restableciendo entorno virtual a su configuración base limpia...")
        environment.reset()
        print("[OK] Entorno virtual reiniciado.")
        return 0

    elif subcmd == "install":
        pkgs = getattr(args, "packages", [])
        if not pkgs:
            print("[ERROR] Debe especificar al menos un paquete para instalar.")
            return 1
        print(f"[INFO] Instalando paquetes en el entorno de Gram: {pkgs}...")
        ok = environment.install(*pkgs)
        if ok:
            print("[OK] Paquetes instalados exitosamente.")
            return 0
        else:
            print("[ERROR] Falló la instalación de paquetes.")
            return 1

    elif subcmd == "list":
        pkgs = environment.list_packages()
        print_banner(f"Paquetes en el Entorno ({len(pkgs)} instalados)")
        for name, ver in sorted(pkgs.items()):
            print(f"  * {name} == {ver}")
        print("=" * 60)
        return 0

    print(f"[ERROR] Subcomando de entorno no reconocido: {subcmd}")
    return 1


# ==============================================================================
# SUBCOMANDOS DE VSIX Y SOPORTE DE EDITOR
# ==============================================================================

def cmd_vsix(args: argparse.Namespace) -> int:
    """Administra la extensión VSIX y el soporte de editor de Gram (gram.vsix)."""
    import gram.vsix as vsix
    from gram.vsix.core import find_vscode_executable

    subcmd = getattr(args, "vsix_subcommand", "info") or "info"

    if subcmd == "compile":
        output_file = getattr(args, "output", None)
        compiler_path = getattr(args, "compiler", "") or ""
        compiler_args = getattr(args, "compiler_args", None)
        custom_exts = getattr(args, "ext", None)
        force = getattr(args, "force", False)

        print_banner("VSIX — Compilación de Extensión VS Code")
        try:
            target_vsix = vsix.compile(
                output_path=output_file,
                force=force,
                custom_extensions=custom_exts,
                compiler_path=compiler_path,
                compiler_args=compiler_args,
            )
            print("[OK] Paquete VSIX compilado exitosamente:")
            print(f"     Ruta: {target_vsix}")
            print(f"     Tamaño: {target_vsix.stat().st_size:,} bytes")
            print(f"     ID de Gram: {vsix.GRAM_FULL_ID}")

            if getattr(args, "install", False):
                print("\n[INFO] Instalando extensión compilada en VS Code...")
                ok, msg = vsix.install(target_vsix)
                if ok:
                    print(f"[OK] {msg}")
                else:
                    print(f"[ERROR] {msg}")
                    return 1
            return 0
        except Exception as exc:
            print(f"[ERROR VSIX] Falló la compilación del paquete: {exc}")
            return 1

    elif subcmd == "install":
        vsix_file = getattr(args, "file", None)
        print_banner("VSIX — Instalación en VS Code")
        ok, msg = vsix.install(vsix_file)
        if ok:
            print(f"[OK] {msg}")
            return 0
        else:
            print(f"[ERROR] {msg}")
            return 1

    elif subcmd == "uninstall":
        print_banner("VSIX — Desinstalación de VS Code")
        print(f"[INFO] Desinstalando extensión oficial de Gram: {vsix.GRAM_FULL_ID}...")
        ok, msg = vsix.uninstall()
        if ok:
            print(f"[OK] {msg}")
            return 0
        else:
            print(f"[ERROR] {msg}")
            return 1

    elif subcmd == "list":
        print_banner("VSIX — Extensiones de Gram en VS Code")
        installed = vsix.list_installed()
        if not installed:
            print("  (No se encontraron extensiones de Gram instaladas en VS Code)")
        else:
            for ext in installed:
                is_official = (ext.lower() == vsix.GRAM_FULL_ID.lower())
                tag = " [Oficial]" if is_official else ""
                print(f"  * {ext}{tag}")
        print("=" * 60)
        return 0

    elif subcmd in ("info", "status"):
        print_banner("VSIX — Estado e Información de Editor")
        code_bin = find_vscode_executable()
        installed = vsix.is_installed()
        active = vsix.get_active_vsix()
        meta = vsix.extract_metadata(include_native=True)

        print(f"  * ID Universal Gram: {vsix.GRAM_FULL_ID}")
        print(f"  * Ejecutable 'code': {code_bin or '[X] No detectado en PATH'}")
        print(f"  * Estado en VS Code: {'[OK] Instalada' if installed else 'No instalada'}")
        print(f"  * Paquete Activo:    {active if active else '(Ninguno compilado en sesión)'}")
        print(f"  * Reglas Sintácticas:{len(meta.rules)} registradas")
        print(f"  * Palabras Clave:    {len(meta.keywords)} registradas")
        print(f"  * Extensiones Arch:  {', '.join(meta.file_extensions)}")
        print("=" * 60)
        return 0

    elif subcmd == "lsp":
        vsix.start_lsp_server()
        return 0

    print(f"[ERROR] Subcomando VSIX no reconocido: {subcmd}")
    return 1


# ==============================================================================
# CONSTRUCCIÓN DEL PARSER PRINCIPAL
# ==============================================================================

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gram",
        description="Gram Framework — Herramienta de Línea de Comandos (CLI)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"Gram {getattr(gram, '__version__', '1.0.0')}",
    )

    subparsers = parser.add_subparsers(dest="command", help="Comando a ejecutar")

    # 1. install
    p_install = subparsers.add_parser("install", help="Instala un plugin en el catálogo (usando CacheSystem, sin load)")
    p_install.add_argument("path", help="Ruta al directorio del plugin")
    p_install.add_argument("--name", help="Nombre del plugin a registrar", default=None)
    p_install.add_argument("-y", "--yes", action="store_true", help="Confirmar automáticamente reemplazos")
    p_install.add_argument("--check", action="store_true", help="Solo validar e inspeccionar sin copiar")
    p_install.set_defaults(func=cmd_install)

    # 2. load
    p_load = subparsers.add_parser("load", help="Carga o instala un plugin en el catálogo")
    p_load.add_argument("path", help="Ruta al directorio del plugin")
    p_load.add_argument("--name", help="Nombre opcional", default=None)
    p_load.add_argument("-y", "--yes", action="store_true", help="Confirmar automáticamente")
    p_load.add_argument("--check", action="store_true", help="Modo dry-run")
    p_load.set_defaults(func=cmd_load)

    # 3. update
    p_update = subparsers.add_parser("update", help="Actualiza un plugin (usa CacheSystem para omitir si no hay cambios)")
    p_update.add_argument("path", help="Ruta al directorio del plugin")
    p_update.add_argument("--name", help="Nombre opcional", default=None)
    p_update.add_argument("-y", "--yes", action="store_true", help="Confirmar automáticamente")
    p_update.set_defaults(func=cmd_update)

    # 4. reload
    p_reload = subparsers.add_parser("reload", help="Recarga incremental de un plugin")
    p_reload.add_argument("path", nargs="?", default=".", help="Ruta al directorio")
    p_reload.add_argument("-y", "--yes", action="store_true", help="Confirmar automáticamente")
    p_reload.set_defaults(func=cmd_reload)

    # 5. remove
    p_remove = subparsers.add_parser("remove", help="Desinstala un plugin del catálogo")
    p_remove.add_argument("plugin_name", help="Nombre del plugin a desinstalar")
    p_remove.add_argument("-y", "--yes", action="store_true", help="Confirmar automáticamente")
    p_remove.set_defaults(func=cmd_remove)

    # 6. list
    p_list = subparsers.add_parser("list", help="Lista los plugins instalados en Gram")
    p_list.set_defaults(func=cmd_list)

    # 7. info
    p_info = subparsers.add_parser("info", help="Muestra detalles técnicos de un plugin")
    p_info.add_argument("plugin_name", help="Nombre del plugin o ruta")
    p_info.set_defaults(func=cmd_info)

    # 8. check
    p_check = subparsers.add_parser("check", help="Inspecciona y valida un plugin sin instalarlo")
    p_check.add_argument("path", help="Ruta al plugin")
    p_check.add_argument("--name", help="Nombre opcional", default=None)
    p_check.set_defaults(func=cmd_check)

    # 9. env
    p_env = subparsers.add_parser("env", help="Administra el entorno virtual dedicado de Gram")
    env_sub = p_env.add_subparsers(dest="env_subcommand", help="Subcomando de entorno")

    p_env_info = env_sub.add_parser("info", help="Muestra información del venv")
    p_env_info.set_defaults(func=cmd_env)

    p_env_create = env_sub.add_parser("create", help="Crea el entorno virtual")
    p_env_create.add_argument("--force", action="store_true", help="Sobrescribir si ya existe")
    p_env_create.set_defaults(func=cmd_env)

    p_env_reset = env_sub.add_parser("reset", help="Restablece el entorno a su estado base")
    p_env_reset.set_defaults(func=cmd_env)

    p_env_install = env_sub.add_parser("install", help="Instala paquetes en el entorno")
    p_env_install.add_argument("packages", nargs="+", help="Paquetes a instalar")
    p_env_install.set_defaults(func=cmd_env)

    p_env_list = env_sub.add_parser("list", help="Lista los paquetes instalados en el entorno")
    p_env_list.set_defaults(func=cmd_env)

    p_env.set_defaults(func=cmd_env)

    # 10. watch
    p_watch = subparsers.add_parser("watch", help="Monitorea cambios en plugins y ejecuta recarga en caliente")
    p_watch.add_argument("path", nargs="?", default=".", help="Ruta al plugin o directorio de plugins")
    p_watch.add_argument("--interval", type=float, default=0.5, help="Intervalo de sondeo en segundos (defecto: 0.5)")
    p_watch.add_argument("--debounce", type=float, default=0.3, help="Tiempo de estabilización debounce en segundos (defecto: 0.3)")
    p_watch.set_defaults(func=cmd_watch)

    # 11. clean
    p_clean = subparsers.add_parser("clean", help="Limpia directorios temporales y archivos de caché")
    p_clean.add_argument("--temp", action="store_true", help="Limpiar solo carpetas temporales")
    p_clean.add_argument("--cache", action="store_true", help="Limpiar solo archivos de caché")
    p_clean.add_argument("--data", action="store_true", help="Limpiar datos persistentes del plugin especificado")
    p_clean.add_argument("--all", "-a", action="store_true", help="Limpiar temporales y caché simultáneamente")
    p_clean.add_argument("--plugin", "-p", default=None, help="Nombre del plugin específico a limpiar")
    p_clean.add_argument("-y", "--yes", action="store_true", help="Omitir confirmaciones")
    p_clean.set_defaults(func=cmd_clean)

    # 12. run
    p_run = subparsers.add_parser("run", help="Analiza código fuente ejecutando el lexer y parser de Gram")
    p_run.add_argument("file", help="Ruta al archivo fuente a procesar")
    p_run.add_argument("--plugin", "-p", default=None, help="Plugin a cargar antes de procesar")
    p_run.add_argument("--tokens-only", "-t", action="store_true", help="Solo ejecutar análisis léxico")
    p_run.add_argument("--print-ast", "-a", action="store_true", help="Imprimir árbol sintáctico estructurado")
    p_run.add_argument("--json", "-j", action="store_true", help="Exportar AST en formato JSON")
    p_run.set_defaults(func=cmd_run)

    # 13. glang
    p_glang = subparsers.add_parser("glang", help="Compila gramáticas GLANG (.glang) o genera/instala extensiones VSIX")
    p_glang.add_argument("action", nargs="?", default=None, help="Acción ('generate', 'compile', 'install', 'uninstall') o ruta al archivo .glang")
    p_glang.add_argument("target", nargs="?", default=None, help="Objetivo ('vsix' o archivo .glang)")
    p_glang.add_argument("--source", "-s", default=None, help="Archivo fuente a parsear con la gramática compilada")
    p_glang.add_argument("--print-ast", "-a", action="store_true", help="Imprimir árbol sintáctico (AST)")
    p_glang.add_argument("-o", "--output", default=None, help="Ruta de salida del paquete .vsix al generar")
    p_glang.add_argument("--install", dest="install_vsix", nargs="?", const="vsix", default=None, help="Genera e instala la extensión en VS Code (--install vsix)")
    p_glang.add_argument("--uninstall", dest="uninstall_vsix", nargs="?", const="vsix", default=None, help="Desinstala la extensión de VS Code (--uninstall vsix)")
    p_glang.set_defaults(func=cmd_glang)

    # 14. vsix
    p_vsix = subparsers.add_parser("vsix", help="Gestiona la extensión y soporte de editor VS Code (VSIX, LSP, temas)")
    vsix_sub = p_vsix.add_subparsers(dest="vsix_subcommand", help="Operación VSIX a ejecutar")

    # vsix compile
    p_vsix_compile = vsix_sub.add_parser("compile", help="Compila el paquete VSIX consolidado con LSP y reglas")
    p_vsix_compile.add_argument("-o", "--output", default=None, help="Ruta de destino del archivo .vsix")
    p_vsix_compile.add_argument("--install", action="store_true", help="Instalar en VS Code inmediatamente tras compilar")
    p_vsix_compile.add_argument("--compiler", default="", help="Ruta al compilador ejecutable objetivo")
    p_vsix_compile.add_argument("--compiler-args", nargs="*", default=None, help="Argumentos por defecto para el compilador")
    p_vsix_compile.add_argument("--ext", nargs="*", default=None, help="Extensiones de archivo adicionales (.ejemplo)")
    p_vsix_compile.add_argument("-f", "--force", action="store_true", help="Forzar recompilación ignorando caché")
    p_vsix_compile.set_defaults(func=cmd_vsix)

    # vsix install
    p_vsix_install = vsix_sub.add_parser("install", help="Instala la extensión en VS Code")
    p_vsix_install.add_argument("file", nargs="?", default=None, help="Ruta al paquete .vsix (opcional, compila si se omite)")
    p_vsix_install.set_defaults(func=cmd_vsix)

    # vsix uninstall
    p_vsix_uninstall = vsix_sub.add_parser("uninstall", help="Desinstala la extensión de Gram en VS Code por su ID universal")
    p_vsix_uninstall.set_defaults(func=cmd_vsix)

    # vsix list
    p_vsix_list = vsix_sub.add_parser("list", help="Lista las extensiones de Gram instaladas en VS Code")
    p_vsix_list.set_defaults(func=cmd_vsix)

    # vsix info / status
    p_vsix_info = vsix_sub.add_parser("info", help="Muestra el estado de la integración de Gram con VS Code y metadatos")
    p_vsix_info.set_defaults(func=cmd_vsix)

    # vsix lsp
    p_vsix_lsp = vsix_sub.add_parser("lsp", help="Inicia el servidor Language Server Protocol (LSP) sobre stdio")
    p_vsix_lsp.set_defaults(func=cmd_vsix)

    p_vsix.set_defaults(func=cmd_vsix)

    # Comandos dinámicos de plugins (commands/commands.json)
    try:
        from gram.plugins.manager.commands_parser import load_plugin_commands
        load_plugin_commands(subparsers)
    except Exception:
        pass

    return parser


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada principal de la CLI de Gram."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not hasattr(args, "func"):
        parser.print_help()
        return 0

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
