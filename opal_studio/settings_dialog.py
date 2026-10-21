"""
Opal - Settings and Preferences Dialog
Plain English: This window lets users configure auto-startup, default output folders,
and Windows right-click menu integration.
"""

from pathlib import Path
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox,
    QRadioButton, QButtonGroup, QLineEdit, QPushButton,
    QFileDialog, QGroupBox, QMessageBox, QComboBox, QFormLayout
)

from opal_studio.config import ConfigManager
from opal_studio.context_menu import install_context_menu, uninstall_context_menu


class SettingsDialog(QDialog):
    settings_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Opal Preferences")
        self.setFixedSize(480, 520)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self._apply_light_theme()
        self._setup_ui()
        self._load_values()

    def _apply_light_theme(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #101625;
                color: #EDF1FA;
                font-family: 'Segoe UI';
            }
            QLabel {
                color: #A8B2C8;
                font-size: 13px;
            }
            QGroupBox {
                border: 1px solid rgba(255,255,255,0.10);
                border-radius: 12px;
                margin-top: 14px;
                padding-top: 18px;
                font-weight: bold;
                color: #A79FFF;
                font-size: 13px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 6px;
            }
            QCheckBox, QRadioButton {
                color: #EDF1FA;
                font-size: 13px;
                spacing: 8px;
            }
            QCheckBox::indicator, QRadioButton::indicator {
                width: 16px;
                height: 16px;
            }
            QLineEdit {
                background-color: rgba(255,255,255,0.05);
                border: 1px solid rgba(255,255,255,0.16);
                border-radius: 10px;
                padding: 6px 10px;
                color: #EDF1FA;
                font-size: 12px;
            }
            QLineEdit:focus {
                border: 1px solid #6C63FF;
            }
            QPushButton {
                background-color: rgba(255,255,255,0.05);
                border: 1px solid rgba(255,255,255,0.16);
                border-radius: 10px;
                padding: 7px 16px;
                color: #EDF1FA;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: rgba(108,99,255,0.18);
                border: 1px solid #6C63FF;
                color: #C9C4FF;
            }
            QPushButton#primaryBtn {
                background-color: #6C63FF;
                border: none;
                color: #FFFFFF;
                font-weight: bold;
            }
            QPushButton#primaryBtn:hover {
                background-color: #8A83FF;
            }
        """)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # Header
        title_label = QLabel("Opal Preferences")
        title_label.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title_label.setStyleSheet("color: #8A83FF;")
        layout.addWidget(title_label)

        # 1. Behavior Group
        grp_behavior = QGroupBox("Behavior & Detection")
        vbox_behavior = QVBoxLayout(grp_behavior)
        vbox_behavior.setSpacing(10)

        self.chk_startup = QCheckBox("Start Opal automatically with Windows")
        vbox_behavior.addWidget(self.chk_startup)

        self.chk_global_drag = QCheckBox("Zero-click drag detection (Tap Shift/Alt/Ctrl while dragging)")
        vbox_behavior.addWidget(self.chk_global_drag)

        self.chk_show_orb = QCheckBox("Show floating desktop Drop Target")
        vbox_behavior.addWidget(self.chk_show_orb)

        self.chk_open_in_studio = QCheckBox("Open files straight into the Floating Studio")
        vbox_behavior.addWidget(self.chk_open_in_studio)

        self.chk_keep_dates = QCheckBox("Keep the original file dates on converted copies")
        vbox_behavior.addWidget(self.chk_keep_dates)

        layout.addWidget(grp_behavior)

        # 1b. AI Engine Group
        grp_ai = QGroupBox("AI Engines")
        ai_layout = QFormLayout(grp_ai)

        self.cmb_bg_model = QComboBox()
        from opal_studio.engines import CUTOUT_MODELS, EngineManager
        for mid, (label, _size) in CUTOUT_MODELS.items():
            mark = "✓" if EngineManager.cutout_cached(mid) else "☁"
            self.cmb_bg_model.addItem(f"{label} {mark}", mid)
        ai_layout.addRow("Background removal model", self.cmb_bg_model)

        self.chk_soft_edges = QCheckBox("Soften the edges of cut-outs")
        ai_layout.addRow("", self.chk_soft_edges)

        self.cmb_upscale_model = QComboBox()
        from opal_studio.engines import ESRGAN_MODELS
        for mid, meta in ESRGAN_MODELS.items():
            label, _size = meta[0], meta[1]
            mark = "✓" if EngineManager.esrgan_cached(mid) else "☁"
            self.cmb_upscale_model.addItem(f"{label} {mark}", mid)
        ai_layout.addRow("Upscaling model", self.cmb_upscale_model)

        ai_hint = QLabel("Models download once, then work offline. The first use may take a minute.")
        ai_hint.setStyleSheet("color: #727E96; font-size: 10px;")
        ai_layout.addRow("", ai_hint)
        layout.addWidget(grp_ai)

        # 2. Destination Folder Group
        grp_output = QGroupBox("Saved File Destination")
        vbox_output = QVBoxLayout(grp_output)
        vbox_output.setSpacing(8)

        self.rad_source = QRadioButton("Save in the same folder as the original file")
        self.rad_downloads = QRadioButton("Save to Windows Downloads folder")
        self.rad_custom = QRadioButton("Save to a specific custom folder:")

        self.output_group = QButtonGroup(self)
        self.output_group.addButton(self.rad_source)
        self.output_group.addButton(self.rad_downloads)
        self.output_group.addButton(self.rad_custom)

        vbox_output.addWidget(self.rad_source)
        vbox_output.addWidget(self.rad_downloads)
        vbox_output.addWidget(self.rad_custom)

        custom_row = QHBoxLayout()
        self.txt_custom_dir = QLineEdit()
        self.txt_custom_dir.setPlaceholderText("Select destination folder...")
        self.btn_browse = QPushButton("Browse...")
        self.btn_browse.clicked.connect(self._browse_custom_dir)
        custom_row.addWidget(self.txt_custom_dir)
        custom_row.addWidget(self.btn_browse)
        vbox_output.addLayout(custom_row)

        self.rad_custom.toggled.connect(self._toggle_custom_state)

        layout.addWidget(grp_output)

        # 3. Windows Shell Integration Group
        grp_shell = QGroupBox("Windows Explorer Integration")
        vbox_shell = QVBoxLayout(grp_shell)
        shell_row = QHBoxLayout()

        self.btn_install_shell = QPushButton("Add Right-Click Menu")
        self.btn_install_shell.clicked.connect(self._install_shell)
        self.btn_remove_shell = QPushButton("Remove Right-Click Menu")
        self.btn_remove_shell.clicked.connect(self._remove_shell)

        shell_row.addWidget(self.btn_install_shell)
        shell_row.addWidget(self.btn_remove_shell)
        vbox_shell.addLayout(shell_row)
        layout.addWidget(grp_shell)

        # Bottom Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_save = QPushButton("Save Preferences")
        self.btn_save.setObjectName("primaryBtn")
        self.btn_save.clicked.connect(self._save_values)
        btn_layout.addWidget(self.btn_save)

        layout.addLayout(btn_layout)

    def _toggle_custom_state(self, checked: bool):
        self.txt_custom_dir.setEnabled(checked)
        self.btn_browse.setEnabled(checked)

    def _browse_custom_dir(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose Output Directory")
        if folder:
            self.txt_custom_dir.setText(folder)

    def _install_shell(self):
        if install_context_menu():
            QMessageBox.information(self, "Opal", "'Convert with Opal' added to right-click menu.")
        else:
            QMessageBox.warning(self, "Opal", "Could not register right-click menu.")

    def _remove_shell(self):
        if uninstall_context_menu():
            QMessageBox.information(self, "Opal", "Removed from right-click menu.")
        else:
            QMessageBox.warning(self, "Opal", "Could not remove right-click menu.")

    def _load_values(self):
        cfg = ConfigManager.load_config()
        self.chk_startup.setChecked(cfg.get("launch_at_startup", True))
        self.chk_global_drag.setChecked(cfg.get("global_drag_enabled", True))
        self.chk_show_orb.setChecked(cfg.get("show_drop_dock", True))
        self.chk_open_in_studio.setChecked(cfg.get("open_in_studio", False))
        self.chk_keep_dates.setChecked(cfg.get("keep_original_dates", True))
        self.chk_soft_edges.setChecked(cfg.get("bg_soft_edges", False))

        bg_model = cfg.get("bg_model", "u2netp")
        idx = self.cmb_bg_model.findData(bg_model)
        if idx >= 0:
            self.cmb_bg_model.setCurrentIndex(idx)
        up_model = cfg.get("upscale_model", "realesrgan-x4plus")
        idx = self.cmb_upscale_model.findData(up_model)
        if idx >= 0:
            self.cmb_upscale_model.setCurrentIndex(idx)

        mode = cfg.get("output_mode", "same_as_source")
        if mode == "downloads":
            self.rad_downloads.setChecked(True)
        elif mode == "custom":
            self.rad_custom.setChecked(True)
        else:
            self.rad_source.setChecked(True)

        self.txt_custom_dir.setText(cfg.get("custom_output_dir", ""))
        self._toggle_custom_state(self.rad_custom.isChecked())

    def _save_values(self):
        mode = "same_as_source"
        if self.rad_downloads.isChecked():
            mode = "downloads"
        elif self.rad_custom.isChecked():
            mode = "custom"

        # Update the existing configuration instead of replacing it, so newer
        # settings (watch folder, AI models) are never lost.
        new_cfg = ConfigManager.load_config()
        new_cfg.update({
            "launch_at_startup": self.chk_startup.isChecked(),
            "global_drag_enabled": self.chk_global_drag.isChecked(),
            "show_drop_dock": self.chk_show_orb.isChecked(),
            "open_in_studio": self.chk_open_in_studio.isChecked(),
            "keep_original_dates": self.chk_keep_dates.isChecked(),
            "bg_model": self.cmb_bg_model.currentData(),
            "bg_soft_edges": self.chk_soft_edges.isChecked(),
            "upscale_model": self.cmb_upscale_model.currentData(),
            "output_mode": mode,
            "custom_output_dir": self.txt_custom_dir.text().strip(),
        })
        ConfigManager.save_config(new_cfg)
        self.settings_changed.emit()
        self.accept()
