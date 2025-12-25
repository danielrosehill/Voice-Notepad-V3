"""Transcription API clients for Gemini (direct) and OpenRouter."""

import base64
import tempfile
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


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


class GeminiClient(TranscriptionClient):
    """Google Gemini API client for audio transcription."""

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash-lite"):
        self.api_key = api_key
        self.model = model
        self._client = None

    def _get_client(self):
        if self._client is None:
            from google import genai
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def transcribe(self, audio_data: bytes, prompt: str) -> TranscriptionResult:
        """Transcribe audio using Gemini's multimodal capabilities."""
        client = self._get_client()
        from google.genai import types

        response = client.models.generate_content(
            model=self.model,
            contents=[
                prompt,
                types.Part.from_bytes(data=audio_data, mime_type="audio/wav")
            ]
        )

        # Extract usage metadata
        input_tokens = 0
        output_tokens = 0
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            input_tokens = getattr(response.usage_metadata, 'prompt_token_count', 0) or 0
            output_tokens = getattr(response.usage_metadata, 'candidates_token_count', 0) or 0

        return TranscriptionResult(
            text=response.text,
            input_tokens=input_tokens,
            output_tokens=output_tokens
        )

    def rewrite_text(self, text: str, instruction: str) -> TranscriptionResult:
        """Rewrite text using Gemini (text-only, no audio)."""
        client = self._get_client()

        prompt = f"{instruction}\n\nText to rewrite:\n{text}"

        response = client.models.generate_content(
            model=self.model,
            contents=[prompt]
        )

        # Extract usage metadata
        input_tokens = 0
        output_tokens = 0
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            input_tokens = getattr(response.usage_metadata, 'prompt_token_count', 0) or 0
            output_tokens = getattr(response.usage_metadata, 'candidates_token_count', 0) or 0

        return TranscriptionResult(
            text=response.text,
            input_tokens=input_tokens,
            output_tokens=output_tokens
        )

    def generate_title(self, text: str) -> str:
        """Generate a short title using Gemini with output constraints."""
        client = self._get_client()
        from google.genai import types

        prompt = (
            "Generate a short, descriptive title for the following text. "
            "The title should be 3-6 words, suitable for a filename (no special characters). "
            "Respond with ONLY the title, no explanations or punctuation at the end.\n\n"
            f"Text:\n{text[:1000]}"  # Limit to first 1000 chars for efficiency
        )

        response = client.models.generate_content(
            model=self.model,
            contents=[prompt],
            config=types.GenerateContentConfig(
                response_mime_type="text/plain",
                max_output_tokens=20,  # Keep titles short
            )
        )

        # Clean up title: remove quotes, periods, and sanitize for filename
        title = response.text.strip().strip('"\'.,!?')
        # Replace spaces with underscores and remove special chars
        title = ''.join(c if c.isalnum() or c in ' -_' else '' for c in title)
        title = '_'.join(title.split())  # Replace spaces with underscores
        return title or "untitled"


class OpenRouterClient(TranscriptionClient):
    """OpenRouter API client for audio transcription (OpenAI-compatible)."""

    OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(self, api_key: str, model: str = "google/gemini-2.5-flash"):
        self.api_key = api_key
        self.model = model
        self._client = None

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI
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
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
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

        # If cost not in response, try to fetch from generation endpoint
        if actual_cost is None and generation_id:
            try:
                from .openrouter_api import get_openrouter_api
                api = get_openrouter_api(self.api_key)
                gen_usage = api.get_generation_usage(generation_id)
                if gen_usage:
                    actual_cost = gen_usage.cost
            except Exception:
                pass  # Fall back to estimated cost

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

        # Try to fetch cost from generation endpoint if not in response
        if actual_cost is None and generation_id:
            try:
                from .openrouter_api import get_openrouter_api
                api = get_openrouter_api(self.api_key)
                gen_usage = api.get_generation_usage(generation_id)
                if gen_usage:
                    actual_cost = gen_usage.cost
            except Exception:
                pass

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


def get_client(provider: str, api_key: str, model: str) -> TranscriptionClient:
    """Factory function to get appropriate transcription client.

    Supported providers:
    - "gemini": Direct Google Gemini API (recommended for gemini-flash-latest)
    - "openrouter": OpenRouter API (access to Gemini models via OpenAI-compatible API)
    """
    if provider == "gemini":
        return GeminiClient(api_key, model)
    elif provider == "openrouter":
        return OpenRouterClient(api_key, model)
    else:
        raise ValueError(f"Unknown provider: {provider}. Supported: gemini, openrouter")
