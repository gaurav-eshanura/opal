"""
Opal - Global Hotkey Listener (Windows / macOS / Linux)
Plain English: This lets you summon Opal from anywhere on the computer with a
keyboard shortcut, without needing to find where the app is running.

On Windows the shortcut is registered with the system, so it works even when
another program has the focus. On macOS and Linux the same combination is
watched directly, which means it fires from anywhere too.
"""

import sys
import threading
import time
from typing import Optional

from PySide6.QtCore import QAbstractNativeEventFilter, QObject, Signal

from opal_studio.input_watch import InputWatcher

IS_WINDOWS = sys.platform.startswith("win")


class WindowsHotkeyFilter(QAbstractNativeEventFilter):
    WM_HOTKEY = 0x0312

    def __init__(self, hotkey_id: int, callback):
        super().__init__()
        self.hotkey_id = hotkey_id
        self.callback = callback

    def nativeEventFilter(self, eventType, message):
        if eventType == b"windows_generic_MSG":
            try:
                addr = int(message)
                if addr != 0:
                    import ctypes
                    from ctypes import wintypes

                    msg = wintypes.MSG.from_address(addr)
                    if msg.message == self.WM_HOTKEY and msg.wParam == self.hotkey_id:
                        self.callback()
                        return True, 0
            except Exception:
                pass
        return False, 0


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
        self.hotkey_id = 1001
        self._poller: Optional[_PollingHotkey] = None

    def register(self, app, vk_key=ord("T"), modifiers=0x0002 | 0x0001):
        """
        Registers the global hotkey.
        Default: Ctrl + Alt + T (MOD_CONTROL=0x0002, MOD_ALT=0x0001)
        """
        if IS_WINDOWS:
            return self._register_windows(app, vk_key, modifiers)
        return self._register_polling()

    def _register_windows(self, app, vk_key, modifiers) -> bool:
        try:
            import ctypes

            user32 = ctypes.windll.user32
            success = user32.RegisterHotKey(None, self.hotkey_id, modifiers, vk_key)
            if success:
                self.filter = WindowsHotkeyFilter(self.hotkey_id, self.hotkey_triggered.emit)
                app.installNativeEventFilter(self.filter)
                self.is_registered = True
                return True
        except Exception:
            pass
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
        if self.is_registered and IS_WINDOWS:
            try:
                import ctypes

                ctypes.windll.user32.UnregisterHotKey(None, self.hotkey_id)
            except Exception:
                pass
            if self.filter:
                app.removeNativeEventFilter(self.filter)
        self.is_registered = False
