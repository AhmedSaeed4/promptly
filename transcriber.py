"""Groq Whisper transcription."""

import io

from PyQt6.QtCore import QSettings
from groq import Groq

# Connection-level problems worth retrying automatically. Everything else
# (bad API key, malformed request, ...) fails immediately — retrying cannot
# fix those, and the app surfaces them right away.
_RETRYABLE_MESSAGE_MARKERS = (
    "connection",
    "timed out",
    "timeout",
    "temporarily",
    "unavailable",
    "rate limit",
    "429",
    "500",
    "502",
    "503",
    "504",
    "529",
)


def is_retryable_error(exc: BaseException) -> bool:
    """Classify a transcription exception as transient (worth retrying) or not."""
    # groq.SDKError covers status errors in older SDKs; newer SDKs expose
    # typed exceptions on the `groq` package. Check attributes defensively so
    # any SDK version classifies sensibly.
    status_code = getattr(exc, "status_code", None)
    if status_code is not None:
        return status_code == 429 or int(status_code) >= 500

    type_name = type(exc).__name__.lower()
    if "connection" in type_name or "timeout" in type_name:
        return True
    if "auth" in type_name or "permission" in type_name or "notfound" in type_name:
        return False

    message = str(exc).lower()
    return any(marker in message for marker in _RETRYABLE_MESSAGE_MARKERS)


def _get_api_key() -> str:
    """Get the Groq API key from the app's saved settings (Windows registry).

    The stored value is sanitized defensively: only the first whitespace-
    separated token is used, so stray newlines or pasted extra text (e.g.
    a MODEL= line) can never corrupt the request.
    """
    settings = QSettings("Promptly", "Promptly")
    key = settings.value("api_key", "") or ""
    key = str(key).strip().split()[0] if str(key).strip() else ""
    return key


_client: Groq | None = None


def get_client() -> Groq:
    """Get or create the Groq client (lazy singleton)."""
    global _client
    if _client is None:
        api_key = _get_api_key()
        if not api_key:
            raise ValueError(
                "No API key found. Right-click the tray icon, open Settings, "
                "and add your Groq API key."
            )
        _client = Groq(api_key=api_key)
    return _client


def _upload_source(source: str | bytes):
    """Build the multipart upload value for a file path or in-memory WAV bytes.

    Bytes are wrapped as ("audio.wav", <binary stream>, "audio/wav") so the
    Groq API receives a proper filename and content type without anything
    ever being written to disk.
    """
    if isinstance(source, bytes):
        return ("audio.wav", io.BytesIO(source), "audio/wav")
    return source


def transcribe(
    source: str | bytes,
    model: str = "whisper-large-v3-turbo",
    language: str = "",
) -> str:
    """Send audio to Groq Whisper and return the transcribed text.

    Args:
        source: Path to an audio file (WAV, MP3, ...) or raw WAV bytes
            for in-memory recordings.
        model: Groq model name. Defaults to the fast turbo model.
        language: Whisper language code (e.g. "hi", "ur"). Empty string
            means auto-detect.

    Returns:
        Transcribed text, stripped of leading/trailing whitespace.
    """
    client = get_client()

    result = client.audio.transcriptions.create(
        file=_upload_source(source),
        model=model,
        response_format="text",
        **({"language": language} if language else {}),
    )

    return result.strip() if result else ""


def translate_to_english(
    source: str | bytes, model: str = "whisper-large-v3"
) -> str:
    """Send audio to Groq's translation endpoint → English text.

    Translates speech in ANY language into English. Note: only
    whisper-large-v3 supports translation — the turbo model does not.

    Args:
        source: Path to an audio file or raw WAV bytes.
        model: Groq model name. Must be whisper-large-v3.

    Returns:
        Translated English text, stripped of leading/trailing whitespace.
    """
    client = get_client()

    result = client.audio.translations.create(
        file=_upload_source(source),
        model=model,
        response_format="text",
    )

    return result.strip() if result else ""
