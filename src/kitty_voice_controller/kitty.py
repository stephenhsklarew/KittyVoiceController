"""Kitty terminal integration via remote control."""

import json
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from .config import Config, LayoutConfig, ProjectConfig


@dataclass
class KittyWindow:
    """Represents a Kitty OS window."""

    title: str
    pid: int | None = None

    def send_text(self, text: str) -> bool:
        """Send text to this window."""
        try:
            subprocess.run(
                ["kitty", "@", "send-text", "--match", f"title:^{self.title}$", text],
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError:
            return False

    def send_command(self, command: str) -> bool:
        """Send a command (text + newline) to this window."""
        return self.send_text(command + "\n")

    def send_interrupt(self) -> bool:
        """Send Ctrl+C to this window."""
        return self.send_text("\x03")

    def get_text(self, extent: str = "screen") -> str:
        """Get text content from this window.

        Args:
            extent: 'screen', 'all', 'selection', or 'first_cmd_output_on_screen'
        """
        try:
            result = subprocess.run(
                [
                    "kitty", "@", "get-text",
                    "--match", f"title:^{self.title}$",
                    "--extent", extent,
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            return result.stdout
        except subprocess.CalledProcessError:
            return ""

    def focus(self) -> bool:
        """Bring this window to focus."""
        try:
            subprocess.run(
                ["kitty", "@", "focus-window", "--match", f"title:^{self.title}$"],
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError:
            return False

    def is_busy(self) -> bool:
        """Check if the window appears to be busy (no prompt visible)."""
        text = self.get_text()
        lines = text.strip().split("\n")
        if not lines:
            return False

        last_line = lines[-1].strip()
        # Claude Code shows a prompt like "> " when ready
        # This is a heuristic - adjust based on actual behavior
        return not (last_line.endswith(">") or last_line.endswith("$"))


class KittyController:
    """Controls Kitty terminal windows."""

    def __init__(self, config: Config):
        self.config = config
        self.windows: dict[str, KittyWindow] = {}

    @staticmethod
    def is_kitty_running() -> bool:
        """Check if Kitty is running."""
        try:
            result = subprocess.run(
                ["pgrep", "-x", "kitty"],
                capture_output=True,
            )
            return result.returncode == 0
        except Exception:
            return False

    @staticmethod
    def is_remote_control_enabled() -> bool:
        """Check if Kitty remote control is working."""
        try:
            result = subprocess.run(
                ["kitty", "@", "ls"],
                capture_output=True,
                timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False

    def launch_window(
        self,
        project: ProjectConfig,
        layout: LayoutConfig,
        position: tuple[int, int] | None = None,
    ) -> KittyWindow | None:
        """Launch a new Kitty OS window for a project."""
        title = f"claude-{project.name}"

        cmd = [
            "kitty",
            "--title", title,
            "--directory", str(project.directory),
        ]

        # Add geometry if position specified
        if position:
            x, y = position
            cmd.extend(["--override", f"initial_window_width={layout.window_width}"])
            cmd.extend(["--override", f"initial_window_height={layout.window_height}"])

        # Add the command to run
        cmd.extend(["-e", "bash", "-c", f"{project.command}; exec bash"])

        try:
            process = subprocess.Popen(
                cmd,
                start_new_session=True,
            )
            window = KittyWindow(title=title, pid=process.pid)
            self.windows[project.name] = window

            # Give window time to start
            time.sleep(0.5)
            return window

        except Exception as e:
            print(f"Failed to launch window for {project.name}: {e}")
            return None

    def launch_all_projects(self) -> dict[str, KittyWindow]:
        """Launch windows for all configured projects."""
        positions = self._calculate_positions()

        for i, (name, project) in enumerate(self.config.projects.items()):
            pos = positions[i] if i < len(positions) else None
            window = self.launch_window(project, self.config.layout, pos)
            if window:
                self.windows[name] = window
                # Stagger launches slightly
                time.sleep(0.3)

        return self.windows

    def launch_projects(self, project_names: list[str]) -> dict[str, KittyWindow]:
        """Launch windows for specific projects."""
        positions = self._calculate_positions()
        launched = {}

        for i, name in enumerate(project_names):
            if name not in self.config.projects:
                print(f"Project '{name}' not found in config")
                continue

            project = self.config.projects[name]
            pos = positions[i] if i < len(positions) else None
            window = self.launch_window(project, self.config.layout, pos)
            if window:
                self.windows[name] = window
                launched[name] = window
                time.sleep(0.3)

        return launched

    def _calculate_positions(self) -> list[tuple[int, int]]:
        """Calculate window positions based on layout arrangement."""
        layout = self.config.layout
        num_projects = len(self.config.projects)

        # Get screen dimensions (approximate for macOS)
        try:
            result = subprocess.run(
                ["system_profiler", "SPDisplaysDataType", "-json"],
                capture_output=True,
                text=True,
            )
            data = json.loads(result.stdout)
            displays = data.get("SPDisplaysDataType", [{}])[0]
            resolution = displays.get("spdisplays_ndrvs", [{}])[0].get("_spdisplays_resolution", "1920x1080")
            screen_width, screen_height = map(int, resolution.split(" ")[0].split("x"))
        except Exception:
            screen_width, screen_height = 1920, 1080

        positions = []
        w, h = layout.window_width, layout.window_height

        if layout.arrangement == "horizontal":
            for i in range(num_projects):
                positions.append((i * w, 0))

        elif layout.arrangement == "vertical":
            for i in range(num_projects):
                positions.append((0, i * h))

        elif layout.arrangement == "grid":
            cols = 2 if num_projects > 1 else 1
            for i in range(num_projects):
                col = i % cols
                row = i // cols
                positions.append((col * w, row * h))

        return positions

    def get_window(self, project_name: str) -> KittyWindow | None:
        """Get window by project name."""
        return self.windows.get(project_name)

    def get_window_by_voice(self, spoken_name: str) -> KittyWindow | None:
        """Get window by spoken name or alias."""
        project = self.config.find_project_by_voice(spoken_name)
        if project:
            return self.windows.get(project.name)
        return None

    def send_to_project(self, project_name: str, text: str) -> bool:
        """Send text to a project's window."""
        window = self.get_window(project_name)
        if window:
            return window.send_command(text)
        return False

    def get_all_status(self) -> dict[str, dict]:
        """Get status of all windows."""
        status = {}
        for name, window in self.windows.items():
            status[name] = {
                "title": window.title,
                "busy": window.is_busy(),
            }
        return status

    def close_all(self) -> None:
        """Send exit command to all windows."""
        for window in self.windows.values():
            window.send_command("/exit")
            time.sleep(0.2)

    def list_kitty_windows(self) -> list[dict]:
        """List all current Kitty windows."""
        try:
            result = subprocess.run(
                ["kitty", "@", "ls"],
                capture_output=True,
                text=True,
                check=True,
            )
            return json.loads(result.stdout)
        except Exception:
            return []


def check_kitty_setup() -> tuple[bool, str]:
    """Check if Kitty is properly set up for remote control.

    Returns:
        Tuple of (is_ready, message)
    """
    # Check if kitty is installed
    try:
        subprocess.run(["which", "kitty"], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        return False, "Kitty terminal is not installed. Install with: brew install --cask kitty"

    # Check if remote control is enabled
    controller = KittyController(Config())
    if not controller.is_remote_control_enabled():
        return False, (
            "Kitty remote control is not enabled.\n"
            "Add to ~/.config/kitty/kitty.conf:\n"
            "  allow_remote_control yes\n"
            "  listen_on unix:/tmp/kitty\n"
            "Then restart Kitty."
        )

    return True, "Kitty is ready for voice control"
