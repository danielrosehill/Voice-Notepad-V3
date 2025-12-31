# Project Planner

This directory contains feature plans and planning documents for Voice Notepad.

## Directory Structure

```
project-planner/
├── voice-notes/     # Drop voice recordings here for transcription
├── considering/     # Ideas being evaluated
├── planned/         # Approved and designed, ready for implementation
├── implemented/     # Completed features (for reference)
└── README.md
```

## Workflow

1. **Voice Notes**: Record ideas and drop audio files in `voice-notes/`
2. **Transcribe**: Use `/transcribe-voice-notes` to convert to feature plans
3. **Considering**: New plans start here for evaluation
4. **Planned**: Move here once approved and fully designed
5. **Implemented**: Move here after the feature ships

## Considering

| Feature | Priority | Description |
|---------|----------|-------------|
| [Assistive Review](considering/assistive-review.md) | High | Accessibility audit for assistive technology users |

## Planned

| Feature | Priority | Description |
|---------|----------|-------------|
| [Second Pass Processing](planned/second-pass-processing/) | Medium | LLM-based correction of transcription errors |
| [MCP Server](planned/mcp-server.md) | Medium | Built-in MCP server for AI agent interoperability |
| [Semantic Search](planned/semantic-search.md) | Medium | Find transcripts by meaning using Gemini embeddings |

## Implemented

| Feature | Version | Description |
|---------|---------|-------------|
| *None yet* | | |
