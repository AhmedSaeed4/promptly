"""Microphone audio recorder using sounddevice."""

import tempfile

import numpy as np
import sounddevice as sd
from scipy.io.wavfile import write as write_wav

SAMPLE_RATE = 16000  # Hz — Whisper expects 16kHz
CHANNELS = 1  # Mono
MIN_DURATION = 0.5  # Ignore recordings shorter than this (seconds)


class AudioRecorder:
    """Records audio from the default microphone into a numpy buffer."""

    def __init__(self, sample_rate: int = SAMPLE_RATE, channels: int = CHANNELS):
        self.sample_rate = sample_rate
        self.channels = channels
        self._chunks: list[np.ndarray] = []
        self._stream: sd.InputStream | None = None
        self._recording = False
        self._level = 0.0  # Smoothed mic level, 0..1 (for the volume meter)

    @property
    def is_recording(self) -> bool:
        return self._recording

    def start(self) -> None:
        """Begin capturing audio from the microphone."""
        self._chunks = []
        self._level = 0.0
        self._recording = False

        stream = None
        try:
            stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="float32",
                callback=self._on_audio_frame,
            )
            stream.start()
        except Exception:
            if stream is not None:
                try:
                    stream.close()
                except Exception:
                    pass
            self._stream = None
            self._recording = False
            raise

        self._stream = stream
        self._recording = True

    def _on_audio_frame(
        self, indata: np.ndarray, frames: int, time_info, status
    ) -> None:
        """Called by sounddevice for each audio chunk."""
        if self._recording:
            self._chunks.append(indata.copy())
            # Track smoothed mic level (0..1) for the live volume meter.
            # Gain + a curve exponent so normal conversation moves the meter,
            # not just loud speech.
            rms = float(np.sqrt(np.mean(indata**2)))
            target = min(1.0, (rms * 25.0) ** 0.75)
            self._level = 0.5 * self._level + 0.5 * target

    @property
    def level(self) -> float:
        """Current smoothed mic level (0..1), for the volume meter."""
        return self._level

    def stop(self) -> np.ndarray | None:
        """Stop capturing and return the full audio array, or None if nothing was captured."""
        self._recording = False

        stream = self._stream
        self._stream = None
        if stream:
            try:
                stream.stop()
            except Exception:
                pass
            try:
                stream.close()
            except Exception:
                pass

        if not self._chunks:
            return None

        audio = np.concatenate(self._chunks, axis=0)
        self._chunks = []
        return audio

    def save_wav(self, audio: np.ndarray) -> str | None:
        """Save a numpy audio array to a temporary WAV file.

        Returns the file path, or None if the recording is too short.
        """
        duration = len(audio) / self.sample_rate

        if duration < MIN_DURATION:
            return None

        temp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        write_wav(temp.name, self.sample_rate, audio)
        return temp.name

    @property
    def duration(self) -> float:
        """Duration of currently buffered audio in seconds (0 if not recording)."""
        if not self._chunks:
            return 0.0
        total_frames = sum(chunk.shape[0] for chunk in self._chunks)
        return total_frames / self.sample_rate
