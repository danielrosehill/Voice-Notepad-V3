"""Text injection module for Wayland using python-evdev uinput.

This module provides reliable text injection (simulating Ctrl+V paste) on Wayland
by creating a virtual keyboard device via the Linux uinput subsystem.

This approach is more reliable than ydotool because:
1. Direct uinput access without needing a daemon
2. Works at the kernel input level, bypassing Wayland's security restrictions
3. Precise timing control

Requirements:
- python-evdev package
- User must be in the 'input' group (for /dev/uinput access)
"""

import threading
import time
from typing import Optional

# Try to import evdev, but don't fail if not available
try:
    from evdev import UInput, ecodes as e
    EVDEV_AVAILABLE = True
except ImportError:
    EVDEV_AVAILABLE = False
    UInput = None
    e = None


class TextInjector:
    """Virtual keyboard for injecting text via uinput.

    This class creates a virtual keyboard device that can send key events
    directly to the Linux input subsystem. This works on Wayland because
    it operates at the kernel level, not the display server level.
    """

    def __init__(self):
        self._ui: Optional[UInput] = None
        self._available = EVDEV_AVAILABLE

    @property
    def available(self) -> bool:
        """Check if text injection is available."""
        return self._available

    def _ensure_device(self) -> bool:
        """Ensure the virtual keyboard device is created.

        Returns True if device is ready, False otherwise.
        """
        if not self._available:
            return False

        if self._ui is not None:
            return True

        try:
            # Create virtual keyboard with common keys
            # We need KEY_LEFTCTRL and KEY_V for Ctrl+V paste
            capabilities = {
                e.EV_KEY: [
                    e.KEY_LEFTCTRL, e.KEY_RIGHTCTRL,
                    e.KEY_LEFTSHIFT, e.KEY_RIGHTSHIFT,
                    e.KEY_LEFTALT, e.KEY_RIGHTALT,
                    e.KEY_V, e.KEY_C, e.KEY_X, e.KEY_A, e.KEY_Z,
                    e.KEY_ENTER, e.KEY_TAB, e.KEY_SPACE,
                    e.KEY_BACKSPACE, e.KEY_DELETE,
                    e.KEY_UP, e.KEY_DOWN, e.KEY_LEFT, e.KEY_RIGHT,
                    e.KEY_HOME, e.KEY_END,
                ]
            }
            self._ui = UInput(capabilities, name='voice-notepad-keyboard')
            # Give the system time to recognize the new device
            time.sleep(0.1)
            return True
        except PermissionError:
            print("Warning: No permission to access /dev/uinput. "
                  "Add user to 'input' group: sudo usermod -aG input $USER")
            self._available = False
            return False
        except Exception as ex:
            print(f"Warning: Failed to create virtual keyboard: {ex}")
            self._available = False
            return False

    def _press_key(self, key_code: int):
        """Press a key (key down event)."""
        if self._ui:
            self._ui.write(e.EV_KEY, key_code, 1)
            self._ui.syn()

    def _release_key(self, key_code: int):
        """Release a key (key up event)."""
        if self._ui:
            self._ui.write(e.EV_KEY, key_code, 0)
            self._ui.syn()

    def _tap_key(self, key_code: int, delay: float = 0.01):
        """Tap a key (press and release)."""
        self._press_key(key_code)
        time.sleep(delay)
        self._release_key(key_code)

    def send_paste(self, delay_before: float = 0.1, delay_between: float = 0.02) -> bool:
        """Send Ctrl+V paste command.

        Args:
            delay_before: Delay before sending the paste (to ensure clipboard is ready)
            delay_between: Delay between key events

        Returns:
            True if paste was sent successfully, False otherwise
        """
        if not self._ensure_device():
            return False

        try:
            # Small delay to ensure clipboard is ready
            time.sleep(delay_before)

            # Press Ctrl
            self._press_key(e.KEY_LEFTCTRL)
            time.sleep(delay_between)

            # Press V while holding Ctrl
            self._press_key(e.KEY_V)
            time.sleep(delay_between)

            # Release V
            self._release_key(e.KEY_V)
            time.sleep(delay_between)

            # Release Ctrl
            self._release_key(e.KEY_LEFTCTRL)

            return True
        except Exception as ex:
            print(f"Warning: Failed to send paste: {ex}")
            return False

    def send_copy(self, delay_between: float = 0.02) -> bool:
        """Send Ctrl+C copy command.

        Returns:
            True if copy was sent successfully, False otherwise
        """
        if not self._ensure_device():
            return False

        try:
            self._press_key(e.KEY_LEFTCTRL)
            time.sleep(delay_between)
            self._press_key(e.KEY_C)
            time.sleep(delay_between)
            self._release_key(e.KEY_C)
            time.sleep(delay_between)
            self._release_key(e.KEY_LEFTCTRL)
            return True
        except Exception as ex:
            print(f"Warning: Failed to send copy: {ex}")
            return False

    def send_key_combo(self, *keys: int, delay_between: float = 0.02) -> bool:
        """Send an arbitrary key combination.

        Args:
            *keys: Key codes to press (in order, all held together)
            delay_between: Delay between key events

        Returns:
            True if combo was sent successfully, False otherwise
        """
        if not self._ensure_device():
            return False

        try:
            # Press all keys in order
            for key in keys:
                self._press_key(key)
                time.sleep(delay_between)

            # Release all keys in reverse order
            for key in reversed(keys):
                self._release_key(key)
                time.sleep(delay_between)

            return True
        except Exception as ex:
            print(f"Warning: Failed to send key combo: {ex}")
            return False

    def close(self):
        """Close the virtual keyboard device."""
        if self._ui:
            try:
                self._ui.close()
            except Exception:
                pass
            self._ui = None

    def __del__(self):
        self.close()


# Singleton instance for the application
_injector: Optional[TextInjector] = None
_injector_lock = threading.Lock()


def get_injector() -> TextInjector:
    """Get the singleton TextInjector instance (thread-safe)."""
    global _injector
    if _injector is None:
        with _injector_lock:
            # Double-check pattern for thread safety
            if _injector is None:
                _injector = TextInjector()
    return _injector


def paste_clipboard(delay_before: float = 0.1) -> bool:
    """Convenience function to paste clipboard contents.

    Args:
        delay_before: Delay before sending paste (for clipboard to be ready)

    Returns:
        True if paste was sent successfully, False otherwise
    """
    return get_injector().send_paste(delay_before=delay_before)


def is_available() -> bool:
    """Check if text injection is available on this system."""
    return get_injector().available


# Fallback to ydotool if evdev is not available
def paste_clipboard_with_fallback(delay_before: float = 0.1) -> bool:
    """Paste clipboard with fallback to ydotool if evdev unavailable.

    This function first tries python-evdev, then falls back to ydotool.

    Returns:
        True if paste was sent successfully, False otherwise
    """
    # Try evdev first (more reliable)
    if is_available():
        return paste_clipboard(delay_before)

    # Fallback to ydotool
    import subprocess
    try:
        time.sleep(delay_before)
        subprocess.run(
            ["ydotool", "key", "--delay", "50", "ctrl+v"],
            check=True,
            capture_output=True,
            timeout=2
        )
        return True
    except FileNotFoundError:
        print("Warning: Neither python-evdev nor ydotool available for text injection.")
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