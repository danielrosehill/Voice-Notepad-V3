"""Global hotkey handling for Voice Notepad V3.

Supports two backends:
1. evdev (Linux) - Works natively on Wayland, reads from input-remapper devices
2. pynput (fallback) - Cross-platform, requires X11/XWayland

evdev is preferred on Linux as it works globally on Wayland without needing
X11 focus. Requires user to be in the 'input' group.
"""

import logging
import os
import select
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Dict, List, Optional

# Try to import evdev (Linux only, preferred for Wayland)
try:
    import evdev
    import evdev.ecodes as ecodes
    EVDEV_AVAILABLE = True
except ImportError:
    EVDEV_AVAILABLE = False

from pynput import keyboard

# Debug logging for hotkeys (enable with VOICE_NOTEPAD_DEBUG_HOTKEYS=1)
_debug_hotkeys = os.environ.get("VOICE_NOTEPAD_DEBUG_HOTKEYS", "").lower() in ("1", "true", "yes")
logger = logging.getLogger(__name__)
if _debug_hotkeys:
    logging.basicConfig(level=logging.DEBUG)
    logger.setLevel(logging.DEBUG)
    logger.debug("Hotkey debug logging enabled")


# Debounce settings
DEBOUNCE_INTERVAL_MS = 100  # Minimum time between hotkey triggers (prevents rapid-fire)
MAX_CALLBACK_THREADS = 2  # Max concurrent callback executions


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
    # F21-F24 may not have direct pynput constants; handled via vk codes
    # These are handled in _normalize_key() and key_to_string()
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
    # Lock keys
    "pause": keyboard.Key.pause,
    "scroll_lock": keyboard.Key.scroll_lock,
    "num_lock": keyboard.Key.num_lock,
    "caps_lock": keyboard.Key.caps_lock,
    "print_screen": keyboard.Key.print_screen,
}

# Reverse mapping for display
KEY_DISPLAY_MAP = {v: k.upper() for k, v in KEY_MAP.items()}

# evdev key code mapping (Linux kernel key codes)
# These are the KEY_* constants from linux/input-event-codes.h
EVDEV_KEY_MAP = {
    "f1": 59, "f2": 60, "f3": 61, "f4": 62, "f5": 63, "f6": 64,
    "f7": 65, "f8": 66, "f9": 67, "f10": 68, "f11": 87, "f12": 88,
    # Extended function keys (F13-F24)
    "f13": 183, "f14": 184, "f15": 185, "f16": 186, "f17": 187,
    "f18": 188, "f19": 189, "f20": 190, "f21": 191, "f22": 192,
    "f23": 193, "f24": 194,
    # Modifiers
    "ctrl": 29, "leftctrl": 29, "rightctrl": 97,
    "alt": 56, "leftalt": 56, "rightalt": 100,
    "shift": 42, "leftshift": 42, "rightshift": 54,
    "super": 125, "leftmeta": 125, "rightmeta": 126,
    # Common keys
    "space": 57, "enter": 28, "tab": 15, "escape": 1,
    "backspace": 14, "delete": 111, "insert": 110,
    "home": 102, "end": 107, "pageup": 104, "pagedown": 109,
}

# Reverse mapping for evdev
EVDEV_KEY_DISPLAY_MAP = {v: k.upper() for k, v in EVDEV_KEY_MAP.items()}


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
    """Convert a pynput key to a display string.

    For unknown keys, returns 'vk:NNNN' format which can be parsed back.
    """
    if key in KEY_DISPLAY_MAP:
        return KEY_DISPLAY_MAP[key]
    elif hasattr(key, "char") and key.char:
        return key.char.upper()
    elif hasattr(key, "vk") and key.vk:
        vk = key.vk
        # Windows VK codes for F13-F24: 124-135
        if 124 <= vk <= 135:
            return f"F{vk - 111}"
        # Linux X11 keysyms for F13-F24: 65482-65493 (0xFFCA-0xFFD5)
        if 65482 <= vk <= 65493:
            return f"F{vk - 65469}"
        # Store unknown keys by their vk code so we can match them later
        return f"vk:{vk}"
    return str(key)


