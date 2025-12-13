# Supported Models

Voice Notepad supports audio multimodal models from several providers. These models can directly process audio input for transcription.

## OpenRouter Models

OpenRouter provides access to multiple providers through a single API key.

| Model ID | Provider | Tier | Notes |
|----------|----------|------|-------|
| `google/gemini-2.5-flash` | Gemini | Standard | Recommended default |
| `google/gemini-2.5-flash-lite` | Gemini | Budget | Fastest/cheapest |
| `google/gemini-2.0-flash-001` | Gemini | Standard | Previous generation |
| `openai/gpt-4o-audio-preview` | OpenAI | Premium | Highest quality |
| `mistralai/voxtral-small-24b-2507` | Mistral | Standard | Mistral's audio model |

## Gemini Models (Direct)

Using the Gemini API directly:

| Model ID | Tier | Notes |
|----------|------|-------|
| `gemini-flash-latest` | Dynamic | Always latest Flash model |
| `gemini-2.5-flash` | Standard | Stable release |
| `gemini-2.5-flash-lite` | Budget | Lite version |
| `gemini-2.5-pro` | Premium | Pro tier |

## OpenAI Models (Direct)

Using the OpenAI API directly:

| Model ID | Tier | Notes |
|----------|------|-------|
| `gpt-4o-audio-preview` | Premium | Full audio capabilities |
| `gpt-4o-mini-audio-preview` | Budget | Smaller, faster |
| `gpt-audio` | Premium | Alias for preview |
| `gpt-audio-mini` | Budget | Alias for mini |

## Mistral Models (Direct)

Using the Mistral API directly:

| Model ID | Tier | Notes |
|----------|------|-------|
| `voxtral-small-latest` | Standard | Standard Voxtral |
| `voxtral-mini-latest` | Budget | Smaller/faster |

## Choosing a Model

### For Most Users

**Recommended**: OpenRouter with `google/gemini-2.5-flash`

- Good balance of quality and cost
- Fast processing
- Accurate transcription

### For Budget-Conscious Users

Use Gemini Flash Lite variants:

- `google/gemini-2.5-flash-lite` (via OpenRouter)
- `gemini-2.5-flash-lite` (direct)

### For Highest Quality

Use GPT-4o audio:

- `openai/gpt-4o-audio-preview` (via OpenRouter)
- `gpt-4o-audio-preview` (direct)

## Model Tiers

Models are categorized into tiers:

| Tier | Characteristics |
|------|-----------------|
| **Premium** | Highest quality, higher cost |
| **Standard** | Good balance of quality and cost |
| **Budget** | Lower cost, still good quality |

## Changing Models

### Default Model

Set your default model in **Settings > Models** for each provider.

### Per-Transcription

Select the model from the toolbar dropdown before recording.

## Model Information

The **Models** tab in the app shows:

- Available models by provider
- Model tier indicators
- Current selection status

## Adding New Models

The model list is maintained in the app source. If a provider adds new audio-capable models, they can be added by updating `transcription.py`.

For providers not yet supported, open an issue or PR on GitHub.
