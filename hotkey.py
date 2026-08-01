"""Global hotkey using Win32 RegisterHotKey API.

This uses native Windows APIs so no admin privileges or extra packages are needed.
The hotkey listener runs in its own daemon thread with its own message loop.
"""

import ctypes
import ctypes.wintypes as wintypes
import threading
import time

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence

user32 = ctypes.windll.user32

WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
VK_F5 = 0x74
VK_V = 0x56

# Qt modifier bits OR'd into key codes by QKeySequence/QKeyEvent
_MOD_BITS = (
    Qt.KeyboardModifier.ShiftModifier
    | Qt.KeyboardModifier.ControlModifier
    | Qt.KeyboardModifier.AltModifier
    | Qt.KeyboardModifier.MetaModifier
    | Qt.KeyboardModifier.KeypadModifier
    | Qt.KeyboardModifier.GroupSwitchModifier
).value


def _to_vk(keycode: int) -> int | None:
    """Map a Qt key code to a Windows virtual-key code, or None if unmappable."""
    if 0x30 <= keycode <= 0x5A:
        return keycode  # Digits 0-9 and A-Z map 1:1 to VK codes
    if Qt.Key.Key_F1.value <= keycode <= Qt.Key.Key_F24.value:
        return 0x70 + (keycode - Qt.Key.Key_F1.value)
    if keycode == Qt.Key.Key_Space.value:
        return 0x20
    arrows = {
        Qt.Key.Key_Left.value: 0x25,
        Qt.Key.Key_Up.value: 0x26,
        Qt.Key.Key_Right.value: 0x27,
        Qt.Key.Key_Down.value: 0x28,
    }
    return arrows.get(keycode)


def parse_hotkey(seq_str: str) -> tuple[int, int] | None:
    """Convert a QKeySequence string (e.g. 'Ctrl+Alt+V') to (vk, modifiers).

    Returns None if the string can't be parsed, has no modifier, or the
    key can't be mapped to a Windows virtual key.
    """
    seq = QKeySequence(seq_str)
    if seq.isEmpty():
        return None

    combined = seq[0].toCombined()
    keycode = combined & ~_MOD_BITS

    mods = 0
    if combined & Qt.KeyboardModifier.ControlModifier.value:
        mods |= MOD_CONTROL
    if combined & Qt.KeyboardModifier.AltModifier.value:
        mods |= MOD_ALT
    if combined & Qt.KeyboardModifier.ShiftModifier.value:
        mods |= MOD_SHIFT
    if combined & Qt.KeyboardModifier.MetaModifier.value:
        mods |= MOD_WIN
    if not mods:
        return None  # A bare key is too dangerous — require a modifier

    vk = _to_vk(keycode)
    if vk is None:
        return None
    return vk, mods


class GlobalHotkey:
    """Register a global hotkey that works even when the app is not focused.

    Usage:
        hotkey = GlobalHotkey(key=VK_V, modifiers=MOD_ALT | MOD_CONTROL)
        hotkey.register(my_callback)
        # ... later ...
        hotkey.unregister()
    """

    def __init__(
        self,
        key: int = VK_V,
        modifiers: int = MOD_ALT | MOD_CONTROL,
        hotkey_id: int = 1,
    ):
        self.key = key
        self.modifiers = modifiers
        self.hotkey_id = hotkey_id
        self._thread: threading.Thread | None = None
        self._running = False
        self._callback = None
        self._on_fail = None
        self._registered = False
        self._ready = threading.Event()

    def register(self, callback, on_fail=None, timeout: float = 2.0) -> bool:
        """Start listening for the hotkey in a background thread.

        Args:
            callback: Function to call when the hotkey is pressed.
                      WARNING: This runs on a background thread, NOT the main thread.
                      Use Qt signals or similar to safely communicate with the GUI.
            on_fail: Optional callback invoked (on the background thread) if the
                      hotkey could not be registered because another app holds it.

        Returns:
            True when Windows registered the hotkey, otherwise False.
        """
        self.unregister()
        self._callback = callback
        self._on_fail = on_fail
        self._registered = False
        self._ready = threading.Event()
        self._running = True
        self._thread = threading.Thread(target=self._listen, daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout):
            self.unregister()
            return False
        return self._registered

    def _listen(self) -> None:
        """Background thread: register the hotkey and listen for events."""
        try:
            registered = bool(
                user32.RegisterHotKey(None, self.hotkey_id, self.modifiers, self.key)
            )
        except Exception:
            registered = False

        if not registered:
            print(
                f"[hotkey] Failed to register hotkey (key=0x{self.key:02X}). "
                "It may be in use by another application."
            )
            self._running = False
            self._ready.set()
            if self._on_fail:
                self._on_fail()
            return

        self._registered = True
        self._ready.set()
        msg = wintypes.MSG()
        while self._running:
            # PeekMessage with PM_REMOVE (1) — non-blocking check
            if user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
                if msg.message == WM_HOTKEY and msg.wParam == self.hotkey_id:
                    if self._callback:
                        self._callback()
            else:
                time.sleep(0.01)  # Small sleep to avoid busy-waiting

        user32.UnregisterHotKey(None, self.hotkey_id)
        self._registered = False

    def unregister(self) -> None:
        """Stop listening and unregister the hotkey."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
