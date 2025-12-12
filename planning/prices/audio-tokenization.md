# Audio Tokenization: How Providers Calculate Audio Input Tokens

*Last updated: December 2025*

## Overview

When sending audio to multimodal AI models, the audio must be converted to tokens for processing and billing. Different providers handle this conversion differently, which significantly impacts cost calculations.

## Google Gemini

### Token Conversion Rate

Gemini provides **clear, documented tokenization**:

| Media Type | Tokens per Second |
|------------|-------------------|
| Audio      | **32 tokens/sec** |
| Video      | 263 tokens/sec    |

This is a **fixed rate** regardless of audio complexity, silence, or speech density.

**Source:** [Gemini API - Understand and count tokens](https://ai.google.dev/gemini-api/docs/tokens)

### Calculation Example

For a 2-minute (120 second) audio file:
```
120 seconds × 32 tokens/sec = 3,840 tokens
```

### Cost by Model (per 1M audio input tokens)

| Model | Audio Input Price | Cost for 1 hour audio |
|-------|-------------------|----------------------|
| Gemini 2.0 Flash | $0.70 | $0.081 |
| Gemini 2.5 Flash | $1.00 | $0.115 |
| Gemini 2.5 Flash-Lite | $0.30 | $0.035 |
| Gemini 2.5 Pro | $1.25* | $0.144 |

*Gemini 2.5 Pro uses unified multimodal input pricing

### Counting Tokens Programmatically

Gemini provides a `countTokens` API endpoint:

```python
import google.generativeai as genai

model = genai.GenerativeModel("gemini-2.0-flash")
audio_file = genai.upload_file("audio.mp3")
token_count = model.count_tokens([audio_file])
print(f"Audio tokens: {token_count.total_tokens}")
```

---

## OpenAI

### Token Conversion Rate

OpenAI is **less transparent** about audio tokenization. Key findings:

- **No official tokens-per-second rate documented**
- OpenAI removed per-minute estimates because they were "very inaccurate"
- Token count appears to vary based on audio content/complexity
- Community recommendation: test in playground and check usage logs

### Inferred Rate (Approximation)

Working backward from pricing:
- Audio input: ~$0.06/minute at $100/1M tokens
- **Rough estimate: ~10 tokens/second** (but this varies)

This is significantly lower token density than Gemini, but OpenAI's per-token price is much higher.

**Source:** [OpenAI Community Discussion](https://community.openai.com/t/confusion-between-per-minute-audio-pricing-vs-token-based-audio-pricing/1073222)

### Cost by Model (Audio Tokens per 1M)

| Model | Audio Input | Audio Output |
|-------|-------------|--------------|
| gpt-4o-audio-preview | $40.00 | $80.00 |
| gpt-4o-mini-audio-preview | $10.00 | $20.00 |
| gpt-audio | $32.00 | $64.00 |
| gpt-audio-mini | $10.00 | $20.00 |
| gpt-realtime | $32.00 | $64.00 |
| gpt-realtime-mini | $10.00 | $20.00 |

### Practical Cost Estimates

Based on community testing:
- **Transcription**: ~$1.55/hour of audio
- **Audio synthesis**: ~$5.93/hour of audio

**Source:** [Azure OpenAI GPT-4o Audio Cost Analysis](https://clemenssiebler.com/posts/azure-openai-gpt4o-audio-api-cost-analysis/)

---

## Mistral (Voxtral)

### Token Conversion Rate

Mistral's Voxtral model documentation does not clearly specify tokens-per-second rates. Pricing is typically:
- Per-minute or per-request based
- Less granular token-level visibility than Gemini

---

## Comparison: Real-World Example

**Test file:** `1.mp3` (135.4 seconds / 2:15)

| Provider | Model | Est. Tokens | Est. Input Cost |
|----------|-------|-------------|-----------------|
| Gemini | gemini-2.0-flash | ~4,333 | ~$0.003 |
| OpenAI | gpt-4o-audio-preview | ~1,350* | ~$0.054 |

*OpenAI token count is approximate

### Key Insight

Despite OpenAI having ~3x fewer tokens for the same audio:
- **Gemini is ~18x cheaper** for audio input
- This is because OpenAI's per-token audio rate ($40-100/1M) is much higher than Gemini's ($0.30-1.00/1M)

---

## Recommendations for Voice Notepad V3

### Cost Optimization

1. **Gemini is significantly cheaper for audio transcription**
   - Use Gemini 2.0 Flash-Lite for maximum economy
   - Gemini 2.0 Flash offers good quality/price balance

2. **Audio preprocessing helps**
   - Downsampling to 16kHz mono reduces file size
   - Matches Gemini's internal processing format
   - Faster uploads, same token count (fixed rate)

3. **Track actual usage**
   - OpenAI: Check usage dashboard for true token counts
   - Gemini: Use `countTokens` API before submission

### Cost Estimation Formula

**Gemini:**
```
cost = (audio_seconds × 32 / 1,000,000) × model_rate_per_million
```

**OpenAI (approximation):**
```
cost ≈ audio_minutes × $0.06  # for gpt-4o-audio-preview input
```

---

## Live API / Real-time Considerations

For live/streaming audio (Gemini Live API, OpenAI Realtime):

| Provider | Audio Rate | Additional Costs |
|----------|------------|------------------|
| Gemini Live | 25 tokens/sec | Session fees may apply |
| OpenAI Realtime | Variable | Higher per-token rates |

**Note:** Live APIs may have different tokenization than batch/file upload APIs.

---

## Sources

- [Gemini API Pricing](https://ai.google.dev/gemini-api/docs/pricing)
- [Gemini Token Documentation](https://ai.google.dev/gemini-api/docs/tokens)
- [OpenAI Pricing](https://openai.com/api/pricing/)
- [OpenAI Community - Audio Token Discussion](https://community.openai.com/t/confusion-between-per-minute-audio-pricing-vs-token-based-audio-pricing/1073222)
- [Clemens Siebler - GPT-4o Audio Cost Analysis](https://clemenssiebler.com/posts/azure-openai-gpt4o-audio-api-cost-analysis/)
