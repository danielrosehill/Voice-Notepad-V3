# Cost Tracking

Voice Notepad provides detailed API usage tracking to help you manage costs.

## Overview

The **Cost** tab shows your API spending across different time periods and models. **OpenRouter is recommended** for the most accurate cost tracking.

## OpenRouter (Recommended)

OpenRouter provides accurate, key-specific cost data through its API:

### Key-Specific Usage

The app uses OpenRouter's `/api/v1/key` endpoint to get usage data for **your specific API key only** (not your entire account). This shows:

- Today's spend
- This week's spend
- This month's spend
- Number of requests

### Account Balance

Real-time credit balance from OpenRouter's `/api/v1/credits` endpoint. Displayed in:

- Status bar (bottom of window)
- Cost tab header

### Model Breakdown

See which models are costing the most via OpenRouter's `/api/v1/activity` endpoint. Shows the last 30 days of usage by model.

## Other Providers

For Gemini, OpenAI, and Mistral direct access, costs are **estimated** based on:

- Token counts from API responses
- Published pricing per million tokens

These estimates may not reflect actual billing due to:

- Pricing tier differences
- Promotional credits
- Rounding differences

## Status Bar Display

The status bar shows: `Today: $X.XXXX (N) | Bal: $X.XX`

- **Today** - Spend today with transcription count (N)
- **Bal** - OpenRouter credit balance (if using OpenRouter)

## Cost Tab Sections

### Balance & Usage

- OpenRouter credit balance
- API key usage by period (day/week/month)
- Number of requests

### Model Breakdown

- Spend by model (last 30 days)
- Percentage of total spend
- Number of requests per model

### Local Statistics

From the local database:

- Total transcriptions
- Total words transcribed
- Total characters
- Storage used

## Understanding Audio Costs

Audio multimodal models charge based on:

1. **Audio input tokens** - The main cost driver
2. **Text output tokens** - Usually smaller portion

### Token Estimation

Different providers tokenize audio differently:

- **Gemini**: ~25 tokens per second of audio
- **OpenAI**: Variable based on content
- **Mistral/Voxtral**: Based on audio duration

### Reducing Costs

1. **Enable VAD** - Removes silence before upload
2. **Use efficient models** - Gemini Flash Lite is cheapest
3. **Keep recordings focused** - Shorter = cheaper

## Data Storage

Cost data is stored locally:

- `~/.config/voice-notepad-v3/usage/` - Daily JSON files
- `~/.config/voice-notepad-v3/transcriptions.db` - Per-transcription costs

## Accuracy Notes

| Provider | Cost Accuracy |
|----------|---------------|
| OpenRouter | High - actual key-specific data from API |
| Gemini | Estimated - based on token counts |
| OpenAI | Estimated - based on token counts |
| Mistral | Estimated - based on token counts |

For accurate cost tracking, **use OpenRouter** as your primary provider.
