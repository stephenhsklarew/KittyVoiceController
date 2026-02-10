"""Configuration management for Kitty Voice Controller."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


CONFIG_DIR = Path.home() / ".config" / "claude-voice"
CONFIG_FILE = CONFIG_DIR / "config.yaml"
DEFAULT_CONFIG_TEMPLATE = """# Claude Voice Controller Configuration
# ─────────────────────────────────────────────

# Projects - each becomes a labeled Kitty window
projects:
  scratch:
    directory: ~/scratch
    command: claude
    voice_alias:
      - "scratchpad"
      - "temp"

# Voice Settings
voice:
  hotkey: ctrl+shift+v            # push-to-talk key
  whisper_model: base             # tiny, base, small, medium, large
  language: en

  tts_voice: Samantha             # macOS voice (run `say -v ?` to list)
  tts_rate: 200                   # words per minute
  volume: 0.8                     # 0.0 to 1.0

  sound_listen_start: true
  sound_listen_stop: true
  sound_error: true

# Summarization
summary:
  max_spoken_length: 150          # max words to speak
  strategy: smart                 # smart, first_last, full
  announce_errors: true
  announce_questions: true
  announce_completion: true

# Layout
layout:
  arrangement: grid               # grid, horizontal, vertical
  window_width: 900
  window_height: 700

# Custom voice commands
commands: {}
"""


@dataclass
class ProjectConfig:
    """Configuration for a single project."""

    name: str
    directory: Path
    command: str = "claude"
    voice_alias: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, name: str, data: dict[str, Any]) -> "ProjectConfig":
        directory = Path(data.get("directory", "~/")).expanduser()
        return cls(
            name=name,
            directory=directory,
            command=data.get("command", "claude"),
            voice_alias=data.get("voice_alias", []),
        )

    def get_all_names(self) -> list[str]:
        """Get all names this project responds to (name + aliases)."""
        return [self.name.lower()] + [a.lower() for a in self.voice_alias]


@dataclass
class VoiceConfig:
    """Voice input/output settings."""

    hotkey: str = "ctrl+shift+v"
    whisper_model: str = "base"
    language: str = "en"
    tts_voice: str = "Samantha"
    tts_rate: int = 200
    volume: float = 0.8
    sound_listen_start: bool = True
    sound_listen_stop: bool = True
    sound_error: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VoiceConfig":
        return cls(
            hotkey=data.get("hotkey", "ctrl+shift+v"),
            whisper_model=data.get("whisper_model", "base"),
            language=data.get("language", "en"),
            tts_voice=data.get("tts_voice", "Samantha"),
            tts_rate=data.get("tts_rate", 200),
            volume=data.get("volume", 0.8),
            sound_listen_start=data.get("sound_listen_start", True),
            sound_listen_stop=data.get("sound_listen_stop", True),
            sound_error=data.get("sound_error", True),
        )


@dataclass
class SummaryConfig:
    """Summarization settings."""

    max_spoken_length: int = 150
    strategy: str = "smart"
    announce_errors: bool = True
    announce_questions: bool = True
    announce_completion: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SummaryConfig":
        return cls(
            max_spoken_length=data.get("max_spoken_length", 150),
            strategy=data.get("strategy", "smart"),
            announce_errors=data.get("announce_errors", True),
            announce_questions=data.get("announce_questions", True),
            announce_completion=data.get("announce_completion", True),
        )


@dataclass
class LayoutConfig:
    """Window layout settings."""

    arrangement: str = "grid"
    window_width: int = 900
    window_height: int = 700

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LayoutConfig":
        return cls(
            arrangement=data.get("arrangement", "grid"),
            window_width=data.get("window_width", 900),
            window_height=data.get("window_height", 700),
        )


@dataclass
class Config:
    """Main configuration container."""

    projects: dict[str, ProjectConfig] = field(default_factory=dict)
    voice: VoiceConfig = field(default_factory=VoiceConfig)
    summary: SummaryConfig = field(default_factory=SummaryConfig)
    layout: LayoutConfig = field(default_factory=LayoutConfig)
    commands: dict[str, dict[str, str]] = field(default_factory=dict)

    @classmethod
    def load(cls, config_path: Path | None = None) -> "Config":
        """Load configuration from file."""
        path = config_path or CONFIG_FILE

        if not path.exists():
            return cls()

        with open(path) as f:
            data = yaml.safe_load(f) or {}

        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Config":
        projects = {}
        for name, proj_data in data.get("projects", {}).items():
            projects[name] = ProjectConfig.from_dict(name, proj_data)

        return cls(
            projects=projects,
            voice=VoiceConfig.from_dict(data.get("voice", {})),
            summary=SummaryConfig.from_dict(data.get("summary", {})),
            layout=LayoutConfig.from_dict(data.get("layout", {})),
            commands=data.get("commands", {}),
        )

    def save(self, config_path: Path | None = None) -> None:
        """Save configuration to file."""
        path = config_path or CONFIG_FILE
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "projects": {
                name: {
                    "directory": str(proj.directory),
                    "command": proj.command,
                    "voice_alias": proj.voice_alias,
                }
                for name, proj in self.projects.items()
            },
            "voice": {
                "hotkey": self.voice.hotkey,
                "whisper_model": self.voice.whisper_model,
                "language": self.voice.language,
                "tts_voice": self.voice.tts_voice,
                "tts_rate": self.voice.tts_rate,
                "volume": self.voice.volume,
                "sound_listen_start": self.voice.sound_listen_start,
                "sound_listen_stop": self.voice.sound_listen_stop,
                "sound_error": self.voice.sound_error,
            },
            "summary": {
                "max_spoken_length": self.summary.max_spoken_length,
                "strategy": self.summary.strategy,
                "announce_errors": self.summary.announce_errors,
                "announce_questions": self.summary.announce_questions,
                "announce_completion": self.summary.announce_completion,
            },
            "layout": {
                "arrangement": self.layout.arrangement,
                "window_width": self.layout.window_width,
                "window_height": self.layout.window_height,
            },
            "commands": self.commands,
        }

        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    def find_project_by_voice(self, spoken_name: str) -> ProjectConfig | None:
        """Find a project by its name or voice alias."""
        spoken_lower = spoken_name.lower().strip()

        for project in self.projects.values():
            if spoken_lower in project.get_all_names():
                return project

        return None

    def add_project(
        self,
        name: str,
        directory: Path,
        command: str = "claude",
        aliases: list[str] | None = None,
    ) -> None:
        """Add a new project."""
        self.projects[name] = ProjectConfig(
            name=name,
            directory=directory,
            command=command,
            voice_alias=aliases or [],
        )

    def remove_project(self, name: str) -> bool:
        """Remove a project by name."""
        if name in self.projects:
            del self.projects[name]
            return True
        return False


def init_config() -> None:
    """Initialize config directory and default config file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    if not CONFIG_FILE.exists():
        with open(CONFIG_FILE, "w") as f:
            f.write(DEFAULT_CONFIG_TEMPLATE)


def ensure_config_exists() -> Config:
    """Ensure config exists and return it."""
    if not CONFIG_FILE.exists():
        init_config()
    return Config.load()
