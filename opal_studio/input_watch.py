"""
Opal - Cross-platform input watcher
Plain English: Reads the global mouse and keyboard state, so Opal can notice
that you are dragging a file while holding a key - on Windows, macOS and
Linux alike.

Each platform answers the same three questions: where is the pointer, is the
left button down, and which modifier and letter keys are held. The rest of
the app never needs to know which platform it is running on.
"""

import ctypes
import os
import subprocess
import sys
from dataclasses import dataclass
from typing import List, Optional, Tuple

IS_WINDOWS = sys.platform.startswith("win")
IS_MAC = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")

# Modifier bits, the same meaning on every platform.
MOD_SHIFT = 1
MOD_ALT = 2
MOD_CTRL = 4
MOD_CMD = 8

# Key codes we care about, mapped per platform.
KEY_T = "t"


@dataclass
class InputState:
    """What the pointer and the keyboard are doing right now."""
    x: int = 0
    y: int = 0
    left_down: bool = False
    shift: bool = False
    alt: bool = False
    ctrl: bool = False
    cmd: bool = False
    t_down: bool = False

    def any_modifier(self) -> bool:
        return self.shift or self.alt or self.ctrl or self.cmd

    def mode(self) -> str:
        """Which wheel the user is asking for."""
        if self.alt:
            return "tools"
        if self.ctrl:
            return "actions"
        if self.cmd:
            return "actions"
        return "convert"


# ---------------------------------------------------------------------------
# Windows
# ---------------------------------------------------------------------------

class _WindowsBackend:
    VK_LBUTTON = 0x01
    VK_SHIFT = 0x10
    VK_CONTROL = 0x11
    VK_MENU = 0x12
    VK_LWIN = 0x5B
    VK_T = 0x54

    def __init__(self):
        import win32api  # noqa: F401
        import win32gui  # noqa: F401
        self._api = win32api
        self._gui = win32gui

    def state(self) -> InputState:
        api = self._api
        pos = self._gui.GetCursorPos()
        return InputState(
            x=int(pos[0]), y=int(pos[1]),
            left_down=bool(api.GetAsyncKeyState(self.VK_LBUTTON) & 0x8000),
            shift=bool(api.GetAsyncKeyState(self.VK_SHIFT) & 0x8000),
            alt=bool(api.GetAsyncKeyState(self.VK_MENU) & 0x8000),
            ctrl=bool(api.GetAsyncKeyState(self.VK_CONTROL) & 0x8000),
            cmd=bool(api.GetAsyncKeyState(self.VK_LWIN) & 0x8000),
            t_down=bool(api.GetAsyncKeyState(self.VK_T) & 0x8000),
        )

    def selected_files(self) -> List[str]:
        """The files selected in the file manager that has the focus."""
        paths: List[str] = []
        try:
            import pythoncom
            import win32com.client

            pythoncom.CoInitialize()
            shell = win32com.client.Dispatch("Shell.Application")
            for window in shell.Windows():
                try:
                    items = window.Document.SelectedItems()
                    if items and items.Count > 0:
                        for item in items:
                            paths.append(item.Path)
                        break
                except Exception:
                    continue
            pythoncom.CoUninitialize()
        except Exception:
            pass
        return paths


# ---------------------------------------------------------------------------
# macOS (CoreGraphics - public API, no extra dependency)
# ---------------------------------------------------------------------------

