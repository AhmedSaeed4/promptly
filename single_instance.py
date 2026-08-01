"""Prevent multiple Promptly processes from running at the same time."""

from collections.abc import Callable
import ctypes
import sys

from PyQt6.QtCore import QObject
from PyQt6.QtNetwork import QLocalServer, QLocalSocket


_kernel32 = None
if sys.platform == "win32":
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _kernel32.CreateMutexW.argtypes = [
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_wchar_p,
    ]
    _kernel32.CreateMutexW.restype = ctypes.c_void_p
    _kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    _kernel32.CloseHandle.restype = ctypes.c_int


ERROR_ALREADY_EXISTS = 183


class SingleInstance(QObject):
    """Enforce one Promptly process and coordinate later launches."""

    SERVER_NAME = "Promptly.SingleInstance"
    MUTEX_NAME = r"Local\Promptly.SingleInstance"

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._server = QLocalServer(self)
        self._server.newConnection.connect(self._on_new_connection)
        self._mutex_handle = None
        self._activation_callback: Callable[[], None] | None = None
        self._pending_activation = False

    def acquire(self) -> bool:
        """Become the primary instance, or notify the existing one."""
        if sys.platform == "win32":
            return self._acquire_windows_mutex()

        return self._acquire_local_server()

    def _acquire_windows_mutex(self) -> bool:
        """Use a native mutex because it is atomic across frozen processes."""
        if _kernel32 is None:
            return False

        handle = _kernel32.CreateMutexW(None, 0, self.MUTEX_NAME)
        if not handle:
            return False

        if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
            _kernel32.CloseHandle(handle)
            self._notify_existing_instance()
            return False

        self._mutex_handle = handle
        self._listen_for_activation()
        return True

    def _acquire_local_server(self) -> bool:
        """Fallback coordination for non-Windows development environments."""
        if self._server.listen(self.SERVER_NAME):
            return True

        # A live server means another Promptly process owns the name. Only
        # remove the endpoint after confirming that it is not reachable.
        if self._notify_existing_instance():
            return False

        QLocalServer.removeServer(self.SERVER_NAME)
        if self._server.listen(self.SERVER_NAME):
            return True

        # Another process may have won the race while the stale endpoint was
        # being removed. In either case, do not allow a second process through.
        self._notify_existing_instance()
        return False

    def _listen_for_activation(self) -> None:
        """Start the activation channel after the process lock is acquired."""
        if self._server.listen(self.SERVER_NAME):
            return

        # A previous process may have left a stale local-server endpoint.
        QLocalServer.removeServer(self.SERVER_NAME)
        self._server.listen(self.SERVER_NAME)

    def set_activation_callback(self, callback: Callable[[], None]) -> None:
        """Set the action to run when a later launch contacts this instance."""
        self._activation_callback = callback
        if self._pending_activation:
            self._pending_activation = False
            callback()

    def _notify_existing_instance(self) -> bool:
        """Ask the existing process to activate and report whether it answered."""
        socket = QLocalSocket()
        socket.connectToServer(self.SERVER_NAME)
        if not socket.waitForConnected(500):
            return False

        socket.write(b"activate")
        socket.waitForBytesWritten(500)
        socket.disconnectFromServer()
        return True

    def _on_new_connection(self) -> None:
        """Handle a launch request from a second Promptly process."""
        while self._server.hasPendingConnections():
            socket = self._server.nextPendingConnection()
            socket.disconnectFromServer()
            socket.deleteLater()

            if self._activation_callback is None:
                self._pending_activation = True
            else:
                self._activation_callback()
