"""
PromptlyApp — main application class.

Orchestrates the system tray, overlay, recording, transcription, and auto-paste.
"""

import os
import sys
import time

from PyQt6.QtCore import QObject, QSettings, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont, QIcon, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import QApplication, QFileDialog, QDialog, QMenu, QSystemTrayIcon

from hotkey import MOD_ALT, MOD_CONTROL, VK_V, GlobalHotkey, parse_hotkey
from overlay import MinimalOverlay, Overlay
from paster import copy_to_clipboard, paste_into_terminal
from recorder import AudioRecorder
from settings_dialog import SettingsDialog
from transcriber import transcribe, translate_to_english

# ── Transcription Worker ─────────────────────────────────────────────────────


class TranscriptionWorker(QThread):
    """Runs transcription in a background thread to keep the UI responsive."""

    done = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(
        self,
        file_path: str,
        model: str,
        language: str = "",
        mode: str = "transcribe",
        cleanup: bool = True,
    ):
        super().__init__()
        self.file_path = file_path
        self.model = model
        self.language = language
        self.mode = mode  # "transcribe" (same language) or "translate" (to English)
        self.cleanup = cleanup  # If True, delete the file after transcription

    def run(self) -> None:
        try:
            import transcriber as _transcriber

            _transcriber._client = None  # Force client to re-read the API key

            if self.mode == "translate":
                text = translate_to_english(self.file_path, self.model)
            else:
                text = transcribe(self.file_path, self.model, self.language)
            self.done.emit(text if text else "")
        except Exception as e:
            self.error.emit(str(e))
        finally:
            if self.cleanup:
                try:
                    os.unlink(self.file_path)
                except OSError:
                    pass


# ── Main Application ─────────────────────────────────────────────────────────


