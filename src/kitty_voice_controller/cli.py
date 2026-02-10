"""Command-line interface for Kitty Voice Controller."""

import argparse
import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table

from .config import CONFIG_FILE, Config, init_config, ensure_config_exists
from .controller import VoiceController
from .kitty import check_kitty_setup
from .voice_output import VoiceOutputHandler


console = Console()


def cmd_start(args) -> int:
    """Start the voice controller."""
    config = ensure_config_exists()

    if not config.projects:
        console.print("[yellow]No projects configured.[/yellow]")
        console.print(f"Run 'claude-voice init' or edit {CONFIG_FILE}")
        return 1

    # Check Kitty setup
    ready, message = check_kitty_setup()
    if not ready:
        console.print(f"[red]Setup issue:[/red] {message}")
        return 1

    # Determine which projects to launch
    project_names = args.projects if args.projects else None

    # Validate project names
    if project_names:
        for name in project_names:
            if name not in config.projects:
                console.print(f"[red]Unknown project:[/red] {name}")
                console.print(f"Available: {', '.join(config.projects.keys())}")
                return 1

    controller = VoiceController(config)
    controller.run(project_names)
    return 0


def cmd_init(args) -> int:
    """Initialize configuration."""
    if CONFIG_FILE.exists() and not args.force:
        console.print(f"[yellow]Config already exists:[/yellow] {CONFIG_FILE}")
        console.print("Use --force to overwrite")
        return 1

    init_config()
    console.print(f"[green]Created config:[/green] {CONFIG_FILE}")
    console.print("\nEdit this file to add your projects, then run:")
    console.print("  claude-voice start")
    return 0


def cmd_add(args) -> int:
    """Add a project."""
    config = ensure_config_exists()

    directory = Path(args.directory).expanduser().resolve()
    if not directory.exists():
        console.print(f"[red]Directory not found:[/red] {directory}")
        return 1

    config.add_project(
        name=args.name,
        directory=directory,
        command=args.command,
        aliases=args.alias or [],
    )
    config.save()

    console.print(f"[green]Added project:[/green] {args.name}")
    console.print(f"  Directory: {directory}")
    console.print(f"  Command: {args.command}")
    if args.alias:
        console.print(f"  Aliases: {', '.join(args.alias)}")
    return 0


def cmd_remove(args) -> int:
    """Remove a project."""
    config = ensure_config_exists()

    if config.remove_project(args.name):
        config.save()
        console.print(f"[green]Removed project:[/green] {args.name}")
        return 0
    else:
        console.print(f"[red]Project not found:[/red] {args.name}")
        return 1


def cmd_list(args) -> int:
    """List configured projects."""
    config = ensure_config_exists()

    if not config.projects:
        console.print("[yellow]No projects configured.[/yellow]")
        console.print(f"Run 'claude-voice add <name> <directory>' to add one")
        return 0

    table = Table(title="Configured Projects")
    table.add_column("Name", style="cyan")
    table.add_column("Directory", style="green")
    table.add_column("Command")
    table.add_column("Aliases", style="dim")

    for name, project in config.projects.items():
        table.add_row(
            name,
            str(project.directory),
            project.command,
            ", ".join(project.voice_alias) if project.voice_alias else "-",
        )

    console.print(table)
    return 0


def cmd_voices(args) -> int:
    """List available macOS voices."""
    voices = VoiceOutputHandler.list_voices()

    if not voices:
        console.print("[yellow]Could not list voices[/yellow]")
        return 1

    table = Table(title="Available Voices")
    table.add_column("Name", style="cyan")
    table.add_column("Language")

    for voice in voices:
        table.add_row(voice["name"], voice.get("language", ""))

    console.print(table)
    console.print("\nSet your preferred voice in config:")
    console.print(f"  {CONFIG_FILE}")
    return 0


def cmd_check(args) -> int:
    """Check system setup."""
    console.print("[bold]Checking system setup...[/bold]\n")

    # Check Kitty
    ready, message = check_kitty_setup()
    if ready:
        console.print("[green]✓[/green] Kitty terminal: Ready")
    else:
        console.print(f"[red]✗[/red] Kitty terminal: {message}")

    # Check config
    if CONFIG_FILE.exists():
        config = Config.load()
        console.print(f"[green]✓[/green] Config file: {CONFIG_FILE}")
        console.print(f"  Projects: {len(config.projects)}")
        console.print(f"  Hotkey: {config.voice.hotkey}")
        console.print(f"  Whisper model: {config.voice.whisper_model}")
    else:
        console.print(f"[yellow]![/yellow] No config file (run 'claude-voice init')")

    # Check Python dependencies
    console.print("\n[bold]Dependencies:[/bold]")
    deps = [
        ("whisper", "openai-whisper"),
        ("pyaudio", "pyaudio"),
        ("pynput", "pynput"),
        ("yaml", "PyYAML"),
        ("rich", "rich"),
    ]

    for module, package in deps:
        try:
            __import__(module)
            console.print(f"  [green]✓[/green] {package}")
        except ImportError:
            console.print(f"  [red]✗[/red] {package} (pip install {package})")

    return 0


def cmd_test_voice(args) -> int:
    """Test voice output."""
    config = ensure_config_exists()
    voice = VoiceOutputHandler(config.voice)

    text = args.text or "Hello, this is a test of the voice output system."
    console.print(f"Speaking with voice '{config.voice.tts_voice}'...")
    voice.speak(text)
    return 0


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        prog="claude-voice",
        description="Voice-controlled interface for Claude Code in Kitty terminal",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # start
    start_parser = subparsers.add_parser("start", help="Start voice control")
    start_parser.add_argument(
        "projects",
        nargs="*",
        help="Specific projects to launch (default: all)",
    )
    start_parser.set_defaults(func=cmd_start)

    # init
    init_parser = subparsers.add_parser("init", help="Initialize configuration")
    init_parser.add_argument("--force", action="store_true", help="Overwrite existing config")
    init_parser.set_defaults(func=cmd_init)

    # add
    add_parser = subparsers.add_parser("add", help="Add a project")
    add_parser.add_argument("name", help="Project name")
    add_parser.add_argument("directory", help="Project directory")
    add_parser.add_argument("--command", "-c", default="claude", help="Command to run (default: claude)")
    add_parser.add_argument("--alias", "-a", action="append", help="Voice alias (can specify multiple)")
    add_parser.set_defaults(func=cmd_add)

    # remove
    remove_parser = subparsers.add_parser("remove", help="Remove a project")
    remove_parser.add_argument("name", help="Project name")
    remove_parser.set_defaults(func=cmd_remove)

    # list
    list_parser = subparsers.add_parser("list", help="List configured projects")
    list_parser.set_defaults(func=cmd_list)

    # voices
    voices_parser = subparsers.add_parser("voices", help="List available macOS voices")
    voices_parser.set_defaults(func=cmd_voices)

    # check
    check_parser = subparsers.add_parser("check", help="Check system setup")
    check_parser.set_defaults(func=cmd_check)

    # test-voice
    test_parser = subparsers.add_parser("test-voice", help="Test voice output")
    test_parser.add_argument("text", nargs="?", help="Text to speak")
    test_parser.set_defaults(func=cmd_test_voice)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
