"""OpenRouter API client for credits, balance, and usage tracking."""

import httpx
import threading
import time
from dataclasses import dataclass, field
from typing import Optional, Callable


OPENROUTER_API_BASE = "https://openrouter.ai/api/v1"

# Cache settings
CACHE_TTL_SECONDS = 60  # How long to cache balance/credits


@dataclass
class OpenRouterCredits:
    """OpenRouter credit balance information."""
    total_credits: float
    total_usage: float

    @property
    def balance(self) -> float:
        """Current available balance."""
        return self.total_credits - self.total_usage


@dataclass
class GenerationUsage:
    """Detailed usage for a specific generation."""
    generation_id: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost: float  # Actual cost charged to account
    cached_tokens: int = 0
    audio_tokens: int = 0
    reasoning_tokens: int = 0


@dataclass
class KeyInfo:
    """API key information and usage statistics."""
    label: str
    usage: float  # Total usage for this key
    usage_daily: float
    usage_weekly: float
    usage_monthly: float
    limit: Optional[float] = None
    limit_remaining: Optional[float] = None
    is_free_tier: bool = False


@dataclass
class ActivityEntry:
    """A single activity entry from the activity endpoint."""
    date: str
    model: str
    model_permaslug: str
    provider_name: str
    usage: float
    requests: int
    prompt_tokens: int
    completion_tokens: int
    reasoning_tokens: int = 0


@dataclass
class ActivityData:
    """Activity data grouped by model."""
    entries: list[ActivityEntry] = field(default_factory=list)

    def get_model_breakdown(self) -> list[dict]:
        """Get usage breakdown by model."""
        model_totals: dict[str, dict] = {}
        for entry in self.entries:
            key = entry.model
            if key not in model_totals:
                model_totals[key] = {
                    "model": entry.model,
                    "provider": entry.provider_name,
                    "usage": 0.0,
                    "requests": 0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                }
            model_totals[key]["usage"] += entry.usage
            model_totals[key]["requests"] += entry.requests
            model_totals[key]["prompt_tokens"] += entry.prompt_tokens
            model_totals[key]["completion_tokens"] += entry.completion_tokens
        return sorted(model_totals.values(), key=lambda x: x["usage"], reverse=True)

    @property
    def total_usage(self) -> float:
        """Total usage across all entries."""
        return sum(e.usage for e in self.entries)

    @property
    def total_requests(self) -> int:
        """Total requests across all entries."""
        return sum(e.requests for e in self.entries)


