# Installation

## Pre-built Packages

Download from [GitHub Releases](https://github.com/danielrosehill/Voice-Notepad/releases).

On Linux, choose AppImage (universal), .deb (Debian/Ubuntu with `sudo apt install ./voice-notepad_*.deb`), or tarball. The package installs to `/opt/voice-notepad/` and creates a desktop entry.

On Windows, choose the installer (.exe) or portable .zip.

## From Source

### Step 1: Install System Dependencies

Install required system packages:

```bash
sudo apt install python3 python3-venv ffmpeg portaudio19-dev libc++1
```

**Package purposes:**
- `ffmpeg` - Audio format conversion and compression
- `portaudio19-dev` - Audio recording library headers
- `libc++1` - Required by TEN VAD for voice activity detection

### Step 2: Clone and Run

Clone and run:

```bash
git clone https://github.com/danielrosehill/Voice-Notepad.git
cd Voice-Notepad
./run.sh
```

The script creates a virtual environment in `app/.venv/`, installs Python dependencies, and launches the application.

For manual setup:

```bash
cd app
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m src.main
```

## Building Packages

To build your own Debian package:

```bash
sudo apt install dpkg fakeroot
./build.sh --deb
./build.sh --install
```

## Troubleshooting

If PyAudio fails to install, ensure PortAudio headers are available:

```bash
sudo apt install portaudio19-dev
```

If you encounter audio problems:

```bash
pactl info           # Check PipeWire/PulseAudio status
pactl list sources short  # List input devices
```
