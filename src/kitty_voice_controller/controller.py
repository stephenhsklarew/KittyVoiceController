"""Main controller that orchestrates voice input, output, and Kitty integration."""

import re
import threading
import time
from dataclasses import dataclass
from typing import Callable

from .config import Config, ensure_config_exists
from .kitty import KittyController, KittyWindow, check_kitty_setup
from .summarizer import OutputSummarizer
from .voice_input import PushToTalkHandler, VoiceInputHandler
from .voice_output import SoundPlayer, VoiceOutputHandler


@dataclass
class ParsedCommand:
    """A parsed voice command."""

    target: str | None  # Project name or None for global command
    command: str  # The command text
    is_global: bool  # Whether this is a global command


class VoiceController:
    """Main controller for voice-controlled Claude Code sessions."""

    # Global commands that don't target a specific window
    GLOBAL_COMMANDS = {
        "status": "get_all_status",
        "mute": "toggle_mute",
        "unmute": "toggle_mute",
        "louder": "increase_volume",
        "softer": "decrease_volume",
        "quieter": "decrease_volume",
        "shut down": "shutdown",
        "shutdown": "shutdown",
        "stop all": "stop_all",
        "help": "speak_help",
    }

    # Window-specific commands
    WINDOW_COMMANDS = {
        "stop": "send_interrupt",
        "read": "read_output",
        "focus": "focus_window",
    }

    def __init__(self, config: Config | None = None):
        self.config = config or ensure_config_exists()
        self.kitty = KittyController(self.config)
        self.voice_input = VoiceInputHandler(self.config.voice)
        self.voice_output = VoiceOutputHandler(self.config.voice)
        self.sound_player = SoundPlayer(self.config.voice)
        self.summarizer = OutputSummarizer(self.config.summary)

        self._running = False
        self._muted = False
        self._ptt_handler: PushToTalkHandler | None = None
        self._monitor_thread: threading.Thread | None = None
        self._last_outputs: dict[str, str] = {}

    def start(self, project_names: list[str] | None = None) -> bool:
        """Start the voice controller.

        Args:
            project_names: Specific projects to launch, or None for all

        Returns:
            True if started successfully
        """
        # Check Kitty setup
        ready, message = check_kitty_setup()
        if not ready:
            print(f"Setup issue: {message}")
            return False

        # Load Whisper model
        print("Initializing voice recognition...")
        self.voice_input.load_model()

        # Launch Kitty windows
        print("Launching Claude sessions...")
        if project_names:
            self.kitty.launch_projects(project_names)
        else:
            self.kitty.launch_all_projects()

        if not self.kitty.windows:
            print("No windows launched. Check your project configuration.")
            return False

        # Start push-to-talk handler
        self._ptt_handler = PushToTalkHandler(
            voice_input=self.voice_input,
            hotkey=self.config.voice.hotkey,
            on_transcription=self._handle_transcription,
            on_start=self._on_listen_start,
            on_stop=self._on_listen_stop,
        )
        self._ptt_handler.start()

        # Start output monitor
        self._running = True
        self._monitor_thread = threading.Thread(target=self._monitor_outputs, daemon=True)
        self._monitor_thread.start()

        # Announce ready
        projects = ", ".join(self.kitty.windows.keys())
        self.speak(f"Voice control ready. Projects: {projects}")

        print(f"\nVoice control active!")
        print(f"Hold {self.config.voice.hotkey} to speak")
        print(f"Projects: {projects}")
        print(f"Press Ctrl+C to exit\n")

        return True

    def run(self, project_names: list[str] | None = None) -> None:
        """Start and run the voice controller until interrupted."""
        if not self.start(project_names):
            return

        try:
            while self._running:
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\nShutting down...")
        finally:
            self.stop()

    def stop(self) -> None:
        """Stop the voice controller."""
        self._running = False

        if self._ptt_handler:
            self._ptt_handler.stop()

        self.speak("Shutting down voice control.")
        self.kitty.close_all()

    def _on_listen_start(self) -> None:
        """Called when push-to-talk is activated."""
        self.sound_player.play_listen_start()

    def _on_listen_stop(self) -> None:
        """Called when push-to-talk is released."""
        self.sound_player.play_listen_stop()

    def _handle_transcription(self, text: str) -> None:
        """Handle transcribed voice input."""
        print(f"Heard: {text}")

        # Parse the command
        parsed = self._parse_command(text)

        if parsed.is_global:
            self._execute_global_command(parsed.command)
        elif parsed.target:
            self._execute_window_command(parsed.target, parsed.command)
        else:
            self.speak("I didn't understand which project you meant.")

    def _parse_command(self, text: str) -> ParsedCommand:
        """Parse a voice command to extract target and action."""
        text_lower = text.lower().strip()

        # Check for global commands first
        for cmd_phrase in self.GLOBAL_COMMANDS:
            if text_lower.startswith(cmd_phrase) or text_lower == cmd_phrase:
                return ParsedCommand(target=None, command=cmd_phrase, is_global=True)

        # Look for project name pattern: "project: command" or "project command"
        # Try colon separator first
        if ":" in text:
            parts = text.split(":", 1)
            target_phrase = parts[0].strip()
            command = parts[1].strip() if len(parts) > 1 else ""

            project = self.config.find_project_by_voice(target_phrase)
            if project:
                return ParsedCommand(target=project.name, command=command, is_global=False)

        # Try to find project name at the start
        for project in self.config.projects.values():
            for name in project.get_all_names():
                # Check if text starts with project name
                pattern = rf"^{re.escape(name)}\s+"
                match = re.match(pattern, text_lower)
                if match:
                    command = text[match.end():].strip()
                    return ParsedCommand(target=project.name, command=command, is_global=False)

        # No target found, might be a bare command for the active window
        # For now, report as unparseable
        return ParsedCommand(target=None, command=text, is_global=False)

    def _execute_global_command(self, command: str) -> None:
        """Execute a global command."""
        method_name = self.GLOBAL_COMMANDS.get(command.lower())
        if method_name and hasattr(self, method_name):
            getattr(self, method_name)()

    def _execute_window_command(self, project_name: str, command: str) -> None:
        """Execute a command for a specific window."""
        window = self.kitty.get_window(project_name)
        if not window:
            self.speak(f"Project {project_name} is not running.")
            return

        command_lower = command.lower().strip()

        # Check for window-specific built-in commands
        if command_lower in self.WINDOW_COMMANDS:
            method_name = self.WINDOW_COMMANDS[command_lower]
            if method_name == "send_interrupt":
                window.send_interrupt()
                self.speak(f"Sent stop signal to {project_name}.")
            elif method_name == "read_output":
                self._read_window_output(project_name, window)
            elif method_name == "focus":
                window.focus()
            return

        # Check for custom commands from config
        for custom_cmd, action in self.config.commands.items():
            if command_lower == custom_cmd.lower():
                send_text = action.get("send", "")
                if send_text:
                    window.send_command(send_text)
                    self.speak(f"Running {custom_cmd} in {project_name}.")
                return

        # Otherwise, send as a regular command to Claude
        window.send_command(command)
        self.speak(f"Sent to {project_name}.")

    def _read_window_output(self, project_name: str, window: KittyWindow) -> None:
        """Read and speak the window's current output."""
        output = window.get_text()
        summary = self.summarizer.summarize(output)
        self.speak(f"{project_name}: {summary.text}")

    def _monitor_outputs(self) -> None:
        """Background thread to monitor window outputs for completion."""
        while self._running:
            for name, window in self.kitty.windows.items():
                try:
                    current_output = window.get_text()

                    # Check if output has changed
                    last_output = self._last_outputs.get(name, "")
                    if current_output != last_output:
                        self._last_outputs[name] = current_output

                        # Check if Claude finished (prompt visible)
                        if self._is_claude_ready(current_output) and not self._is_claude_ready(last_output):
                            # Claude just finished
                            self._announce_completion(name, current_output, last_output)

                except Exception as e:
                    pass  # Ignore monitoring errors

            time.sleep(1)  # Check every second

    def _is_claude_ready(self, output: str) -> bool:
        """Check if Claude Code prompt is visible (ready for input)."""
        lines = output.strip().split("\n")
        if not lines:
            return False

        last_line = lines[-1].strip()
        # Claude Code shows "> " prompt when ready
        return last_line.endswith(">") or "> " in last_line

    def _announce_completion(self, project_name: str, current_output: str, last_output: str) -> None:
        """Announce when Claude completes a task."""
        if not self.config.summary.announce_completion:
            return

        # Get just the new output
        new_output = current_output
        if last_output and last_output in current_output:
            idx = current_output.find(last_output)
            if idx >= 0:
                new_output = current_output[idx + len(last_output):]

        summary = self.summarizer.summarize(new_output)

        # Only announce if there's meaningful content
        if summary.raw_length > 50 or summary.has_error or summary.has_question:
            self.speak(f"{project_name}: {summary.text}")

    def speak(self, text: str) -> None:
        """Speak text if not muted."""
        if not self._muted:
            self.voice_output.speak(text)

    # Global command implementations
    def get_all_status(self) -> None:
        """Report status of all windows."""
        status_parts = []
        for name, window in self.kitty.windows.items():
            state = "busy" if window.is_busy() else "ready"
            status_parts.append(f"{name} is {state}")

        self.speak(". ".join(status_parts))

    def toggle_mute(self) -> None:
        """Toggle voice output mute."""
        self._muted = not self._muted
        # Always speak this even if muting
        self.voice_output.speak("Muted." if self._muted else "Unmuted.")

    def increase_volume(self) -> None:
        """Increase TTS volume."""
        self.config.voice.volume = min(1.0, self.config.voice.volume + 0.1)
        self.speak("Volume increased.")

    def decrease_volume(self) -> None:
        """Decrease TTS volume."""
        self.config.voice.volume = max(0.1, self.config.voice.volume - 0.1)
        self.speak("Volume decreased.")

    def stop_all(self) -> None:
        """Send interrupt to all windows."""
        for window in self.kitty.windows.values():
            window.send_interrupt()
        self.speak("Stopped all sessions.")

    def shutdown(self) -> None:
        """Shutdown the voice controller."""
        self._running = False

    def speak_help(self) -> None:
        """Speak help information."""
        self.speak(
            "Say a project name followed by your command. "
            "For example: frontend, add a login button. "
            "Say status to check all projects. "
            "Say mute or unmute to toggle voice output. "
            "Say shutdown to exit."
        )
