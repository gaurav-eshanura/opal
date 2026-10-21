"""
Opal - Configuration and History Store
Plain English: This file saves your preferences (such as start-at-login and output
folders) and keeps a local log of past conversions. In portable mode the files
live next to the app, so nothing is written to the system profile.
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, Any, List

from opal_studio.platform_compat import user_data_dir, set_startup_entry, startup_supported
from opal_studio.safepath import safe_path

APPDATA_DIR = user_data_dir()
CONFIG_FILE = safe_path(APPDATA_DIR, "config.json")
HISTORY_FILE = safe_path(APPDATA_DIR, "history.json")


DEFAULT_CONFIG: Dict[str, Any] = {
    "launch_at_startup": True,
    "global_drag_enabled": True,
    "show_drop_dock": True,
    "output_mode": "same_as_source",  # "same_as_source", "downloads", "custom"
    "custom_output_dir": "",
    "sound_effects": True,
    "max_history_items": 100,
    "watch_folder_enabled": True,
    "watch_folder_path": str(Path.home() / "Downloads" / "Opal_AutoConvert"),
    "bg_model": "u2netp",
    "bg_soft_edges": False,
    "keep_original_dates": True,
    "upscale_model": "realesrgan-x4plus",
    "open_in_studio": False,
}


class ConfigManager:
    @classmethod
    def get_app_dir(cls) -> Path:
        APPDATA_DIR.mkdir(parents=True, exist_ok=True)
        return APPDATA_DIR

    @classmethod
    def load_config(cls) -> Dict[str, Any]:
        cls.get_app_dir()
        if not CONFIG_FILE.exists():
            cls.save_config(DEFAULT_CONFIG)
            return dict(DEFAULT_CONFIG)
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Ensure all default keys exist
                for k, v in DEFAULT_CONFIG.items():
                    data.setdefault(k, v)
                return data
        except Exception:
            return dict(DEFAULT_CONFIG)

    @classmethod
    def save_config(cls, config: Dict[str, Any]) -> bool:
        try:
            cls.get_app_dir()
            CONFIG_FILE.write_text(json.dumps(config, indent=2), encoding="utf-8")
            # Sync startup registry setting
            cls.set_startup_registry(config.get("launch_at_startup", True))
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False

    @classmethod
    def set_startup_registry(cls, enable: bool) -> bool:
        """Registers the app to start at login (Windows Run key or Linux autostart)."""
        if not startup_supported():
            return False
        try:
            return set_startup_entry(enable)
        except Exception as e:
            print(f"Startup entry update error: {e}")
            return False

    # --- HISTORY MANAGEMENT ---

    @classmethod
    def load_history(cls) -> List[Dict[str, Any]]:
        cls.get_app_dir()
        if not HISTORY_FILE.exists():
            return []
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    @classmethod
    def add_history_entry(cls, source_name: str, target_name: str, action: str, output_path: str, saved_bytes: int):
        import time
        history = cls.load_history()
        entry = {
            "source_name": source_name,
            "target_name": target_name,
            "action": action,
            "output_path": output_path,
            "saved_bytes": saved_bytes,
            "timestamp": time.time(),
        }
        history.insert(0, entry)
        config = cls.load_config()
        max_items = config.get("max_history_items", 100)
        history = history[:max_items]
        try:
            HISTORY_FILE.write_text(json.dumps(history, indent=2), encoding="utf-8")
        except Exception:
            pass

    @classmethod
    def clear_history(cls):
        try:
            HISTORY_FILE.write_text(json.dumps([]), encoding="utf-8")
        except Exception:
            pass