class _MacBackend:
    # CoreGraphics event source constants
    _HID_SYSTEM = 1
    _LEFT_BUTTON = 0
    _FLAG_SHIFT = 0x20000
    _FLAG_ALT = 0x80000
    _FLAG_CONTROL = 0x40000
    _FLAG_COMMAND = 0x100000

    def __init__(self):
        cg = ctypes.cdll.LoadLibrary(
            "/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")
        self._cg = cg
        cg.CGEventSourceCreate.restype = ctypes.c_void_p
        cg.CGEventSourceCreate.argtypes = [ctypes.c_int]
        cg.CGEventSourceButtonState.restype = ctypes.c_bool
        cg.CGEventSourceButtonState.argtypes = [ctypes.c_void_p, ctypes.c_int]
        cg.CGEventSourceFlagsState.restype = ctypes.c_ulong
        cg.CGEventSourceFlagsState.argtypes = [ctypes.c_void_p]
        cg.CGEventSourceKeyState.restype = ctypes.c_bool
        cg.CGEventSourceKeyState.argtypes = [ctypes.c_void_p, ctypes.c_ushort]
        cg.CGEventCreate.restype = ctypes.c_void_p
        cg.CGEventCreate.argtypes = [ctypes.c_void_p]
        cg.CGEventGetLocation.restype = ctypes.c_void_p
        cg.CGEventGetLocation.argtypes = [ctypes.c_void_p]
        self._source = cg.CGEventSourceCreate(self._HID_SYSTEM)
        # The virtual key code of "T" on a US layout.
        self._t_keycode = 20

    def state(self) -> InputState:
        cg = self._cg
        source = self._source
        flags = cg.CGEventSourceFlagsState(source)
        # The cursor lives on the newest mouse event.
        event = cg.CGEventCreate(None)
        x = y = 0
        if event:
            point = cg.CGEventGetLocation(event)
            if point:
                # CGPoint is two doubles.
                raw = ctypes.cast(point, ctypes.POINTER(ctypes.c_double))
                x, y = int(raw[0]), int(raw[1])
        return InputState(
            x=x, y=y,
            left_down=bool(cg.CGEventSourceButtonState(source, self._LEFT_BUTTON)),
            shift=bool(flags & self._FLAG_SHIFT),
            alt=bool(flags & self._FLAG_ALT),
            ctrl=bool(flags & self._FLAG_CONTROL),
            cmd=bool(flags & self._FLAG_COMMAND),
            t_down=bool(cg.CGEventSourceKeyState(source, self._t_keycode)),
        )

    def selected_files(self) -> List[str]:
        """The files selected in the Finder window that has the focus."""
        paths: List[str] = []
        script = (
            'tell application "System Events" to tell (first process whose frontmost is true)\n'
            '  try\n'
            '    set out to ""\n'
            '    repeat with row in (every row of every list of every UI element of '
            'every list of every UI element of every scroll area of every window)\n'
            '      try\n'
            '        set out to out & (value of attribute "AXURL" of row) & linefeed\n'
            '      end try\n'
            '    end repeat\n'
            '    return out\n'
            '  end try\n'
            'end tell\n'
        )
        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True, text=True, timeout=2.5)
            if result.returncode == 0 and result.stdout:
                for line in result.stdout.splitlines():
                    line = line.strip()
                    if line.startswith("/"):
                        paths.append(line)
        except Exception:
            pass
        if not paths:
            paths = self._finder_selection()
        return paths

    def _finder_selection(self) -> List[str]:
        """A simpler Finder query, used when the UI scripting route comes back empty."""
        paths: List[str] = []
        script = ('tell application "Finder" to get POSIX path of '
                  '(selection of front window as alias)')
        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True, text=True, timeout=2.5)
            if result.returncode == 0 and result.stdout:
                paths = [p.strip() for p in result.stdout.split(",") if p.strip()]
        except Exception:
            pass
        return paths


# ---------------------------------------------------------------------------
# Linux (X11)
# ---------------------------------------------------------------------------

class _X11Backend:
    def __init__(self):
        self._x = ctypes.cdll.LoadLibrary("libX11.so.6")
        self._x.XOpenDisplay.restype = ctypes.c_void_p
        self._x.XOpenDisplay.argtypes = [ctypes.c_char_p]
        self._x.XQueryPointer.restype = ctypes.c_int
        self._x.XQueryPointer.argtypes = [
            ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong),
            ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_uint),
            ctypes.POINTER(ctypes.c_uint)]
        self._x.XQueryKeymap.restype = ctypes.c_int
        self._x.XQueryKeymap.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_char)]
        self._x.XKeysymToKeycode.restype = ctypes.c_ubyte
        self._x.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        self._x.XStringToKeysym.restype = ctypes.c_ulong
        self._x.XStringToKeysym.argtypes = [ctypes.c_char_p]
        self._x.XFree.argtypes = [ctypes.c_void_p]
        self._display = self._x.XOpenDisplay(None)
        self._root = 0
        if self._display:
            self._x.XDefaultRootWindow.restype = ctypes.c_ulong
            self._x.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
            self._root = self._x.XDefaultRootWindow(self._display)
            self._t_keycode = self._x.XKeysymToKeycode(
                self._display, self._x.XStringToKeysym(b"T"))

    def state(self) -> InputState:
        if not self._display:
            return InputState()
        x = ctypes.c_ulong()
        y = ctypes.c_ulong()
        win = ctypes.c_ulong()
        root = ctypes.c_ulong()
        mask = ctypes.c_uint()
        buttons = ctypes.c_uint()
        self._x.XQueryPointer(self._display, self._root,
                              ctypes.byref(root), ctypes.byref(x), ctypes.byref(y),
                              ctypes.byref(win), ctypes.byref(win),
                              ctypes.byref(mask), ctypes.byref(buttons))
        # ShiftMask=1, LockMask=2, ControlMask=4, Mod1Mask=8 (Alt)
        return InputState(
            x=int(x.value), y=int(y.value),
            left_down=bool(buttons.value & 0x100),
            shift=bool(mask.value & 1),
            ctrl=bool(mask.value & 4),
            alt=bool(mask.value & 8),
            cmd=bool(mask.value & 64),
            t_down=self._key_down(),
        )

    def _key_down(self) -> bool:
        if not self._display or not self._t_keycode:
            return False
        keys = (ctypes.c_char * 32)()
        self._x.XQueryKeymap(self._display, keys)
        index = self._t_keycode // 8
        if index >= 32:
            return False
        byte = keys[index]
        return bool(byte & (1 << (self._t_keycode % 8)))

    def selected_files(self) -> List[str]:
        """The files a drag is carrying, read from the X11 drag-and-drop selection."""
        paths: List[str] = []
        if not self._display:
            return paths
        try:
            paths = _x11_dnd_selection(self._x, self._display, self._root)
        except Exception:
            paths = []
        return paths


