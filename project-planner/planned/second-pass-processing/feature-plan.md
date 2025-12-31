# Feature: Second Pass Processing

**Status:** Planned
**Priority:** Medium
**Complexity:** Medium-High

## Summary

Add an optional second-pass LLM processing step to correct transcription errors that slip through the initial Gemini multimodal transcription. This addresses recurring mistakes like "Claude Code" → "Clyde Code" or "Open Router" → "Open Rider" without requiring manual word replacement lists.

## Problem

The current single-pass Gemini transcription works well in general but has edge cases where it consistently mishears certain words—particularly technical terms, product names, and proper nouns. Traditional word replacement tools are:

- Clunky to maintain
- Not portable across systems
- Impossible to predict all errors in advance
- Always playing catch-up with new mistakes

## Solution

Implement a "Fix" button that sends the transcript through a second LLM pass designed to identify and correct likely transcription errors using contextual reasoning.

## Implementation Options

### Option 1: Re-send with Audio (Heavy)

Send the original audio + first transcript back to Gemini with a prompt like "You got stuff wrong, pay attention to what the user said."

**Pros:** Model can verify against actual audio
**Cons:** Slower, more expensive, may repeat same mistakes

### Option 2: Text-Only Second Pass (Preferred)

Send only the transcript text to an LLM with a prompt asking it to identify likely transcription errors based on context.

**Pros:**
- Fast (text-only, no audio upload)
- Cost-effective
- Can use contextual reasoning ("Open Rider in a coding context → Open Router")

**Cons:** No access to original audio for verification

### Option 3: Small Local Model

Use a small, fast model (Llama or similar) fine-tuned on transcription error correction.

**Pros:**
- Very fast
- No API costs
- Could run locally

**Cons:**
- Adds setup complexity (another model to install)
- Contradicts the app's cloud-first philosophy
- VAD is already local; adding more local components increases complexity

## Recommended Approach

**Option 2 with a small cloud model** (not necessarily Gemini):

1. User clicks "Fix" button after transcription
2. Transcript text sent to a fast, cheap model
3. Model identifies likely errors using context
4. Returns corrected transcript
5. Quick turnaround—should feel instant

## Preventive Mode (Future Consideration)

An option to automatically run every transcription through second-pass processing.

**Challenge:** Models are biased toward making changes. A second-pass model might "fix" things that weren't wrong, potentially degrading good transcriptions.

**Mitigation:** The prompt must emphasize "most transcripts are correct—only fix obvious errors."

## UI/UX

- **Fix Button**: Lightning-fast button in the main interface
- No prompt required from user—just click and wait
- Optional: Settings toggle for automatic second-pass on all transcriptions

## Technical Approach

```python
# New method in transcription.py
def fix_transcription(self, transcript: str) -> str:
    """Send transcript for error correction."""
    prompt = """
    The following text was transcribed from audio and may contain errors.
    Common issues include mishearing technical terms, product names, and proper nouns.

    Review the text and fix any likely transcription errors based on context.
    Only make changes where you're confident something was misheard.
    If the text appears correct, return it unchanged.

    Text to review:
    {transcript}
    """
    # Use a fast, cheap model for this
    response = self.client.generate(prompt.format(transcript=transcript))
    return response.text
```

## Files to Modify

| File | Changes |
|------|---------|
| `app/src/transcription.py` | Add `fix_transcription()` method |
| `app/src/main.py` | Add "Fix" button to UI |
| `app/src/config.py` | Add settings for second-pass model selection |

## Implementation Steps

1. [ ] Design prompt for error correction
2. [ ] Add `fix_transcription()` method to GeminiClient
3. [ ] Add "Fix" button to main UI
4. [ ] Test with known error cases (Claude Code, Open Router)
5. [ ] Evaluate different models for speed/accuracy tradeoff
6. [ ] Optional: Add automatic second-pass setting
7. [ ] Document the feature

## Open Questions

- Which model to use for second pass? (Gemini Flash Lite? Different provider?)
- Should the Fix button be visible always or only after transcription?
- How to handle cases where the "fix" makes things worse?

## Future Enhancements

- Learn from user corrections over time
- Build a personal vocabulary/context file
- Fine-tune a small model on user's specific error patterns
