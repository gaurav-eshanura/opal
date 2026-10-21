# -*- mode: python ; coding: utf-8 -*-
# Opal - portable build definition (Windows / macOS / Linux).
# Plain English: one file that tells PyInstaller exactly which modules, engines
# and data to bake into the portable app.

import os
import sys

IS_WINDOWS = sys.platform.startswith("win")
IS_MAC = sys.platform == "darwin"

# A "core" build ships only the essentials; the AI and media engines are then
# installed on demand the first time somebody actually uses those tools.
CORE_BUILD = os.environ.get("OPAL_CORE", "").strip().lower() in ("1", "true", "yes")
DIST_NAME = os.environ.get("OPAL_DIST_NAME", "Opal")

# FFmpeg travels with the app on every platform so video and audio work offline.
_binaries = []
if not CORE_BUILD:
    if IS_WINDOWS:
        _binaries.append(('assets\\bin\\ffmpeg.exe', '.'))
    elif IS_MAC:
        _binaries.append(('assets\\bin\\ffmpeg', '.'))

_entry = 'opal_studio\\main.py' if IS_WINDOWS else 'opal_studio/main.py'
_datas = [('opal_studio', 'opal_studio')]

# The full build carries the cut-out model with it, so "Remove Background"
# works on the very first click with no network at all. The core build stays
# small and fetches the model on demand instead.
if not CORE_BUILD:
    _bundled_model = os.path.join('assets', 'models', 'u2netp.onnx')
    if os.path.isfile(_bundled_model):
        _datas.append((_bundled_model, 'models'))

a = Analysis(
    [_entry],
    pathex=['.'],
    binaries=_binaries,
    datas=_datas,
    hiddenimports=[
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'PySide6.QtPrintSupport',
        'PySide6.QtMultimedia',
        'PySide6.QtMultimediaWidgets',
        'PySide6.QtSvg',
        'win32com.client',
        'pythoncom',
        'PIL',
        'pypdf',
        'fitz',
        'pymupdf',
        'docx',
        'openpyxl',
        'pptx',
        'ebooklib',
        'bs4',
        'lxml',
        'markdown',
        'fontTools.ttLib',
        'qrcode',
        'pillow_heif',
        'send2trash',
        'onnxruntime',
        'cryptography',
        'pyhanko',
        'pyhanko.sign',
        'pyhanko.sign.signers',
        'pyhanko.sign.fields',
        'pyhanko.pdf_utils.incremental_writer',
        'asn1crypto',
        'opal_studio.watch_folder',
        'opal_studio.float_viewer',
        'opal_studio.viewer_pdf',
        'opal_studio.viewer_image',
        'opal_studio.viewer_doc',
        'opal_studio.viewer_media',
        'opal_studio.engines',
        'opal_studio.pdf_tools',
        'opal_studio.dsc_sign',
        'opal_studio.cli',
        'opal_studio.theme',
        'opal_studio.icons',
        'opal_studio.engine',
        'opal_studio.dashboard',
        'opal_studio.radial_widget',
        'opal_studio.drop_orb',
        'opal_studio.hotkey',
        'opal_studio.drag_detector',
        'opal_studio.toast',
        'opal_studio.tray',
        'opal_studio.settings_dialog',
        'opal_studio.history_dialog',
        'opal_studio.platform_compat',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # --- Qt modules the app never touches (big download savings) ---
        'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets', 'PySide6.QtWebEngineQuick',
        'PySide6.QtQuick', 'PySide6.QtQuick3D', 'PySide6.QtQml', 'PySide6.QtQuickWidgets',
        'PySide6.Qt3DCore', 'PySide6.Qt3DRender', 'PySide6.Qt3DInput',
        'PySide6.Qt3DAnimation', 'PySide6.Qt3DExtras', 'PySide6.QtCharts',
        'PySide6.QtDataVisualization', 'PySide6.QtSql', 'PySide6.QtTest',
        'PySide6.QtDesigner', 'PySide6.QtHelp', 'PySide6.QtUiTools',
        'PySide6.QtWebSockets', 'PySide6.QtWebChannel', 'PySide6.QtHttpServer',
        'PySide6.QtBluetooth', 'PySide6.QtNfc', 'PySide6.QtPositioning',
        'PySide6.QtSensors', 'PySide6.QtSerialPort', 'PySide6.QtSerialBus',
        'PySide6.QtSpatialAudio', 'PySide6.QtTextToSpeech', 'PySide6.QtVirtualKeyboard',
        'PySide6.QtScxml', 'PySide6.QtStateMachine', 'PySide6.QtGraphs',
        'PySide6.QtPdf', 'PySide6.QtPdfWidgets', 'PySide6.QtOpenGLWidgets',
        # --- science stacks we never import ---
        'nltk',
        'sklearn',
        'scipy',
        'torch',
        'torchaudio',
        'torchvision',
        'transformers',
        'matplotlib',
        'pandas',
        'IPython',
        'jupyter',
        'notebook',
        'pytest',
        'tkinter',
        'static_ffmpeg',
        'rembg',
        'pymatting',
        'cupy',
    ] + (['cv2', 'onnxruntime', 'onnxruntime.capi', 'numpy', 'imageio_ffmpeg']
         if CORE_BUILD else []),
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=DIST_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=(['opal_studio\\app.ico'] if IS_WINDOWS else []),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=DIST_NAME,
)
