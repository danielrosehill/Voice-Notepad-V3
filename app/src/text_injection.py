"""Text injection module for Wayland using ydotool.

This module provides text injection (simulating Ctrl+V paste) on Wayland
using ydotool, which works reliably with the ydotoold daemon.

Requirements:
- ydotool installed and ydotoold daemon running
- For best results: systemctl --user enable --now ydotool
"""

import subprocess
import time
from typing import Optional


def _check_ydotool_available() -> bool:
    """Check if ydotool is available."""
    try:
        result = subprocess.run(
            ["which", "ydotool"],
            capture_output=True,
            timeout=2
        )
        return result.returncode == 0
    except Exception:
        return False


_ydotool_available: Optional[bool] = None


def is_available() -> bool:
    """Check if text injection is available on this system."""
    global _ydotool_available
    if _ydotool_available is None:
        _ydotool_available = _check_ydotool_available()
    return _ydotool_available


def _get_ydotool_socket() -> Optional[str]:
    """Find the ydotool socket path."""
    import os
    from pathlib import Path

    # Check common socket locations
    candidates = [
        os.environ.get('YDOTOOL_SOCKET'),
        '/tmp/.ydotool_socket',
        f'/run/user/{os.getuid()}/.ydotool_socket',
        str(Path.home() / '.ydotool_socket'),
    ]

    for path in candidates:
        if path and Path(path).exists():
            return path
    return None


def paste_clipboard(delay_before: float = 0.1) -> bool:
    """Paste clipboard contents using ydotool.

    Args:
        delay_before: Delay before sending paste (for clipboard to be ready)

    Returns:
        True if paste was sent successfully, False otherwise
    """
    import os

    if not is_available():
        print("Warning: ydotool not available for text injection.")
        return False

    try:
        # Wait for clipboard to be ready
        time.sleep(delay_before)

        # Find and set the ydotool socket
        socket_path = _get_ydotool_socket()
        env = os.environ.copy()
        if socket_path:
            env['YDOTOOL_SOCKET'] = socket_path

        # Use ydotool to send Ctrl+V
        result = subprocess.run(
            ["ydotool", "key", "ctrl+v"],
            check=True,
            capture_output=True,
            timeout=2,
            env=env
        )
        return True
    except FileNotFoundError:
        print("Warning: ydotool not found. Install with: sudo apt install ydotool")
        return False
    except subprocess.TimeoutExpired:
        print("Warning: ydotool paste timed out")
        return False
    except subprocess.CalledProcessError as ex:
        print(f"Warning: ydotool paste failed: {ex}")
        return False
    except Exception as ex:
        print(f"Warning: Text injection failed: {ex}")
        return False


# Alias for backward compatibility
paste_clipboard_with_fallback = paste_clipboard
