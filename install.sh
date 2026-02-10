#!/bin/bash
# Installation script for Kitty Voice Controller

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="$HOME/.config/claude-voice"

echo "╔════════════════════════════════════════════╗"
echo "║   Kitty Voice Controller Installation     ║"
echo "╚════════════════════════════════════════════╝"
echo

# Check for Python 3.10+
echo "Checking Python version..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not found"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 10 ]); then
    echo "❌ Python 3.10+ is required (found $PYTHON_VERSION)"
    exit 1
fi
echo "✓ Python $PYTHON_VERSION"

# Check for Kitty
echo "Checking for Kitty terminal..."
if ! command -v kitty &> /dev/null; then
    echo "❌ Kitty terminal not found"
    echo "  Install with: brew install --cask kitty"
    exit 1
fi
echo "✓ Kitty terminal found"

# Check for portaudio (required for pyaudio)
echo "Checking for portaudio..."
if ! brew list portaudio &> /dev/null 2>&1; then
    echo "Installing portaudio..."
    brew install portaudio
fi
echo "✓ portaudio available"

# Install Python package
echo
echo "Installing Python package..."
cd "$SCRIPT_DIR"
pip3 install -e . --quiet

echo "✓ Package installed"

# Create config directory
echo
echo "Setting up configuration..."
mkdir -p "$CONFIG_DIR"

if [ ! -f "$CONFIG_DIR/config.yaml" ]; then
    cp "$SCRIPT_DIR/config.example.yaml" "$CONFIG_DIR/config.yaml"
    echo "✓ Created config at $CONFIG_DIR/config.yaml"
else
    echo "✓ Config already exists at $CONFIG_DIR/config.yaml"
fi

# Check Kitty remote control
echo
echo "Checking Kitty remote control..."
KITTY_CONF="$HOME/.config/kitty/kitty.conf"

if [ -f "$KITTY_CONF" ]; then
    if grep -q "allow_remote_control" "$KITTY_CONF"; then
        echo "✓ Remote control setting found in kitty.conf"
    else
        echo "⚠ Adding remote control to kitty.conf..."
        echo "" >> "$KITTY_CONF"
        echo "# Added by claude-voice installer" >> "$KITTY_CONF"
        echo "allow_remote_control yes" >> "$KITTY_CONF"
        echo "listen_on unix:/tmp/kitty" >> "$KITTY_CONF"
        echo "✓ Added remote control settings"
        echo "  Note: Restart Kitty for changes to take effect"
    fi
else
    mkdir -p "$HOME/.config/kitty"
    echo "# Kitty configuration" > "$KITTY_CONF"
    echo "allow_remote_control yes" >> "$KITTY_CONF"
    echo "listen_on unix:/tmp/kitty" >> "$KITTY_CONF"
    echo "✓ Created kitty.conf with remote control enabled"
fi

# Download Whisper model
echo
echo "Pre-downloading Whisper model (this may take a moment)..."
python3 -c "import whisper; whisper.load_model('base')" 2>/dev/null || {
    echo "  Model will be downloaded on first run"
}
echo "✓ Whisper model ready"

echo
echo "╔════════════════════════════════════════════╗"
echo "║         Installation Complete!            ║"
echo "╚════════════════════════════════════════════╝"
echo
echo "Next steps:"
echo "1. Edit your projects in: $CONFIG_DIR/config.yaml"
echo "2. Restart Kitty terminal (if remote control was just added)"
echo "3. Run: claude-voice start"
echo
echo "Quick commands:"
echo "  claude-voice list       # Show configured projects"
echo "  claude-voice add NAME DIR  # Add a project"
echo "  claude-voice check      # Verify setup"
echo "  claude-voice start      # Start voice control"
echo
