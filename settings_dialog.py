"""Settings dialog for configuring the voice input app."""

from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtGui import QKeySequence

from hotkey import parse_hotkey
from startup import sync as sync_startup

# Language options — empty value means "auto-detect" (Whisper figures it out).
# Keys are Whisper language codes.
LANGUAGES = [
    ("Auto-detect (recommended)", ""),
    ("English", "en"),
    ("Hindi", "hi"),
    ("Urdu", "ur"),
    ("Spanish", "es"),
    ("French", "fr"),
    ("German", "de"),
    ("Portuguese", "pt"),
    ("Arabic", "ar"),
    ("Chinese (Simplified)", "zh"),
    ("Japanese", "ja"),
    ("Korean", "ko"),
    ("Russian", "ru"),
    ("Italian", "it"),
    ("Dutch", "nl"),
    ("Turkish", "tr"),
    ("Bengali", "bn"),
]

# Task modes — "transcribe" keeps the spoken language, "translate" outputs English.
MODES = [
    ("Transcribe (same language)", "transcribe"),
    ("Translate to English", "translate"),
]

# Overlay styles — both remain available so users can choose their preferred UI.
OVERLAY_STYLES = [
    ("Classic (Game Bar)", "classic"),
    ("Minimal pill", "minimal"),
]


from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QKeySequenceEdit,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QMessageBox,
    QVBoxLayout,
)


