"""
Opal - Production Executable Compiler
Plain English: Builds a self-contained, portable application that runs without
installation. The build definition lives in Opal.spec, and this script also
prunes the payload afterwards so the download stays small.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.resolve()

# Qt modules the app never touches - dropping them saves a lot of download.
EXCLUDED_MODULES = [
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
    "PySide6.QtQuick", "PySide6.QtQuick3D", "PySide6.QtQml", "PySide6.QtQuickWidgets",
    "PySide6.Qt3DCore", "PySide6.Qt3DRender", "PySide6.Qt3DInput",
    "PySide6.Qt3DAnimation", "PySide6.Qt3DExtras", "PySide6.QtCharts",
    "PySide6.QtDataVisualization", "PySide6.QtSql", "PySide6.QtTest",
    "PySide6.QtDesigner", "PySide6.QtHelp", "PySide6.QtUiTools",
    "PySide6.QtWebSockets", "PySide6.QtWebChannel", "PySide6.QtHttpServer",
    "PySide6.QtBluetooth", "PySide6.QtNfc", "PySide6.QtPositioning",
    "PySide6.QtSensors", "PySide6.QtSerialPort", "PySide6.QtSerialBus",
    "PySide6.QtSpatialAudio", "PySide6.QtTextToSpeech", "PySide6.QtVirtualKeyboard",
    "PySide6.QtScxml", "PySide6.QtStateMachine", "PySide6.QtGraphs",
    "PySide6.QtPdf", "PySide6.QtPdfWidgets", "PySide6.QtOpenGLWidgets",
    "tkinter", "IPython", "jupyter", "notebook", "pytest", "matplotlib", "pandas",
]

# Files and folders that are large but never used at runtime.
# Globs are supported.
PRUNE_FILES = [
    # --- GPU libraries: the AI models run on the CPU, so CUDA is dead weight (~760 MB) ---
    "cublas*.dll",
    "cufft*.dll",
    "cudart*.dll",
    "cudnn*.dll",
    "nvrtc*.dll",
    "nvjitlink*.dll",
    "nvidia",
    "cupy",
    "onnxruntime/capi/onnxruntime_providers_cuda.dll",
    "onnxruntime/capi/onnxruntime_providers_tensorrt.dll",
    # --- Qt payload we never touch ---
    "PySide6/opengl32sw.dll",          # software OpenGL fallback (20 MB)
    "PySide6/translations",             # 60 languages we do not speak (7 MB)
    "PySide6/Qt6Quick.dll",
    "PySide6/Qt6QuickWidgets.dll",
    "PySide6/Qt6Qml.dll",
    "PySide6/Qt6QmlMeta.dll",
    "PySide6/Qt6QmlModels.dll",
    "PySide6/Qt6QmlWorkerScript.dll",
    "PySide6/Qt6Pdf.dll",
    "PySide6/Qt6PdfWidgets.dll",
    "PySide6/Qt6WebEngine*.dll",
    "PySide6/Qt6Charts.dll",
    "PySide6/Qt63D*.dll",
    "PySide6/Qt6Sql.dll",
    "PySide6/Qt6Test.dll",
    "PySide6/Qt6Designer.dll",
    "PySide6/Qt6Help.dll",
    "PySide6/Qt6UiTools.dll",
    "PySide6/Qt6WebSockets.dll",
    "PySide6/Qt6WebChannel.dll",
    "PySide6/Qt6Bluetooth.dll",
    "PySide6/Qt6Nfc.dll",
    "PySide6/Qt6Positioning.dll",
    "PySide6/Qt6Sensors.dll",
    "PySide6/Qt6SerialPort.dll",
    "PySide6/Qt6SpatialAudio.dll",
    "PySide6/Qt6TextToSpeech.dll",
    "PySide6/Qt6VirtualKeyboard.dll",
    "PySide6/Qt6Scxml.dll",
    "PySide6/Qt6StateMachine.dll",
    "PySide6/Qt6Graphs.dll",
    "PySide6/plugins/sqldrivers",
    "PySide6/plugins/printsupport",
    "libx265*.dll",
    "imageio_ffmpeg",      # a second copy of ffmpeg we do not need
    # OpenCV's own bundled FFmpeg, for its video reader. We do our video
    # work through ffmpeg directly, so this 28 MB is never loaded.
    "cv2/opencv_videoio_ffmpeg*.dll",
    # --- OpenSSL copies picked up from whatever was on PATH ---
    # PyInstaller collects these from Git for Windows by mistake. Nothing in
    # the build imports them, and the real ones ship with Python.
    "libcrypto-3-x64.dll",
    "libssl-3-x64.dll",
    "torch",
    "torchvision",
    "torchaudio",
]


def prune(dist_dir: Path) -> int:
    """Removes unused payload from the built app and reports the saving."""
    internal = dist_dir / "_internal"
    if not internal.exists():
        return 0
    freed = 0
    for pattern in PRUNE_FILES:
        for target in internal.glob(pattern):
            try:
                if target.is_dir():
                    freed += sum(f.stat().st_size for f in target.rglob("*") if f.is_file())
                    shutil.rmtree(target, ignore_errors=True)
                else:
                    freed += target.stat().st_size
                    target.unlink()
            except OSError:
                pass
    return freed


def build_executable() -> int:
    core = "--core" in sys.argv
    print("=== BUILDING PORTABLE OPAL ===")
    print("Variant:", "core (engines on demand)" if core else "full (everything included)")
    spec = ROOT / "Opal.spec"
    dist_name = "Opal" if core else "Opal-Full"

    # FFmpeg travels with the app so the video and audio tools work out of the box.
    ffmpeg_src = ROOT / "ffmpeg_backup" / "ffmpeg.exe"
    ffmpeg_dst = ROOT / "assets" / "bin" / "ffmpeg.exe"
    if ffmpeg_src.exists():
        ffmpeg_dst.parent.mkdir(parents=True, exist_ok=True)
        if not ffmpeg_dst.exists() or ffmpeg_src.stat().st_mtime > ffmpeg_dst.stat().st_mtime:
            shutil.copy2(ffmpeg_src, ffmpeg_dst)
            print(f"Bundled FFmpeg -> {ffmpeg_dst}")

    env = dict(os.environ)
    if core:
        env["OPAL_CORE"] = "1"
    env["OPAL_DIST_NAME"] = dist_name
    build_args = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", str(spec)]
    print("Running PyInstaller with Opal.spec...")
    result = subprocess.run(build_args, cwd=str(ROOT), shell=False, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for line in (result.stdout or "").splitlines()[-10:]:
        print("  " + line)

    if result.returncode == 0:
        dist_dir = ROOT / "dist" / dist_name
        if dist_dir.exists():
            freed = prune(dist_dir)
            if freed:
                print(f"Trimmed {freed / 1024 / 1024:.0f} MB of unused libraries")
            ffmpeg_internal = dist_dir / "_internal" / "ffmpeg.exe"
            if ffmpeg_internal.exists():
                shutil.copy2(ffmpeg_internal, dist_dir / "ffmpeg.exe")
        print("\n==================================================")
        print("BUILD SUCCESSFUL!")
        print(f"Portable app: {dist_dir}")
        print("==================================================")
        return 0
    print("\nBuild failed with exit code:", result.returncode)
    return result.returncode


if __name__ == "__main__":
    sys.exit(build_executable())
