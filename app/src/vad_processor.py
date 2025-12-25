"""Voice Activity Detection (VAD) for removing silence from audio."""

import io
import wave
import struct
from pathlib import Path
from typing import Tuple, Optional, Any
import urllib.request

try:
    import onnxruntime as ort
    ONNX_AVAILABLE = True
except ImportError:
    ort = None  # type: ignore
    ONNX_AVAILABLE = False

from pydub import AudioSegment


# Model storage location
MODELS_DIR = Path.home() / ".config" / "voice-notepad-v3" / "models"
SILERO_MODEL_URL = "https://github.com/snakers4/silero-vad/raw/master/src/silero_vad/data/silero_vad.onnx"
SILERO_MODEL_PATH = MODELS_DIR / "silero_vad.onnx"

# VAD parameters
SAMPLE_RATE = 16000  # Silero VAD expects 16kHz
WINDOW_SIZE_SAMPLES = 512  # ~32ms at 16kHz
THRESHOLD = 0.5  # Speech probability threshold
MIN_SPEECH_DURATION_MS = 250  # Minimum speech segment duration
MIN_SILENCE_DURATION_MS = 100  # Minimum silence to consider removing
SPEECH_PAD_MS = 30  # Padding around speech segments


class VADProcessor:
    """Voice Activity Detection processor using Silero VAD."""

    def __init__(self):
        self._session: Optional[Any] = None  # ort.InferenceSession when loaded
        self._h = None
        self._c = None
        self._sr = None

    def _ensure_model(self) -> bool:
        """Download the model if not present. Returns True if model is available."""
        if not ONNX_AVAILABLE:
            print("VAD: onnxruntime not installed, VAD disabled")
            return False

        if SILERO_MODEL_PATH.exists():
            return True

        print("VAD: Downloading Silero VAD model...")
        try:
            MODELS_DIR.mkdir(parents=True, exist_ok=True)
            urllib.request.urlretrieve(SILERO_MODEL_URL, SILERO_MODEL_PATH)
            print("VAD: Model downloaded successfully")
            return True
        except Exception as e:
            print(f"VAD: Failed to download model: {e}")
            return False

    def _get_session(self) -> Optional[Any]:
        """Get or create the ONNX inference session."""
        if self._session is not None:
            return self._session

        if not self._ensure_model():
            return None

        try:
            self._session = ort.InferenceSession(
                str(SILERO_MODEL_PATH),
                providers=['CPUExecutionProvider']
            )
            return self._session
        except Exception as e:
            print(f"VAD: Failed to load model: {e}")
            return None

    def _reset_states(self):
        """Reset the LSTM states for a new audio stream."""
        import numpy as np
        self._h = np.zeros((2, 1, 64), dtype=np.float32)
        self._c = np.zeros((2, 1, 64), dtype=np.float32)
        self._sr = np.array([SAMPLE_RATE], dtype=np.int64)

    def _predict(self, audio_chunk: 'np.ndarray') -> float:
        """Run VAD prediction on a single audio chunk."""
        import numpy as np

        session = self._get_session()
        if session is None:
            return 1.0  # Assume speech if VAD unavailable

        # Prepare input
        audio_chunk = audio_chunk.astype(np.float32)
        if audio_chunk.ndim == 1:
            audio_chunk = audio_chunk[np.newaxis, :]

        # Run inference
        ort_inputs = {
            'input': audio_chunk,
            'sr': self._sr,
            'h': self._h,
            'c': self._c,
        }

        out, self._h, self._c = session.run(None, ort_inputs)
        return float(out[0][0])

    def get_speech_timestamps(self, audio_data: bytes) -> list[dict]:
        """
        Get timestamps of speech segments in audio.

        Args:
            audio_data: WAV audio bytes

        Returns:
            List of dicts with 'start' and 'end' keys (in samples)
        """
        import numpy as np

        session = self._get_session()
        if session is None:
            return []

        # Load and prepare audio
        audio = AudioSegment.from_wav(io.BytesIO(audio_data))

        # Convert to 16kHz mono
        if audio.channels > 1:
            audio = audio.set_channels(1)
        if audio.frame_rate != SAMPLE_RATE:
            audio = audio.set_frame_rate(SAMPLE_RATE)

        # Convert to numpy array
        samples = np.array(audio.get_array_of_samples(), dtype=np.float32)
        samples = samples / 32768.0  # Normalize to [-1, 1]

        # Reset LSTM states
        self._reset_states()

        # Process audio in chunks
        speech_probs = []
        for i in range(0, len(samples), WINDOW_SIZE_SAMPLES):
            chunk = samples[i:i + WINDOW_SIZE_SAMPLES]
            if len(chunk) < WINDOW_SIZE_SAMPLES:
                # Pad last chunk
                chunk = np.pad(chunk, (0, WINDOW_SIZE_SAMPLES - len(chunk)))
            prob = self._predict(chunk)
            speech_probs.append(prob)

        # Convert probabilities to speech segments
        triggered = False
        speeches = []
        current_speech = {}
        min_speech_samples = int(MIN_SPEECH_DURATION_MS * SAMPLE_RATE / 1000)
        min_silence_samples = int(MIN_SILENCE_DURATION_MS * SAMPLE_RATE / 1000)
        speech_pad_samples = int(SPEECH_PAD_MS * SAMPLE_RATE / 1000)

        for i, prob in enumerate(speech_probs):
            sample_pos = i * WINDOW_SIZE_SAMPLES

            if prob >= THRESHOLD and not triggered:
                triggered = True
                current_speech = {'start': max(0, sample_pos - speech_pad_samples)}

            elif prob < THRESHOLD and triggered:
                # Check if silence is long enough
                # Look ahead to see if speech resumes quickly
                look_ahead = speech_probs[i:i + (min_silence_samples // WINDOW_SIZE_SAMPLES) + 1]
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

    def remove_silence(self, audio_data: bytes) -> Tuple[bytes, float, float]:
        """
        Remove silence from audio using VAD.

        Args:
            audio_data: WAV audio bytes

        Returns:
            Tuple of (processed_audio_bytes, original_duration_seconds, processed_duration_seconds)
        """
        import numpy as np

        # Get original duration
        original_audio = AudioSegment.from_wav(io.BytesIO(audio_data))
        original_duration = len(original_audio) / 1000.0

        # Get speech timestamps
        speeches = self.get_speech_timestamps(audio_data)

        if not speeches:
            # No speech detected, return original
            return audio_data, original_duration, original_duration

        # Prepare audio for extraction
        audio = AudioSegment.from_wav(io.BytesIO(audio_data))
        if audio.channels > 1:
            audio = audio.set_channels(1)
        if audio.frame_rate != SAMPLE_RATE:
            audio = audio.set_frame_rate(SAMPLE_RATE)

        # Extract speech segments
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
    """Check if VAD is available (onnxruntime installed)."""
    return ONNX_AVAILABLE