class GlobalHotkeyListener:
    """Manages global hotkey listening and callbacks."""

    def __init__(self):
        self.hotkeys: Dict[str, set] = {}  # name -> key set
        self.callbacks: Dict[str, Callable] = {}  # name -> callback (on press)
        self.release_callbacks: Dict[str, Callable] = {}  # name -> callback (on release)
        self.pressed_keys: set = set()
        self.active_hotkeys: set = set()  # Track which hotkeys are currently "active" (pressed)
        self.listener: Optional[keyboard.Listener] = None
        self._lock = threading.Lock()
        # Debouncing: track last trigger time per hotkey
        self._last_trigger_time: Dict[str, float] = {}
        # Thread pool for callbacks (prevents thread explosion)
        self._executor = ThreadPoolExecutor(max_workers=MAX_CALLBACK_THREADS, thread_name_prefix="hotkey")

    def register(
        self,
        name: str,
        hotkey_str: str,
        callback: Callable,
        release_callback: Optional[Callable] = None
    ) -> bool:
        """Register a hotkey with callbacks for press and optional release.

        Args:
            name: Unique name for this hotkey (e.g., 'start_recording')
            hotkey_str: Hotkey string like 'f16' or 'ctrl+shift+r'
            callback: Function to call when hotkey is pressed
            release_callback: Optional function to call when hotkey is released (for PTT)

        Returns:
            True if registration was successful, False otherwise
        """
        keys = parse_hotkey(hotkey_str)
        if keys is None:
            # Remove any existing registration for this name
            with self._lock:
                self.hotkeys.pop(name, None)
                self.callbacks.pop(name, None)
                self.release_callbacks.pop(name, None)
            return False

        with self._lock:
            self.hotkeys[name] = keys
            self.callbacks[name] = callback
            if release_callback:
                self.release_callbacks[name] = release_callback
            else:
                self.release_callbacks.pop(name, None)
        return True

    def unregister(self, name: str):
        """Unregister a hotkey by name."""
        with self._lock:
            self.hotkeys.pop(name, None)
            self.callbacks.pop(name, None)
            self.release_callbacks.pop(name, None)
            self.active_hotkeys.discard(name)

    def start(self):
        """Start listening for global hotkeys."""
        if self.listener is not None:
            if _debug_hotkeys:
                logger.debug("Listener already running")
            return

        if _debug_hotkeys:
            logger.debug("Starting global hotkey listener...")
            logger.debug(f"  Registered hotkeys: {list(self.hotkeys.keys())}")
            for name, keys in self.hotkeys.items():
                logger.debug(f"    {name}: {keys}")

        self.listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release
        )
        self.listener.start()

        if _debug_hotkeys:
            logger.debug(f"  Listener started: {self.listener.is_alive()}")

    def stop(self):
        """Stop listening for global hotkeys."""
        if self.listener is not None:
            self.listener.stop()
            self.listener = None
        self.pressed_keys.clear()
        self.active_hotkeys.clear()
        # Shutdown thread pool gracefully
        self._executor.shutdown(wait=False)

    def _should_debounce(self, name: str) -> bool:
        """Check if this hotkey should be debounced (triggered too recently)."""
        now = time.time() * 1000  # Convert to milliseconds
        last_time = self._last_trigger_time.get(name, 0)
        if now - last_time < DEBOUNCE_INTERVAL_MS:
            return True
        self._last_trigger_time[name] = now
        return False

    def _on_press(self, key):
        """Handle key press events."""
        if _debug_hotkeys:
            logger.debug(f"Key press: {key} (type: {type(key).__name__}, vk: {getattr(key, 'vk', 'N/A')})")

        # Normalize the key
        normalized = self._normalize_key(key)
        self.pressed_keys.add(normalized)

        if _debug_hotkeys:
            logger.debug(f"  Normalized: {normalized}")
            logger.debug(f"  pressed_keys: {self.pressed_keys}")

        # Check if any hotkey combination is pressed
        with self._lock:
            for name, hotkey_keys in self.hotkeys.items():
                # Only trigger if not already active (prevent repeat triggers while held)
                if name not in self.active_hotkeys:
                    if hotkey_keys and hotkey_keys.issubset(self.pressed_keys):
                        if _debug_hotkeys:
                            logger.debug(f"  Hotkey matched: {name}")
                        self.active_hotkeys.add(name)
                        callback = self.callbacks.get(name)
                        if callback:
                            # Debounce check (outside lock to avoid contention)
                            if not self._should_debounce(name):
                                if _debug_hotkeys:
                                    logger.debug(f"  Executing callback for {name}")
                                # Use thread pool instead of spawning new threads
                                try:
                                    self._executor.submit(callback)
                                except RuntimeError:
                                    # Executor shut down, ignore
                                    pass
                            elif _debug_hotkeys:
                                logger.debug(f"  Debounced: {name}")

    def _on_release(self, key):
        """Handle key release events."""
        normalized = self._normalize_key(key)
        self.pressed_keys.discard(normalized)

        # Check if any active hotkey is no longer fully pressed
        with self._lock:
            released_hotkeys = []
            for name in list(self.active_hotkeys):
                hotkey_keys = self.hotkeys.get(name, set())
                # If any key in the hotkey combo is released, the hotkey is released
                if hotkey_keys and not hotkey_keys.issubset(self.pressed_keys):
                    released_hotkeys.append(name)

            for name in released_hotkeys:
                self.active_hotkeys.discard(name)
                release_callback = self.release_callbacks.get(name)
                if release_callback:
                    # Use thread pool for release callbacks too
                    try:
                        self._executor.submit(release_callback)
                    except RuntimeError:
                        # Executor shut down, ignore
                        pass

    def _normalize_key(self, key):
        """Normalize a key for consistent comparison."""
        # Handle modifier keys specially
        if hasattr(key, "vk"):
            vk = key.vk
            # Some keys have vk=None, skip vk-based normalization for those
            if vk is not None:
                # Map left/right modifiers to generic ones
                if vk in (65505, 65506):  # Left/Right Shift (X11)
                    return keyboard.Key.shift
                if vk in (65507, 65508):  # Left/Right Ctrl (X11)
                    return keyboard.Key.ctrl
                if vk in (65513, 65514):  # Left/Right Alt (X11)
                    return keyboard.Key.alt
                # F13-F24 handling - Windows VK codes: 124-135
                if 124 <= vk <= 135:
                    f_num = vk - 111
                    key_name = f"f{f_num}"
                    if key_name in KEY_MAP:
                        return KEY_MAP[key_name]
                # F13-F24 handling - Linux X11 keysyms: 65482-65493
                if 65482 <= vk <= 65493:
                    f_num = vk - 65469  # 65482 - 65469 = 13, so F13
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


