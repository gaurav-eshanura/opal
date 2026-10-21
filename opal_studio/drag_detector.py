"""
Opal - Global Drag & Modifier Key Detector
Plain English: This watches for the moment you are dragging a file while
holding Shift, Alt or Ctrl, and summons the Radial Wheel under your cursor.

It works the same way on Windows, macOS and Linux. On the platforms where the
system can tell us which files you have selected, the wheel appears as you
drag. Where it cannot, the mode you chose is remembered and applied to the
file when you drop it on Opal.
"""

import math
import time
from typing import List

from PySide6.QtCore import QThread, Signal, QPoint

from opal_studio.input_watch import InputWatcher


class GlobalDragDetector(QThread):
    # Emits (file_paths, screen_pos, mode)
    drag_triggered = Signal(list, QPoint, str)
    # Emits (screen_pos, mode) when the files cannot be read yet.
    mode_detected = Signal(QPoint, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.running = True
        self.enabled = True
        self.watcher = InputWatcher()

    def stop(self):
        self.running = False
        # Make sure the polling thread really finishes: destroying a QThread that
        # is still running aborts the whole process on Windows.
        if self.isRunning():
            self.wait(2000)

    def run(self):
        if not self.watcher.available():
            return

        is_dragging = False
        drag_start_pos = (0, 0)
        has_triggered_this_drag = False

        while self.running:
            try:
                if not self.enabled:
                    time.sleep(0.1)
                    continue

                state = self.watcher.state()

                if state.left_down:
                    if not is_dragging:
                        drag_start_pos = (state.x, state.y)
                        is_dragging = True
                        has_triggered_this_drag = False
                    else:
                        dx = state.x - drag_start_pos[0]
                        dy = state.y - drag_start_pos[1]
                        dist = math.hypot(dx, dy)

                        # A threshold of 12 pixels confirms a real drag rather
                        # than a click.
                        if dist > 12 and not has_triggered_this_drag and state.any_modifier():
                            mode = state.mode()
                            files = self.watcher.selected_files()
                            if files:
                                has_triggered_this_drag = True
                                pt = QPoint(state.x, state.y)
                                self.drag_triggered.emit(files, pt, mode)
                            else:
                                # The system will not tell us what is being
                                # dragged; remember the mode for the drop.
                                has_triggered_this_drag = True
                                pt = QPoint(state.x, state.y)
                                self.mode_detected.emit(pt, mode)
                else:
                    is_dragging = False
                    has_triggered_this_drag = False

                time.sleep(0.02)  # 50 Hz loop

            except Exception:
                time.sleep(0.05)
