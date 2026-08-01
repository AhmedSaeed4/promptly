"""Groq Whisper transcription."""

from PyQt6.QtCore import QSettings
from groq import Groq


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


def transcribe(
    file_path: str,
    model: str = "whisper-large-v3-turbo",
    language: str = "",
) -> str:
    """Send an audio file to Groq Whisper and return the transcribed text.

    Args:
        file_path: Path to the audio file (WAV, MP3, etc.)
        model: Groq model name. Defaults to the fast turbo model.
        language: Whisper language code (e.g. "hi", "ur"). Empty string
            means auto-detect.

    Returns:
        Transcribed text, stripped of leading/trailing whitespace.
    """
    client = get_client()

    with open(file_path, "rb") as f:
        kwargs = {
            "file": f,
            "model": model,
            "response_format": "text",
        }
        if language:
            kwargs["language"] = language
        result = client.audio.transcriptions.create(**kwargs)

    return result.strip() if result else ""


def translate_to_english(file_path: str, model: str = "whisper-large-v3") -> str:
    """Send an audio file to Groq's translation endpoint → English text.

    Translates speech in ANY language into English. Note: only
    whisper-large-v3 supports translation — the turbo model does not.

    Args:
        file_path: Path to the audio file (WAV, MP3, etc.)
        model: Groq model name. Must be whisper-large-v3.

    Returns:
        Translated English text, stripped of leading/trailing whitespace.
    """
    client = get_client()

    with open(file_path, "rb") as f:
        result = client.audio.translations.create(
            file=f,
            model=model,
            response_format="text",
        )

    return result.strip() if result else ""