class PromptlyApp(QObject):
    """Main application — system tray app with global hotkey voice input.

    State machine:
        IDLE → (Ctrl+Alt+V / ▶) → RECORDING → (Ctrl+Alt+V / ⏹) → TRANSCRIBING → (done) → IDLE
    """

    # Signals to safely cross from the hotkey background thread to the Qt main thread
    _hotkey_pressed = pyqtSignal()
    _hotkey_failed = pyqtSignal(str)

    IDLE = "idle"
    RECORDING = "recording"
    TRANSCRIBING = "transcribing"
    DONE = "done"
    ERROR = "error"

    def __init__(self):
        super().__init__()

        self._state = self.IDLE
        self._worker: TranscriptionWorker | None = None
        self._rec_timer: QTimer | None = None
        self._reset_timer = QTimer(self)
        self._reset_timer.setSingleShot(True)
        self._reset_timer.timeout.connect(self._reset)
        self._shutting_down = False
        self._shutdown_complete = False
        self._success_action = "Pasted"
        self._error_message = ""

        # Components
        self.recorder = AudioRecorder()
        self._overlay_style = self._get_overlay_style()
        self.overlay = self._create_overlay(self._overlay_style)

        # System tray (must exist before the hotkey can show failure notifications)
        self._setup_tray()

        # App-wide window icon (overlay, settings dialog, alt-tab)
        app = QApplication.instance()
        if app is not None:
            app.setWindowIcon(self._create_icon("gray", badge=False))

        # Global hotkey — the user's choice from Settings, defaulting to
        # Ctrl+Alt+V. The callback fires on a background thread, and if
        # another app already holds the hotkey the user gets a tray warning.
        settings = QSettings("Promptly", "Promptly")
        configured_hotkey = str(settings.value("hotkey", "") or "").strip()
        hotkey_str = configured_hotkey or "Ctrl+Alt+V"
        parsed = parse_hotkey(hotkey_str)
        if not configured_hotkey:
            hotkey_str = "Ctrl+Alt+V"
            parsed = (VK_V, MOD_ALT | MOD_CONTROL)
        self._active_hotkey_text = hotkey_str
        self._hotkey_text = hotkey_str if parsed is not None else "Invalid hotkey"
        self.overlay.set_hotkey_text(self._hotkey_text)

        self._hotkey_pressed.connect(self._toggle)
        self._hotkey_failed.connect(self._on_hotkey_failed)
        self.hotkey: GlobalHotkey | None = None
        if parsed is not None:
            vk, mods = parsed
            self.hotkey = GlobalHotkey(key=vk, modifiers=mods)
            self.hotkey.register(
                callback=self._hotkey_pressed.emit,
                on_fail=lambda text=hotkey_str: self._hotkey_failed.emit(
                    f"{text} is already in use by another app. "
                    "Choose another hotkey in Settings."
                ),
            )
        else:
            self._on_hotkey_failed(
                f"Saved hotkey '{configured_hotkey}' is not supported. "
                "Open Settings and choose another hotkey."
            )

        # First-launch check: show Settings if no API key is configured
        self._check_first_launch()

        # Show the overlay on startup so new users see the interface right away
        if not self._overlay_auto_hide():
            self._show_overlay()

    # ── Tray Icon ────────────────────────────────────────────────────────────

    def _get_overlay_style(self) -> str:
        """Read the saved overlay style, falling back to the existing design."""
        settings = QSettings("Promptly", "Promptly")
        style = str(settings.value("overlay_style", "classic") or "classic")
        return style if style in ("classic", "minimal") else "classic"

    def _create_overlay(self, style: str):
        """Create the selected overlay and connect its shared app signals."""
        overlay = MinimalOverlay() if style == "minimal" else Overlay()
        overlay.toggle_requested.connect(self._toggle)
        overlay.close_requested.connect(self._hide_overlay)
        return overlay

    def _set_overlay_style(self, style: str) -> None:
        """Switch overlay designs without restarting or losing its screen position."""
        style = style if style in ("classic", "minimal") else "classic"
        if style == self._overlay_style:
            return

        old_overlay = self.overlay
        was_visible = old_overlay.isVisible()
        old_center = old_overlay.frameGeometry().center()
        old_overlay.hide()

        self._overlay_style = style
        self.overlay = self._create_overlay(style)
        self.overlay.move(old_center - self.overlay.rect().center())
        self.overlay.set_hotkey_text(self._hotkey_text)
        old_overlay.deleteLater()

        if was_visible:
            self._render_overlay_state()
            self.overlay.show()
        self._sync_overlay_tray_action()

    def _icon_path(self) -> str:
        """Locate the bundled app-icon.svg (inside the exe when frozen)."""
        if getattr(sys, "frozen", False):
            base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        else:
            base = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base, "app-icon.svg")

    def _create_icon(self, color_name: str, badge: bool = True) -> QIcon:
        """Tray/window icon: the SVG app icon, plus a state-colored status dot.

        The badge dot shows the current state (gray/red/blue/green). Falls
        back to the drawn mic icon if the SVG cannot be loaded.
        """
        try:
            from PyQt6.QtSvg import QSvgRenderer
        except ImportError:
            return self._create_fallback_icon(color_name)

        path = self._icon_path()
        if not os.path.exists(path):
            return self._create_fallback_icon(color_name)

        size = 64
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        renderer = QSvgRenderer(path)
        renderer.render(painter)

        if badge:
            colors = {
                "gray": QColor(140, 140, 140),
                "red": QColor(220, 50, 50),
                "blue": QColor(50, 80, 200),
                "green": QColor(50, 180, 50),
            }
            color = colors.get(color_name, QColor(140, 140, 140))
            r = 11
            painter.setPen(QPen(QColor(255, 255, 255, 220), 3))
            painter.setBrush(QBrush(color))
            painter.drawEllipse(
                size - 2 * r - 1, size - 2 * r - 1, 2 * r, 2 * r
            )

        painter.end()
        return QIcon(pixmap)

    def _create_fallback_icon(self, color_name: str) -> QIcon:
        """Drawn fallback: colored circle with a white microphone symbol."""
        colors = {
            "gray": QColor(140, 140, 140),
            "red": QColor(220, 50, 50),
            "blue": QColor(50, 80, 200),
            "green": QColor(50, 180, 50),
        }
        color = colors.get(color_name, QColor(140, 140, 140))

        size = 64
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)

        from PyQt6.QtGui import QPainter, QPainterPath

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw filled circle
        painter.setBrush(QBrush(color))
        painter.setPen(QPen(QColor(255, 255, 255, 60), 2))
        painter.drawEllipse(4, 4, size - 8, size - 8)

        # Draw microphone icon (white)
        painter.setPen(
            QPen(
                QColor(255, 255, 255),
                2.5,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
        )
        painter.setBrush(Qt.BrushStyle.NoBrush)

        cx, cy = size // 2, size // 2

        # Mic body (rounded rect)
        mic_w, mic_h = 10, 16
        painter.drawRoundedRect(
            cx - mic_w // 2, cy - mic_h // 2 - 2, mic_w, mic_h, 5, 5
        )

        # Mic holder arc
        painter.drawArc(cx - 12, cy - 10, 24, 24, -30 * 16, -120 * 16)

        # Mic stand
        painter.drawLine(cx, cy + 7, cx, cy + 13)

        # Mic base
        painter.drawLine(cx - 5, cy + 13, cx + 5, cy + 13)

        painter.end()
        return QIcon(pixmap)

    def _setup_tray(self) -> None:
        """Create the system tray icon with context menu."""
        self.tray_icon = QSystemTrayIcon()
        self.tray_icon.setIcon(self._create_icon("gray"))
        self.tray_icon.setToolTip("Promptly — Ready")

        # Context menu
        menu = QMenu()

        self.overlay_action = menu.addAction("🎤  Show Overlay")
        self.overlay_action.triggered.connect(self._toggle_overlay)

        self.test_action = menu.addAction("🧪  Test with audio file...")
        self.test_action.triggered.connect(self._test_with_file)

        menu.addSeparator()

        settings_action = menu.addAction("⚙️  Settings")
        settings_action.triggered.connect(self._show_settings)

        menu.addSeparator()

        quit_action = menu.addAction("❌  Quit")
        quit_action.triggered.connect(self._quit)

        self.tray_icon.setContextMenu(menu)

        # Left-click also toggles recording
        self.tray_icon.activated.connect(self._on_tray_activated)

        self.tray_icon.show()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        """Handle tray icon clicks — left-click toggles overlay visibility."""
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._toggle_overlay()

    def _on_hotkey_failed(self, message: str) -> None:
        """Warn the user when their hotkey could not be registered."""
        if self._shutting_down:
            return
        print(message)
        self.tray_icon.showMessage(
            "Promptly",
            f"⚠️ {message}",
            QSystemTrayIcon.MessageIcon.Warning,
            5000,
        )

    # ── Overlay Visibility ──────────────────────────────────────────────────

    def _toggle_overlay(self) -> None:
        """Toggle the overlay window on/off."""
        if self.overlay.isVisible():
            self._hide_overlay()
        else:
            self._show_overlay()

    def _overlay_auto_hide(self) -> bool:
        """Whether the overlay should hide after the recording workflow ends."""
        settings = QSettings("Promptly", "Promptly")
        return settings.value("overlay_auto_hide", False, type=bool)

    def _apply_overlay_visibility_setting(self) -> None:
        """Apply the overlay visibility preference after Settings is saved."""
        if self._overlay_auto_hide():
            if self._state != self.RECORDING:
                self.overlay.hide()
                self._sync_overlay_tray_action()
            return

        if not self.overlay.isVisible():
            self._show_overlay()

    def _render_overlay_state(self) -> None:
        """Render the overlay from the app state, including transient states."""
        if self._state == self.RECORDING:
            self.overlay.show_recording()
        elif self._state == self.TRANSCRIBING:
            self.overlay.show_transcribing()
        elif self._state == self.DONE:
            self.overlay.show_done(self._success_action)
        elif self._state == self.ERROR:
            self.overlay.show_error(self._error_message)
        else:
            self.overlay.show_ready()

    def _sync_overlay_tray_action(self) -> None:
        """Keep the tray command aligned with the overlay's actual visibility."""
        self.overlay_action.setText(
            "🎤  Hide Overlay" if self.overlay.isVisible() else "🎤  Show Overlay"
        )

    def _show_overlay(self) -> None:
        """Show the overlay in the current application state."""
        if self._shutting_down:
            return
        self._render_overlay_state()
        self.overlay.show()
        self._sync_overlay_tray_action()

    def activate_existing_instance(self) -> None:
        """Show the existing overlay when a second launch is attempted."""
        if self._shutting_down:
            return
        self._show_overlay()
        self.overlay.raise_()
        self.overlay.activateWindow()

    def _hide_overlay(self) -> None:
        """Hide the overlay. Cancels recording if active, lets transcription finish."""
        if self._shutting_down:
            self.overlay.hide()
            self._sync_overlay_tray_action()
            return
        if self._state == self.RECORDING:
            # Cancel the active recording
            self._stop_rec_timer()
            self.recorder.stop()
            self._reset_timer.stop()
            self._state = self.IDLE
            self.tray_icon.setIcon(self._create_icon("gray"))
            self.tray_icon.setToolTip("Promptly — Ready")
        # If transcribing, let it continue — result goes to clipboard

        self.overlay.hide()
        self._sync_overlay_tray_action()

    # ── State Machine ────────────────────────────────────────────────────────

    # ── First Launch ─────────────────────────────────────────────────────────

    def _check_first_launch(self) -> None:
        """Check if an API key is configured. Show Settings dialog if not found.

        The key lives in the registry only — no .env file, so the app stays a
        single portable file.
        """
        settings = QSettings("Promptly", "Promptly")
        api_key = settings.value("api_key", "") or ""

        if not api_key:
            print(
                "[promptly] No API key found — opening Settings for first-time setup."
            )
            self._show_settings()

    # ── State Machine ────────────────────────────────────────────────────────

    def _has_api_key(self) -> bool:
        """True if a Groq API key is configured in settings."""
        settings = QSettings("Promptly", "Promptly")
        key = settings.value("api_key", "") or ""
        return bool(str(key).strip())

    def _require_api_key(self) -> bool:
        """If no API key is set, guide the user to Settings and return False."""
        if self._has_api_key():
            return True
        self._show_error("API key required")
        self.tray_icon.showMessage(
            "Promptly",
            "❌ No API key found. The Settings window will open so you can add "
            "your Groq API key.",
            QSystemTrayIcon.MessageIcon.Warning,
            5000,
        )
        print("[promptly] No API key set — opening Settings.")
        QTimer.singleShot(800, self._show_settings)
        return False

    def _toggle(self) -> None:
        """Toggle recording via hotkey or overlay button.

        Recording starts with the overlay shown directly in the recording
        state — it is never flashed to Ready first, which caused a visible
        layout shift when recording started.
        """
        if self._shutting_down:
            return
        if self._state in (self.IDLE, self.DONE, self.ERROR):
            self._reset_timer.stop()
            if not self._require_api_key():
                return
            self._start_recording()
        elif self._state == self.RECORDING:
            self._stop_and_transcribe()

    def _start_recording(self) -> None:
        """Begin recording from the microphone."""
        self._reset_timer.stop()

        try:
            self.recorder.start()
        except Exception as e:
            self._show_error(
                f"No microphone found. Please connect a mic and try again."
            )
            print(f"[promptly] Mic error: {e}")
            return

        self._state = self.RECORDING

        # Update UI — show the overlay directly in the recording state
        # (no Ready flash) so the state change is a single clean layout pass.
        self.overlay.show_recording()
        self.overlay.show()
        self._sync_overlay_tray_action()
        self.tray_icon.setIcon(self._create_icon("red"))
        self.tray_icon.setToolTip("Promptly — Recording...")

        # Live recording timer + volume meter (~20 updates/sec)
        self._rec_start = time.monotonic()
        self._rec_timer = QTimer(self)
        self._rec_timer.setInterval(50)
        self._rec_timer.timeout.connect(self._update_recording_ui)
        self._rec_timer.start()

    def _update_recording_ui(self) -> None:
        """Push elapsed time + mic level to the overlay while recording."""
        elapsed = time.monotonic() - self._rec_start
        self.overlay.update_recording(elapsed, self.recorder.level)

    def _stop_rec_timer(self) -> None:
        """Stop the live recording UI updates."""
        if self._rec_timer is not None:
            self._rec_timer.stop()
            self._rec_timer = None

    def _stop_and_transcribe(self) -> None:
        """Stop recording and start transcription."""
        if self._shutting_down:
            return
        self._state = self.TRANSCRIBING

        # Stop recording
        self._stop_rec_timer()
        audio = self.recorder.stop()

        # Update UI
        self.overlay.show_transcribing()
        self.tray_icon.setIcon(self._create_icon("blue"))
        mode = self._get_mode()
        busy_label = "Translating" if mode == "translate" else "Transcribing"
        self.tray_icon.setToolTip(f"Promptly — {busy_label}...")

        # Check if we got audio
        if audio is None:
            self._show_error("No audio captured")
            return

        # Save to temp WAV
        wav_path = self.recorder.save_wav(audio)
        if wav_path is None:
            self._show_error("Recording too short")
            return

        duration = len(audio) / self.recorder.sample_rate
        print(f"[promptly] Recorded {duration:.1f}s -> {busy_label.lower()}...")

        # Start transcription in background thread.
        # Translation is only supported by whisper-large-v3, so force it.
        model = "whisper-large-v3" if mode == "translate" else self._get_model()
        language = self._get_language()
        self._worker = TranscriptionWorker(
            wav_path, model, language=language, mode=mode
        )
        self._worker.done.connect(self._on_transcription_done)
        self._worker.error.connect(self._on_transcription_error)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.start()

    def _on_transcription_done(self, text: str) -> None:
        """Called when transcription completes successfully."""
        if self._shutting_down:
            return
        if not text:
            self._show_error("No speech detected")
            return

        print(
            f"[promptly] Transcribed: {text[:80]}{'...' if len(text) > 80 else ''}"
        )

        # Honor the auto-paste setting: paste into the active window, or
        # just copy to the clipboard when auto-paste is disabled.
        settings = QSettings("Promptly", "Promptly")
        auto_paste = settings.value("auto_paste", True, type=bool)

        if auto_paste:
            try:
                paste_into_terminal(text)
                action = "Pasted"
            except Exception as e:
                print(f"[promptly] Paste failed: {e}")
                try:
                    copy_to_clipboard(text)
                except Exception as copy_error:
                    print(f"[promptly] Clipboard fallback failed: {copy_error}")
                    self._show_error("Paste and clipboard copy failed")
                    return
                action = "Copied"
        else:
            try:
                copy_to_clipboard(text)
                action = "Copied"
            except Exception as e:
                print(f"[promptly] Copy failed: {e}")
                self._show_error("Could not copy transcription to clipboard")
                return

        # Show success silently — the overlay's green state is the feedback.
        # Tray notifications are reserved for errors only.
        self._state = self.DONE
        self._success_action = action
        self._error_message = ""
        self._render_overlay_state()
        if self._overlay_auto_hide():
            self.overlay.hide()
            self._sync_overlay_tray_action()
        self.tray_icon.setIcon(self._create_icon("green"))
        self.tray_icon.setToolTip(f"Promptly — {action}!")

        # Reset after a short delay
        self._schedule_reset(2000)

    def _on_transcription_error(self, error_msg: str) -> None:
        """Called when transcription fails."""
        if self._shutting_down:
            return
        self._show_error(f"Transcription failed: {error_msg}")

    def _on_worker_finished(self) -> None:
        """Finish a pending shutdown only after the network worker exits."""
        if self._shutting_down:
            self._finish_shutdown()

    def _show_error(self, message: str) -> None:
        """Show an error overlay and notification, then reset."""
        if self._shutting_down:
            return
        print(f"[promptly] Error: {message}")
        self._state = self.ERROR
        self._error_message = message
        self._render_overlay_state()
        if self._overlay_auto_hide():
            self.overlay.hide()
            self._sync_overlay_tray_action()
        self.tray_icon.showMessage(
            "Promptly",
            f"❌ {message}",
            QSystemTrayIcon.MessageIcon.Critical,
            3000,
        )
        self._schedule_reset(3000)

    def _schedule_reset(self, delay_ms: int) -> None:
        """Schedule one guarded reset, replacing any previous pending reset."""
        self._reset_timer.stop()
        self._reset_timer.start(delay_ms)

    def _reset(self) -> None:
        """Reset to idle state."""
        if self._shutting_down:
            return
        if self._state not in (self.DONE, self.ERROR):
            return
        self._state = self.IDLE
        self._error_message = ""
        self._render_overlay_state()
        if self._overlay_auto_hide():
            self.overlay.hide()
            self._sync_overlay_tray_action()
        self.tray_icon.setIcon(self._create_icon("gray"))
        self.tray_icon.setToolTip("Promptly — Ready")
        self.test_action.setEnabled(True)

    # ── Test Mode ────────────────────────────────────────────────────────────

    def _test_with_file(self) -> None:
        """Open a file picker and transcribe the selected audio file (no mic needed)."""
        if self._shutting_down or self._state != self.IDLE:
            return

        if not self._require_api_key():
            return

        file_path, _ = QFileDialog.getOpenFileName(
            None,
            "Select an audio or video file to transcribe",
            "",
            "Media Files (*.wav *.mp3 *.m4a *.ogg *.flac *.webm *.mp4 *.avi *.mkv *.mov *.wmv *.ts);;All Files (*)",
        )

        if not file_path:
            return  # User cancelled

        print(f"[promptly] Test mode: transcribing {file_path}")

        self._state = self.TRANSCRIBING
        self.overlay.show_transcribing()
        self.overlay.show()
        self._sync_overlay_tray_action()
        self.tray_icon.setIcon(self._create_icon("blue"))
        mode = self._get_mode()
        busy_label = "Translating" if mode == "translate" else "Transcribing"
        self.tray_icon.setToolTip(f"Promptly — {busy_label} (test)...")
        self.test_action.setEnabled(False)

        # Transcribe without deleting the user's file (cleanup=False).
        # Translation is only supported by whisper-large-v3, so force it.
        model = "whisper-large-v3" if mode == "translate" else self._get_model()
        language = self._get_language()
        self._worker = TranscriptionWorker(
            file_path, model, language=language, mode=mode, cleanup=False
        )
        self._worker.done.connect(self._on_transcription_done)
        self._worker.error.connect(self._on_transcription_error)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.start()

    # ── Settings ─────────────────────────────────────────────────────────────

    def _get_model(self) -> str:
        """Get the model name from settings."""
        from PyQt6.QtCore import QSettings

        settings = QSettings("Promptly", "Promptly")
        return settings.value("model", "whisper-large-v3-turbo")

    def _get_language(self) -> str:
        """Get the Whisper language code from settings ("" = auto-detect)."""
        from PyQt6.QtCore import QSettings

        settings = QSettings("Promptly", "Promptly")
        language = settings.value("language", "") or ""
        return str(language)

    def _get_mode(self) -> str:
        """Get the task mode from settings ("transcribe" or "translate")."""
        from PyQt6.QtCore import QSettings

        settings = QSettings("Promptly", "Promptly")
        mode = settings.value("mode", "transcribe") or "transcribe"
        return str(mode)

    def _replace_hotkey(self, new_text: str, parsed: tuple[int, int]) -> None:
        """Replace the registered hotkey transactionally, restoring it on failure."""
        old_text = self._active_hotkey_text
        old_hotkey = self.hotkey
        old_key = old_hotkey.key if old_hotkey is not None else None
        old_modifiers = old_hotkey.modifiers if old_hotkey is not None else None

        if (
            old_hotkey is not None
            and (old_key, old_modifiers) == parsed
            and self._hotkey_text == new_text
        ):
            return

        if old_hotkey is not None:
            old_hotkey.unregister()

        candidate = GlobalHotkey(key=parsed[0], modifiers=parsed[1])
        if candidate.register(callback=self._hotkey_pressed.emit):
            settings = QSettings("Promptly", "Promptly")
            settings.setValue("hotkey", new_text)
            settings.sync()
            self.hotkey = candidate
            self._active_hotkey_text = new_text
            self._hotkey_text = new_text
            self.overlay.set_hotkey_text(new_text)
            return

        candidate.unregister()

        # The new combination is unavailable. Restore the previous setting and
        # listener before telling the user that the change was rejected.
        settings = QSettings("Promptly", "Promptly")
        settings.setValue("hotkey", old_text)
        settings.sync()

        restored = False
        if old_key is not None and old_modifiers is not None:
            previous = GlobalHotkey(key=old_key, modifiers=old_modifiers)
            restored = previous.register(callback=self._hotkey_pressed.emit)
            if restored:
                self.hotkey = previous
            else:
                previous.unregister()
                self.hotkey = None
        else:
            self.hotkey = None

        self._active_hotkey_text = old_text
        self._hotkey_text = old_text if parse_hotkey(old_text) is not None else "Invalid hotkey"
        self.overlay.set_hotkey_text(self._hotkey_text)

        if restored:
            message = (
                f"{new_text} is already in use by another app. "
                f"Your previous hotkey ({old_text}) is still active."
            )
        else:
            message = (
                f"Could not register {new_text}, and the previous hotkey could "
                "not be restored. Open Settings to choose another hotkey."
            )
        self._on_hotkey_failed(message)

    def _show_settings(self) -> None:
        """Open settings and apply a new hotkey without restarting the app."""
        if self._shutting_down:
            return
        dialog = SettingsDialog()
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        settings = QSettings("Promptly", "Promptly")
        hotkey_text = str(settings.value("hotkey", "") or "").strip()
        parsed = parse_hotkey(hotkey_text) if hotkey_text else None
        if parsed is None:
            # SettingsDialog validates this path, but retain a defensive guard
            # so an invalid persisted value can never replace a working key.
            settings.setValue("hotkey", self._active_hotkey_text)
            settings.sync()
            self._on_hotkey_failed("The selected hotkey is not supported.")
            return

        self._replace_hotkey(hotkey_text, parsed)
        self._set_overlay_style(self._get_overlay_style())
        self._apply_overlay_visibility_setting()

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def run(self) -> None:
        """Enter the main event loop (blocks until quit)."""
        pass  # QApplication.exec() is called in main.py

    def _quit(self) -> None:
        """Stop new work and quit only after any network worker has finished."""
        if self._shutting_down:
            return

        self._shutting_down = True
        self._reset_timer.stop()
        self._stop_rec_timer()
        if self.recorder.is_recording:
            self.recorder.stop()

        if self.hotkey is not None:
            self.hotkey.unregister()
            self.hotkey = None

        self.overlay.hide()
        self._sync_overlay_tray_action()
        self.tray_icon.hide()

        if self._worker is not None and self._worker.isRunning():
            return

        self._finish_shutdown()

    def _finish_shutdown(self) -> None:
        """Complete shutdown after the transcription thread has stopped."""
        if self._shutdown_complete:
            return
        if self._worker is not None and self._worker.isRunning():
            return
        self._shutdown_complete = True
        QApplication.quit()
