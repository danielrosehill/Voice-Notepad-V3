# Text Injection Setup (Wayland)

Text injection automatically pastes transcribed text at your cursor position after transcription completes.

## Tested Environment

This setup has been validated on:
- **OS**: Ubuntu 25.10
- **Desktop**: KDE Plasma 6
- **Display Server**: Wayland
- **ydotool version**: 1.0.4

Other Wayland environments (GNOME, Sway, Hyprland) should work similarly, but may require adjustments.

## Automated Setup Script

Run the setup script to check your configuration and fix common issues:

```bash
./scripts/setup-text-injection.sh
```

The script will:
1. Detect your environment
2. Check if ydotool is installed (and offer to install it)
3. Verify the daemon is running with correct permissions
4. Provide remediation commands if needed

## The Problem

On X11, tools like `xdotool` could easily simulate keyboard input. Wayland intentionally blocks this for security reasons - applications cannot inject keystrokes into other applications by default.

This is a common frustration for Linux users of speech-to-text applications. Many dictation tools work perfectly for transcription but fail at the final step: actually typing the text.

## The Solution: ydotool

Voice Notepad uses `ydotool` for text injection on Wayland. Unlike X11 tools, ydotool works at the Linux kernel level via `/dev/uinput`, bypassing Wayland's restrictions.

**However**, ydotool requires a daemon (`ydotoold`) to be running with the correct permissions. This is where most users encounter problems.

## Quick Setup

### 1. Install ydotool

```bash
# Ubuntu/Debian
sudo apt install ydotool

# Fedora
sudo dnf install ydotool

# Arch
sudo pacman -S ydotool
```

### 2. Start the daemon as YOUR user (not root)

This is the critical step most guides miss. The daemon must run as your user, not as root:

```bash
# Kill any existing root-owned daemon
sudo pkill ydotoold
sudo rm -f /tmp/.ydotool_socket

# Start as your user
ydotoold &
```

### 3. Verify the socket is user-owned

```bash
ls -la /tmp/.ydotool_socket
```

You should see your username as the owner:
```
srw-rw-rw- 1 youruser youruser 0 Dec 25 17:52 /tmp/.ydotool_socket
```

**If it shows `root root`, text injection will not work.** Repeat step 2.

### 4. Test it works

```bash
# Copy something to clipboard
echo "Hello World" | wl-copy

# Open a text editor and focus it, then run:
ydotool key ctrl+v
```

If "Hello World" appears in your editor, ydotool is working correctly.

## Making It Persistent (Autostart)

To have ydotoold start automatically on login:

### Option A: Systemd user service (recommended)

Create `~/.config/systemd/user/ydotoold.service`:

```ini
[Unit]
Description=ydotool daemon

[Service]
ExecStart=/usr/bin/ydotoold

[Install]
WantedBy=default.target
```

Then enable it:

```bash
systemctl --user daemon-reload
systemctl --user enable --now ydotoold
```

### Option B: Desktop autostart

Create `~/.config/autostart/ydotoold.desktop`:

```ini
[Desktop Entry]
Type=Application
Name=ydotoold
Exec=ydotoold
X-GNOME-Autostart-enabled=true
```

### Option C: Add to shell profile

Add to your `~/.bashrc` or `~/.zshrc`:

```bash
# Start ydotoold if not running
if ! pgrep -x ydotoold > /dev/null; then
    ydotoold &
fi
```

## Troubleshooting

### "ydotoold backend unavailable" warning

This means ydotool cannot connect to the daemon. Check:

1. **Is ydotoold running?**
   ```bash
   pgrep -a ydotoold
   ```

2. **Is the socket user-owned?**
   ```bash
   ls -la /tmp/.ydotool_socket
   ```

   If owned by root, restart the daemon as your user (see Quick Setup step 2).

3. **Are there multiple daemons running?**
   ```bash
   pgrep -a ydotoold
   ```

   If you see multiple processes, kill them all and start fresh:
   ```bash
   pkill ydotoold
   sudo rm -f /tmp/.ydotool_socket
   ydotoold &
   ```

### Text injection does nothing (no paste)

1. **Verify clipboard has content:**
   ```bash
   wl-paste
   ```

2. **Test ydotool directly:**
   ```bash
   echo "test" | wl-copy
   # Focus a text field, then:
   ydotool key ctrl+v
   ```

3. **Check socket permissions:**
   ```bash
   ls -la /tmp/.ydotool_socket
   ```

   The socket must be owned by your user, not root.

### Permission denied errors

Add your user to the `input` group:

```bash
sudo usermod -aG input $USER
```

Then log out and back in for the group change to take effect.

## Why Not Other Tools?

| Tool | Issue on Wayland |
|------|------------------|
| `xdotool` | X11 only, does not work on Wayland |
| `wtype` | Requires compositor support for virtual keyboard protocol (KDE Plasma doesn't support it) |
| `dotool` | Similar issues to ydotool, less maintained |
| Direct uinput | Works but requires root/sudo to create the device |

ydotool is currently the most reliable option for Wayland that doesn't require running the application as root.

## Security Notes

- ydotoold creates a virtual keyboard device at the kernel level
- The daemon socket should only be accessible by your user
- No root access is required for the Voice Notepad application itself
- The daemon only needs to run as your user, not as root

## Alternative: Disable Text Injection

If you can't get ydotool working, you can disable text injection and use manual paste:

1. Uncheck "Text Injection (Beta)" in the main window
2. After transcription, use Ctrl+V manually to paste

The transcription is always copied to your clipboard automatically, so manual paste will always work.

## References

- [ydotool GitHub](https://github.com/ReimuNotMoe/ydotool)
- [Wayland Input Method Protocol](https://wayland.freedesktop.org/docs/html/apa.html)
- [Linux uinput documentation](https://www.kernel.org/doc/html/latest/input/uinput.html)
