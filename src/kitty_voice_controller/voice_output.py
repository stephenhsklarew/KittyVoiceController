"""Voice output handling using macOS text-to-speech."""

import subprocess
import threading
from pathlib import Path
from typing import Callable

from .config import VoiceConfig


class VoiceOutputHandler:
    """Handles voice output using macOS 'say' command."""

    def __init__(self, config: VoiceConfig):
        self.config = config
        self._speaking = False
        self._current_process: subprocess.Popen | None = None
        self._lock = threading.Lock()

    def speak(self, text: str, blocking: bool = True) -> None:
        """Speak the given text.

        Args:
            text: Text to speak
            blocking: If True, wait for speech to complete
        """
        if not text:
            return

        with self._lock:
            # Stop any current speech
            self.stop()

            cmd = [
                "say",
                "-v", self.config.tts_voice,
                "-r", str(self.config.tts_rate),
                text,
            ]

            if blocking:
                subprocess.run(cmd, check=False)
            else:
                self._current_process = subprocess.Popen(cmd)
                self._speaking = True

    def speak_async(self, text: str, on_complete: Callable[[], None] | None = None) -> None:
        """Speak text asynchronously."""
        def _speak_thread():
            self.speak(text, blocking=True)
            self._speaking = False
            if on_complete:
                on_complete()

        thread = threading.Thread(target=_speak_thread, daemon=True)
        thread.start()

    def stop(self) -> None:
        """Stop current speech."""
        with self._lock:
            if self._current_process:
                self._current_process.terminate()
                self._current_process = None
            self._speaking = False

    def is_speaking(self) -> bool:
        """Check if currently speaking."""
        return self._speaking

    @staticmethod
    def list_voices() -> list[dict]:
        """List available macOS voices."""
        try:
            result = subprocess.run(
                ["say", "-v", "?"],
                capture_output=True,
                text=True,
                check=True,
            )

            voices = []
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                # Parse format: "Name    language  # description"
                parts = line.split()
                if len(parts) >= 2:
                    name = parts[0]
                    lang = parts[1] if len(parts) > 1 else ""
                    voices.append({"name": name, "language": lang})

            return voices
        except Exception:
            return []


class SoundPlayer:
    """Plays feedback sounds."""

    # Default system sounds on macOS
    SOUNDS = {
        "listen_start": "/System/Library/Sounds/Pop.aiff",
        "listen_stop": "/System/Library/Sounds/Blow.aiff",
        "error": "/System/Library/Sounds/Basso.aiff",
        "success": "/System/Library/Sounds/Glass.aiff",
    }

    def __init__(self, config: VoiceConfig):
        self.config = config
        self._custom_sounds: dict[str, Path] = {}

    def set_custom_sound(self, name: str, path: Path) -> None:
        """Set a custom sound file for a sound type."""
        self._custom_sounds[name] = path

    def play(self, sound_name: str, blocking: bool = False) -> None:
        """Play a sound by name."""
        # Check config for whether this sound is enabled
        if sound_name == "listen_start" and not self.config.sound_listen_start:
            return
        if sound_name == "listen_stop" and not self.config.sound_listen_stop:
            return
        if sound_name == "error" and not self.config.sound_error:
            return

        # Get sound path
        sound_path = self._custom_sounds.get(sound_name) or self.SOUNDS.get(sound_name)
        if not sound_path:
            return

        # Play using afplay
        cmd = ["afplay", str(sound_path)]

        if blocking:
            subprocess.run(cmd, check=False)
        else:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def play_listen_start(self) -> None:
        """Play the listening start sound."""
        self.play("listen_start")

    def play_listen_stop(self) -> None:
        """Play the listening stop sound."""
        self.play("listen_stop")

    def play_error(self) -> None:
        """Play the error sound."""
        self.play("error")

    def play_success(self) -> None:
        """Play the success sound."""
        self.play("success")
