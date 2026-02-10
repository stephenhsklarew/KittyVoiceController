# Kitty Voice Controller

Voice-controlled interface for [Claude Code](https://claude.ai/claude-code) in [Kitty terminal](https://sw.kovidgoyal.net/kitty/). Speak commands to multiple Claude sessions and hear summarized responses.

## Features

- **Push-to-talk voice input** using OpenAI's Whisper for accurate speech recognition
- **Text-to-speech feedback** via macOS `say` for hands-free operation
- **Multi-project support** - run separate Claude sessions for frontend, backend, etc.
- **Voice aliases** - say "frontend", "front", or "UI" to target the same window
- **Smart summarization** - long outputs are condensed to key points before speaking
- **Auto-announcements** - hear when Claude finishes, encounters errors, or asks questions
- **Custom voice commands** - define shortcuts like "run tests" → `/run npm test`

## Requirements

- macOS (uses native `say` command for TTS)
- Python 3.10+
- [Kitty terminal](https://sw.kovidgoyal.net/kitty/)
- [Claude Code CLI](https://claude.ai/claude-code)

## Installation

```bash
git clone https://github.com/stephenhsklarew/KittyVoiceController.git
cd KittyVoiceController
./install.sh
```

The installer will:
1. Check dependencies (Python, Kitty, portaudio)
2. Install the Python package
3. Create config at `~/.config/claude-voice/config.yaml`
4. Enable Kitty remote control
5. Pre-download the Whisper speech recognition model

## Quick Start

```bash
# Add your projects
claude-voice add frontend ~/code/myapp/frontend --alias "front" "UI"
claude-voice add backend ~/code/myapp/backend --alias "back" "API"

# Verify setup
claude-voice check

# Start voice control
claude-voice start
```

## Usage

### CLI Commands

| Command | Description |
|---------|-------------|
| `claude-voice start` | Launch all configured projects |
| `claude-voice start frontend backend` | Launch specific projects only |
| `claude-voice list` | Show configured projects |
| `claude-voice add NAME DIR` | Add a project |
| `claude-voice remove NAME` | Remove a project |
| `claude-voice voices` | List available macOS voices |
| `claude-voice check` | Verify system setup |
| `claude-voice test-voice "hello"` | Test text-to-speech |
| `claude-voice init` | Create default config file |

### Voice Commands

Once running, hold **Ctrl+Shift+V** (configurable) and speak:

#### Target a Project
- `"frontend: add a dark mode toggle"` - Send command to frontend session
- `"backend fix the authentication bug"` - Send to backend (colon is optional)
- `"API: show me the user routes"` - Use any configured alias

#### Window Control
- `"frontend stop"` - Send Ctrl+C to interrupt
- `"backend read"` - Read the current output aloud
- `"frontend focus"` - Bring window to foreground

#### Global Commands
- `"status"` - Hear which projects are busy or ready
- `"mute"` / `"unmute"` - Toggle voice output
- `"louder"` / `"softer"` - Adjust speech volume
- `"stop all"` - Send interrupt to all windows
- `"shutdown"` - Exit voice control
- `"help"` - Hear available commands

## Configuration

Edit `~/.config/claude-voice/config.yaml`:

```yaml
# Projects
projects:
  frontend:
    directory: ~/code/myapp/frontend
    command: claude
    voice_alias:
      - "front"
      - "UI"

  backend:
    directory: ~/code/myapp/backend
    command: claude
    voice_alias:
      - "back"
      - "API"

# Voice settings
voice:
  hotkey: ctrl+shift+v
  whisper_model: base        # tiny, base, small, medium, large
  tts_voice: Samantha        # Run 'claude-voice voices' to list
  tts_rate: 200              # Words per minute

# Summarization
summary:
  max_spoken_length: 150     # Max words to speak
  strategy: smart            # smart, first_last, full
  announce_errors: true
  announce_questions: true
  announce_completion: true

# Custom voice commands
commands:
  "run tests":
    send: "/run npm test"
  "commit changes":
    send: "/commit"
```

## How It Works

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  You speak      │────▶│  Whisper STT    │────▶│  Parse target   │
│  "frontend:     │     │  transcribes    │     │  + command      │
│   fix the bug"  │     │                 │     │                 │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                         │
                                                         ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  macOS 'say'    │◀────│  Summarize      │◀────│  kitty @        │
│  speaks summary │     │  output         │     │  send-text      │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

1. **Voice Input**: Hold hotkey, speak your command
2. **Transcription**: Whisper converts speech to text locally
3. **Parsing**: Extract target project and command
4. **Routing**: Send to correct Kitty window via remote control
5. **Monitoring**: Watch for Claude completion
6. **Summarization**: Condense output to key points
7. **Speech**: Announce result via macOS TTS

## Whisper Models

| Model | Size | Speed | Accuracy |
|-------|------|-------|----------|
| `tiny` | 39 MB | Fastest | Good for clear speech |
| `base` | 74 MB | Fast | **Recommended** |
| `small` | 244 MB | Medium | Better accuracy |
| `medium` | 769 MB | Slow | High accuracy |
| `large` | 1.5 GB | Slowest | Best accuracy |

Set in config: `voice.whisper_model: base`

## Kitty Setup

The installer configures this automatically, but if needed manually add to `~/.config/kitty/kitty.conf`:

```
allow_remote_control yes
listen_on unix:/tmp/kitty
```

Then restart Kitty.

## Troubleshooting

### "Kitty remote control not enabled"
1. Check `~/.config/kitty/kitty.conf` has the settings above
2. Restart Kitty terminal completely

### No audio input
1. Check System Settings → Privacy & Security → Microphone
2. Ensure terminal app has microphone permission
3. Run `claude-voice check` to verify pyaudio

### Speech not recognized well
- Try a larger Whisper model: `whisper_model: small`
- Speak clearly after the beep
- Reduce background noise

### Commands going to wrong window
- Check your voice aliases don't overlap
- Use more distinct project names
- Say the full project name if aliases conflict

## License

MIT

## Credits

Built with:
- [OpenAI Whisper](https://github.com/openai/whisper) for speech recognition
- [Kitty](https://sw.kovidgoyal.net/kitty/) terminal's remote control protocol
- [pynput](https://github.com/moses-palmer/pynput) for hotkey detection
- macOS `say` for text-to-speech
