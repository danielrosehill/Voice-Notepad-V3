#!/usr/bin/env python3
"""Voice Notepad V3 - Voice recording with AI-powered transcription cleanup."""

import sys
import os
from pathlib import Path

# Load .env file if present (check both src/ and project root)
env_file = Path(__file__).parent / ".env"
if not env_file.exists():
    env_file = Path(__file__).parent.parent / ".env"
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())

from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QPushButton,
    QTextEdit,
    QComboBox,
    QLabel,
    QSystemTrayIcon,
    QMenu,
    QMenuBar,
    QDialog,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QCheckBox,
    QMessageBox,
    QFrame,
    QFileDialog,
    QRadioButton,
    QButtonGroup,
    QGroupBox,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize, QPropertyAnimation, QEasingCurve, QEvent
import time
from PyQt6.QtGui import QIcon, QAction, QFont, QClipboard, QShortcut, QKeySequence, QActionGroup
from PyQt6.QtWidgets import QGraphicsOpacityEffect
from PyQt6.QtWidgets import QCompleter, QToolButton

from .config import (
    Config,
    load_config,
    save_config,
    load_env_keys,
    CONFIG_DIR,
    OPENROUTER_MODELS,
    MODEL_TIERS,
    build_cleanup_prompt,
    get_model_display_name,
    FORMAT_TEMPLATES,
    FORMAT_DISPLAY_NAMES,
    FORMALITY_DISPLAY_NAMES,
    VERBOSITY_DISPLAY_NAMES,
    EMAIL_SIGNOFFS,
    is_favorite_configured,
    get_active_model,
    get_fallback_model,
    is_preset_configured,
    get_language_display_name,
    get_language_flag,
)
from .audio_recorder import AudioRecorder
from .transcription import get_client, TranscriptionResult
from .audio_processor import (
    compress_audio_for_api,
    archive_audio,
    get_audio_info,
    combine_wav_segments,
)
from .markdown_widget import MarkdownTextWidget
from .database_mongo import get_db, AUDIO_ARCHIVE_DIR
from .vad_processor import remove_silence, is_vad_available
from .hotkeys import (
    create_hotkey_listener,
    HotkeyCapture,
    SUGGESTED_HOTKEYS,
    HOTKEY_DESCRIPTIONS,
    HOTKEY_MODE_NAMES,
    HOTKEY_MODE_DESCRIPTIONS,
)
from .cost_tracker import get_tracker
from .history_window import HistoryWindow
from .file_transcription_window import FileTranscriptionWindow
from .analytics_widget import AnalyticsDialog
from .analysis_widget import format_word_count
from .settings_widget import SettingsDialog
from .about_widget import AboutDialog
from .audio_feedback import get_feedback
from .tts_announcer import get_announcer
from .prompt_library import PromptLibrary, build_prompt_from_config
from .stack_builder import StackBuilderWidget
from .prompt_editor_window import PromptEditorWindow
from .rewrite_dialog import RewriteDialog
from .ui_utils import get_provider_icon, get_model_icon
from .clipboard import copy_to_clipboard
from .recent_panel import RecentPanel
from .transcription_queue import TranscriptionQueue
from .output_panel import DualOutputPanel


