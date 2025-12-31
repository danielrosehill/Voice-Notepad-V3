#!/bin/bash
# Generate TTS audio assets for Voice Notepad accessibility announcements.
#
# Uses Edge TTS with British English male voice (en-GB-RyanNeural).
# Run once to generate assets, then commit them to the repository.
#
# Usage:
#     ./scripts/generate_tts_assets.py
#
# Requirements:
#     pip install edge-tts

set -e

VOICE="en-GB-RyanNeural"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OUTPUT_DIR="$SCRIPT_DIR/../app/assets/tts"

# Create output directory
mkdir -p "$OUTPUT_DIR"

echo "Generating TTS assets with voice: $VOICE"
echo "Output directory: $OUTPUT_DIR"
echo

# Announcements to generate
# Keys are filenames, values are the spoken text
declare -A ANNOUNCEMENTS=(
    # Recording states
    ["recording"]="Recording"
    ["stopped"]="Recording stopped"
    ["paused"]="Recording paused"
    ["resumed"]="Recording resumed"
    ["discarded"]="Recording discarded"
    ["appended"]="Recording appended"
    ["cached"]="Cached"

    # Transcription states
    ["transcribing"]="Transcribing"
    ["complete"]="Complete"
    ["error"]="Error"

    # Output modes (transcription result destination)
    ["text_in_app"]="Text in app"
    ["text_on_clipboard"]="Text on clipboard"
    ["clipboard"]="Clipboard"
    ["text_injected"]="Text injected"
    ["injection_failed"]="Injection failed"

    # Output mode toggles (when user enables/disables output destinations)
    ["app_enabled"]="App enabled"
    ["app_disabled"]="App disabled"
    ["clipboard_enabled"]="Clipboard enabled"
    ["clipboard_disabled"]="Clipboard disabled"
    ["inject_enabled"]="Inject enabled"
    ["inject_disabled"]="Inject disabled"

    # Settings toggles
    ["vad_enabled"]="Voice activity detection enabled"
    ["vad_disabled"]="Voice activity detection disabled"

    # Append mode
    ["appending"]="Appending"

    # Prompt stack changes
    ["format_updated"]="Format updated"
    ["format_inference"]="Format inference activated"
    ["tone_updated"]="Tone updated"
    ["style_updated"]="Style updated"
    ["verbatim_mode"]="Verbatim mode selected"
    ["general_mode"]="General mode selected"

    # Audio feedback mode changes
    ["tts_activated"]="TTS mode activated"
    ["tts_deactivated"]="TTS mode deactivated"

    # Settings/config actions
    ["default_prompt_configured"]="Default prompt configured"
    ["copied_to_clipboard"]="Copied to clipboard"

    # Legacy (kept for compatibility)
    ["copied"]="Copied"
    ["injected"]="Injected"
    ["cleared"]="Cleared"
)

for name in "${!ANNOUNCEMENTS[@]}"; do
    text="${ANNOUNCEMENTS[$name]}"
    mp3_file="$OUTPUT_DIR/$name.mp3"
    wav_file="$OUTPUT_DIR/$name.wav"
    echo "Generating '$text'..."
    # Generate MP3 with edge-tts
    edge-tts --voice "$VOICE" --text "$text" --write-media "$mp3_file"
    # Convert to WAV (16kHz mono, 16-bit) for simpleaudio compatibility
    ffmpeg -y -i "$mp3_file" -ar 16000 -ac 1 -sample_fmt s16 "$wav_file" 2>/dev/null
    # Remove MP3, keep only WAV
    rm "$mp3_file"
    size=$(stat -c%s "$wav_file" 2>/dev/null || stat -f%z "$wav_file")
    echo "  Generated: $name.wav ($size bytes)"
done

echo
echo "Done! Generated ${#ANNOUNCEMENTS[@]} audio files."
total_size=$(du -sb "$OUTPUT_DIR" | cut -f1)
echo "Total size: $total_size bytes"