class EvdevHotkeyListener:
    """Evdev-based global hotkey listener for Linux/Wayland.

    This listener reads directly from input devices via evdev, which works
    globally on Wayland without needing X11. It specifically monitors
    input-remapper virtual keyboard devices for hotkey events.

    Requires the user to be in the 'input' group.
    """

    def __init__(self):
        self.hotkeys: Dict[str, set] = {}  # name -> set of evdev key codes
        self.callbacks: Dict[str, Callable] = {}  # name -> callback (on press)
        self.release_callbacks: Dict[str, Callable] = {}  # name -> callback (on release)
        self.pressed_keys: set = set()
        self.active_hotkeys: set = set()
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._devices: List = []
        self._last_trigger_time: Dict[str, float] = {}
        self._executor = ThreadPoolExecutor(max_workers=MAX_CALLBACK_THREADS, thread_name_prefix="evdev-hotkey")

    def _find_devices(self) -> List:
        """Find input-remapper keyboard devices to monitor."""
        if not EVDEV_AVAILABLE:
            return []

        devices = []
        try:
            for path in evdev.list_devices():
                try:
                    device = evdev.InputDevice(path)
                    # Monitor input-remapper keyboard (where remapped keys appear)
                    # and any other keyboard devices
                    name_lower = device.name.lower()
                    if "input-remapper" in name_lower and "keyboard" in name_lower:
                        devices.append(device)
                        if _debug_hotkeys:
                            logger.debug(f"Found evdev device: {device.path} - {device.name}")
                except (PermissionError, OSError) as e:
                    if _debug_hotkeys:
                        logger.debug(f"Cannot access {path}: {e}")
        except Exception as e:
            if _debug_hotkeys:
                logger.debug(f"Error listing evdev devices: {e}")

        return devices

    def register(
        self,
        name: str,
        hotkey_str: str,
        callback: Callable,
        release_callback: Optional[Callable] = None
    ) -> bool:
        """Register a hotkey with callbacks for press and optional release."""
        if not hotkey_str or not hotkey_str.strip():
            with self._lock:
                self.hotkeys.pop(name, None)
                self.callbacks.pop(name, None)
                self.release_callbacks.pop(name, None)
            return False

        # Parse hotkey string to evdev key codes
        parts = [p.strip().lower() for p in hotkey_str.split("+")]
        key_codes = set()

        for part in parts:
            if part in EVDEV_KEY_MAP:
                key_codes.add(EVDEV_KEY_MAP[part])
            elif len(part) == 1:
                # Single character - map to evdev key code
                # A-Z are codes 30-44, 46-54 in evdev
                char = part.upper()
                if 'A' <= char <= 'Z':
                    # Approximate mapping (not all letters are sequential)
                    code = ord(char) - ord('A') + 30
                    if code > 38:  # Skip some non-letter keys
                        code += 7
                    key_codes.add(code)
            else:
                if _debug_hotkeys:
                    logger.debug(f"Unknown key in hotkey: {part}")
                return False

        if not key_codes:
            return False

        with self._lock:
            self.hotkeys[name] = key_codes
            self.callbacks[name] = callback
            if release_callback:
                self.release_callbacks[name] = release_callback
            else:
                self.release_callbacks.pop(name, None)

        if _debug_hotkeys:
            logger.debug(f"Registered evdev hotkey '{name}': {hotkey_str} -> codes {key_codes}")

        return True

    def unregister(self, name: str):
        """Unregister a hotkey by name."""
        with self._lock:
            self.hotkeys.pop(name, None)
            self.callbacks.pop(name, None)
            self.release_callbacks.pop(name, None)
            self.active_hotkeys.discard(name)

    def start(self):
        """Start listening for global hotkeys via evdev."""
        if self._running:
            if _debug_hotkeys:
                logger.debug("Evdev listener already running")
            return

        self._devices = self._find_devices()
        if not self._devices:
            logger.warning("No input-remapper keyboard devices found for evdev hotkeys")
            return

        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()

        if _debug_hotkeys:
            logger.debug(f"Started evdev hotkey listener with {len(self._devices)} device(s)")

    def stop(self):
        """Stop listening for global hotkeys."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None

        # Close devices
        for device in self._devices:
            try:
                device.close()
            except Exception:
                pass
        self._devices = []

        self.pressed_keys.clear()
        self.active_hotkeys.clear()
        self._executor.shutdown(wait=False)

    def _should_debounce(self, name: str) -> bool:
        """Check if this hotkey should be debounced."""
        now = time.time() * 1000
        last_time = self._last_trigger_time.get(name, 0)
        if now - last_time < DEBOUNCE_INTERVAL_MS:
            return True
        self._last_trigger_time[name] = now
        return False

    def _listen_loop(self):
        """Main loop that reads from evdev devices."""
        while self._running:
            try:
                # Use select to wait for events with timeout
                r, w, x = select.select(self._devices, [], [], 0.1)

                for device in r:
                    try:
                        for event in device.read():
                            if event.type == ecodes.EV_KEY:
                                self._handle_key_event(event.code, event.value)
                    except (OSError, IOError) as e:
                        if _debug_hotkeys:
                            logger.debug(f"Error reading from {device.path}: {e}")
                        # Device might have been disconnected
                        continue

            except Exception as e:
                if _debug_hotkeys:
                    logger.debug(f"Error in evdev listen loop: {e}")
                time.sleep(0.1)

    def _handle_key_event(self, code: int, value: int):
        """Handle a key event from evdev.

        value: 0 = release, 1 = press, 2 = repeat
        """
        if _debug_hotkeys:
            key_name = EVDEV_KEY_DISPLAY_MAP.get(code, f"CODE_{code}")
            state = "PRESS" if value == 1 else ("RELEASE" if value == 0 else "REPEAT")
            logger.debug(f"Evdev key: {key_name} ({code}) - {state}")

        if value == 1:  # Key press
            self.pressed_keys.add(code)
            self._check_hotkeys_press()
        elif value == 0:  # Key release
            self.pressed_keys.discard(code)
            self._check_hotkeys_release()

    def _check_hotkeys_press(self):
        """Check if any hotkey combination is now pressed."""
        with self._lock:
            for name, hotkey_codes in self.hotkeys.items():
                if name not in self.active_hotkeys:
                    if hotkey_codes and hotkey_codes.issubset(self.pressed_keys):
                        if _debug_hotkeys:
                            logger.debug(f"Evdev hotkey matched: {name}")
                        self.active_hotkeys.add(name)
                        callback = self.callbacks.get(name)
                        if callback and not self._should_debounce(name):
                            if _debug_hotkeys:
                                logger.debug(f"Executing evdev callback for {name}")
                            try:
                                self._executor.submit(callback)
                            except RuntimeError:
                                pass

    def _check_hotkeys_release(self):
        """Check if any active hotkey is no longer pressed."""
        with self._lock:
            released = []
            for name in list(self.active_hotkeys):
                hotkey_codes = self.hotkeys.get(name, set())
                if hotkey_codes and not hotkey_codes.issubset(self.pressed_keys):
                    released.append(name)

            for name in released:
                self.active_hotkeys.discard(name)
                release_callback = self.release_callbacks.get(name)
                if release_callback:
                    try:
                        self._executor.submit(release_callback)
                    except RuntimeError:
                        pass


def create_hotkey_listener():
    """Create the best available hotkey listener for this platform.

    Returns EvdevHotkeyListener on Linux if evdev is available and devices
    are accessible, otherwise returns GlobalHotkeyListener (pynput-based).
    """
    if EVDEV_AVAILABLE:
        listener = EvdevHotkeyListener()
        devices = listener._find_devices()
        if devices:
            if _debug_hotkeys:
                logger.debug(f"Using evdev hotkey listener ({len(devices)} device(s))")
            # Close the test devices
            for d in devices:
                try:
                    d.close()
                except Exception:
                    pass
            return EvdevHotkeyListener()  # Return fresh instance
        else:
            if _debug_hotkeys:
                logger.debug("No evdev devices found, falling back to pynput")

    if _debug_hotkeys:
        logger.debug("Using pynput hotkey listener")
    return GlobalHotkeyListener()


# Suggested hotkeys for users with macro keys
SUGGESTED_HOTKEYS = {
    # Single Key mode (primary/recommended)
    "single_key": "F15",
    # Tap-to-Toggle mode
    "record_toggle": "F16",
    "stop_and_transcribe": "F17",
    # Separate mode
    "start": "F16",
    "stop_discard": "F17",
    # PTT mode
    "ptt": "F16",
}

HOTKEY_DESCRIPTIONS = {
    "record_toggle": "Record Toggle (Start/Stop)",
    "stop_and_transcribe": "Stop & Transcribe",
    "start": "Start Recording",
    "stop_discard": "Stop & Discard",
    "ptt": "Push-to-Talk",
}

# Hotkey mode display names
HOTKEY_MODE_NAMES = {
    "single_key": "Single Key (Recommended)",
    "tap_toggle": "Tap to Toggle",
    "separate": "Separate Start/Stop",
    "ptt": "Push-to-Talk (PTT)",
}

HOTKEY_MODE_DESCRIPTIONS = {
    "single_key": "One key controls everything: Press to start, press again to stop and transcribe. Simple and efficient.",
    "tap_toggle": "One key toggles recording on/off. A separate key stops and transcribes.",
    "separate": "Different keys for Start, Stop (discard), and Stop & Transcribe.",
    "ptt": "Hold a key to record. Recording stops when you release the key.",
}
