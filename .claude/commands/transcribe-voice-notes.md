# Transcribe Voice Notes to Feature Plans

Transcribe voice note recordings from `project-planner/voice-notes/` into formatted feature plan documents.

## Instructions

1. Look for audio files (MP3, WAV, OGG, FLAC, Opus) in `project-planner/voice-notes/`
   - For Opus files, convert to WAV first using ffmpeg:
     `ffmpeg -i input.opus -ar 16000 -ac 1 output.wav`

2. For each audio file, use the Gemini transcription MCP to transcribe it:
   - Use `mcp__gemini-transcription__transcribe_audio` for cleaned transcript
   - Use `mcp__gemini-transcription__transcribe_audio_raw` for raw transcript
   - Pass the absolute file path

3. Create a subfolder in the appropriate status directory (usually `project-planner/planned/`) with:
   - `transcript-raw.md` - The raw/verbatim transcript
   - `transcript-cleaned.md` - The cleaned/edited transcript
   - `feature-plan.md` - The structured feature plan document

4. Transform the transcription into a feature plan document using this template:

```markdown
# Feature: [Feature Name]

**Status:** Considering | Planned
**Priority:** Low | Medium | High
**Complexity:** Low | Medium | High

## Summary

[One paragraph describing the feature]

## Problem

[What problem does this solve?]

## Solution

[High-level approach]

## Technical Approach

[Implementation details - expand on any technical points from the voice note]

## Files to Modify

| File | Changes |
|------|---------|
| `file.py` | Description of changes |

## Implementation Steps

1. [ ] Step 1
2. [ ] Step 2

## Notes from Voice Recording

[Include any raw ideas or considerations mentioned that don't fit above]
```

5. Update `project-planner/README.md` to add the new plan to the appropriate table

## Output Location

- Feature plans go to: `project-planner/considering/` or `project-planner/planned/` (NOT `private/planning/`)
- These are PUBLIC plans intended to be shared in the repository

## User Request

$ARGUMENTS
