"""Voice input handling using Whisper for speech-to-text."""

import io
import tempfile
import threading
import time
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np

from .config import VoiceConfig

# Lazy imports for heavy dependencies
whisper = None
pyaudio = None


def _ensure_whisper():
    global whisper
    if whisper is None:
        import whisper as _whisper
        whisper = _whisper


def _ensure_pyaudio():
    global pyaudio
    if pyaudio is None:
        import pyaudio as _pyaudio
        pyaudio = _pyaudio


@dataclass
class TranscriptionResult:
    """Result of a voice transcription."""

    text: str
    language: str
    confidence: float


class VoiceInputHandler:
    """Handles voice input using Whisper for transcription."""

    # Audio settings
    SAMPLE_RATE = 16000
    CHANNELS = 1
    CHUNK_SIZE = 1024
    FORMAT_BITS = 16

    def __init__(self, config: VoiceConfig):
        self.config = config
        self.model = None
        self._recording = False
        self._audio_data: list[bytes] = []
        self._stream = None
        self._audio = None
        self._lock = threading.Lock()

    def load_model(self) -> None:
        """Load the Whisper model."""
        _ensure_whisper()

        model_name = self.config.whisper_model
        print(f"Loading Whisper model '{model_name}'...")

        self.model = whisper.load_model(model_name)
        print("Whisper model loaded.")

    def ensure_model_loaded(self) -> None:
        """Ensure the model is loaded."""
        if self.model is None:
            self.load_model()

    def start_recording(self) -> None:
        """Start recording audio from the microphone."""
        _ensure_pyaudio()

        with self._lock:
            if self._recording:
                return

            self._audio_data = []
            self._recording = True

            self._audio = pyaudio.PyAudio()
            self._stream = self._audio.open(
                format=pyaudio.paInt16,
                channels=self.CHANNELS,
                rate=self.SAMPLE_RATE,
                input=True,
                frames_per_buffer=self.CHUNK_SIZE,
                stream_callback=self._audio_callback,
            )
            self._stream.start_stream()

    def _audio_callback(self, in_data, frame_count, time_info, status):
        """Callback for audio stream."""
        _ensure_pyaudio()

        if self._recording:
            self._audio_data.append(in_data)
        return (in_data, pyaudio.paContinue)

    def stop_recording(self) -> bytes:
        """Stop recording and return the audio data."""
        _ensure_pyaudio()

        with self._lock:
            self._recording = False

            if self._stream:
                self._stream.stop_stream()
                self._stream.close()
                self._stream = None

            if self._audio:
                self._audio.terminate()
                self._audio = None

            audio_bytes = b"".join(self._audio_data)
            self._audio_data = []
            return audio_bytes

    def transcribe_audio(self, audio_data: bytes) -> TranscriptionResult | None:
        """Transcribe audio data to text using Whisper."""
        self.ensure_model_loaded()

        if not audio_data:
            return None

        # Convert bytes to numpy array
        audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0

        # Transcribe
        result = self.model.transcribe(
            audio_np,
            language=self.config.language if self.config.language != "auto" else None,
            fp16=False,  # Use fp32 for CPU compatibility
        )

        text = result.get("text", "").strip()
        if not text:
            return None

        return TranscriptionResult(
            text=text,
            language=result.get("language", "en"),
            confidence=1.0,  # Whisper doesn't provide per-transcription confidence
        )

    def record_and_transcribe(self, duration: float = None, stop_event: threading.Event = None) -> TranscriptionResult | None:
        """Record audio and transcribe it.

        Args:
            duration: Maximum recording duration in seconds (None for manual stop)
            stop_event: Event to signal stop recording

        Returns:
            TranscriptionResult or None if no speech detected
        """
        self.start_recording()

        if duration:
            time.sleep(duration)
        elif stop_event:
            stop_event.wait()
        else:
            # Default timeout
            time.sleep(10)

        audio_data = self.stop_recording()
        return self.transcribe_audio(audio_data)

    def is_recording(self) -> bool:
        """Check if currently recording."""
        return self._recording


