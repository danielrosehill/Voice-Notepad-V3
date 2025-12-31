# Feature: Semantic Search for Transcription History

**Status:** Planned
**Priority:** Medium
**Complexity:** Medium

## Summary

Add semantic search capabilities to the transcription history, allowing users to find past transcripts by meaning rather than exact keywords. Uses Gemini's `text-embedding-004` model to generate embeddings for each transcript.

## Problem

Current search is regex-based (keyword matching only). Users can't find transcripts when they remember the topic but not the exact words used.

Example: Searching "meeting about the project deadline" won't find a transcript that says "we discussed when the milestone is due."

## Solution

1. **Generate embeddings** for each transcript using Gemini's embedding API
2. **Store embeddings** alongside transcript documents in Mongita
3. **Vector search** using cosine similarity to find semantically similar transcripts
4. **Hybrid search** combining keyword and semantic results

## Technical Approach

### Embedding Model

- **Model:** `text-embedding-004` (Gemini)
- **Dimensions:** 768 floats per embedding
- **Cost:** ~$0.00002 per 1K tokens (negligible)
- **Already have:** `google-genai` SDK and API key configured

### Database Changes

Add to `TranscriptionRecord`:
```python
embedding: Optional[List[float]] = None  # 768-dim vector
embedding_model: Optional[str] = None    # Track which model was used
```

### New Database Methods

```python
def save_embedding(self, transcript_id: str, embedding: List[float], model: str) -> bool
def semantic_search(self, query_embedding: List[float], limit: int = 10) -> List[TranscriptionRecord]
def get_unembedded_transcripts(self, limit: int = 100) -> List[TranscriptionRecord]
```

### New API Client Method

Add to `GeminiClient` in `transcription.py`:
```python
def embed_text(self, text: str) -> EmbeddingResult:
    """Generate embedding for text using text-embedding-004."""
    client = self._get_client()
    response = client.models.embed_content(
        model="text-embedding-004",
        contents=[text]
    )
    return EmbeddingResult(
        embedding=response.embeddings[0].values,
        input_tokens=response.usage_metadata.prompt_token_count
    )
```

### UI Changes

In History tab:
- Add toggle: "Keyword" / "Semantic" / "Both"
- Show similarity score for semantic results
- Visual indicator for search mode

### Background Embedding

Option 1: Embed on save (adds ~200ms to transcription flow)
Option 2: Lazy embedding (embed on first semantic search)
Option 3: Background worker (embed existing transcripts gradually)

**Recommended:** Option 1 for new transcripts + Option 3 for backfill

## Files to Modify

| File | Changes |
|------|---------|
| `database_mongo.py` | Add embedding field, semantic_search method |
| `transcription.py` | Add `embed_text()` to GeminiClient |
| `history_widget.py` | Add search mode toggle, similarity display |
| `config.py` | Add embedding model config |
| `requirements.txt` | Add `numpy` for cosine similarity |

## Storage Considerations

- Each embedding: 768 floats × 4 bytes = ~3KB
- 1,000 transcripts: ~3MB additional storage
- Mongita handles this fine; no need for specialized vector DB

## Implementation Steps

1. [ ] Add `embed_text()` method to GeminiClient
2. [ ] Update TranscriptionRecord with embedding fields
3. [ ] Add `save_embedding()` and `semantic_search()` to database
4. [ ] Create background embedding worker
5. [ ] Update History tab UI with search mode toggle
6. [ ] Add settings option to enable/disable semantic search
7. [ ] Test with various query types

## Future Enhancements

- Cluster similar transcripts automatically
- "More like this" button on transcript items
- Semantic duplicate detection
- Topic extraction and tagging
