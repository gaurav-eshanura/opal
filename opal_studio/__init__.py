"""
Opal - every file, in every light.
"""
from opal_studio.main import OpalApp
from opal_studio.engine import OpalEngine, ConversionResult, BatchConversionResult
from opal_studio.radial_widget import RadialMenuWidget
from opal_studio.drop_orb import DropOrbWidget
from opal_studio.toast import OpalToast
from opal_studio.tray import OpalTray
from opal_studio.config import ConfigManager
from opal_studio.drag_detector import GlobalDragDetector
from opal_studio.settings_dialog import SettingsDialog
from opal_studio.history_dialog import HistoryDialog
from opal_studio.float_viewer import FloatStudio
from opal_studio.engines import EngineManager
from opal_studio import pdf_tools

__all__ = [
    "OpalApp",
    "OpalEngine",
    "ConversionResult",
    "BatchConversionResult",
    "RadialMenuWidget",
    "DropOrbWidget",
    "OpalToast",
    "OpalTray",
    "ConfigManager",
    "GlobalDragDetector",
    "SettingsDialog",
    "HistoryDialog",
    "FloatStudio",
    "EngineManager",
    "pdf_tools",
]
