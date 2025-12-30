# Keyboard Shortcuts

## In-App Shortcuts

These work when the AI Transcription Notepad window is focused.

| Shortcut | Action |
|----------|--------|
| Ctrl+R | Start recording |
| Ctrl+Space | Pause/resume recording |
| Ctrl+Return | Stop and transcribe |
| Ctrl+S | Save to file |
| Ctrl+Shift+C | Copy to clipboard |
| Ctrl+N | Clear editor |

## Global Hotkeys

Global hotkeys work system-wide, even when AI Transcription Notepad is minimized or unfocused.

### Current Hotkey Mapping

| Key | Action | Description |
|-----|--------|-------------|
| F15 | Toggle Recording | Start recording, or stop and cache audio |
| F16 | Tap | Same as F15 (toggle recording) |
| F17 | Transcribe Only | Transcribe cached audio without starting a new recording |
| F18 | Clear/Delete | Delete current recording and clear all cached audio |
| F19 | Append | Start a new recording that appends to cached audio |

### Workflow Example

1. Press **F15** to start recording
2. Press **F15** again to stop and cache (audio is held in memory)
3. Press **F19** to record another segment (appends to cache)
4. Press **F17** to transcribe all cached segments together
5. Press **F18** to clear cache and start over

### Why F15-F19?

These extended function keys are ideal because:
- They don't conflict with other applications or desktop shortcuts
- They work reliably across Linux, including Wayland
- They're available on keyboards with macro/programmable keys

Most standard keyboards only have F1-F12. If your keyboard doesn't have F15+ keys, you can remap other keys or buttons to emit these keycodes.

### Setting Up Hotkeys with Input Remapper

If you have a USB foot pedal, macro keypad, or want to remap standard keys like Pause/Break, see the **[Hotkey Setup Guide](hotkey-setup.md)** for step-by-step instructions using Input Remapper.

Common remapping options:
- **Pause/Break key** to F15 for toggle recording
- **USB foot pedal buttons** to F15/F17/F18 for hands-free operation
- **Extra mouse buttons** to F15 for quick dictation

### Technical Notes

- On Linux/Wayland: Hotkeys work via evdev (reads directly from input devices)
- Requires user to be in the 'input' group for evdev access
- Falls back to pynput/X11 on non-Linux systems
- Configure hotkeys in Settings > Hotkeys (F13-F24 keys supported)
