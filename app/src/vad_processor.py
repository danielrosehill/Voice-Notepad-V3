"""Voice Activity Detection (VAD) for removing silence from audio.

Uses TEN VAD - a lightweight, high-performance voice activity detector.
https://github.com/TEN-framework/ten-vad
"""

import io
from typing import Tuple, Optional

try:
    from ten_vad import TenVad
    TEN_VAD_AVAILABLE = True
except ImportError:
    TenVad = None  # type: ignore
    TEN_VAD_AVAILABLE = False

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    np = None  # type: ignore
    NUMPY_AVAILABLE = False

from pydub import AudioSegment


# VAD parameters
SAMPLE_RATE = 16000  # TEN VAD expects 16kHz
HOP_SIZE = 256  # ~16ms at 16kHz (TEN VAD optimal)
THRESHOLD = 0.5  # Speech probability threshold
MIN_SPEECH_DURATION_MS = 250  # Minimum speech segment duration
MIN_SILENCE_DURATION_MS = 100  # Minimum silence to consider removing
SPEECH_PAD_MS = 30  # Padding around speech segments


class VADProcessor:
    """Voice Activity Detection processor using TEN VAD."""

    def __init__(self):
        self._vad: Optional[TenVad] = None

    def _get_vad(self) -> Optional[TenVad]:
        """Get or create the TEN VAD instance."""
        if self._vad is not None:
            return self._vad

        if not TEN_VAD_AVAILABLE:
            print("VAD: ten-vad not installed, VAD disabled")
            return None

        if not NUMPY_AVAILABLE:
            print("VAD: numpy not installed, VAD disabled")
            return None

        try:
            self._vad = TenVad(hop_size=HOP_SIZE, threshold=THRESHOLD)
            return self._vad
        except Exception as e:
            print(f"VAD: Failed to initialize TEN VAD: {e}")
            return None

    def _prepare_audio(self, audio_data: bytes) -> AudioSegment:
        """Load and prepare audio for VAD processing.

        Args:
            audio_data: WAV audio bytes

        Returns:
            AudioSegment converted to 16kHz mono
        """
        audio = AudioSegment.from_wav(io.BytesIO(audio_data))

        # Convert to 16kHz mono
        if audio.channels > 1:
            audio = audio.set_channels(1)
        if audio.frame_rate != SAMPLE_RATE:
            audio = audio.set_frame_rate(SAMPLE_RATE)

        return audio

    def _get_speech_timestamps_from_audio(self, audio: AudioSegment) -> list[dict]:
        """Get timestamps of speech segments from prepared audio.

        Args:
            audio: AudioSegment already converted to 16kHz mono

        Returns:
            List of dicts with 'start' and 'end' keys (in samples)
        """
        vad = self._get_vad()
        if vad is None:
            return []

        # Convert to numpy array (int16 for TEN VAD)
        samples = np.array(audio.get_array_of_samples(), dtype=np.int16)

        # Process audio in chunks
        speech_probs = []
        for i in range(0, len(samples), HOP_SIZE):
            chunk = samples[i:i + HOP_SIZE]
            if len(chunk) < HOP_SIZE:
                # Pad last chunk
                chunk = np.pad(chunk, (0, HOP_SIZE - len(chunk)))
            prob, flag = vad.process(chunk)
            speech_probs.append(prob)

        # Convert probabilities to speech segments
        triggered = False
        speeches = []
        current_speech = {}
        min_speech_samples = int(MIN_SPEECH_DURATION_MS * SAMPLE_RATE / 1000)
        min_silence_samples = int(MIN_SILENCE_DURATION_MS * SAMPLE_RATE / 1000)
        speech_pad_samples = int(SPEECH_PAD_MS * SAMPLE_RATE / 1000)

        for i, prob in enumerate(speech_probs):
            sample_pos = i * HOP_SIZE

            if prob >= THRESHOLD and not triggered:
                triggered = True
                current_speech = {'start': max(0, sample_pos - speech_pad_samples)}

            elif prob < THRESHOLD and triggered:
                # Check if silence is long enough
                # Look ahead to see if speech resumes quickly
                look_ahead = speech_probs[i:i + (min_silence_samples // HOP_SIZE) + 1]
                if all(p < THRESHOLD for p in look_ahead) or i >= len(speech_probs) - 1:
                    triggered = False
                    current_speech['end'] = min(len(samples), sample_pos + speech_pad_samples)

                    # Only keep if long enough
                    duration = current_speech['end'] - current_speech['start']
                    if duration >= min_speech_samples:
                        speeches.append(current_speech)

        # Handle case where audio ends during speech
        if triggered and current_speech:
            current_speech['end'] = len(samples)
            duration = current_speech['end'] - current_speech['start']
            if duration >= min_speech_samples:
                speeches.append(current_speech)

        return speeches

    def get_speech_timestamps(self, audio_data: bytes) -> list[dict]:
        """
        Get timestamps of speech segments in audio.

        Args:
            audio_data: WAV audio bytes

        Returns:
            List of dicts with 'start' and 'end' keys (in samples)
        """
        audio = self._prepare_audio(audio_data)
        return self._get_speech_timestamps_from_audio(audio)

    def remove_silence(self, audio_data: bytes) -> Tuple[bytes, float, float]:
        """
        Remove silence from audio using VAD.

        PERFORMANCE: Loads audio only once and reuses for all operations.

        Args:
            audio_data: WAV audio bytes

        Returns:
            Tuple of (processed_audio_bytes, original_duration_seconds, processed_duration_seconds)
        """
        # Load and prepare audio ONCE
        audio = self._prepare_audio(audio_data)
        original_duration = len(audio) / 1000.0

        # Get speech timestamps using the already-prepared audio
        speeches = self._get_speech_timestamps_from_audio(audio)

        if not speeches:
            # No speech detected, return original
            print("VAD: No speech detected, returning original audio")
            return audio_data, original_duration, original_duration

        # Extract speech segments (audio is already 16kHz mono from _prepare_audio)
        combined = AudioSegment.empty()
        for speech in speeches:
            start_ms = int(speech['start'] * 1000 / SAMPLE_RATE)
            end_ms = int(speech['end'] * 1000 / SAMPLE_RATE)
            segment = audio[start_ms:end_ms]
            combined += segment

        if len(combined) == 0:
            return audio_data, original_duration, original_duration

        # Export to WAV bytes
        output = io.BytesIO()
        combined.export(output, format="wav")
        processed_data = output.getvalue()
        processed_duration = len(combined) / 1000.0

        return processed_data, original_duration, processed_duration


# Global instance
_vad: Optional[VADProcessor] = None


def get_vad() -> VADProcessor:
    """Get the global VAD processor instance."""
    global _vad
    if _vad is None:
        _vad = VADProcessor()
    return _vad


def remove_silence(audio_data: bytes) -> Tuple[bytes, float, float]:
    """
    Convenience function to remove silence from audio.

    Args:
        audio_data: WAV audio bytes

    Returns:
        Tuple of (processed_audio_bytes, original_duration_seconds, processed_duration_seconds)
    """
    vad = get_vad()
    return vad.remove_silence(audio_data)


def is_vad_available() -> bool:
    """Check if VAD is available (ten-vad installed)."""
    return TEN_VAD_AVAILABLE and NUMPY_AVAILABLE
