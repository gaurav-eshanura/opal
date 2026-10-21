"""
Opal - Cross-platform integration layer
Plain English: Everything that only Windows can do lives here, behind one small
API, so the same build runs on macOS and Linux. If a platform cannot do
something (a shell extension, a global hotkey) the app simply carries on
without it instead of crashing.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

IS_WINDOWS = sys.platform.startswith("win")
IS_MAC = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")
APP_NAME = "Opal"


def platform_name() -> str:
    if IS_WINDOWS:
        return "Windows"
    if IS_MAC:
        return "macOS"
    if IS_LINUX:
        return "Linux"
    return sys.platform or "unknown"


# ---------------------------------------------------------------------------
# Opening and revealing files
# ---------------------------------------------------------------------------

def open_with_default(path: str) -> bool:
    """Opens a file with the operating system's default application."""
    p = str(path)
    try:
        if IS_WINDOWS:
            os.startfile(p)  # type: ignore[attr-defined]
            return True
        if IS_MAC:
            subprocess.Popen(["open", p])
            return True
        subprocess.Popen(["xdg-open", p])
        return True
    except Exception:
        return False


def reveal_in_file_manager(path: str) -> bool:
    """Shows the file inside Explorer / Finder / the Linux file manager."""
    p = Path(path)
    try:
        if IS_WINDOWS:
            subprocess.Popen(["explorer", f"/select,{p.resolve()}"])
            return True
        if IS_MAC:
            subprocess.Popen(["open", "-R", str(p.resolve())])
            return True
        # Linux: try the common file managers, then fall back to the folder
        for cmd in (["nautilus", "--select", str(p.resolve())],
                     ["dolphin", "--select", str(p.resolve())],
                     ["nemo", str(p.parent)]):
            if shutil.which(cmd[0]):
                subprocess.Popen(cmd)
                return True
        subprocess.Popen(["xdg-open", str(p.parent)])
        return True
    except Exception:
        return False


def open_terminal(path: str) -> bool:
    """Opens a terminal window in the file's folder."""
    folder = str(Path(path).parent if Path(path).is_file() else path)
    try:
        if IS_WINDOWS:
            subprocess.Popen(["powershell", "-NoExit", "-Command", f"Set-Location '{folder}'"])
            return True
        if IS_MAC:
            subprocess.Popen(["open", "-a", "Terminal", folder])
            return True
        for cmd in ("x-terminal-emulator", "gnome-terminal", "konsole", "xfce4-terminal", "xterm"):
            if shutil.which(cmd):
                subprocess.Popen([cmd], cwd=folder)
                return True
        return False
    except Exception:
        return False


def copy_text_to_clipboard(text: str) -> bool:
    """Copies text to the system clipboard without needing a GUI toolkit."""
    try:
        if IS_WINDOWS:
            payload = text.replace("'", "''")
            subprocess.Popen(["powershell", "-NoProfile", "-Command",
                              f"Set-Clipboard -Value '{payload}'"],
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            return True
        if IS_MAC:
            proc = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
            proc.communicate(text.encode("utf-8"))
            return True
        for cmd in ("wl-copy", "xclip", "xsel"):
            if shutil.which(cmd):
                proc = subprocess.Popen([cmd, "-selection", "clipboard"], stdin=subprocess.PIPE)
                proc.communicate(text.encode("utf-8"))
                return True
        return False
    except Exception:
        return False


def send_to_trash(path: str) -> bool:
    """Moves a file to the system trash (or the recycle bin on Windows)."""
    try:
        from send2trash import send2trash
        send2trash(str(path))
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Start at login
# ---------------------------------------------------------------------------

def startup_supported() -> bool:
    """Whether this platform can register the app to start at login."""
    return IS_WINDOWS or IS_LINUX


def set_startup_entry(enable: bool, command: Optional[str] = None) -> bool:
    """
    Registers (or removes) the app in the system's start-up list.
    Windows uses the Run key, Linux writes a .desktop entry. macOS is handled
    by the user in System Settings, so we politely do nothing there.
    """
    if command is None:
        command = _startup_command()

    if IS_WINDOWS:
        try:
            import winreg
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0,
                                winreg.KEY_SET_VALUE) as key:
                if enable:
                    winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, command)
                else:
                    try:
                        winreg.DeleteValue(key, APP_NAME)
                    except FileNotFoundError:
                        pass
            return True
        except Exception:
            return False

    if IS_LINUX:
        try:
            autostart = Path.home() / ".config" / "autostart"
            autostart.mkdir(parents=True, exist_ok=True)
            entry = autostart / "opal.desktop"
            if enable:
                entry.write_text(
                    "[Desktop Entry]\nType=Application\nName=Opal\n"
                    f"Exec={command}\nTerminal=false\nX-GNOME-Autostart-enabled=true\n",
                    encoding="utf-8")
            elif entry.exists():
                entry.unlink()
            return True
        except Exception:
            return False

    return False


