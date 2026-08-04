"""Floating overlay widgets for the Classic and Minimal Promptly designs."""

import math
import os
import sys

from PyQt6.QtCore import QRectF, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QCursor,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class EqualizerMeter(QWidget):
    """Mini equalizer: vertical bars that grow up AND down from a center line.

    Each bar extends symmetrically from the middle axis as you speak (like a
    classic VU meter), with per-bar smoothing so the bars ripple naturally.
    """

    BAR_COUNT = 5
    BAR_WIDTH = 5
    BAR_GAP = 3
    BAR_HEIGHT = 20
    CENTER_LINE = QColor(235, 240, 245, 60)

    # Silver metallic gradient: bright at the top, steel at the bottom
    _GRAD_TOP = QColor(245, 248, 250)
    _GRAD_BOTTOM = QColor(150, 158, 172)

    # Per-bar gain + smoothing rate → subtle wave effect
    _GAINS = (0.7, 0.9, 1.0, 0.9, 0.7)
    _RATES = (0.4, 0.6, 0.8, 0.6, 0.4)

    def __init__(self, parent=None):
        super().__init__(parent)
        width = (
            self.BAR_COUNT * self.BAR_WIDTH
            + (self.BAR_COUNT - 1) * self.BAR_GAP
        )
        self.setFixedSize(width, self.BAR_HEIGHT)
        self._bars = [0.0] * self.BAR_COUNT

    def set_level(self, level: float) -> None:
        level = max(0.0, min(1.0, level))
        changed = False
        for i in range(self.BAR_COUNT):
            target = min(1.0, max(0.05, level * self._GAINS[i]))
            smoothed = self._bars[i] + (target - self._bars[i]) * self._RATES[i]
            if abs(smoothed - self._bars[i]) > 0.001:
                changed = True
            self._bars[i] = smoothed
        if changed:
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)

        center = self.BAR_HEIGHT // 2
        radius = self.BAR_WIDTH / 2

        # Subtle center axis line
        painter.setBrush(self.CENTER_LINE)
        painter.drawRect(0, center - 1, self.width(), 2)

        # Bars grow from the middle, up and down at the same time
        for i, bar in enumerate(self._bars):
            x = i * (self.BAR_WIDTH + self.BAR_GAP)
            half = max(1, round(center * bar))
            gradient = QLinearGradient(0, center - half, 0, center + half)
            gradient.setColorAt(0.0, self._GRAD_TOP)
            gradient.setColorAt(1.0, self._GRAD_BOTTOM)
            painter.setBrush(QBrush(gradient))
            painter.drawRoundedRect(
                x, center - half, self.BAR_WIDTH, half * 2, radius, radius
            )

        painter.end()


