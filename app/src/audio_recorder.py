"""Audio recording functionality using PyAudio."""

import io
import wave
import threading
from typing import Optional, Callable
import pyaudio


class AudioRecorder:
    """Records audio from microphone."""

    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    # Common sample rates to try, in order of preference
    SAMPLE_RATES = [48000, 44100, 22050, 16000]

    def __init__(self, sample_rate: int = 48000):
        self.sample_rate = sample_rate
        self.actual_sample_rate = sample_rate  # What we actually use
        self.audio = pyaudio.PyAudio()
        self.stream: Optional[pyaudio.Stream] = None
        self.frames: list[bytes] = []
        self.is_recording = False
        self.is_paused = False
        self._record_thread: Optional[threading.Thread] = None
        self._device_index: Optional[int] = None
        self._lock = threading.Lock()
        # Callback for error notifications (mic disconnect, etc.)
        self.on_error: Optional[Callable[[str], None]] = None
        self._error_occurred = False

    def get_input_devices(self) -> list[tuple[int, str]]:
        """Get list of available input devices."""
        devices = []
        for i in range(self.audio.get_device_count()):
            info = self.audio.get_device_info_by_index(i)
            if info["maxInputChannels"] > 0:
                devices.append((i, info["name"]))
        return devices

    def set_device(self, device_index: Optional[int]) -> None:
        """Set the input device to use."""
        self._device_index = device_index

    def _get_supported_sample_rate(self, device_index: Optional[int]) -> int:
        """Find a supported sample rate for the device."""
        # Try to get device's default sample rate first
        if device_index is not None:
            try:
                info = self.audio.get_device_info_by_index(device_index)
                default_rate = int(info.get("defaultSampleRate", 48000))
                if self._test_sample_rate(device_index, default_rate):
                    return default_rate
            except Exception:
                pass

        # Try common sample rates
        for rate in self.SAMPLE_RATES:
            if self._test_sample_rate(device_index, rate):
                return rate

        # Fallback
        return 48000

    def _test_sample_rate(self, device_index: Optional[int], rate: int) -> bool:
        """Test if a sample rate is supported."""
        try:
            supported = self.audio.is_format_supported(
                rate,
                input_device=device_index,
                input_channels=self.CHANNELS,
                input_format=self.FORMAT,
            )
            return supported
        except ValueError:
            return False

    def is_device_available(self, device_index: Optional[int] = None) -> bool:
        """Check if the specified device is still available."""
        if device_index is None:
            device_index = self._device_index
        if device_index is None:
            return True  # Default device assumed available

        try:
            info = self.audio.get_device_info_by_index(device_index)
            return info.get("maxInputChannels", 0) > 0
        except Exception:
            return False

    def start_recording(self) -> bool:
        """Start recording audio.

        Returns:
            True if recording started successfully, False on error.
        """
        if self.is_recording:
            return True

        # Check if device is available before starting
        if self._device_index is not None and not self.is_device_available(self._device_index):
            if self.on_error:
                self.on_error("Microphone disconnected or unavailable")
            return False

        with self._lock:
            self.frames = []
            self._error_occurred = False

        self.is_recording = True
        self.is_paused = False

        # Find a working sample rate
        self.actual_sample_rate = self._get_supported_sample_rate(self._device_index)

        try:
            self.stream = self.audio.open(
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self.actual_sample_rate,
                input=True,
                input_device_index=self._device_index,
                frames_per_buffer=self.CHUNK,
            )
        except Exception as e:
            self.is_recording = False
            if self.on_error:
                self.on_error(f"Failed to open microphone: {e}")
            return False

        self._record_thread = threading.Thread(target=self._record_loop, daemon=True)
        self._record_thread.start()
        return True

    def _record_loop(self) -> None:
        """Recording loop running in separate thread."""
        consecutive_errors = 0
        max_consecutive_errors = 5

        while self.is_recording:
            if not self.is_paused and self.stream:
                try:
                    data = self.stream.read(self.CHUNK, exception_on_overflow=False)
                    with self._lock:
                        self.frames.append(data)
                    consecutive_errors = 0  # Reset on success
                except OSError as e:
                    # OSError often indicates device disconnect
                    consecutive_errors += 1
                    if consecutive_errors >= max_consecutive_errors:
                        self._error_occurred = True
                        if self.on_error:
                            self.on_error("Microphone disconnected during recording")
                        break
                except Exception as e:
                    consecutive_errors += 1
                    if consecutive_errors >= max_consecutive_errors:
                        self._error_occurred = True
                        if self.on_error:
                            self.on_error(f"Recording error: {e}")
                        break

    def pause_recording(self) -> None:
        """Pause recording."""
        self.is_paused = True

    def resume_recording(self) -> None:
        """Resume recording."""
        self.is_paused = False

    def stop_recording(self) -> bytes:
        """Stop recording and return WAV data."""
        self.is_recording = False

        if self._record_thread:
            self._record_thread.join(timeout=1.0)

        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None

        # Convert to WAV bytes
        return self._frames_to_wav()

    def _frames_to_wav(self) -> bytes:
        """Convert recorded frames to WAV format."""
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wf:
            wf.setnchannels(self.CHANNELS)
            wf.setsampwidth(self.audio.get_sample_size(self.FORMAT))
            wf.setframerate(self.actual_sample_rate)
            wf.writeframes(b"".join(self.frames))
        return buffer.getvalue()

    def clear(self) -> None:
        """Clear recorded audio."""
        with self._lock:
            self.frames = []

    def get_duration(self) -> float:
        """Get current recording duration in seconds."""
        with self._lock:
            if not self.frames:
                return 0.0
            total_samples = len(self.frames) * self.CHUNK
        return total_samples / self.actual_sample_rate

    def had_error(self) -> bool:
        """Check if an error occurred during recording."""
        return self._error_occurred

    def cleanup(self) -> None:
        """Clean up audio resources."""
        if self.stream:
            self.stream.close()
        self.audio.terminate()
