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
    QTabWidget,
    QMessageBox,
    QFrame,
    QFileDialog,
    QRadioButton,
    QButtonGroup,
    QGroupBox,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize
import time
from PyQt6.QtGui import QIcon, QAction, QFont, QClipboard, QShortcut, QKeySequence, QActionGroup
from PyQt6.QtWidgets import QCompleter

from .config import (
    Config, load_config, save_config, load_env_keys, CONFIG_DIR,
    GEMINI_MODELS, OPENROUTER_MODELS,
    MODEL_TIERS, build_cleanup_prompt, get_model_display_name,
    FORMAT_TEMPLATES, FORMAT_DISPLAY_NAMES, FORMALITY_DISPLAY_NAMES, VERBOSITY_DISPLAY_NAMES, EMAIL_SIGNOFFS,
)
from .audio_recorder import AudioRecorder
from .transcription import get_client, TranscriptionResult
from .audio_processor import compress_audio_for_api, archive_audio, get_audio_info, combine_wav_segments
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
from .history_widget import HistoryWidget
from .analytics_widget import AnalyticsDialog
from .settings_widget import SettingsDialog
from .about_widget import AboutDialog
from .audio_feedback import get_feedback
from .file_transcription_widget import FileTranscriptionWidget
from .mic_naming_ai import MicrophoneNamingAI
from .prompt_library import PromptLibrary, build_prompt_from_config
from .favorites_bar import FavoritesBar
from .prompt_editor_window import PromptEditorWindow
from .rewrite_dialog import RewriteDialog


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
        provider: str,
        api_key: str,
        model: str,
        prompt: str,
        vad_enabled: bool = False,
    ):
        super().__init__()
        self.audio_data = audio_data
        self.provider = provider
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
                        print(f"VAD: Reduced audio from {orig_dur:.1f}s to {vad_dur:.1f}s ({reduction:.0f}% reduction)")
                except Exception as e:
                    print(f"VAD failed, using original audio: {e}")

            # Compress audio to 16kHz mono before sending
            self.status.emit("Compressing audio...")
            compressed_audio = compress_audio_for_api(audio_data)

            self.status.emit("Transcribing...")
            start_time = time.time()
            client = get_client(self.provider, self.api_key, self.model)
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
        provider: str,
        api_key: str,
        model: str,
    ):
        super().__init__()
        self.text = text
        self.instruction = instruction
        self.provider = provider
        self.api_key = api_key
        self.model = model
        self.inference_time_ms: int = 0

    def run(self):
        try:
            self.status.emit("Rewriting...")
            start_time = time.time()
            client = get_client(self.provider, self.api_key, self.model)
            result = client.rewrite_text(self.text, self.instruction)
            self.inference_time_ms = int((time.time() - start_time) * 1000)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class TitleGeneratorWorker(QThread):
    """Worker thread for title generation."""

    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, text: str, provider: str, api_key: str, model: str):
        super().__init__()
        self.text = text
        self.provider = provider
        self.api_key = api_key
        self.model = model

    def run(self):
        try:
            client = get_client(self.provider, self.api_key, self.model)
            title = client.generate_title(self.text)
            self.finished.emit(title)
        except Exception as e:
            self.error.emit(str(e))



