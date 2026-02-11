#!/bin/bash
# Installation script for Kitty Voice Controller

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="$HOME/.config/claude-voice"
VENV_DIR="$SCRIPT_DIR/.venv"

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
KITTY_PATH=""
if command -v kitty &> /dev/null; then
    KITTY_PATH="$(command -v kitty)"
elif [ -x "/Applications/kitty.app/Contents/MacOS/kitty" ]; then
    KITTY_PATH="/Applications/kitty.app/Contents/MacOS/kitty"
    echo "  Found Kitty in Applications, adding to PATH..."
    export PATH="/Applications/kitty.app/Contents/MacOS:$PATH"

    # Add to shell profile if not already there
    SHELL_RC="$HOME/.zshrc"
    [ -f "$HOME/.bashrc" ] && [ ! -f "$HOME/.zshrc" ] && SHELL_RC="$HOME/.bashrc"

    if ! grep -q "kitty.app/Contents/MacOS" "$SHELL_RC" 2>/dev/null; then
        echo '' >> "$SHELL_RC"
        echo '# Kitty terminal CLI' >> "$SHELL_RC"
        echo 'export PATH="/Applications/kitty.app/Contents/MacOS:$PATH"' >> "$SHELL_RC"
        echo "  Added Kitty to $SHELL_RC"
    fi
fi

if [ -z "$KITTY_PATH" ]; then
    echo "❌ Kitty terminal not found"
    echo "  Install with: brew install --cask kitty"
    exit 1
fi
echo "✓ Kitty terminal found: $KITTY_PATH"

# Check for portaudio (required for pyaudio)
echo "Checking for portaudio..."
if ! brew list portaudio &> /dev/null 2>&1; then
    echo "Installing portaudio..."
    brew install portaudio
fi
echo "✓ portaudio available"

# Create virtual environment
echo
echo "Creating virtual environment..."
if [ -d "$VENV_DIR" ]; then
    echo "  Removing existing venv..."
    rm -rf "$VENV_DIR"
fi
python3 -m venv "$VENV_DIR"
echo "✓ Virtual environment created"

# Install Python package in venv
echo
echo "Installing Python package (this may take a moment)..."
source "$VENV_DIR/bin/activate"
pip install --upgrade pip --quiet
pip install -e "$SCRIPT_DIR" --quiet
deactivate
echo "✓ Package installed"

# Create wrapper script
echo
echo "Creating command wrapper..."
WRAPPER_SCRIPT="$SCRIPT_DIR/claude-voice"
cat > "$WRAPPER_SCRIPT" << 'WRAPPER'
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/.venv/bin/activate"
python -m kitty_voice_controller.cli "$@"
WRAPPER
chmod +x "$WRAPPER_SCRIPT"

# Add to PATH via symlink or shell profile
BIN_DIR="$HOME/.local/bin"
mkdir -p "$BIN_DIR"
ln -sf "$WRAPPER_SCRIPT" "$BIN_DIR/claude-voice"

# Ensure ~/.local/bin is in PATH
SHELL_RC="$HOME/.zshrc"
[ -f "$HOME/.bashrc" ] && [ ! -f "$HOME/.zshrc" ] && SHELL_RC="$HOME/.bashrc"

if ! grep -q '\.local/bin' "$SHELL_RC" 2>/dev/null; then
    echo '' >> "$SHELL_RC"
    echo '# Local binaries' >> "$SHELL_RC"
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$SHELL_RC"
    echo "  Added ~/.local/bin to PATH in $SHELL_RC"
fi
export PATH="$HOME/.local/bin:$PATH"

echo "✓ Command 'claude-voice' installed"

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
source "$VENV_DIR/bin/activate"
python -c "import whisper; whisper.load_model('base')" 2>/dev/null || {
    echo "  Model will be downloaded on first run"
}
deactivate
echo "✓ Whisper model ready"

echo
echo "╔════════════════════════════════════════════╗"
echo "║         Installation Complete!            ║"
echo "╚════════════════════════════════════════════╝"
echo
echo "Next steps:"
echo "1. Restart your shell or run: source $SHELL_RC"
echo "2. Edit your projects in: $CONFIG_DIR/config.yaml"
echo "3. Restart Kitty terminal (if remote control was just added)"
echo "4. Run: claude-voice start"
echo
echo "Quick commands:"
echo "  claude-voice list       # Show configured projects"
echo "  claude-voice add NAME DIR  # Add a project"
echo "  claude-voice check      # Verify setup"
echo "  claude-voice start      # Start voice control"
echo
