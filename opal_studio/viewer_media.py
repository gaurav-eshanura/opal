"""
Opal - Floating Media Studio
Plain English: Plays video and audio inside a floating, always-on-top window.
Shows a real waveform for audio, lets you grab a frame, trim a clip by
dragging on the waveform, change speed, and convert to other formats without
leaving the window. Everything is local.
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional, List

from PySide6.QtCore import Qt, QTimer, Signal, QUrl, QRectF, QPointF
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QBrush, QPixmap, QImage
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSlider,
                               QMessageBox, QFileDialog, QComboBox, QSpinBox, QApplication,
                               QSizePolicy, QCheckBox)

try:
    from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput, QMediaDevices
    from PySide6.QtMultimediaWidgets import QVideoWidget
    MULTIMEDIA = True
except Exception:
    MULTIMEDIA = False

CITRUS = QColor(255, 122, 24)


def _btn(text: str, tip: str = "") -> QPushButton:
    b = QPushButton(text)
    b.setToolTip(tip or text)
    b.setCursor(Qt.PointingHandCursor)
    b.setStyleSheet("""
        QPushButton { background: rgba(255,255,255,0.05); color: #EDF1FA; border: 1px solid rgba(255,255,255,0.16);
                      border-radius: 10px; padding: 5px 11px; font-size: 11px; font-weight: 600; }
        QPushButton:hover { background: #6C63FF; color: #FFFFFF; border-color: #8A83FF; }
        QPushButton:disabled { background: #101625; color: rgba(237,241,250,0.28); border-color: rgba(255,255,255,0.09); }
    """)
    return b


class WaveformView(QWidget):
    """Draws the decoded audio waveform and lets you seek or select a range."""

    range_selected = Signal(float, float)  # start fraction, end fraction

    def __init__(self, parent=None):
        super().__init__(parent)
        self.peaks: List[float] = []
        self.progress = 0.0
        self.selection: Optional[tuple] = None
        self.drag_start: Optional[float] = None
        self.setMinimumHeight(70)
        self.setMaximumHeight(130)
        self.setStyleSheet("background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.10); border-radius:14px;")

    def set_peaks(self, peaks: List[float]):
        self.peaks = peaks
        self.update()

    def set_progress(self, fraction: float):
        self.progress = max(0.0, min(1.0, fraction))
        self.update()

    def _fraction_from_x(self, x: int) -> float:
        return max(0.0, min(1.0, x / max(1, self.width())))

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        self.drag_start = self._fraction_from_x(int(event.position().x()))

    def mouseMoveEvent(self, event):
        if self.drag_start is None:
            return
        cur = self._fraction_from_x(int(event.position().x()))
        if abs(cur - self.drag_start) > 0.01:
            self.selection = (min(self.drag_start, cur), max(self.drag_start, cur))
            self.update()

    def mouseReleaseEvent(self, event):
        if self.drag_start is None:
            return
        cur = self._fraction_from_x(int(event.position().x()))
        if self.selection:
            self.range_selected.emit(self.selection[0], self.selection[1])
        elif abs(cur - self.drag_start) < 0.01:
            self.range_selected.emit(-1.0, cur)  # negative start means "seek"
        self.drag_start = None

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor(255, 255, 255))
        if not self.peaks:
            painter.setPen(QPen(QColor(138, 145, 137)))
            painter.setFont(QFont("Segoe UI", 9))
            painter.drawText(self.rect(), Qt.AlignCenter, "Waveform unavailable")
            return
        mid = self.height() / 2
        bar_w = 2
        gap = 1
        count = max(1, self.width() // (bar_w + gap))
        step = len(self.peaks) / count
        for i in range(count):
            start = int(i * step)
            end = max(start + 1, int((i + 1) * step))
            chunk = self.peaks[start:end]
            if not chunk:
                continue
            peak = max(chunk)
            h = max(2.0, peak * (self.height() * 0.45))
            x = i * (bar_w + gap)
            played = (i / count) <= self.progress
            color = CITRUS if played else QColor(196, 201, 194)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(color))
            painter.drawRoundedRect(QRectF(x, mid - h, bar_w, h * 2), 1, 1)
        if self.selection:
            x0 = self.selection[0] * self.width()
            x1 = self.selection[1] * self.width()
            painter.fillRect(QRectF(x0, 0, x1 - x0, self.height()), QColor(255, 122, 24, 50))
            painter.setPen(QPen(CITRUS, 1))
            painter.drawLine(QPointF(x0, 0), QPointF(x0, self.height()))
            painter.drawLine(QPointF(x1, 0), QPointF(x1, self.height()))


class MediaStudio(QWidget):
    """Floating video & audio workspace."""

    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        from opal_studio.theme import apply_field
        apply_field(self)
        self.file_path = str(Path(file_path).resolve())
        self.is_video = Path(self.file_path).suffix.lower() in (
            ".mp4", ".mov", ".mkv", ".webm", ".avi", ".wmv", ".flv", ".m4v")
        self.duration = 0.0
        self._build_ui()
        if MULTIMEDIA:
            self._setup_player()
        self._load_metadata()
        self._load_waveform()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(4)

        header = QHBoxLayout()
        self.title_label = QLabel(Path(self.file_path).name)
        self.title_label.setStyleSheet("color:#fff; font-size:12px; font-weight:700;")
        self.meta_label = QLabel("")
        self.meta_label.setStyleSheet("color:#727E96; font-size:10px;")
        header.addWidget(self.title_label)
        header.addWidget(self.meta_label)
        header.addStretch()
        for text, tip, slot in [
            ("📷 Frame", "Save the current frame as PNG", self._snapshot),
            ("🎬 → MP4", "Convert to MP4", lambda: self._convert("mp4")),
            ("🎞️ → GIF", "Convert to GIF", lambda: self._convert("gif")),
            ("🎵 → MP3", "Extract the audio", lambda: self._convert("mp3")),
            ("✂️ Trim", "Trim using the waveform selection", self._trim_selection),
        ]:
            b = _btn(text, tip)
            b.clicked.connect(slot)
            header.addWidget(b)
        root.addLayout(header)

        self.video_area = QWidget()
        video_lay = QVBoxLayout(self.video_area)
        video_lay.setContentsMargins(0, 0, 0, 0)
        if MULTIMEDIA and self.is_video:
            self.video_widget = QVideoWidget()
            self.video_widget.setStyleSheet("background:#1A1A1A; border-radius:12px;")
            video_lay.addWidget(self.video_widget, 1)
        else:
            art = QLabel("🎧")
            art.setAlignment(Qt.AlignCenter)
            art.setStyleSheet("font-size:64px; color:#8A83FF;")
            video_lay.addWidget(art, 1)
        root.addWidget(self.video_area, 1)

        self.waveform = WaveformView()
        root.addWidget(self.waveform)

        controls = QHBoxLayout()
        self.play_btn = _btn("▶", "Play / pause")
        self.play_btn.clicked.connect(self._toggle_play)
        controls.addWidget(self.play_btn)
        self.position_lbl = QLabel("0:00")
        self.position_lbl.setStyleSheet("color:#A8B2C8; font-size:10px;")
        controls.addWidget(self.position_lbl)
        self.seek_slider = QSlider(Qt.Horizontal)
        self.seek_slider.setStyleSheet("QSlider::groove:horizontal { background:rgba(255,255,255,0.05); height:4px; "
                                       "border-radius:2px; } QSlider::handle:horizontal { "
                                       "background:#6C63FF; width:12px; margin:-5px 0; border-radius:6px; }")
        self.seek_slider.sliderMoved.connect(self._seek)
        self.seek_slider.sliderReleased.connect(self._seek_release)
        controls.addWidget(self.seek_slider, 1)
        self.duration_lbl = QLabel("0:00")
        self.duration_lbl.setStyleSheet("color:#A8B2C8; font-size:10px;")
        controls.addWidget(self.duration_lbl)
        controls.addWidget(QLabel("🔊"))
        self.volume = QSlider(Qt.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setValue(70)
        self.volume.setFixedWidth(90)
        controls.addWidget(self.volume)
        self.speed = QComboBox()
        for s in ("0.5x", "0.75x", "1x", "1.25x", "1.5x", "2x"):
            self.speed.addItem(s)
        self.speed.setCurrentText("1x")
        self.speed.setToolTip("Playback speed")
        self.speed.currentTextChanged.connect(self._set_speed)
        controls.addWidget(self.speed)
        root.addLayout(controls)

    def _setup_player(self):
        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(self.volume.value() / 100.0)
        self.volume.valueChanged.connect(
            lambda v: self.audio_output.setVolume(v / 100.0))
        if self.is_video:
            self.player.setVideoOutput(self.video_widget)
        self.player.durationChanged.connect(self._on_duration)
        self.player.positionChanged.connect(self._on_position)
        self.player.playbackStateChanged.connect(self._on_state)
        self.player.setSource(QUrl.fromLocalFile(self.file_path))

    # ------------------------------------------------------------------
    # Metadata & waveform
    # ------------------------------------------------------------------

    def _load_metadata(self):
        try:
            from opal_studio.engines import EngineManager
            self.duration = EngineManager.media_duration(Path(self.file_path))
        except Exception:
            self.duration = 0.0
        info = [f"{_fmt_time(self.duration)}"]
        try:
            from opal_studio.engines import EngineManager
            ffprobe = EngineManager.ffprobe_bin()
            if ffprobe:
                out = subprocess.run(
                    [ffprobe, "-v", "error", "-show_entries",
                     "stream=codec_name,width,height,r_frame_rate",
                     "-of", "default=noprint_wrappers=1", str(self.file_path)],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                    timeout=15).stdout
                for line in out.splitlines():
                    if "codec_name" in line:
                        info.append(line.split("=")[-1])
                    elif "width" in line:
                        info.append(f"{line.split('=')[-1]}px")
        except Exception:
            pass
        self.meta_label.setText(" | ".join(info))
        self.duration_lbl.setText(_fmt_time(self.duration))

    def _load_waveform(self):
        """Decodes a low-rate mono copy to draw real peaks."""
        try:
            from opal_studio.engines import EngineManager
            ff = EngineManager.ffmpeg_bin()
            if not ff:
                return
            cmd = [ff, "-v", "error", "-i", str(self.file_path), "-ac", "1", "-ar", "8000",
                   "-f", "s16le", "-"]
            raw = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                                 timeout=180).stdout
            if not raw:
                return
            import array
            samples = array.array("h")
            samples.frombytes(raw[:len(raw) - (len(raw) % 2)])
            if not samples:
                return
            target = 900
            chunk = max(1, len(samples) // target)
            peaks = []
            for i in range(0, len(samples), chunk):
                piece = samples[i:i + chunk]
                if piece:
                    peaks.append(max(abs(min(piece)), abs(max(piece))) / 32768.0)
            self.waveform.set_peaks(peaks)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Playback
    # ------------------------------------------------------------------

    def _toggle_play(self):
        if not MULTIMEDIA:
            return
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def _on_state(self, state):
        self.play_btn.setText("❚❚" if state == QMediaPlayer.PlayingState else "▶")

    def _on_duration(self, ms):
        if ms > 0:
            self.duration = ms / 1000.0
            self.seek_slider.setRange(0, int(ms))
            self.duration_lbl.setText(_fmt_time(self.duration))

    def _on_position(self, ms):
        if not self.seek_slider.isSliderDown():
            self.seek_slider.setValue(int(ms))
        self.position_lbl.setText(_fmt_time(ms / 1000.0))
        if self.duration > 0:
            self.waveform.set_progress(ms / 1000.0 / self.duration)

    def _seek(self, value):
        self.position_lbl.setText(_fmt_time(value / 1000.0))

    def _seek_release(self):
        if MULTIMEDIA:
            self.player.setPosition(self.seek_slider.value())

    def _set_speed(self, text: str):
        if MULTIMEDIA:
            self.player.setPlaybackRate(float(text.rstrip("x")))

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _snapshot(self):
        if not MULTIMEDIA or not self.is_video:
            QMessageBox.information(self, "Snapshot", "Frames can only be grabbed from video.")
            return
        try:
            from opal_studio.engines import EngineManager
            ff = EngineManager.ffmpeg_bin()
            if not ff:
                return
            time_pos = self.player.position() / 1000.0
            out = Path(self.file_path).with_name(f"{Path(self.file_path).stem}_frame.png")
            subprocess.run([ff, "-y", "-ss", f"{time_pos:.2f}", "-i", str(self.file_path),
                            "-frames:v", "1", str(out)],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                           timeout=60)
            if out.exists():
                QMessageBox.information(self, "Frame Saved", f"Saved:\n{out}")
        except Exception as e:
            QMessageBox.warning(self, "Snapshot Failed", str(e))

    def _convert(self, target: str):
        from opal_studio.engine import OpalEngine
        res = OpalEngine.execute_single(self.file_path, target)
        if res.success:
            QMessageBox.information(self, "Converted", f"Saved to:\n{res.output_path}")
        else:
            QMessageBox.warning(self, "Conversion Failed", res.message)

    def _trim_selection(self):
        selection = getattr(self, "_last_selection", None)
        if not selection or selection[0] < 0:
            QMessageBox.information(self, "Trim", "Drag across the waveform to pick a range first.")
            return
        from opal_studio.engines import EngineManager
        ff = EngineManager.ffmpeg_bin()
        if not ff:
            return
        start = selection[0] * self.duration
        end = selection[1] * self.duration
        src = Path(self.file_path)
        out = src.with_name(f"{src.stem}_trim{src.suffix}")
        cmd = [ff, "-y", "-ss", f"{start:.2f}", "-to", f"{end:.2f}", "-i", str(src),
               "-c:v", "libx264", "-preset", "fast", "-c:a", "aac", str(out)]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
        if out.exists():
            QMessageBox.information(self, "Trimmed", f"Saved to:\n{out}")

    def _on_waveform_range(self, start: float, end: float):
        self._last_selection = (start, end)
        if start < 0:
            if MULTIMEDIA and self.duration > 0:
                self.player.setPosition(int(end * self.duration * 1000))
        else:
            self.status = f"Trim selection: {start:.2f}s - {end:.2f}s"

    def showEvent(self, event):
        super().showEvent(event)
        self.waveform.range_selected.connect(self._on_waveform_range)


def _fmt_time(seconds: float) -> str:
    seconds = max(0, int(seconds))
    return f"{seconds // 60}:{seconds % 60:02d}"
