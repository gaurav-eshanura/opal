"""
Opal - Master Application Orchestrator
Plain English: This launches the commercial background app, manages single-instance protection,
listens for global drags across Windows, and connects the user interface.
"""

import sys
import os
from pathlib import Path
from typing import List

# Ensure package root is in path
sys.path.insert(0, str(Path(__file__).parent.parent))

from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QApplication, QFileDialog

from opal_studio.config import ConfigManager
from opal_studio.drop_orb import DropOrbWidget
from opal_studio.radial_widget import RadialMenuWidget
from opal_studio.toast import OpalToast
from opal_studio.tray import OpalTray, create_opal_icon
from opal_studio.worker import ConversionWorker
from opal_studio.hotkey import GlobalHotkeyManager
from opal_studio.drag_detector import GlobalDragDetector
from opal_studio.settings_dialog import SettingsDialog
from opal_studio.history_dialog import HistoryDialog
from opal_studio.float_viewer import FloatStudio
from opal_studio.dashboard import OpalDashboard
from opal_studio.watch_folder import WatchFolderWorker


class OpalApp:
    def __init__(self, app: QApplication):
        self.app = app
        self.app.setWindowIcon(create_opal_icon(64))

        self.config = ConfigManager.load_config()

        # Core Components
        self.dashboard = OpalDashboard()
        self.drop_orb = DropOrbWidget()
        self.radial_menu = RadialMenuWidget()
        self.toast = OpalToast()
        self.tray = OpalTray()
        self.hotkey_mgr = GlobalHotkeyManager()
        self.drag_detector = GlobalDragDetector()
        self.studio = FloatStudio()
        self.studio.file_action.connect(self.on_action_selected)

        # Dialogs
        self.settings_dialog = None
        self.history_dialog = None

        self.current_worker = None
        self.watch_folder_worker = None

        self._connect_signals()
        self._apply_config()
        self._position_drop_orb()

        # Register Ctrl+Alt+T global hotkey
        self.hotkey_mgr.register(self.app)

        # Clean shutdown on quit
        self.app.aboutToQuit.connect(self._on_about_to_quit)

        # Start Global Drag Detector if enabled
        if self.config.get("global_drag_enabled", True):
            self.drag_detector.start()

        # Start Automated Watch Folder if enabled
        if self.config.get("watch_folder_enabled", True):
            self.watch_folder_worker = WatchFolderWorker(self.config.get("watch_folder_path"))
            self.watch_folder_worker.file_processed_signal.connect(self.on_watch_folder_file_processed)
            self.watch_folder_worker.start()

    def _on_about_to_quit(self):
        self.drag_detector.stop()
        self.drag_detector.wait(1500)
        if self.watch_folder_worker:
            self.watch_folder_worker.stop()

    def on_watch_folder_file_processed(self, original_name: str, output_path: str, message: str):
        self.toast.show_message("Auto-Converted", message, target_path=output_path, is_error=False)

    def _connect_signals(self):
        # Dashboard events
        self.dashboard.files_selected.connect(self.on_files_dropped)
        self.dashboard.radial_test_requested.connect(self.on_radial_test_requested)
        self.dashboard.settings_requested.connect(self.open_settings)
        self.dashboard.history_requested.connect(self.open_history)
        self.dashboard.toggle_orb_requested.connect(self.toggle_orb)
        self.dashboard.studio_requested.connect(self.show_studio)

        # Drop orb events
        self.drop_orb.files_dropped.connect(self.on_files_dropped)
        self.drop_orb.settings_requested.connect(self.open_settings)
        self.drop_orb.history_requested.connect(self.open_history)

        # Radial menu events
        self.radial_menu.action_selected.connect(self.on_action_selected)

        # Tray events
        self.tray.open_dashboard_requested.connect(self.show_dashboard)
        self.tray.open_studio_requested.connect(self.show_studio)
        self.tray.toggle_orb_requested.connect(self.toggle_orb)
        self.tray.files_selected.connect(self.on_files_picked_manually)
        self.tray.settings_requested.connect(self.open_settings)
        self.tray.history_requested.connect(self.open_history)

        # Global Hotkey event
        self.hotkey_mgr.hotkey_triggered.connect(self.on_hotkey_triggered)

        # Global Drag Detection
        self.drag_detector.drag_triggered.connect(self.on_global_drag_detected)
        self.drag_detector.mode_detected.connect(self.on_drag_mode_detected)
        self._pending_mode = "convert"

    def _apply_config(self):
        show_orb = self.config.get("show_drop_dock", True)
        self.drop_orb.setVisible(show_orb)
        self.drag_detector.enabled = self.config.get("global_drag_enabled", True)

    def _position_drop_orb(self):
        screen = self.app.primaryScreen().geometry()
        x = screen.width() - self.drop_orb.width() - 25
        y = (screen.height() - self.drop_orb.height()) // 2
        self.drop_orb.move(x, y)

    def show(self):
        self.tray.show()
        self.dashboard.show()
        self.dashboard.raise_()
        self.dashboard.activateWindow()
        if self.config.get("show_drop_dock", True):
            self.drop_orb.show()
            self.drop_orb.raise_()

    def show_dashboard(self):
        self.dashboard.show()
        self.dashboard.raise_()
        self.dashboard.activateWindow()

    def show_studio(self):
        """Bring the floating studio to the front (and open a file picker if empty)."""
        if self.studio.tabs.count() <= 1:
            paths, _ = QFileDialog.getOpenFileNames(
                self.dashboard, "Open in Opal Studio", "", "All Files (*.*)")
            for p in paths:
                self.studio.open_file(p)
        self.studio.show()
        self.studio.raise_()
        self.studio.activateWindow()

    def on_radial_test_requested(self):
        import tempfile
        from PIL import Image
        temp_img = Path(tempfile.gettempdir()) / "Opal_Demo_Image.png"
        if not temp_img.exists():
            img = Image.new("RGBA", (400, 400), color=(255, 122, 24, 255))
            img.save(temp_img)
        pos = self.dashboard.mapToGlobal(QPoint(self.dashboard.width() // 2, self.dashboard.height() // 2))
        self.radial_menu.show_for_files([str(temp_img)], pos, initial_mode="convert")

    def toggle_orb(self):
        if self.drop_orb.isVisible():
            self.drop_orb.hide()
        else:
            self.drop_orb.show()
            self.drop_orb.raise_()

    def open_settings(self):
        if not self.settings_dialog:
            self.settings_dialog = SettingsDialog()
            self.settings_dialog.settings_changed.connect(self._on_settings_saved)
        self.settings_dialog.show()
        self.settings_dialog.raise_()
        self.settings_dialog.activateWindow()

    def _on_settings_saved(self):
        self.config = ConfigManager.load_config()
        self._apply_config()

    def open_history(self):
        if not self.history_dialog:
            self.history_dialog = HistoryDialog()
        self.history_dialog.load_history()
        self.history_dialog.show()
        self.history_dialog.raise_()
        self.history_dialog.activateWindow()

    def on_files_dropped(self, file_paths: List[str], screen_pos: QPoint):
        mode = getattr(self, "_pending_mode", "convert")
        self._pending_mode = "convert"
        self.radial_menu.show_for_files(file_paths, screen_pos, initial_mode=mode)

    def on_files_picked_manually(self, file_paths: List[str]):
        pos = QCursor.pos()
        self.radial_menu.show_for_files(file_paths, pos, initial_mode="convert")

    def on_global_drag_detected(self, file_paths: List[str], screen_pos: QPoint, mode: str):
        self.radial_menu.show_for_files(file_paths, screen_pos, initial_mode=mode)

    def on_drag_mode_detected(self, screen_pos: QPoint, mode: str):
        """The system would not tell us what is being dragged, but we know
        which mode was asked for. Remember it and apply it to the drop."""
        self._pending_mode = mode
        self.toast.show_message("Opal", f"{mode.title()} mode armed - drop the file on Opal.")

    def on_hotkey_triggered(self):
        clipboard = self.app.clipboard()
        mime = clipboard.mimeData()
        if mime.hasUrls():
            urls = mime.urls()
            valid = [u.toLocalFile() for u in urls if u.isLocalFile()]
            if valid:
                self.radial_menu.show_for_files(valid, QCursor.pos(), initial_mode="convert")
                return

        # Instant Clipboard Screenshot (Win+Shift+S or browser copied image)
        if mime.hasImage():
            image = clipboard.image()
            if not image.isNull():
                import time
                config = ConfigManager.load_config()
                mode = config.get("output_mode", "same_as_source")
                custom_dir = config.get("custom_output_dir", "")
                if mode == "custom" and custom_dir and Path(custom_dir).exists():
                    target_dir = Path(custom_dir)
                else:
                    target_dir = Path.home() / "Downloads"
                target_dir.mkdir(parents=True, exist_ok=True)
                temp_file = target_dir / f"Screenshot_{int(time.time())}.png"
                image.save(str(temp_file), "PNG")
                self.radial_menu.show_for_files([str(temp_file)], QCursor.pos(), initial_mode="convert")
                return

        files, _ = QFileDialog.getOpenFileNames(
            None,
            "Select File(s) for Opal",
            "",
            "All Files (*.*)"
        )
        if files:
            self.radial_menu.show_for_files(files, QCursor.pos(), initial_mode="convert")

    def on_action_selected(self, file_paths: List[str], action_id: str):
        if action_id == "pdf_dsc_sign":
            # Open the document in the studio and start the certificate flow.
            for fp in file_paths:
                self.studio.open_file(fp)
            self.studio.show()
            self.studio.raise_()
            from opal_studio.viewer_pdf import PdfStudio
            for index in range(self.studio.tabs.count()):
                widget = self.studio.tabs.widget(index)
                if isinstance(widget, PdfStudio):
                    self.studio.setCurrentIndex(index)
                    widget._open_dsc()
                    break
            return

        if action_id == "float":
            for fp in file_paths:
                self.studio.open_file(fp)
            self.studio.show()
            self.studio.raise_()
            self.studio.activateWindow()
            self.toast.show_message("Opal", f"Studio opened with {len(file_paths)} file(s).")
            return

        count = len(file_paths)
        target_desc = Path(file_paths[0]).name if count == 1 else f"{count} files"
        self.toast.show_message("Opal", f"Processing {target_desc}...")

        self.current_worker = ConversionWorker(file_paths, action_id)
        self.current_worker.finished_signal.connect(self.on_conversion_finished)
        self.current_worker.start()

    def on_conversion_finished(self, batch_result):
        if batch_result.succeeded > 0:
            first_output = batch_result.outputs[0] if batch_result.outputs else None
            saved_str = f" (Saved {batch_result.saved_bytes // 1024} KB)" if batch_result.saved_bytes > 0 else ""
            self.toast.show_message("Conversion Complete", f"{batch_result.message}{saved_str}", target_path=first_output, is_error=False)
        else:
            self.toast.show_message("Conversion Error", batch_result.message, is_error=True)


def main():
    # Command line mode: no window, just do the work and report.
    argv = sys.argv[1:]
    cli_flags = ("--convert", "--tool", "--catalog", "--info", "--list-formats", "--to")
    if any(a.startswith(cli_flags) for a in argv):
        try:
            if sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
                sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
        from opal_studio.cli import main as cli_main
        sys.exit(cli_main(argv))

    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName("Opal")
    app.setOrganizationName("Opal")
    app.setQuitOnLastWindowClosed(False)
    from opal_studio.theme import build_stylesheet
    app.setStyleSheet(build_stylesheet())

    tangerine = OpalApp(app)

    # If launched with file arguments (e.g. from context menu)
    if len(sys.argv) > 1:
        args_files = [f for f in sys.argv[1:] if os.path.exists(f)]
        studio_requested = "--studio" in sys.argv
        if args_files:
            tangerine.tray.show()
            if studio_requested or tangerine.config.get("open_in_studio", False):
                for f in args_files:
                    tangerine.studio.open_file(f)
                tangerine.studio.show()
                tangerine.studio.raise_()
                tangerine.studio.activateWindow()
            else:
                tangerine.radial_menu.show_for_files(args_files, QCursor.pos(),
                                                     initial_mode="convert")
        else:
            tangerine.show()
    else:
        tangerine.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
