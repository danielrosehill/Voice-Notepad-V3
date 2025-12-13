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
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
import time
from PyQt6.QtGui import QIcon, QAction, QFont, QClipboard, QShortcut, QKeySequence

from .config import (
    Config, load_config, save_config, load_env_keys,
    GEMINI_MODELS, OPENAI_MODELS, MISTRAL_MODELS,
)
from .audio_recorder import AudioRecorder
from .transcription import get_client, TranscriptionResult
from .audio_processor import compress_audio_for_api, archive_audio, get_audio_info
from .markdown_widget import MarkdownTextWidget
from .database import get_db, AUDIO_ARCHIVE_DIR
from .vad_processor import remove_silence, is_vad_available
from .hotkeys import (
    GlobalHotkeyListener,
    HotkeyCapture,
    SUGGESTED_HOTKEYS,
    HOTKEY_DESCRIPTIONS,
)
from .cost_tracker import get_tracker
from .history_widget import HistoryWidget
from .cost_widget import CostWidget
from .analysis_widget import AnalysisWidget
from .audio_feedback import get_feedback


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

    def __init__(self, audio_data: bytes, provider: str, api_key: str, model: str, prompt: str):
        super().__init__()
        self.audio_data = audio_data
        self.provider = provider
        self.api_key = api_key
        self.model = model
        self.prompt = prompt
        self.inference_time_ms: int = 0

    def run(self):
        try:
            # Compress audio to 16kHz mono before sending
            self.status.emit("Compressing audio...")
            compressed_audio = compress_audio_for_api(self.audio_data)

            self.status.emit("Transcribing...")
            start_time = time.time()
            client = get_client(self.provider, self.api_key, self.model)
            result = client.transcribe(compressed_audio, self.prompt)
            self.inference_time_ms = int((time.time() - start_time) * 1000)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class SettingsDialog(QDialog):
    """Settings dialog for API keys and preferences."""

    def __init__(self, config: Config, recorder, parent=None):
        super().__init__(parent)
        self.config = config
        self.recorder = recorder
        self.setWindowTitle("Settings")
        self.setMinimumWidth(500)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        tabs = QTabWidget()

        # API Keys tab
        api_tab = QWidget()
        api_layout = QFormLayout(api_tab)

        self.gemini_key = QLineEdit(self.config.gemini_api_key)
        self.gemini_key.setEchoMode(QLineEdit.EchoMode.Password)
        api_layout.addRow("Gemini API Key:", self.gemini_key)

        self.openai_key = QLineEdit(self.config.openai_api_key)
        self.openai_key.setEchoMode(QLineEdit.EchoMode.Password)
        api_layout.addRow("OpenAI API Key:", self.openai_key)

        self.mistral_key = QLineEdit(self.config.mistral_api_key)
        self.mistral_key.setEchoMode(QLineEdit.EchoMode.Password)
        api_layout.addRow("Mistral API Key:", self.mistral_key)

        tabs.addTab(api_tab, "API Keys")

        # Audio tab (microphone selection)
        audio_tab = QWidget()
        audio_layout = QFormLayout(audio_tab)

        self.mic_combo = QComboBox()
        self._refresh_microphones()
        audio_layout.addRow("Microphone:", self.mic_combo)

        self.sample_rate = QComboBox()
        self.sample_rate.addItems(["16000", "22050", "44100", "48000"])
        self.sample_rate.setCurrentText(str(self.config.sample_rate))
        audio_layout.addRow("Sample Rate:", self.sample_rate)

        tabs.addTab(audio_tab, "Audio")

        # Behavior tab
        behavior_tab = QWidget()
        behavior_layout = QFormLayout(behavior_tab)

        self.start_minimized = QCheckBox()
        self.start_minimized.setChecked(self.config.start_minimized)
        behavior_layout.addRow("Start minimized to tray:", self.start_minimized)

        # Storage settings section
        behavior_layout.addRow(QLabel(""))  # Spacer
        storage_label = QLabel("Storage Settings")
        storage_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        behavior_layout.addRow(storage_label)

        self.vad_enabled = QCheckBox()
        self.vad_enabled.setChecked(self.config.vad_enabled)
        self.vad_enabled.setToolTip(
            "Remove silence from recordings before sending to API.\n"
            "Reduces file size and API costs."
        )
        behavior_layout.addRow("Enable VAD (silence removal):", self.vad_enabled)

        self.store_audio = QCheckBox()
        self.store_audio.setChecked(self.config.store_audio)
        self.store_audio.setToolTip(
            "Archive audio recordings in Opus format (~24kbps).\n"
            "Audio files are stored in ~/.config/voice-notepad-v3/audio-archive/"
        )
        behavior_layout.addRow("Archive audio recordings:", self.store_audio)

        # Audio feedback section
        behavior_layout.addRow(QLabel(""))  # Spacer
        feedback_label = QLabel("Audio Feedback")
        feedback_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        behavior_layout.addRow(feedback_label)

        self.beep_on_record = QCheckBox()
        self.beep_on_record.setChecked(self.config.beep_on_record)
        self.beep_on_record.setToolTip(
            "Play a short beep when recording starts and stops.\n"
            "Useful for confirming hotkey actions."
        )
        behavior_layout.addRow("Beep on record start/stop:", self.beep_on_record)

        tabs.addTab(behavior_tab, "Behavior")

        # Hotkeys tab
        hotkeys_tab = QWidget()
        hotkeys_layout = QVBoxLayout(hotkeys_tab)

        # Info label
        info_label = QLabel(
            "Configure global hotkeys that work even when the app is minimized.\n"
            "F14-F20 (macro keys) are recommended to avoid conflicts with other apps.\n"
            "Click a field and press a key to set. Press Delete/Backspace to clear."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #666; margin-bottom: 10px;")
        hotkeys_layout.addWidget(info_label)

        hotkeys_form = QFormLayout()

        self.hotkey_toggle = HotkeyEdit()
        self.hotkey_toggle.setText(self.config.hotkey_record_toggle.upper())
        hotkeys_form.addRow("Record Toggle (Start/Stop):", self.hotkey_toggle)

        self.hotkey_stop_transcribe = HotkeyEdit()
        self.hotkey_stop_transcribe.setText(self.config.hotkey_stop_and_transcribe.upper())
        hotkeys_form.addRow("Stop && Transcribe:", self.hotkey_stop_transcribe)

        hotkeys_layout.addLayout(hotkeys_form)

        # Suggested hotkeys button
        suggest_btn = QPushButton("Use Suggested (F15, F16)")
        suggest_btn.clicked.connect(self._use_suggested_hotkeys)
        hotkeys_layout.addWidget(suggest_btn)

        hotkeys_layout.addStretch()
        tabs.addTab(hotkeys_tab, "Hotkeys")

        # Prompt tab
        prompt_tab = QWidget()
        prompt_layout = QVBoxLayout(prompt_tab)
        prompt_layout.addWidget(QLabel("Cleanup Prompt:"))
        self.cleanup_prompt = QTextEdit()
        self.cleanup_prompt.setPlainText(self.config.cleanup_prompt)
        prompt_layout.addWidget(self.cleanup_prompt)
        tabs.addTab(prompt_tab, "Prompt")

        layout.addWidget(tabs)

        # Buttons
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.save_settings)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)

    def _refresh_microphones(self):
        """Refresh the list of available microphones."""
        self.mic_combo.clear()
        devices = self.recorder.get_input_devices()
        for idx, name in devices:
            self.mic_combo.addItem(name, idx)

        # Select previously used mic if available
        if self.config.selected_microphone:
            idx = self.mic_combo.findText(self.config.selected_microphone)
            if idx >= 0:
                self.mic_combo.setCurrentIndex(idx)
                return

        # Default to "pulse" which routes through PipeWire/PulseAudio
        idx = self.mic_combo.findText("pulse")
        if idx >= 0:
            self.mic_combo.setCurrentIndex(idx)
            return

        # Fallback to "default"
        idx = self.mic_combo.findText("default")
        if idx >= 0:
            self.mic_combo.setCurrentIndex(idx)

    def _use_suggested_hotkeys(self):
        """Fill in the suggested hotkeys (F15, F16)."""
        self.hotkey_toggle.setText(SUGGESTED_HOTKEYS["record_toggle"])
        self.hotkey_stop_transcribe.setText(SUGGESTED_HOTKEYS["stop_and_transcribe"])

    def save_settings(self):
        self.config.gemini_api_key = self.gemini_key.text()
        self.config.openai_api_key = self.openai_key.text()
        self.config.mistral_api_key = self.mistral_key.text()
        self.config.selected_microphone = self.mic_combo.currentText()
        self.config.start_minimized = self.start_minimized.isChecked()
        self.config.sample_rate = int(self.sample_rate.currentText())
        self.config.cleanup_prompt = self.cleanup_prompt.toPlainText()
        # Hotkeys (store lowercase for consistency)
        self.config.hotkey_record_toggle = self.hotkey_toggle.text().lower()
        self.config.hotkey_stop_and_transcribe = self.hotkey_stop_transcribe.text().lower()
        # Storage settings
        self.config.vad_enabled = self.vad_enabled.isChecked()
        self.config.store_audio = self.store_audio.isChecked()
        # Audio feedback
        self.config.beep_on_record = self.beep_on_record.isChecked()
        save_config(self.config)
        self.accept()


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.config = load_env_keys(load_config())
        self.recorder = AudioRecorder(self.config.sample_rate)
        self.worker: TranscriptionWorker | None = None
        self.recording_duration = 0.0

        self.setWindowTitle("Voice Notepad")
        self.setMinimumSize(480, 550)
        self.resize(self.config.window_width, self.config.window_height)

        self.setup_ui()
        self.setup_tray()
        self.setup_timer()
        self.setup_shortcuts()
        self.setup_global_hotkeys()

        # Start minimized if configured
        if self.config.start_minimized:
            self.hide()

    def setup_ui(self):
        """Set up the main UI with tabs."""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(12, 12, 12, 12)

        # Header with settings
        header = QHBoxLayout()
        title = QLabel("Voice Notepad")
        title.setFont(QFont("Sans", 16, QFont.Weight.Bold))
        header.addWidget(title)
        header.addStretch()

        settings_btn = QPushButton("Settings")
        settings_btn.clicked.connect(self.show_settings)
        header.addWidget(settings_btn)
        main_layout.addLayout(header)

        # Main tabs
        self.tabs = QTabWidget()

        # Record tab
        record_tab = QWidget()
        layout = QVBoxLayout(record_tab)
        layout.setSpacing(12)
        layout.setContentsMargins(8, 12, 8, 8)

        # Provider and model selection
        provider_layout = QHBoxLayout()

        provider_layout.addWidget(QLabel("Provider:"))
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["Gemini", "OpenAI", "Mistral"])
        self.provider_combo.setCurrentText(self.config.selected_provider.title())
        self.provider_combo.currentTextChanged.connect(self.on_provider_changed)
        provider_layout.addWidget(self.provider_combo)

        provider_layout.addSpacing(20)

        provider_layout.addWidget(QLabel("Model:"))
        self.model_combo = QComboBox()
        self.update_model_combo()  # Populate based on current provider
        self.model_combo.currentIndexChanged.connect(self.on_model_changed)
        provider_layout.addWidget(self.model_combo, 1)

        layout.addLayout(provider_layout)

        # Microphone indicator
        mic_layout = QHBoxLayout()
        mic_icon = QLabel("🎤")
        mic_icon.setStyleSheet("font-size: 14px;")
        mic_layout.addWidget(mic_icon)
        self.mic_label = QLabel()
        self.mic_label.setStyleSheet("color: #555; font-size: 12px;")
        mic_layout.addWidget(self.mic_label)
        mic_layout.addStretch()
        layout.addLayout(mic_layout)
        self._update_mic_display()

        # Recording status, cost, and duration
        status_layout = QHBoxLayout()
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #666;")
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()

        # Cost tracking display
        self.cost_label = QLabel("")
        self.cost_label.setStyleSheet("color: #888; font-size: 11px;")
        status_layout.addWidget(self.cost_label)
        status_layout.addSpacing(15)

        self.duration_label = QLabel("0:00")
        self.duration_label.setFont(QFont("Monospace", 12))
        status_layout.addWidget(self.duration_label)
        layout.addLayout(status_layout)

        # Initialize cost display
        self._update_cost_display()

        # Recording controls
        controls = QHBoxLayout()
        controls.setSpacing(8)

        self.record_btn = QPushButton("● Record")
        self.record_btn.setMinimumHeight(45)
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
        self.pause_btn.clicked.connect(self.toggle_pause)
        controls.addWidget(self.pause_btn)

        self.stop_btn = QPushButton("Transcribe")
        self.stop_btn.setMinimumHeight(45)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("""
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
        """)
        self.stop_btn.clicked.connect(self.stop_and_transcribe)
        controls.addWidget(self.stop_btn)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setMinimumHeight(45)
        self.delete_btn.setEnabled(False)
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

        self.save_btn = QPushButton("Save")
        self.save_btn.setMinimumHeight(38)
        self.save_btn.clicked.connect(self.save_to_file)
        bottom.addWidget(self.save_btn)

        bottom.addStretch()

        self.copy_btn = QPushButton("Copy")
        self.copy_btn.setMinimumHeight(38)
        self.copy_btn.clicked.connect(self.copy_to_clipboard)
        bottom.addWidget(self.copy_btn)

        layout.addLayout(bottom)

        self.tabs.addTab(record_tab, "Record")

        # History tab
        self.history_widget = HistoryWidget()
        self.history_widget.transcription_selected.connect(self.on_history_transcription_selected)
        self.tabs.addTab(self.history_widget, "History")

        # Cost tab
        self.cost_widget = CostWidget()
        self.tabs.addTab(self.cost_widget, "Cost")

        # Analysis tab
        self.analysis_widget = AnalysisWidget()
        self.tabs.addTab(self.analysis_widget, "Analysis")

        # Refresh data when switching tabs
        self.tabs.currentChanged.connect(self.on_tab_changed)

        main_layout.addWidget(self.tabs, 1)

    def setup_tray(self):
        """Set up system tray icon."""
        self.tray = QSystemTrayIcon(self)

        # Create a simple icon (you can replace with a proper icon file)
        icon = self.style().standardIcon(self.style().StandardPixmap.SP_MediaVolume)
        self.tray.setIcon(icon)
        self.setWindowIcon(icon)

        # Tray menu
        menu = QMenu()

        show_action = QAction("Show", self)
        show_action.triggered.connect(self.show_window)
        menu.addAction(show_action)

        record_action = QAction("Start Recording", self)
        record_action.triggered.connect(self.toggle_recording)
        menu.addAction(record_action)

        menu.addSeparator()

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.quit_app)
        menu.addAction(quit_action)

        self.tray.setContextMenu(menu)
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
        """Set up shortcuts based on user-configured hotkeys."""
        # Remove old shortcuts if they exist
        if hasattr(self, '_record_toggle_shortcut'):
            self._record_toggle_shortcut.setEnabled(False)
            self._record_toggle_shortcut.deleteLater()
        if hasattr(self, '_stop_transcribe_shortcut'):
            self._stop_transcribe_shortcut.setEnabled(False)
            self._stop_transcribe_shortcut.deleteLater()

        # Record toggle shortcut (e.g., F15)
        if self.config.hotkey_record_toggle:
            key_seq = self._hotkey_to_qt_sequence(self.config.hotkey_record_toggle)
            if key_seq:
                self._record_toggle_shortcut = QShortcut(key_seq, self)
                self._record_toggle_shortcut.activated.connect(self._hotkey_record_toggle)

        # Stop and transcribe shortcut (e.g., F16)
        if self.config.hotkey_stop_and_transcribe:
            key_seq = self._hotkey_to_qt_sequence(self.config.hotkey_stop_and_transcribe)
            if key_seq:
                self._stop_transcribe_shortcut = QShortcut(key_seq, self)
                self._stop_transcribe_shortcut.activated.connect(self._hotkey_stop_and_transcribe)

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
        """Register all configured hotkeys."""
        # Use lambdas that post events to the main thread
        if self.config.hotkey_record_toggle:
            self.hotkey_listener.register(
                "record_toggle",
                self.config.hotkey_record_toggle,
                lambda: QTimer.singleShot(0, self._hotkey_record_toggle)
            )

        if self.config.hotkey_stop_and_transcribe:
            self.hotkey_listener.register(
                "stop_and_transcribe",
                self.config.hotkey_stop_and_transcribe,
                lambda: QTimer.singleShot(0, self._hotkey_stop_and_transcribe)
            )

    def _hotkey_record_toggle(self):
        """Handle global hotkey for toggling recording on/off."""
        if self.recorder.is_recording:
            self.delete_recording()  # Stop and discard
        else:
            self.toggle_recording()  # Start recording

    def _hotkey_stop_and_transcribe(self):
        """Handle global hotkey for stop and transcribe."""
        if self.recorder.is_recording:
            self.stop_and_transcribe()

    def toggle_pause_if_recording(self):
        """Toggle pause only if currently recording."""
        if self.recorder.is_recording:
            self.toggle_pause()

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

    def on_tab_changed(self, index: int):
        """Handle tab change - refresh data in the selected tab."""
        if index == 1:  # History tab
            self.history_widget.refresh()
        elif index == 2:  # Cost tab
            self.cost_widget.refresh()
        elif index == 3:  # Analysis tab
            self.analysis_widget.refresh()

    def on_history_transcription_selected(self, text: str):
        """Handle transcription selected from history - put in editor."""
        self.text_output.setMarkdown(text)
        self.tabs.setCurrentIndex(0)  # Switch to Record tab
        self.update_word_count()

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

    def update_model_combo(self):
        """Update the model dropdown based on selected provider."""
        self.model_combo.blockSignals(True)
        self.model_combo.clear()

        provider = self.config.selected_provider.lower()
        if provider == "gemini":
            models = GEMINI_MODELS
            current_model = self.config.gemini_model
        elif provider == "openai":
            models = OPENAI_MODELS
            current_model = self.config.openai_model
        else:
            models = MISTRAL_MODELS
            current_model = self.config.mistral_model

        for model_id, display_name in models:
            self.model_combo.addItem(display_name, model_id)

        # Select current model
        idx = self.model_combo.findData(current_model)
        if idx >= 0:
            self.model_combo.setCurrentIndex(idx)

        self.model_combo.blockSignals(False)

    def on_provider_changed(self, provider: str):
        """Handle provider change."""
        self.config.selected_provider = provider.lower()
        self.update_model_combo()
        save_config(self.config)

    def on_model_changed(self, index: int):
        """Handle model selection change."""
        if index < 0:
            return
        model_id = self.model_combo.currentData()
        provider = self.config.selected_provider.lower()

        if provider == "gemini":
            self.config.gemini_model = model_id
        elif provider == "openai":
            self.config.openai_model = model_id
        else:
            self.config.mistral_model = model_id

        save_config(self.config)

    def get_selected_microphone_index(self):
        """Get the index of the configured microphone."""
        devices = self.recorder.get_input_devices()

        # Try to find configured mic
        if self.config.selected_microphone:
            for idx, name in devices:
                if name == self.config.selected_microphone:
                    return idx

        # Default to "pulse" which routes through PipeWire/PulseAudio
        # This picks up the system's default source (e.g., USB microphones)
        for idx, name in devices:
            if name == "pulse":
                return idx

        # Fallback to "default" if pulse not available
        for idx, name in devices:
            if name == "default":
                return idx

        # Fall back to first device
        if devices:
            return devices[0][0]
        return None

    def toggle_recording(self):
        """Start or stop recording."""
        if not self.recorder.is_recording:
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
            self.stop_btn.setEnabled(True)
            self.delete_btn.setEnabled(True)
            self.status_label.setText("Recording...")
            self.status_label.setStyleSheet("color: #dc3545; font-weight: bold;")
            self.timer.start(100)

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

    def stop_and_transcribe(self):
        """Stop recording and send for transcription."""
        # Play stop beep
        feedback = get_feedback()
        feedback.enabled = self.config.beep_on_record
        feedback.play_stop_beep()

        self.timer.stop()
        audio_data = self.recorder.stop_recording()

        # Get original audio info
        audio_info = get_audio_info(audio_data)
        self.last_audio_duration = audio_info["duration_seconds"]
        self.last_vad_duration = None

        # Apply VAD if enabled
        if self.config.vad_enabled and is_vad_available():
            self.status_label.setText("Removing silence...")
            self.status_label.setStyleSheet("color: #007bff; font-weight: bold;")
            try:
                audio_data, orig_dur, vad_dur = remove_silence(audio_data)
                self.last_vad_duration = vad_dur
                if vad_dur < orig_dur:
                    reduction = (1 - vad_dur / orig_dur) * 100
                    print(f"VAD: Reduced audio from {orig_dur:.1f}s to {vad_dur:.1f}s ({reduction:.0f}% reduction)")
            except Exception as e:
                print(f"VAD failed, using original audio: {e}")

        # Store audio data for later archiving
        self.last_audio_data = audio_data

        self.record_btn.setText("Record")
        self.record_btn.setEnabled(False)
        self.pause_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.delete_btn.setEnabled(False)
        self.status_label.setText("Transcribing...")
        self.status_label.setStyleSheet("color: #007bff; font-weight: bold;")

        # Get API key for selected provider
        provider = self.config.selected_provider
        if provider == "gemini":
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
        self.worker = TranscriptionWorker(
            audio_data, provider, api_key, model, self.config.cleanup_prompt
        )
        self.worker.finished.connect(self.on_transcription_complete)
        self.worker.error.connect(self.on_transcription_error)
        self.worker.status.connect(self.on_worker_status)
        self.worker.start()

    def on_worker_status(self, status: str):
        """Handle worker status updates."""
        self.status_label.setText(status)
        self.status_label.setStyleSheet("color: #007bff; font-weight: bold;")

    def on_transcription_complete(self, result: TranscriptionResult):
        """Handle completed transcription."""
        self.text_output.setMarkdown(result.text)

        # Get provider/model info
        provider = self.config.selected_provider
        if provider == "gemini":
            model = self.config.gemini_model
        elif provider == "openai":
            model = self.config.openai_model
        else:
            model = self.config.mistral_model

        # Track cost if we have usage data
        estimated_cost = 0.0
        if result.input_tokens > 0 or result.output_tokens > 0:
            tracker = get_tracker()
            estimated_cost = tracker.record_usage(provider, model, result.input_tokens, result.output_tokens)
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
        db = get_db()
        db.save_transcription(
            provider=provider,
            model=model,
            transcript_text=result.text,
            audio_duration_seconds=audio_duration,
            inference_time_ms=inference_time_ms,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            estimated_cost=estimated_cost,
            audio_file_path=audio_file_path,
            vad_audio_duration_seconds=vad_duration,
        )

        # Clear stored audio data
        if hasattr(self, 'last_audio_data'):
            del self.last_audio_data
        if hasattr(self, 'last_audio_duration'):
            del self.last_audio_duration
        if hasattr(self, 'last_vad_duration'):
            del self.last_vad_duration

        self.reset_ui()
        self.status_label.setText("Done!")
        self.status_label.setStyleSheet("color: #28a745; font-weight: bold;")

    def on_transcription_error(self, error: str):
        """Handle transcription error."""
        QMessageBox.critical(self, "Transcription Error", error)
        self.reset_ui()

    def _update_cost_display(self):
        """Update the cost display label."""
        tracker = get_tracker()
        today_cost = tracker.get_today_cost()
        count = tracker.get_today_count()

        if count > 0:
            self.cost_label.setText(f"Today: ~${today_cost:.4f} ({count})")
            self.cost_label.setToolTip(
                f"Estimated cost today: ${today_cost:.4f}\n"
                f"Transcriptions: {count}\n\n"
                f"⚠ Estimate only - may not reflect actual billing.\n"
                f"Check your provider's dashboard for precise costs."
            )
        else:
            self.cost_label.setText("")
            self.cost_label.setToolTip("")

    def _update_mic_display(self):
        """Update the microphone display label."""
        mic_name = self._get_active_microphone_name()
        self.mic_label.setText(mic_name)
        self.mic_label.setToolTip(f"Active microphone: {mic_name}\nChange in Settings → Audio")

    def _get_active_microphone_name(self) -> str:
        """Get the name of the currently active microphone."""
        # If user has selected a specific mic
        if self.config.selected_microphone:
            return self.config.selected_microphone

        # Otherwise determine the default that would be used
        devices = self.recorder.get_input_devices()

        # Check for "pulse" (PipeWire/PulseAudio default)
        for idx, name in devices:
            if name == "pulse":
                return "pulse (system default)"

        # Check for "default"
        for idx, name in devices:
            if name == "default":
                return "default"

        # Fall back to first device
        if devices:
            return devices[0][1]

        return "No microphone found"

    def reset_ui(self):
        """Reset UI to initial state."""
        self.record_btn.setText("● Record")
        self.record_btn.setStyleSheet(self._record_btn_idle_style)
        self.pause_btn.setText("Pause")
        self.pause_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.delete_btn.setEnabled(False)
        self.duration_label.setText("0:00")
        self.status_label.setText("Ready")
        self.status_label.setStyleSheet("color: #666;")

    def delete_recording(self):
        """Delete current recording."""
        # Play stop beep when discarding
        if self.recorder.is_recording:
            feedback = get_feedback()
            feedback.enabled = self.config.beep_on_record
            feedback.play_stop_beep()

        self.timer.stop()
        if self.recorder.is_recording:
            self.recorder.stop_recording()
        self.recorder.clear()
        self.reset_ui()

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

    def copy_to_clipboard(self):
        """Copy transcription to clipboard."""
        text = self.text_output.toPlainText()
        if text:
            clipboard = QApplication.clipboard()
            clipboard.setText(text)
            self.status_label.setText("Copied!")
            self.status_label.setStyleSheet("color: #28a745;")
            QTimer.singleShot(2000, lambda: self.status_label.setText("Ready"))
            QTimer.singleShot(2000, lambda: self.status_label.setStyleSheet("color: #666;"))

    def show_settings(self):
        """Show settings dialog."""
        dialog = SettingsDialog(self.config, self.recorder, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.config = load_config()
            self.recorder.sample_rate = self.config.sample_rate
            # Re-register hotkeys with new settings
            self._register_hotkeys()
            # Re-setup in-focus shortcuts
            self._setup_configurable_shortcuts()
            # Update mic display
            self._update_mic_display()

    def show_window(self):
        """Show and raise the window."""
        self.show()
        self.raise_()
        self.activateWindow()

    def on_tray_activated(self, reason):
        """Handle tray icon activation."""
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self.show_window()

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
