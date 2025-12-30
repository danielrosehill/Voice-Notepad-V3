# Audio Pipeline

AI Transcription Notepad processes audio through several stages before sending it to AI models.

## Overview

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Recording  │───▶│     AGC     │───▶│     VAD     │───▶│ Compression │───▶│  API Call   │
│  (PyAudio)  │    │  (Normalize)│    │ (TEN VAD)   │    │  (16kHz)    │    │  (Gemini)   │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
     48kHz              ±20dB          Remove silence      Downsample         Transcribe
```

## Pipeline Stages

### 1. Recording (`audio_recorder.py`)

- **Format**: 16-bit PCM, mono
- **Sample rate**: Device native (typically 44.1kHz or 48kHz)
- **Library**: PyAudio
- **Features**: Automatic sample rate negotiation, microphone disconnect handling

### 2. Automatic Gain Control (`audio_processor.py`)

Normalizes audio levels for consistent transcription accuracy.

| Parameter | Value | Description |
|-----------|-------|-------------|
| Target peak | -3 dBFS | Leaves headroom while ensuring good signal |
| Minimum threshold | -40 dBFS | Skip AGC if audio is quieter (noise floor) |
| Maximum gain | +20 dB | Prevents over-amplification |

**Behavior**: Only boosts quiet audio—never attenuates loud audio.

### 3. Voice Activity Detection (`vad_processor.py`)

Removes silence segments before API upload to reduce costs and improve accuracy.

**Engine**: [TEN VAD](https://github.com/TEN-framework/ten-vad) (Apache 2.0)

TEN VAD was chosen over alternatives (Silero VAD, WebRTC VAD) for:
- Smaller footprint (~306KB vs ~2.2MB for Silero)
- Faster speech-to-silence transition detection
- Lower latency for real-time processing
- No model download required (bundled with pip package)

| Parameter | Value | Description |
|-----------|-------|-------------|
| Sample rate | 16kHz | Required by TEN VAD |
| Hop size | 256 samples | ~16ms analysis windows |
| Threshold | 0.5 | Speech probability threshold |
| Min speech duration | 250ms | Ignore speech shorter than this |
| Min silence duration | 100ms | Ignore silence shorter than this |
| Padding | 30ms | Buffer around speech segments |

### 4. Compression (`audio_processor.py`)

- **Output**: 16kHz mono WAV
- **Reduction**: ~66% smaller than 48kHz stereo input
- **Quality**: No perceptible loss for speech transcription (matches Gemini's internal format)

### 5. API Submission (`transcription.py`)

- Audio is base64-encoded and sent with the cleanup prompt
- Supports Gemini Direct API and OpenRouter
- Returns transcript, token counts, and cost data

### 6. Storage (`database_mongo.py`)

- **Transcripts**: Saved to Mongita (MongoDB-compatible local database)
- **Audio archive** (optional): Opus format at ~24kbps (~180KB per minute)

## Performance Benchmarks

Benchmarked on **Intel Core i7-12700F** (12th Gen, 12 cores).

### VAD Processing Time

| Audio Length | Processing Time | Real-Time Factor | Speed |
|--------------|-----------------|------------------|-------|
| 5 seconds | 63ms | 0.013 | 80x faster than real-time |
| 10 seconds | 131ms | 0.013 | 76x faster than real-time |
| 30 seconds | 436ms | 0.015 | 69x faster than real-time |
| 60 seconds | 864ms | 0.014 | 69x faster than real-time |

**Average RTF**: 0.014 (adds ~14ms per second of audio)

### Silence Reduction

With typical dictation patterns (speech with pauses):

| Scenario | Original | After VAD | Reduction |
|----------|----------|-----------|-----------|
| Continuous speech | 30s | 28s | 7% |
| Speech with pauses | 30s | 15s | 50% |
| Long pauses/thinking | 30s | 6s | 80% |

### End-to-End Latency

For a typical 30-second recording:

| Stage | Duration | Notes |
|-------|----------|-------|
| VAD processing | ~400ms | Scales linearly with audio length |
| Compression | ~100ms | Resampling to 16kHz |
| API round-trip | 1500-3000ms | Depends on network and model |
| **Total** | **2-3.5 seconds** | VAD overhead is negligible |

### CPU Impact

- **VAD**: Negligible (~1% CPU during processing)
- **Processing is 70x faster than real-time**, so CPU usage is brief
- No GPU required—runs entirely on CPU

## Configuration

VAD can be toggled via the checkbox on the main recording page, or in Settings → Behavior.

Audio archival is configured in Settings → Behavior → Archive audio recordings.

## System Requirements

**Linux**: TEN VAD requires `libc++1`:
```bash
sudo apt install libc++1
```

## Source Files

| File | Purpose |
|------|---------|
| `audio_recorder.py` | PyAudio recording with device management |
| `audio_processor.py` | AGC, compression, Opus archival |
| `vad_processor.py` | TEN VAD integration |
| `transcription.py` | API clients for Gemini and OpenRouter |
