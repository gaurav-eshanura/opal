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
import zipfile
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(ROOT))

from opal_studio.version import __version__  # noqa: E402

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
    # The same Qt modules on Linux and macOS, where they are shared objects
    # (macOS also ships them inside frameworks).
    "PySide6/Qt6Quick*",
    "PySide6/Qt6Qml*",
    "PySide6/Qt6QuickWidgets*",
    "PySide6/Qt6Quick3D*",
    "PySide6/Qt/lib/QtQuick.framework",
    "PySide6/Qt/lib/QtQml.framework",
    "PySide6/Qt/lib/QtQuickWidgets.framework",
    "PySide6/Qt/lib/QtQuick3D.framework",
    "PySide6/Qt/translations",
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


def payload_roots(dist_dir: Path) -> list[Path]:
    """The folders inside a built app that hold the payload files.

    Windows and Linux get a plain folder with an ``_internal`` directory;
    a macOS .app keeps the same files inside ``Contents/Frameworks``.
    """
    roots = []
    internal = dist_dir / "_internal"
    if internal.is_dir():
        roots.append(internal)
    frameworks = dist_dir / "Contents" / "Frameworks"
    if frameworks.is_dir():
        roots.append(frameworks)
    resources = dist_dir / "Contents" / "Resources"
    if resources.is_dir():
        roots.append(resources)
    return roots


def prune(dist_dir: Path) -> int:
    """Removes unused payload from the built app and reports the saving."""
    freed = 0
    for internal in payload_roots(dist_dir):
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


def find_dist_dir(dist_name: str) -> Path:
    """Where the build put the app.

    Windows and Linux get a folder, macOS gets a ``.app`` bundle - and the
    bundle is the one people should download.
    """
    folder = ROOT / "dist" / dist_name
    if folder.exists():
        return folder
    bundle = ROOT / "dist" / f"{dist_name}.app"
    if bundle.exists():
        return bundle
    return folder


def make_release_zip(dist_dir: Path, dist_name: str) -> Path | None:
    """Zip the built app into the archive people download, and stage it for
    the website so the download button has a real file behind it."""
    if not dist_dir.exists():
        return None
    platform = {"Windows": "Windows-x64", "Darwin": "macOS-x64", "Linux": "Linux-x64"}
    tag = platform.get(sys.platform, "Windows-x64")
    zip_path = ROOT / "dist" / f"{dist_name}-v{__version__}-{tag}.zip"
    print(f"Packing {zip_path.name} ...")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for item in sorted(dist_dir.rglob("*")):
            if item.is_file():
                zf.write(item, item.relative_to(dist_dir.parent))
    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"  {zip_path.name}  {size_mb:.0f} MB")

    downloads = ROOT / "website" / "downloads"
    downloads.mkdir(parents=True, exist_ok=True)
    staged = downloads / zip_path.name
    shutil.copy2(zip_path, staged)
    print(f"  staged for the website -> {staged.relative_to(ROOT)}")
    return zip_path

def build_executable() -> int:
    core = "--core" in sys.argv
    print("=== BUILDING PORTABLE OPAL ===")
    print("Variant:", "core (engines on demand)" if core else "full (everything included)")
    spec = ROOT / "Opal.spec"
    dist_name = "Opal" if core else "Opal-Full"

    # FFmpeg travels with the app so the video and audio tools work out of the box.
    # The binary is named for the platform: "ffmpeg.exe" on Windows, plain
    # "ffmpeg" on macOS and Linux - which is also the name the app looks for.
    if sys.platform.startswith("win"):
        ffmpeg_name = "ffmpeg.exe"
    else:
        ffmpeg_name = "ffmpeg"
    ffmpeg_src = ROOT / "ffmpeg_backup" / ffmpeg_name
    ffmpeg_dst = ROOT / "assets" / "bin" / ffmpeg_name
    if not ffmpeg_src.exists():
        # Fall back to whatever ffmpeg is on this machine, so the full build
        # can be made on a fresh checkout.
        found = shutil.which("ffmpeg")
        if found:
            ffmpeg_src = Path(found)
    if ffmpeg_src.exists():
        ffmpeg_dst.parent.mkdir(parents=True, exist_ok=True)
        if not ffmpeg_dst.exists() or ffmpeg_src.stat().st_mtime > ffmpeg_dst.stat().st_mtime:
            shutil.copy2(ffmpeg_src, ffmpeg_dst)
            os.chmod(ffmpeg_dst, 0o755)
            print(f"Bundled FFmpeg -> {ffmpeg_dst}")
    elif not core:
        print("  (no FFmpeg found - the full build will not carry one)")

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
        dist_dir = find_dist_dir(dist_name)
        if dist_dir.exists():
            freed = prune(dist_dir)
            if freed:
                print(f"Trimmed {freed / 1024 / 1024:.0f} MB of unused libraries")
            # FFmpeg has to sit next to the executable, because that is the
            # first place the app looks for it.
            exe_dir = (dist_dir / "Contents" / "MacOS") if dist_dir.suffix == ".app" else dist_dir
            for root in payload_roots(dist_dir):
                for name in ("ffmpeg.exe", "ffmpeg"):
                    candidate = root / name
                    if candidate.exists():
                        shutil.copy2(candidate, exe_dir / name)
                        print(f"FFmpeg -> {exe_dir / name}")
                        break
                else:
                    continue
                break
        make_release_zip(dist_dir, dist_name)
        print("\n==================================================")
        print("BUILD SUCCESSFUL!")
        print(f"Portable app: {dist_dir}")
        print("==================================================")
        return 0
    print("\nBuild failed with exit code:", result.returncode)
    return result.returncode


if __name__ == "__main__":
    sys.exit(build_executable())
