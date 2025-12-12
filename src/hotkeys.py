"""Global hotkey handling for Voice Notepad V3.

Uses pynput for cross-platform global hotkey support.
On Wayland, this works via XWayland compatibility layer.
"""

import threading
from typing import Callable, Dict, Optional
from pynput import keyboard


# Mapping of key names to pynput Key objects
# Includes F14-F20 (macro keys) which are recommended for avoiding conflicts
KEY_MAP = {
    # Function keys (standard)
    "f1": keyboard.Key.f1,
    "f2": keyboard.Key.f2,
    "f3": keyboard.Key.f3,
    "f4": keyboard.Key.f4,
    "f5": keyboard.Key.f5,
    "f6": keyboard.Key.f6,
    "f7": keyboard.Key.f7,
    "f8": keyboard.Key.f8,
    "f9": keyboard.Key.f9,
    "f10": keyboard.Key.f10,
    "f11": keyboard.Key.f11,
    "f12": keyboard.Key.f12,
    # Extended function keys (macro keys) - F13-F24
    "f13": keyboard.Key.f13,
    "f14": keyboard.Key.f14,
    "f15": keyboard.Key.f15,
    "f16": keyboard.Key.f16,
    "f17": keyboard.Key.f17,
    "f18": keyboard.Key.f18,
    "f19": keyboard.Key.f19,
    "f20": keyboard.Key.f20,
    # Common modifiers for combinations
    "ctrl": keyboard.Key.ctrl,
    "alt": keyboard.Key.alt,
    "shift": keyboard.Key.shift,
    "super": keyboard.Key.cmd,  # Super/Windows key
    # Special keys
    "space": keyboard.Key.space,
    "enter": keyboard.Key.enter,
    "tab": keyboard.Key.tab,
    "escape": keyboard.Key.esc,
    "backspace": keyboard.Key.backspace,
    "delete": keyboard.Key.delete,
    "insert": keyboard.Key.insert,
    "home": keyboard.Key.home,
    "end": keyboard.Key.end,
    "pageup": keyboard.Key.page_up,
    "pagedown": keyboard.Key.page_down,
    # Media keys (some keyboards)
    "media_play_pause": keyboard.Key.media_play_pause,
    "media_next": keyboard.Key.media_next,
    "media_previous": keyboard.Key.media_previous,
}

# Reverse mapping for display
KEY_DISPLAY_MAP = {v: k.upper() for k, v in KEY_MAP.items()}


def parse_hotkey(hotkey_str: str) -> Optional[set]:
    """Parse a hotkey string like 'ctrl+shift+r' or 'f16' into a set of keys.

    Returns None if the hotkey string is empty or invalid.
    """
    if not hotkey_str or not hotkey_str.strip():
        return None

    parts = [p.strip().lower() for p in hotkey_str.split("+")]
    keys = set()

    for part in parts:
        if part in KEY_MAP:
            keys.add(KEY_MAP[part])
        elif len(part) == 1:
            # Single character key
            keys.add(keyboard.KeyCode.from_char(part))
        else:
            # Unknown key
            return None

    return keys if keys else None


def key_to_string(key) -> str:
    """Convert a pynput key to a display string."""
    if key in KEY_DISPLAY_MAP:
        return KEY_DISPLAY_MAP[key]
    elif hasattr(key, "char") and key.char:
        return key.char.upper()
    elif hasattr(key, "vk"):
        # Try to identify the key by virtual key code
        # F13-F24 might come through as vk codes
        vk = key.vk
        if 124 <= vk <= 135:  # F13-F24 on some systems
            return f"F{vk - 111}"
        return f"KEY_{vk}"
    return str(key)