def _x11_dnd_selection(xlib, display, root) -> List[str]:
    """Reads the URI list an X11 drag is offering, if there is one."""
    xlib.XGetSelectionOwner.restype = ctypes.c_void_p
    xlib.XGetSelectionOwner.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    xlib.XInternAtom.restype = ctypes.c_ulong
    xlib.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_bool]
    xlib.XConvertSelection.restype = ctypes.c_int
    xlib.XConvertSelection.argtypes = [
        ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_void_p,
        ctypes.c_int, ctypes.c_ulong]
    xlib.XGetWindowProperty.restype = ctypes.c_int
    xlib.XGetWindowProperty.argtypes = [
        ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_long,
        ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_ulong),
        ctypes.POINTER(ctypes.POINTER(ctypes.c_ubyte)), ctypes.POINTER(ctypes.c_ulong)]
    xlib.XDefaultRootWindow.restype = ctypes.c_ulong
    xlib.XDefaultRootWindow.argtypes = [ctypes.c_void_p]

    xdnd = xlib.XInternAtom(display, b"XdndSelection", False)
    uri_list = xlib.XInternAtom(display, b"text/uri-list", False)
    target = xlib.XInternAtom(display, b"UTF8_STRING", False)
    if not xdnd:
        return []
    owner = xlib.XGetSelectionOwner(display, xdnd)
    if not owner:
        return []
    request = xlib.XConvertSelection(display, xdnd, target, 0, 0, 0, None, 0)
    if not request:
        return []
    # The owner answers asynchronously; give it a moment and read the property.
    import time
    for _ in range(20):
        time.sleep(0.02)
        actual_type = ctypes.c_ulong()
        actual_format = ctypes.c_int()
        nitems = ctypes.c_ulong()
        bytes_after = ctypes.c_ulong()
        data = ctypes.POINTER(ctypes.c_ubyte)()
        prop = xlib.XGetWindowProperty(display, owner, uri_list, 0, 65536, False,
                                       0, ctypes.byref(actual_type),
                                       ctypes.byref(actual_format), ctypes.byref(nitems),
                                       ctypes.byref(bytes_after), ctypes.byref(data))
        if prop and nitems.value and data:
            raw = ctypes.string_at(data, nitems.value)
            xlib.XFree(data)
            for chunk in raw.decode("utf-8", "replace").split("\n"):
                chunk = chunk.strip()
                if chunk.startswith("file://"):
                    from urllib.parse import unquote, urlparse
                    paths = unquote(urlparse(chunk).path)
                    yield_paths = [paths]
                    return yield_paths
        if data:
            xlib.XFree(data)
    return []


# ---------------------------------------------------------------------------
# The public watcher
# ---------------------------------------------------------------------------

class InputWatcher:
    """Reads the global input state, whichever platform we are on."""

    def __init__(self):
        self._backend = None
        self._failed = False

    def _get_backend(self):
        if self._backend is not None or self._failed:
            return self._backend
        try:
            if IS_WINDOWS:
                self._backend = _WindowsBackend()
            elif IS_MAC:
                self._backend = _MacBackend()
            elif IS_LINUX:
                self._backend = _X11Backend()
        except Exception:
            self._failed = True
            self._backend = None
        return self._backend

    def available(self) -> bool:
        return self._get_backend() is not None

    def state(self) -> InputState:
        backend = self._get_backend()
        if backend is None:
            return InputState()
        try:
            return backend.state()
        except Exception:
            return InputState()

    def selected_files(self) -> List[str]:
        backend = self._get_backend()
        if backend is None:
            return []
        try:
            return backend.selected_files()
        except Exception:
            return []