class PushToTalkHandler:
    """Handles push-to-talk functionality with hotkey detection."""

    def __init__(
        self,
        voice_input: VoiceInputHandler,
        hotkey: str,
        on_transcription: Callable[[str], None],
        on_start: Callable[[], None] | None = None,
        on_stop: Callable[[], None] | None = None,
    ):
        self.voice_input = voice_input
        self.hotkey = hotkey
        self.on_transcription = on_transcription
        self.on_start = on_start
        self.on_stop = on_stop
        self._running = False
        self._key_pressed = False
        self._listener = None

    def _parse_hotkey(self) -> tuple[set, str]:
        """Parse hotkey string into modifiers and key."""
        parts = self.hotkey.lower().split("+")
        key = parts[-1]
        modifiers = set(parts[:-1])
        return modifiers, key

    def start(self) -> None:
        """Start listening for the hotkey."""
        from pynput import keyboard

        self._running = True
        required_modifiers, trigger_key = self._parse_hotkey()

        current_modifiers = set()

        def on_press(key):
            nonlocal current_modifiers

            if not self._running:
                return False

            # Track modifiers
            try:
                if hasattr(key, "name"):
                    key_name = key.name.lower()
                    if key_name in ("ctrl", "ctrl_l", "ctrl_r"):
                        current_modifiers.add("ctrl")
                    elif key_name in ("shift", "shift_l", "shift_r"):
                        current_modifiers.add("shift")
                    elif key_name in ("alt", "alt_l", "alt_r", "option"):
                        current_modifiers.add("alt")
                    elif key_name in ("cmd", "cmd_l", "cmd_r", "super"):
                        current_modifiers.add("cmd")
            except AttributeError:
                pass

            # Check for trigger key
            try:
                key_char = key.char.lower() if hasattr(key, "char") and key.char else None
                key_name = key.name.lower() if hasattr(key, "name") else None
                actual_key = key_char or key_name

                if actual_key == trigger_key and required_modifiers <= current_modifiers:
                    if not self._key_pressed:
                        self._key_pressed = True
                        self._on_hotkey_pressed()
            except AttributeError:
                pass

        def on_release(key):
            nonlocal current_modifiers

            if not self._running:
                return False

            # Track modifier release
            try:
                if hasattr(key, "name"):
                    key_name = key.name.lower()
                    if key_name in ("ctrl", "ctrl_l", "ctrl_r"):
                        current_modifiers.discard("ctrl")
                    elif key_name in ("shift", "shift_l", "shift_r"):
                        current_modifiers.discard("shift")
                    elif key_name in ("alt", "alt_l", "alt_r", "option"):
                        current_modifiers.discard("alt")
                    elif key_name in ("cmd", "cmd_l", "cmd_r", "super"):
                        current_modifiers.discard("cmd")
            except AttributeError:
                pass

            # Check for trigger key release
            try:
                key_char = key.char.lower() if hasattr(key, "char") and key.char else None
                key_name = key.name.lower() if hasattr(key, "name") else None
                actual_key = key_char or key_name

                if actual_key == trigger_key:
                    if self._key_pressed:
                        self._key_pressed = False
                        self._on_hotkey_released()
            except AttributeError:
                pass

        self._listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        self._listener.start()

    def _on_hotkey_pressed(self) -> None:
        """Called when hotkey is pressed."""
        if self.on_start:
            self.on_start()
        self.voice_input.start_recording()

    def _on_hotkey_released(self) -> None:
        """Called when hotkey is released."""
        if self.on_stop:
            self.on_stop()

        audio_data = self.voice_input.stop_recording()
        result = self.voice_input.transcribe_audio(audio_data)

        if result and result.text:
            self.on_transcription(result.text)

    def stop(self) -> None:
        """Stop listening for the hotkey."""
        self._running = False
        if self._listener:
            self._listener.stop()
            self._listener = None

    def is_running(self) -> bool:
        """Check if the handler is running."""
        return self._running
