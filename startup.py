"""Launch-with-Windows support for Promptly.

Windows keeps a "Run" list in the registry (HKCU) that it reads at every
sign-in and launches everything on it. Promptly manages a single entry
there that points at the running Promptly.exe, so the tray app — and its
hotkeys — come back after every restart without a double-click.

Re-writing the entry on every launch (see `sync`) also heals a moved exe:
the entry always ends up pointing at wherever the app last ran from.
"""

import logging
import sys

try:
    import winreg
except ImportError:  # non-Windows (e.g. dev on another OS) — feature stays off
    winreg = None

logger = logging.getLogger(__name__)

RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "Promptly"


def _exe_command() -> str | None:
    """Registry command that re-launches this exact app, or None.

    Only the packaged exe registers itself; a dev run (`python main.py`)
    must never put an interpreter on the startup list.
    """
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    return None


def is_enabled() -> bool:
    """True when a Promptly entry exists on the startup list."""
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH) as key:
            winreg.QueryValueEx(key, VALUE_NAME)
            return True
    except OSError:
        return False


def enable(command: str | None = None) -> bool:
    """Add (or refresh) the Promptly entry. Returns True on success.

    `command` overrides the registered command line — test hook only.
    """
    if winreg is None:
        return False
    if command is None:
        command = _exe_command()
    if not command:
        return False
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH) as key:
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, command)
        logger.info("Startup entry set: %s", command)
        return True
    except OSError as exc:
        logger.warning("Could not set startup entry: %s", exc)
        return False


def disable() -> bool:
    """Remove the Promptly entry. Returns True when it is gone."""
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.DeleteValue(key, VALUE_NAME)
        logger.info("Startup entry removed")
        return True
    except FileNotFoundError:
        return True  # already gone — the goal state
    except OSError as exc:
        logger.warning("Could not remove startup entry: %s", exc)
        return False


def sync(enabled: bool, command: str | None = None) -> bool:
    """Make the startup list match `enabled`; returns whether it succeeded.

    Called at every app launch, so a move of the exe is picked up
    automatically on the next run.
    """
    return enable(command) if enabled else disable()
