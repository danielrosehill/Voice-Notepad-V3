"""Cost tracking for API usage."""

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, asdict
from datetime import datetime, date
from pathlib import Path
from threading import Lock
from typing import Optional


USAGE_DIR = Path.home() / ".config" / "voice-notepad-v3" / "usage"

# Shared thread pool for background I/O operations (shared with database)
_io_executor: Optional[ThreadPoolExecutor] = None
_executor_lock = Lock()


def get_io_executor() -> ThreadPoolExecutor:
    """Get or create the shared I/O thread pool."""
    global _io_executor
    if _io_executor is None:
        with _executor_lock:
            if _io_executor is None:
                _io_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="io_worker")
    return _io_executor


# Pricing per million tokens (approximate, as of Jan 2025)
# Audio models have different pricing structures
MODEL_PRICING = {
    # Gemini 3 models (primary supported models)
    "gemini-3-flash-preview": {"input": 0.10, "output": 0.40},
    "gemini-3-pro-preview": {"input": 1.25, "output": 5.00},
    "google/gemini-3-flash-preview": {"input": 0.10, "output": 0.40},
    "google/gemini-3-pro-preview": {"input": 1.25, "output": 5.00},
    # Legacy Gemini models (deprecated, kept for historical cost tracking)
    "gemini-flash-latest": {"input": 0.075, "output": 0.30},
    "gemini-2.5-flash": {"input": 0.075, "output": 0.30},
    "gemini-2.5-flash-lite": {"input": 0.02, "output": 0.10},
    "gemini-2.5-pro": {"input": 1.25, "output": 5.00},
    "google/gemini-2.5-flash": {"input": 0.075, "output": 0.30},
    "google/gemini-2.5-flash-lite": {"input": 0.02, "output": 0.10},
    "google/gemini-2.0-flash-001": {"input": 0.075, "output": 0.30},
    "google/gemini-2.0-flash-lite-001": {"input": 0.02, "output": 0.10},
}


@dataclass
class UsageRecord:
    """A single API usage record."""
    timestamp: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    estimated_cost: float

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "UsageRecord":
        return cls(**data)


class CostTracker:
    """Tracks API usage and costs.

    File writes are performed asynchronously in a background thread
    to avoid blocking the main event loop during transcription.
    """

    def __init__(self):
        USAGE_DIR.mkdir(parents=True, exist_ok=True)
        self._today_file = USAGE_DIR / f"{date.today().isoformat()}.json"
        self._records: list[UsageRecord] = []
        self._lock = Lock()  # Protect in-memory records
        self._load_today()

    def _load_today(self):
        """Load today's usage records."""
        if self._today_file.exists():
            try:
                with open(self._today_file, "r") as f:
                    data = json.load(f)
                self._records = [UsageRecord.from_dict(r) for r in data]
            except (json.JSONDecodeError, KeyError):
                self._records = []
        else:
            self._records = []

    def _save_today(self):
        """Save today's usage records (runs in background thread)."""
        with open(self._today_file, "w") as f:
            json.dump([r.to_dict() for r in self._records], f, indent=2)

    def _save_today_async(self):
        """Queue file save to background thread."""
        # Create a snapshot of records to avoid race conditions
        with self._lock:
            records_snapshot = [r.to_dict() for r in self._records]
            filepath = self._today_file

        def do_save():
            try:
                with open(filepath, "w") as f:
                    json.dump(records_snapshot, f, indent=2)
            except Exception as e:
                print(f"Error saving cost tracker data: {e}")

        get_io_executor().submit(do_save)

    def _check_date_rollover(self):
        """Check if we've crossed midnight and need a new file."""
        expected_file = USAGE_DIR / f"{date.today().isoformat()}.json"
        if expected_file != self._today_file:
            self._today_file = expected_file
            self._records = []

    def record_usage(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int
    ) -> float:
        """Record API usage and return estimated cost.

        File write is performed asynchronously to avoid blocking.
        """
        self._check_date_rollover()

        # Calculate cost
        pricing = MODEL_PRICING.get(model, {"input": 0.10, "output": 0.30})
        cost = (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000

        record = UsageRecord(
            timestamp=datetime.now().isoformat(),
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost=cost
        )

        with self._lock:
            self._records.append(record)

        # Save asynchronously to avoid blocking the transcription flow
        self._save_today_async()

        return cost

    def get_today_cost(self) -> float:
        """Get total estimated cost for today."""
        self._check_date_rollover()
        return sum(r.estimated_cost for r in self._records)

    def get_today_count(self) -> int:
        """Get number of transcriptions today."""
        self._check_date_rollover()
        return len(self._records)

    def get_today_summary(self) -> dict:
        """Get detailed summary for today."""
        self._check_date_rollover()
        return {
            "total_cost": self.get_today_cost(),
            "transcription_count": len(self._records),
            "total_input_tokens": sum(r.input_tokens for r in self._records),
            "total_output_tokens": sum(r.output_tokens for r in self._records),
            "by_provider": self._group_by_provider()
        }

    def _group_by_provider(self) -> dict:
        """Group usage by provider."""
        by_provider = {}
        for r in self._records:
            if r.provider not in by_provider:
                by_provider[r.provider] = {"cost": 0.0, "count": 0}
            by_provider[r.provider]["cost"] += r.estimated_cost
            by_provider[r.provider]["count"] += 1
        return by_provider


# Global instance
_tracker: Optional[CostTracker] = None


def get_tracker() -> CostTracker:
    """Get the global cost tracker instance."""
    global _tracker
    if _tracker is None:
        _tracker = CostTracker()
    return _tracker
