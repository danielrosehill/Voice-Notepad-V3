"""TTS accessibility announcements for Voice Notepad V3.

Plays pre-generated voice announcements for status changes.
Uses British English male voice (en-GB-RyanNeural) via Edge TTS.

Also supports dynamic TTS generation for stats readout.
"""

import asyncio
import os
import tempfile
import threading
import time
from collections import deque
from pathlib import Path
from typing import Optional, Tuple

# Edge TTS for dynamic speech generation
try:
    import edge_tts
    HAS_EDGE_TTS = True
except ImportError:
    HAS_EDGE_TTS = False

# Try to use simpleaudio for playback (non-blocking, can load WAV files)
try:
    import simpleaudio as sa
    HAS_SIMPLEAUDIO = True
except ImportError:
    HAS_SIMPLEAUDIO = False

# Fallback to PyAudio if available
try:
    import pyaudio
    import wave
    HAS_PYAUDIO = True
except ImportError:
    HAS_PYAUDIO = False


def _get_assets_dir() -> Path:
    """Get the path to TTS assets directory.

    Handles both development (running from source) and installed scenarios.
    """
    # First, check relative to this source file (development)
    src_dir = Path(__file__).parent
    dev_assets = src_dir.parent / "assets" / "tts"
    if dev_assets.exists():
        return dev_assets

    # Check in installed location (alongside src)
    installed_assets = src_dir / "assets" / "tts"
    if installed_assets.exists():
        return installed_assets

    # Check in system-wide location
    system_assets = Path("/opt/voice-notepad/assets/tts")
    if system_assets.exists():
        return system_assets

    # Fallback to development path (may not exist)
    return dev_assets


