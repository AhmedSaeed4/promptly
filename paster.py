"""Auto-paste transcribed text into the active terminal using Win32 SendInput."""

import ctypes
import ctypes.wintypes as wintypes
import time

import pyperclip

user32 = ctypes.windll.user32

# Win32 constants
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
VK_CONTROL = 0x11
VK_V = 0x56


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("ki", _KEYBDINPUT),
        ("mi", _MOUSEINPUT),
    ]


class _INPUT(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.DWORD),
        ("union", _INPUT_UNION),
    ]


def _send_key(vk: int, flags: int = 0) -> bool:
    """Send a single key event using Win32 SendInput."""
    inp = _INPUT()
    inp.type = INPUT_KEYBOARD
    inp.union.ki.wVk = vk
    inp.union.ki.dwFlags = flags
    return user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT)) == 1


def copy_to_clipboard(text: str) -> None:
    """Copy text to the clipboard without pasting."""
    pyperclip.copy(text)
    time.sleep(0.05)
    if pyperclip.paste() != text:
        raise RuntimeError("Clipboard verification failed")


def paste_into_terminal(text: str) -> None:
    """Copy text to clipboard and simulate Ctrl+V to paste into the active window.

    The text remains on the clipboard after pasting, so the user can
    Ctrl+V again anywhere.
    """
    # Copy to clipboard
    copy_to_clipboard(text)

    # Simulate Ctrl+V: Ctrl down, V down, V up, Ctrl up
    events = (
        (VK_CONTROL, 0),
        (VK_V, 0),
        (VK_V, KEYEVENTF_KEYUP),
        (VK_CONTROL, KEYEVENTF_KEYUP),
    )
    for vk, flags in events:
        if not _send_key(vk, flags):
            raise RuntimeError("Windows rejected the paste input")
