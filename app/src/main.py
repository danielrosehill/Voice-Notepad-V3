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
from PyQt6.QtGui import QIcon, QAction, QFont, QClipboard, QShortcut, QKeySequence
from PyQt6.QtWidgets import QCompleter

from .config import (
    Config, load_config, save_config, load_env_keys,
    GEMINI_MODELS, OPENAI_MODELS, MISTRAL_MODELS, OPENROUTER_MODELS,
    MODEL_TIERS, FOUNDATION_PROMPT_COMPONENTS, OPTIONAL_PROMPT_COMPONENTS, build_cleanup_prompt,
    FORMAT_TEMPLATES, FORMAT_DISPLAY_NAMES, FORMALITY_DISPLAY_NAMES, VERBOSITY_DISPLAY_NAMES, EMAIL_SIGNOFFS,
)
from .audio_recorder import AudioRecorder
from .transcription import get_client, TranscriptionResult
from .audio_processor import compress_audio_for_api, archive_audio, get_audio_info, combine_wav_segments
from .markdown_widget import MarkdownTextWidget
from .database_mongo import get_db, AUDIO_ARCHIVE_DIR
from .vad_processor import remove_silence, is_vad_available
from .hotkeys import (
    GlobalHotkeyListener,
    HotkeyCapture,
    SUGGESTED_HOTKEYS,
    HOTKEY_DESCRIPTIONS,
    HOTKEY_MODE_NAMES,
    HOTKEY_MODE_DESCRIPTIONS,
)
from .cost_tracker import get_tracker
from .history_widget import HistoryWidget
from .analytics_widget import AnalyticsWidget
from .settings_widget import SettingsWidget
from .about_widget import AboutWidget
from .audio_feedback import get_feedback
from .file_transcription_widget import FileTranscriptionWidget
from .mic_naming_ai import MicrophoneNamingAI
from .prompt_options_dialog import PromptOptionsDialog
from .format_manager_dialog import FormatManagerDialog
from .stack_manager_dialog import StackManagerDialog
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

        # Set window title (add DEV suffix if in dev mode)
        title = "Voice Notepad"
        if os.environ.get("VOICE_NOTEPAD_DEV_MODE") == "1":
            title += " (DEV)"
        self.setWindowTitle(title)
        self.setMinimumSize(480, 550)
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
            "open router": "or_icon.png",
            "gemini": "gemini_icon.png",
            "google": "gemini_icon.png",
            "openai": "openai_icon.png",
            "mistral": "mistral_icon.png",
        }
        icon_filename = icon_map.get(provider.lower(), "")
        if icon_filename:
            icon_path = icons_dir / icon_filename
            if icon_path.exists():
                return QIcon(str(icon_path))
        return QIcon()  # Return empty icon if not found

    def _get_model_icon(self, model_id: str) -> QIcon:
        """Get the icon for a model based on its originator (not inference provider)."""
        icons_dir = Path(__file__).parent / "icons"
        model_lower = model_id.lower()

        # Determine model originator from model ID
        if model_lower.startswith("google/") or model_lower.startswith("gemini"):
            icon_filename = "gemini_icon.png"
        elif model_lower.startswith("openai/") or model_lower.startswith("gpt"):
            icon_filename = "openai_icon.png"
        elif model_lower.startswith("mistralai/") or model_lower.startswith("voxtral"):
            icon_filename = "mistral_icon.png"
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
        self.record_btn.setText("● Record")
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
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(12, 12, 12, 12)

        # Header with settings
        header = QHBoxLayout()
        header.addStretch()

        settings_btn = QPushButton("Settings")
        settings_btn.clicked.connect(self.show_settings)
        header.addWidget(settings_btn)
        main_layout.addLayout(header)

        # Status indicator (tally light)
        self.status_indicator = QLabel("● READY")
        self.status_indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_indicator.setStyleSheet("""
            QLabel {
                background-color: #f8f9fa;
                color: #6c757d;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 13px;
                border: 2px solid #dee2e6;
            }
        """)
        main_layout.addWidget(self.status_indicator)

        # Main tabs
        self.tabs = QTabWidget()

        # Record tab
        record_tab = QWidget()
        layout = QVBoxLayout(record_tab)
        layout.setSpacing(12)
        layout.setContentsMargins(8, 12, 8, 8)

        # System Prompt Configuration Button (opens modal dialog)
        prompt_config_layout = QHBoxLayout()

        configure_prompt_btn = QPushButton("⚙ Configure System Prompt...")
        configure_prompt_btn.setMinimumHeight(34)
        configure_prompt_btn.setToolTip(
            "Configure detailed system prompt options:\n"
            "• Optional enhancements (filler words, punctuation, etc.)\n"
            "• Format settings and tone\n"
            "• Verbosity reduction\n"
            "• Email signature settings"
        )
        configure_prompt_btn.setStyleSheet("""
            QPushButton {
                background-color: #f8f9fa;
                color: #495057;
                border: 1px solid #ced4da;
                border-radius: 4px;
                font-size: 12px;
                padding: 6px 16px;
            }
            QPushButton:hover {
                background-color: #e9ecef;
                border-color: #adb5bd;
            }
        """)
        configure_prompt_btn.clicked.connect(self._open_prompt_options_dialog)
        prompt_config_layout.addWidget(configure_prompt_btn)

        # Indicator showing active enhancements
        self.prompt_indicator_label = QLabel()
        self.prompt_indicator_label.setStyleSheet("color: #6c757d; font-size: 11px;")
        self._update_prompt_indicator()
        prompt_config_layout.addWidget(self.prompt_indicator_label)

        prompt_config_layout.addStretch()
        layout.addLayout(prompt_config_layout)

        # Prompt Stacks Section
        prompt_stack_header = QHBoxLayout()
        prompt_stack_label = QLabel("Advanced: Prompt Stacks")
        prompt_stack_label.setStyleSheet("font-weight: bold; font-size: 12px; color: #495057;")
        prompt_stack_header.addWidget(prompt_stack_label)

        # Enable/disable checkbox
        self.use_prompt_stacks_checkbox = QCheckBox("Enable")
        self.use_prompt_stacks_checkbox.setChecked(self.config.use_prompt_stacks)
        self.use_prompt_stacks_checkbox.stateChanged.connect(self._on_use_prompt_stacks_changed)
        prompt_stack_header.addWidget(self.use_prompt_stacks_checkbox)

        prompt_stack_header.addSpacing(10)

        # Manage Stacks button
        manage_stacks_btn = QPushButton("⚙️ Manage Stacks...")
        manage_stacks_btn.setFixedHeight(28)
        manage_stacks_btn.setStyleSheet("""
            QPushButton {
                background-color: #f8f9fa;
                color: #495057;
                border: 1px solid #ced4da;
                border-radius: 4px;
                font-size: 11px;
                padding: 4px 12px;
            }
            QPushButton:hover {
                background-color: #e9ecef;
                border-color: #adb5bd;
            }
        """)
        manage_stacks_btn.clicked.connect(self._open_stack_manager)
        prompt_stack_header.addWidget(manage_stacks_btn)

        prompt_stack_header.addStretch()
        layout.addLayout(prompt_stack_header)

        # Quick format selector with help text
        format_section_layout = QVBoxLayout()
        format_section_layout.setSpacing(8)

        # Help text explaining the format system
        format_help = QLabel(
            "<b>Quick Formats:</b> Pre-configured output styles for common use cases. "
            "These formats work with the system prompt (configured above) to shape your transcription. "
            "For more formats, click 'Manage Formats' or use 'Prompt Stacks' for advanced combinations."
        )
        format_help.setWordWrap(True)
        format_help.setStyleSheet("color: #666; font-size: 11px; padding: 4px 0; margin-bottom: 4px;")
        format_section_layout.addWidget(format_help)

        # Quick format selector buttons
        format_quick_select_layout = QHBoxLayout()
        format_quick_select_layout.setSpacing(8)

        format_label = QLabel("Format:")
        format_label.setStyleSheet("font-weight: bold; color: #495057;")
        format_quick_select_layout.addWidget(format_label)

        # Create button group for mutual exclusivity
        self.format_button_group = QButtonGroup(self)

        # General button (default)
        self.general_format_btn = QPushButton("General")
        self.general_format_btn.setCheckable(True)
        self.general_format_btn.setMinimumHeight(32)
        self.general_format_btn.clicked.connect(lambda: self._set_quick_format("general"))
        self.format_button_group.addButton(self.general_format_btn)
        format_quick_select_layout.addWidget(self.general_format_btn)

        # Verbatim button
        self.verbatim_format_btn = QPushButton("Verbatim")
        self.verbatim_format_btn.setCheckable(True)
        self.verbatim_format_btn.setMinimumHeight(32)
        self.verbatim_format_btn.clicked.connect(lambda: self._set_quick_format("verbatim"))
        self.format_button_group.addButton(self.verbatim_format_btn)
        format_quick_select_layout.addWidget(self.verbatim_format_btn)

        # Email button
        self.email_format_btn = QPushButton("Email")
        self.email_format_btn.setCheckable(True)
        self.email_format_btn.setMinimumHeight(32)
        self.email_format_btn.clicked.connect(lambda: self._set_quick_format("email"))
        self.format_button_group.addButton(self.email_format_btn)
        format_quick_select_layout.addWidget(self.email_format_btn)

        # AI Prompt button
        self.ai_prompt_format_btn = QPushButton("AI Prompt")
        self.ai_prompt_format_btn.setCheckable(True)
        self.ai_prompt_format_btn.setMinimumHeight(32)
        self.ai_prompt_format_btn.clicked.connect(lambda: self._set_quick_format("ai_prompt"))
        self.format_button_group.addButton(self.ai_prompt_format_btn)
        format_quick_select_layout.addWidget(self.ai_prompt_format_btn)

        # System Prompt button
        self.system_prompt_format_btn = QPushButton("System Prompt")
        self.system_prompt_format_btn.setCheckable(True)
        self.system_prompt_format_btn.setMinimumHeight(32)
        self.system_prompt_format_btn.clicked.connect(lambda: self._set_quick_format("system_prompt"))
        self.format_button_group.addButton(self.system_prompt_format_btn)
        format_quick_select_layout.addWidget(self.system_prompt_format_btn)

        # Dev Prompt button
        self.dev_prompt_format_btn = QPushButton("Dev Prompt")
        self.dev_prompt_format_btn.setCheckable(True)
        self.dev_prompt_format_btn.setMinimumHeight(32)
        self.dev_prompt_format_btn.clicked.connect(lambda: self._set_quick_format("dev_prompt"))
        self.format_button_group.addButton(self.dev_prompt_format_btn)
        format_quick_select_layout.addWidget(self.dev_prompt_format_btn)

        # Tech Docs button
        self.tech_docs_format_btn = QPushButton("Tech Docs")
        self.tech_docs_format_btn.setCheckable(True)
        self.tech_docs_format_btn.setMinimumHeight(32)
        self.tech_docs_format_btn.clicked.connect(lambda: self._set_quick_format("tech_docs"))
        self.format_button_group.addButton(self.tech_docs_format_btn)
        format_quick_select_layout.addWidget(self.tech_docs_format_btn)

        # To-Do button
        self.todo_format_btn = QPushButton("To-Do")
        self.todo_format_btn.setCheckable(True)
        self.todo_format_btn.setMinimumHeight(32)
        self.todo_format_btn.clicked.connect(lambda: self._set_quick_format("todo"))
        self.format_button_group.addButton(self.todo_format_btn)
        format_quick_select_layout.addWidget(self.todo_format_btn)

        format_quick_select_layout.addStretch()

        # Manage Formats button
        manage_formats_btn = QPushButton("⚙️ Manage Formats...")
        manage_formats_btn.setFixedHeight(32)
        manage_formats_btn.setStyleSheet("""
            QPushButton {
                background-color: #f8f9fa;
                color: #495057;
                border: 2px solid #ced4da;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
                padding: 4px 12px;
            }
            QPushButton:hover {
                background-color: #e9ecef;
                border-color: #adb5bd;
            }
        """)
        manage_formats_btn.clicked.connect(self._open_format_manager)
        format_quick_select_layout.addWidget(manage_formats_btn)

        # Style the format buttons
        format_button_style = """
            QPushButton {
                background-color: #e9ecef;
                color: #495057;
                border: 2px solid #ced4da;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
                padding: 4px 12px;
            }
            QPushButton:hover {
                background-color: #dee2e6;
                border-color: #adb5bd;
            }
            QPushButton:checked {
                background-color: #007bff;
                color: white;
                border-color: #007bff;
            }
        """
        self.general_format_btn.setStyleSheet(format_button_style)
        self.verbatim_format_btn.setStyleSheet(format_button_style)
        self.email_format_btn.setStyleSheet(format_button_style)
        self.ai_prompt_format_btn.setStyleSheet(format_button_style)
        self.system_prompt_format_btn.setStyleSheet(format_button_style)
        self.dev_prompt_format_btn.setStyleSheet(format_button_style)
        self.tech_docs_format_btn.setStyleSheet(format_button_style)
        self.todo_format_btn.setStyleSheet(format_button_style)

        # Set initial button state based on config
        if self.config.format_preset == "verbatim":
            self.verbatim_format_btn.setChecked(True)
        elif self.config.format_preset == "email":
            self.email_format_btn.setChecked(True)
        elif self.config.format_preset == "ai_prompt":
            self.ai_prompt_format_btn.setChecked(True)
        elif self.config.format_preset == "system_prompt":
            self.system_prompt_format_btn.setChecked(True)
        elif self.config.format_preset == "dev_prompt":
            self.dev_prompt_format_btn.setChecked(True)
        elif self.config.format_preset == "tech_docs":
            self.tech_docs_format_btn.setChecked(True)
        elif self.config.format_preset == "todo":
            self.todo_format_btn.setChecked(True)
        else:
            self.general_format_btn.setChecked(True)

        format_section_layout.addLayout(format_quick_select_layout)
        layout.addLayout(format_section_layout)

        layout.addSpacing(8)

        # Recording status and duration
        status_layout = QHBoxLayout()
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #666;")
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()

        self.duration_label = QLabel("0:00")
        self.duration_label.setFont(QFont("Monospace", 12))
        status_layout.addWidget(self.duration_label)

        self.segment_label = QLabel("")
        self.segment_label.setStyleSheet("color: #17a2b8; font-weight: bold;")
        status_layout.addWidget(self.segment_label)

        layout.addLayout(status_layout)

        # Recording controls
        controls = QHBoxLayout()
        controls.setSpacing(8)

        self.record_btn = QPushButton("● Record")
        self.record_btn.setMinimumHeight(45)
        self.record_btn.setToolTip(
            "Start a new recording.\n"
            "Clears any cached audio and begins fresh."
        )
        # Store styles for different states
        self._record_btn_idle_style = """
            QPushButton {
                background-color: #dc3545;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
        """
        self._record_btn_recording_style = """
            QPushButton {
                background-color: #ff0000;
                color: white;
                border: 3px solid #ff6666;
                border-radius: 6px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #cc0000;
            }
        """
        self.record_btn.setStyleSheet(self._record_btn_idle_style)
        self.record_btn.clicked.connect(self.toggle_recording)
        controls.addWidget(self.record_btn)

        self.pause_btn = QPushButton("Pause")
        self.pause_btn.setMinimumHeight(45)
        self.pause_btn.setEnabled(False)
        self.pause_btn.setToolTip(
            "Pause/resume the current recording.\n"
            "Only available while recording is active."
        )
        self.pause_btn.clicked.connect(self.toggle_pause)
        controls.addWidget(self.pause_btn)

        self.append_btn = QPushButton("Append")
        self.append_btn.setMinimumHeight(45)
        self.append_btn.setEnabled(False)
        self.append_btn.setToolTip(
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
                font-size: 14px;
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
        controls.addWidget(self.append_btn)

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setMinimumHeight(45)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setToolTip(
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
                font-size: 14px;
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
        controls.addWidget(self.stop_btn)

        self.transcribe_btn = QPushButton("Transcribe")
        self.transcribe_btn.setMinimumHeight(45)
        self.transcribe_btn.setEnabled(False)
        self.transcribe_btn.setToolTip(
            "Transcribe audio to text.\n"
            "• While recording: Stops and transcribes immediately\n"
            "• After stopping: Transcribes cached audio"
        )
        # Store styles for different states (yellow while recording, green when cached)
        self._transcribe_btn_idle_style = """
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
            QPushButton:disabled {
                background-color: #6c757d;
                color: #aaa;
            }
        """
        self._transcribe_btn_recording_style = """
            QPushButton {
                background-color: #ffc107;
                color: black;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #e0a800;
            }
            QPushButton:disabled {
                background-color: #6c757d;
                color: #aaa;
            }
        """
        self.transcribe_btn.setStyleSheet(self._transcribe_btn_idle_style)
        self.transcribe_btn.clicked.connect(self.stop_and_transcribe)
        controls.addWidget(self.transcribe_btn)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setMinimumHeight(45)
        self.delete_btn.setEnabled(False)
        self.delete_btn.setToolTip(
            "Discard all cached audio without transcribing.\n"
            "Use this to abandon a recording without sending it to the API."
        )
        self.delete_btn.clicked.connect(self.delete_recording)
        controls.addWidget(self.delete_btn)

        layout.addLayout(controls)

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

        # Bottom buttons
        bottom = QHBoxLayout()

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setMinimumHeight(38)
        self.clear_btn.clicked.connect(self.clear_transcription)
        bottom.addWidget(self.clear_btn)

        self.rewrite_btn = QPushButton("✍️ Rewrite")
        self.rewrite_btn.setMinimumHeight(38)
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
        self.save_btn.clicked.connect(self.save_to_file)
        bottom.addWidget(self.save_btn)

        bottom.addStretch()

        self.copy_btn = QPushButton("Copy")
        self.copy_btn.setMinimumHeight(38)
        self.copy_btn.clicked.connect(self.copy_to_clipboard)
        bottom.addWidget(self.copy_btn)

        layout.addLayout(bottom)

        # Bottom status bar: microphone (left) and cost (center)
        status_bar = QHBoxLayout()

        # Microphone info (left)
        self.mic_label = QLabel()
        self.mic_label.setStyleSheet("color: #888; font-size: 10px;")
        status_bar.addWidget(self.mic_label)

        status_bar.addStretch()

        # Cost info (center)
        self.cost_label = QLabel("")
        self.cost_label.setTextFormat(Qt.TextFormat.RichText)
        self.cost_label.setStyleSheet("color: #888; font-size: 11px;")
        self.cost_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_bar.addWidget(self.cost_label)

        status_bar.addStretch()

        layout.addLayout(status_bar)

        # Initialize mic and cost displays
        self._update_mic_display()
        self._update_cost_display()

        self.tabs.addTab(record_tab, "🎙️ Record")

        # File Transcription tab (right after Record)
        self.file_transcription_widget = FileTranscriptionWidget(config=self.config)
        self.tabs.addTab(self.file_transcription_widget, "📁 File")

        # History tab
        self.history_widget = HistoryWidget(config=self.config)
        self.history_widget.transcription_selected.connect(self.on_history_transcription_selected)
        self.tabs.addTab(self.history_widget, "📝 History")

        # Analytics tab (combines Cost + Analysis)
        self.analytics_widget = AnalyticsWidget()
        self.tabs.addTab(self.analytics_widget, "📊 Analytics")

        # Settings tab (consolidates all settings)
        self.settings_widget = SettingsWidget(self.config, self.recorder)
        self.tabs.addTab(self.settings_widget, "⚙️ Settings")

        # About tab
        self.about_widget = AboutWidget()
        self.tabs.addTab(self.about_widget, "ℹ️ About")

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
        self.hotkey_listener = GlobalHotkeyListener()

        # Register configured hotkeys
        self._register_hotkeys()

        # Start listening
        self.hotkey_listener.start()

    def _register_hotkeys(self):
        """Register fixed F-key hotkeys for all actions.

        FIXED F-KEY MAPPING (simple implementation):
        - F15: Toggle recording (start/stop and cache)
        - F16: Tap (same as F15)
        - F17: Transcribe cached audio only
        - F18: Clear cache/delete recording
        - F19: Append (start new recording to append to cache)

        NOTE: Pause key is intentionally NOT registered as pynput can receive
        spurious Key.pause events on some systems (e.g., mouse clicks being
        misinterpreted as pause key presses).
        """
        # Unregister all existing hotkeys first
        for name in ["pause_toggle", "f16_tap", "f17_transcribe", "f18_delete", "f19_append"]:
            self.hotkey_listener.unregister(name)

        # F16: Tap (toggle recording)
        self.hotkey_listener.register(
            "f16_tap",
            "f16",
            lambda: QTimer.singleShot(0, self._hotkey_toggle_recording)
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
        """Handle F15/F16: Toggle recording on/off (caches audio when stopped)."""
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
        # Tabs: 0=Record, 1=File, 2=History, 3=Analytics, 4=Settings, 5=About
        if index == 2:  # History tab
            self.history_widget.refresh()
        elif index == 3:  # Analytics tab
            self.analytics_widget.refresh()
        elif index == 4:  # Settings tab
            self.settings_widget.refresh()
        # Record (0), File (1), About (5) don't need refresh

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

    def _open_prompt_options_dialog(self):
        """Open the prompt options configuration dialog."""
        dialog = PromptOptionsDialog(self.config, self)
        dialog.settings_changed.connect(self._update_prompt_indicator)
        dialog.exec()

    def _update_prompt_indicator(self):
        """Update the indicator showing active prompt enhancements."""
        # Count enabled optional enhancements
        enabled_count = sum(
            1 for field_name, _, _ in OPTIONAL_PROMPT_COMPONENTS
            if getattr(self.config, field_name, False)
        )

        if enabled_count == 0:
            self.prompt_indicator_label.setText("")
        elif enabled_count == 1:
            self.prompt_indicator_label.setText("1 enhancement enabled")
        else:
            self.prompt_indicator_label.setText(f"{enabled_count} enhancements enabled")

    def _open_format_manager(self):
        """Open the format management dialog."""
        from .config import CONFIG_DIR
        dialog = FormatManagerDialog(self.config, self)
        dialog.formats_changed.connect(self._update_prompt_indicator)
        dialog.exec()

    def _open_stack_manager(self):
        """Open the stack management dialog."""
        from .config import CONFIG_DIR
        dialog = StackManagerDialog(CONFIG_DIR, self)
        dialog.stacks_changed.connect(self._update_prompt_indicator)
        dialog.exec()

    def _on_use_prompt_stacks_changed(self):
        """Handle enable/disable of prompt stack system."""
        self.config.use_prompt_stacks = self.use_prompt_stacks_checkbox.isChecked()
        save_config(self.config)

    def _set_quick_format(self, format_key: str):
        """Handle quick format button clicks.

        For 'verbatim' format, also configures optional enhancements to minimal settings.
        """
        # Update the config
        self.config.format_preset = format_key

        # If verbatim is selected, configure minimal optional enhancements
        if format_key == "verbatim":
            # Enable only "follow verbal instructions"
            self.config.prompt_follow_instructions = True

            # Disable all other optional enhancements
            self.config.prompt_add_subheadings = False
            self.config.prompt_markdown_formatting = False
            self.config.prompt_remove_unintentional_dialogue = False
            self.config.prompt_enhancement_enabled = False

            # Update the prompt indicator to reflect changes
            self._update_prompt_indicator()

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

            # Play start beep
            feedback = get_feedback()
            feedback.enabled = self.config.beep_on_record
            feedback.play_start_beep()

            self.recorder.start_recording()
            self.record_btn.setText("● Recording")
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
            self.pause_btn.setText("Pause")
            self.status_label.setText("Recording...")
            self.status_label.setStyleSheet("color: #dc3545; font-weight: bold;")
        else:
            self.recorder.pause_recording()
            self.pause_btn.setText("Resume")
            self.status_label.setText("Paused")
            self.status_label.setStyleSheet("color: #ffc107; font-weight: bold;")

    def handle_stop_button(self):
        """Stop recording and cache audio without transcribing."""
        if not self.recorder.is_recording:
            return

        # Play stop beep
        feedback = get_feedback()
        feedback.enabled = self.config.beep_on_record
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
        self.record_btn.setText("● Record")
        self.record_btn.setStyleSheet(self._record_btn_idle_style)
        self.record_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.pause_btn.setText("Pause")
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
        self.record_btn.setText("Record")
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
        if provider == "openrouter":
            api_key = self.config.openrouter_api_key
            model = self.config.openrouter_model
        elif provider == "gemini":
            api_key = self.config.gemini_api_key
            model = self.config.gemini_model
        elif provider == "openai":
            api_key = self.config.openai_api_key
            model = self.config.openai_model
        else:
            api_key = self.config.mistral_api_key
            model = self.config.mistral_model

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
            # Play stop beep
            feedback = get_feedback()
            feedback.enabled = self.config.beep_on_record
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

        self.record_btn.setText("Record")
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
        if provider == "openrouter":
            api_key = self.config.openrouter_api_key
            model = self.config.openrouter_model
        elif provider == "gemini":
            api_key = self.config.gemini_api_key
            model = self.config.gemini_model
        elif provider == "openai":
            api_key = self.config.openai_api_key
            model = self.config.openai_model
        else:
            api_key = self.config.mistral_api_key
            model = self.config.mistral_model

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
            # Append to existing text - always at the end
            existing_text = self.text_output.toPlainText()
            if existing_text:
                # Add a newline separator if there's existing content
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
        if provider == "openrouter":
            model = self.config.openrouter_model
        elif provider == "gemini":
            model = self.config.gemini_model
        elif provider == "openai":
            model = self.config.openai_model
        else:
            model = self.config.mistral_model

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

        # Play clipboard beep
        feedback = get_feedback()
        feedback.enabled = self.config.beep_on_clipboard
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
        """Update the cost display label with today's spend and trigger async balance fetch."""
        db = get_db()
        today = db.get_cost_today()
        today_cost = today['total_cost']
        count = today['count']

        # Store for balance callback
        self._today_cost = today_cost
        self._today_count = count

        # Build today's cost text immediately (no blocking)
        today_text = ""
        if count > 0:
            today_text = f"Today: ${today_cost:.2f}"

        # Show today's cost immediately
        self.cost_label.setText(today_text)
        self.cost_label.setToolTip(f"Spent today: ${today_cost:.2f}\nTranscriptions: {count}" if count > 0 else "")

        # Trigger async balance fetch for OpenRouter (non-blocking)
        if self.config.openrouter_api_key and self.config.selected_provider == "openrouter":
            try:
                from .openrouter_api import get_openrouter_api
                api = get_openrouter_api(self.config.openrouter_api_key)
                # Async fetch - callback will update display when ready
                api.get_credits_async(lambda credits: self.balance_updated.emit(credits))
            except Exception:
                pass

    def _on_balance_received(self, credits):
        """Handle balance update from async fetch (called on main thread via signal)."""
        if credits is None:
            return

        # Rebuild display with balance info
        today_text = ""
        tooltip_parts = []

        if hasattr(self, '_today_count') and self._today_count > 0:
            today_text = f"Today: ${self._today_cost:.2f}"
            tooltip_parts.append(f"Spent today: ${self._today_cost:.2f}")
            tooltip_parts.append(f"Transcriptions: {self._today_count}")

        balance = credits.balance
        # Format balance: cents if < $1, dollars if >= $1
        if balance < 1.0:
            cents = int(round(balance * 100))
            balance_display = f"({cents} cents)"
        else:
            balance_display = f"(${balance:.1f})"
        # Style with distinctive background
        balance_text = f'<span style="background-color: rgba(100, 149, 237, 0.3); padding: 1px 4px; border-radius: 3px;">{balance_display}</span>'
        tooltip_parts.append(f"\nOpenRouter Balance: ${balance:.2f}")
        tooltip_parts.append(f"Credits: ${credits.total_credits:.2f}")
        tooltip_parts.append(f"Usage: ${credits.total_usage:.2f}")

        # Update display
        parts = [p for p in [today_text, balance_text] if p]
        self.cost_label.setText("  ".join(parts))
        self.cost_label.setToolTip("\n".join(tooltip_parts))

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

    def reset_ui(self):
        """Reset UI to initial state.

        Note: Does not change tray state - caller is responsible for setting
        appropriate tray state (idle, complete, etc.) after calling this.
        """
        self.record_btn.setText("● Record")
        self.record_btn.setStyleSheet(self._record_btn_idle_style)
        self.record_btn.setEnabled(True)
        self.pause_btn.setText("Pause")
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

        # Play stop beep when discarding
        if self.recorder.is_recording or self.recorder.is_paused:
            feedback = get_feedback()
            feedback.enabled = self.config.beep_on_record
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
        if provider == "openrouter":
            api_key = self.config.openrouter_api_key
            model = self.config.openrouter_model
        elif provider == "gemini":
            api_key = self.config.gemini_api_key
            model = self.config.gemini_model
        elif provider == "openai":
            api_key = self.config.openai_api_key
            model = self.config.openai_model
        else:
            api_key = self.config.mistral_api_key
            model = self.config.mistral_model

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
        if provider == "openrouter":
            model = self.config.openrouter_model
        elif provider == "gemini":
            model = self.config.gemini_model
        elif provider == "openai":
            model = self.config.openai_model
        else:
            model = self.config.mistral_model

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
        """Show settings tab."""
        # Switch to Settings tab (index 4)
        self.tabs.setCurrentIndex(4)
        # Show window if minimized
        if self.isMinimized():
            self.showNormal()
        self.raise_()
        self.activateWindow()

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
        # Update icon
        if state == 'idle':
            self.tray.setIcon(self._tray_icon_idle)
            self.status_indicator.setText("● READY")
            self.status_indicator.setStyleSheet("""
                QLabel {
                    background-color: #f8f9fa;
                    color: #6c757d;
                    padding: 8px 16px;
                    border-radius: 4px;
                    font-weight: bold;
                    font-size: 13px;
                    border: 2px solid #dee2e6;
                }
            """)
        elif state == 'recording':
            self.tray.setIcon(self._tray_icon_recording)
            self.status_indicator.setText("● RECORDING")
            self.status_indicator.setStyleSheet("""
                QLabel {
                    background-color: #f8d7da;
                    color: #dc3545;
                    padding: 8px 16px;
                    border-radius: 4px;
                    font-weight: bold;
                    font-size: 13px;
                    border: 2px solid #dc3545;
                }
            """)
        elif state == 'stopped':
            self.tray.setIcon(self._tray_icon_stopped)
            self.status_indicator.setText("⏸ PAUSED")
            self.status_indicator.setStyleSheet("""
                QLabel {
                    background-color: #fff3cd;
                    color: #ffc107;
                    padding: 8px 16px;
                    border-radius: 4px;
                    font-weight: bold;
                    font-size: 13px;
                    border: 2px solid #ffc107;
                }
            """)
        elif state == 'transcribing':
            self.tray.setIcon(self._tray_icon_transcribing)
            self.status_indicator.setText("⟳ TRANSCRIBING")
            self.status_indicator.setStyleSheet("""
                QLabel {
                    background-color: #cfe2ff;
                    color: #007bff;
                    padding: 8px 16px;
                    border-radius: 4px;
                    font-weight: bold;
                    font-size: 13px;
                    border: 2px solid #007bff;
                }
            """)
        elif state == 'complete':
            self.tray.setIcon(self._tray_icon_complete)
            self.status_indicator.setText("✓ COMPLETE")
            self.status_indicator.setStyleSheet("""
                QLabel {
                    background-color: #d1e7dd;
                    color: #28a745;
                    padding: 8px 16px;
                    border-radius: 4px;
                    font-weight: bold;
                    font-size: 13px;
                    border: 2px solid #28a745;
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
