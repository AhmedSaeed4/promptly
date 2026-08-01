"""Floating overlay widget — Xbox Game Bar style design with bottom accent line."""

import os
import sys

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QCursor,
    QLinearGradient,
    QPainter,
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