class GlobalHotkeyListener:
    """Manages global hotkey listening and callbacks."""

    def __init__(self):
        self.hotkeys: Dict[str, set] = {}  # name -> key set
        self.callbacks: Dict[str, Callable] = {}  # name -> callback
        self.pressed_keys: set = set()
        self.listener: Optional[keyboard.Listener] = None
        self._lock = threading.Lock()

    def register(self, name: str, hotkey_str: str, callback: Callable) -> bool:
        """Register a hotkey with a callback.

        Args:
            name: Unique name for this hotkey (e.g., 'start_recording')
            hotkey_str: Hotkey string like 'f16' or 'ctrl+shift+r'
            callback: Function to call when hotkey is pressed

        Returns:
            True if registration was successful, False otherwise
        """
        keys = parse_hotkey(hotkey_str)
        if keys is None:
            # Remove any existing registration for this name
            with self._lock:
                self.hotkeys.pop(name, None)
                self.callbacks.pop(name, None)
            return False

        with self._lock:
            self.hotkeys[name] = keys
            self.callbacks[name] = callback
        return True

    def unregister(self, name: str):
        """Unregister a hotkey by name."""
        with self._lock:
            self.hotkeys.pop(name, None)
            self.callbacks.pop(name, None)

    def start(self):
        """Start listening for global hotkeys."""
        if self.listener is not None:
            return

        self.listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release
        )
        self.listener.start()

    def stop(self):
        """Stop listening for global hotkeys."""
        if self.listener is not None:
            self.listener.stop()
            self.listener = None
        self.pressed_keys.clear()

    def _on_press(self, key):
        """Handle key press events."""
        # Normalize the key
        normalized = self._normalize_key(key)
        self.pressed_keys.add(normalized)

        # Check if any hotkey combination is pressed
        with self._lock:
            for name, hotkey_keys in self.hotkeys.items():
                if hotkey_keys and hotkey_keys.issubset(self.pressed_keys):
                    callback = self.callbacks.get(name)
                    if callback:
                        # Call callback in a separate thread to avoid blocking
                        threading.Thread(target=callback, daemon=True).start()

    def _on_release(self, key):
        """Handle key release events."""
        normalized = self._normalize_key(key)
        self.pressed_keys.discard(normalized)

    def _normalize_key(self, key):
        """Normalize a key for consistent comparison."""
        # Handle modifier keys specially
        if hasattr(key, "vk"):
            vk = key.vk
            # Map left/right modifiers to generic ones
            if vk in (65505, 65506):  # Left/Right Shift
                return keyboard.Key.shift
            if vk in (65507, 65508):  # Left/Right Ctrl
                return keyboard.Key.ctrl
            if vk in (65513, 65514):  # Left/Right Alt
                return keyboard.Key.alt
            # F13-F24 handling
            if 124 <= vk <= 135:
                f_num = vk - 111
                key_name = f"f{f_num}"
                if key_name in KEY_MAP:
                    return KEY_MAP[key_name]
        return key


class HotkeyCapture:
    """Temporarily captures key presses for hotkey configuration."""

    def __init__(self, callback: Callable[[str], None]):
        """
        Args:
            callback: Called with the captured hotkey string when a key is pressed
        """
        self.callback = callback
        self.listener: Optional[keyboard.Listener] = None
        self.pressed_keys: set = set()
        self.modifier_keys = {
            keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r,
            keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r,
            keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r,
            keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r,
        }

    def start(self):
        """Start capturing key presses."""
        self.pressed_keys.clear()
        self.listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release
        )
        self.listener.start()

    def stop(self):
        """Stop capturing."""
        if self.listener:
            self.listener.stop()
            self.listener = None

    def _on_press(self, key):
        """Handle key press during capture."""
        self.pressed_keys.add(key)

        # Check if we have a non-modifier key
        non_modifiers = [k for k in self.pressed_keys if k not in self.modifier_keys]

        if non_modifiers:
            # Build the hotkey string
            parts = []

            # Add modifiers first (in standard order)
            if any(k in self.pressed_keys for k in [keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r]):
                parts.append("ctrl")
            if any(k in self.pressed_keys for k in [keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r]):
                parts.append("alt")
            if any(k in self.pressed_keys for k in [keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r]):
                parts.append("shift")
            if any(k in self.pressed_keys for k in [keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r]):
                parts.append("super")

            # Add the main key
            main_key = non_modifiers[0]
            key_str = key_to_string(main_key).lower()
            parts.append(key_str)

            hotkey_str = "+".join(parts)
            self.stop()
            self.callback(hotkey_str)

    def _on_release(self, key):
        """Handle key release during capture."""
        self.pressed_keys.discard(key)


# Suggested hotkeys for users with macro keys
SUGGESTED_HOTKEYS = {
    "start_recording": "F14",
    "stop_recording": "F15",
    "stop_and_transcribe": "F16",
}

HOTKEY_DESCRIPTIONS = {
    "start_recording": "Start Recording",
    "stop_recording": "Stop Recording (discard)",
    "stop_and_transcribe": "Stop & Transcribe",
}