class MainWindow(QMainWindow):
    """Main application window."""

    # Signal for handling mic errors from background thread
    mic_error = pyqtSignal(str)
    # Signal for balance updates from background thread
    balance_updated = pyqtSignal(object)  # OpenRouterCredits or None

    def __init__(self):
        super().__init__()
        self.config = load_env_keys(load_config())
        self.recorder = AudioRecorder(self.config.sample_rate)
        self.recorder.on_error = self._on_recorder_error
        self.worker: TranscriptionWorker | None = None
        self.recording_duration = 0.0
        self.accumulated_segments: list[bytes] = []  # For append mode
        self.accumulated_duration: float = 0.0
        self.append_mode: bool = False  # Track if next transcription should append
        self.has_cached_audio: bool = False  # Track if we have stopped audio waiting to be transcribed

        # Initialize unified prompt library
        self.prompt_library = PromptLibrary(CONFIG_DIR)
        self.current_prompt_id = self.config.format_preset or "general"

        # Set window title (add DEV suffix if in dev mode)
        title = "Voice Notepad"
        if os.environ.get("VOICE_NOTEPAD_DEV_MODE") == "1":
            title += " (DEV)"
        self.setWindowTitle(title)
        self.setMinimumSize(620, 700)
        self.resize(self.config.window_width, self.config.window_height)

        self.setup_ui()
        self.setup_tray()
        self.setup_timer()
        self.setup_shortcuts()
        self.setup_global_hotkeys()

        # Connect mic error signal (for thread-safe error handling)
        self.mic_error.connect(self._handle_mic_error)
        # Connect balance update signal (for async balance fetch)
        self.balance_updated.connect(self._on_balance_received)

        # Start minimized if configured
        if self.config.start_minimized:
            self.hide()

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

    def _on_recorder_error(self, error_msg: str):
        """Called from recorder thread when an error occurs."""
        # Emit signal to handle on main thread
        self.mic_error.emit(error_msg)

    def _handle_mic_error(self, error_msg: str):
        """Handle microphone error on main thread."""
        self.timer.stop()
        self.status_label.setText(f"⚠️ {error_msg}")
        self.status_label.setStyleSheet("color: #dc3545; font-weight: bold;")
        self.tray.showMessage(
            "Voice Notepad",
            error_msg,
            QSystemTrayIcon.MessageIcon.Warning,
            3000,
        )
        # Reset UI but keep any recorded audio
        self.record_btn.setText("●")
        self.record_btn.setStyleSheet(self._record_btn_idle_style)
        self.record_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        # Keep transcribe enabled if we have cached audio
        if self.accumulated_segments:
            self.has_cached_audio = True
            self.stop_btn.setEnabled(False)
            self.transcribe_btn.setEnabled(True)
            self.transcribe_btn.setStyleSheet(self._transcribe_btn_idle_style)  # Green when cached
            self.append_btn.setEnabled(True)
            self.delete_btn.setEnabled(True)
        else:
            self.has_cached_audio = False
            self.stop_btn.setEnabled(False)
            self.transcribe_btn.setEnabled(False)
            self.append_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
        self._set_tray_state('idle')

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
        analytics_action = QAction("Analytics...", self)
        analytics_action.triggered.connect(self.show_analytics)
        view_menu.addAction(analytics_action)

        # Settings menu
        settings_menu = menubar.addMenu("Settings")
        preferences_action = QAction("Preferences...", self)
        preferences_action.triggered.connect(self.show_settings)
        settings_menu.addAction(preferences_action)

        # Help menu
        help_menu = menubar.addMenu("Help")
        about_action = QAction("About Voice Notepad...", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(12, 8, 12, 12)

        # Recording controls (centered)
        control_bar = QHBoxLayout()
        control_bar.setSpacing(8)
        control_bar.addStretch()

        # Recording controls - using icons for compact display
        self.record_btn = QPushButton("●")  # Record icon
        self.record_btn.setMinimumHeight(36)
        self.record_btn.setMinimumWidth(44)
        self.record_btn.setToolTip(
            "Record\n"
            "Start a new recording.\n"
            "Clears any cached audio and begins fresh."
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
                font-size: 18px;
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
                font-size: 18px;
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

        self.pause_btn = QPushButton("⏸")  # Pause icon (changes to ▶ when paused)
        self.pause_btn.setMinimumHeight(36)
        self.pause_btn.setMinimumWidth(44)
        self.pause_btn.setEnabled(False)
        self.pause_btn.setToolTip(
            "Pause\n"
            "Pause/resume the current recording.\n"
            "Only available while recording is active."
        )
        self.pause_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 16px;
                padding: 0 8px;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
            QPushButton:disabled {
                background-color: #6c757d;
                color: #aaa;
            }
        """)
        self.pause_btn.clicked.connect(self.toggle_pause)
        control_bar.addWidget(self.pause_btn)

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
                font-size: 20px;
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

        self.transcribe_btn = QPushButton("➤")  # Transcribe/send icon
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
                    stop:0 #34c759, stop:1 #28a745);
                color: white;
                border: none;
                border-bottom: 3px solid #1e7b34;
                border-radius: 6px;
                font-weight: bold;
                font-size: 18px;
                padding: 0 8px;
            }
            QPushButton:hover {
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #28a745, stop:1 #218838);
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
                font-size: 18px;
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
                font-size: 18px;
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
        main_layout.addLayout(control_bar)

        # Status line (centered below controls)
        status_bar = QHBoxLayout()
        status_bar.setSpacing(8)
        status_bar.addStretch()

        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("""
            QLabel {
                color: #6c757d;
                font-weight: bold;
                font-size: 13px;
            }
        """)
        status_bar.addWidget(self.status_label)

        self.duration_label = QLabel("0:00")
        self.duration_label.setFont(QFont("Monospace", 12))
        status_bar.addWidget(self.duration_label)

        self.segment_label = QLabel("")
        self.segment_label.setStyleSheet("color: #17a2b8; font-weight: bold;")
        status_bar.addWidget(self.segment_label)

        status_bar.addStretch()
        main_layout.addLayout(status_bar)

        # Main tabs
        self.tabs = QTabWidget()

        # Record tab
        record_tab = QWidget()
        layout = QVBoxLayout(record_tab)
        layout.setSpacing(12)
        layout.setContentsMargins(8, 12, 8, 8)

        # Quick format selector with help text
        format_section_layout = QVBoxLayout()
        format_section_layout.setSpacing(8)

        # Help text explaining the format system
        format_help = QLabel(
            "<b>Quick Formats:</b> Pre-configured output styles for common use cases. "
            "These formats work with the system prompt to shape your transcription. "
            "For more formats, click 'Manage Prompts' or use 'Prompt Stacks' for advanced combinations."
        )
        format_help.setWordWrap(True)
        format_help.setStyleSheet("color: #666; font-size: 11px; padding: 4px 0; margin-bottom: 4px;")
        format_section_layout.addWidget(format_help)

        # Dynamic favorites bar for quick format selection
        # Supports up to 20 user-configurable favorites
        self.favorites_bar = FavoritesBar(CONFIG_DIR)
        self.favorites_bar.prompt_selected.connect(self._on_prompt_selected_from_bar)
        self.favorites_bar.manage_clicked.connect(self._open_prompt_editor)

        # Set initial selection based on config
        if self.config.format_preset:
            self.favorites_bar.set_selected_prompt_id(self.config.format_preset)

        format_section_layout.addWidget(self.favorites_bar)
        layout.addLayout(format_section_layout)

        # Quick toggles row (Quiet Mode, Text Injection)
        toggles_layout = QHBoxLayout()
        toggles_layout.setSpacing(20)

        self.quiet_mode_checkbox = QCheckBox("🔇 Quiet Mode")
        self.quiet_mode_checkbox.setChecked(self.config.quiet_mode)
        self.quiet_mode_checkbox.setToolTip("Suppress all audio beeps")
        self.quiet_mode_checkbox.toggled.connect(self._on_quiet_mode_changed)
        toggles_layout.addWidget(self.quiet_mode_checkbox)

        self.auto_paste_cb = QCheckBox("📋 Text Injection")
        self.auto_paste_cb.setChecked(self.config.auto_paste)
        self.auto_paste_cb.setToolTip("Auto-paste (Ctrl+V) after copying to clipboard")
        self.auto_paste_cb.toggled.connect(self._on_auto_paste_toggled)
        toggles_layout.addWidget(self.auto_paste_cb)

        toggles_layout.addStretch()
        layout.addLayout(toggles_layout)

        # Text output area with markdown rendering
        self.text_output = MarkdownTextWidget()
        self.text_output.setPlaceholderText("Transcription will appear here...")
        self.text_output.setFont(QFont("Sans", 11))
        layout.addWidget(self.text_output, 1)

        # Word count label
        self.word_count_label = QLabel("")
        self.word_count_label.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(self.word_count_label)

        # Connect text changes to word count update
        self.text_output.textChanged.connect(self.update_word_count)

        # Bottom buttons with improved spacing
        bottom = QHBoxLayout()
        bottom.setSpacing(12)  # Increased spacing between buttons

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setMinimumHeight(38)
        self.clear_btn.setMinimumWidth(100)
        self.clear_btn.clicked.connect(self.clear_transcription)
        bottom.addWidget(self.clear_btn)

        self.rewrite_btn = QPushButton("✍️ Rewrite")
        self.rewrite_btn.setMinimumHeight(38)
        self.rewrite_btn.setMinimumWidth(120)
        self.rewrite_btn.setEnabled(False)  # Disabled until we have text
        self.rewrite_btn.setToolTip(
            "Send the transcript back to the AI with custom instructions to rewrite it"
        )
        self.rewrite_btn.setStyleSheet("""
            QPushButton {
                background-color: #17a2b8;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #138496;
            }
            QPushButton:disabled {
                background-color: #6c757d;
                color: #aaa;
            }
        """)
        self.rewrite_btn.clicked.connect(self.rewrite_transcript)
        bottom.addWidget(self.rewrite_btn)

        self.download_btn = QPushButton("⬇ Download")
        self.download_btn.setMinimumHeight(38)
        self.download_btn.setMinimumWidth(130)
        self.download_btn.setEnabled(False)  # Disabled until we have text
        self.download_btn.setToolTip(
            "Download the transcript with an AI-generated filename"
        )
        self.download_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
            QPushButton:disabled {
                background-color: #6c757d;
                color: #aaa;
            }
        """)
        self.download_btn.clicked.connect(self.download_transcript)
        bottom.addWidget(self.download_btn)

        self.save_btn = QPushButton("Save As...")
        self.save_btn.setMinimumHeight(38)
        self.save_btn.setMinimumWidth(110)
        self.save_btn.clicked.connect(self.save_to_file)
        bottom.addWidget(self.save_btn)

        bottom.addStretch()

        self.copy_btn = QPushButton("Copy")
        self.copy_btn.setMinimumHeight(38)
        self.copy_btn.setMinimumWidth(100)
        self.copy_btn.clicked.connect(self.copy_to_clipboard)
        bottom.addWidget(self.copy_btn)

        layout.addLayout(bottom)

        # Bottom status bar: microphone (left), model (right)
        status_bar = QHBoxLayout()

        # Microphone info (left)
        self.mic_label = QLabel()
        self.mic_label.setStyleSheet("color: #888; font-size: 11px;")
        status_bar.addWidget(self.mic_label)

        status_bar.addStretch()

        # Model info (right)
        self.model_label = QLabel()
        self.model_label.setStyleSheet("color: #888; font-size: 11px;")
        status_bar.addWidget(self.model_label)

        layout.addLayout(status_bar)

        # Initialize mic and model displays
        self._update_mic_display()
        self._update_model_display()

        self.tabs.addTab(record_tab, "🎙️ Record")

        # File Transcription tab (right after Record)
        self.file_transcription_widget = FileTranscriptionWidget(config=self.config)
        self.tabs.addTab(self.file_transcription_widget, "📁 File")

        # History tab
        self.history_widget = HistoryWidget(config=self.config)
        self.history_widget.transcription_selected.connect(self.on_history_transcription_selected)
        self.tabs.addTab(self.history_widget, "📝 History")

        # Prompt Editor window (opened via button, not a tab)
        self.prompt_editor_window = None

        # Dialogs (opened via menu, not tabs)
        self.settings_dialog = None
        self.analytics_dialog = None
        self.about_dialog = None

        # Refresh data when switching tabs
        self.tabs.currentChanged.connect(self.on_tab_changed)

        main_layout.addWidget(self.tabs, 1)

    def setup_tray(self):
        """Set up system tray icon."""
        self.tray = QSystemTrayIcon(self)

        # Track tray state for click behavior and menu updates
        # States: 'idle', 'recording', 'stopped', 'transcribing', 'complete'
        self._tray_state = 'idle'

        # Set up icons for different states
        # Idle: notepad/text editor icon (common in KDE themes)
        self._tray_icon_idle = QIcon.fromTheme(
            "accessories-text-editor",
            QIcon.fromTheme("text-x-generic",
                self.style().standardIcon(self.style().StandardPixmap.SP_FileDialogDetailedView))
        )
        # Recording: red record icon
        self._tray_icon_recording = QIcon.fromTheme(
            "media-record",
            self.style().standardIcon(self.style().StandardPixmap.SP_DialogNoButton)
        )
        # Stopped: pause icon (recording stopped, awaiting user decision)
        self._tray_icon_stopped = QIcon.fromTheme(
            "media-playback-pause",
            QIcon.fromTheme("player-pause",
                self.style().standardIcon(self.style().StandardPixmap.SP_MediaPause))
        )
        # Transcribing: process/sync icon (horizontal bar style)
        self._tray_icon_transcribing = QIcon.fromTheme(
            "emblem-synchronizing",
            QIcon.fromTheme("view-refresh",
                self.style().standardIcon(self.style().StandardPixmap.SP_BrowserReload))
        )
        # Complete: green tick/checkmark
        self._tray_icon_complete = QIcon.fromTheme(
            "emblem-ok",
            QIcon.fromTheme("dialog-ok",
                self.style().standardIcon(self.style().StandardPixmap.SP_DialogApplyButton))
        )

        self.tray.setIcon(self._tray_icon_idle)
        self.setWindowIcon(self._tray_icon_idle)

        # Tray menu - dynamic based on state
        self._tray_menu = QMenu()

        # Store actions as instance variables for dynamic visibility
        self._tray_show_action = QAction("Show", self)
        self._tray_show_action.triggered.connect(self.show_window)

        self._tray_record_action = QAction("Start Recording", self)
        self._tray_record_action.triggered.connect(self.toggle_recording)

        self._tray_stop_action = QAction("Stop Recording", self)
        self._tray_stop_action.triggered.connect(self._tray_stop_recording)

        self._tray_transcribe_action = QAction("Transcribe", self)
        self._tray_transcribe_action.triggered.connect(self._tray_transcribe_stopped)

        self._tray_delete_action = QAction("Delete Recording", self)
        self._tray_delete_action.triggered.connect(self._tray_delete_stopped)

        self._tray_resume_action = QAction("Append Clip", self)
        self._tray_resume_action.triggered.connect(self._tray_resume_recording)

        self._tray_quit_action = QAction("Quit", self)
        self._tray_quit_action.triggered.connect(self.quit_app)

        # Build initial menu
        self._update_tray_menu()

        self.tray.setContextMenu(self._tray_menu)
        self.tray.activated.connect(self.on_tray_activated)
        self.tray.show()

    def setup_timer(self):
        """Set up timer for updating recording duration."""
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_duration)

    def setup_shortcuts(self):
        """Set up keyboard shortcuts."""
        # Ctrl+R to start recording
        record_shortcut = QShortcut(QKeySequence("Ctrl+R"), self)
        record_shortcut.activated.connect(self.toggle_recording)

        # Ctrl+Space to pause/resume
        pause_shortcut = QShortcut(QKeySequence("Ctrl+Space"), self)
        pause_shortcut.activated.connect(self.toggle_pause_if_recording)

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

        # Set up configurable in-focus hotkeys (F15, F16, etc.)
        self._setup_configurable_shortcuts()

    def _setup_configurable_shortcuts(self):
        """Set up fixed F15-F19 shortcuts for when app has focus.

        Note: Global hotkeys (work when app is minimized) are handled separately
        in setup_global_hotkeys(). These in-focus shortcuts provide additional
        responsiveness when the window has focus.
        """
        # Clean up old shortcuts if they exist
        for attr in ['_f15_shortcut', '_f16_shortcut', '_f17_shortcut', '_f18_shortcut', '_f19_shortcut']:
            if hasattr(self, attr):
                shortcut = getattr(self, attr)
                shortcut.setEnabled(False)
                shortcut.deleteLater()

        # F15: Toggle recording
        self._f15_shortcut = QShortcut(QKeySequence("F15"), self)
        self._f15_shortcut.activated.connect(self._hotkey_toggle_recording)

        # F16: Tap (same as F15)
        self._f16_shortcut = QShortcut(QKeySequence("F16"), self)
        self._f16_shortcut.activated.connect(self._hotkey_toggle_recording)

        # F17: Transcribe only
        self._f17_shortcut = QShortcut(QKeySequence("F17"), self)
        self._f17_shortcut.activated.connect(self._hotkey_transcribe_only)

        # F18: Delete/clear
        self._f18_shortcut = QShortcut(QKeySequence("F18"), self)
        self._f18_shortcut.activated.connect(self._hotkey_delete)

        # F19: Append
        self._f19_shortcut = QShortcut(QKeySequence("F19"), self)
        self._f19_shortcut.activated.connect(self._hotkey_append)

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
        """Register fixed F-key hotkeys for all actions.

        FIXED F-KEY MAPPING:
        - F15: Simple toggle - Start recording / Stop and transcribe
        - F16: Tap toggle - Start recording / Stop and cache (for append mode)
        - F17: Transcribe cached audio only
        - F18: Clear cache/delete recording
        - F19: Append (start new recording to append to cache)

        NOTE: Pause key is intentionally NOT registered as pynput can receive
        spurious Key.pause events on some systems (e.g., mouse clicks being
        misinterpreted as pause key presses).
        """
        # Unregister all existing hotkeys first
        for name in ["pause_toggle", "f15_toggle", "f16_tap", "f17_transcribe", "f18_delete", "f19_append"]:
            self.hotkey_listener.unregister(name)

        # F15: Toggle recording (start/stop and cache)
        self.hotkey_listener.register(
            "f15_toggle",
            "f15",
            lambda: QTimer.singleShot(0, self._hotkey_toggle_recording)
        )

        # F16: Tap toggle (stop caches for append mode, unlike F15 which transcribes)
        self.hotkey_listener.register(
            "f16_tap",
            "f16",
            lambda: QTimer.singleShot(0, self._hotkey_tap_toggle)
        )

        # F17: Transcribe only (cached audio)
        self.hotkey_listener.register(
            "f17_transcribe",
            "f17",
            lambda: QTimer.singleShot(0, self._hotkey_transcribe_only)
        )

        # F18: Clear cache/delete
        self.hotkey_listener.register(
            "f18_delete",
            "f18",
            lambda: QTimer.singleShot(0, self._hotkey_delete)
        )

        # F19: Append
        self.hotkey_listener.register(
            "f19_append",
            "f19",
            lambda: QTimer.singleShot(0, self._hotkey_append)
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
        """Handle F19: Append (start new recording to add to cache)."""
        if not self.recorder.is_recording:
            self.append_to_transcription()

    def toggle_pause_if_recording(self):
        """Toggle pause only if currently recording."""
        if self.recorder.is_recording:
            self.toggle_pause()

    def stop_if_recording(self):
        """Stop and transcribe only if currently recording."""
        if self.recorder.is_recording:
            self.stop_and_transcribe()

    def update_word_count(self):
        """Update the word count display and enable/disable buttons."""
        text = self.text_output.toPlainText()
        if text:
            words = len(text.split())
            chars = len(text)
            self.word_count_label.setText(f"{words} words, {chars} characters")
            # Enable rewrite and download buttons when we have text
            self.rewrite_btn.setEnabled(True)
            self.download_btn.setEnabled(True)
        else:
            self.word_count_label.setText("")
            # Disable rewrite and download buttons when no text
            self.rewrite_btn.setEnabled(False)
            self.download_btn.setEnabled(False)

    def on_tab_changed(self, index: int):
        """Handle tab change - refresh data in the selected tab."""
        # Tabs: 0=Record, 1=File, 2=History, 3=Prompt
        if index == 2:  # History tab
            self.history_widget.refresh()
        # Record (0), File (1), Prompt (3) don't need refresh

    def on_history_transcription_selected(self, text: str):
        """Handle transcription selected from history - put in editor."""
        self.text_output.setMarkdown(text)
        self.tabs.setCurrentIndex(0)  # Switch to Record tab
        self.update_word_count()
        # Enable append button since we have text
        self.append_btn.setEnabled(True)

    def save_to_file(self):
        """Save transcription to a file."""
        text = self.text_output.toPlainText()
        if not text:
            self.status_label.setText("Nothing to save")
            self.status_label.setStyleSheet("color: #ffc107;")
            QTimer.singleShot(2000, lambda: self.status_label.setText("Ready"))
            QTimer.singleShot(2000, lambda: self.status_label.setStyleSheet("color: #666;"))
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Transcription",
            "",
            "Markdown Files (*.md);;Text Files (*.txt);;All Files (*)"
        )

        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(text)
                self.status_label.setText("Saved!")
                self.status_label.setStyleSheet("color: #28a745;")
            except Exception as e:
                QMessageBox.critical(self, "Save Error", str(e))
            finally:
                QTimer.singleShot(2000, lambda: self.status_label.setText("Ready"))
                QTimer.singleShot(2000, lambda: self.status_label.setStyleSheet("color: #666;"))

    def _open_prompt_editor(self):
        """Open the unified Prompt Editor window."""
        if self.prompt_editor_window is None:
            self.prompt_editor_window = PromptEditorWindow(
                self.config, CONFIG_DIR, self
            )
            self.prompt_editor_window.favorites_changed.connect(self._on_favorites_changed)

        self.prompt_editor_window.show()
        self.prompt_editor_window.raise_()
        self.prompt_editor_window.activateWindow()

    def _on_quiet_mode_changed(self, checked: bool):
        """Handle Quiet Mode checkbox toggle.

        Quiet Mode suppresses all beeps without changing the default beep settings.
        When unchecked, beeps will play according to Settings → Behavior preferences.
        """
        self.config.quiet_mode = checked
        save_config(self.config)

    def _on_auto_paste_toggled(self, checked: bool):
        """Handle Text Injection (auto-paste) checkbox toggle.

        When enabled, automatically simulates Ctrl+V after copying transcription
        to clipboard, pasting the text wherever the cursor is focused.
        """
        self.config.auto_paste = checked
        save_config(self.config)

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

    def _on_favorites_changed(self, favorites=None):
        """Handle changes to favorites in the prompt library or editor."""
        # Refresh the favorites bar if we have one
        if hasattr(self, 'favorites_bar'):
            self.favorites_bar.update_library()

    def _on_prompt_selected_from_bar(self, prompt_id: str):
        """Handle prompt selection from the favorites bar."""
        self.current_prompt_id = prompt_id
        self.config.format_preset = prompt_id
        save_config(self.config)

    def get_selected_microphone_index(self):
        """Get the index of the configured microphone.

        Priority order:
        1. Preferred microphone (if configured and available)
        2. Fallback microphone (if configured and available)
        3. "pulse" (routes through PipeWire/PulseAudio)
        4. "default"
        5. First available device
        """
        devices = self.recorder.get_input_devices()

        # 1. Try preferred microphone first
        if self.config.preferred_mic_name:
            for idx, name in devices:
                if name == self.config.preferred_mic_name:
                    return idx

        # 2. Try fallback microphone
        if self.config.fallback_mic_name:
            for idx, name in devices:
                if name == self.config.fallback_mic_name:
                    return idx

        # 3. Default to "pulse" which routes through PipeWire/PulseAudio
        for idx, name in devices:
            if name == "pulse":
                return idx

        # 4. Fallback to "default" if pulse not available
        for idx, name in devices:
            if name == "default":
                return idx

        # 5. Fall back to first device
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

            # Set microphone from config
            mic_idx = self.get_selected_microphone_index()
            if mic_idx is not None:
                self.recorder.set_device(mic_idx)

            # Play start beep (unless in Quiet Mode)
            feedback = get_feedback()
            feedback.enabled = self.config.beep_on_record and not self.config.quiet_mode
            feedback.play_start_beep()

            self.recorder.start_recording()
            self.record_btn.setText("●")
            self.record_btn.setStyleSheet(self._record_btn_recording_style)
            self.pause_btn.setEnabled(True)
            self.append_btn.setEnabled(False)  # Disable append while recording
            self.stop_btn.setEnabled(True)  # Can stop recording to cache
            self.transcribe_btn.setEnabled(True)  # Can stop and transcribe immediately
            self.transcribe_btn.setStyleSheet(self._transcribe_btn_recording_style)  # Yellow while recording
            self.delete_btn.setEnabled(True)  # Can delete current recording
            self.status_label.setText("Recording...")
            self.status_label.setStyleSheet("color: #dc3545; font-weight: bold;")
            self.timer.start(100)
            # Update tray to recording state
            self._set_tray_state('recording')

    def toggle_pause(self):
        """Toggle pause state."""
        if self.recorder.is_paused:
            self.recorder.resume_recording()
            self.pause_btn.setText("⏸")
            self.status_label.setText("Recording...")
            self.status_label.setStyleSheet("color: #dc3545; font-weight: bold;")
        else:
            self.recorder.pause_recording()
            self.pause_btn.setText("▶")
            self.status_label.setText("Paused")
            self.status_label.setStyleSheet("color: #ffc107; font-weight: bold;")

    def handle_stop_button(self):
        """Stop recording and cache audio without transcribing."""
        if not self.recorder.is_recording:
            return

        # Play stop beep (unless in Quiet Mode)
        feedback = get_feedback()
        feedback.enabled = self.config.beep_on_record and not self.config.quiet_mode
        feedback.play_stop_beep()

        self.timer.stop()
        audio_data = self.recorder.stop_recording()

        # Add to accumulated segments
        self.accumulated_segments.append(audio_data)
        audio_info = get_audio_info(audio_data)
        self.accumulated_duration += audio_info["duration_seconds"]
        self._update_segment_indicator()

        # Mark that we have cached audio
        self.has_cached_audio = True

        # Update UI to "stopped with cached audio" state
        self.record_btn.setText("●")
        self.record_btn.setStyleSheet(self._record_btn_idle_style)
        self.record_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.pause_btn.setText("⏸")
        self.stop_btn.setEnabled(False)  # Can't stop when not recording
        self.append_btn.setEnabled(True)  # Can append more clips
        self.transcribe_btn.setEnabled(True)  # Can transcribe cached audio
        self.transcribe_btn.setStyleSheet(self._transcribe_btn_idle_style)  # Green when cached
        self.delete_btn.setEnabled(True)  # Can delete cached audio
        self.status_label.setText(f"Stopped ({len(self.accumulated_segments)} clip{'s' if len(self.accumulated_segments) > 1 else ''})")
        self.status_label.setStyleSheet("color: #ffc107; font-weight: bold;")

        # Update tray to stopped state
        self._set_tray_state('stopped')

    def append_to_transcription(self):
        """Start a new recording that will be appended to cached audio."""
        if self.recorder.is_recording:
            return  # Already recording

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
        self.status_label.setStyleSheet("color: #007bff; font-weight: bold;")
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
        self.pause_btn.setEnabled(False)
        self.append_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.transcribe_btn.setEnabled(False)
        self.delete_btn.setEnabled(False)
        self.status_label.setText("Transcribing...")
        self.status_label.setStyleSheet("color: #007bff; font-weight: bold;")

        # Update tray to transcribing state
        self._set_tray_state('transcribing')

        # Get API key for selected provider
        provider = self.config.selected_provider
        if provider == "gemini":
            api_key = self.config.gemini_api_key
            model = self.config.gemini_model
        else:  # openrouter
            api_key = self.config.openrouter_api_key
            model = self.config.openrouter_model

        if not api_key:
            QMessageBox.warning(
                self,
                "Missing API Key",
                f"Please set your {provider.title()} API key in Settings.",
            )
            self.reset_ui()
            return

        # Start transcription worker
        cleanup_prompt = build_cleanup_prompt(self.config)
        self.worker = TranscriptionWorker(
            audio_data,
            provider,
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
        # If currently recording, stop it first
        if self.recorder.is_recording:
            # Play stop beep (unless in Quiet Mode)
            feedback = get_feedback()
            feedback.enabled = self.config.beep_on_record and not self.config.quiet_mode
            feedback.play_stop_beep()

            self.timer.stop()
            audio_data = self.recorder.stop_recording()

            # If we have accumulated segments, add current recording and combine all
            if self.accumulated_segments:
                self.accumulated_segments.append(audio_data)
                self.status_label.setText("Combining clips...")
                self.status_label.setStyleSheet("color: #007bff; font-weight: bold;")
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
        self.record_btn.setEnabled(False)
        self.pause_btn.setEnabled(False)
        self.append_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.transcribe_btn.setEnabled(False)
        self.delete_btn.setEnabled(False)
        self.status_label.setText("Transcribing...")
        self.status_label.setStyleSheet("color: #007bff; font-weight: bold;")

        # Update tray to transcribing state
        self._set_tray_state('transcribing')

        # Get API key for selected provider
        provider = self.config.selected_provider
        if provider == "gemini":
            api_key = self.config.gemini_api_key
            model = self.config.gemini_model
        else:  # openrouter
            api_key = self.config.openrouter_api_key
            model = self.config.openrouter_model

        if not api_key:
            QMessageBox.warning(
                self,
                "Missing API Key",
                f"Please set your {provider.title()} API key in Settings.",
            )
            self.reset_ui()
            return

        # Start transcription worker (VAD + compression + transcription all in background)
        cleanup_prompt = build_cleanup_prompt(self.config)
        self.worker = TranscriptionWorker(
            audio_data,
            provider,
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

    def on_worker_status(self, status: str):
        """Handle worker status updates."""
        self.status_label.setText(status)
        self.status_label.setStyleSheet("color: #007bff; font-weight: bold;")

    def on_vad_complete(self, orig_dur: float, vad_dur: float):
        """Handle VAD processing complete - store duration for database."""
        self.last_vad_duration = vad_dur

    def on_transcription_complete(self, result: TranscriptionResult):
        """Handle completed transcription."""
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
            # Replace text (normal mode)
            self.text_output.setMarkdown(result.text)

        # Get provider/model info
        provider = self.config.selected_provider
        if provider == "gemini":
            model = self.config.gemini_model
        else:  # openrouter
            model = self.config.openrouter_model

        # Determine cost: use actual cost from OpenRouter, or estimate for others
        final_cost = 0.0
        if result.actual_cost is not None:
            # Use actual cost from OpenRouter API
            final_cost = result.actual_cost
        elif result.input_tokens > 0 or result.output_tokens > 0:
            # Fall back to estimated cost
            tracker = get_tracker()
            final_cost = tracker.record_usage(provider, model, result.input_tokens, result.output_tokens)

        self._update_cost_display()

        # Get inference time from worker
        inference_time_ms = self.worker.inference_time_ms if self.worker else 0

        # Optionally archive audio
        audio_file_path = None
        if self.config.store_audio and hasattr(self, 'last_audio_data'):
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            audio_filename = f"{timestamp}.opus"
            audio_path = AUDIO_ARCHIVE_DIR / audio_filename
            if archive_audio(self.last_audio_data, str(audio_path)):
                audio_file_path = str(audio_path)

        # Save to database
        audio_duration = getattr(self, 'last_audio_duration', None)
        vad_duration = getattr(self, 'last_vad_duration', None)
        prompt_length = len(self.worker.prompt) if self.worker else 0
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
        )

        # Clear stored audio data
        if hasattr(self, 'last_audio_data'):
            del self.last_audio_data
        if hasattr(self, 'last_audio_duration'):
            del self.last_audio_duration
        if hasattr(self, 'last_vad_duration'):
            del self.last_vad_duration

        # Auto-copy to clipboard (using wl-copy for Wayland)
        self._copy_to_clipboard_wayland(result.text)

        # Auto-paste if enabled (inject text at cursor using ydotool)
        if self.config.auto_paste:
            self._paste_wayland()

        # Play clipboard beep (unless in Quiet Mode)
        feedback = get_feedback()
        feedback.enabled = self.config.beep_on_clipboard and not self.config.quiet_mode
        feedback.play_clipboard_beep()

        self.reset_ui()

        # Enable append button now that we have a transcription
        self.append_btn.setEnabled(True)

        self.status_label.setText("Copied!")
        self.status_label.setStyleSheet("color: #28a745; font-weight: bold;")

        # Show complete state (green tick) then transition to idle after 3 seconds
        self._set_tray_state('complete')
        QTimer.singleShot(3000, lambda: self._set_tray_state('idle') if self._tray_state == 'complete' else None)

    def on_transcription_error(self, error: str):
        """Handle transcription error."""
        QMessageBox.critical(self, "Transcription Error", error)
        self.reset_ui()
        self._set_tray_state('idle')

    def _update_cost_display(self):
        """No-op: Cost display removed from status bar."""
        pass

    def _on_balance_received(self, credits):
        """No-op: Cost display removed from status bar."""
        pass

    def _update_mic_display(self):
        """Update the microphone display label."""
        display_name, full_name = self._get_active_microphone_name()
        # Limit to 3 words
        words = display_name.split()
        if len(words) > 3:
            display_name = ' '.join(words[:3])
        self.mic_label.setText(display_name)
        self.mic_label.setToolTip(f"Active microphone: {full_name}\nChange in Settings → Audio")

    def _get_active_microphone_name(self) -> tuple[str, str]:
        """Get the name of the currently active microphone.

        Returns:
            Tuple of (display_name, full_name) where display_name may be a
            nickname and full_name is always the device's actual name.
        """
        import subprocess

        # Get the actual device name that will be/is being used
        actual_device_name = None

        # Check which device is actually selected based on config
        devices = self.recorder.get_input_devices()
        device_names = [name for _, name in devices]

        # Priority: preferred > fallback > pulse > default > first
        if self.config.preferred_mic_name and self.config.preferred_mic_name in device_names:
            actual_device_name = self.config.preferred_mic_name
        elif self.config.fallback_mic_name and self.config.fallback_mic_name in device_names:
            actual_device_name = self.config.fallback_mic_name
        elif "pulse" in device_names or "default" in device_names:
            # Query PipeWire/PulseAudio for the actual default source
            try:
                result = subprocess.run(
                    ["pactl", "get-default-source"],
                    capture_output=True, text=True, timeout=2
                )
                if result.returncode == 0:
                    source_name = result.stdout.strip()
                    if source_name:
                        # Get the description for this source
                        desc_result = subprocess.run(
                            ["pactl", "list", "sources"],
                            capture_output=True, text=True, timeout=2
                        )
                        if desc_result.returncode == 0:
                            lines = desc_result.stdout.split('\n')
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

        # Fallback to first device
        if not actual_device_name and devices:
            actual_device_name = devices[0][1]

        if not actual_device_name:
            return ("No microphone found", "No microphone found")

        # Check if the actual device matches preferred or fallback mic
        # If so, return the nickname (if set) as display name
        if actual_device_name == self.config.preferred_mic_name:
            if self.config.preferred_mic_nickname:
                return (self.config.preferred_mic_nickname, actual_device_name)
        elif actual_device_name == self.config.fallback_mic_name:
            if self.config.fallback_mic_nickname:
                return (self.config.fallback_mic_nickname, actual_device_name)

        return (actual_device_name, actual_device_name)

    def _update_model_display(self):
        """Update the model display label."""
        provider, model = self._get_current_model()
        # Get human-readable display name from config
        display_name = get_model_display_name(model, provider)
        # Truncate if too long
        if len(display_name) > 30:
            display_name = display_name[:27] + "..."
        self.model_label.setText(display_name)
        self.model_label.setToolTip(f"Provider: {provider}\nModel: {model}\nChange in Settings → Model")

    def _get_current_model(self) -> tuple[str, str]:
        """Get the currently selected provider and model.

        Returns:
            Tuple of (provider, model).
        """
        provider = self.config.selected_provider
        if provider == "gemini":
            model = self.config.gemini_model
        elif provider == "openrouter":
            model = self.config.openrouter_model
        else:
            model = "unknown"
        return (provider, model)

    def reset_ui(self):
        """Reset UI to initial state.

        Note: Does not change tray state - caller is responsible for setting
        appropriate tray state (idle, complete, etc.) after calling this.
        """
        self.record_btn.setText("●")
        self.record_btn.setStyleSheet(self._record_btn_idle_style)
        self.record_btn.setEnabled(True)
        self.pause_btn.setText("⏸")
        self.pause_btn.setEnabled(False)
        self.append_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.transcribe_btn.setEnabled(False)
        self.transcribe_btn.setStyleSheet(self._transcribe_btn_idle_style)  # Reset to green
        self.delete_btn.setEnabled(False)
        self.duration_label.setText("0:00")
        self.status_label.setText("Ready")
        self.status_label.setStyleSheet("color: #666;")

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

        # Play stop beep when discarding (unless in Quiet Mode)
        if self.recorder.is_recording or self.recorder.is_paused:
            feedback = get_feedback()
            feedback.enabled = self.config.beep_on_record and not self.config.quiet_mode
            feedback.play_stop_beep()

        self.timer.stop()
        if self.recorder.is_recording or self.recorder.is_paused:
            self.recorder.stop_recording()
        self.recorder.clear()

        # Clear accumulated segments
        self.accumulated_segments = []
        self.accumulated_duration = 0.0
        self._update_segment_indicator()

        # Reset state flags
        self.append_mode = False
        self.has_cached_audio = False

        self.reset_ui()
        self._set_tray_state('idle')

    def update_duration(self):
        """Update the duration display."""
        duration = self.recorder.get_duration()
        mins = int(duration // 60)
        secs = int(duration % 60)
        self.duration_label.setText(f"{mins}:{secs:02d}")

    def clear_transcription(self):
        """Clear the transcription text."""
        self.text_output.clear()
        self.word_count_label.setText("")
        # Disable append button when clearing
        self.append_btn.setEnabled(False)
        self.append_mode = False

    def _copy_to_clipboard_wayland(self, text: str):
        """Copy text to clipboard using wl-copy (Wayland-native)."""
        import subprocess
        try:
            # Use wl-copy for reliable Wayland clipboard
            process = subprocess.Popen(
                ["wl-copy"],
                stdin=subprocess.PIPE,
                stderr=subprocess.DEVNULL
            )
            process.communicate(input=text.encode("utf-8"))
        except FileNotFoundError:
            # Fallback to Qt clipboard if wl-copy not available
            clipboard = QApplication.clipboard()
            clipboard.setText(text)
        except Exception:
            # Fallback to Qt clipboard on any error
            clipboard = QApplication.clipboard()
            clipboard.setText(text)

    def _paste_wayland(self):
        """Simulate Ctrl+V paste using ydotool (Wayland-compatible).

        This uses ydotool to inject keyboard input at the uinput level,
        which works on Wayland where xdotool cannot. Requires the user
        to be in the 'input' group or have appropriate permissions.

        Falls back silently if ydotool is not available.
        """
        import subprocess
        try:
            # Small delay to ensure clipboard is ready
            subprocess.run(
                ["ydotool", "key", "--delay", "50", "ctrl+v"],
                check=True,
                capture_output=True,
                timeout=2
            )
        except FileNotFoundError:
            # ydotool not installed - fail silently
            print("Warning: ydotool not found for auto-paste. Install with: sudo apt install ydotool")
        except subprocess.TimeoutExpired:
            print("Warning: ydotool paste timed out")
        except subprocess.CalledProcessError as e:
            print(f"Warning: ydotool paste failed: {e}")
        except Exception as e:
            print(f"Warning: Auto-paste failed: {e}")

    def copy_to_clipboard(self):
        """Copy transcription to clipboard."""
        text = self.text_output.toPlainText()
        if text:
            self._copy_to_clipboard_wayland(text)

            # Don't play beep here - only play when transcription first arrives
            self.status_label.setText("Copied!")
            self.status_label.setStyleSheet("color: #28a745;")
            QTimer.singleShot(2000, lambda: self.status_label.setText("Ready"))
            QTimer.singleShot(2000, lambda: self.status_label.setStyleSheet("color: #666;"))

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

        # Get API key for selected provider
        provider = self.config.selected_provider
        if provider == "gemini":
            api_key = self.config.gemini_api_key
            model = self.config.gemini_model
        else:  # openrouter
            api_key = self.config.openrouter_api_key
            model = self.config.openrouter_model

        if not api_key:
            QMessageBox.warning(
                self,
                "Missing API Key",
                f"Please set your {provider.title()} API key in Settings.",
            )
            return

        # Disable UI during rewrite
        self.rewrite_btn.setEnabled(False)
        self.download_btn.setEnabled(False)
        self.status_label.setText("Rewriting...")
        self.status_label.setStyleSheet("color: #007bff; font-weight: bold;")

        # Start rewrite worker
        self.rewrite_worker = RewriteWorker(
            text,
            instruction,
            provider,
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
        provider = self.config.selected_provider
        if provider == "gemini":
            model = self.config.gemini_model
        else:  # openrouter
            model = self.config.openrouter_model

        # Determine cost
        final_cost = 0.0
        if result.actual_cost is not None:
            final_cost = result.actual_cost
        elif result.input_tokens > 0 or result.output_tokens > 0:
            tracker = get_tracker()
            final_cost = tracker.record_usage(provider, model, result.input_tokens, result.output_tokens)

        self._update_cost_display()

        # Get inference time from worker
        inference_time_ms = self.rewrite_worker.inference_time_ms if self.rewrite_worker else 0

        # Save to database
        db = get_db()
        db.save_transcription(
            provider=provider,
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

        # Re-enable buttons
        self.rewrite_btn.setEnabled(True)
        self.download_btn.setEnabled(True)
        self.status_label.setText("Rewrite complete!")
        self.status_label.setStyleSheet("color: #28a745; font-weight: bold;")
        QTimer.singleShot(2000, lambda: self.status_label.setText("Ready"))
        QTimer.singleShot(2000, lambda: self.status_label.setStyleSheet("color: #666;"))

    def on_rewrite_error(self, error: str):
        """Handle rewrite error."""
        QMessageBox.critical(self, "Rewrite Error", error)
        self.rewrite_btn.setEnabled(True)
        self.download_btn.setEnabled(True)
        self.status_label.setText("Ready")
        self.status_label.setStyleSheet("color: #666;")

    def download_transcript(self):
        """Download transcript with AI-generated title."""
        text = self.text_output.toPlainText()
        if not text:
            return

        # Get API key for Gemini (always use Gemini for title generation)
        api_key = self.config.gemini_api_key
        if not api_key:
            # Fallback: use manual filename if no Gemini key
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"transcript_{timestamp}.md"
            self._save_transcript_to_file(filename, text)
            return

        # Disable button during title generation
        self.download_btn.setEnabled(False)
        self.status_label.setText("Generating title...")
        self.status_label.setStyleSheet("color: #007bff; font-weight: bold;")

        # Start title generation worker
        self.title_worker = TitleGeneratorWorker(
            text,
            "gemini",
            api_key,
            "gemini-2.0-flash-lite",  # Use fast, cheap model for titles
        )
        self.title_worker.finished.connect(self.on_title_generated)
        self.title_worker.error.connect(self.on_title_error)
        self.title_worker.start()

    def on_title_generated(self, title: str):
        """Handle generated title and download file."""
        text = self.text_output.toPlainText()
        filename = f"{title}.md"
        self._save_transcript_to_file(filename, text)

        # Re-enable button
        self.download_btn.setEnabled(True)
        self.status_label.setText("Downloaded!")
        self.status_label.setStyleSheet("color: #28a745; font-weight: bold;")
        QTimer.singleShot(2000, lambda: self.status_label.setText("Ready"))
        QTimer.singleShot(2000, lambda: self.status_label.setStyleSheet("color: #666;"))

    def on_title_error(self, error: str):
        """Handle title generation error - fall back to timestamp."""
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        text = self.text_output.toPlainText()
        filename = f"transcript_{timestamp}.md"
        self._save_transcript_to_file(filename, text)

        # Re-enable button
        self.download_btn.setEnabled(True)
        self.status_label.setText("Downloaded (timestamp)")
        self.status_label.setStyleSheet("color: #28a745; font-weight: bold;")
        QTimer.singleShot(2000, lambda: self.status_label.setText("Ready"))
        QTimer.singleShot(2000, lambda: self.status_label.setStyleSheet("color: #666;"))

    def _save_transcript_to_file(self, filename: str, text: str):
        """Save transcript to Downloads folder with given filename."""
        from pathlib import Path
        import os

        # Get Downloads folder
        downloads_dir = Path.home() / "Downloads"
        file_path = downloads_dir / filename

        # Save file
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(text)
            print(f"Saved to: {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Download Error", f"Failed to save file: {e}")

    def show_settings(self):
        """Show settings dialog."""
        # Create dialog if it doesn't exist
        if self.settings_dialog is None:
            self.settings_dialog = SettingsDialog(self.config, self.recorder, self)
            # Connect to settings_closed signal to sync quiet mode checkbox
            self.settings_dialog.settings_closed.connect(self._sync_quiet_mode_checkbox)

        # Refresh and show
        self.settings_dialog.refresh()
        self.settings_dialog.show()
        self.settings_dialog.raise_()
        self.settings_dialog.activateWindow()

    def _sync_quiet_mode_checkbox(self):
        """Sync the toggle checkboxes state with current config.

        Called when settings dialog is closed. Ensures consistency if
        settings are modified in the Settings → Behavior tab.
        """
        # Block signals to prevent triggering the toggle handlers
        self.quiet_mode_checkbox.blockSignals(True)
        self.quiet_mode_checkbox.setChecked(self.config.quiet_mode)
        self.quiet_mode_checkbox.blockSignals(False)

        self.auto_paste_cb.blockSignals(True)
        self.auto_paste_cb.setChecked(self.config.auto_paste)
        self.auto_paste_cb.blockSignals(False)

        # Update status bar displays in case they changed
        self._update_mic_display()
        self._update_model_display()

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
        """Show and raise the window."""
        self.show()
        self.raise_()
        self.activateWindow()

    def on_tray_activated(self, reason):
        """Handle tray icon activation based on current state."""
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self._tray_state == 'recording':
                # Clicking during recording stops it and enters stopped state
                self._tray_stop_recording()
            elif self._tray_state == 'stopped':
                # In stopped state, show window so user can decide
                self.show_window()
            else:
                # For idle, transcribing, complete: toggle window visibility
                if self.isVisible():
                    self.hide()
                else:
                    self.show_window()

    def _set_tray_state(self, state: str):
        """Update tray icon and menu based on state.

        States: 'idle', 'recording', 'stopped', 'transcribing', 'complete'
        """
        self._tray_state = state
        # Update icon and status label
        if state == 'idle':
            self.tray.setIcon(self._tray_icon_idle)
            self.status_label.setText("● Ready")
            self.status_label.setStyleSheet("""
                QLabel {
                    color: #6c757d;
                    font-weight: bold;
                    font-size: 13px;
                    padding: 0 8px;
                }
            """)
        elif state == 'recording':
            self.tray.setIcon(self._tray_icon_recording)
            self.status_label.setText("● Recording")
            self.status_label.setStyleSheet("""
                QLabel {
                    color: #dc3545;
                    font-weight: bold;
                    font-size: 13px;
                    padding: 0 8px;
                }
            """)
        elif state == 'stopped':
            self.tray.setIcon(self._tray_icon_stopped)
            self.status_label.setText("⏸ Stopped")
            self.status_label.setStyleSheet("""
                QLabel {
                    color: #ffc107;
                    font-weight: bold;
                    font-size: 13px;
                    padding: 0 8px;
                }
            """)
        elif state == 'transcribing':
            self.tray.setIcon(self._tray_icon_transcribing)
            self.status_label.setText("⟳ Transcribing")
            self.status_label.setStyleSheet("""
                QLabel {
                    color: #007bff;
                    font-weight: bold;
                    font-size: 13px;
                    padding: 0 8px;
                }
            """)
        elif state == 'complete':
            self.tray.setIcon(self._tray_icon_complete)
            self.status_label.setText("✓ Complete")
            self.status_label.setStyleSheet("""
                QLabel {
                    color: #28a745;
                    font-weight: bold;
                    font-size: 13px;
                    padding: 0 8px;
                }
            """)
        # Update menu
        self._update_tray_menu()

    def _update_tray_menu(self):
        """Rebuild tray menu based on current state."""
        self._tray_menu.clear()

        # Show action is always available
        self._tray_menu.addAction(self._tray_show_action)
        self._tray_menu.addSeparator()

        if self._tray_state == 'idle' or self._tray_state == 'complete':
            self._tray_menu.addAction(self._tray_record_action)
        elif self._tray_state == 'recording':
            self._tray_menu.addAction(self._tray_stop_action)
        elif self._tray_state == 'stopped':
            self._tray_menu.addAction(self._tray_transcribe_action)
            self._tray_menu.addAction(self._tray_resume_action)
            self._tray_menu.addAction(self._tray_delete_action)
        # transcribing state: no recording actions available

        self._tray_menu.addSeparator()
        self._tray_menu.addAction(self._tray_quit_action)

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
        if self._tray_state != 'stopped':
            return

        # Transcribe cached audio
        if self.has_cached_audio:
            self.transcribe_cached_audio()
        elif self.recorder.is_recording:
            # Fallback in case state is inconsistent
            self.stop_and_transcribe()

    def _tray_delete_stopped(self):
        """Delete the stopped recording from tray menu."""
        if self._tray_state != 'stopped':
            return
        self.delete_recording()

    def _tray_resume_recording(self):
        """Append more audio from stopped state via tray menu."""
        if self._tray_state != 'stopped':
            return

        # Use append functionality to record more clips
        self.append_to_transcription()

    def quit_app(self):
        """Quit the application."""
        self.hotkey_listener.stop()
        self.recorder.cleanup()
        save_config(self.config)
        QApplication.quit()

    def closeEvent(self, event):
        """Handle window close - minimize to tray instead."""
        event.ignore()
        self.hide()
        self.tray.showMessage(
            "Voice Notepad",
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