class Overlay(QWidget):
    """Voice input overlay — Xbox Game Bar inspired design.

    Dark, semi-transparent, minimal, compact.
    Positioned at top-center, always on top.
    Features a subtle light border at the bottom.

    States:
        - Ready:        subtle dark bar with record button
        - Recording:    subtle red accent
        - Transcribing: subtle blue accent
        - Done:         subtle green accent
        - Error:        subtle red accent
    """

    toggle_requested = pyqtSignal()
    close_requested = pyqtSignal()

    READY = "ready"
    RECORDING = "recording"
    TRANSCRIBING = "transcribing"
    DONE = "done"
    ERROR = "error"

    # ── Color Palette (Game Bar inspired) ─────────────────────────────────────

    # Background — dark charcoal, semi-transparent
    BG_READY = "rgba(35, 35, 40, 0.92)"
    BG_RECORDING = "rgba(45, 25, 25, 0.94)"
    BG_TRANSCRIBING = "rgba(30, 35, 50, 0.94)"
    BG_DONE = "rgba(25, 45, 30, 0.94)"
    BG_ERROR = "rgba(45, 25, 25, 0.94)"

    # Borders — subtle, barely visible
    BORDER_READY = "rgba(255, 255, 255, 0.06)"
    BORDER_RECORDING = "rgba(239, 100, 100, 0.15)"
    BORDER_TRANSCRIBING = "rgba(100, 150, 239, 0.15)"
    BORDER_DONE = "rgba(100, 200, 100, 0.15)"
    BORDER_ERROR = "rgba(239, 100, 100, 0.2)"

    # Bottom accent line — white/light
    BOTTOM_LINE_READY = "rgba(255, 255, 255, 0.25)"
    BOTTOM_LINE_RECORDING = "rgba(239, 100, 100, 0.5)"
    BOTTOM_LINE_TRANSCRIBING = "rgba(100, 150, 239, 0.5)"
    BOTTOM_LINE_DONE = "rgba(100, 200, 100, 0.5)"
    BOTTOM_LINE_ERROR = "rgba(239, 100, 100, 0.5)"

    # Button styles — rounded, subtle, minimal
    _BTN_READY = """
        QPushButton {
            background: rgba(255, 255, 255, 0.1);
            color: rgba(255, 255, 255, 0.9);
            border: 1px solid rgba(255, 255, 255, 0.15);
            border-radius: 10px;
            font-size: 11px;
            font-weight: 500;
            padding: 4px 12px;
            min-width: 56px;
        }
        QPushButton:hover {
            background: rgba(255, 255, 255, 0.18);
            border: 1px solid rgba(255, 255, 255, 0.25);
        }
        QPushButton:pressed {
            background: rgba(255, 255, 255, 0.08);
        }
    """

    _BTN_RECORDING = """
        QPushButton {
            background: rgba(239, 100, 100, 0.25);
            color: rgba(255, 255, 255, 0.95);
            border: 1px solid rgba(239, 100, 100, 0.4);
            border-radius: 10px;
            font-size: 11px;
            font-weight: 500;
            padding: 4px 12px;
            min-width: 56px;
        }
        QPushButton:hover {
            background: rgba(239, 100, 100, 0.35);
        }
        QPushButton:pressed {
            background: rgba(239, 100, 100, 0.2);
        }
    """

    _BTN_DISABLED = """
        QPushButton {
            background: rgba(255, 255, 255, 0.05);
            color: rgba(255, 255, 255, 0.4);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 10px;
            font-size: 11px;
            font-weight: 500;
            padding: 4px 12px;
            min-width: 56px;
        }
    """

    def __init__(self):
        super().__init__()
        self.setObjectName("overlayWidget")

        # Window: frameless, always on top, no taskbar
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        # Compact size — Game Bar style
        self.setFixedSize(340, 44)

        # Drag state
        self._drag_start = None

        # Current hotkey shown in the hint (set by the app at startup)
        self._hotkey_text = "Ctrl+Alt+V"
        self._visual_state = self.READY
        self._success_text = "Pasted"
        self._error_message = ""

        # ── Main Vertical Layout ─────────────────────────────────────────────
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── Content Layout (horizontal) ──────────────────────────────────────
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(12, 6, 12, 6)
        content_layout.setSpacing(5)

        # Status icon (small, minimal)
        self.icon_label = QLabel("🎤")
        self.icon_label.setFixedSize(20, 20)
        self.icon_label.setStyleSheet(
            "font-size: 14px; background: transparent; color: rgba(255,255,255,0.7);"
        )
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Status text (clean, minimal)
        self.text_label = QLabel("Promptly")
        self.text_label.setStyleSheet(
            "color: rgba(255, 255, 255, 0.85);"
            "font-size: 12px;"
            "font-weight: 500;"
            "background: transparent;"
        )

        # Separator (subtle vertical line)
        self.separator = QLabel("│")
        self.separator.setStyleSheet(
            "color: rgba(255, 255, 255, 0.15); font-size: 14px; background: transparent;"
        )

        # Shortcut hint
        self.hint_label = QLabel("Ctrl+Alt+V")
        self.hint_label.setStyleSheet(
            "color: rgba(255, 255, 255, 0.4);"
            "font-size: 11px;"
            "font-weight: 400;"
            "background: transparent;"
        )
        self.hint_label.setFixedWidth(112)

        # Recording timer (visible only while recording)
        self.timer_label = QLabel("0:00")
        self.timer_label.setStyleSheet(
            "color: rgba(255, 255, 255, 0.85);"
            "font-size: 11px;"
            "font-weight: 600;"
            "font-family: Consolas, monospace;"
            "background: transparent;"
        )
        self.timer_label.hide()

        # Live volume meter (visible only while recording)
        self.meter = EqualizerMeter()
        self.meter.hide()

        # Action button (Start/Stop)
        self.action_button = QPushButton("⏵")
        self.action_button.setFixedSize(52, 28)
        self.action_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.action_button.clicked.connect(self._on_button_click)

        # Close button (×)
        self.close_button = QPushButton("×")
        self.close_button.setFixedSize(24, 24)
        self.close_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.close_button.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: rgba(255, 255, 255, 0.4);
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(255, 80, 80, 0.3);
                color: rgba(255, 255, 255, 0.8);
            }
        """)
        self.close_button.clicked.connect(self._on_close_click)

        # Spacer to push button to right
        content_layout.addWidget(self.icon_label)
        content_layout.addWidget(self.text_label)
        content_layout.addWidget(self.timer_label)
        content_layout.addWidget(self.meter)
        content_layout.addWidget(self.separator)
        content_layout.addWidget(self.hint_label)
        content_layout.addStretch()
        content_layout.addWidget(self.action_button)
        content_layout.addWidget(self.close_button)

        # ── Bottom Accent Line ───────────────────────────────────────────────
        self.bottom_line = QLabel()
        self.bottom_line.setFixedHeight(2)
        self.bottom_line.setStyleSheet(
            f"background: {self.BOTTOM_LINE_READY}; border: none;"
        )

        # Add layouts to main layout
        main_layout.addLayout(content_layout)
        main_layout.addWidget(self.bottom_line)

        self._position()

    def paintEvent(self, event):
        """Paint a soft manual shadow, then the styled background on top.

        A QGraphicsDropShadowEffect was deliberately NOT used: on translucent
        always-on-top windows it caused ghosting (old and new states merged
        together) and stale repaints. A plain manual shadow gives the same
        look with none of the rendering quirks.
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 70))
        painter.drawRoundedRect(
            3, 6, self.width() - 6, self.height() - 6, 12, 12
        )
        painter.end()
        super().paintEvent(event)

    def _position(self) -> None:
        """Position at top-center of screen."""
        screen = QApplication.primaryScreen().availableGeometry()
        x = (screen.width() - self.width()) // 2
        y = 16
        self.move(x, y)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.position().toPoint()

    def mouseMoveEvent(self, event):
        if self._drag_start is not None and (
            event.buttons() & Qt.MouseButton.LeftButton
        ):
            delta = event.position().toPoint() - self._drag_start
            self.move(self.pos() + delta)

    def mouseReleaseEvent(self, event):
        self._drag_start = None

    def closeEvent(self, event) -> None:
        """Hide through the app so tray state stays synchronized."""
        event.ignore()
        self.close_requested.emit()

    def _on_button_click(self) -> None:
        self.toggle_requested.emit()

    def _on_close_click(self) -> None:
        self.close_requested.emit()

    def _apply_style(
        self,
        bg: str,
        border: str,
        bottom_line: str,
        btn_style: str,
        icon: str,
        text: str,
        hint: str,
        btn_text: str,
        btn_enabled: bool = True,
    ) -> None:
        """Apply visual state."""
        self.setStyleSheet(f"""
            #overlayWidget {{
                background: {bg};
                border: 1px solid {border};
                border-radius: 12px;
            }}
        """)

        self.bottom_line.setStyleSheet(f"background: {bottom_line}; border: none;")
        self.icon_label.setPixmap(QPixmap())
        self.icon_label.setText(icon)
        self.text_label.setText(text)
        self.hint_label.setText(self._display_hint(hint))
        self.action_button.setText(btn_text)
        self.action_button.setStyleSheet(btn_style)
        self.action_button.setEnabled(btn_enabled)

        # Force an immediate repaint so state changes are shown without
        # having to hover over the overlay (translucent frameless windows
        # can skip repainting until a mouse event triggers one).
        self._force_repaint()

    def _force_repaint(self) -> None:
        """Activate the layout and schedule a clean redraw.

        An immediate synchronous repaint() could paint stale/transitional
        child geometry; activating the layout first and using update()
        avoids that. (A drop-shadow effect that once caused stale painting
        has been removed, so a normal update() repaints reliably.)
        """
        layout = self.layout()
        if layout is not None:
            layout.activate()
        self.update()

    def _display_hint(self, hint: str) -> str:
        """Keep the hotkey inside the compact overlay without changing state text."""
        if hint != self._hotkey_text:
            self.hint_label.setToolTip("")
            return hint

        self.hint_label.setToolTip(self._hotkey_text)
        return self.hint_label.fontMetrics().elidedText(
            self._hotkey_text,
            Qt.TextElideMode.ElideRight,
            self.hint_label.width(),
        )

    def set_hotkey_text(self, text: str) -> None:
        """Update the hotkey without overwriting Done/Error/Transcribing text."""
        self._hotkey_text = text
        if self._visual_state == self.READY:
            self.hint_label.setText(self._display_hint(text))
            self._force_repaint()

    def show_current_state(self) -> None:
        """Re-render the last visual state after the overlay is shown again."""
        if self._visual_state == self.RECORDING:
            self.show_recording()
        elif self._visual_state == self.TRANSCRIBING:
            self.show_transcribing()
        elif self._visual_state == self.DONE:
            self.show_done(self._success_text)
        elif self._visual_state == self.ERROR:
            self.show_error(self._error_message)
        else:
            self.show_ready()

    # ── SVG Icon ────────────────────────────────────────────────────────────

    def _icon_path(self) -> str:
        """Locate the bundled app-icon.svg (inside the exe when frozen)."""
        if getattr(sys, "frozen", False):
            base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        else:
            base = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base, "app-icon.svg")

    def _svg_mic_pixmap(self, size: int = 20):
        """Render the app icon SVG to a small pixmap, or None on failure."""
        try:
            from PyQt6.QtSvg import QSvgRenderer
        except ImportError:
            return None

        path = self._icon_path()
        if not os.path.exists(path):
            return None

        renderer = QSvgRenderer(path)
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        renderer.render(painter)
        painter.end()
        return pixmap

    # ── State Methods ────────────────────────────────────────────────────────

    def _show_recording_widgets(self) -> None:
        """Show the timer + volume meter, hide the shortcut hint."""
        self.timer_label.show()
        self.meter.show()
        self.separator.hide()
        self.hint_label.hide()

    def _hide_recording_widgets(self) -> None:
        """Hide the timer + volume meter, restore the shortcut hint."""
        self.timer_label.hide()
        self.meter.hide()
        self.separator.show()
        self.hint_label.show()

    def show_ready(self) -> None:
        """Ready state — minimal, subtle."""
        self._visual_state = self.READY
        self._hide_recording_widgets()
        self._apply_style(
            bg=self.BG_READY,
            border=self.BORDER_READY,
            bottom_line=self.BOTTOM_LINE_READY,
            btn_style=self._BTN_READY,
            icon="🎤",
            text="Promptly",
            hint=self._hotkey_text,
            btn_text="⏵",
        )
        # Show the real app icon instead of the emoji mic
        pixmap = self._svg_mic_pixmap(20)
        if pixmap is not None:
            self.icon_label.setText("")
            self.icon_label.setPixmap(pixmap)
            self._force_repaint()

    def show_recording(self) -> None:
        """Recording state — subtle red accent."""
        self._visual_state = self.RECORDING
        self.timer_label.setText("0:00")
        self.meter.set_level(0.0)
        self._show_recording_widgets()
        self._apply_style(
            bg=self.BG_RECORDING,
            border=self.BORDER_RECORDING,
            bottom_line=self.BOTTOM_LINE_RECORDING,
            btn_style=self._BTN_RECORDING,
            icon="⏺",
            text="Recording",
            hint=self._hotkey_text,
            btn_text="⏹",
        )

    def update_recording(self, seconds: float, level: float) -> None:
        """Update the recording timer and volume meter (called ~20x/sec)."""
        if not self.timer_label.isVisible():
            return
        mins, secs = int(seconds) // 60, int(seconds) % 60
        self.timer_label.setText(f"{mins}:{secs:02d}")
        self.meter.set_level(level)

    def show_transcribing(self) -> None:
        """Transcribing state — subtle blue accent, button disabled."""
        self._visual_state = self.TRANSCRIBING
        self._hide_recording_widgets()
        self._apply_style(
            bg=self.BG_TRANSCRIBING,
            border=self.BORDER_TRANSCRIBING,
            bottom_line=self.BOTTOM_LINE_TRANSCRIBING,
            btn_style=self._BTN_DISABLED,
            icon="⏳",
            text="Transcribing",
            hint="...",
            btn_text="⏳",
            btn_enabled=False,
        )

    def show_done(self, text: str = "Pasted") -> None:
        """Done state — subtle green accent."""
        self._visual_state = self.DONE
        self._success_text = text
        self._hide_recording_widgets()
        self._apply_style(
            bg=self.BG_DONE,
            border=self.BORDER_DONE,
            bottom_line=self.BOTTOM_LINE_DONE,
            btn_style=self._BTN_READY,
            icon="✓",
            text=text,
            hint="done",
            btn_text="⏵",
        )

    def show_copied(self) -> None:
        """Copied state — used when auto-paste is off."""
        self.show_done("Copied")

    def show_error(self, message: str) -> None:
        """Error state — subtle red."""
        self._visual_state = self.ERROR
        self._error_message = message
        # Truncate long messages
        display_text = message if len(message) < 20 else message[:17] + "..."
        self._apply_style(
            bg=self.BG_ERROR,
            border=self.BORDER_ERROR,
            bottom_line=self.BOTTOM_LINE_ERROR,
            btn_style=self._BTN_READY,
            icon="⚠",
            text=display_text,
            hint="retry",
            btn_text="⏵",
        )


