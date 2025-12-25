# Audio Pipeline

AI Transcription Notepad processes audio through several stages before sending it to AI models.

## Overview

Audio flows through recording, optional VAD processing, compression, API submission, and storage:

1. **Recording**: PyAudio captures from the microphone at the system's default sample rate (typically 44.1kHz or 48kHz) in 16-bit PCM format.

2. **Automatic Gain Control**: Normalizes audio levels. Target peak is -3 dBFS, with a maximum gain of +20 dB. Only boosts quiet audio; never attenuates loud audio.

3. **Voice Activity Detection** (optional): Silero VAD detects speech segments and removes silence. Uses 32ms analysis windows with a 0.5 speech probability threshold. Typically reduces file size by 30-50%.

4. **Compression**: Audio is downsampled to 16kHz mono. This matches Gemini's internal format and reduces file size by about 66% compared to 48kHz stereo. No quality loss for speech transcription.

5. **API Submission**: The processed audio is base64-encoded and sent with the cleanup prompt to the selected AI model. The response includes the transcript, token counts, and cost data.

6. **Storage**: Transcripts are saved to SQLite. Optionally, audio is archived in Opus format at about 24kbps (~180KB per minute).

## VAD Parameters

| Parameter | Value |
|-----------|-------|
| Sample rate | 16kHz |
| Window size | 512 samples (~32ms) |
| Threshold | 0.5 |
| Minimum speech | 250ms |
| Minimum silence | 100ms |
| Padding | 30ms |

## Timing

For a 30-second recording, typical latency is:

| Stage | Duration |
|-------|----------|
| VAD processing | 500-1000ms |
| Compression | 100-500ms |
| API round-trip | 1500-3000ms |
| Total | 2-4 seconds |

## Configuration

Enable or disable VAD and audio archival in Settings > Behavior.
