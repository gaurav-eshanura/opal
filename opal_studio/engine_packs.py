"""
Opal - On-demand engine packs
Plain English: Some tools need heavy libraries (the AI vision stack, the media
encoder). Rather than shipping hundreds of megabytes to everybody, Opal
installs an engine the first time you actually use that tool - into a folder
next to the app or in your user data. After that it works completely offline,
forever.
"""

import os
import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path
from typing import Callable, Optional, Tuple

# What each pack needs, and roughly what it costs.
PACKS = {
    "vision": {
        "title": "AI vision engine",
        "blurb": "Background removal, face blur, object removal and photo OCR need "
                 "an extra engine (about 150 MB).",
        "packages": ["onnxruntime", "numpy", "opencv-python-headless"],
        "size": "about 150 MB",
    },
    "media": {
        "title": "Media engine",
        "blurb": "Video and audio conversion needs an extra engine (about 80 MB).",
        "packages": ["imageio-ffmpeg"],
        "size": "about 80 MB",
    },
}

_state = {"vision": False, "media": False}


def engines_dir() -> Path:
    """The folder where engine packs are installed."""
    from opal_studio.platform_compat import user_data_dir
    target = user_data_dir() / "engines"
    target.mkdir(parents=True, exist_ok=True)
    return target


def _pip_available() -> bool:
    try:
        import pip  # noqa: F401
        return True
    except Exception:
        # A frozen build can still run pip if it was bundled.
        return "pip" in sys.modules or (Path(sys.executable).parent / "pip").exists()


def _run_pip(target: Path, packages, progress: Optional[Callable[[str], None]] = None) -> bool:
    """Installs packages into a target folder using pip, quietly."""
    target.mkdir(parents=True, exist_ok=True)
    args = [sys.executable, "-m", "pip", "install", "--no-warn-script-location",
            "--disable-pip-version-check", "--target", str(target)]
    args += list(packages)
    if progress:
        progress(f"Downloading {', '.join(packages)} ...")
    try:
        creationflags = 0
        if sys.platform.startswith("win"):
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        proc = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              text=True, creationflags=creationflags)
        if proc.returncode != 0:
            if progress:
                progress(f"Engine install failed:\n{(proc.stdout or '')[-300:]}")
            return False
        return True
    except Exception as e:
        if progress:
            progress(f"Engine install failed: {e}")
        return False


def _add_to_path(target: Path) -> None:
    path = str(target)
    if path not in sys.path:
        sys.path.insert(0, path)
    import importlib
    importlib.invalidate_caches()


# ---------------------------------------------------------------------------
# Vision engine (background removal, face blur, OCR)
# ---------------------------------------------------------------------------

def vision_available() -> bool:
    """True when the AI vision libraries can be imported right now."""
    if _state["vision"]:
        return True
    try:
        import cv2  # noqa: F401
        import onnxruntime  # noqa: F401
        _state["vision"] = True
        return True
    except Exception:
        pass
    local = engines_dir()
    if (local / "cv2").exists() or (local / "onnxruntime").exists():
        _add_to_path(local)
        try:
            import cv2  # noqa: F401
            import onnxruntime  # noqa: F401
            _state["vision"] = True
            return True
        except Exception:
            return False
    return False


def install_vision_engine(progress: Optional[Callable[[str], None]] = None) -> bool:
    """Downloads and installs the AI vision engine. Returns True on success."""
    if vision_available():
        return True
    if not _pip_available():
        if progress:
            progress("This build cannot install engines automatically. "
                     "Reinstall the full version of Opal to use AI tools.")
        return False
    target = engines_dir()
    if not _run_pip(target, PACKS["vision"]["packages"], progress):
        return False
    _add_to_path(target)
    ok = vision_available()
    if progress:
        progress("AI engine ready." if ok else "The engine installed but could not be loaded.")
    return ok


# ---------------------------------------------------------------------------
# Media engine (video and audio)
# ---------------------------------------------------------------------------

def media_available() -> bool:
    """True when an FFmpeg binary is available."""
    from opal_studio.engines import EngineManager
    return EngineManager.ffmpeg_bin() is not None


def install_media_engine(progress: Optional[Callable[[str], None]] = None) -> bool:
    """Downloads and installs the media engine. Returns True on success."""
    if media_available():
        return True
    if not _pip_available():
        if progress:
            progress("This build cannot install engines automatically.")
        return False
    target = engines_dir()
    if not _run_pip(target, PACKS["media"]["packages"], progress):
        return False
    _add_to_path(target)
    try:
        import imageio_ffmpeg
        binary = Path(imageio_ffmpeg.get_ffmpeg_exe())
        name = "ffmpeg.exe" if sys.platform.startswith("win") else "ffmpeg"
        shutil.copy2(binary, target / name)
        (target / name).chmod(0o755)
    except Exception as e:
        if progress:
            progress(f"Media engine installed but the binary is missing: {e}")
        return False
    from opal_studio.engines import EngineManager
    found = EngineManager.ffmpeg_bin()
    if progress:
        progress("Media engine ready." if found else "Media engine installed.")
    return found is not None


def engine_status() -> dict:
    """Which engines are ready right now."""
    return {
        "vision": vision_available(),
        "media": media_available(),
    }


def describe_missing() -> str:
    """A human sentence about what is missing, for the UI."""
    missing = []
    if not vision_available():
        missing.append(f"AI vision engine ({PACKS['vision']['size']})")
    if not media_available():
        missing.append(f"media engine ({PACKS['media']['size']})")
    if not missing:
        return "Every engine is ready."
    return "Still needed: " + " and ".join(missing) + "."
