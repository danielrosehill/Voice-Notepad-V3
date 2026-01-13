"""Transcription Queue - Manages concurrent transcriptions for rapid dictation.

Allows users to record a second (or third) dictation while the first is still
being transcribed. The queue processes items concurrently up to a configurable
limit (default 2).
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Callable
import uuid
import time

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from .transcription import get_client, TranscriptionResult
from .audio_processor import compress_audio_for_api
from .vad_processor import remove_silence, is_vad_available


class QueueItemState(Enum):
    """State of a queue item."""
    QUEUED = "queued"
    TRANSCRIBING = "transcribing"
    COMPLETE = "complete"
    ERROR = "error"


@dataclass
class TranscriptionSettings:
    """Snapshot of settings at the time of queuing."""
    provider: str
    api_key: str
    model: str
    prompt: str
    vad_enabled: bool = False


@dataclass
class QueueItem:
    """A single item in the transcription queue."""
    id: str
    audio_data: bytes
    settings: TranscriptionSettings
    state: QueueItemState = QueueItemState.QUEUED
    result: Optional[TranscriptionResult] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    inference_time_ms: int = 0
    original_duration: Optional[float] = None
    vad_duration: Optional[float] = None


class QueueWorker(QThread):
    """Worker thread for a single queued transcription."""

    finished = pyqtSignal(str, TranscriptionResult)  # item_id, result
    error = pyqtSignal(str, str)  # item_id, error_message
    status = pyqtSignal(str, str)  # item_id, status_message
    vad_complete = pyqtSignal(str, float, float)  # item_id, orig_dur, vad_dur

    def __init__(self, item: QueueItem, parent=None):
        super().__init__(parent)
        self.item = item
        self.inference_time_ms: int = 0
        self.original_duration: Optional[float] = None
        self.vad_duration: Optional[float] = None

    def run(self):
        try:
            item = self.item
            audio_data = item.audio_data
            settings = item.settings

            # Apply VAD if enabled
            if settings.vad_enabled and is_vad_available():
                self.status.emit(item.id, "Removing silence...")
                try:
                    audio_data, orig_dur, vad_dur = remove_silence(audio_data)
                    self.original_duration = orig_dur
                    self.vad_duration = vad_dur
                    self.vad_complete.emit(item.id, orig_dur, vad_dur)
                    if vad_dur < orig_dur:
                        reduction = (1 - vad_dur / orig_dur) * 100
                        print(
                            f"[Queue {item.id[:8]}] VAD: {orig_dur:.1f}s → {vad_dur:.1f}s ({reduction:.0f}% reduction)"
                        )
                except Exception as e:
                    print(f"[Queue {item.id[:8]}] VAD failed, using original: {e}")

            # Compress audio
            self.status.emit(item.id, "Compressing...")
            compressed_audio = compress_audio_for_api(audio_data)

            # Transcribe
            self.status.emit(item.id, "Transcribing...")
            start_time = time.time()
            client = get_client(settings.provider, settings.api_key, settings.model)
            result = client.transcribe(compressed_audio, settings.prompt)
            self.inference_time_ms = int((time.time() - start_time) * 1000)

            self.finished.emit(item.id, result)

        except Exception as e:
            self.error.emit(self.item.id, str(e))


class TranscriptionQueue(QObject):
    """Manages a queue of transcriptions with concurrent processing."""

    # Signals
    item_queued = pyqtSignal(str)  # item_id - new item added to queue
    item_started = pyqtSignal(str)  # item_id - transcription started
    item_complete = pyqtSignal(str, object)  # item_id, TranscriptionResult
    item_error = pyqtSignal(str, str)  # item_id, error_message
    item_status = pyqtSignal(str, str)  # item_id, status_message
    queue_changed = pyqtSignal()  # Queue size/state changed

    def __init__(self, max_concurrent: int = 2, parent=None):
        super().__init__(parent)
        self.max_concurrent = max_concurrent
        self.pending: list[QueueItem] = []
        self.active: Dict[str, QueueWorker] = {}  # id -> worker
        self.completed: list[QueueItem] = []
        self._max_completed = 10  # Keep last N completed items

    def enqueue(
        self,
        audio_data: bytes,
        provider: str,
        api_key: str,
        model: str,
        prompt: str,
        vad_enabled: bool = False,
    ) -> str:
        """Add an item to the transcription queue.

        Args:
            audio_data: Raw audio bytes
            provider: API provider ("gemini" or "openrouter")
            api_key: API key for the provider
            model: Model name
            prompt: Cleanup prompt
            vad_enabled: Whether to apply VAD

        Returns:
            item_id: Unique ID for tracking this item
        """
        settings = TranscriptionSettings(
            provider=provider,
            api_key=api_key,
            model=model,
            prompt=prompt,
            vad_enabled=vad_enabled,
        )

        item = QueueItem(
            id=str(uuid.uuid4()),
            audio_data=audio_data,
            settings=settings,
        )

        self.pending.append(item)
        self.item_queued.emit(item.id)
        self.queue_changed.emit()

        # Try to start processing
        self._process_queue()

        return item.id

    def _process_queue(self):
        """Start transcription workers if slots are available."""
        while len(self.active) < self.max_concurrent and self.pending:
            item = self.pending.pop(0)
            self._start_transcription(item)

    def _start_transcription(self, item: QueueItem):
        """Spin up a worker for an item."""
        item.state = QueueItemState.TRANSCRIBING
        item.started_at = datetime.now()

        worker = QueueWorker(item)
        worker.finished.connect(self._on_worker_finished)
        worker.error.connect(self._on_worker_error)
        worker.status.connect(self._on_worker_status)
        worker.vad_complete.connect(self._on_worker_vad)

        self.active[item.id] = worker
        self.item_started.emit(item.id)
        self.queue_changed.emit()

        worker.start()

    def _on_worker_finished(self, item_id: str, result: TranscriptionResult):
        """Handle worker completion."""
        if item_id not in self.active:
            return

        worker = self.active.pop(item_id)

        # Find and update the item
        item = self._find_active_item(item_id)
        if item:
            item.state = QueueItemState.COMPLETE
            item.completed_at = datetime.now()
            item.result = result
            item.inference_time_ms = worker.inference_time_ms
            item.original_duration = worker.original_duration
            item.vad_duration = worker.vad_duration
            # Clear audio data to free memory
            item.audio_data = b''
            self.completed.append(item)

            # Limit completed list size
            while len(self.completed) > self._max_completed:
                self.completed.pop(0)

        # Emit completion signal
        self.item_complete.emit(item_id, result)
        self.queue_changed.emit()

        # Clean up worker
        worker.deleteLater()

        # Process next in queue
        self._process_queue()

    def _on_worker_error(self, item_id: str, error: str):
        """Handle worker error."""
        if item_id not in self.active:
            return

        worker = self.active.pop(item_id)

        # Find and update the item
        item = self._find_active_item(item_id)
        if item:
            item.state = QueueItemState.ERROR
            item.completed_at = datetime.now()
            item.error = error
            item.audio_data = b''  # Free memory
            self.completed.append(item)

            while len(self.completed) > self._max_completed:
                self.completed.pop(0)

        self.item_error.emit(item_id, error)
        self.queue_changed.emit()

        worker.deleteLater()
        self._process_queue()

    def _on_worker_status(self, item_id: str, status: str):
        """Forward worker status updates."""
        self.item_status.emit(item_id, status)

    def _on_worker_vad(self, item_id: str, orig_dur: float, vad_dur: float):
        """Handle VAD completion for an item."""
        # Store in item for later database save
        item = self._find_active_item(item_id)
        if item:
            item.original_duration = orig_dur
            item.vad_duration = vad_dur

    def _find_active_item(self, item_id: str) -> Optional[QueueItem]:
        """Find an item by ID in active workers."""
        worker = self.active.get(item_id)
        if worker:
            return worker.item
        return None

    def get_queue_status(self) -> dict:
        """Get current queue state for UI display."""
        return {
            "pending_count": len(self.pending),
            "active_count": len(self.active),
            "completed_count": len(self.completed),
            "active_ids": list(self.active.keys()),
            "pending_ids": [item.id for item in self.pending],
        }

    def get_pending_count(self) -> int:
        """Get number of items waiting to be processed."""
        return len(self.pending)

    def get_active_count(self) -> int:
        """Get number of items currently being processed."""
        return len(self.active)

    def is_processing(self) -> bool:
        """Check if any items are being processed."""
        return len(self.active) > 0

    def is_empty(self) -> bool:
        """Check if queue is empty (no pending or active items)."""
        return len(self.pending) == 0 and len(self.active) == 0

    def clear_pending(self):
        """Clear all pending items (does not stop active workers)."""
        self.pending.clear()
        self.queue_changed.emit()

    def clear_completed(self):
        """Clear completed items list."""
        self.completed.clear()

    def cancel_all(self):
        """Cancel all pending items and stop active workers."""
        # Clear pending
        self.pending.clear()

        # Stop active workers
        for item_id, worker in list(self.active.items()):
            worker.quit()
            if not worker.wait(2000):  # 2 second timeout
                worker.terminate()
            worker.deleteLater()

        self.active.clear()
        self.queue_changed.emit()

    def cleanup(self):
        """Clean up all resources. Call before destroying."""
        self.cancel_all()
        self.completed.clear()
