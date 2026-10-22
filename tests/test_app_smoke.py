"""
Opal - Application smoke test
Plain English: Starts the real application (dashboard, drop orb, radial wheel,
tray, floating studio, watch folder) exactly as a user would, then drives the
main interactions and shuts it down cleanly. Catches import errors, broken
signal wiring and crashes that unit-style tests miss.
"""

import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPoint, Qt

PASS, FAIL = [], []


def check(name, ok, detail=""):
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {('- ' + str(detail)) if detail else ''}")
    (PASS if ok else FAIL).append(name)


def pump(app, ms=150):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.005)


def main():
    from opal_studio.main import OpalApp
    from opal_studio.engine import OpalEngine

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    print("\n--- APPLICATION BOOT ---")
    tangerine = OpalApp(app)
    pump(app, 400)
    check("app boots", tangerine is not None)
    check("dashboard created", tangerine.dashboard is not None)
    check("drop orb created", tangerine.drop_orb is not None)
    check("radial wheel created", tangerine.radial_menu is not None)
    check("tray created", tangerine.tray is not None)
    check("floating studio created", tangerine.studio is not None)
    check("watch folder worker started", tangerine.watch_folder_worker is not None)

    print("\n--- RADIAL WHEEL ---")
    sample = ROOT / "test_sandbox" / "viewers" / "photo.jpg"
    if not sample.exists():
        from PIL import Image
        sample.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (400, 300), (255, 122, 24)).save(sample)
    tangerine.radial_menu.show_for_files([str(sample)], QPoint(100, 100), initial_mode="convert")
    pump(app, 200)
    check("wheel opens for a file", tangerine.radial_menu.isVisible())
    check("wheel lists conversions", len(tangerine.radial_menu.options) > 3,
          len(tangerine.radial_menu.options))
    convert_ids = [o["id"] for o in tangerine.radial_menu.options]
    check("wheel offers webp", "webp" in convert_ids, convert_ids)
    tangerine.radial_menu.set_mode("tools")
    pump(app, 120)
    tool_ids = [o["id"] for o in tangerine.radial_menu.options]
    check("tools wheel offers AI background removal", "remove_bg" in tool_ids, tool_ids)
    check("tools wheel offers upscaling", "upscale_2x" in tool_ids)
    tangerine.radial_menu.set_mode("actions")
    pump(app, 120)
    action_ids = [o["id"] for o in tangerine.radial_menu.options]
    check("actions wheel offers float", "float" in action_ids, action_ids)
    check("actions wheel offers checksums", "hash_file" in action_ids)
    tangerine.radial_menu.close()

    print("\n--- STUDIO INTEGRATION ---")
    tangerine.on_action_selected([str(sample)], "float")
    pump(app, 400)
    check("float action opens the studio", tangerine.studio.tabs.count() >= 2,
          tangerine.studio.tabs.count())
    check("studio tab is the image lab",
          type(tangerine.studio.tabs.widget(1)).__name__ == "ImageLab")

    print("\n--- CONVERSION ROUND TRIP ---")
    result = OpalEngine.execute_single(str(sample), "webp")
    check("engine converts through the app path", result.success and result.output_path,
          result.message)
    if result.success:
        check("converted file exists", Path(result.output_path).exists())

    print("\n--- HISTORY & CONFIG ---")
    from opal_studio.config import ConfigManager
    ConfigManager.add_history_entry("photo.jpg", "photo_webp.webp", "webp",
                                    str(sample), 1024)
    history = ConfigManager.load_history()
    check("history records the run", len(history) >= 1, len(history))
    cfg = ConfigManager.load_config()
    check("config has new keys", "bg_model" in cfg and "keep_original_dates" in cfg)

    print("\n--- CLEAN SHUTDOWN ---")
    tangerine.shutdown()
    app.quit()
    pump(app, 300)
    check("clean shutdown completes", True)

    print("\n" + "=" * 60)
    print(f"APP RESULT: {len(PASS)} passed, {len(FAIL)} failed")
    if FAIL:
        print("FAILED:", ", ".join(FAIL))
    return 0 if not FAIL else 1


if __name__ == "__main__":
    sys.exit(main())
