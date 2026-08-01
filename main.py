"""Promptly for Terminal — Entry Point.

Speak your terminal prompts instead of typing them.

Usage:
    uv run python main.py
"""

import os
import sys

from app import PromptlyApp
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication


def _redirect_crash_log() -> None:
    """Capture stderr to a file next to the exe (windowed builds have no console).

    PyQt6 prints unhandled-exception tracebacks to stderr right before it
    aborts — this makes those tracebacks readable in the log file.
    """
    try:
        if getattr(sys, "frozen", False):
            log_path = os.path.join(
                os.path.dirname(sys.executable), "promptly-crash.log"
            )
            sys.stderr = open(log_path, "a", buffering=1, encoding="utf-8")
    except OSError:
        pass


def main():
    _redirect_crash_log()

    # High DPI support
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # Keep running in system tray
    app.setDesktopFileName("promptly")
    app.setApplicationDisplayName("Promptly")

    voice_app = PromptlyApp()
    voice_app.run()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