class MinimalOverlay(QWidget):
    """Compact monochrome pill overlay with only close and action controls."""

    toggle_requested = pyqtSignal()
    close_requested = pyqtSignal()

    READY = "ready"
    RECORDING = "recording"
    TRANSCRIBING = "transcribing"
    DONE = "done"
    ERROR = "error"

    WIDTH = 116
    HEIGHT = 29
    PILL_X = 0
    PILL_Y = 0
    PILL_WIDTH = 116
    PILL_HEIGHT = 29
    CONTROL_WIDTH = 28
    BAR_COUNT = 7
    BAR_WIDTH = 2
    BAR_GAP = 2

    def __init__(self):
        super().__init__()
        self.setObjectName("minimalOverlayWidget")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedSize(self.WIDTH, self.HEIGHT)

        self._drag_start_global = None
        self._last_global = None
        self._hotkey_text = "Ctrl+Alt+V"
        self._visual_state = self.READY
        self._success_text = "Pasted"
        self._error_message = ""
        self._elapsed = 0.0
        self._level = 0.0
        self._phase = 0.0

        self._wave_timer = QTimer(self)
        self._wave_timer.setInterval(90)
        self._wave_timer.timeout.connect(self._animate_wave)

        self._position()

    def _position(self) -> None:
        """Position at top-center of screen."""
        screen = QApplication.primaryScreen().availableGeometry()
        x = (screen.width() - self.width()) // 2
        self.move(x, 16)

    def _animate_wave(self) -> None:
        self._phase += 0.42
        self.update()

    def _set_state(self, state: str) -> None:
        self._visual_state = state
        if state == self.RECORDING:
            self._wave_timer.start()
        else:
            self._wave_timer.stop()
        self.update()

    def set_hotkey_text(self, text: str) -> None:
        """Keep the same interface as the Classic overlay."""
        self._hotkey_text = text

    def show_current_state(self) -> None:
        """Re-render the last visual state after the overlay is shown again."""
        if self._visual_state == self.RECORDING:
            self.show_recording()
        elif self._visual_state == self.TRANSCRIBING:
            self.show_transcribing()
        elif self._visual_state == self.DONE:
            self.show_done(self._success_text)
        elif self._visual_state == self.ERROR:
            self.show_error(self._error_message)
        else:
            self.show_ready()

    def show_ready(self) -> None:
        """Ready state with a quiet waveform."""
        self._level = 0.0
        self._set_state(self.READY)

    def show_recording(self) -> None:
        """Recording state with a live waveform and elapsed timer."""
        self._elapsed = 0.0
        self._level = 0.0
        self._set_state(self.RECORDING)

    def update_recording(self, seconds: float, level: float) -> None:
        """Update the timer and waveform from the recorder."""
        if self._visual_state != self.RECORDING:
            return
        self._elapsed = max(0.0, seconds)
        self._level = max(0.0, min(1.0, level))
        self.update()

    def show_transcribing(self) -> None:
        """Transcribing state with a subdued static waveform."""
        self._level = 0.0
        self._set_state(self.TRANSCRIBING)

    def show_done(self, text: str = "Pasted") -> None:
        """Done state with a brighter border."""
        self._success_text = text
        self._set_state(self.DONE)

    def show_copied(self) -> None:
        """Copied state — used when auto-paste is off."""
        self.show_done("Copied")

    def show_error(self, message: str) -> None:
        """Error state with a subdued waveform."""
        self._error_message = message
        self._set_state(self.ERROR)

    def _border_alpha(self) -> int:
        return {
            self.READY: 72,
            self.RECORDING: 72,
            self.TRANSCRIBING: 72,
            self.DONE: 148,
            self.ERROR: 107,
        }.get(self._visual_state, 72)

    def _format_elapsed(self) -> str:
        minutes, seconds = int(self._elapsed) // 60, int(self._elapsed) % 60
        return f"{minutes}:{seconds:02d}"

    def _wave_geometry(self) -> tuple[float, bool]:
        wave_width = self.BAR_COUNT * self.BAR_WIDTH + (self.BAR_COUNT - 1) * self.BAR_GAP
        show_timer = self._visual_state == self.RECORDING
        content_width = wave_width + (6 + 25 if show_timer else 0)
        middle_left = self.PILL_X + 24
        middle_width = self.PILL_WIDTH - 48
        return middle_left + (middle_width - content_width) / 2, show_timer

    def _paint_wave(self, painter: QPainter) -> None:
        start_x, show_timer = self._wave_geometry()
        center_y = self.PILL_Y + self.PILL_HEIGHT / 2
        profiles = (0.45, 0.7, 0.9, 1.0, 0.9, 0.7, 0.45)

        for index, profile in enumerate(profiles):
            if self._visual_state == self.RECORDING:
                motion = 0.55 + 0.45 * abs(math.sin(self._phase + index * 0.65))
                strength = max(0.18, min(1.0, 0.2 + self._level * 0.7 + motion * 0.3))
            elif self._visual_state == self.TRANSCRIBING:
                strength = 0.32
            elif self._visual_state in (self.DONE, self.ERROR):
                strength = 0.24
            else:
                strength = 0.38

            height = max(2.0, 16 * profile * strength)
            x = start_x + index * (self.BAR_WIDTH + self.BAR_GAP)
            y = center_y - height / 2
            alpha = 235 if self._visual_state == self.RECORDING else 150
            painter.setBrush(QColor(255, 255, 255, alpha))
            painter.drawRoundedRect(QRectF(x, y, self.BAR_WIDTH, height), 1.0, 1.0)

        if show_timer:
            timer_x = start_x + self.BAR_COUNT * self.BAR_WIDTH + (self.BAR_COUNT - 1) * self.BAR_GAP + 6
            painter.setPen(QColor(255, 255, 255, 185))
            font = painter.font()
            font.setFamily("Consolas")
            font.setPixelSize(9)
            painter.setFont(font)
            painter.drawText(
                QRectF(timer_x, self.PILL_Y, 25, self.PILL_HEIGHT),
                Qt.AlignmentFlag.AlignVCenter,
                self._format_elapsed(),
            )

    def _paint_close(self, painter: QPainter) -> None:
        center_x = self.PILL_X + 14
        center_y = self.PILL_Y + self.PILL_HEIGHT / 2
        circle = QRectF(center_x - 9.5, center_y - 9.5, 19, 19)
        painter.setBrush(QColor(255, 255, 255, 20))
        painter.setPen(QPen(QColor(255, 255, 255, 107), 1))
        painter.drawEllipse(circle)
        pen = QPen(QColor(255, 255, 255, 230), 1.2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        path = QPainterPath()
        path.moveTo(center_x - 3.3, center_y - 3.3)
        path.lineTo(center_x + 3.3, center_y + 3.3)
        path.moveTo(center_x + 3.3, center_y - 3.3)
        path.lineTo(center_x - 3.3, center_y + 3.3)
        painter.drawPath(path)

    def _paint_check(self, painter: QPainter) -> None:
        center_x = self.PILL_X + self.PILL_WIDTH - 14
        center_y = self.PILL_Y + self.PILL_HEIGHT / 2
        circle = QRectF(center_x - 9.5, center_y - 9.5, 19, 19)
        painter.setBrush(QColor(255, 255, 255, 20))
        painter.setPen(QPen(QColor(255, 255, 255, 107), 1))
        painter.drawEllipse(circle)
        pen = QPen(QColor(255, 255, 255, 230), 1.2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        path = QPainterPath()
        path.moveTo(center_x - 2.5, center_y)
        path.lineTo(center_x - 0.83, center_y + 1.67)
        path.lineTo(center_x + 2.5, center_y - 2.08)
        painter.drawPath(path)

    def paintEvent(self, event) -> None:
        """Paint the monochrome pill and its state-dependent waveform."""
        painter = QPainter(self)
        painter.setRenderHints(
            QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing
        )
        pill_path = QPainterPath()
        pill_path.addRoundedRect(
            QRectF(
                self.PILL_X + 0.5,
                self.PILL_Y + 0.5,
                self.PILL_WIDTH - 1.0,
                self.PILL_HEIGHT - 1.0,
            ),
            14.0,
            14.0,
        )
        painter.setBrush(QColor(0, 0, 0, 255))
        painter.fillPath(pill_path, painter.brush())
        painter.setPen(QPen(QColor(255, 255, 255, self._border_alpha()), 1.0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(pill_path)
        self._paint_wave(painter)
        self._paint_close(painter)
        self._paint_check(painter)
        painter.end()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            global_position = event.globalPosition().toPoint()
            self._drag_start_global = global_position
            self._last_global = global_position
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._last_global is not None and event.buttons() & Qt.MouseButton.LeftButton:
            global_position = event.globalPosition().toPoint()
            self.move(self.pos() + global_position - self._last_global)
            self._last_global = global_position
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton or self._drag_start_global is None:
            return

        start = self._drag_start_global
        self._drag_start_global = None
        self._last_global = None
        global_position = event.globalPosition().toPoint()
        if (global_position - start).manhattanLength() > 4:
            return

        position = event.position().toPoint()
        in_close_button = (
            self.PILL_X + 4 <= position.x() <= self.PILL_X + 24
            and self.PILL_Y + 5 <= position.y() <= self.PILL_Y + 24
        )
        if in_close_button:
            self.close_requested.emit()
        else:
            self.toggle_requested.emit()
        event.accept()

    def closeEvent(self, event) -> None:
        """Hide through the app so tray state stays synchronized."""
        event.ignore()
        self.close_requested.emit()
