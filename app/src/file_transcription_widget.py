"""File transcription tab widget for transcribing audio files from disk."""

import io
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QFileDialog,
    QApplication,
    QFrame,
    QProgressBar,
    QComboBox,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QDragEnterEvent, QDropEvent, QIcon

from .config import GEMINI_MODELS, OPENROUTER_MODELS, Config

from pydub import AudioSegment

from .audio_processor import compress_audio_for_api, archive_audio, get_audio_info
from .vad_processor import remove_silence, is_vad_available
from .transcription import get_client, TranscriptionResult
from .markdown_widget import MarkdownTextWidget
from .audio_feedback import get_feedback
from .database_mongo import get_db, AUDIO_ARCHIVE_DIR


# Supported audio formats (pydub + ffmpeg)
SUPPORTED_FORMATS = {
    ".mp3": "MP3",
    ".wav": "WAV",
    ".m4a": "M4A/AAC",
    ".ogg": "OGG",
    ".flac": "FLAC",
    ".aiff": "AIFF",
    ".aif": "AIFF",
    ".wma": "WMA",
    ".opus": "Opus",
}


class FileTranscriptionWorker(QThread):
    """Worker thread for file transcription."""

    finished = pyqtSignal(TranscriptionResult)
    error = pyqtSignal(str)
    status = pyqtSignal(str)
    progress = pyqtSignal(int)  # 0-100
    vad_complete = pyqtSignal(float, float)  # original_duration, vad_duration

    def __init__(
        self,
        file_path: str,
        provider: str,
        api_key: str,
        model: str,
        prompt: str,
        vad_enabled: bool = False,
    ):
        super().__init__()
        self.file_path = file_path
        self.provider = provider
        self.api_key = api_key
        self.model = model
        self.prompt = prompt
        self.vad_enabled = vad_enabled
        self.inference_time_ms: int = 0
        self.original_duration: Optional[float] = None
        self.vad_duration: Optional[float] = None

    def run(self):
        import time

        try:
            # Step 1: Load audio file
            self.status.emit("Loading audio file...")
            self.progress.emit(10)

            audio = AudioSegment.from_file(self.file_path)
            self.original_duration = len(audio) / 1000.0  # ms to seconds

            # Convert to WAV bytes for pipeline
            wav_buffer = io.BytesIO()
            audio.export(wav_buffer, format="wav")
            audio_data = wav_buffer.getvalue()

            self.progress.emit(30)

            # Step 2: Apply VAD if enabled
            if self.vad_enabled and is_vad_available():
                self.status.emit("Removing silence...")
                try:
                    audio_data, orig_dur, vad_dur = remove_silence(audio_data)
                    self.vad_duration = vad_dur
                    self.vad_complete.emit(orig_dur, vad_dur)
                    if vad_dur < orig_dur:
                        reduction = (1 - vad_dur / orig_dur) * 100
                        print(f"VAD: Reduced audio from {orig_dur:.1f}s to {vad_dur:.1f}s ({reduction:.0f}% reduction)")
                except Exception as e:
                    print(f"VAD failed, using original audio: {e}")

            self.progress.emit(50)

            # Step 3: Compress audio
            self.status.emit("Compressing audio...")
            compressed_audio = compress_audio_for_api(audio_data)
            self.progress.emit(70)

            # Step 4: Transcribe
            self.status.emit("Transcribing...")
            start_time = time.time()
            client = get_client(self.provider, self.api_key, self.model)
            result = client.transcribe(compressed_audio, self.prompt)
            self.inference_time_ms = int((time.time() - start_time) * 1000)

            self.progress.emit(100)
            self.finished.emit(result)

        except Exception as e:
            self.error.emit(str(e))