class TTSAnnouncer:
    """Manages TTS accessibility announcements.

    Note: The announcer always plays when methods are called. The calling code
    (main.py) is responsible for checking config.audio_feedback_mode == "tts"
    before calling announce_* methods.
    """

    def __init__(self):
        self._assets_dir = _get_assets_dir()
        self._audio_cache: dict[str, Optional[bytes]] = {}
        self._sample_rate = 16000  # WAV files are 16kHz

        # Anti-collision queue and worker
        self._announcement_queue: deque[Tuple[str, bool, Optional[int]]] = deque()
        self._queue_lock = threading.Lock()
        self._worker_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._last_played_time = 0.0
        self._min_pause_ms = 300  # Minimum pause between announcements (300ms)
        self._is_playing = False

        # Pre-load all audio files
        self._preload_audio()

        # Start the queue worker thread
        self._start_worker()

    def _preload_audio(self) -> None:
        """Pre-load all TTS audio files into memory."""
        announcements = [
            # Recording states
            "recording", "stopped", "paused", "resumed", "discarded", "appended", "cached",
            # Transcription states
            "transcribing", "complete", "error",
            # Output modes
            "text_in_app", "text_on_clipboard", "clipboard", "text_injected", "injection_failed",
            # Prompt stack changes
            "format_updated", "format_inference", "tone_updated", "style_updated", "verbatim_mode", "general_mode",
            # Audio feedback mode changes
            "tts_activated", "tts_deactivated",
            # Output mode toggles
            "app_enabled", "app_disabled", "clipboard_enabled", "clipboard_disabled",
            "inject_enabled", "inject_disabled",
            # Settings toggles
            "vad_enabled", "vad_disabled",
            # Append mode
            "appending",
            # Settings/config actions
            "default_prompt_configured", "copied_to_clipboard",
            # Legacy (kept for compatibility)
            "copied", "injected", "cleared",
        ]

        for name in announcements:
            wav_path = self._assets_dir / f"{name}.wav"
            if wav_path.exists():
                try:
                    if HAS_SIMPLEAUDIO:
                        # Load as WaveObject for simpleaudio
                        self._audio_cache[name] = sa.WaveObject.from_wave_file(str(wav_path))
                    elif HAS_PYAUDIO:
                        # Read raw audio data for PyAudio
                        with wave.open(str(wav_path), 'rb') as wf:
                            self._audio_cache[name] = wf.readframes(wf.getnframes())
                    else:
                        self._audio_cache[name] = None
                except Exception:
                    self._audio_cache[name] = None
            else:
                self._audio_cache[name] = None

    def _start_worker(self) -> None:
        """Start the queue worker thread."""
        if self._worker_thread is None or not self._worker_thread.is_alive():
            self._stop_event.clear()
            self._worker_thread = threading.Thread(target=self._queue_worker, daemon=True)
            self._worker_thread.start()

    def _queue_worker(self) -> None:
        """Worker thread that processes the announcement queue."""
        while not self._stop_event.is_set():
            # Get next announcement from queue
            announcement = None
            with self._queue_lock:
                if self._announcement_queue:
                    announcement = self._announcement_queue.popleft()

            if announcement is None:
                # No announcements, sleep briefly and retry
                time.sleep(0.05)
                continue

            name, blocking, buffer_ms = announcement

            # Check if we need a pause before playing
            current_time = time.time()
            time_since_last = (current_time - self._last_played_time) * 1000  # Convert to ms
            if time_since_last < self._min_pause_ms:
                time.sleep((self._min_pause_ms - time_since_last) / 1000.0)

            # Mark as playing
            self._is_playing = True

            # Play the announcement
            audio = self._audio_cache.get(name)
            if audio is not None:
                self._play_audio(name, audio)

            # Update last played time
            self._last_played_time = time.time()
            self._is_playing = False

            # Apply buffer if specified (for blocking calls)
            if buffer_ms and buffer_ms > 0:
                time.sleep(buffer_ms / 1000.0)

    def _play_async(self, name: str) -> None:
        """Queue an announcement for playback (non-blocking)."""
        audio = self._audio_cache.get(name)
        if audio is None:
            return

        with self._queue_lock:
            self._announcement_queue.append((name, False, None))

    def _play_sync(self, name: str, buffer_ms: int = 100) -> None:
        """Queue and play an announcement, blocking until complete.

        Used for announce_recording() to ensure the TTS finishes before
        the microphone starts capturing, preventing "Recording" from
        appearing in transcripts.

        Args:
            name: The announcement name (e.g., "recording")
            buffer_ms: Extra delay after playback to ensure audio is flushed
        """
        audio = self._audio_cache.get(name)
        if audio is None:
            return

        # Create an event to signal completion
        completion_event = threading.Event()

        # Add to queue with blocking flag
        with self._queue_lock:
            # Insert at front of queue for priority
            self._announcement_queue.appendleft((name, True, buffer_ms))

        # Wait for this announcement to complete
        while True:
            with self._queue_lock:
                # Check if this is the current announcement being played
                if self._announcement_queue:
                    # Still in queue or being processed
                    pass
                elif not self._is_playing:
                    # Queue empty and not playing, must be done
                    break

            time.sleep(0.01)

    def _play_audio(self, name: str, audio) -> None:
        """Play audio data."""
        if HAS_SIMPLEAUDIO and isinstance(audio, sa.WaveObject):
            try:
                play_obj = audio.play()
                play_obj.wait_done()
                return
            except Exception:
                pass

        if HAS_PYAUDIO and isinstance(audio, bytes):
            try:
                p = pyaudio.PyAudio()
                stream = p.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=self._sample_rate,
                    output=True
                )
                stream.write(audio)
                stream.stop_stream()
                stream.close()
                p.terminate()
                return
            except Exception:
                pass

        # If no audio backend available, silently fail

    # -------------------------------------------------------------------------
    # Recording state announcements
    # -------------------------------------------------------------------------

    def announce_recording(self) -> None:
        """Announce: Recording started (blocking).

        This method blocks until the announcement finishes to prevent
        the TTS audio from being captured by the microphone.
        """
        self._play_sync("recording")

    def announce_stopped(self) -> None:
        """Announce: Recording stopped."""
        self._play_async("stopped")

    def announce_paused(self) -> None:
        """Announce: Recording paused."""
        self._play_async("paused")

    def announce_resumed(self) -> None:
        """Announce: Recording resumed (blocking).

        Blocks to prevent 'Recording resumed' from being captured.
        """
        self._play_sync("resumed")

    def announce_discarded(self) -> None:
        """Announce: Recording discarded."""
        self._play_async("discarded")

    def announce_appended(self) -> None:
        """Announce: Recording appended to cache."""
        self._play_async("appended")

    def announce_cached(self) -> None:
        """Announce: Audio cached for append mode."""
        self._play_async("cached")

    # -------------------------------------------------------------------------
    # Transcription state announcements
    # -------------------------------------------------------------------------

    def announce_transcribing(self) -> None:
        """Announce: Transcription in progress."""
        self._play_async("transcribing")

    def announce_complete(self) -> None:
        """Announce: Transcription complete."""
        self._play_async("complete")

    def announce_error(self) -> None:
        """Announce: Error occurred."""
        self._play_async("error")

    # -------------------------------------------------------------------------
    # Output mode announcements
    # -------------------------------------------------------------------------

    def announce_text_in_app(self) -> None:
        """Announce: Text displayed in app."""
        self._play_async("text_in_app")

    def announce_text_on_clipboard(self) -> None:
        """Announce: Text copied to clipboard."""
        self._play_async("clipboard")

    def announce_text_injected(self) -> None:
        """Announce: Text injected at cursor."""
        self._play_async("text_injected")

    def announce_injection_failed(self) -> None:
        """Announce: Text injection failed."""
        self._play_async("injection_failed")

    # -------------------------------------------------------------------------
    # Prompt stack change announcements
    # -------------------------------------------------------------------------

    def announce_format_updated(self) -> None:
        """Announce: Format preset changed."""
        self._play_async("format_updated")

    def announce_format_inference(self) -> None:
        """Announce: Format inference activated (Infer format selected)."""
        self._play_async("format_inference")

    def announce_tone_updated(self) -> None:
        """Announce: Tone changed."""
        self._play_async("tone_updated")

    def announce_style_updated(self) -> None:
        """Announce: Style changed."""
        self._play_async("style_updated")

    def announce_verbatim_mode(self) -> None:
        """Announce: Verbatim mode selected."""
        self._play_async("verbatim_mode")

    def announce_general_mode(self) -> None:
        """Announce: General mode selected (returning from verbatim)."""
        self._play_async("general_mode")

    # -------------------------------------------------------------------------
    # Audio feedback mode announcements
    # -------------------------------------------------------------------------

    def announce_tts_activated(self) -> None:
        """Announce: TTS mode activated."""
        self._play_async("tts_activated")

    def announce_tts_deactivated(self) -> None:
        """Announce: TTS mode deactivated (switching to beeps or silent)."""
        self._play_async("tts_deactivated")

    # -------------------------------------------------------------------------
    # Output mode toggle announcements
    # -------------------------------------------------------------------------

    def announce_app_enabled(self) -> None:
        """Announce: App output mode enabled."""
        self._play_async("app_enabled")

    def announce_app_disabled(self) -> None:
        """Announce: App output mode disabled."""
        self._play_async("app_disabled")

    def announce_clipboard_enabled(self) -> None:
        """Announce: Clipboard output mode enabled."""
        self._play_async("clipboard_enabled")

    def announce_clipboard_disabled(self) -> None:
        """Announce: Clipboard output mode disabled."""
        self._play_async("clipboard_disabled")

    def announce_inject_enabled(self) -> None:
        """Announce: Inject output mode enabled."""
        self._play_async("inject_enabled")

    def announce_inject_disabled(self) -> None:
        """Announce: Inject output mode disabled."""
        self._play_async("inject_disabled")

    # -------------------------------------------------------------------------
    # Settings toggle announcements
    # -------------------------------------------------------------------------

    def announce_vad_enabled(self) -> None:
        """Announce: Voice activity detection enabled."""
        self._play_async("vad_enabled")

    def announce_vad_disabled(self) -> None:
        """Announce: Voice activity detection disabled."""
        self._play_async("vad_disabled")

    def announce_microphone_changed(self, mic_name: str) -> None:
        """Announce: Microphone changed.

        Args:
            mic_name: Display name of the new microphone
        """
        # Truncate long mic names for brevity
        short_name = mic_name[:30] + "..." if len(mic_name) > 30 else mic_name
        self.speak_text(f"Microphone: {short_name}", blocking=False)

    # -------------------------------------------------------------------------
    # Append mode announcements
    # -------------------------------------------------------------------------

    def announce_appending(self) -> None:
        """Announce: Append mode activated (before recording starts)."""
        self._play_async("appending")

    # -------------------------------------------------------------------------
    # Settings/config action announcements
    # -------------------------------------------------------------------------

    def announce_default_prompt_configured(self) -> None:
        """Announce: Default prompt configured (Reset button pressed)."""
        self._play_async("default_prompt_configured")

    def announce_copied_to_clipboard(self) -> None:
        """Announce: Copied to clipboard."""
        self._play_async("copied_to_clipboard")

    def announce_model_changed(self, model_name: str) -> None:
        """Announce: Model changed to a new preset.

        Args:
            model_name: Display name of the new model/preset
        """
        # Use dynamic TTS for model name since it varies
        self.speak_text(f"Model: {model_name}", blocking=False)

    # -------------------------------------------------------------------------
    # Legacy methods (kept for compatibility)
    # -------------------------------------------------------------------------

    def announce_copied(self) -> None:
        """Announce: Copied (legacy, use announce_text_on_clipboard)."""
        self._play_async("copied")

    def announce_injected(self) -> None:
        """Announce: Injected (legacy, use announce_text_injected)."""
        self._play_async("injected")

    def announce_cleared(self) -> None:
        """Announce: Cleared (legacy, use announce_discarded)."""
        self._play_async("cleared")

    # -------------------------------------------------------------------------
    # Dynamic TTS generation (for stats readout)
    # -------------------------------------------------------------------------

    def speak_text(self, text: str, blocking: bool = False) -> bool:
        """Generate and play TTS for arbitrary text using Edge TTS.

        Args:
            text: The text to speak
            blocking: If True, wait for speech to complete before returning

        Returns:
            True if speech was generated and played, False if Edge TTS unavailable
        """
        if not HAS_EDGE_TTS:
            print("Edge TTS not available for dynamic speech")
            return False

        if blocking:
            self._speak_text_sync(text)
        else:
            thread = threading.Thread(target=self._speak_text_sync, args=(text,), daemon=True)
            thread.start()
        return True

    def _speak_text_sync(self, text: str) -> None:
        """Generate and play TTS synchronously (internal method)."""
        try:
            # Wait for any ongoing announcement to finish
            while self._is_playing:
                time.sleep(0.01)

            # Apply pause if needed
            current_time = time.time()
            time_since_last = (current_time - self._last_played_time) * 1000
            if time_since_last < self._min_pause_ms:
                time.sleep((self._min_pause_ms - time_since_last) / 1000.0)

            # Create temp file for generated audio
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_path = tmp.name

            # Generate speech using Edge TTS (async)
            asyncio.run(self._generate_tts(text, tmp_path))

            # Mark as playing
            self._is_playing = True

            # Play the generated audio
            self._play_temp_file(tmp_path)

            # Update last played time
            self._last_played_time = time.time()
            self._is_playing = False

        except Exception as e:
            print(f"Error generating TTS: {e}")
            self._is_playing = False
        finally:
            # Clean up temp file
            try:
                if 'tmp_path' in locals():
                    os.unlink(tmp_path)
            except Exception:
                pass

    async def _generate_tts(self, text: str, output_path: str) -> None:
        """Generate TTS audio file using Edge TTS."""
        # Use same voice as pre-generated assets
        voice = "en-GB-RyanNeural"
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_path)

    def _play_temp_file(self, filepath: str) -> None:
        """Play a temporary audio file."""
        if HAS_SIMPLEAUDIO:
            try:
                wave_obj = sa.WaveObject.from_wave_file(filepath)
                play_obj = wave_obj.play()
                play_obj.wait_done()
                return
            except Exception:
                pass

        if HAS_PYAUDIO:
            try:
                import wave
                with wave.open(filepath, 'rb') as wf:
                    p = pyaudio.PyAudio()
                    stream = p.open(
                        format=p.get_format_from_width(wf.getsampwidth()),
                        channels=wf.getnchannels(),
                        rate=wf.getframerate(),
                        output=True
                    )
                    data = wf.readframes(1024)
                    while data:
                        stream.write(data)
                        data = wf.readframes(1024)
                    stream.stop_stream()
                    stream.close()
                    p.terminate()
                return
            except Exception:
                pass

    def speak_stats(self, total_transcripts: int, total_words: int) -> bool:
        """Speak usage statistics.

        Args:
            total_transcripts: Total number of transcriptions
            total_words: Total word count

        Returns:
            True if speech was initiated, False if Edge TTS unavailable
        """
        # Format numbers with commas for natural speech
        text = f"You have completed {total_transcripts:,} transcriptions, totaling {total_words:,} words."
        return self.speak_text(text, blocking=False)


# Global singleton instance
_announcer: Optional[TTSAnnouncer] = None
_announcer_lock = threading.Lock()


def get_announcer() -> TTSAnnouncer:
    """Get the global TTSAnnouncer instance (thread-safe)."""
    global _announcer
    if _announcer is None:
        with _announcer_lock:
            # Double-check pattern for thread safety
            if _announcer is None:
                _announcer = TTSAnnouncer()
    return _announcer
