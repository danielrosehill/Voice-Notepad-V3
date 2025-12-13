# Installation

Voice Notepad can be installed either from a Debian package or run directly from source.

## System Requirements

- **OS**: Linux (tested on Ubuntu 24.04+)
- **Python**: 3.10+
- **Audio**: Working microphone and audio system
- **Dependencies**: ffmpeg, PortAudio

## Option 1: Debian Package (Recommended)

Download and install the latest `.deb` package:

```bash
# Install the package
sudo apt install ./voice-notepad_*.deb
```

The package installs to `/opt/voice-notepad/` and creates a desktop entry.

### Building from Source

To build your own Debian package:

```bash
# Install build dependencies
sudo apt install dpkg fakeroot

# Build the package
./build.sh

# Install
./install.sh
```

## Option 2: Run from Source

### Prerequisites

Install system dependencies:

```bash
# Ubuntu/Debian
sudo apt install python3 python3-venv ffmpeg portaudio19-dev
```

### Setup

```bash
# Clone the repository
git clone https://github.com/danielrosehill/Voice-Notepad.git
cd Voice-Notepad

# Run the app (creates venv automatically)
./run.sh
```

The `run.sh` script will:

1. Create a virtual environment in `app/.venv/` if needed
2. Install Python dependencies
3. Launch the application

### Manual Setup

If you prefer manual setup:

```bash
cd app

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run
python -m src.main
```

## API Keys

You'll need an API key for at least one provider. See [Configuration](configuration.md) for details.

## Troubleshooting

### Audio Issues

If you encounter audio problems:

```bash
# Check PipeWire/PulseAudio status
pactl info

# List available input devices
pactl list sources short
```

### Missing Dependencies

If PyAudio fails to install:

```bash
# Install PortAudio development headers
sudo apt install portaudio19-dev
```