class HotkeyEdit(QLineEdit):
    """A QLineEdit that captures hotkey presses when focused."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setPlaceholderText("Click and press a key...")
        self.capture: HotkeyCapture | None = None

    def focusInEvent(self, event):
        """Start capturing when focused."""
        super().focusInEvent(event)
        self.setStyleSheet("background-color: #fff3cd; border: 2px solid #ffc107;")
        self.setPlaceholderText("Press a key combination...")

        # Start key capture
        self.capture = HotkeyCapture(self._on_key_captured)
        self.capture.start()

    def focusOutEvent(self, event):
        """Stop capturing when focus is lost."""
        super().focusOutEvent(event)
        self.setStyleSheet("")
        self.setPlaceholderText("Click and press a key...")

        if self.capture:
            self.capture.stop()
            self.capture = None

    def _on_key_captured(self, hotkey_str: str):
        """Handle captured hotkey."""
        # Update on main thread
        QTimer.singleShot(0, lambda: self._set_hotkey(hotkey_str))

    def _set_hotkey(self, hotkey_str: str):
        """Set the hotkey text (called on main thread)."""
        self.setText(hotkey_str.upper())
        self.clearFocus()

    def keyPressEvent(self, event):
        """Handle key press - allow Escape to clear, Delete/Backspace to remove."""
        if event.key() == Qt.Key.Key_Escape:
            self.clearFocus()
        elif event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.clear()
            self.clearFocus()
        # Don't call super - we handle key capture separately


class TranscriptionWorker(QThread):
    """Worker thread for transcription API calls."""

    finished = pyqtSignal(TranscriptionResult)
    error = pyqtSignal(str)
    status = pyqtSignal(str)
    # Signal for VAD results: (processed_audio, original_duration, vad_duration)
    vad_complete = pyqtSignal(float, float)

    def __init__(
        self,
        audio_data: bytes,
        api_key: str,
        model: str,
        prompt: str,
        vad_enabled: bool = False,
    ):
        super().__init__()
        self.audio_data = audio_data
        self.api_key = api_key
        self.model = model
        self.prompt = prompt
        self.vad_enabled = vad_enabled
        self.inference_time_ms: int = 0
        self.original_duration: float | None = None
        self.vad_duration: float | None = None

    def run(self):
        try:
            audio_data = self.audio_data

            # Apply VAD if enabled (now in background thread!)
            if self.vad_enabled and is_vad_available():
                self.status.emit("Removing silence...")
                try:
                    audio_data, orig_dur, vad_dur = remove_silence(audio_data)
                    self.original_duration = orig_dur
                    self.vad_duration = vad_dur
                    self.vad_complete.emit(orig_dur, vad_dur)
                    if vad_dur < orig_dur:
                        reduction = (1 - vad_dur / orig_dur) * 100
                        print(
                            f"VAD: Reduced audio from {orig_dur:.1f}s to {vad_dur:.1f}s ({reduction:.0f}% reduction)"
                        )
                except Exception as e:
                    print(f"VAD failed, using original audio: {e}")

            # Compress audio to 16kHz mono before sending
            self.status.emit("Compressing audio...")
            compressed_audio = compress_audio_for_api(audio_data)

            self.status.emit("Transcribing...")
            start_time = time.time()
            client = get_client(self.api_key, self.model)
            result = client.transcribe(compressed_audio, self.prompt)
            self.inference_time_ms = int((time.time() - start_time) * 1000)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class RewriteWorker(QThread):
    """Worker thread for text rewriting API calls."""

    finished = pyqtSignal(TranscriptionResult)
    error = pyqtSignal(str)
    status = pyqtSignal(str)

    def __init__(
        self,
        text: str,
        instruction: str,
        api_key: str,
        model: str,
    ):
        super().__init__()
        self.text = text
        self.instruction = instruction
        self.api_key = api_key
        self.model = model
        self.inference_time_ms: int = 0

    def run(self):
        try:
            self.status.emit("Rewriting...")
            start_time = time.time()
            client = get_client(self.api_key, self.model)
            result = client.rewrite_text(self.text, self.instruction)
            self.inference_time_ms = int((time.time() - start_time) * 1000)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class TitleGeneratorWorker(QThread):
    """Worker thread for title generation."""

    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, text: str, api_key: str, model: str):
        super().__init__()
        self.text = text
        self.api_key = api_key
        self.model = model

    def run(self):
        try:
            client = get_client(self.api_key, self.model)
            title = client.generate_title(self.text)
            self.finished.emit(title)
        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    """Main application window."""

    # Signal for handling mic errors from background thread
    mic_error = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.config = load_env_keys(load_config())

        # Initialize TTS announcer with configured voice pack
        from .tts_announcer import get_announcer
        get_announcer(self.config.tts_voice_pack)

        self.recorder = AudioRecorder(self.config.sample_rate)
        self.recorder.on_error = self._on_recorder_error
        self.worker: TranscriptionWorker | None = None
        self.rewrite_worker: RewriteWorker | None = None
        self.title_worker: TitleGeneratorWorker | None = None
        self.recording_duration = 0.0
        self.accumulated_segments: list[bytes] = []  # For append mode
        self.accumulated_duration: float = 0.0
        self.append_mode: bool = False  # Track if next transcription should append
        self.has_cached_audio: bool = (
            False  # Track if we have stopped audio waiting to be transcribed
        )
        self.has_failed_audio: bool = (
            False  # Track if we have audio from a failed transcription (for retry)
        )
        self._failover_in_progress: bool = False  # Track if we're currently in a failover attempt

        # Initialize unified prompt library
        self.prompt_library = PromptLibrary(CONFIG_DIR)
        self.current_prompt_id = self.config.format_preset or "general"

        # Set window title (add DEV suffix if in dev mode)
        title = "AI Transcription Utility"
        if os.environ.get("VOICE_NOTEPAD_DEV_MODE") == "1":
            title += " (DEV)"
        self.setWindowTitle(title)
        self.setMinimumSize(900, 850)
        self.resize(self.config.window_width, self.config.window_height)

        self.setup_ui()
        self.setup_tray()
        self.setup_timer()
        self.setup_shortcuts()
        self.setup_global_hotkeys()

        # Connect mic error signal (for thread-safe error handling)
        self.mic_error.connect(self._handle_mic_error)

        # Start minimized if configured
        if self.config.start_minimized:
            self.hide()

    def _on_recorder_error(self, error_msg: str):
        """Called from recorder thread when an error occurs."""
        # Emit signal to handle on main thread
        self.mic_error.emit(error_msg)

    def _handle_mic_error(self, error_msg: str):
        """Handle microphone error on main thread."""
        self.timer.stop()
        self.status_label.setText(f"⚠️ {error_msg}")
        self.status_label.setStyleSheet("color: rgba(220, 53, 69, 0.7); font-size: 11px;")
        self.status_label.show()
        self.tray.showMessage(
            "AI Transcription Utility",
            error_msg,
            QSystemTrayIcon.MessageIcon.Warning,
            3000,
        )
        # Stop visual effects (pulsating, grayscale)
        self._stop_recording_visual_effects()
        # Reset UI but keep any recorded audio or failed audio
        self.record_btn.setText("●")
        self.record_btn.setStyleSheet(self._record_btn_idle_style)
        self.record_btn.setEnabled(True)
        self.retake_btn.setEnabled(False)
        # Keep transcribe enabled if we have cached audio or failed audio
        if self.accumulated_segments:
            self.has_cached_audio = True
            self.stop_btn.setEnabled(False)
            self.transcribe_btn.setEnabled(True)
            self.transcribe_btn.setStyleSheet(self._transcribe_btn_idle_style)  # Green when cached
            self.append_btn.setEnabled(True)
            self.delete_btn.setEnabled(True)
        elif self.has_failed_audio:
            # Keep retry UI state
            self.stop_btn.setEnabled(False)
            self.transcribe_btn.setEnabled(True)
            self.transcribe_btn.setStyleSheet(self._transcribe_btn_idle_style)
            self.append_btn.setEnabled(False)
            self.delete_btn.setEnabled(True)
        else:
            self.has_cached_audio = False
            self.stop_btn.setEnabled(False)
            self.transcribe_btn.setEnabled(False)
            self.append_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
        self._set_tray_state("idle")

    def _cleanup_worker(self, worker_attr: str, timeout_ms: int = 2000):
        """Safely clean up a worker thread before creating a new one.

        Args:
            worker_attr: Name of the worker attribute (e.g., 'worker', 'rewrite_worker')
            timeout_ms: How long to wait for the thread to finish (in milliseconds)
        """
        worker = getattr(self, worker_attr, None)
        if worker is None:
            return

        # Disconnect all signals to prevent callbacks from old worker
        try:
            worker.finished.disconnect()
        except (TypeError, RuntimeError):
            pass  # Already disconnected or object deleted
        try:
            worker.error.disconnect()
        except (TypeError, RuntimeError):
            pass
        try:
            if hasattr(worker, "status"):
                worker.status.disconnect()
        except (TypeError, RuntimeError):
            pass
        try:
            if hasattr(worker, "vad_complete"):
                worker.vad_complete.disconnect()
        except (TypeError, RuntimeError):
            pass
        try:
            if hasattr(worker, "progress"):
                worker.progress.disconnect()
        except (TypeError, RuntimeError):
            pass

        # Request thread to quit and wait for it
        if worker.isRunning():
            worker.quit()
            if not worker.wait(timeout_ms):
                # Thread didn't finish in time, force terminate (last resort)
                print(f"Warning: {worker_attr} thread did not finish in time, terminating")
                worker.terminate()
                worker.wait(1000)

        # Clear the reference
        setattr(self, worker_attr, None)

    def _cleanup_all_workers(self):
        """Clean up all worker threads. Called on application quit."""
        self._cleanup_worker("worker")
        self._cleanup_worker("rewrite_worker")
        self._cleanup_worker("title_worker")

    def setup_ui(self):
        """Set up the main UI with tabs."""
        # Create menu bar
        menubar = self.menuBar()

        # Prompts menu
        prompts_menu = menubar.addMenu("Prompts")
        manage_prompts_action = QAction("Manage Prompts...", self)
        manage_prompts_action.triggered.connect(self._open_prompt_editor)
        prompts_menu.addAction(manage_prompts_action)

        # View menu
        view_menu = menubar.addMenu("View")
        history_action = QAction("Transcription History", self)
        history_action.setShortcut("Ctrl+Shift+H")
        history_action.triggered.connect(self.show_history_window)
        view_menu.addAction(history_action)
        view_menu.addSeparator()
        analytics_action = QAction("Analytics...", self)
        analytics_action.triggered.connect(self.show_analytics)
        view_menu.addAction(analytics_action)

        # Beta menu (experimental features)
        beta_menu = menubar.addMenu("Beta")
        file_transcription_action = QAction("File Transcription...", self)
        file_transcription_action.triggered.connect(self.show_file_transcription_window)
        beta_menu.addAction(file_transcription_action)

        # Settings menu
        settings_menu = menubar.addMenu("Settings")
        preferences_action = QAction("Preferences...", self)
        preferences_action.triggered.connect(self.show_settings)
        settings_menu.addAction(preferences_action)

        # Help menu
        help_menu = menubar.addMenu("Help")
        about_action = QAction("About AI Transcription Utility...", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(12, 12, 12, 12)

        # Recording controls container with subtle background
        recording_container = QFrame()
        recording_container.setObjectName("recordingContainer")
        recording_container.setStyleSheet("""
            QFrame#recordingContainer {
                background-color: #f8f9fa;
                border: 1px solid #e9ecef;
                border-radius: 8px;
            }
        """)
        recording_layout = QVBoxLayout(recording_container)
        recording_layout.setSpacing(6)
        recording_layout.setContentsMargins(16, 12, 16, 12)

        # Recording controls (centered)
        control_bar = QHBoxLayout()
        control_bar.setSpacing(8)
        control_bar.addStretch()

        # Recording controls - using icons for compact display
        self.record_btn = QPushButton("●")  # Record icon
        self.record_btn.setMinimumHeight(42)
        self.record_btn.setMinimumWidth(50)
        self.record_btn.setToolTip(
            "Record\nStart a new recording.\nClears any cached audio and begins fresh."
        )
        self._record_btn_idle_style = """
            QPushButton {
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #e84c5a, stop:1 #dc3545);
                color: white;
                border: none;
                border-bottom: 3px solid #a71d2a;
                border-radius: 6px;
                font-weight: bold;
                font-size: 20px;
                padding: 0 8px;
            }
            QPushButton:hover {
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #dc3545, stop:1 #c82333);
            }
        """
        self._record_btn_recording_style = """
            QPushButton {
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ff3333, stop:1 #ff0000);
                color: white;
                border: 3px solid #ff6666;
                border-bottom: 4px solid #cc0000;
                border-radius: 6px;
                font-weight: bold;
                font-size: 20px;
                padding: 0 8px;
            }
            QPushButton:hover {
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ff0000, stop:1 #cc0000);
            }
        """
        self.record_btn.setStyleSheet(self._record_btn_idle_style)
        self.record_btn.clicked.connect(self.toggle_recording)
        control_bar.addWidget(self.record_btn)

        self.retake_btn = QPushButton("↺")  # Retake/restart icon
        self.retake_btn.setMinimumHeight(36)
        self.retake_btn.setMinimumWidth(44)
        self.retake_btn.setEnabled(False)
        self.retake_btn.setToolTip(
            "Retake\nDiscard current recording and start fresh.\nQuickly restart without transcribing."
        )
        self.retake_btn.setStyleSheet("""
            QPushButton {
                background-color: #fd7e14;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 16px;
                padding: 0 8px;
            }
            QPushButton:hover {
                background-color: #e96b02;
            }
            QPushButton:disabled {
                background-color: #6c757d;
                color: #aaa;
            }
        """)
        self.retake_btn.clicked.connect(self.retake_recording)
        control_bar.addWidget(self.retake_btn)

        self.append_btn = QPushButton("+")  # Append/plus icon
        self.append_btn.setMinimumHeight(36)
        self.append_btn.setMinimumWidth(44)
        self.append_btn.setEnabled(False)
        self.append_btn.setToolTip(
            "Append\n"
            "Record additional audio and combine with cached audio.\n"
            "Useful for recording in segments - all clips are transcribed together."
        )
        self.append_btn.setStyleSheet("""
            QPushButton {
                background-color: #17a2b8;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 16px;
                padding: 0 8px;
            }
            QPushButton:hover {
                background-color: #138496;
            }
            QPushButton:disabled {
                background-color: #6c757d;
                color: #aaa;
            }
        """)
        self.append_btn.clicked.connect(self.append_to_transcription)
        control_bar.addWidget(self.append_btn)

        self.stop_btn = QPushButton("■")  # Stop icon (filled square)
        self.stop_btn.setMinimumHeight(36)
        self.stop_btn.setMinimumWidth(44)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setToolTip(
            "Stop\n"
            "Stop recording and cache audio without transcribing.\n"
            "You can then Append more clips, Transcribe, or Delete."
        )
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #ffc107;
                color: black;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 16px;
                padding: 0 8px;
            }
            QPushButton:hover {
                background-color: #e0a800;
            }
            QPushButton:disabled {
                background-color: #6c757d;
                color: #aaa;
            }
        """)
        self.stop_btn.clicked.connect(self.handle_stop_button)
        control_bar.addWidget(self.stop_btn)

        self.transcribe_btn = QPushButton("⬆")  # Transcribe/send icon (vertical arrow)
        self.transcribe_btn.setMinimumHeight(36)
        self.transcribe_btn.setMinimumWidth(44)
        self.transcribe_btn.setEnabled(False)
        self.transcribe_btn.setToolTip(
            "Transcribe\n"
            "Transcribe audio to text.\n"
            "• While recording: Stops and transcribes immediately\n"
            "• After stopping: Transcribes cached audio"
        )
        self._transcribe_btn_idle_style = """
            QPushButton {
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #90EE90, stop:1 #7CCD7C);
                color: #1a5c1a;
                border: none;
                border-bottom: 3px solid #5CB85C;
                border-radius: 6px;
                font-weight: bold;
                font-size: 16px;
                padding: 0 8px;
            }
            QPushButton:hover {
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #7CCD7C, stop:1 #6BBF6B);
            }
            QPushButton:disabled {
                background-color: #6c757d;
                color: #aaa;
                border-bottom: none;
            }
        """
        self._transcribe_btn_recording_style = """
            QPushButton {
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ffd43b, stop:1 #ffc107);
                color: black;
                border: none;
                border-bottom: 3px solid #c59600;
                border-radius: 6px;
                font-weight: bold;
                font-size: 16px;
                padding: 0 8px;
            }
            QPushButton:hover {
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ffc107, stop:1 #e0a800);
            }
            QPushButton:disabled {
                background-color: #6c757d;
                color: #aaa;
                border-bottom: none;
            }
        """
        self.transcribe_btn.setStyleSheet(self._transcribe_btn_idle_style)
        self.transcribe_btn.clicked.connect(self.stop_and_transcribe)
        control_bar.addWidget(self.transcribe_btn)

        self.delete_btn = QPushButton("✕")  # Delete/X icon
        self.delete_btn.setMinimumHeight(36)
        self.delete_btn.setMinimumWidth(44)
        self.delete_btn.setEnabled(False)
        self.delete_btn.setToolTip(
            "Delete\n"
            "Discard all cached audio without transcribing.\n"
            "Use this to abandon a recording without sending it to the API."
        )
        self.delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 16px;
                padding: 0 8px;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
            QPushButton:disabled {
                background-color: #6c757d;
                color: #aaa;
            }
        """)
        self.delete_btn.clicked.connect(self.delete_recording)
        control_bar.addWidget(self.delete_btn)

        control_bar.addStretch()  # Balance the stretch to center controls

        # Duration display (to the right of controls)
        self.duration_container = QFrame()
        self.duration_container.setObjectName("durationContainer")
        self.duration_container.setStyleSheet("""
            QFrame#durationContainer {
                background-color: transparent;
                border: none;
            }
        """)
        self.duration_container.setFixedWidth(70)  # Wide enough for HH:MM:SS
        self.duration_container.hide()  # Visibility controlled by update_duration()
        duration_box_layout = QHBoxLayout(self.duration_container)
        duration_box_layout.setContentsMargins(8, 4, 8, 4)
        duration_box_layout.setSpacing(0)

        self.duration_label = QLabel("")
        self.duration_label.setFont(QFont("Monospace", 11))
        self.duration_label.setStyleSheet("color: #495057; font-weight: bold;")
        self.duration_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        duration_box_layout.addWidget(self.duration_label)

        control_bar.addWidget(self.duration_container)

        # Track last shown minute for fade animation
        self._last_shown_minute = 0

        recording_layout.addLayout(control_bar)

        # Status label is created in the bottom status bar section below

        # Segment indicator (for append mode)
        self.segment_label = QLabel("")
        self.segment_label.setStyleSheet("color: #6c757d; font-weight: bold; font-size: 11px;")
        self.segment_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.segment_label.hide()
        recording_layout.addWidget(self.segment_label)

        # Output mode buttons (where text goes after transcription)
        mode_layout = QHBoxLayout()
        mode_layout.setSpacing(8)
        mode_layout.addStretch()

        # Store buttons for easy access
        self._mode_buttons = {}

        # Common style for mode buttons
        self._mode_btn_inactive_style = """
            QPushButton {
                background-color: #f8f9fa;
                color: #6c757d;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                padding: 4px 12px;
                font-size: 11px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #e9ecef;
                color: #495057;
            }
        """
        self._mode_btn_active_style = """
            QPushButton {
                background-color: #28a745;
                color: white;
                border: 1px solid #28a745;
                border-radius: 4px;
                padding: 4px 12px;
                font-size: 11px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #218838;
                border-color: #218838;
            }
        """

        # App button (toggleable)
        self.mode_app_btn = QPushButton("App")
        self.mode_app_btn.setToolTip("App: Show text in app window")
        self.mode_app_btn.clicked.connect(lambda: self._toggle_output_mode("app"))
        self._mode_buttons["app"] = self.mode_app_btn
        mode_layout.addWidget(self.mode_app_btn)

        # Clipboard button (toggleable)
        self.mode_clipboard_btn = QPushButton("Clipboard")
        self.mode_clipboard_btn.setToolTip("Clipboard: Copy text to clipboard")
        self.mode_clipboard_btn.clicked.connect(lambda: self._toggle_output_mode("clipboard"))
        self._mode_buttons["clipboard"] = self.mode_clipboard_btn
        mode_layout.addWidget(self.mode_clipboard_btn)

        # Inject button (toggleable)
        self.mode_inject_btn = QPushButton("Inject")
        self.mode_inject_btn.setToolTip("Inject: Type text directly at cursor")
        self.mode_inject_btn.clicked.connect(lambda: self._toggle_output_mode("inject"))
        self._mode_buttons["inject"] = self.mode_inject_btn
        mode_layout.addWidget(self.mode_inject_btn)

        # Add spacing before VAD checkbox
        mode_layout.addSpacing(12)

        # VAD checkbox (silence removal)
        self.vad_checkbox = QCheckBox("VAD")
        self.vad_checkbox.setToolTip(
            "Voice Activity Detection\n"
            "Remove silence from audio before transcription.\n"
            "Reduces API costs and improves accuracy."
        )
        self.vad_checkbox.setChecked(self.config.vad_enabled)
        self.vad_checkbox.stateChanged.connect(self._on_vad_checkbox_changed)
        self.vad_checkbox.setStyleSheet("""
            QCheckBox {
                color: #495057;
                font-size: 11px;
                font-weight: bold;
                spacing: 4px;
            }
        """)
        mode_layout.addWidget(self.vad_checkbox)

        # Status label (right side) - shows recording/transcribing state
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("""
            QLabel {
                color: rgba(108, 117, 125, 0.7);
                font-size: 11px;
            }
        """)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.status_label.setMinimumWidth(100)  # Ensure enough space for status text
        self.status_label.hide()
        mode_layout.addWidget(self.status_label)

        mode_layout.addStretch()
        recording_layout.addLayout(mode_layout)

        # Apply initial button styles based on current mode
        self._update_mode_button_styles()

        # Add the recording container to main layout
        main_layout.addWidget(recording_container)

        # Main content area (formerly the Record tab)
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setSpacing(12)
        layout.setContentsMargins(8, 12, 8, 8)

        # Prompt Stack Builder - columnar interface for building prompts
        presets_section_layout = QVBoxLayout()
        presets_section_layout.setSpacing(8)

        # Prompt library for custom prompts (used by stack builder)
        self.prompt_library = PromptLibrary(CONFIG_DIR)

        # Stack Builder widget with Format, Tone, Style, and Stacks accordions
        self.stack_builder = StackBuilderWidget(self.config, CONFIG_DIR)
        self.stack_builder.prompt_changed.connect(self._on_stack_changed)
        presets_section_layout.addWidget(self.stack_builder)

        # Personalization and Date row
        personalization_layout = QHBoxLayout()
        personalization_layout.setSpacing(10)

        self.personalize_checkbox = QCheckBox("Personalize")
        self.personalize_checkbox.setChecked(self.config.personalization_enabled)
        self.personalize_checkbox.setToolTip(
            "Include your name, email, and signature in the output.\n"
            "Configure personalization details in Settings → Personalization.\n"
            "Note: Always enabled for Email format."
        )
        self.personalize_checkbox.toggled.connect(self._on_personalize_toggled)
        personalization_layout.addWidget(self.personalize_checkbox)

        # Info button with tooltip for personalization
        personalize_info_btn = QToolButton()
        personalize_info_btn.setText("ⓘ")
        personalize_info_btn.setStyleSheet("""
            QToolButton {
                border: none;
                color: #888;
                font-size: 14px;
                padding: 0px 4px;
            }
            QToolButton:hover {
                color: #555;
            }
        """)
        personalize_info_btn.setToolTip(
            "Personalization fields:\n"
            "• Full Name - Used for formal sign-offs\n"
            "• Short Name - Used for casual sign-offs\n"
            "• Email address - Injected into emails\n"
            "• Signature - Full signature block\n\n"
            "Configure in Settings → Personalization"
        )
        personalization_layout.addWidget(personalize_info_btn)

        personalization_layout.addSpacing(20)

        self.add_date_checkbox = QCheckBox("Add Date")
        self.add_date_checkbox.setChecked(self.config.add_date_enabled)
        self.add_date_checkbox.setToolTip("Include today's date in the output where appropriate")
        self.add_date_checkbox.toggled.connect(self._on_add_date_toggled)
        personalization_layout.addWidget(self.add_date_checkbox)

        personalization_layout.addStretch()
        presets_section_layout.addLayout(personalization_layout)

        # TLDR modifier row
        tldr_layout = QHBoxLayout()
        tldr_layout.setSpacing(10)

        self.tldr_checkbox = QCheckBox("Add TLDR")
        self.tldr_checkbox.setChecked(self.config.tldr_enabled)
        self.tldr_checkbox.setToolTip("Add a TLDR/summary section to the output")
        self.tldr_checkbox.toggled.connect(self._on_tldr_toggled)
        tldr_layout.addWidget(self.tldr_checkbox)

        tldr_position_label = QLabel("Position:")
        tldr_position_label.setStyleSheet("color: #666;")
        tldr_layout.addWidget(tldr_position_label)

        self.tldr_position_combo = QComboBox()
        self.tldr_position_combo.addItems(["Top", "Bottom"])
        self.tldr_position_combo.setCurrentText(self.config.tldr_position.capitalize())
        self.tldr_position_combo.setFixedWidth(80)
        self.tldr_position_combo.currentTextChanged.connect(self._on_tldr_position_changed)
        tldr_layout.addWidget(self.tldr_position_combo)

        tldr_layout.addStretch()
        presets_section_layout.addLayout(tldr_layout)

        layout.addLayout(presets_section_layout)

        # Text output area - dual panel for queue mode
        self.output_panel = DualOutputPanel()
        self.output_panel.setMinimumHeight(120)
        self.output_panel.copy_clicked.connect(self._on_output_copy_clicked)
        self.output_panel.text_changed.connect(self.update_word_count)
        layout.addWidget(self.output_panel, 1)

        # Legacy compatibility: text_output points to slot1's text widget
        self.text_output = self.output_panel.slot1.text_widget

        # Create transcription queue
        self.transcription_queue = TranscriptionQueue(
            max_concurrent=self.config.queue_max_concurrent
        )
        self.transcription_queue.item_started.connect(self._on_queue_item_started)
        self.transcription_queue.item_complete.connect(self._on_queue_item_complete)
        self.transcription_queue.item_error.connect(self._on_queue_item_error)
        self.transcription_queue.item_status.connect(self._on_queue_item_status)
        self.transcription_queue.queue_changed.connect(self._on_queue_changed)

        # Word count label
        self.word_count_label = QLabel("")
        self.word_count_label.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(self.word_count_label)

        # Connect text changes to word count update
        self.text_output.textChanged.connect(self.update_word_count)

        # Bottom status bar: microphone selector (left), model selector (right)
        status_bar = QHBoxLayout()

        # Pill label style (shared by both labels)
        pill_label_style = """
            QLabel {
                color: #888;
                font-size: 10px;
                background-color: #f0f0f0;
                border-radius: 8px;
                padding: 2px 8px;
            }
        """

        # Microphone label (left)
        mic_label = QLabel("Microphone")
        mic_label.setStyleSheet(pill_label_style)
        status_bar.addWidget(mic_label)
        status_bar.addSpacing(4)

        # Microphone selector (left) - dropdown button
        self.mic_selector_btn = QToolButton()
        self.mic_selector_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.mic_selector_btn.setStyleSheet("""
            QToolButton {
                color: #888;
                font-size: 11px;
                border: none;
                padding: 2px 4px;
            }
            QToolButton:hover {
                background-color: rgba(0, 0, 0, 0.05);
                border-radius: 4px;
            }
            QToolButton::menu-indicator {
                width: 0;
                height: 0;
            }
        """)
        self.mic_selector_btn.setToolTip("Click to change microphone")
        self._setup_microphone_menu()
        status_bar.addWidget(self.mic_selector_btn)

        # Translation indicator (shown only when translation mode is active)
        self.translation_indicator = QLabel()
        self.translation_indicator.setStyleSheet("""
            QLabel {
                color: #0d6efd;
                font-size: 11px;
                background-color: #e7f3ff;
                border: 1px solid #b6d4fe;
                border-radius: 10px;
                padding: 2px 10px;
                font-weight: bold;
            }
        """)
        self.translation_indicator.setToolTip("Translation mode is active - transcriptions will be translated")
        self.translation_indicator.hide()  # Hidden by default
        status_bar.addWidget(self.translation_indicator)

        status_bar.addStretch()

        # Model label (right)
        model_label = QLabel("Model")
        model_label.setStyleSheet(pill_label_style)
        status_bar.addWidget(model_label)
        status_bar.addSpacing(4)

        # Model selector (right) - dropdown button
        self.model_selector_btn = QToolButton()
        self.model_selector_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.model_selector_btn.setStyleSheet("""
            QToolButton {
                color: #888;
                font-size: 11px;
                border: none;
                padding: 2px 4px;
            }
            QToolButton:hover {
                background-color: rgba(0, 0, 0, 0.05);
                border-radius: 4px;
            }
            QToolButton::menu-indicator {
                width: 0;
                height: 0;
            }
        """)
        self.model_selector_btn.setToolTip("Click to change model preset")
        self._setup_model_preset_menu()
        status_bar.addWidget(self.model_selector_btn)

        layout.addLayout(status_bar)

        # Initialize mic, model, and translation displays
        self._update_mic_display()
        self._update_model_display()
        self._update_translation_indicator()

        # Add content widget to main layout
        main_layout.addWidget(content_widget, 1)

        # Prompt Editor window (opened via button, not a tab)
        self.prompt_editor_window = None

        # Dialogs and windows (opened via menu)
        self.settings_dialog = None
        self.analytics_dialog = None
        self.about_dialog = None
        self.history_window = None
        self.file_transcription_window = None

        # Recent Transcriptions Panel (collapsible)
        self.recent_panel = RecentPanel(
            database=get_db(),
            max_items=self.config.recent_panel_max_items,
        )
        self.recent_panel.set_collapsed(self.config.recent_panel_collapsed)
        self.recent_panel.view_all_clicked.connect(self.show_history_window)
        self.recent_panel.transcript_selected.connect(self._load_transcript_from_history)
        self.recent_panel.transcript_copied.connect(self._on_recent_copied)
        main_layout.addWidget(self.recent_panel)

        # Persistent audio feedback footer
        feedback_footer = QHBoxLayout()
        feedback_footer.setSpacing(8)
        feedback_footer.setContentsMargins(0, 8, 0, 0)

        feedback_footer.addStretch()

        # Notification Mode label
        notification_mode_label = QLabel("Notification Mode")
        notification_mode_label.setStyleSheet("""
            QLabel {
                color: #888;
                font-size: 10px;
                background-color: #f0f0f0;
                border-radius: 8px;
                padding: 2px 8px;
            }
        """)
        feedback_footer.addWidget(notification_mode_label)
        feedback_footer.addSpacing(8)

        # Create button group for mutual exclusion
        self._feedback_buttons = {}
        feedback_btn_style = """
            QPushButton {
                background-color: #f0f0f0;
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 4px 12px;
                font-size: 11px;
                color: #555;
            }
            QPushButton:hover {
                background-color: #e8e8e8;
            }
            QPushButton:checked {
                background-color: #007bff;
                border-color: #007bff;
                color: white;
            }
        """

        quiet_btn = QPushButton("Quiet")
        quiet_btn.setCheckable(True)
        quiet_btn.setStyleSheet(feedback_btn_style)
        quiet_btn.clicked.connect(lambda: self._set_audio_feedback_mode("silent"))
        self._feedback_buttons["silent"] = quiet_btn
        feedback_footer.addWidget(quiet_btn)

        tts_btn = QPushButton("TTS")
        tts_btn.setCheckable(True)
        tts_btn.setStyleSheet(feedback_btn_style)
        tts_btn.clicked.connect(lambda: self._set_audio_feedback_mode("tts"))
        self._feedback_buttons["tts"] = tts_btn
        feedback_footer.addWidget(tts_btn)

        beeps_btn = QPushButton("Beeps")
        beeps_btn.setCheckable(True)
        beeps_btn.setStyleSheet(feedback_btn_style)
        beeps_btn.clicked.connect(lambda: self._set_audio_feedback_mode("beeps"))
        self._feedback_buttons["beeps"] = beeps_btn
        feedback_footer.addWidget(beeps_btn)

        feedback_footer.addStretch()

        # All-time word count display
        self.all_time_word_count_label = QLabel("")
        self.all_time_word_count_label.setStyleSheet("""
            QLabel {
                color: #888;
                font-size: 10px;
            }
        """)
        self.all_time_word_count_label.setToolTip("Total words transcribed across all sessions")
        feedback_footer.addWidget(self.all_time_word_count_label)
        feedback_footer.addSpacing(12)

        # Open History link button
        history_link = QPushButton("Open History")
        history_link.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                color: #007bff;
                font-size: 11px;
                text-decoration: underline;
                padding: 4px 8px;
            }
            QPushButton:hover {
                color: #0056b3;
            }
        """)
        history_link.setCursor(Qt.CursorShape.PointingHandCursor)
        history_link.setToolTip("Open transcription history in a separate window (Ctrl+Shift+H)")
        history_link.clicked.connect(self.show_history_window)
        feedback_footer.addWidget(history_link)

        main_layout.addLayout(feedback_footer)

        # Set initial state based on config
        self._update_feedback_buttons()
        self._update_all_time_word_count()

    def setup_tray(self):
        """Set up system tray icon."""
        self.tray = QSystemTrayIcon(self)

        # Track tray state for click behavior and menu updates
        # States: 'idle', 'recording', 'stopped', 'transcribing', 'complete'
        self._tray_state = "idle"

        # Set up icons for different states
        # Idle: notepad/text editor icon (common in KDE themes)
        self._tray_icon_idle = QIcon.fromTheme(
            "accessories-text-editor",
            QIcon.fromTheme(
                "text-x-generic",
                self.style().standardIcon(self.style().StandardPixmap.SP_FileDialogDetailedView),
            ),
        )
        # Recording: red record icon
        self._tray_icon_recording = QIcon.fromTheme(
            "media-record", self.style().standardIcon(self.style().StandardPixmap.SP_DialogNoButton)
        )
        # Stopped: pause icon (recording stopped, awaiting user decision)
        self._tray_icon_stopped = QIcon.fromTheme(
            "media-playback-pause",
            QIcon.fromTheme(
                "player-pause", self.style().standardIcon(self.style().StandardPixmap.SP_MediaPause)
            ),
        )
        # Transcribing: process/sync icon (horizontal bar style)
        self._tray_icon_transcribing = QIcon.fromTheme(
            "emblem-synchronizing",
            QIcon.fromTheme(
                "view-refresh",
                self.style().standardIcon(self.style().StandardPixmap.SP_BrowserReload),
            ),
        )
        # Complete: green tick/checkmark
        self._tray_icon_complete = QIcon.fromTheme(
            "emblem-ok",
            QIcon.fromTheme(
                "dialog-ok",
                self.style().standardIcon(self.style().StandardPixmap.SP_DialogApplyButton),
            ),
        )
        # Clipboard complete: clipboard/paste icon
        self._tray_icon_clipboard = QIcon.fromTheme(
            "edit-paste",
            QIcon.fromTheme(
                "clipboard",
                self.style().standardIcon(self.style().StandardPixmap.SP_FileDialogContentsView),
            ),
        )
        # Inject complete: keyboard/input icon
        self._tray_icon_inject = QIcon.fromTheme(
            "input-keyboard",
            QIcon.fromTheme(
                "preferences-desktop-keyboard",
                self.style().standardIcon(self.style().StandardPixmap.SP_ComputerIcon),
            ),
        )

        self.tray.setIcon(self._tray_icon_idle)
        self.setWindowIcon(self._tray_icon_idle)

        # Tray menu - dynamic based on state
        self._tray_menu = QMenu()

        # Store actions as instance variables for dynamic visibility
        # Using Unicode symbols for visual clarity in menus
        self._tray_show_action = QAction("👁  Show Window", self)
        self._tray_show_action.triggered.connect(self.show_window)

        self._tray_record_action = QAction("●  Start Recording", self)
        self._tray_record_action.triggered.connect(self.toggle_recording)

        self._tray_stop_action = QAction("■  Stop Recording", self)
        self._tray_stop_action.triggered.connect(self._tray_stop_recording)

        self._tray_retake_action = QAction("↺  Retake", self)
        self._tray_retake_action.triggered.connect(self._tray_retake_recording)

        self._tray_send_action = QAction("⬆  Send", self)
        self._tray_send_action.triggered.connect(self._tray_send_for_transcription)

        self._tray_transcribe_action = QAction("⬆  Transcribe", self)
        self._tray_transcribe_action.triggered.connect(self._tray_transcribe_stopped)

        self._tray_delete_action = QAction("✕  Discard", self)
        self._tray_delete_action.triggered.connect(self._tray_delete_stopped)

        # Discard action for recording state (stops and discards without transcribing)
        self._tray_discard_action = QAction("✕  Discard", self)
        self._tray_discard_action.triggered.connect(self._tray_discard_recording)

        self._tray_resume_action = QAction("+  Append Clip", self)
        self._tray_resume_action.triggered.connect(self._tray_resume_recording)

        # Utility actions
        self._tray_copy_action = QAction("📋  Copy to Clipboard", self)
        self._tray_copy_action.triggered.connect(self.copy_to_clipboard)

        self._tray_history_action = QAction("📜  History", self)
        self._tray_history_action.triggered.connect(self.show_history_window)

        self._tray_settings_action = QAction("⚙  Settings", self)
        self._tray_settings_action.triggered.connect(self.show_settings)

        self._tray_quit_action = QAction("⏻  Quit", self)
        self._tray_quit_action.triggered.connect(self.quit_app)

        # Mode submenu with independently checkable actions (can combine multiple)
        self._tray_mode_menu = QMenu("📤  Output To", self)
        self._tray_mode_actions = {}

        self._tray_mode_app_action = QAction("🖥  App", self)
        self._tray_mode_app_action.setCheckable(True)
        self._tray_mode_app_action.triggered.connect(lambda: self._tray_toggle_mode("app"))
        self._tray_mode_actions["app"] = self._tray_mode_app_action

        self._tray_mode_clipboard_action = QAction("📋  Clipboard", self)
        self._tray_mode_clipboard_action.setCheckable(True)
        self._tray_mode_clipboard_action.triggered.connect(
            lambda: self._tray_toggle_mode("clipboard")
        )
        self._tray_mode_actions["clipboard"] = self._tray_mode_clipboard_action

        self._tray_mode_inject_action = QAction("⌨  Inject", self)
        self._tray_mode_inject_action.setCheckable(True)
        self._tray_mode_inject_action.triggered.connect(lambda: self._tray_toggle_mode("inject"))
        self._tray_mode_actions["inject"] = self._tray_mode_inject_action

        # Build initial menu
        self._update_tray_menu()

        self.tray.setContextMenu(self._tray_menu)
        self.tray.activated.connect(self.on_tray_activated)
        self.tray.show()

    def setup_timer(self):
        """Set up timer for updating recording duration."""
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_duration)

        # Pulsation timer for record button animation
        self._pulse_timer = QTimer()
        self._pulse_timer.timeout.connect(self._on_pulse_timer)
        self._pulse_phase = 0.0  # 0.0 to 1.0, tracks animation phase

        # Balance polling timer - periodically fetches OpenRouter balance in background
        # This replaces per-transcription cost lookups for lower latency
        self._balance_poll_timer = QTimer()
        self._balance_poll_timer.timeout.connect(self._poll_openrouter_balance)
        # Start polling if OpenRouter is configured
        self._start_balance_polling()

    def _on_pulse_timer(self):
        """Handle pulsation animation for record button."""
        import math

        # Increment phase (complete cycle every ~2 seconds at 50ms intervals)
        self._pulse_phase += 0.025
        if self._pulse_phase > 1.0:
            self._pulse_phase = 0.0

        # Use sine wave for smooth pulsation (0.0 to 1.0)
        pulse = (math.sin(self._pulse_phase * 2 * math.pi) + 1) / 2

        # Interpolate between dim red and bright red
        # Dim: #cc0000, Bright: #ff4444
        r_dim, g_dim, b_dim = 0xCC, 0x00, 0x00
        r_bright, g_bright, b_bright = 0xFF, 0x44, 0x44

        r = int(r_dim + (r_bright - r_dim) * pulse)
        g = int(g_dim + (g_bright - g_dim) * pulse)
        b = int(b_dim + (b_bright - b_dim) * pulse)

        # Border brightness also pulses
        border_dim = 0x99
        border_bright = 0xFF
        border_val = int(border_dim + (border_bright - border_dim) * pulse)

        style = f"""
            QPushButton {{
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #{r:02x}{g:02x}{b:02x}, stop:1 #{max(r - 30, 0):02x}{max(g - 30, 0):02x}{max(b - 30, 0):02x});
                color: white;
                border: 3px solid #{border_val:02x}{border_val // 3:02x}{border_val // 3:02x};
                border-bottom: 4px solid #{max(r - 60, 0):02x}0000;
                border-radius: 6px;
                font-weight: bold;
                font-size: 20px;
                padding: 0 8px;
            }}
        """
        self.record_btn.setStyleSheet(style)

    def _start_recording_visual_effects(self):
        """Start pulsating record button animation."""
        # Start pulsation animation (50ms interval = 20 fps)
        self._pulse_phase = 0.0
        self._pulse_timer.start(50)

    def _stop_recording_visual_effects(self):
        """Stop pulsating record button animation."""
        # Stop pulsation animation
        self._pulse_timer.stop()

    def _start_balance_polling(self):
        """Start or restart the OpenRouter balance polling timer.

        Polls balance at the interval configured in settings (default 30 minutes).
        This runs independently of transcriptions to minimize latency.
        """
        # Stop existing timer if running
        self._balance_poll_timer.stop()

        # Only poll if OpenRouter API key is configured
        if not self.config.openrouter_api_key:
            return

        # Get interval from config (default 30 minutes)
        interval_minutes = getattr(self.config, 'balance_poll_interval_minutes', 30)
        interval_ms = interval_minutes * 60 * 1000

        # Start the timer
        self._balance_poll_timer.start(interval_ms)

        # Also do an initial poll right away (in background)
        QTimer.singleShot(1000, self._poll_openrouter_balance)

    def _poll_openrouter_balance(self):
        """Poll OpenRouter balance in background thread.

        Updates the cached balance data used by the Cost widget.
        This runs on a timer, not on each transcription.
        """
        if not self.config.openrouter_api_key:
            return

        def do_poll():
            try:
                from .openrouter_api import get_openrouter_api
                api = get_openrouter_api(self.config.openrouter_api_key)
                # These calls update the internal cache in openrouter_api
                api.get_credits(use_cache=False)
                api.get_key_info()
            except Exception as e:
                # Silently ignore polling errors - non-critical background task
                import logging
                logging.getLogger(__name__).debug(f"Balance poll failed: {e}")

        # Run in background thread to avoid blocking UI
        import threading
        thread = threading.Thread(target=do_poll, daemon=True)
        thread.start()

    def setup_shortcuts(self):
        """Set up keyboard shortcuts."""
        # Ctrl+R to start recording
        record_shortcut = QShortcut(QKeySequence("Ctrl+R"), self)
        record_shortcut.activated.connect(self.toggle_recording)

        # Ctrl+Space to retake (discard and restart)
        retake_shortcut = QShortcut(QKeySequence("Ctrl+Space"), self)
        retake_shortcut.activated.connect(self.retake_recording)

        # Ctrl+Return to stop and transcribe
        stop_shortcut = QShortcut(QKeySequence("Ctrl+Return"), self)
        stop_shortcut.activated.connect(self.stop_if_recording)

        # Ctrl+S to save
        save_shortcut = QShortcut(QKeySequence("Ctrl+S"), self)
        save_shortcut.activated.connect(self.save_to_file)

        # Ctrl+Shift+C to copy
        copy_shortcut = QShortcut(QKeySequence("Ctrl+Shift+C"), self)
        copy_shortcut.activated.connect(self.copy_to_clipboard)

        # Ctrl+N to clear
        clear_shortcut = QShortcut(QKeySequence("Ctrl+N"), self)
        clear_shortcut.activated.connect(self.clear_transcription)

        # Ctrl+H to open History window
        history_shortcut = QShortcut(QKeySequence("Ctrl+H"), self)
        history_shortcut.activated.connect(self.show_history_window)

        # Ctrl+1 through Ctrl+5 to copy recent transcriptions
        for i in range(5):
            shortcut = QShortcut(QKeySequence(f"Ctrl+{i + 1}"), self)
            shortcut.activated.connect(lambda idx=i: self._copy_recent_by_index(idx))

        # Set up configurable in-focus hotkeys (F15, F16, etc.)
        self._setup_configurable_shortcuts()

    def _setup_configurable_shortcuts(self):
        """Set up in-focus shortcuts using configured hotkeys.

        Note: Global hotkeys (work when app is minimized) are handled separately
        in setup_global_hotkeys(). These in-focus shortcuts provide additional
        responsiveness when the window has focus.
        """
        # Clean up old shortcuts if they exist
        shortcut_attrs = [
            "_shortcut_toggle",
            "_shortcut_tap_toggle",
            "_shortcut_transcribe",
            "_shortcut_clear",
            "_shortcut_append",
            "_shortcut_pause",
        ]
        for attr in shortcut_attrs:
            if hasattr(self, attr):
                shortcut = getattr(self, attr)
                shortcut.setEnabled(False)
                shortcut.deleteLater()

        # Toggle: start/stop and transcribe
        if self.config.hotkey_toggle:
            seq = self._hotkey_to_qt_sequence(self.config.hotkey_toggle)
            if seq:
                self._shortcut_toggle = QShortcut(seq, self)
                self._shortcut_toggle.activated.connect(self._hotkey_toggle_recording)

        # Tap toggle: start/stop and cache
        if self.config.hotkey_tap_toggle:
            seq = self._hotkey_to_qt_sequence(self.config.hotkey_tap_toggle)
            if seq:
                self._shortcut_tap_toggle = QShortcut(seq, self)
                self._shortcut_tap_toggle.activated.connect(self._hotkey_tap_toggle)

        # Transcribe: transcribe cached audio
        if self.config.hotkey_transcribe:
            seq = self._hotkey_to_qt_sequence(self.config.hotkey_transcribe)
            if seq:
                self._shortcut_transcribe = QShortcut(seq, self)
                self._shortcut_transcribe.activated.connect(self._hotkey_transcribe_only)

        # Clear: delete recording and cache
        if self.config.hotkey_clear:
            seq = self._hotkey_to_qt_sequence(self.config.hotkey_clear)
            if seq:
                self._shortcut_clear = QShortcut(seq, self)
                self._shortcut_clear.activated.connect(self._hotkey_delete)

        # Append: start recording to add to cache
        if self.config.hotkey_append:
            seq = self._hotkey_to_qt_sequence(self.config.hotkey_append)
            if seq:
                self._shortcut_append = QShortcut(seq, self)
                self._shortcut_append.activated.connect(self._hotkey_append)

        # Retake: discard current and start fresh recording
        if self.config.hotkey_retake:
            seq = self._hotkey_to_qt_sequence(self.config.hotkey_retake)
            if seq:
                self._shortcut_retake = QShortcut(seq, self)
                self._shortcut_retake.activated.connect(self._hotkey_retake)

    def _hotkey_to_qt_sequence(self, hotkey_str: str) -> QKeySequence | None:
        """Convert a hotkey string like 'f15' or 'ctrl+f15' to a QKeySequence."""
        if not hotkey_str:
            return None

        # Normalize and convert to Qt format
        parts = [p.strip().lower() for p in hotkey_str.split("+")]
        qt_parts = []

        for part in parts:
            # Handle modifiers
            if part == "ctrl":
                qt_parts.append("Ctrl")
            elif part == "alt":
                qt_parts.append("Alt")
            elif part == "shift":
                qt_parts.append("Shift")
            elif part == "super":
                qt_parts.append("Meta")
            # Handle function keys (f1-f24)
            elif part.startswith("f") and part[1:].isdigit():
                qt_parts.append(part.upper())  # F15, F16, etc.
            else:
                # Single character or other key
                qt_parts.append(part.upper())

        if qt_parts:
            return QKeySequence("+".join(qt_parts))
        return None

    def setup_global_hotkeys(self):
        """Set up global hotkeys that work even when app is not focused."""
        self.hotkey_listener = create_hotkey_listener()

        # Register configured hotkeys
        self._register_hotkeys()

        # Start listening
        self.hotkey_listener.start()

    def _register_hotkeys(self):
        """Register global hotkeys for all actions using config values.

        Hotkey functions (configurable via Settings → Hotkeys):
        - toggle: Simple toggle - Start recording / Stop and transcribe
        - tap_toggle: Tap toggle - Start recording / Stop and cache (for append mode)
        - transcribe: Transcribe cached audio only
        - clear: Clear cache/delete recording
        - append: Append (start new recording to append to cache)
        - retake: Discard current and start fresh recording

        Each hotkey can be configured to any key from F13-F24, or disabled.
        """
        # Unregister all existing hotkeys first
        for name in [
            "hotkey_toggle",
            "hotkey_tap_toggle",
            "hotkey_transcribe",
            "hotkey_clear",
            "hotkey_append",
            "hotkey_retake",
            "hotkey_copy_last",
        ]:
            self.hotkey_listener.unregister(name)

        # Toggle: start/stop and transcribe
        if self.config.hotkey_toggle:
            self.hotkey_listener.register(
                "hotkey_toggle",
                self.config.hotkey_toggle,
                lambda: QTimer.singleShot(0, self._hotkey_toggle_recording),
            )

        # Tap toggle: start/stop and cache (for append mode)
        if self.config.hotkey_tap_toggle:
            self.hotkey_listener.register(
                "hotkey_tap_toggle",
                self.config.hotkey_tap_toggle,
                lambda: QTimer.singleShot(0, self._hotkey_tap_toggle),
            )

        # Transcribe: transcribe cached audio only
        if self.config.hotkey_transcribe:
            self.hotkey_listener.register(
                "hotkey_transcribe",
                self.config.hotkey_transcribe,
                lambda: QTimer.singleShot(0, self._hotkey_transcribe_only),
            )

        # Clear: clear cache/delete recording
        if self.config.hotkey_clear:
            self.hotkey_listener.register(
                "hotkey_clear",
                self.config.hotkey_clear,
                lambda: QTimer.singleShot(0, self._hotkey_delete),
            )

        # Append: start new recording to add to cache
        if self.config.hotkey_append:
            self.hotkey_listener.register(
                "hotkey_append",
                self.config.hotkey_append,
                lambda: QTimer.singleShot(0, self._hotkey_append),
            )

        # Retake: discard current and start fresh recording
        if self.config.hotkey_retake:
            self.hotkey_listener.register(
                "hotkey_retake",
                self.config.hotkey_retake,
                lambda: QTimer.singleShot(0, self._hotkey_retake),
            )

        # Copy last: copy most recent transcription to clipboard
        if self.config.hotkey_copy_last:
            self.hotkey_listener.register(
                "hotkey_copy_last",
                self.config.hotkey_copy_last,
                lambda: QTimer.singleShot(0, self._copy_last_transcription),
            )

    def _hotkey_toggle_recording(self):
        """Handle F15: Simple toggle - start recording, or stop and transcribe."""
        if self.recorder.is_recording:
            self.stop_and_transcribe()  # Stop and immediately transcribe
        else:
            self.toggle_recording()  # Start recording

    def _hotkey_tap_toggle(self):
        """Handle F16: Toggle recording on/off (caches audio when stopped for append mode)."""
        if self.recorder.is_recording:
            self.handle_stop_button()  # Stop and cache (enables append mode)
        else:
            # If we have cached audio, enable append mode before starting
            if self.accumulated_segments:
                self.append_mode = True
            self.toggle_recording()  # Start recording (or append if audio is cached)

    def _hotkey_transcribe_only(self):
        """Handle F17: Transcribe cached audio only (without recording).

        If recording, stops and transcribes. If stopped with cache, transcribes cache.
        """
        if self.recorder.is_recording:
            self.stop_and_transcribe()  # Stop recording and transcribe
        elif self.accumulated_segments:
            self.transcribe_cached_audio()  # Transcribe cached audio
        # else: do nothing (no audio to transcribe)

    def _hotkey_delete(self):
        """Handle F18: Clear cache/delete recording."""
        self.delete_recording()

    def _hotkey_append(self):
        """Handle Append hotkey: Start new recording to add to cache."""
        if not self.recorder.is_recording:
            self.append_to_transcription()

    def _hotkey_retake(self):
        """Handle Retake hotkey: Discard current and start fresh recording."""
        self.retake_recording()

    def stop_if_recording(self):
        """Stop and transcribe only if currently recording."""
        if self.recorder.is_recording:
            self.stop_and_transcribe()

    def update_word_count(self):
        """Update the word count display."""
        text = self.text_output.toPlainText()
        if text:
            words = len(text.split())
            chars = len(text)
            self.word_count_label.setText(f"{words} words, {chars} characters")
        else:
            self.word_count_label.setText("")

    def save_to_file(self):
        """Save transcription to a file."""
        text = self.text_output.toPlainText()
        if not text:
            self.status_label.setText("Nothing to save")
            self.status_label.setStyleSheet("color: rgba(255, 193, 7, 0.8); font-size: 11px;")
            self.status_label.show()
            QTimer.singleShot(2000, lambda: self.status_label.hide())
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Transcription",
            "",
            "Markdown Files (*.md);;Text Files (*.txt);;All Files (*)",
        )

        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(text)
                self.status_label.setText("Saved!")
                self.status_label.setStyleSheet("color: rgba(40, 167, 69, 0.7); font-size: 11px;")
                self.status_label.show()
            except Exception as e:
                QMessageBox.critical(self, "Save Error", str(e))
            finally:
                QTimer.singleShot(2000, lambda: self.status_label.hide())

    def _open_prompt_editor(self):
        """Open the unified Prompt Editor window."""
        if self.prompt_editor_window is None:
            self.prompt_editor_window = PromptEditorWindow(self.config, CONFIG_DIR, self)
            self.prompt_editor_window.prompts_changed.connect(self._on_prompts_changed)

        self.prompt_editor_window.show()
        self.prompt_editor_window.raise_()
        self.prompt_editor_window.activateWindow()

    def _toggle_output_mode(self, mode: str):
        """Toggle an output mode on/off.

        Args:
            mode: One of "app", "clipboard", or "inject"
        """
        # Toggle the mode
        if mode == "app":
            self.config.output_to_app = not self.config.output_to_app
            enabled = self.config.output_to_app
        elif mode == "clipboard":
            self.config.output_to_clipboard = not self.config.output_to_clipboard
            enabled = self.config.output_to_clipboard
        elif mode == "inject":
            self.config.output_to_inject = not self.config.output_to_inject
            enabled = self.config.output_to_inject
        else:
            enabled = False

        save_config(self.config)
        self._update_mode_button_styles()

        # Audio feedback for mode toggle
        if self.config.audio_feedback_mode == "beeps":
            if enabled:
                get_feedback().play_toggle_on_beep()
            else:
                get_feedback().play_toggle_off_beep()
        elif self.config.audio_feedback_mode == "tts":
            announcer = get_announcer()
            if mode == "app":
                if enabled:
                    announcer.announce_app_enabled()
                else:
                    announcer.announce_app_disabled()
            elif mode == "clipboard":
                if enabled:
                    announcer.announce_clipboard_enabled()
                else:
                    announcer.announce_clipboard_disabled()
            elif mode == "inject":
                if enabled:
                    announcer.announce_inject_enabled()
                else:
                    announcer.announce_inject_disabled()

    def _set_output_mode(self, mode: str, enabled: bool):
        """Set a specific output mode to enabled or disabled.

        Args:
            mode: One of "app", "clipboard", or "inject"
            enabled: Whether to enable or disable the mode
        """
        if mode == "app":
            self.config.output_to_app = enabled
        elif mode == "clipboard":
            self.config.output_to_clipboard = enabled
        elif mode == "inject":
            self.config.output_to_inject = enabled
        save_config(self.config)
        self._update_mode_button_styles()

    def _update_mode_button_styles(self):
        """Update mode button styles based on current enabled states."""
        mode_states = {
            "app": self.config.output_to_app,
            "clipboard": self.config.output_to_clipboard,
            "inject": self.config.output_to_inject,
        }
        for mode_key, btn in self._mode_buttons.items():
            if mode_states.get(mode_key, False):
                btn.setStyleSheet(self._mode_btn_active_style)
            else:
                btn.setStyleSheet(self._mode_btn_inactive_style)

    def _set_audio_feedback_mode(self, mode: str):
        """Set the audio feedback mode.

        Args:
            mode: One of "silent", "tts", or "beeps"
        """
        old_mode = self.config.audio_feedback_mode

        # Announce TTS mode changes (before changing the mode)
        if old_mode == "tts" and mode != "tts":
            # Leaving TTS mode - announce deactivation while TTS is still active
            get_announcer().announce_tts_deactivated()
        elif old_mode != "tts" and mode == "tts":
            # Entering TTS mode - announce after setting mode
            self.config.audio_feedback_mode = mode
            save_config(self.config)
            self._update_feedback_buttons()
            get_announcer().announce_tts_activated()
            return

        self.config.audio_feedback_mode = mode
        save_config(self.config)
        self._update_feedback_buttons()

    def _update_feedback_buttons(self):
        """Update feedback button checked states based on current config."""
        current_mode = self.config.audio_feedback_mode
        for mode_key, btn in self._feedback_buttons.items():
            btn.setChecked(mode_key == current_mode)

    def _update_all_time_word_count(self):
        """Update the all-time word count display in the footer."""
        try:
            db = get_db()
            stats = db.get_all_time_stats()
            total_words = stats.get("total_words", 0)
            if total_words > 0:
                formatted = format_word_count(total_words)
                self.all_time_word_count_label.setText(f"Words transcribed: {formatted}")
            else:
                self.all_time_word_count_label.setText("")
        except Exception:
            # Silently ignore errors - the label just won't update
            pass

    def _on_personalize_toggled(self, checked: bool):
        """Handle Personalize checkbox toggle.

        When enabled, adds personalization elements (name, email, signature) to prompts.
        Note: Always enabled automatically for email format preset.
        """
        self.config.personalization_enabled = checked
        save_config(self.config)

    def _on_add_date_toggled(self, checked: bool):
        """Handle Add Date checkbox toggle.

        When enabled, includes today's date in the output.
        """
        self.config.add_date_enabled = checked
        save_config(self.config)

    def _on_tldr_toggled(self, checked: bool):
        """Handle TLDR checkbox toggle.

        When enabled, adds a TLDR/summary section to the output.
        """
        self.config.tldr_enabled = checked
        save_config(self.config)

    def _on_tldr_position_changed(self, position: str):
        """Handle TLDR position dropdown change.

        Sets where the TLDR section appears: top or bottom.
        """
        self.config.tldr_position = position.lower()
        save_config(self.config)

    def _on_vad_checkbox_changed(self, state: int):
        """Handle VAD checkbox toggle.

        When enabled, removes silence from audio before transcription.
        """
        enabled = state == Qt.CheckState.Checked.value
        self.config.vad_enabled = enabled
        save_config(self.config)

        # Audio feedback for VAD toggle
        if self.config.audio_feedback_mode == "beeps":
            if enabled:
                get_feedback().play_toggle_on_beep()
            else:
                get_feedback().play_toggle_off_beep()
        elif self.config.audio_feedback_mode == "tts":
            if enabled:
                get_announcer().announce_vad_enabled()
            else:
                get_announcer().announce_vad_disabled()

    def _set_quick_format(self, format_key: str):
        """Handle quick format button clicks."""
        # Update the config and current prompt ID
        self.config.format_preset = format_key
        self.current_prompt_id = format_key

        # Disable prompt stacks mode when selecting a preset format
        if self.config.use_prompt_stacks:
            self.config.use_prompt_stacks = False

        # If verbatim is selected, disable optional enhancements
        if format_key == "verbatim":
            self.config.prompt_remove_unintentional_dialogue = False
            self.config.prompt_enhancement_enabled = False

        save_config(self.config)

    def _on_prompts_changed(self):
        """Handle changes to prompts in the prompt library or editor."""
        # Reload the prompt library
        self.prompt_library = PromptLibrary(CONFIG_DIR)
        # Refresh the stack builder to show updated prompts and stacks
        if hasattr(self, "stack_builder"):
            self.stack_builder.refresh_custom_prompts()

    def _on_stack_changed(self):
        """Handle changes from the stack builder widget.

        The stack builder has already updated self.config with the new values.
        We just need to save and update any dependent UI elements.
        """
        save_config(self.config)
        self._update_translation_indicator()

    def get_selected_microphone_index(self):
        """Get the index of the system default microphone.

        The app always uses the OS-level default microphone, routed through
        PipeWire/PulseAudio. To change the microphone, update your system
        audio settings (System Settings → Sound).

        Priority order:
        1. "pulse" (routes through PipeWire/PulseAudio - uses system default)
        2. "default"
        3. First available device
        """
        devices = self.recorder.get_input_devices()

        # 1. Default to "pulse" which routes through PipeWire/PulseAudio
        for idx, name in devices:
            if name == "pulse":
                return idx

        # 2. Fallback to "default" if pulse not available
        for idx, name in devices:
            if name == "default":
                return idx

        # 3. Fall back to first device
        if devices:
            return devices[0][0]
        return None

    def toggle_recording(self):
        """Start or stop recording."""
        if not self.recorder.is_recording:
            # Only clear text if not in append mode and no accumulated segments
            if not self.append_mode and not self.accumulated_segments:
                self.text_output.clear()
                self.word_count_label.setText("")
                # Reset append mode if starting fresh
                self.append_mode = False

            # Clear any failed audio state when starting a new recording
            if self.has_failed_audio:
                self.has_failed_audio = False
                if hasattr(self, "last_audio_data"):
                    del self.last_audio_data
                if hasattr(self, "last_audio_duration"):
                    del self.last_audio_duration
                if hasattr(self, "last_vad_duration"):
                    del self.last_vad_duration

            # Set microphone from config
            mic_idx = self.get_selected_microphone_index()
            if mic_idx is not None:
                self.recorder.set_device(mic_idx)

            # Audio feedback (beeps or TTS based on mode)
            if self.config.audio_feedback_mode == "beeps":
                get_feedback().play_start_beep()
            elif self.config.audio_feedback_mode == "tts":
                get_announcer().announce_recording()

            self.recorder.start_recording()
            self.record_btn.setText("●")
            self.retake_btn.setEnabled(True)
            self.append_btn.setEnabled(False)  # Disable append while recording
            self.stop_btn.setEnabled(True)  # Can stop recording to cache
            self.transcribe_btn.setEnabled(True)  # Can stop and transcribe immediately
            self.delete_btn.setEnabled(True)  # Can delete current recording
            self.status_label.setText("Recording...")
            self.status_label.setStyleSheet("color: rgba(220, 53, 69, 0.7); font-size: 11px;")
            self.timer.start(100)
            # Start visual effects (pulsating record button, grayscale other controls)
            self._start_recording_visual_effects()
            # Update tray to recording state
            self._set_tray_state("recording")

    def retake_recording(self):
        """Discard current recording and immediately start a fresh one.

        This is a quick workflow for restarting without transcribing -
        useful when you want to redo a recording from scratch.
        """
        # Only available if we have something to discard
        if not self.recorder.is_recording and not self.has_cached_audio:
            return

        # Audio feedback for retake
        if self.config.audio_feedback_mode == "beeps":
            if self.recorder.is_recording:
                get_feedback().play_stop_beep()
        elif self.config.audio_feedback_mode == "tts":
            get_announcer().announce_discarded()

        # Stop recording if active
        self.timer.stop()
        if self.recorder.is_recording:
            self.recorder.stop_recording()
            self._stop_recording_visual_effects()

        # Clear everything (no confirmation for retake)
        self.recorder.clear()
        self.accumulated_segments = []
        self.accumulated_duration = 0.0
        self._update_segment_indicator()
        self.append_mode = False
        self.has_cached_audio = False
        self.has_failed_audio = False

        # Clear any failed audio data
        if hasattr(self, "last_audio_data"):
            del self.last_audio_data
        if hasattr(self, "last_audio_duration"):
            del self.last_audio_duration
        if hasattr(self, "last_vad_duration"):
            del self.last_vad_duration

        # Reset UI briefly
        self.reset_ui()

        # Immediately start fresh recording
        self.toggle_recording()

    def handle_stop_button(self):
        """Stop recording and cache audio without transcribing."""
        if not self.recorder.is_recording:
            return

        # Audio feedback (beeps or TTS based on mode)
        if self.config.audio_feedback_mode == "beeps":
            get_feedback().play_stop_beep()
        elif self.config.audio_feedback_mode == "tts":
            # Announce "Cached" for append mode, "Stopped" otherwise
            if self.append_mode or self.accumulated_segments:
                get_announcer().announce_cached()
            else:
                get_announcer().announce_stopped()

        self.timer.stop()
        audio_data = self.recorder.stop_recording()

        # Add to accumulated segments
        self.accumulated_segments.append(audio_data)
        audio_info = get_audio_info(audio_data)
        self.accumulated_duration += audio_info["duration_seconds"]
        self._update_segment_indicator()

        # Mark that we have cached audio
        self.has_cached_audio = True

        # Stop visual effects (pulsating, grayscale)
        self._stop_recording_visual_effects()

        # Update UI to "stopped with cached audio" state
        self.record_btn.setText("●")
        self.record_btn.setStyleSheet(self._record_btn_idle_style)
        self.record_btn.setEnabled(True)
        self.retake_btn.setEnabled(True)  # Can retake (discard and start fresh)
        self.stop_btn.setEnabled(False)  # Can't stop when not recording
        self.append_btn.setEnabled(True)  # Can append more clips
        self.transcribe_btn.setEnabled(True)  # Can transcribe cached audio
        self.transcribe_btn.setStyleSheet(self._transcribe_btn_idle_style)  # Green when cached
        self.delete_btn.setEnabled(True)  # Can delete cached audio
        self.status_label.setText(
            f"Stopped ({len(self.accumulated_segments)} clip{'s' if len(self.accumulated_segments) > 1 else ''})"
        )
        self.status_label.setStyleSheet("color: rgba(255, 193, 7, 0.8); font-size: 11px;")

        # Update tray to stopped state
        self._set_tray_state("stopped")

    def append_to_transcription(self):
        """Start a new recording that will be appended to cached audio."""
        if self.recorder.is_recording:
            return  # Already recording

        # Audio feedback for entering append mode (before recording starts)
        if self.config.audio_feedback_mode == "beeps":
            get_feedback().play_append_beep()
        elif self.config.audio_feedback_mode == "tts":
            get_announcer().announce_appending()

        # Enable append mode (keeps cached audio)
        self.append_mode = True

        # Start recording (will not clear cache due to append_mode flag)
        self.toggle_recording()

    def transcribe_cached_audio(self):
        """Transcribe all accumulated audio segments."""
        if not self.accumulated_segments:
            return  # Nothing to transcribe

        # Combine all segments
        self.status_label.setText("Combining clips...")
        self.status_label.setStyleSheet("color: rgba(0, 123, 255, 0.7); font-size: 11px;")
        self.status_label.show()
        audio_data = combine_wav_segments(self.accumulated_segments)

        # Get original audio info
        audio_info = get_audio_info(audio_data)
        self.last_audio_duration = audio_info["duration_seconds"]
        self.last_vad_duration = None

        # Store audio data for later archiving
        self.last_audio_data = audio_data

        # Clear cache
        self.accumulated_segments = []
        self.accumulated_duration = 0.0
        self._update_segment_indicator()
        self.has_cached_audio = False

        # Disable all controls during transcription
        self.record_btn.setText("●")
        self.record_btn.setEnabled(False)
        self.retake_btn.setEnabled(False)
        self.append_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.transcribe_btn.setEnabled(False)
        self.delete_btn.setEnabled(False)
        self.status_label.setText("Transcribing...")
        self.status_label.setStyleSheet("color: rgba(0, 123, 255, 0.7); font-size: 11px;")

        # Update tray to transcribing state
        self._set_tray_state("transcribing")

        # Get model from active preset (always using OpenRouter)
        _, model = self._get_current_model()
        api_key = self.config.openrouter_api_key

        if not api_key:
            QMessageBox.warning(
                self,
                "Missing API Key",
                "Please set your OpenRouter API key in Settings.",
            )
            self.reset_ui()
            return

        # Build cleanup prompt (pass audio duration for short audio optimization)
        cleanup_prompt = build_cleanup_prompt(
            self.config, audio_duration_seconds=self.last_audio_duration
        )

        # Use queue for transcription (enables rapid dictation)
        if self.config.queue_enabled:
            self.transcription_queue.enqueue(
                audio_data,
                api_key=api_key,
                model=model,
                prompt=cleanup_prompt,
                vad_enabled=self.config.vad_enabled,
            )
        else:
            # Legacy single-worker mode
            self._cleanup_worker("worker")
            self.worker = TranscriptionWorker(
                audio_data,
                api_key,
                model,
                cleanup_prompt,
                vad_enabled=self.config.vad_enabled,
            )
            self.worker.finished.connect(self.on_transcription_complete)
            self.worker.error.connect(self.on_transcription_error)
            self.worker.status.connect(self.on_worker_status)
            self.worker.vad_complete.connect(self.on_vad_complete)
            self.worker.start()

        # TTS announcement for transcribing
        if self.config.audio_feedback_mode == "tts":
            get_announcer().announce_transcribing()

    def retry_transcription(self):
        """Retry transcription of previously failed audio.

        Uses the stored last_audio_data from the failed attempt.
        """
        if not hasattr(self, "last_audio_data") or not self.last_audio_data:
            return  # No audio to retry

        # Clear the failed audio flag
        self.has_failed_audio = False

        # Disable all controls during transcription
        self.record_btn.setText("●")
        self.record_btn.setEnabled(False)
        self.retake_btn.setEnabled(False)
        self.append_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.transcribe_btn.setEnabled(False)
        self.delete_btn.setEnabled(False)
        self.status_label.setText("Retrying transcription...")
        self.status_label.setStyleSheet("color: rgba(0, 123, 255, 0.7); font-size: 11px;")
        self.status_label.show()

        # Update tray to transcribing state
        self._set_tray_state("transcribing")

        # Get model from active preset (always using OpenRouter)
        _, model = self._get_current_model()
        api_key = self.config.openrouter_api_key

        if not api_key:
            QMessageBox.warning(
                self,
                "Missing API Key",
                "Please set your OpenRouter API key in Settings.",
            )
            # Restore failed audio state so user can try again after setting key
            self.has_failed_audio = True
            self._show_retry_ui()
            return

        # Build cleanup prompt (use stored duration for short audio optimization)
        audio_duration = getattr(self, "last_audio_duration", None)
        cleanup_prompt = build_cleanup_prompt(self.config, audio_duration_seconds=audio_duration)

        # Use queue for transcription (enables rapid dictation)
        if self.config.queue_enabled:
            self.transcription_queue.enqueue(
                self.last_audio_data,
                api_key=api_key,
                model=model,
                prompt=cleanup_prompt,
                vad_enabled=self.config.vad_enabled,
            )
        else:
            # Legacy single-worker mode
            self._cleanup_worker("worker")
            self.worker = TranscriptionWorker(
                self.last_audio_data,
                api_key,
                model,
                cleanup_prompt,
                vad_enabled=self.config.vad_enabled,
            )
            self.worker.finished.connect(self.on_transcription_complete)
            self.worker.error.connect(self.on_transcription_error)
            self.worker.status.connect(self.on_worker_status)
            self.worker.vad_complete.connect(self.on_vad_complete)
            self.worker.start()

        # TTS announcement for transcribing
        if self.config.audio_feedback_mode == "tts":
            get_announcer().announce_transcribing()

    def _show_retry_ui(self):
        """Show UI state for retry available."""
        # Stop visual effects if somehow still running
        self._stop_recording_visual_effects()
        self.record_btn.setText("●")
        self.record_btn.setStyleSheet(self._record_btn_idle_style)
        self.record_btn.setEnabled(True)
        self.retake_btn.setEnabled(False)
        self.append_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.transcribe_btn.setEnabled(True)  # Enable for retry
        self.transcribe_btn.setStyleSheet(self._transcribe_btn_idle_style)
        self.delete_btn.setEnabled(True)  # Enable to discard failed audio
        self.status_label.setText("Transcription failed — click ⬆ to retry")
        self.status_label.setStyleSheet("color: rgba(220, 53, 69, 0.9); font-size: 11px;")
        self.status_label.show()

    def _update_segment_indicator(self):
        """Update the segment count display."""
        count = len(self.accumulated_segments)
        if count > 0:
            total_mins = int(self.accumulated_duration // 60)
            total_secs = int(self.accumulated_duration % 60)
            self.segment_label.setText(f"({count} clips, {total_mins}:{total_secs:02d})")
        else:
            self.segment_label.setText("")

    def stop_and_transcribe(self):
        """Stop recording (if recording) and send for transcription immediately.

        This is used by hotkeys for quick transcription without caching.
        If you want to cache audio first, use handle_stop_button() instead.
        """
        # If we have failed audio waiting for retry, retry it
        if self.has_failed_audio:
            self.retry_transcription()
            return

        # If currently recording, stop it first
        if self.recorder.is_recording:
            # Audio feedback for stop (beeps only - TTS "transcribing" comes later)
            if self.config.audio_feedback_mode == "beeps":
                get_feedback().play_stop_beep()

            self.timer.stop()
            # Stop visual effects (pulsating, grayscale)
            self._stop_recording_visual_effects()
            audio_data = self.recorder.stop_recording()

            # If we have accumulated segments, add current recording and combine all
            if self.accumulated_segments:
                self.accumulated_segments.append(audio_data)
                self.status_label.setText("Combining clips...")
                self.status_label.setStyleSheet("color: rgba(0, 123, 255, 0.7); font-size: 11px;")
                self.status_label.show()
                audio_data = combine_wav_segments(self.accumulated_segments)
                # Clear accumulated segments after combining
                self.accumulated_segments = []
                self.accumulated_duration = 0.0
                self._update_segment_indicator()
        elif self.has_cached_audio:
            # If we have cached audio, just transcribe it
            self.transcribe_cached_audio()
            return
        else:
            # Nothing to transcribe
            return

        # Get original audio info
        audio_info = get_audio_info(audio_data)
        self.last_audio_duration = audio_info["duration_seconds"]
        self.last_vad_duration = None

        # Store audio data for later archiving (VAD now happens in worker thread)
        self.last_audio_data = audio_data

        # Clear state flags
        self.has_cached_audio = False

        self.record_btn.setText("●")
        self.record_btn.setStyleSheet(self._record_btn_idle_style)  # Reset to idle color
        self.record_btn.setEnabled(False)
        self.retake_btn.setEnabled(False)
        self.append_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.transcribe_btn.setEnabled(False)
        self.delete_btn.setEnabled(False)
        self.status_label.setText("Transcribing...")
        self.status_label.setStyleSheet("color: rgba(0, 123, 255, 0.7); font-size: 11px;")

        # Update tray to transcribing state
        self._set_tray_state("transcribing")

        # Get model from active preset (always using OpenRouter)
        _, model = self._get_current_model()
        api_key = self.config.openrouter_api_key

        if not api_key:
            QMessageBox.warning(
                self,
                "Missing API Key",
                "Please set your OpenRouter API key in Settings.",
            )
            self.reset_ui()
            return

        # Build cleanup prompt (pass audio duration for short audio optimization)
        cleanup_prompt = build_cleanup_prompt(
            self.config, audio_duration_seconds=self.last_audio_duration
        )

        # Use queue for transcription (enables rapid dictation)
        if self.config.queue_enabled:
            self.transcription_queue.enqueue(
                audio_data,
                api_key=api_key,
                model=model,
                prompt=cleanup_prompt,
                vad_enabled=self.config.vad_enabled,
            )
        else:
            # Legacy single-worker mode
            self._cleanup_worker("worker")
            self.worker = TranscriptionWorker(
                audio_data,
                api_key,
                model,
                cleanup_prompt,
                vad_enabled=self.config.vad_enabled,
            )
            self.worker.finished.connect(self.on_transcription_complete)
            self.worker.error.connect(self.on_transcription_error)
            self.worker.status.connect(self.on_worker_status)
            self.worker.vad_complete.connect(self.on_vad_complete)
            self.worker.start()

        # TTS announcement for transcribing
        if self.config.audio_feedback_mode == "tts":
            get_announcer().announce_transcribing()

    def on_worker_status(self, status: str):
        """Handle worker status updates."""
        self.status_label.setText(status)
        self.status_label.setStyleSheet("color: rgba(0, 123, 255, 0.7); font-size: 11px;")
        self.status_label.show()

    def on_vad_complete(self, orig_dur: float, vad_dur: float):
        """Handle VAD processing complete - store duration for database."""
        self.last_vad_duration = vad_dur

    def on_transcription_complete(self, result: TranscriptionResult):
        """Handle completed transcription.

        PERFORMANCE: User-facing actions (clipboard, inject, app display) happen first.
        Housekeeping tasks (database save, audio archive, cost tracking) are deferred
        to avoid blocking the user from receiving their transcribed text.
        """
        # Get output mode states
        output_to_app = self.config.output_to_app
        output_to_clipboard = self.config.output_to_clipboard
        output_to_inject = self.config.output_to_inject

        # === PRIORITY 1: User-facing outputs (do these FIRST for lowest latency) ===

        # Handle clipboard output IMMEDIATELY - this is what the user is waiting for
        did_clipboard = False
        if output_to_clipboard:
            copy_to_clipboard(result.text)
            did_clipboard = True

        # Handle text injection (typing at cursor)
        injection_failed = False
        did_inject = False
        if output_to_inject:
            if self._inject_text_at_cursor(result.text):
                did_inject = True
            else:
                injection_failed = True

        # Handle app output
        if output_to_app:
            if self.append_mode:
                existing_text = self.text_output.toPlainText()
                if existing_text:
                    if self.config.append_position == "cursor":
                        # Insert at cursor position
                        cursor = self.text_output.source_view.textCursor()
                        cursor.insertText("\n\n" + result.text)
                        self.text_output.source_view.setTextCursor(cursor)
                    else:
                        # Append at end (default)
                        combined_text = existing_text + "\n\n" + result.text
                        self.text_output.setMarkdown(combined_text)
                        # Move cursor to end of document after appending
                        cursor = self.text_output.source_view.textCursor()
                        cursor.movePosition(cursor.MoveOperation.End)
                        self.text_output.source_view.setTextCursor(cursor)
                else:
                    self.text_output.setMarkdown(result.text)
                # Reset append mode
                self.append_mode = False
            else:
                # Normal mode - append to existing text if present
                existing_text = self.text_output.toPlainText()
                if existing_text.strip():
                    # Append new transcription to existing text
                    combined_text = existing_text + "\n\n" + result.text
                    self.text_output.setMarkdown(combined_text)
                    # Move cursor to end
                    cursor = self.text_output.source_view.textCursor()
                    cursor.movePosition(cursor.MoveOperation.End)
                    self.text_output.source_view.setTextCursor(cursor)
                else:
                    self.text_output.setMarkdown(result.text)
        else:
            # App output disabled - clear the text area
            self.text_output.setMarkdown("")
            self.append_mode = False

        # Audio feedback for completion (beeps or TTS based on mode)
        if self.config.audio_feedback_mode == "beeps":
            # Beep for invisible actions (clipboard/inject)
            if did_clipboard or did_inject:
                get_feedback().play_clipboard_beep()
        elif self.config.audio_feedback_mode == "tts":
            # TTS: announce what happened based on output modes
            if injection_failed:
                get_announcer().announce_injection_failed()
            elif did_clipboard:
                get_announcer().announce_text_on_clipboard()
            elif did_inject:
                get_announcer().announce_text_injected()
            elif output_to_app:
                get_announcer().announce_text_in_app()
            else:
                get_announcer().announce_complete()

        self.reset_ui()

        # Enable append button if app mode is enabled (text is visible)
        self.append_btn.setEnabled(output_to_app)

        # Determine tray state and status message based on what was done
        # Only mention invisible actions (clipboard/inject) - app is visually obvious
        tray_state = self._get_completion_tray_state(did_clipboard, did_inject)
        self._set_tray_state(tray_state)

        # In silent mode for clipboard/inject, keep status visible indefinitely
        # (it will clear when user starts next recording)
        # Otherwise, auto-hide after 3 seconds
        invisible_action = did_clipboard or did_inject
        is_silent = self.config.audio_feedback_mode == "silent"
        if not is_silent or not invisible_action:
            complete_states = (
                "complete",
                "clipboard_complete",
                "inject_complete",
                "clipboard_inject_complete",
            )
            QTimer.singleShot(
                3000,
                lambda: self._set_tray_state("idle")
                if self._tray_state in complete_states
                else None,
            )

        # === PRIORITY 2: Housekeeping tasks (deferred to not block user) ===
        # These run on the next event loop iteration via QTimer.singleShot(0)
        self._schedule_post_transcription_tasks(result)

    def _schedule_post_transcription_tasks(self, result: TranscriptionResult):
        """Schedule housekeeping tasks to run after user-facing output is complete.

        This defers database save, audio archiving, and cost tracking to the next
        event loop iteration, ensuring the user gets their transcribed text
        on the clipboard/in the app with minimal latency.
        """
        # Capture all state needed for deferred tasks
        model = get_active_model(self.config)
        audio_duration = getattr(self, "last_audio_duration", None)
        vad_duration = getattr(self, "last_vad_duration", None)
        prompt_length = len(self.worker.prompt) if self.worker else 0
        inference_time_ms = self.worker.inference_time_ms if self.worker else 0
        store_audio = self.config.store_audio
        last_audio_data = getattr(self, "last_audio_data", None)

        # Determine cost
        final_cost = 0.0
        if result.actual_cost is not None:
            final_cost = result.actual_cost
        elif result.input_tokens > 0 or result.output_tokens > 0:
            tracker = get_tracker()
            final_cost = tracker.record_usage(
                "openrouter", model, result.input_tokens, result.output_tokens
            )

        def do_housekeeping():
            # Archive audio if enabled
            audio_file_path = None
            if store_audio and last_audio_data:
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                audio_filename = f"{timestamp}.opus"
                audio_path = AUDIO_ARCHIVE_DIR / audio_filename
                if archive_audio(last_audio_data, str(audio_path)):
                    audio_file_path = str(audio_path)

            # Save to database
            db = get_db()
            db.save_transcription(
                provider="openrouter",
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
            )

            # Check if embedding batch processing is needed
            if self.config.embedding_enabled and self.config.openrouter_api_key:
                self._check_embedding_batch()

            # Update all-time word count in footer
            self._update_all_time_word_count()

            # Refresh recent panel
            self.recent_panel.refresh()

        # Clear stored audio data and retry state now (synchronously)
        self.has_failed_audio = False
        if hasattr(self, "last_audio_data"):
            del self.last_audio_data
        if hasattr(self, "last_audio_duration"):
            del self.last_audio_duration
        if hasattr(self, "last_vad_duration"):
            del self.last_vad_duration

        # Run housekeeping on next event loop iteration
        QTimer.singleShot(0, do_housekeeping)

    def on_transcription_error(self, error: str):
        """Handle transcription error with automatic failover support."""
        # Check if we should attempt failover
        should_failover = (
            self.config.failover_enabled
            and not self._failover_in_progress
            and hasattr(self, "last_audio_data")
            and self.last_audio_data
            and is_preset_configured(self.config, "fallback")
        )

        if should_failover:
            # Attempt failover to the fallback model
            fallback_model = get_fallback_model(self.config)
            if fallback_model:
                fallback_api_key = self.config.openrouter_api_key

                if fallback_api_key:
                    print(
                        f"Primary transcription failed. Attempting failover to {fallback_model}..."
                    )
                    self.status_label.setText(
                        f"Failover: trying {self.config.fallback_name or 'fallback'}..."
                    )
                    self.status_label.setStyleSheet(
                        "color: rgba(255, 165, 0, 0.9); font-size: 11px;"
                    )  # Orange for failover
                    self.status_label.show()

                    # Set flag to prevent infinite failover loop
                    self._failover_in_progress = True

                    # Clean up the failed worker
                    self._cleanup_worker("worker")

                    # Start failover transcription
                    audio_duration = getattr(self, "last_audio_duration", None)
                    cleanup_prompt = build_cleanup_prompt(
                        self.config, audio_duration_seconds=audio_duration
                    )
                    self.worker = TranscriptionWorker(
                        self.last_audio_data,
                        fallback_api_key,
                        fallback_model,
                        cleanup_prompt,
                        vad_enabled=self.config.vad_enabled,
                    )
                    self.worker.finished.connect(self._on_failover_complete)
                    self.worker.error.connect(self._on_failover_error)
                    self.worker.status.connect(self.on_worker_status)
                    self.worker.vad_complete.connect(self.on_vad_complete)
                    self.worker.start()
                    return  # Don't show error yet, wait for failover result

        # No failover possible or failover disabled - show error
        self._failover_in_progress = False  # Reset flag

        # TTS announcement for error
        if self.config.audio_feedback_mode == "tts":
            get_announcer().announce_error()

        # Check if we have audio data to retry with
        if hasattr(self, "last_audio_data") and self.last_audio_data:
            self.has_failed_audio = True
            QMessageBox.warning(
                self,
                "Transcription Failed",
                f"{error}\n\nYour audio has been preserved. Click the transcribe button (⬆) to retry, "
                "or delete to discard.",
            )
            self._show_retry_ui()
            self._set_tray_state("idle")
        else:
            # No audio to retry with - show error and reset normally
            QMessageBox.critical(self, "Transcription Error", error)
            self.reset_ui()
            self._set_tray_state("idle")

    def _on_failover_complete(self, result: TranscriptionResult):
        """Handle successful failover transcription."""
        self._failover_in_progress = False
        print(f"Failover transcription successful!")
        # Delegate to normal completion handler
        self.on_transcription_complete(result)

    def _on_failover_error(self, error: str):
        """Handle failover transcription error."""
        self._failover_in_progress = False
        print(f"Failover also failed: {error}")

        # Both primary and fallback failed - show error
        # TTS announcement for error
        if self.config.audio_feedback_mode == "tts":
            get_announcer().announce_error()

        if hasattr(self, "last_audio_data") and self.last_audio_data:
            self.has_failed_audio = True
            QMessageBox.warning(
                self,
                "Transcription Failed",
                f"Both primary and fallback models failed.\n\n"
                f"Error: {error}\n\n"
                f"Your audio has been preserved. Click the transcribe button (⬆) to retry, "
                "or delete to discard.",
            )
            self._show_retry_ui()
            self._set_tray_state("idle")
        else:
            QMessageBox.critical(
                self,
                "Transcription Error",
                f"Both primary and fallback models failed.\n\nError: {error}",
            )
            self.reset_ui()
            self._set_tray_state("idle")

    def _update_mic_display(self):
        """Update the microphone display button text.

        The app uses the system default microphone. This display is read-only
        and shows the current OS-level default audio input device.
        """
        display_name, full_name = self._get_active_microphone_name()
        # Limit to 3 words for compact display
        words = display_name.split()
        if len(words) > 3:
            display_name = " ".join(words[:3])
        self.mic_selector_btn.setText(display_name)
        self.mic_selector_btn.setToolTip(
            f"Microphone: {full_name}\n"
            "Using system default. Change in System Settings → Sound."
        )

    def _setup_microphone_menu(self):
        """Set up the microphone info menu.

        The app always uses the system default microphone. This menu provides
        information and a shortcut to system audio settings.
        """
        self.microphone_menu = QMenu(self)

        # Info header (disabled, just for display)
        info_action = QAction("Using System Default Microphone", self)
        info_action.setEnabled(False)
        self.microphone_menu.addAction(info_action)

        self.microphone_menu.addSeparator()

        # Refresh action
        refresh_action = QAction("Refresh", self)
        refresh_action.triggered.connect(self._update_mic_display)
        self.microphone_menu.addAction(refresh_action)

        # Open system sound settings
        settings_action = QAction("Open System Sound Settings...", self)
        settings_action.triggered.connect(self._open_system_sound_settings)
        self.microphone_menu.addAction(settings_action)

        self.mic_selector_btn.setMenu(self.microphone_menu)

    def _open_system_sound_settings(self):
        """Open the system sound settings (KDE Plasma)."""
        import subprocess
        try:
            # Try KDE systemsettings first
            subprocess.Popen(["systemsettings", "kcm_pulseaudio"])
        except FileNotFoundError:
            try:
                # Fallback to pavucontrol
                subprocess.Popen(["pavucontrol"])
            except FileNotFoundError:
                # Last resort: generic settings
                subprocess.Popen(["xdg-open", "settings://sound"])

    def _get_active_microphone_name(self) -> tuple[str, str]:
        """Get the name of the system default microphone.

        Queries PipeWire/PulseAudio to get the actual default audio input device.

        Returns:
            Tuple of (display_name, full_name).
        """
        import subprocess

        actual_device_name = None

        # Query PipeWire/PulseAudio for the actual default source
        try:
            result = subprocess.run(
                ["pactl", "get-default-source"], capture_output=True, text=True, timeout=2
            )
            if result.returncode == 0:
                source_name = result.stdout.strip()
                if source_name:
                    # Get the description for this source
                    desc_result = subprocess.run(
                        ["pactl", "list", "sources"], capture_output=True, text=True, timeout=2
                    )
                    if desc_result.returncode == 0:
                        lines = desc_result.stdout.split("\n")
                        found_source = False
                        for line in lines:
                            if f"Name: {source_name}" in line:
                                found_source = True
                            elif found_source and "Description:" in line:
                                actual_device_name = line.split("Description:", 1)[1].strip()
                                break
                    if not actual_device_name:
                        # Fallback: clean up the source name
                        if "usb-" in source_name:
                            parts = source_name.split("usb-")[1].split("-00")[0]
                            actual_device_name = parts.replace("_", " ")
                        else:
                            actual_device_name = source_name
        except Exception:
            pass

        # Fallback to PyAudio device list
        if not actual_device_name:
            devices = self.recorder.get_input_devices()
            if devices:
                actual_device_name = devices[0][1]

        if not actual_device_name:
            return ("No microphone found", "No microphone found")

        return (actual_device_name, actual_device_name)

    def _update_model_display(self):
        """Update the model display button text and menu."""
        _, model = self._get_current_model()
        preset = self.config.active_model_preset

        # Button shows just "Primary" or "Fallback"
        display_text = preset.title()

        # Get custom name for tooltip (if configured)
        if preset == "primary" and self.config.primary_name:
            custom_name = self.config.primary_name
        elif preset == "fallback" and self.config.fallback_name:
            custom_name = self.config.fallback_name
        else:
            custom_name = get_model_display_name(model)

        # Set button text (no indicator - click shows menu)
        self.model_selector_btn.setText(display_text)
        self.model_selector_btn.setToolTip(
            f"{custom_name}\n"
            f"Model: {model}\n"
            f"Failover: {'Enabled' if self.config.failover_enabled else 'Disabled'}\n"
            f"Click to change"
        )

        # Update menu checkmarks
        self._update_model_preset_menu_checks()

    def _update_translation_indicator(self):
        """Update the translation indicator visibility and text."""
        if self.config.translation_mode_enabled:
            target_lang = get_language_display_name(self.config.translation_target_language)
            target_flag = get_language_flag(self.config.translation_target_language)
            self.translation_indicator.setText(f"{target_flag} → {target_lang}")
            self.translation_indicator.setToolTip(
                f"Translation mode is active\n"
                f"Output will be translated to {target_lang}\n"
                f"Click the Translation radio button to disable"
            )
            self.translation_indicator.show()
        else:
            self.translation_indicator.hide()

    def _setup_model_preset_menu(self):
        """Set up the model preset dropdown menu."""
        self.model_preset_menu = QMenu(self)
        self.model_preset_actions = {}

        # Action group for mutual exclusion
        self.model_preset_action_group = QActionGroup(self)
        self.model_preset_action_group.setExclusive(True)

        # Primary action (simple label, tooltip shows model details)
        primary_action = QAction("● Primary", self)
        primary_action.setCheckable(True)
        primary_action.setData("primary")
        primary_action.triggered.connect(lambda: self._on_model_preset_changed("primary"))
        self.model_preset_action_group.addAction(primary_action)
        self.model_preset_menu.addAction(primary_action)
        self.model_preset_actions["primary"] = primary_action

        # Fallback action (simple label, tooltip shows model details)
        fallback_action = QAction("○ Fallback", self)
        fallback_action.setCheckable(True)
        fallback_action.setData("fallback")
        fallback_action.triggered.connect(lambda: self._on_model_preset_changed("fallback"))
        self.model_preset_action_group.addAction(fallback_action)
        self.model_preset_menu.addAction(fallback_action)
        self.model_preset_actions["fallback"] = fallback_action

        # Settings shortcut
        self.model_preset_menu.addSeparator()
        settings_action = QAction("Configure Models...", self)
        settings_action.triggered.connect(self.show_settings)
        self.model_preset_menu.addAction(settings_action)

        self.model_selector_btn.setMenu(self.model_preset_menu)

        # Set initial check state
        self._update_model_preset_menu_checks()

    def _update_model_preset_menu_checks(self):
        """Update the checkmarks in the model preset menu."""
        current_preset = self.config.active_model_preset
        for preset_key, action in self.model_preset_actions.items():
            action.setChecked(preset_key == current_preset)

    def _on_model_preset_changed(self, preset: str):
        """Handle model preset selection change."""
        if preset == self.config.active_model_preset:
            return  # No change

        self.config.active_model_preset = preset
        save_config(self.config)

        # Update display
        self._update_model_display()

        # Play TTS announcement if enabled
        announcer = get_announcer()
        _, model = self._get_current_model()
        model_name = get_model_display_name(model)
        announcer.announce_model_changed(model_name)

    def _refresh_model_preset_menu(self):
        """Refresh the model preset menu (e.g., after settings change)."""
        # Remove old menu
        if hasattr(self, "model_preset_menu"):
            self.model_preset_menu.deleteLater()
        # Recreate menu
        self._setup_model_preset_menu()
        self._update_model_display()

    def _play_stats(self):
        """Play usage statistics via TTS."""
        db = get_db()
        stats = db.get_all_time_stats()
        total_transcripts = stats["count"]
        total_words = stats["total_words"]

        # Use TTS announcer to speak the stats
        announcer = get_announcer()
        if not announcer.speak_stats(total_transcripts, total_words):
            # Edge TTS not available - show message instead
            self.status_label.setText(
                f"Stats: {total_transcripts:,} transcriptions, {total_words:,} words"
            )
            self.status_label.show()

    def _get_current_model(self) -> tuple[str, str]:
        """Get the currently selected provider and model based on active preset.

        Returns:
            Tuple of (provider, model). Provider is always "openrouter".
        """
        return ("openrouter", get_active_model(self.config))

    def reset_ui(self):
        """Reset UI to initial state.

        Note: Does not change tray state - caller is responsible for setting
        appropriate tray state (idle, complete, etc.) after calling this.
        """
        # Stop visual effects (pulsating, grayscale)
        self._stop_recording_visual_effects()
        self.record_btn.setText("●")
        self.record_btn.setStyleSheet(self._record_btn_idle_style)
        self.record_btn.setEnabled(True)
        self.retake_btn.setEnabled(False)
        self.append_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.transcribe_btn.setEnabled(False)
        self.transcribe_btn.setStyleSheet(self._transcribe_btn_idle_style)  # Reset to green
        self.delete_btn.setEnabled(False)
        # Hide duration display and reset minute counter
        self.duration_label.setText("")
        self.duration_container.hide()
        self._last_shown_minute = 0
        # Hide status label (no longer shows "Ready")
        self.status_label.setText("")
        self.status_label.hide()

    def delete_recording(self):
        """Delete current recording and any accumulated segments."""
        # Show confirmation dialog
        reply = QMessageBox.question(
            self,
            "Delete Recording",
            "Are you sure you want to delete this recording?\n\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # Audio feedback for discard (beeps or TTS based on mode)
        if self.config.audio_feedback_mode == "beeps":
            if self.recorder.is_recording or self.recorder.is_paused:
                get_feedback().play_stop_beep()
        elif self.config.audio_feedback_mode == "tts":
            get_announcer().announce_discarded()

        self.timer.stop()
        if self.recorder.is_recording or self.recorder.is_paused:
            self.recorder.stop_recording()
            # Stop visual effects (pulsating, grayscale)
            self._stop_recording_visual_effects()
        self.recorder.clear()

        # Clear accumulated segments
        self.accumulated_segments = []
        self.accumulated_duration = 0.0
        self._update_segment_indicator()

        # Reset state flags
        self.append_mode = False
        self.has_cached_audio = False
        self.has_failed_audio = False

        # Clear any failed audio data
        if hasattr(self, "last_audio_data"):
            del self.last_audio_data
        if hasattr(self, "last_audio_duration"):
            del self.last_audio_duration
        if hasattr(self, "last_vad_duration"):
            del self.last_vad_duration

        self.reset_ui()
        self._set_tray_state("idle")

    def update_duration(self):
        """Update the duration display based on configured mode."""
        mode = self.config.duration_display_mode

        # None mode - always hidden
        if mode == "none":
            self.duration_container.hide()
            return

        duration = self.recorder.get_duration()

        if mode == "mm_ss":
            # Minutes/Seconds mode - show immediately from 0:00
            if not self.duration_container.isVisible():
                self.duration_container.show()

            hours = int(duration // 3600)
            mins = int((duration % 3600) // 60)
            secs = int(duration % 60)

            if hours > 0:
                new_text = f"{hours}:{mins:02d}:{secs:02d}"
            else:
                new_text = f"{mins}:{secs:02d}"

            # Direct update (no fade for MM:SS mode - updates every tick)
            self.duration_label.setText(new_text)

        elif mode == "minutes_only":
            # Minutes Only mode - show from 1 minute with fade transitions
            mins = int(duration // 60)

            if mins < 1:
                self.duration_container.hide()
                return

            if not self.duration_container.isVisible():
                self.duration_container.show()

            # Fade animation on minute change
            if mins != self._last_shown_minute:
                self._last_shown_minute = mins
                self._animate_duration_change(f"{mins}M")

    def _animate_duration_change(self, new_text: str):
        """Animate duration label with fade out/in effect."""
        # Set up opacity effect if not already present
        if not self.duration_label.graphicsEffect():
            effect = QGraphicsOpacityEffect(self.duration_label)
            self.duration_label.setGraphicsEffect(effect)

        effect = self.duration_label.graphicsEffect()

        # Fade out animation
        self._fade_out = QPropertyAnimation(effect, b"opacity")
        self._fade_out.setDuration(150)
        self._fade_out.setStartValue(1.0)
        self._fade_out.setEndValue(0.0)
        self._fade_out.setEasingCurve(QEasingCurve.Type.OutQuad)

        # When fade out completes, update text and fade in
        def on_fade_out_finished():
            self.duration_label.setText(new_text)
            self._fade_in = QPropertyAnimation(effect, b"opacity")
            self._fade_in.setDuration(200)
            self._fade_in.setStartValue(0.0)
            self._fade_in.setEndValue(1.0)
            self._fade_in.setEasingCurve(QEasingCurve.Type.InQuad)
            self._fade_in.start()

        self._fade_out.finished.connect(on_fade_out_finished)
        self._fade_out.start()

    def clear_transcription(self):
        """Clear the transcription text."""
        self.text_output.clear()
        self.word_count_label.setText("")
        # Disable append button when clearing
        self.append_btn.setEnabled(False)
        self.append_mode = False

    def _paste_wayland(self):
        """Simulate Ctrl+V paste using python-evdev uinput (Wayland-compatible).

        This uses python-evdev to create a virtual keyboard and inject
        key events directly at the Linux kernel input level. This is more
        reliable than ydotool as it doesn't require a daemon.

        Requires the user to be in the 'input' group for /dev/uinput access.
        Falls back to ydotool if python-evdev is unavailable.
        """
        from .text_injection import paste_clipboard_with_fallback

        paste_clipboard_with_fallback(delay_before=0.1)

    def _inject_text_at_cursor(self, text: str) -> bool:
        """Inject text at cursor by copying to clipboard and simulating Ctrl+V.

        This method preserves formatting (paragraph breaks, etc.) by using
        clipboard paste rather than character-by-character typing.

        Note: This temporarily modifies the clipboard contents.

        Requires ydotool installed and ydotoold daemon running.

        Returns:
            True if injection succeeded, False otherwise.
        """
        from .text_injection import paste_clipboard

        # Copy text to clipboard first
        copy_to_clipboard(text)

        # Simulate Ctrl+V to paste
        return paste_clipboard(delay_before=0.1)

    def copy_to_clipboard(self):
        """Copy transcription to clipboard."""
        text = self.text_output.toPlainText()
        if text:
            copy_to_clipboard(text)

            # TTS announcement for manual copy action
            if self.config.audio_feedback_mode == "tts":
                get_announcer().announce_copied_to_clipboard()

            # Don't play beep here - only play when transcription first arrives
            self.status_label.setText("Copied!")
            self.status_label.setStyleSheet("color: rgba(40, 167, 69, 0.7); font-size: 11px;")
            self.status_label.show()
            QTimer.singleShot(2000, lambda: self.status_label.hide())

    def rewrite_transcript(self):
        """Rewrite the transcript with user instructions."""
        text = self.text_output.toPlainText()
        if not text:
            return

        # Show dialog to get rewrite instructions
        dialog = RewriteDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        instruction = dialog.get_instruction()
        if not instruction:
            QMessageBox.warning(
                self,
                "No Instruction",
                "Please enter instructions for how to rewrite the text.",
            )
            return

        # Get model from active preset (always using OpenRouter)
        _, model = self._get_current_model()
        api_key = self.config.openrouter_api_key

        if not api_key:
            QMessageBox.warning(
                self,
                "Missing API Key",
                "Please set your OpenRouter API key in Settings.",
            )
            return

        # Show rewrite status
        self.status_label.setText("Rewriting...")
        self.status_label.setStyleSheet("color: rgba(0, 123, 255, 0.7); font-size: 11px;")
        self.status_label.show()

        # Clean up any previous rewrite worker
        self._cleanup_worker("rewrite_worker")

        # Start rewrite worker
        self.rewrite_worker = RewriteWorker(
            text,
            instruction,
            api_key,
            model,
        )
        self.rewrite_worker.finished.connect(self.on_rewrite_complete)
        self.rewrite_worker.error.connect(self.on_rewrite_error)
        self.rewrite_worker.status.connect(self.on_worker_status)
        self.rewrite_worker.start()

    def on_rewrite_complete(self, result: TranscriptionResult):
        """Handle completed rewrite."""
        # Replace text with rewritten version
        self.text_output.setMarkdown(result.text)

        # Update cost tracking
        model = get_active_model(self.config)

        # Determine cost
        final_cost = 0.0
        if result.actual_cost is not None:
            final_cost = result.actual_cost
        elif result.input_tokens > 0 or result.output_tokens > 0:
            tracker = get_tracker()
            final_cost = tracker.record_usage(
                "openrouter", model, result.input_tokens, result.output_tokens
            )

        # Get inference time from worker
        inference_time_ms = self.rewrite_worker.inference_time_ms if self.rewrite_worker else 0

        # Save to database
        db = get_db()
        db.save_transcription(
            provider="openrouter",
            model=model,
            transcript_text=result.text,
            audio_duration_seconds=None,  # No audio for rewrite
            inference_time_ms=inference_time_ms,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            estimated_cost=final_cost,
            audio_file_path=None,
            vad_audio_duration_seconds=None,
            prompt_text_length=len(self.rewrite_worker.instruction) if self.rewrite_worker else 0,
        )

        # Check if embedding batch processing is needed
        if self.config.embedding_enabled and self.config.openrouter_api_key:
            self._check_embedding_batch()

        # Update all-time word count in footer
        self._update_all_time_word_count()

        self.status_label.setText("Rewrite complete!")
        self.status_label.setStyleSheet("color: rgba(40, 167, 69, 0.7); font-size: 11px;")
        self.status_label.show()
        QTimer.singleShot(2000, lambda: self.status_label.hide())

    def on_rewrite_error(self, error: str):
        """Handle rewrite error."""
        QMessageBox.critical(self, "Rewrite Error", error)
        self.status_label.hide()

    def download_transcript(self):
        """Download transcript with AI-generated title."""
        text = self.text_output.toPlainText()
        if not text:
            return

        # Get API key for title generation
        api_key = self.config.openrouter_api_key
        if not api_key:
            # Fallback: use manual filename if no API key
            from datetime import datetime

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"transcript_{timestamp}.md"
            self._save_transcript_to_file(filename, text)
            return

        self.status_label.setText("Generating title...")
        self.status_label.setStyleSheet("color: rgba(0, 123, 255, 0.7); font-size: 11px;")
        self.status_label.show()

        # Clean up any previous title worker
        self._cleanup_worker("title_worker")

        # Start title generation worker
        self.title_worker = TitleGeneratorWorker(
            text,
            api_key,
            "google/gemini-2.5-flash-lite",  # Use fast, cheap model for titles
        )
        self.title_worker.finished.connect(self.on_title_generated)
        self.title_worker.error.connect(self.on_title_error)
        self.title_worker.start()

    def on_title_generated(self, title: str):
        """Handle generated title and download file."""
        text = self.text_output.toPlainText()
        filename = f"{title}.md"
        self._save_transcript_to_file(filename, text)

        self.status_label.setText("Downloaded!")
        self.status_label.setStyleSheet("color: rgba(40, 167, 69, 0.7); font-size: 11px;")
        self.status_label.show()
        QTimer.singleShot(2000, lambda: self.status_label.hide())

    def on_title_error(self, error: str):
        """Handle title generation error - fall back to timestamp."""
        from datetime import datetime

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        text = self.text_output.toPlainText()
        filename = f"transcript_{timestamp}.md"
        self._save_transcript_to_file(filename, text)

        self.status_label.setText("Downloaded (timestamp)")
        self.status_label.setStyleSheet("color: rgba(40, 167, 69, 0.7); font-size: 11px;")
        self.status_label.show()
        QTimer.singleShot(2000, lambda: self.status_label.hide())

    def _save_transcript_to_file(self, filename: str, text: str):
        """Save transcript to Downloads folder with given filename."""
        from pathlib import Path
        import os

        # Get Downloads folder
        downloads_dir = Path.home() / "Downloads"
        file_path = downloads_dir / filename

        # Save file
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(text)
            print(f"Saved to: {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Download Error", f"Failed to save file: {e}")

    def show_settings(self):
        """Show settings dialog."""
        # Create dialog if it doesn't exist
        if self.settings_dialog is None:
            self.settings_dialog = SettingsDialog(self.config, self.recorder, self)
            # Connect to settings_closed signal to sync UI state
            self.settings_dialog.settings_closed.connect(self._sync_ui_from_settings)
            # Connect to hotkeys_changed signal to re-register global hotkeys
            self.settings_dialog.hotkeys_changed.connect(self._refresh_hotkeys)

        # Refresh and show
        self.settings_dialog.refresh()
        self.settings_dialog.show()
        self.settings_dialog.raise_()
        self.settings_dialog.activateWindow()

    def _refresh_hotkeys(self):
        """Re-register global hotkeys after config change."""
        # Re-register global hotkeys
        self._register_hotkeys()
        # Re-setup in-focus shortcuts
        self._setup_configurable_shortcuts()

    def _sync_ui_from_settings(self):
        """Sync UI state with current config after settings dialog closes."""
        # Update status bar displays in case they changed
        self._update_mic_display()
        # Refresh model preset menu in case favorites were added/removed/renamed
        self._refresh_model_preset_menu()

    def show_history_window(self):
        """Show the standalone history window."""
        # Create window if it doesn't exist
        if self.history_window is None:
            self.history_window = HistoryWindow(config=self.config)

        # Show (refreshes automatically via showEvent)
        self.history_window.show()
        self.history_window.raise_()
        self.history_window.activateWindow()

    def _check_embedding_batch(self):
        """Check if embedding batch processing is needed and run if so.

        Embeddings are generated in batches of 100 transcripts to avoid
        excessive API calls. This method checks if we have enough unembedded
        transcripts and triggers background processing if needed.
        """
        try:
            from .embedding_store import get_embedding_store, get_batch_processor

            store = get_embedding_store()
            if store is None:
                return

            # Check if we have enough unembedded transcripts
            if not store.needs_batch_processing():
                return

            # Get or create batch processor
            processor = get_batch_processor(self.config.openrouter_api_key)
            if processor is None:
                return

            # Skip if already processing
            if processor.is_processing():
                return

            # Start batch processing in background
            def on_batch_complete(count, error):
                if error:
                    print(f"Embedding batch error: {error}")
                elif count > 0:
                    print(f"Generated {count} embeddings")

            processor.process_batch_async(callback=on_batch_complete)

        except Exception as e:
            # Non-critical error, just log it
            print(f"Embedding batch check failed: {e}")

    def show_file_transcription_window(self):
        """Show the file transcription window (Beta feature)."""
        # Create window if it doesn't exist
        if self.file_transcription_window is None:
            self.file_transcription_window = FileTranscriptionWindow(config=self.config)

        # Show
        self.file_transcription_window.show()
        self.file_transcription_window.raise_()
        self.file_transcription_window.activateWindow()

    def show_analytics(self):
        """Show analytics dialog."""
        # Create dialog if it doesn't exist
        if self.analytics_dialog is None:
            self.analytics_dialog = AnalyticsDialog(self)

        # Show (refreshes automatically via showEvent)
        self.analytics_dialog.show()
        self.analytics_dialog.raise_()
        self.analytics_dialog.activateWindow()

    def show_about(self):
        """Show about dialog."""
        # Create dialog if it doesn't exist
        if self.about_dialog is None:
            self.about_dialog = AboutDialog(self)

        # Show
        self.about_dialog.show()
        self.about_dialog.raise_()
        self.about_dialog.activateWindow()

    def show_window(self):
        """Show and raise the window, handling minimized state."""
        # If minimized, restore to normal state first
        if self.isMinimized():
            self.showNormal()
        else:
            self.show()
        self.raise_()
        self.activateWindow()
        # On Wayland/KDE, we may need additional activation
        # Setting window state can help ensure it comes to front
        self.setWindowState(
            (self.windowState() & ~Qt.WindowState.WindowMinimized) | Qt.WindowState.WindowActive
        )

    def eventFilter(self, watched, event):
        """Handle events from child widgets."""
        # DualOutputPanel handles its own layout, so we just pass through
        return super().eventFilter(watched, event)

    def changeEvent(self, event):
        """Handle window state changes for proper taskbar activation on Wayland/KDE."""

        if event.type() == QEvent.Type.ActivationChange:
            # When window is activated (e.g., via taskbar click), ensure it's visible and raised
            if self.isActiveWindow() and self.isMinimized():
                self.showNormal()
        elif event.type() == QEvent.Type.WindowStateChange:
            # If being restored from minimized state, ensure proper activation
            if not self.isMinimized() and self.isVisible():
                self.raise_()
                self.activateWindow()
        super().changeEvent(event)

    def on_tray_activated(self, reason):
        """Handle tray icon activation based on current state."""
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self._tray_state == "recording":
                # Clicking during recording stops it and enters stopped state
                self._tray_stop_recording()
            elif self._tray_state == "stopped":
                # In stopped state, show window so user can decide
                self.show_window()
            else:
                # For idle, transcribing, complete: toggle window visibility
                if self.isVisible():
                    self.hide()
                else:
                    self.show_window()

    def _get_completion_tray_state(self, did_clipboard: bool, did_inject: bool) -> str:
        """Determine the appropriate tray state based on what actions were performed.

        Args:
            did_clipboard: Whether text was copied to clipboard
            did_inject: Whether text was injected at cursor

        Returns:
            Tray state string for _set_tray_state
        """
        if did_clipboard and did_inject:
            return "clipboard_inject_complete"
        elif did_clipboard:
            return "clipboard_complete"
        elif did_inject:
            return "inject_complete"
        else:
            return "complete"

    def _set_tray_state(self, state: str):
        """Update tray icon and menu based on state.

        States: 'idle', 'recording', 'stopped', 'transcribing', 'complete',
                'clipboard_complete', 'inject_complete', 'clipboard_inject_complete'
        """
        self._tray_state = state
        # Update icon and status label
        if state == "idle":
            self.tray.setIcon(self._tray_icon_idle)
            self.status_label.hide()  # No status shown in idle state
        elif state == "recording":
            self.tray.setIcon(self._tray_icon_recording)
            self.status_label.setText("● Recording")
            self.status_label.setStyleSheet("""
                QLabel {
                    color: rgba(220, 53, 69, 0.7);
                    font-size: 11px;
                }
            """)
            self.status_label.show()
        elif state == "stopped":
            self.tray.setIcon(self._tray_icon_stopped)
            self.status_label.setText("⏸ Stopped")
            self.status_label.setStyleSheet("""
                QLabel {
                    color: rgba(255, 193, 7, 0.8);
                    font-size: 11px;
                }
            """)
            self.status_label.show()
        elif state == "transcribing":
            self.tray.setIcon(self._tray_icon_transcribing)
            self.status_label.setText("⟳ Transcribing")
            self.status_label.setStyleSheet("""
                QLabel {
                    color: rgba(0, 123, 255, 0.7);
                    font-size: 11px;
                }
            """)
            self.status_label.show()
        elif state == "complete":
            self.tray.setIcon(self._tray_icon_complete)
            self.status_label.setText("✓ Complete")
            self.status_label.setStyleSheet("""
                QLabel {
                    color: rgba(40, 167, 69, 0.7);
                    font-size: 11px;
                }
            """)
            self.status_label.show()
        elif state == "clipboard_complete":
            self.tray.setIcon(self._tray_icon_clipboard)
            self.status_label.setText("📋 Text on Clipboard")
            self.status_label.setStyleSheet("""
                QLabel {
                    color: rgba(40, 167, 69, 0.7);
                    font-size: 11px;
                }
            """)
            self.status_label.show()
        elif state == "inject_complete":
            self.tray.setIcon(self._tray_icon_inject)
            self.status_label.setText("⌨ Text Injected")
            self.status_label.setStyleSheet("""
                QLabel {
                    color: rgba(40, 167, 69, 0.7);
                    font-size: 11px;
                }
            """)
            self.status_label.show()
        elif state == "clipboard_inject_complete":
            # Both clipboard and inject were performed
            self.tray.setIcon(self._tray_icon_clipboard)  # Use clipboard icon as primary
            self.status_label.setText("📋⌨ Copied + Injected")
            self.status_label.setStyleSheet("""
                QLabel {
                    color: rgba(40, 167, 69, 0.7);
                    font-size: 11px;
                }
            """)
            self.status_label.show()
        # Update menu
        self._update_tray_menu()

    def _update_tray_menu(self):
        """Rebuild tray menu based on current state."""
        self._tray_menu.clear()

        # Show action is always available
        self._tray_menu.addAction(self._tray_show_action)

        self._tray_menu.addSeparator()

        # Recording actions - state dependent
        complete_states = (
            "complete",
            "clipboard_complete",
            "inject_complete",
            "clipboard_inject_complete",
        )
        if self._tray_state == "idle" or self._tray_state in complete_states:
            self._tray_menu.addAction(self._tray_record_action)
        elif self._tray_state == "recording":
            self._tray_menu.addAction(self._tray_send_action)
            self._tray_menu.addAction(self._tray_stop_action)
            self._tray_menu.addAction(self._tray_retake_action)
            # Discard option while recording
            self._tray_menu.addAction(self._tray_discard_action)
        elif self._tray_state == "stopped":
            self._tray_menu.addAction(self._tray_transcribe_action)
            self._tray_menu.addAction(self._tray_resume_action)
            self._tray_menu.addAction(self._tray_retake_action)
            self._tray_menu.addAction(self._tray_delete_action)
        # transcribing state: no recording actions available

        self._tray_menu.addSeparator()

        # Mode submenu - always available (now with independent checkboxes)
        self._tray_mode_menu.clear()
        mode_states = {
            "app": self.config.output_to_app,
            "clipboard": self.config.output_to_clipboard,
            "inject": self.config.output_to_inject,
        }
        for mode_key, action in self._tray_mode_actions.items():
            action.setChecked(mode_states.get(mode_key, False))
            self._tray_mode_menu.addAction(action)
        self._tray_menu.addMenu(self._tray_mode_menu)

        # Utility actions - always available
        self._tray_menu.addAction(self._tray_copy_action)
        self._tray_menu.addAction(self._tray_history_action)
        self._tray_menu.addAction(self._tray_settings_action)

        self._tray_menu.addSeparator()
        self._tray_menu.addAction(self._tray_quit_action)

    def _tray_toggle_mode(self, mode: str):
        """Toggle output mode from tray menu.

        Args:
            mode: One of "app", "clipboard", or "inject"
        """
        self._toggle_output_mode(mode)
        # Update tray menu to reflect new checkmark
        self._update_tray_menu()

    def _tray_stop_recording(self):
        """Stop recording from tray click - enters stopped state for user decision."""
        if not self.recorder.is_recording:
            return

        # Use the new handle_stop_button method to stop and cache audio
        self.handle_stop_button()

        # Show notification
        self.tray.showMessage(
            "Recording Stopped",
            "Click Transcribe, Append, or Delete from tray menu, or use main window.",
            QSystemTrayIcon.MessageIcon.Information,
            3000,
        )

    def _tray_transcribe_stopped(self):
        """Transcribe the stopped recording from tray menu."""
        if self._tray_state != "stopped":
            return

        # Transcribe cached audio
        if self.has_cached_audio:
            self.transcribe_cached_audio()
        elif self.recorder.is_recording:
            # Fallback in case state is inconsistent
            self.stop_and_transcribe()

    def _tray_delete_stopped(self):
        """Delete the stopped recording from tray menu."""
        if self._tray_state != "stopped":
            return
        self.delete_recording()

    def _tray_resume_recording(self):
        """Append more audio from stopped state via tray menu."""
        if self._tray_state != "stopped":
            return

        # Use append functionality to record more clips
        self.append_to_transcription()

    def _tray_retake_recording(self):
        """Retake recording from tray menu - discard current and start fresh."""
        self.retake_recording()

    def _tray_send_for_transcription(self):
        """Stop recording and send for transcription from tray menu."""
        if self.recorder.is_recording:
            self.stop_and_transcribe()

    def _tray_discard_recording(self):
        """Discard current recording from tray menu (no confirmation dialog).

        This is a quick-access discard that stops and deletes the recording
        without showing a confirmation dialog. Use this for rapid workflow
        when you know you don't want the recording.
        """
        if not self.recorder.is_recording and not self.recorder.is_paused:
            return

        # Audio feedback for discard (beeps or TTS based on mode)
        if self.config.audio_feedback_mode == "beeps":
            get_feedback().play_stop_beep()
        elif self.config.audio_feedback_mode == "tts":
            get_announcer().announce_discarded()

        self.timer.stop()
        self.recorder.stop_recording()
        self._stop_recording_visual_effects()
        self.recorder.clear()

        # Clear accumulated segments
        self.accumulated_segments = []
        self.accumulated_duration = 0.0
        self._update_segment_indicator()

        # Reset state flags
        self.append_mode = False
        self.has_cached_audio = False
        self.has_failed_audio = False

        # Clear any failed audio data
        if hasattr(self, "last_audio_data"):
            del self.last_audio_data
        if hasattr(self, "last_audio_duration"):
            del self.last_audio_duration
        if hasattr(self, "last_vad_duration"):
            del self.last_vad_duration

        self.reset_ui()
        self._set_tray_state("idle")

        # Show brief notification
        self.tray.showMessage(
            "Recording Discarded",
            "Recording has been deleted.",
            QSystemTrayIcon.MessageIcon.Information,
            1500,
        )

    # =========================================================================
    # RECENT PANEL HELPERS
    # =========================================================================

    def _load_transcript_from_history(self, transcript_id: str):
        """Load a transcript from history into the text output area."""
        db = get_db()
        record = db.get_transcription(transcript_id)
        if record:
            self.text_output.setMarkdown(record.transcript_text)

    def _on_recent_copied(self, transcript_id: str):
        """Handle copy from recent panel - play audio feedback."""
        if self.config.audio_feedback_mode == "beeps":
            get_feedback().play_clipboard_beep()
        elif self.config.audio_feedback_mode == "tts":
            get_announcer().announce_text_on_clipboard()

    def _copy_last_transcription(self):
        """Copy the most recent transcription to clipboard (for global hotkey)."""
        text = self.recent_panel.get_most_recent_text()
        if text:
            copy_to_clipboard(text)
            if self.config.audio_feedback_mode == "beeps":
                get_feedback().play_clipboard_beep()
            elif self.config.audio_feedback_mode == "tts":
                get_announcer().announce_text_on_clipboard()

    def _copy_recent_by_index(self, index: int):
        """Copy recent transcript by index (0-4 for Ctrl+1 through Ctrl+5)."""
        if self.recent_panel.copy_by_index(index):
            if self.config.audio_feedback_mode == "beeps":
                get_feedback().play_clipboard_beep()
            elif self.config.audio_feedback_mode == "tts":
                get_announcer().announce_text_on_clipboard()

    # =========================================================================
    # QUEUE AND OUTPUT PANEL HANDLERS
    # =========================================================================

    def _on_output_copy_clicked(self, slot_number: int):
        """Handle copy button click from output panel."""
        if self.config.audio_feedback_mode == "beeps":
            get_feedback().play_clipboard_beep()
        elif self.config.audio_feedback_mode == "tts":
            get_announcer().announce_text_on_clipboard()

    def _on_queue_item_started(self, item_id: str):
        """Handle queue item starting transcription."""
        self.output_panel.on_transcription_started(item_id)
        self._set_tray_state("transcribing")

    def _on_queue_item_complete(self, item_id: str, result):
        """Handle queue item completion."""
        # Display in the output panel
        self.output_panel.on_transcription_complete(item_id, result.text)

        # Handle output modes (clipboard, inject)
        self._handle_queue_result_outputs(result)

        # Schedule housekeeping
        self._schedule_queue_housekeeping(item_id, result)

        # Update UI state
        if self.transcription_queue.is_empty():
            self.reset_ui()
            self._set_tray_state("complete")
            QTimer.singleShot(3000, lambda: self._set_tray_state("idle") if self._tray_state == "complete" else None)

    def _on_queue_item_error(self, item_id: str, error: str):
        """Handle queue item error."""
        self.output_panel.on_transcription_error(item_id, error)

        # Show error notification
        self.tray.showMessage(
            "Transcription Error",
            error[:100] + "..." if len(error) > 100 else error,
            QSystemTrayIcon.MessageIcon.Warning,
            3000,
        )

        if self.transcription_queue.is_empty():
            self.reset_ui()
            self._set_tray_state("idle")

    def _on_queue_item_status(self, item_id: str, status: str):
        """Handle queue item status update."""
        self.output_panel.on_transcription_status(item_id, status)

    def _on_queue_changed(self):
        """Handle queue state change."""
        status = self.transcription_queue.get_queue_status()
        self.output_panel.update_queue_status(
            status["pending_count"],
            status["active_count"]
        )

    def _handle_queue_result_outputs(self, result):
        """Handle clipboard and inject outputs for a queue result."""
        output_to_clipboard = self.config.output_to_clipboard
        output_to_inject = self.config.output_to_inject

        did_clipboard = False
        did_inject = False

        if output_to_clipboard:
            copy_to_clipboard(result.text)
            did_clipboard = True

        if output_to_inject:
            if self._inject_text_at_cursor(result.text):
                did_inject = True

        # Audio feedback
        if self.config.audio_feedback_mode == "beeps":
            if did_clipboard or did_inject:
                get_feedback().play_clipboard_beep()
        elif self.config.audio_feedback_mode == "tts":
            if did_clipboard:
                get_announcer().announce_text_on_clipboard()
            elif did_inject:
                get_announcer().announce_text_injected()
            else:
                get_announcer().announce_complete()

    def _schedule_queue_housekeeping(self, item_id: str, result):
        """Schedule housekeeping tasks for a completed queue item."""
        # Get queue item for metadata
        item = None
        for completed in self.transcription_queue.completed:
            if completed.id == item_id:
                item = completed
                break

        if not item:
            return

        model = item.settings.model
        audio_duration = item.original_duration
        vad_duration = item.vad_duration
        prompt_length = len(item.settings.prompt)
        inference_time_ms = item.inference_time_ms

        # Determine cost
        final_cost = 0.0
        if result.actual_cost is not None:
            final_cost = result.actual_cost
        elif result.input_tokens > 0 or result.output_tokens > 0:
            tracker = get_tracker()
            final_cost = tracker.record_usage(
                "openrouter", model, result.input_tokens, result.output_tokens
            )

        def do_housekeeping():
            # Save to database
            db = get_db()
            db.save_transcription(
                provider="openrouter",
                model=model,
                transcript_text=result.text,
                audio_duration_seconds=audio_duration,
                inference_time_ms=inference_time_ms,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                estimated_cost=final_cost,
                audio_file_path=None,  # Queue doesn't support archival yet
                vad_audio_duration_seconds=vad_duration,
                prompt_text_length=prompt_length,
            )

            # Check embedding batch
            if self.config.embedding_enabled and self.config.openrouter_api_key:
                self._check_embedding_batch()

            # Update stats
            self._update_all_time_word_count()
            self.recent_panel.refresh()

        QTimer.singleShot(0, do_housekeeping)

    def quit_app(self):
        """Quit the application."""
        # Clean up all worker threads first to prevent callbacks after quit
        self._cleanup_all_workers()

        # Clean up transcription queue
        self.transcription_queue.cleanup()

        # Stop hotkey listener
        self.hotkey_listener.stop()

        # Clean up audio recorder
        self.recorder.cleanup()

        # Save recent panel state
        self.config.recent_panel_collapsed = self.recent_panel.collapsed

        # Save config
        save_config(self.config)

        # Now quit the application
        QApplication.quit()

    def closeEvent(self, event):
        """Handle window close - minimize to tray instead."""
        event.ignore()
        self.hide()
        self.tray.showMessage(
            "AI Transcription Utility",
            "Minimized to system tray. Click icon to restore.",
            QSystemTrayIcon.MessageIcon.Information,
            2000,
        )


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # Keep running in tray

    window = MainWindow()
    if not window.config.start_minimized:
        window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
