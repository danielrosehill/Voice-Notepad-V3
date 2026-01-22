"""Transcription API client using OpenRouter."""

import base64
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

try:
    from openai import OpenAI
    OPENAI_SDK_AVAILABLE = True
except ImportError:
    OpenAI = None
    OPENAI_SDK_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class TranscriptionResult:
    """Result from transcription API including usage data."""
    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    actual_cost: Optional[float] = None  # Actual cost from provider (OpenRouter)
    generation_id: Optional[str] = None  # Generation ID for usage lookup


class TranscriptionClient(ABC):
    """Base class for transcription clients."""

    @abstractmethod
    def transcribe(self, audio_data: bytes, prompt: str) -> TranscriptionResult:
        """Transcribe audio with cleanup prompt."""
        pass

    @abstractmethod
    def rewrite_text(self, text: str, instruction: str) -> TranscriptionResult:
        """Rewrite text with given instruction (no audio)."""
        pass

    @abstractmethod
    def generate_title(self, text: str) -> str:
        """Generate a short title for the given text."""
        pass


class OpenRouterClient(TranscriptionClient):
    """OpenRouter API client for audio transcription (OpenAI-compatible).

    This is the sole transcription backend. All models (including Gemini)
    are accessed through OpenRouter's unified API.
    """

    OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(self, api_key: str, model: str = "google/gemini-3-flash-preview"):
        self.api_key = api_key
        self.model = model
        self._client = None

    def _get_client(self):
        if self._client is None:
            if not OPENAI_SDK_AVAILABLE:
                raise ImportError("openai package not installed")
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.OPENROUTER_BASE_URL,
            )
        return self._client

    def transcribe(self, audio_data: bytes, prompt: str) -> TranscriptionResult:
        """Transcribe audio using OpenRouter's multimodal models."""
        client = self._get_client()

        # Encode audio as base64
        audio_b64 = base64.b64encode(audio_data).decode("utf-8")

        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": prompt
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Transcribe and clean up this audio recording."},
                        {
                            "type": "input_audio",
                            "input_audio": {
                                "data": audio_b64,
                                "format": "wav"
                            }
                        }
                    ]
                }
            ],
            # Request usage information including cost
            extra_body={"usage": {"include": True}},
        )

        # Extract usage data
        input_tokens = 0
        output_tokens = 0
        actual_cost = None
        generation_id = None

        # Get generation ID for usage lookup
        if hasattr(response, 'id') and response.id:
            generation_id = response.id

        if hasattr(response, 'usage') and response.usage:
            input_tokens = getattr(response.usage, 'prompt_tokens', 0) or 0
            output_tokens = getattr(response.usage, 'completion_tokens', 0) or 0
            # OpenRouter includes cost in usage when requested
            if hasattr(response.usage, 'cost'):
                actual_cost = getattr(response.usage, 'cost', None)

        # Note: We no longer fetch cost per-transcription to minimize latency.
        # Cost is estimated from tokens using MODEL_PRICING in cost_tracker.py.
        # Actual spend is polled periodically via OpenRouter's /key endpoint.

        return TranscriptionResult(
            text=response.choices[0].message.content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            actual_cost=actual_cost,
            generation_id=generation_id,
        )

    def rewrite_text(self, text: str, instruction: str) -> TranscriptionResult:
        """Rewrite text using OpenRouter (text-only, no audio)."""
        client = self._get_client()

        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": instruction
                },
                {
                    "role": "user",
                    "content": text
                }
            ],
            extra_body={"usage": {"include": True}},
        )

        # Extract usage data
        input_tokens = 0
        output_tokens = 0
        actual_cost = None
        generation_id = None

        if hasattr(response, 'id') and response.id:
            generation_id = response.id

        if hasattr(response, 'usage') and response.usage:
            input_tokens = getattr(response.usage, 'prompt_tokens', 0) or 0
            output_tokens = getattr(response.usage, 'completion_tokens', 0) or 0
            if hasattr(response.usage, 'cost'):
                actual_cost = getattr(response.usage, 'cost', None)

        return TranscriptionResult(
            text=response.choices[0].message.content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            actual_cost=actual_cost,
            generation_id=generation_id,
        )

    def generate_title(self, text: str) -> str:
        """Generate a short title using OpenRouter."""
        client = self._get_client()

        prompt = (
            "Generate a short, descriptive title for the following text. "
            "The title should be 3-6 words, suitable for a filename (no special characters). "
            "Respond with ONLY the title, no explanations or punctuation at the end."
        )

        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": text[:1000]}
            ],
            max_tokens=20
        )

        # Clean up title
        title = response.choices[0].message.content.strip().strip('"\'.,!?')
        title = ''.join(c if c.isalnum() or c in ' -_' else '' for c in title)
        title = '_'.join(title.split())
        return title or "untitled"


def get_client(api_key: str, model: str) -> TranscriptionClient:
    """Factory function to get transcription client.

    All transcription uses OpenRouter as the sole backend.
    Gemini and other models are accessed through OpenRouter's unified API.
    """
    return OpenRouterClient(api_key, model)
