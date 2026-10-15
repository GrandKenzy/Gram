"""
VSIX Grammar Analyzer and Schema Indexer (`gram.vsix.core`).
============================================================
Inspects grammar rules reachable from a root `RuleItem` entrypoint, extracting
declarative editor metadata (colors, autocomplete, suggestions, hints) and
compiling an editor-ready canonical dictionary.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Literal

from gram import config
from gram.core.combinators.base import Combinator, RuleItem
from gram.core.combinators.reference import Ref
from gram.core.lexer import words
from gram.core.rules.codes import code_manager
from gram.vsix.control import VSIXState

Supports = Literal["vscode", "default"]


class VSIXAnalyzer(VSIXState):
    """
    Grammar introspector and metadata extractor for Language Server Protocol (LSP)
    and Visual Studio Code extension manifests.
    """

    def __init__(self, output: Supports = "default", logfile: str | None = None) -> None:
        super().__init__(logfile)
        self.output: Supports = output

    def _collect_rules(self, entrypoint: type[RuleItem]) -> list[type[RuleItem]]:
        visited: set[type[RuleItem]] = set()
        collected: list[type[RuleItem]] = []

        def _traverse(rule_cls: type[RuleItem]) -> None:
            if not isinstance(rule_cls, type) or not issubclass(rule_cls, RuleItem):
                return
            if rule_cls in visited:
                return

            visited.add(rule_cls)
            collected.append(rule_cls)

            entrypoint = getattr(rule_cls, "entrypoint", None)
            if entrypoint is not None:
                _inspect_combinator(entrypoint)

        def _inspect_combinator(comb: Any) -> None:
            if comb is None:
                return

            if isinstance(comb, Ref):
                target = getattr(comb, "rule", None)
                if isinstance(target, type) and issubclass(target, RuleItem):
                    _traverse(target)
                elif comb.rule_name:
                    for r in code_manager.rules.values():
                        if isinstance(r, type) and issubclass(r, RuleItem):
                            r_name = getattr(r, "name", "") or r.__name__
                            if r_name == comb.rule_name:
                                _traverse(r)
                return

            if isinstance(comb, type) and issubclass(comb, RuleItem):
                _traverse(comb)
                return

            if hasattr(comb, "combinators"):
                for child in comb.combinators:
                    _inspect_combinator(child)

            if hasattr(comb, "combinator"):
                _inspect_combinator(comb.combinator)

            if hasattr(comb, "content"):
                _inspect_combinator(comb.content)

            if hasattr(comb, "values"):
                vals = comb.values
                if isinstance(vals, (list, tuple, set, frozenset)):
                    for item in vals:
                        _inspect_combinator(item)
                else:
                    _inspect_combinator(vals)

            if hasattr(comb, "sep"):
                _inspect_combinator(comb.sep)

            if hasattr(comb, "_ref_values"):
                for ref_item in comb._ref_values:
                    _inspect_combinator(ref_item)

            if hasattr(comb, "entrypoint"):
                ep = comb.entrypoint
                if isinstance(ep, type) and issubclass(ep, RuleItem):
                    _traverse(ep)

        _traverse(entrypoint)
        return collected

    def _extract_dependencies(self, rule_cls: type[RuleItem]) -> list[str]:
        deps: list[str] = []
        visited_in_rule: set[str] = set()

        def _walk(comb: Any) -> None:
            if comb is None:
                return
            if isinstance(comb, Ref):
                name = getattr(comb, "rule_name", "")
                target_rule = getattr(comb, "rule", None)
                if not name and isinstance(target_rule, type):
                    name = getattr(target_rule, "name", "") or target_rule.__name__
                if name and name not in visited_in_rule:
                    visited_in_rule.add(name)
                    deps.append(name)
                return
            if isinstance(comb, type) and issubclass(comb, RuleItem):
                name = getattr(comb, "name", "") or comb.__name__
                if name and name not in visited_in_rule:
                    visited_in_rule.add(name)
                    deps.append(name)
                return
            if hasattr(comb, "combinators"):
                for c in comb.combinators:
                    _walk(c)
            if hasattr(comb, "combinator"):
                _walk(comb.combinator)
            if hasattr(comb, "content"):
                _walk(comb.content)
            if hasattr(comb, "values"):
                vals = comb.values
                if isinstance(vals, (list, tuple, set, frozenset)):
                    for v in vals:
                        _walk(v)
                else:
                    _walk(vals)
            if hasattr(comb, "_ref_values"):
                for r in comb._ref_values:
                    _walk(r)

        _walk(getattr(rule_cls, "entrypoint", None))
        return deps

    def _extract_lexicon(self) -> dict[str, Any]:
        group_catalog: dict[str, list[str]] = {}
        for g_name, g_obj in words.groups.all().items():
            vals = getattr(g_obj, "values", None)
            if callable(vals):
                group_catalog[g_name] = [
                    str(k.name if hasattr(k, "name") else k) for k in vals()
                ]
            elif isinstance(vals, (list, tuple, set)):
                group_catalog[g_name] = [
                    str(k.name if hasattr(k, "name") else k) for k in vals
                ]
            elif hasattr(g_obj, "_keywords"):
                group_catalog[g_name] = list(g_obj._keywords.keys())
            else:
                group_catalog[g_name] = []

        keyword_catalog: dict[str, dict[str, Any]] = {}
        for kw_name, kw_obj in words.MAP_KEYWORDS.items():
            keyword_catalog[kw_name] = {
                "group": kw_obj.group,
                "color": getattr(kw_obj, "hex_color", None),
                "description": getattr(kw_obj, "description", ""),
                "documentation": getattr(kw_obj, "documentation", ""),
            }

        return {
            "groups": group_catalog,
            "keywords": keyword_catalog,
        }

    @staticmethod
    def _normalize_map(value: Any) -> dict[Any, Any]:
        """Normalize editor metadata attribute into a mapping indexed by token key."""
        if isinstance(value, dict):
            return dict(value)
        if isinstance(value, (list, tuple, set)):
            return {idx: item for idx, item in enumerate(value)}
        if callable(value):
            return {"this": value}
        if value is not None and value != "":
            return {"this": value}
        return {}

    def process(self, entrypoint: type[RuleItem]) -> dict[str, Any]:
        """
        Analyze all rules reachable from `entrypoint` and produce an editor-ready canonical dictionary.

        Args:
            entrypoint (type[RuleItem]): Root grammar rule class to analyze.

        Returns:
            dict[str, Any]: The extracted language schema dictionary.
        """
        self.node("VSIXProcessing", f"Extracting metadata from entrypoint {entrypoint.__name__}", set_target=True)
        try:
            rules_list = self._collect_rules(entrypoint)
            rules_dict: dict[str, Any] = {}

            all_colors: dict[str, dict[Any, str]] = {}
            all_completions: list[dict[str, Any]] = []
            all_inlay_hints: list[dict[str, Any]] = []

            for rule_cls in rules_list:
                r_name = getattr(rule_cls, "name", "") or rule_cls.__name__
                r_code = getattr(rule_cls, "code", 0)
                r_desc = getattr(rule_cls, "description", "")
                r_nodeable = getattr(rule_cls, "nodeable", True)
                r_structural = getattr(rule_cls, "is_structural", False)
                r_ignore = getattr(rule_cls, "ignore", False)

                raw_colors = self._normalize_map(getattr(rule_cls, "colors", {}))
                raw_autocomplete = self._normalize_map(getattr(rule_cls, "autocomplete", {}))
                raw_suggestions = self._normalize_map(getattr(rule_cls, "suggestions", {}))
                raw_hints = self._normalize_map(getattr(rule_cls, "hints", {}))
                raw_playhints = self._normalize_map(getattr(rule_cls, "playhints", {}))

                if not r_nodeable and (raw_colors or raw_autocomplete or raw_suggestions):
                    self.warn(f"Rule '{r_name}' defines editor maps but nodeable is False.")

                normalized_suggestions: dict[Any, list[str]] = {}
                for k, provider in raw_suggestions.items():
                    if callable(provider):
                        try:
                            res = provider()
                            normalized_suggestions[k] = list(res) if isinstance(res, (list, tuple)) else [str(res)]
                        except Exception:
                            normalized_suggestions[k] = ["<dynamic_provider>"]
                    elif isinstance(provider, (list, tuple, set, frozenset)):
                        normalized_suggestions[k] = [str(x) for x in provider]
                    else:
                        normalized_suggestions[k] = [str(provider)]

                rules_dict[r_name] = {
                    "name": r_name,
                    "code": r_code,
                    "description": r_desc,
                    "nodeable": r_nodeable,
                    "is_structural": r_structural,
                    "ignore": r_ignore,
                    "colors": raw_colors,
                    "autocomplete": raw_autocomplete,
                    "suggestions": normalized_suggestions,
                    "hints": raw_hints,
                    "playhints": raw_playhints,
                    "dependencies": self._extract_dependencies(rule_cls),
                }

                if raw_colors:
                    all_colors[r_name] = raw_colors

                for idx, text in raw_autocomplete.items():
                    all_completions.append({
                        "label": text,
                        "rule": r_name,
                        "token_index": idx,
                        "kind": "Snippet",
                    })

                for idx, sug_list in normalized_suggestions.items():
                    for sug in sug_list:
                        all_completions.append({
                            "label": sug,
                            "rule": r_name,
                            "token_index": idx,
                            "kind": "Value",
                        })

                for idx, h_text in raw_hints.items():
                    all_inlay_hints.append({
                        "rule": r_name,
                        "token_index": idx,
                        "text": h_text,
                        "kind": "Type",
                    })

                for idx, ph_text in raw_playhints.items():
                    all_inlay_hints.append({
                        "rule": r_name,
                        "token_index": idx,
                        "text": ph_text,
                        "kind": "Parameter",
                    })

            all_hovers: dict[str, dict[str, Any]] = {}

            for r_name, r_info in rules_dict.items():
                r_desc = r_info.get("description", "")
                r_hints = r_info.get("hints", {})
                if r_desc or r_hints:
                    all_hovers[r_name] = {
                        "name": r_name,
                        "description": r_desc,
                        "hints": r_hints,
                        "kind": "Rule",
                    }

            lexicon = self._extract_lexicon()

            for kw_name, kw_info in lexicon["keywords"].items():
                kw_desc = kw_info.get("description", "")
                kw_doc = kw_info.get("documentation", "")
                all_completions.append({
                    "label": kw_name,
                    "detail": kw_info.get("group") or "keyword",
                    "kind": "Keyword",
                    "documentation": kw_doc or kw_desc,
                    "color": kw_info.get("color"),
                })
                if kw_desc or kw_doc:
                    all_hovers[kw_name] = {
                        "name": kw_name,
                        "group": kw_info.get("group", ""),
                        "description": kw_desc,
                        "documentation": kw_doc,
                        "color": kw_info.get("color"),
                        "kind": "Keyword",
                    }

            entrypoint_mod = getattr(entrypoint, "__module__", "")
            if entrypoint_mod in ("", "__main__"):
                entrypoint_mod = Path(sys.argv[0]).stem if sys.argv and sys.argv[0] else "prueba"

            return {
                "meta": {
                    "entrypoint": getattr(entrypoint, "name", "") or entrypoint.__name__,
                    "entrypoint_class": entrypoint.__name__,
                    "entrypoint_module": entrypoint_mod,
                    "total_rules": len(rules_list),
                    "comment_token": config.LEXER_COMMENT_TOKEN,
                    "target": self.output,
                },
                "rules": rules_dict,
                "lexicon": lexicon,
                "indexes": {
                    "colors": all_colors,
                    "completions": all_completions,
                    "inlay_hints": all_inlay_hints,
                    "hovers": all_hovers,
                },
            }
        finally:
            self.down()


__all__ = ["Supports", "VSIXAnalyzer"]