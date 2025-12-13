# Troubleshooting

## Audio Issues

### No Microphone Detected

**Symptoms**: Microphone dropdown is empty or shows no devices

**Solutions**:

1. Check that your microphone is connected and recognized:
   ```bash
   pactl list sources short
   ```

2. Ensure PipeWire/PulseAudio is running:
   ```bash
   pactl info
   ```

3. For USB microphones, check permissions:
   ```bash
   ls -la /dev/snd/
   ```

### Recording Not Working

**Symptoms**: Click Record but no audio levels shown

**Solutions**:

1. Verify the correct input device is selected in the dropdown
2. Check system audio settings for the input device
3. Test microphone in another application
4. Restart PipeWire:
   ```bash
   systemctl --user restart pipewire
   ```

### Poor Audio Quality

**Solutions**:

1. Position microphone closer
2. Reduce background noise
3. Check microphone gain in system settings
4. Use a USB microphone for better quality

## API Issues

### API Key Not Working

**Symptoms**: "Unauthorized" or "Invalid API key" errors

**Solutions**:

1. Verify the API key is correct in Settings
2. Check that the key has the required permissions
3. For OpenRouter, verify credits are available
4. Try setting the key via environment variable:
   ```bash
   export OPENROUTER_API_KEY=your_key
   ./run.sh
   ```

### Transcription Fails

**Symptoms**: Error during transcription, no output

**Solutions**:

1. Check internet connection
2. Verify API key is valid and has credits
3. Try a different provider/model
4. Check the terminal output for error details
5. For large recordings, try enabling VAD to reduce file size

### Rate Limiting

**Symptoms**: "Rate limit exceeded" errors

**Solutions**:

1. Wait a few minutes before trying again
2. Consider using a different provider
3. For heavy usage, contact the provider for higher limits

## Installation Issues

### PyAudio Installation Fails

**Symptoms**: Error installing PyAudio

**Solution**:

```bash
sudo apt install portaudio19-dev
pip install pyaudio
```

### Missing ffmpeg

**Symptoms**: Audio processing errors, missing codec

**Solution**:

```bash
sudo apt install ffmpeg
```

### Qt Platform Issues

**Symptoms**: "Could not find the Qt platform plugin" error

**Solution**:

```bash
sudo apt install libxcb-cursor0
```

## Global Hotkeys

### Hotkeys Not Working

**Symptoms**: Global hotkeys don't trigger recording

**Solutions**:

1. Check hotkey configuration in Settings > Hotkeys
2. On Wayland, ensure XWayland is available
3. Some keys may be captured by the desktop environment
4. Try different key combinations (F14-F20 recommended)

### Key Conflicts

**Solutions**:

1. Use F14-F20 (macro keys) to avoid conflicts
2. Check desktop environment shortcuts
3. Disable conflicting shortcuts in other applications

## Database Issues

### History Not Showing

**Symptoms**: History tab is empty despite transcriptions

**Solutions**:

1. Check database file exists:
   ```bash
   ls -la ~/.config/voice-notepad-v3/transcriptions.db
   ```

2. Verify write permissions on config directory

3. If corrupted, backup and delete the database to start fresh

### Cost Data Missing

**Solutions**:

1. For OpenRouter, verify API key has access to usage endpoints
2. Check usage directory:
   ```bash
   ls -la ~/.config/voice-notepad-v3/usage/
   ```

## Performance Issues

### Slow Transcription

**Solutions**:

1. Enable VAD to reduce audio size
2. Use a faster model (e.g., Gemini Flash Lite)
3. Check internet connection speed
4. For very long recordings, consider splitting them

### High Memory Usage

**Solutions**:

1. Close unused tabs
2. Clear old history if database is large
3. Restart the application periodically

## Getting Help

If you can't resolve an issue:

1. Check the [GitHub Issues](https://github.com/danielrosehill/Voice-Notepad/issues) for similar problems
2. Open a new issue with:
   - Steps to reproduce
   - Error messages (from terminal)
   - System information (OS, Python version)
   - Provider/model being used