class SettingsDialog(QDialog):
    """Settings dialog for the Promptly app."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Promptly — Settings")
        self.setFixedSize(420, 620)
        self.setModal(True)

        self._settings = QSettings("Promptly", "Promptly")

        self._init_ui()
        self._load_settings()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Header
        header = QLabel("⚙️ Promptly Settings")
        header.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(header)

        # Form
        form = QFormLayout()

        # API Key
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setPlaceholderText("gsk_...")
        form.addRow("Groq API Key:", self.api_key_input)

        # Model
        self.model_combo = QComboBox()
        self.model_combo.addItem(
            "Whisper Large v3 Turbo (fast)", "whisper-large-v3-turbo"
        )
        self.model_combo.addItem("Whisper Large v3 (accurate)", "whisper-large-v3")
        form.addRow("Model:", self.model_combo)

        # Mode (transcribe vs translate to English)
        self.mode_combo = QComboBox()
        for label, value in MODES:
            self.mode_combo.addItem(label, value)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        form.addRow("Mode:", self.mode_combo)

        # Language
        self.language_combo = QComboBox()
        for label, code in LANGUAGES:
            self.language_combo.addItem(label, code)
        form.addRow("Language:", self.language_combo)

        # Auto-paste
        self.auto_paste_check = QCheckBox("Automatically paste into active terminal")
        self.auto_paste_check.setChecked(True)
        form.addRow("", self.auto_paste_check)

        # AI text polish
        self.polish_check = QCheckBox("Polish text with AI (fix grammar & sentences)")
        self.polish_check.setToolTip(
            "After transcription, a fast Groq AI model cleans up the text — "
            "grammar, punctuation, filler words — before pasting. The meaning "
            "and language are never changed. If the AI is unreachable, the "
            "raw transcript is used instead."
        )
        form.addRow("Text polish:", self.polish_check)

        # Personal vocabulary — tricky names/brands/jargon the listener
        # mishears (e.g. "Claude Code" -> "cloud code"). One term per line.
        self.vocab_input = QPlainTextEdit()
        self.vocab_input.setPlaceholderText(
            "Claude Code\nGroq\nAisha\nKubernetes"
        )
        self.vocab_input.setToolTip(
            "Words the transcription often gets wrong — names, brands, jargon. "
            "One term per line. They are used as a spelling hint while "
            "listening and taught to the AI cleanup, which only fixes a word "
            "when the sentence shows you meant that term — a genuine use of a "
            "similar-sounding word is never replaced."
        )
        self.vocab_input.setMaximumHeight(88)
        form.addRow("My words:", self.vocab_input)

        # Overlay style
        self.overlay_style_combo = QComboBox()
        for label, value in OVERLAY_STYLES:
            self.overlay_style_combo.addItem(label, value)
        form.addRow("Overlay style:", self.overlay_style_combo)

        # Overlay visibility
        self.overlay_auto_hide_check = QCheckBox(
            "Auto-hide overlay after transcription"
        )
        self.overlay_auto_hide_check.setToolTip(
            "Show the overlay when recording starts and hide it when transcription finishes."
        )
        form.addRow("Overlay visibility:", self.overlay_auto_hide_check)

        # Launch with Windows — the tray app (and hotkeys) start at sign-in
        self.auto_start_check = QCheckBox(
            "Start Promptly automatically when Windows starts"
        )
        self.auto_start_check.setToolTip(
            "Adds Promptly to Windows' startup list, so the tray app — and "
            "your hotkeys — are ready right after every restart, no "
            "double-click needed. Uncheck to remove it from the list again."
        )
        form.addRow("Windows startup:", self.auto_start_check)

        # Hotkey (user-selectable, press the combo in the box)
        self.hotkey_edit = QKeySequenceEdit(QKeySequence("Ctrl+Alt+V"))
        self.hotkey_edit.setMaximumSequenceLength(1)
        form.addRow("Hotkey:", self.hotkey_edit)
        hotkey_note = QLabel("Click the box and press your combination (e.g. Ctrl+Alt+S)")
        hotkey_note.setStyleSheet("color: gray; font-size: 11px;")
        form.addRow("", hotkey_note)

        layout.addLayout(form)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save_settings)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_mode_changed(self) -> None:
        """Keep model/language consistent with the selected mode.

        Translation only works with whisper-large-v3 (not turbo), and the
        translation output is always English, so the language picker is
        irrelevant in translate mode.
        """
        if self.mode_combo.currentData() == "translate":
            index = self.model_combo.findData("whisper-large-v3")
            self.model_combo.setCurrentIndex(index)
            self.model_combo.setEnabled(False)
            self.language_combo.setEnabled(False)
        else:
            self.model_combo.setEnabled(True)
            self.language_combo.setEnabled(True)

    def _load_settings(self) -> None:
        """Load settings from QSettings."""
        api_key = self._settings.value("api_key", "")
        if api_key:
            self.api_key_input.setText(api_key)

        model = self._settings.value("model", "whisper-large-v3-turbo")
        index = self.model_combo.findData(model)
        if index >= 0:
            self.model_combo.setCurrentIndex(index)

        language = self._settings.value("language", "") or ""
        index = self.language_combo.findData(language)
        if index >= 0:
            self.language_combo.setCurrentIndex(index)
        else:
            self.language_combo.setCurrentIndex(0)  # Auto-detect

        mode = self._settings.value("mode", "transcribe") or "transcribe"
        index = self.mode_combo.findData(mode)
        if index >= 0:
            self.mode_combo.setCurrentIndex(index)
        else:
            self.mode_combo.setCurrentIndex(0)  # Transcribe
        self._on_mode_changed()

        auto_paste = self._settings.value("auto_paste", True, type=bool)
        self.auto_paste_check.setChecked(auto_paste)

        polish = self._settings.value("polish_text", True, type=bool)
        self.polish_check.setChecked(polish)

        vocab = self._settings.value("custom_vocab", "") or ""
        self.vocab_input.setPlainText(vocab)

        overlay_style = self._settings.value("overlay_style", "classic") or "classic"
        index = self.overlay_style_combo.findData(overlay_style)
        self.overlay_style_combo.setCurrentIndex(index if index >= 0 else 0)

        overlay_auto_hide = self._settings.value(
            "overlay_auto_hide", False, type=bool
        )
        self.overlay_auto_hide_check.setChecked(overlay_auto_hide)

        auto_start = self._settings.value("auto_start", True, type=bool)
        self.auto_start_check.setChecked(auto_start)

        hotkey = self._settings.value("hotkey", "") or ""
        if hotkey:
            self.hotkey_edit.setKeySequence(QKeySequence(hotkey))

    def _save_settings(self) -> None:
        """Save settings to the registry (no .env file needed)."""
        api_key = self.api_key_input.text().strip()
        model = self.model_combo.currentData()
        mode = self.mode_combo.currentData() or "transcribe"
        language = self.language_combo.currentData() or ""
        auto_paste = self.auto_paste_check.isChecked()
        polish_text = self.polish_check.isChecked()
        # One term per line, trimmed, blanks dropped — stored as the raw
        # newline-joined text so it round-trips exactly what the user sees.
        vocab = "\n".join(
            line.strip() for line in self.vocab_input.toPlainText().splitlines()
            if line.strip()
        )
        overlay_style = self.overlay_style_combo.currentData() or "classic"
        overlay_auto_hide = self.overlay_auto_hide_check.isChecked()
        auto_start = self.auto_start_check.isChecked()

        if not api_key:
            QMessageBox.warning(
                self, "Missing API Key", "Please enter your Groq API Key."
            )
            return

        hotkey_text = self.hotkey_edit.keySequence().toString(
            QKeySequence.SequenceFormat.PortableText
        ).strip()
        if not hotkey_text or parse_hotkey(hotkey_text) is None:
            QMessageBox.warning(
                self,
                "Invalid Hotkey",
                "Please press a supported combination with a modifier key "
                "(Ctrl, Alt, Shift, or Win), such as Ctrl+Alt+S.",
            )
            return

        self._settings.setValue("api_key", api_key)
        self._settings.setValue("model", model)
        self._settings.setValue("mode", mode)
        self._settings.setValue("language", language)
        self._settings.setValue("auto_paste", auto_paste)
        self._settings.setValue("polish_text", polish_text)
        self._settings.setValue("custom_vocab", vocab)
        self._settings.setValue("overlay_style", overlay_style)
        self._settings.setValue("overlay_auto_hide", overlay_auto_hide)
        self._settings.setValue("auto_start", auto_start)
        self._settings.setValue("hotkey", hotkey_text)

        # Apply the startup-list change right away (a no-op for dev runs,
        # which never touch the real startup list).
        sync_startup(auto_start)

        self.accept()

    def get_model(self) -> str:
        """Get the currently selected model."""
        return self.model_combo.currentData()

    def get_auto_paste(self) -> bool:
        """Get the auto-paste setting."""
        return self.auto_paste_check.isChecked()
