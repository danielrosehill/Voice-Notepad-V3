# Feature: Built-in MCP Server

**Status:** Planned
**Priority:** Medium
**Complexity:** Medium-High

## Summary

Voice Notepad will function as an MCP (Model Context Protocol) server, exposing its transcription history and transcription generation capabilities to external AI agents. This enables AI tooling to programmatically request transcriptions and query the transcript database.

## Problem

Currently, Voice Notepad operates as a standalone desktop application. AI agents and automation workflows cannot directly interact with it to:
- Request transcriptions of audio files
- Query the transcription history database
- Integrate voice transcription into multi-agent workflows

## Solution

Implement an MCP server within Voice Notepad that exposes:
1. **Transcription generation** - Accept audio file paths and return cleaned transcripts
2. **History access** - Query and search the transcription database
3. **Status information** - Current configuration, costs, model availability

## Scope & Limitations

**In Scope:**
- File-based transcription (agent provides path to audio file)
- Transcription history queries
- Configuration/status endpoints

**Out of Scope:**
- Live recording control (programmatic recording would require the agent to manage audio capture, which is outside MCP's design)
- Real-time streaming transcription

The MCP interface is designed for **file-based workflows** where an AI agent has already captured or received an audio file and needs it transcribed.

## Technical Approach

### MCP Server Implementation

Voice Notepad will run an MCP server (likely stdio-based for local use, with optional SSE for network access).

### Exposed Tools

```python
# Tool: transcribe_file
{
    "name": "transcribe_file",
    "description": "Transcribe an audio file using Voice Notepad's AI-powered cleanup",
    "parameters": {
        "file_path": "Absolute path to audio file (WAV, MP3, OGG, FLAC)",
        "format_preset": "Optional: email, todo, meeting_notes, general (default)",
        "formality": "Optional: casual, neutral, professional (default: neutral)",
        "model": "Optional: model override (default: configured model)"
    }
}

# Tool: search_history
{
    "name": "search_history",
    "description": "Search transcription history by keyword or semantic similarity",
    "parameters": {
        "query": "Search query text",
        "mode": "keyword | semantic | both (default: keyword)",
        "limit": "Maximum results (default: 10)"
    }
}

# Tool: get_transcript
{
    "name": "get_transcript",
    "description": "Retrieve a specific transcript by ID",
    "parameters": {
        "transcript_id": "Database ID of the transcript"
    }
}

# Tool: get_status
{
    "name": "get_status",
    "description": "Get Voice Notepad status and configuration",
    "parameters": {}
}
```

### Resources (Read-only Data)

```python
# Resource: recent_transcripts
{
    "uri": "voice-notepad://transcripts/recent",
    "description": "List of recent transcriptions with metadata"
}

# Resource: daily_stats
{
    "uri": "voice-notepad://stats/daily",
    "description": "Today's transcription statistics and costs"
}
```

### Architecture Options

**Option A: Embedded Server (Recommended)**
- MCP server runs within the PyQt6 application process
- Shares database and configuration with the UI
- Starts/stops with the application
- Lower complexity, single process

**Option B: Separate Daemon**
- Standalone MCP server process
- Can run headless without the UI
- More complex but allows transcription without GUI

### Integration with Existing Code

The MCP server would reuse existing modules:
- `transcription.py` - GeminiClient for actual transcription
- `database_mongo.py` - History queries
- `audio_processor.py` - Audio preprocessing (AGC, VAD)
- `config.py` - Settings access

## Use Cases

1. **AI Agent Workflows**: An agent records audio via another tool, then uses Voice Notepad MCP to transcribe and clean it

2. **Batch Processing**: Process a folder of audio files through Voice Notepad's cleanup pipeline

3. **Integration with Note Systems**: AI assistant queries transcription history to find relevant past notes

4. **Voice Command Systems**: External voice capture system sends files for high-quality transcription

## Files to Create/Modify

| File | Changes |
|------|---------|
| `app/src/mcp_server.py` | New: MCP server implementation |
| `app/src/main.py` | Start/stop MCP server with application |
| `app/src/config.py` | MCP server settings (port, enabled, etc.) |
| `app/requirements.txt` | Add `mcp` package |

## Implementation Steps

1. [ ] Add `mcp` package to requirements
2. [ ] Create `mcp_server.py` with basic stdio server
3. [ ] Implement `transcribe_file` tool
4. [ ] Implement `search_history` tool
5. [ ] Implement `get_transcript` tool
6. [ ] Implement `get_status` tool
7. [ ] Add MCP resources for recent transcripts and stats
8. [ ] Integrate server startup into main application
9. [ ] Add Settings UI for MCP configuration
10. [ ] Test with Claude Code and other MCP clients
11. [ ] Document MCP server setup and usage

## Configuration

New settings in `config.json`:
```json
{
    "mcp": {
        "enabled": true,
        "transport": "stdio",
        "name": "voice-notepad"
    }
}
```

## Future Enhancements

- SSE transport for network access
- Authentication for remote connections
- Prompt/template selection via MCP
- Cost budget limits for agent usage
- Webhook notifications on transcription complete