class OpenRouterAPI:
    """Client for OpenRouter-specific API endpoints."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._client: Optional[httpx.Client] = None
        self._lock = threading.Lock()
        # Cache for credits
        self._credits_cache: Optional[OpenRouterCredits] = None
        self._credits_cache_time: float = 0
        # Cache for key info
        self._key_info_cache: Optional[KeyInfo] = None
        self._key_info_cache_time: float = 0
        # Background fetch state
        self._fetch_in_progress = False

    def _get_client(self) -> httpx.Client:
        """Get HTTP client, creating if needed."""
        if self._client is None:
            self._client = httpx.Client(
                base_url=OPENROUTER_API_BASE,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=10.0,  # Reduced timeout for responsiveness
            )
        return self._client

    def get_credits(self, use_cache: bool = True) -> Optional[OpenRouterCredits]:
        """
        Fetch current credit balance from OpenRouter.

        Args:
            use_cache: If True, return cached value if available and fresh

        Returns None if the request fails.
        Note: Values are cached for up to 60 seconds.
        """
        # Check cache first
        if use_cache and self._credits_cache is not None:
            age = time.time() - self._credits_cache_time
            if age < CACHE_TTL_SECONDS:
                return self._credits_cache

        try:
            client = self._get_client()
            response = client.get("/credits")
            response.raise_for_status()
            data = response.json()

            credits_data = data.get("data", {})
            credits = OpenRouterCredits(
                total_credits=credits_data.get("total_credits", 0.0),
                total_usage=credits_data.get("total_usage", 0.0),
            )

            # Update cache
            with self._lock:
                self._credits_cache = credits
                self._credits_cache_time = time.time()

            return credits
        except Exception as e:
            print(f"Failed to fetch OpenRouter credits: {e}")
            # Return stale cache if available
            return self._credits_cache

    def get_credits_async(self, callback: Callable[[Optional[OpenRouterCredits]], None]):
        """
        Fetch credits in background thread and call callback with result.

        This prevents blocking the UI while fetching balance.
        """
        # Return cached value immediately if fresh
        if self._credits_cache is not None:
            age = time.time() - self._credits_cache_time
            if age < CACHE_TTL_SECONDS:
                callback(self._credits_cache)
                return

        # Don't start multiple fetches
        with self._lock:
            if self._fetch_in_progress:
                # Return stale cache while fetch is in progress
                callback(self._credits_cache)
                return
            self._fetch_in_progress = True

        def fetch():
            try:
                result = self.get_credits(use_cache=False)
                callback(result)
            finally:
                with self._lock:
                    self._fetch_in_progress = False

        thread = threading.Thread(target=fetch, daemon=True)
        thread.start()

    def get_generation_usage(self, generation_id: str) -> Optional[GenerationUsage]:
        """
        Fetch detailed usage for a specific generation.

        This can be used to get accurate cost after a completion.
        """
        try:
            client = self._get_client()
            # Note: This endpoint is /v1/generation/{id}, not under /api/v1
            # We need to use the full URL
            response = client.get(
                f"https://openrouter.ai/v1/generation/{generation_id}",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                },
            )
            response.raise_for_status()
            data = response.json()

            usage = data.get("usage", {})
            prompt_details = usage.get("prompt_tokens_details", {})
            completion_details = usage.get("completion_tokens_details", {})

            return GenerationUsage(
                generation_id=data.get("id", generation_id),
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
                cost=usage.get("cost", 0.0),
                cached_tokens=prompt_details.get("cached_tokens", 0),
                audio_tokens=prompt_details.get("audio_tokens", 0),
                reasoning_tokens=completion_details.get("reasoning_tokens", 0),
            )
        except Exception as e:
            print(f"Failed to fetch generation usage: {e}")
            return None

    def get_key_info(self) -> Optional[KeyInfo]:
        """
        Fetch information about the current API key including usage stats.

        Returns key-specific usage (daily, weekly, monthly) - not account-wide.
        """
        try:
            client = self._get_client()
            response = client.get("/key")
            response.raise_for_status()
            data = response.json().get("data", {})

            return KeyInfo(
                label=data.get("label", ""),
                usage=data.get("usage", 0.0),
                usage_daily=data.get("usage_daily", 0.0),
                usage_weekly=data.get("usage_weekly", 0.0),
                usage_monthly=data.get("usage_monthly", 0.0),
                limit=data.get("limit"),
                limit_remaining=data.get("limit_remaining"),
                is_free_tier=data.get("is_free_tier", False),
            )
        except Exception as e:
            print(f"Failed to fetch key info: {e}")
            return None

    def get_activity(self) -> Optional[ActivityData]:
        """
        Fetch activity data for the last 30 days.

        Returns detailed breakdown by model and date.
        """
        try:
            client = self._get_client()
            response = client.get("/activity")
            response.raise_for_status()
            data = response.json().get("data", [])

            entries = []
            for item in data:
                entries.append(ActivityEntry(
                    date=item.get("date", ""),
                    model=item.get("model", ""),
                    model_permaslug=item.get("model_permaslug", ""),
                    provider_name=item.get("provider_name", ""),
                    usage=item.get("usage", 0.0),
                    requests=item.get("requests", 0),
                    prompt_tokens=item.get("prompt_tokens", 0),
                    completion_tokens=item.get("completion_tokens", 0),
                    reasoning_tokens=item.get("reasoning_tokens", 0),
                ))
            return ActivityData(entries=entries)
        except Exception as e:
            print(f"Failed to fetch activity: {e}")
            return None

    def close(self):
        """Close the HTTP client."""
        if self._client:
            self._client.close()
            self._client = None


# Global instance cache
_api_instances: dict[str, OpenRouterAPI] = {}


def get_openrouter_api(api_key: str) -> OpenRouterAPI:
    """Get or create an OpenRouterAPI instance for the given API key."""
    if api_key not in _api_instances:
        _api_instances[api_key] = OpenRouterAPI(api_key)
    return _api_instances[api_key]
