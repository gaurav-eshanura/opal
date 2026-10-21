"""
Opal - Automated Watch Folder (Surpasses Filee)
Plain English: This monitors an automatic folder (like Downloads/Opal_AutoConvert).
Whenever you drop or download a file into it, Opal automatically converts,
compresses, or extracts it in the background without needing a single click.
"""

import time
import os
import shutil
from pathlib import Path
from typing import Optional, Set

from PySide6.QtCore import QThread, Signal
from opal_studio.config import ConfigManager
from opal_studio.engine import OpalEngine


class WatchFolderWorker(QThread):
    """Background monitor thread that watches a folder and auto-converts files."""
    file_processed_signal = Signal(str, str, str)  # (original_name, output_path, message)

    def __init__(self, watch_path: Optional[str] = None):
        super().__init__()
        self.watch_path = Path(watch_path) if watch_path else Path.home() / "Downloads" / "Opal_AutoConvert"
        self.output_dir = self.watch_path / "Output"
        self.processed_dir = self.watch_path / "Originals"
        self.is_running = True
        self.known_files: Set[str] = set()

    def run(self):
        try:
            self.watch_path.mkdir(parents=True, exist_ok=True)
            self.output_dir.mkdir(parents=True, exist_ok=True)
            self.processed_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

        # Populate initial existing files so we don't re-convert old files
        if self.watch_path.exists():
            for p in self.watch_path.iterdir():
                if p.is_file():
                    self.known_files.add(str(p.resolve()))

        while self.is_running:
            try:
                if self.watch_path.exists():
                    current_items = [p for p in self.watch_path.iterdir() if p.is_file()]
                    for item in current_items:
                        resolved = str(item.resolve())
                        if resolved not in self.known_files:
                            self.known_files.add(resolved)
                            self._process_incoming_file(item)
            except Exception:
                pass

            # Sleep 1.5s between scans
            time.sleep(1.5)

    def _process_incoming_file(self, file_path: Path):
        # 1. Wait for file to finish downloading/copying (size stability check)
        prev_size = -1
        stable_count = 0
        for _ in range(10):
            if not file_path.exists():
                return
            try:
                sz = file_path.stat().st_size
                if sz == prev_size and sz > 0:
                    stable_count += 1
                    if stable_count >= 2:
                        break
                else:
                    stable_count = 0
                prev_size = sz
            except Exception:
                pass
            time.sleep(0.5)

        if not file_path.exists() or file_path.stat().st_size == 0:
            return

        # Ignore temporary browser download files (.crdownload, .tmp, .part)
        ext = file_path.suffix.lower()
        if ext in (".tmp", ".crdownload", ".part", ".partial", ".bak"):
            return

        cat = OpalEngine.get_file_category([str(file_path)])
        dest_action = None

        # Intelligent auto-routing:
        if ext in (".heic", ".avif"):
            dest_action = "jpg"
        elif cat == "image":
            # If user drops image with keyword 'nobg', remove bg, else webp
            if "nobg" in file_path.stem.lower():
                dest_action = "remove_bg"
            else:
                dest_action = "webp"
        elif cat == "pdf":
            dest_action = "compress_pdf"
        elif cat == "document":
            dest_action = "pdf"
        elif cat in ("video", "audio") and file_path.stat().st_size > 25 * 1024 * 1024:
            dest_action = "fit_25mb"

        if not dest_action:
            return

        # Execute conversion
        res = OpalEngine.execute_single(str(file_path), dest_action)
        if res.success and res.output_path:
            # Move converted output to watch_path/Output
            try:
                out_p = Path(res.output_path)
                if out_p.exists() and out_p.parent != self.output_dir:
                    final_dst = self.output_dir / out_p.name
                    if final_dst.exists():
                        final_dst.unlink()
                    shutil.move(str(out_p), str(final_dst))
                    res.output_path = str(final_dst)
            except Exception:
                pass

            # Move source file to Originals
            try:
                orig_dst = self.processed_dir / file_path.name
                if orig_dst.exists():
                    orig_dst.unlink()
                shutil.move(str(file_path), str(orig_dst))
            except Exception:
                pass

            self.file_processed_signal.emit(
                file_path.name,
                res.output_path,
                f"Auto-Converted: {file_path.name} -> {Path(res.output_path).name}"
            )

    def stop(self):
        self.is_running = False
        if self.isRunning():
            self.wait(3000)