class FileTranscriptionWidget(QWidget):
    """Widget for transcribing audio files from disk."""

    # Signal to request config from main window
    config_requested = pyqtSignal()

    def __init__(self, config: Config = None, parent=None):
        super().__init__(parent)
        self.config = config
        self.selected_file: Optional[str] = None
        self.worker: Optional[FileTranscriptionWorker] = None
        self.last_audio_duration: Optional[float] = None
        self.last_vad_duration: Optional[float] = None
        self.setup_ui()

        # Enable drag and drop
        self.setAcceptDrops(True)

    def _get_provider_icon(self, provider: str) -> QIcon:
        """Get the icon for a given provider."""
        icons_dir = Path(__file__).parent / "icons"
        icon_map = {
            "openrouter": "or_icon.png",
            "gemini": "gemini_icon.png",
            "google": "gemini_icon.png",
        }
        icon_filename = icon_map.get(provider.lower(), "")
        if icon_filename:
            icon_path = icons_dir / icon_filename
            if icon_path.exists():
                return QIcon(str(icon_path))
        return QIcon()  # Return empty icon if not found

    def _get_model_icon(self, model_id: str) -> QIcon:
        """Get the icon for a model based on its originator."""
        icons_dir = Path(__file__).parent / "icons"
        model_lower = model_id.lower()

        # All models are now Gemini-based
        if model_lower.startswith("google/") or model_lower.startswith("gemini"):
            icon_filename = "gemini_icon.png"
        else:
            return QIcon()  # No icon for unknown models

        icon_path = icons_dir / icon_filename
        if icon_path.exists():
            return QIcon(str(icon_path))
        return QIcon()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(12, 12, 12, 12)

        # Title
        title = QLabel("File Transcription (Upload Audio)")
        title.setFont(QFont("Sans", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        # Description
        desc = QLabel("Upload and transcribe pre-recorded audio files using multimodal AI.")
        desc.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(desc)

        # Provider and model selection
        provider_layout = QHBoxLayout()

        provider_layout.addWidget(QLabel("Provider:"))
        self.provider_combo = QComboBox()
        self.provider_combo.setIconSize(QSize(16, 16))
        # Add providers with icons (Gemini first as recommended)
        providers = [
            ("Google Gemini (Recommended)", "google"),
            ("OpenRouter", "openrouter"),
        ]
        for display_name, provider_key in providers:
            icon = self._get_provider_icon(provider_key)
            self.provider_combo.addItem(icon, display_name)
        # Default to Google Gemini
        self.provider_combo.setCurrentText("Google Gemini (Recommended)")
        self.provider_combo.currentTextChanged.connect(self._on_provider_changed)
        provider_layout.addWidget(self.provider_combo)

        provider_layout.addSpacing(20)

        provider_layout.addWidget(QLabel("Model:"))
        self.model_combo = QComboBox()
        self.model_combo.setIconSize(QSize(16, 16))
        self._update_model_combo()
        provider_layout.addWidget(self.model_combo, 1)

        layout.addLayout(provider_layout)

        # File selection frame
        file_frame = QFrame()
        file_frame.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border: 2px dashed #dee2e6;
                border-radius: 8px;
                padding: 16px;
            }
            QFrame:hover {
                border-color: #007bff;
            }
        """)
        file_layout = QVBoxLayout(file_frame)

        # Drop zone label
        self.drop_label = QLabel("Drop audio file here or click Browse")
        self.drop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_label.setStyleSheet("color: #666; font-size: 13px;")
        file_layout.addWidget(self.drop_label)

        # File path and browse button
        path_row = QHBoxLayout()

        self.file_path_edit = QLineEdit()
        self.file_path_edit.setPlaceholderText("Select an audio file...")
        self.file_path_edit.setReadOnly(True)
        self.file_path_edit.setStyleSheet("""
            QLineEdit {
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 8px;
                background-color: white;
            }
        """)
        path_row.addWidget(self.file_path_edit, 1)

        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.setMinimumWidth(100)
        self.browse_btn.clicked.connect(self.browse_file)
        path_row.addWidget(self.browse_btn)

        file_layout.addLayout(path_row)

        # Supported formats hint
        formats = ", ".join(sorted(set(SUPPORTED_FORMATS.values())))
        format_hint = QLabel(f"Supported: {formats}")
        format_hint.setStyleSheet("color: #888; font-size: 11px;")
        file_layout.addWidget(format_hint)

        layout.addWidget(file_frame)

        # Audio info display
        self.audio_info_label = QLabel("")
        self.audio_info_label.setStyleSheet("color: #17a2b8; font-size: 12px;")
        layout.addWidget(self.audio_info_label)

        # Controls row
        controls = QHBoxLayout()

        self.transcribe_btn = QPushButton("Transcribe")
        self.transcribe_btn.setMinimumHeight(40)
        self.transcribe_btn.setEnabled(False)
        self.transcribe_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 14px;
                padding: 0 24px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
            QPushButton:disabled {
                background-color: #6c757d;
                color: #aaa;
            }
        """)
        self.transcribe_btn.clicked.connect(self.start_transcription)
        controls.addWidget(self.transcribe_btn)

        self.clear_file_btn = QPushButton("Clear")
        self.clear_file_btn.setMinimumHeight(40)
        self.clear_file_btn.clicked.connect(self.clear_selection)
        controls.addWidget(self.clear_file_btn)

        controls.addStretch()

        layout.addLayout(controls)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ccc;
                border-radius: 4px;
                text-align: center;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: #007bff;
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.progress_bar)

        # Status label
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #666;")
        layout.addWidget(self.status_label)

        # Output area
        self.text_output = MarkdownTextWidget()
        self.text_output.setPlaceholderText("Transcription will appear here...")
        self.text_output.setFont(QFont("Sans", 11))
        layout.addWidget(self.text_output, 1)

        # Word count
        self.word_count_label = QLabel("")
        self.word_count_label.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(self.word_count_label)

        # Connect text changes to word count
        self.text_output.textChanged.connect(self.update_word_count)

        # Bottom buttons
        bottom = QHBoxLayout()

        self.clear_text_btn = QPushButton("Clear Text")
        self.clear_text_btn.clicked.connect(self.text_output.clear)
        bottom.addWidget(self.clear_text_btn)

        bottom.addStretch()

        self.copy_btn = QPushButton("Copy to Clipboard")
        self.copy_btn.clicked.connect(self.copy_to_clipboard)
        bottom.addWidget(self.copy_btn)

        layout.addLayout(bottom)

    def _on_provider_changed(self, provider: str):
        """Handle provider selection change."""
        self._update_model_combo()

    def _update_model_combo(self):
        """Update model dropdown based on selected provider."""
        self.model_combo.blockSignals(True)
        self.model_combo.clear()

        # Map display name to internal name
        provider_display = self.provider_combo.currentText()
        provider_map = {
            "Google Gemini (Recommended)": "gemini",
            "OpenRouter": "openrouter",
        }
        provider = provider_map.get(provider_display, "gemini")

        # Get model list for provider
        if provider == "gemini":
            models = GEMINI_MODELS
        else:  # openrouter
            models = OPENROUTER_MODELS

        # Add models with model originator icon
        for model_id, display_name in models:
            model_icon = self._get_model_icon(model_id)
            self.model_combo.addItem(model_icon, display_name, model_id)

        self.model_combo.blockSignals(False)

    def _get_selected_provider(self) -> str:
        """Get the internal provider name."""
        provider_display = self.provider_combo.currentText()
        display_to_internal = {
            "Google Gemini (Recommended)": "gemini",
            "OpenRouter": "openrouter",
        }
        return display_to_internal.get(provider_display, "gemini")

    def _get_selected_model(self) -> str:
        """Get the selected model ID."""
        return self.model_combo.currentData() or "google/gemini-2.5-flash"

    def browse_file(self):
        """Open file browser to select audio file."""
        filter_parts = []
        for ext, name in SUPPORTED_FORMATS.items():
            filter_parts.append(f"*{ext}")

        filter_str = f"Audio Files ({' '.join(filter_parts)});;All Files (*)"

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Audio File",
            "",
            filter_str
        )

        if file_path:
            self.set_file(file_path)

    def set_file(self, file_path: str):
        """Set the selected file and update UI."""
        path = Path(file_path)

        if not path.exists():
            self.status_label.setText("File not found")
            self.status_label.setStyleSheet("color: #dc3545;")
            return

        ext = path.suffix.lower()
        if ext not in SUPPORTED_FORMATS:
            self.status_label.setText(f"Unsupported format: {ext}")
            self.status_label.setStyleSheet("color: #dc3545;")
            return

        self.selected_file = file_path
        self.file_path_edit.setText(file_path)
        self.transcribe_btn.setEnabled(True)
        self.status_label.setText("")
        self.status_label.setStyleSheet("color: #666;")

        # Get and display audio info
        try:
            audio = AudioSegment.from_file(file_path)
            duration = len(audio) / 1000.0
            mins = int(duration // 60)
            secs = int(duration % 60)
            channels = "stereo" if audio.channels == 2 else "mono"
            sample_rate = audio.frame_rate

            self.audio_info_label.setText(
                f"Duration: {mins}:{secs:02d} | {sample_rate}Hz | {channels} | {SUPPORTED_FORMATS.get(ext, ext)}"
            )
        except Exception as e:
            self.audio_info_label.setText(f"Could not read audio info: {e}")

    def clear_selection(self):
        """Clear the selected file."""
        self.selected_file = None
        self.file_path_edit.clear()
        self.audio_info_label.setText("")
        self.transcribe_btn.setEnabled(False)
        self.status_label.setText("")
        self.status_label.setStyleSheet("color: #666;")

    def start_transcription(self):
        """Start transcribing the selected file."""
        if not self.selected_file:
            return

        # Get config from parent (main window)
        main_window = self.window()
        if not hasattr(main_window, 'config'):
            self.status_label.setText("Error: Could not access configuration")
            self.status_label.setStyleSheet("color: #dc3545;")
            return

        config = main_window.config

        # Use File tab's own provider/model selection
        provider = self._get_selected_provider()
        model = self._get_selected_model()

        # Get API key for selected provider
        if provider == "gemini":
            api_key = config.gemini_api_key
        else:  # openrouter
            api_key = config.openrouter_api_key

        if not api_key:
            provider_name = {
                "gemini": "Google Gemini",
                "openrouter": "OpenRouter",
            }.get(provider, provider.title())
            self.status_label.setText(f"Missing API key for {provider_name}. Set in Settings → API Keys")
            self.status_label.setStyleSheet("color: #dc3545;")
            return

        # Build cleanup prompt
        from .config import build_cleanup_prompt
        cleanup_prompt = build_cleanup_prompt(config)

        # Disable controls during transcription
        self.transcribe_btn.setEnabled(False)
        self.browse_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        # Start worker
        self.worker = FileTranscriptionWorker(
            self.selected_file,
            provider,
            api_key,
            model,
            cleanup_prompt,
            vad_enabled=config.vad_enabled,
        )
        self.worker.finished.connect(self.on_transcription_complete)
        self.worker.error.connect(self.on_transcription_error)
        self.worker.status.connect(self.on_worker_status)
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.vad_complete.connect(self.on_vad_complete)
        self.worker.start()

    def on_worker_status(self, status: str):
        """Update status label."""
        self.status_label.setText(status)
        self.status_label.setStyleSheet("color: #007bff; font-weight: bold;")

    def on_vad_complete(self, orig_dur: float, vad_dur: float):
        """Store VAD duration for database."""
        self.last_audio_duration = orig_dur
        self.last_vad_duration = vad_dur

    def on_transcription_complete(self, result: TranscriptionResult):
        """Handle completed transcription."""
        self.text_output.setMarkdown(result.text)

        # Get provider/model info from File tab's own selection
        provider = self._get_selected_provider()
        model = self._get_selected_model()

        # Get config for other settings
        main_window = self.window()
        config = main_window.config

        # Calculate cost
        final_cost = 0.0
        if result.actual_cost is not None:
            final_cost = result.actual_cost
        elif result.input_tokens > 0 or result.output_tokens > 0:
            from .cost_tracker import get_tracker
            tracker = get_tracker()
            final_cost = tracker.record_usage(provider, model, result.input_tokens, result.output_tokens)

        # Get durations
        audio_duration = self.worker.original_duration if self.worker else None
        vad_duration = self.worker.vad_duration if self.worker else None
        inference_time_ms = self.worker.inference_time_ms if self.worker else 0
        prompt_length = len(self.worker.prompt) if self.worker else 0

        # Optionally archive audio
        audio_file_path = None
        if config.store_audio and self.selected_file:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            audio_filename = f"file_{timestamp}.opus"
            audio_path = AUDIO_ARCHIVE_DIR / audio_filename
            try:
                # Load and archive
                audio = AudioSegment.from_file(self.selected_file)
                wav_buffer = io.BytesIO()
                audio.export(wav_buffer, format="wav")
                if archive_audio(wav_buffer.getvalue(), str(audio_path)):
                    audio_file_path = str(audio_path)
            except Exception as e:
                print(f"Failed to archive audio: {e}")

        # Save to database
        db = get_db()
        db.save_transcription(
            provider=provider,
            model=model,
            transcript_text=result.text,
            audio_duration_seconds=audio_duration,
            inference_time_ms=inference_time_ms,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            estimated_cost=final_cost,
            audio_file_path=audio_file_path,
            vad_audio_duration_seconds=vad_duration,
            prompt_text_length=prompt_length,
            source="file",
            source_path=self.selected_file,
        )

        # Reset UI
        self.progress_bar.setVisible(False)
        self.transcribe_btn.setEnabled(True)
        self.browse_btn.setEnabled(True)
        self.status_label.setText("Complete!")
        self.status_label.setStyleSheet("color: #28a745; font-weight: bold;")

        # Auto-copy to clipboard
        self.copy_to_clipboard()

    def on_transcription_error(self, error: str):
        """Handle transcription error."""
        self.progress_bar.setVisible(False)
        self.transcribe_btn.setEnabled(True)
        self.browse_btn.setEnabled(True)
        self.status_label.setText(f"Error: {error}")
        self.status_label.setStyleSheet("color: #dc3545; font-weight: bold;")

    def update_word_count(self):
        """Update word count display."""
        text = self.text_output.toPlainText()
        if text:
            words = len(text.split())
            chars = len(text)
            self.word_count_label.setText(f"{words} words, {chars} characters")
        else:
            self.word_count_label.setText("")

    def copy_to_clipboard(self):
        """Copy transcription to clipboard."""
        text = self.text_output.toPlainText()
        if not text:
            return

        # Use wl-copy for Wayland
        import subprocess
        try:
            process = subprocess.Popen(
                ["wl-copy"],
                stdin=subprocess.PIPE,
                stderr=subprocess.DEVNULL
            )
            process.communicate(input=text.encode("utf-8"))
            self.status_label.setText("Copied!")
            self.status_label.setStyleSheet("color: #28a745;")
        except FileNotFoundError:
            # Fallback to Qt clipboard
            clipboard = QApplication.clipboard()
            clipboard.setText(text)
            self.status_label.setText("Copied!")
            self.status_label.setStyleSheet("color: #28a745;")
        except Exception:
            clipboard = QApplication.clipboard()
            clipboard.setText(text)

        # Auto-paste if enabled (inject text at cursor using ydotool)
        if self.config and self.config.auto_paste:
            self._paste_wayland()

        # Play clipboard beep
        if self.config:
            feedback = get_feedback()
            feedback.enabled = self.config.beep_on_clipboard
            feedback.play_clipboard_beep()

    def _paste_wayland(self):
        """Simulate Ctrl+V paste using ydotool (Wayland-compatible)."""
        import subprocess
        try:
            subprocess.run(
                ["ydotool", "key", "--delay", "50", "ctrl+v"],
                check=True,
                capture_output=True,
                timeout=2
            )
        except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.CalledProcessError, Exception):
            pass  # Fail silently for file transcription widget

    # Drag and drop support
    def dragEnterEvent(self, event: QDragEnterEvent):
        """Handle drag enter."""
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls:
                path = urls[0].toLocalFile()
                ext = Path(path).suffix.lower()
                if ext in SUPPORTED_FORMATS:
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event: QDropEvent):
        """Handle file drop."""
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            self.set_file(path)
