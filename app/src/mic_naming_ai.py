"""AI-powered microphone name generation using OpenRouter."""

import os
from typing import Optional
import requests


class MicrophoneNamingAI:
    """Uses AI to generate friendly microphone names from device names."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize with OpenRouter API key.

        Args:
            api_key: OpenRouter API key. Falls back to OPENROUTER_API_KEY env var.
        """
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
        self.base_url = "https://openrouter.ai/api/v1"
        # Use a fast, cheap model for simple text generation
        self.model = "google/gemini-2.5-flash-lite"

    def generate_nickname(self, device_name: str) -> Optional[str]:
        """Generate a friendly nickname for a microphone device.

        Args:
            device_name: Full device name from PyAudio (e.g., "Samson Q2U Microphone: USB Audio")

        Returns:
            Friendly nickname (e.g., "Q2U") or None on error
        """
        if not self.api_key:
            return None

        prompt = self._build_prompt(device_name)

        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt,
                        }
                    ],
                    "temperature": 0.3,  # Low temperature for consistent naming
                    "max_tokens": 20,     # Short response
                },
                timeout=10,
            )
            response.raise_for_status()

            data = response.json()
            if "choices" in data and len(data["choices"]) > 0:
                nickname = data["choices"][0]["message"]["content"].strip()
                # Remove quotes if AI wrapped response in them
                nickname = nickname.strip('"\'')
                return nickname if nickname else None

        except Exception as e:
            print(f"Error generating microphone nickname: {e}")
            return None

    def generate_nicknames_batch(self, device_names: list[str]) -> dict[str, str]:
        """Generate nicknames for multiple devices in a single API call.

        Args:
            device_names: List of device names

        Returns:
            Dictionary mapping device names to nicknames
        """
        if not self.api_key or not device_names:
            return {}

        prompt = self._build_batch_prompt(device_names)

        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt,
                        }
                    ],
                    "temperature": 0.3,
                    "max_tokens": 200,
                },
                timeout=15,
            )
            response.raise_for_status()

            data = response.json()
            if "choices" in data and len(data["choices"]) > 0:
                content = data["choices"][0]["message"]["content"].strip()
                return self._parse_batch_response(content, device_names)

        except Exception as e:
            print(f"Error generating microphone nicknames: {e}")
            return {}

    def _build_prompt(self, device_name: str) -> str:
        """Build prompt for single device naming."""
        return f"""Generate a short, friendly nickname (2-4 words max) for this microphone device:

Device name: {device_name}

Rules:
- Extract the key identifying information (brand/model)
- Make it short and memorable
- Remove technical suffixes like "USB Audio", "Microphone", etc.
- Examples:
  - "Samson Q2U Microphone: USB Audio" → "Q2U"
  - "Blue Yeti USB Microphone" → "Blue Yeti"
  - "Logitech H390 Headset: USB Audio" → "H390 Headset"
  - "Built-in Audio Analog Stereo" → "Built-in"

Output ONLY the nickname, nothing else."""

    def _build_batch_prompt(self, device_names: list[str]) -> str:
        """Build prompt for batch device naming."""
        devices_list = "\n".join(f"{i+1}. {name}" for i, name in enumerate(device_names))

        return f"""Generate short, friendly nicknames (2-4 words max) for these microphone devices:

{devices_list}

Rules:
- Extract the key identifying information (brand/model)
- Make it short and memorable
- Remove technical suffixes like "USB Audio", "Microphone", etc.
- Examples:
  - "Samson Q2U Microphone: USB Audio" → "Q2U"
  - "Blue Yeti USB Microphone" → "Blue Yeti"
  - "Logitech H390 Headset: USB Audio" → "H390 Headset"
  - "Built-in Audio Analog Stereo" → "Built-in"

Output format (one per line, matching the numbering above):
1. nickname1
2. nickname2
3. nickname3
etc.

Output ONLY the numbered list, nothing else."""

    def _parse_batch_response(self, content: str, device_names: list[str]) -> dict[str, str]:
        """Parse batch response into device name → nickname mapping."""
        result = {}
        lines = content.strip().split("\n")

        for i, line in enumerate(lines):
            if i >= len(device_names):
                break

            # Remove numbering prefix (e.g., "1. " or "1) ")
            nickname = line.strip()
            if ". " in nickname:
                nickname = nickname.split(". ", 1)[1]
            elif ") " in nickname:
                nickname = nickname.split(") ", 1)[1]

            nickname = nickname.strip('"\'')  # Remove quotes

            if nickname:
                result[device_names[i]] = nickname

        return result