def _startup_command() -> str:
    """The command that launches this app with no arguments."""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    main_py = Path(__file__).parent / "main.py"
    python = sys.executable
    pythonw = python.replace("python.exe", "pythonw.exe")
    if Path(pythonw).exists():
        python = pythonw
    return f'"{python}" "{main_py}"'


# ---------------------------------------------------------------------------
# File-manager integration ("Open with Opal")
# ---------------------------------------------------------------------------

def context_menu_supported() -> bool:
    return IS_WINDOWS or IS_LINUX


def install_context_menu() -> bool:
    """
    Adds "Convert with Opal" to the file manager.
    Windows: the per-user Run/registry shell key. Linux: a shared-mime handler.
    macOS: not supported by the system, so we say so instead of failing.
    """
    if IS_WINDOWS:
        try:
            import winreg
            command = f'{_startup_command()} "%1"'
            key_path = r"Software\Classes\*\shell\Opal"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                winreg.SetValue(key, "", winreg.REG_SZ, "Convert with Opal")
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path + r"\command") as key:
                winreg.SetValue(key, "", winreg.REG_SZ, command)
            return True
        except Exception:
            return False

    if IS_LINUX:
        try:
            apps = Path.home() / ".local" / "share" / "applications"
            apps.mkdir(parents=True, exist_ok=True)
            desktop = apps / "opal.desktop"
            desktop.write_text(
                "[Desktop Entry]\nType=Application\nName=Convert with Opal\n"
                f"Exec={_startup_command()} %f\nTerminal=false\n"
                "MimeType=application/pdf;image/*;video/*;audio/*;text/*;\n",
                encoding="utf-8")
            return True
        except Exception:
            return False

    return False


def uninstall_context_menu() -> bool:
    """Removes the file-manager entry."""
    if IS_WINDOWS:
        try:
            import winreg
            key_path = r"Software\Classes\*\shell\Opal"
            for sub in (r"\command", ""):
                try:
                    winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key_path + sub)
                except FileNotFoundError:
                    pass
            return True
        except Exception:
            return False

    if IS_LINUX:
        try:
            desktop = Path.home() / ".local" / "share" / "applications" / "opal.desktop"
            if desktop.exists():
                desktop.unlink()
            return True
        except Exception:
            return False

    return False


# ---------------------------------------------------------------------------
# Where the app keeps its settings
# ---------------------------------------------------------------------------

def portable_root() -> Optional[Path]:
    """
    In portable mode the settings live in a folder next to the executable, so
    the whole app can be carried on a USB stick with no trace left behind.
    """
    marker = None
    if getattr(sys, "frozen", False):
        marker = Path(sys.executable).parent / "portable.txt"
    else:
        marker = Path(__file__).parent.parent / "portable.txt"
    if marker.exists():
        base = marker.parent
        for candidate in (base / "OpalData", base / "data"):
            if candidate.is_dir():
                return candidate
        target = base / "OpalData"
        target.mkdir(parents=True, exist_ok=True)
        return target
    return None


def user_data_dir() -> Path:
    """The folder that holds settings, history and cached models."""
    portable = portable_root()
    if portable:
        return portable
    if IS_MAC:
        base = Path.home() / "Library" / "Application Support"
    elif IS_LINUX:
        base = Path.home() / ".local" / "share"
    else:
        base = Path(os.environ.get("APPDATA", Path.home()))
    target = base / "Opal"
    _migrate_legacy_data(base, target)
    target.mkdir(parents=True, exist_ok=True)
    return target


def _migrate_legacy_data(base: Path, target: Path) -> None:
    """Carries the data folder over from the product's previous names.

    Settings, history and the cached models live in here, so a rename must
    not leave a returning user with an empty app.
    """
    if target.exists():
        return
    for old_name in ("RindStudio", "Tangerine"):
        old = base / old_name
        if not old.is_dir():
            continue
        try:
            old.rename(target)
        except OSError:
            pass
        break


def is_portable() -> bool:
    return portable_root() is not None
