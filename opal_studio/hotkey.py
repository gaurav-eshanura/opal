"""
Opal - Global Hotkey Listener (Windows / macOS / Linux)
Plain English: This lets you summon Opal from anywhere on the computer with a
keyboard shortcut, without needing to find where the app is running.

On Windows the shortcut is registered with the system, so it works even when
another program has the focus. On macOS and Linux the same combination is
watched directly, which means it fires from anywhere too.

All the native work lives in opal_studio/input_watch.py, so this file stays
free of operating-system calls.
"""

import sys
import threading
import time
from typing import Optional

from PySide6.QtCore import QObject, Signal

from opal_studio.input_watch import InputWatcher, register_native_hotkey

IS_WINDOWS = sys.platform.startswith("win")


class _PollingHotkey(threading.Thread):
    """Watches the modifier and key combination directly.

    Used where the system will not register a shortcut for us. The thread
    sleeps between checks, so it costs almost nothing.
    """

    def __init__(self, on_fire, watcher: Optional[InputWatcher] = None):
        super().__init__(daemon=True)
        self.on_fire = on_fire
        self.watcher = watcher or InputWatcher()
        self.running = True
        self._fired = False

    def stop(self):
        self.running = False

    def run(self):
        if not self.watcher.available():
            return
        while self.running:
            try:
                state = self.watcher.state()
                combo = state.ctrl and state.alt and state.t_down
                if combo and not self._fired:
                    self._fired = True
                    self.on_fire()
                elif not combo:
                    self._fired = False
            except Exception:
                pass
            time.sleep(0.03)


class GlobalHotkeyManager(QObject):
    hotkey_triggered = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.filter = None
        self.is_registered = False
        self._poller: Optional[_PollingHotkey] = None

    def register(self, app, vk_key=ord("T"), modifiers=0x0002 | 0x0001):
        """
        Registers the global hotkey.
        Default: Ctrl + Alt + T (MOD_CONTROL=0x0002, MOD_ALT=0x0001)
        """
        if IS_WINDOWS:
            filter = register_native_hotkey(app, vk_key, modifiers,
                                            self.hotkey_triggered.emit)
            if filter is not None:
                self.filter = filter
                self.is_registered = True
                return True
        return self._register_polling()

    def _register_polling(self) -> bool:
        self._poller = _PollingHotkey(self.hotkey_triggered.emit)
        self._poller.start()
        self.is_registered = True
        return True

    def unregister(self, app):
        if self._poller is not None:
            self._poller.stop()
            self._poller = None
        if self.filter is not None:
            try:
                app.removeNativeEventFilter(self.filter)
            except Exception:
                pass
            self.filter = None
        self.is_registered = False
