"""
Opal - Plugin API
Plain English: drop a .py file into the plugins folder and its tool appears in
the wheel next to the built-in ones. In portable mode the folder sits next to
the app (plugins/), otherwise in the Opal data folder; OPAL_PLUGINS_DIR
overrides both.

A plugin file defines a metadata dict and one function:

    OPAL_PLUGIN = {
        "id": "upper",            # shown in the wheel as plugin:upper
        "label": "UPPERCASE",
        "desc": "Write the text back in capitals",
        "exts": [".txt"],         # optional; empty means every file
    }

    def run(file_path, options=None):
        return {"success": True, "output_path": "...", "message": "..."}

A plugin that fails to import, lacks the metadata, or raises while running is
reported as an error and skipped - it never takes the app down with it.
"""

import importlib.util
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


class Plugin:
    def __init__(self, path: Path, meta: Dict[str, Any], module: Any):
        self.path = path
        self.id = str(meta.get("id", "")).strip()
        self.label = str(meta.get("label", self.id))
        self.desc = str(meta.get("desc", ""))
        exts = meta.get("exts") or []
        self.exts = {e.lower() if e.startswith(".") else f".{e.lower()}" for e in exts}
        self.module = module
        self.error = ""

    @property
    def action_id(self) -> str:
        return f"plugin:{self.id}"

    def applies_to(self, path: Path) -> bool:
        return not self.exts or path.suffix.lower() in self.exts


class PluginManager:
    _cache_sig = None
    _cache_plugins: List[Plugin] = []
    _cache_errors: Dict[str, str] = {}

    @classmethod
    def plugins_dir(cls) -> Path:
        env = os.environ.get("OPAL_PLUGINS_DIR")
        if env:
            return Path(env)
        from opal_studio.platform_compat import user_data_dir
        return user_data_dir() / "plugins"

    @classmethod
    def reload(cls) -> None:
        cls._cache_sig = None

    @classmethod
    def _signature(cls, folder: Path) -> tuple:
        try:
            return tuple(sorted((p.name, p.stat().st_mtime_ns)
                                for p in folder.glob("*.py") if p.is_file()))
        except Exception:
            return ()

    @classmethod
    def discover(cls) -> List[Plugin]:
        """Load every plugin in the plugins folder. Results are cached on the
        folder's signature, so editing a plugin is picked up on the next call."""
        folder = cls.plugins_dir()
        sig = cls._signature(folder)
        if sig is not None and sig == cls._cache_sig:
            return list(cls._cache_plugins)

        plugins: List[Plugin] = []
        errors: Dict[str, str] = {}
        if folder.is_dir():
            for path in sorted(folder.glob("*.py")):
                if not path.is_file() or path.name.startswith("_"):
                    continue
                try:
                    module = cls._load_module(path)
                    meta = getattr(module, "OPAL_PLUGIN", None)
                    if not isinstance(meta, dict) or not str(meta.get("id", "")).strip():
                        raise ValueError("no OPAL_PLUGIN dict with an id")
                    if not callable(getattr(module, "run", None)):
                        raise ValueError("no run(file_path, options) function")
                    plugins.append(Plugin(path, meta, module))
                except Exception as e:
                    errors[path.name] = f"{type(e).__name__}: {e}"

        cls._cache_sig = sig
        cls._cache_plugins = plugins
        cls._cache_errors = errors
        return list(plugins)

    @classmethod
    def _load_module(cls, path: Path):
        """Imports one plugin file under its own module name. The plugin's own
        folder is not put on sys.path and the cwd is untouched, so a plugin
        cannot shadow Opal's own modules by accident."""
        name = f"opal_plugin_{path.stem}_{abs(hash(str(path.resolve())))}"
        spec = importlib.util.spec_from_file_location(name, str(path))
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot load {path.name}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        try:
            spec.loader.exec_module(module)
        except Exception:
            sys.modules.pop(name, None)
            raise
        return module

    @classmethod
    def errors(cls) -> Dict[str, str]:
        cls.discover()
        return dict(cls._cache_errors)

    @classmethod
    def options_for_files(cls, file_paths: List[str]) -> List[Dict[str, str]]:
        """Wheel entries for every plugin that applies to at least one file."""
        paths = [Path(f) for f in file_paths]
        opts = []
        for plugin in cls.discover():
            if any(plugin.applies_to(p) for p in paths):
                opts.append({"id": plugin.action_id,
                             "label": plugin.label,
                             "desc": plugin.desc or f"Plugin: {plugin.id}"})
        return opts

    @classmethod
    def run_plugin(cls, plugin_id: str, src: Path, options: Optional[Dict[str, Any]]):
        """Runs one plugin on one file. Always returns a ConversionResult; a
        raising plugin is a failed conversion, not a crash."""
        from opal_studio.engine import ConversionResult
        for plugin in cls.discover():
            if plugin.id == plugin_id:
                try:
                    result = plugin.module.run(str(src), options or {})
                    if isinstance(result, ConversionResult):
                        return result
                    if isinstance(result, dict):
                        return ConversionResult(
                            bool(result.get("success")),
                            output_path=str(result.get("output_path") or ""),
                            message=str(result.get("message") or ""))
                    return ConversionResult(False, message="plugin returned no result")
                except Exception as e:
                    return ConversionResult(
                        False, message=f"Plugin {plugin_id} failed: {type(e).__name__}: {e}")
        return ConversionResult(False, message=f"No plugin with id '{plugin_id}'.")
