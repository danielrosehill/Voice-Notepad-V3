# Supported Models

AI Transcription Notepad uses Google Gemini models exclusively for audio transcription. These models can be accessed either directly through the Google AI API or via OpenRouter.

## Google Gemini Models Reference

The same underlying Gemini models are available through both providers, but with different endpoint names:

| Google Direct | OpenRouter | Tier | Notes |
|---------------|------------|------|-------|
| `gemini-flash-latest` | *(not available)* | Dynamic | Always points to latest Flash - **recommended** |
| `gemini-2.5-flash` | `google/gemini-2.5-flash` | Standard | Current stable release |
| `gemini-2.5-flash-lite` | `google/gemini-2.5-flash-lite` | Budget | Fastest and cheapest |
| `gemini-2.5-pro` | `google/gemini-2.5-pro` | Premium | Pro tier |
| *(n/a)* | `google/gemini-2.0-flash-001` | Standard | Previous generation |

## Provider Comparison

### Gemini Direct (Recommended)

Direct access to Google's Gemini API offers:

- **Dynamic `gemini-flash-latest` endpoint** - Always points to Google's latest Flash model, eliminating manual updates when new versions release
- Lower latency (no proxy layer)
- Simpler billing through Google Cloud

### OpenRouter

OpenRouter proxies requests through an OpenAI-compatible API:

- Unified billing across multiple providers
- Accurate per-key cost tracking via `/api/v1/key` endpoint
- No access to the dynamic `gemini-flash-latest` endpoint

**Note:** OpenRouter model names use the `google/` prefix (e.g., `google/gemini-2.5-flash`) while Google Direct uses the model name directly (e.g., `gemini-2.5-flash`).

## Choosing a Model

For most users, **Gemini Direct with `gemini-flash-latest`** is recommended. This ensures you always use Google's latest Flash model without manual configuration changes.

If you prefer OpenRouter's unified billing or cost tracking features, use `google/gemini-2.5-flash` as your default.

For lowest costs, use Flash Lite variants (`gemini-2.5-flash-lite` or `google/gemini-2.5-flash-lite`).

Set your default model in Settings > Models, or select per-transcription from the toolbar dropdown.
