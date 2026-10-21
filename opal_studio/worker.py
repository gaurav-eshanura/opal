"""
Opal - Production Non-Blocking Worker Thread
Plain English: This worker processes files and batches in the background so your desktop,
mouse cursor, and open apps remain fast and responsive during conversions.
"""

from typing import List
from PySide6.QtCore import QThread, Signal
from opal_studio.engine import OpalEngine, BatchConversionResult


class ConversionWorker(QThread):
    finished_signal = Signal(object)  # BatchConversionResult

    def __init__(self, file_paths: List[str], action_id: str, parent=None):
        super().__init__(parent)
        self.file_paths = file_paths
        self.action_id = action_id

    def run(self):
        result = OpalEngine.execute_batch(self.file_paths, self.action_id)
        self.finished_signal.emit(result)
