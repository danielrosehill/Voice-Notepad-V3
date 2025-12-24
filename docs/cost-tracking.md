# Cost Tracking

AI Transcription Notepad tracks API usage in the Cost tab. OpenRouter provides the most accurate data because it reports actual key-specific costs from its API.

## OpenRouter

With OpenRouter, the app queries three endpoints:

- `/api/v1/key` returns usage for your specific API key (not your entire account), showing today's, this week's, and this month's spend.
- `/api/v1/credits` returns your account balance, displayed in the status bar and Cost tab.
- `/api/v1/activity` returns per-model usage for the last 30 days.

## Other Providers

For Gemini, OpenAI, and Mistral direct access, costs are estimated based on token counts and published pricing. These estimates may not reflect actual billing due to pricing tier differences, promotional credits, or rounding.

## Status Bar

The status bar shows `Today: $X.XXXX (N) | Bal: $X.XX` where N is the transcription count and Bal is your OpenRouter credit balance.

## Reducing Costs

Enable Voice Activity Detection to remove silence before upload, which reduces the audio size sent to the API. Use Gemini Flash Lite for the lowest per-transcription cost. Keep recordings focused rather than leaving long pauses.

## Local Storage

Cost data is stored in `~/.config/voice-notepad-v3/usage/` as daily JSON files. The SQLite database also stores per-transcription token counts and costs.
