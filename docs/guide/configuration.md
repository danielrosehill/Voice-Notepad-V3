# Configuration

AI Transcription Notepad stores settings in `~/.config/voice-notepad-v3/`.

## API Keys

You need an API key for at least one provider. OpenRouter is recommended because it provides access to multiple models through a single key with accurate cost tracking.

Set keys via environment variables:

```bash
OPENROUTER_API_KEY=your_key  # Recommended
GEMINI_API_KEY=your_key
OPENAI_API_KEY=your_key
MISTRAL_API_KEY=your_key
```

Or configure them in Settings > API Keys within the app.

## Providers

**OpenRouter** proxies requests to multiple providers through a single API. You get access to Gemini, GPT-4o, and Voxtral models without managing separate keys. OpenRouter also provides accurate per-key cost tracking.

**Gemini** (direct) offers gemini-flash-latest, gemini-2.5-flash, gemini-2.5-flash-lite, and gemini-2.5-pro.

**OpenAI** (direct) offers gpt-4o-audio-preview and gpt-4o-mini-audio-preview.

**Mistral** (direct) offers voxtral-small-latest and voxtral-mini-latest.

## Behavior Settings

**Voice Activity Detection** removes silence from audio before sending to the API. This reduces file size and API costs. Uses [TEN VAD](https://github.com/TEN-framework/ten-vad), a lightweight native library bundled with the application. Enable in Settings > Behavior.

**Automatic Gain Control** normalizes audio levels for consistent transcription accuracy. Boosts quiet audio (up to +20dB) while leaving loud audio unchanged. Enable in Settings > Behavior.

**Audio Archival** saves recordings in Opus format (~24kbps) to `~/.config/voice-notepad-v3/audio-archive/`. A one-minute recording uses about 180KB.

## Cleanup Prompt

The cleanup prompt instructs the AI how to process your transcription. The default removes filler words, adds punctuation and paragraph spacing, follows verbal instructions in the recording, and returns markdown. Customize in Settings > Prompt.

## Storage Locations

Settings and data are stored in `~/.config/voice-notepad-v3/`:

- `config.json` - API keys and preferences
- `mongita/` - MongoDB-compatible transcript database
- `usage/` - Daily cost tracking
- `audio-archive/` - Opus recordings (if enabled)
