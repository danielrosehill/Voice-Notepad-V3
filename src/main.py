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
from PyQt6.QtGui import QIcon, QAction, QFont, QClipboard, QShortcut, QKeySequence

from .config import (
    Config, load_config, save_config, load_env_keys,
    GEMINI_MODELS, OPENAI_MODELS, MISTRAL_MODELS,
)
from .audio_recorder import AudioRecorder
from .transcription import get_client
from .audio_processor import compress_audio_for_api
from .markdown_widget import MarkdownTextWidget
from .hotkeys import (
    GlobalHotkeyListener,
    HotkeyCapture,
    SUGGESTED_HOTKEYS,
    HOTKEY_DESCRIPTIONS,
)


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

    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    status = pyqtSignal(str)

    def __init__(self, audio_data: bytes, provider: str, api_key: str, model: str, prompt: str):
        super().__init__()
        self.audio_data = audio_data
        self.provider = provider
        self.api_key = api_key
        self.model = model
        self.prompt = prompt

    def run(self):
        try:
            # Compress audio to 16kHz mono before sending
            self.status.emit("Compressing audio...")
            compressed_audio = compress_audio_for_api(self.audio_data)

            self.status.emit("Transcribing...")
            client = get_client(self.provider, self.api_key, self.model)
            result = client.transcribe(compressed_audio, self.prompt)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class SettingsDialog(QDialog):
    """Settings dialog for API keys and preferences."""

    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        self.config = config
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

        # Models tab
        models_tab = QWidget()
        models_layout = QFormLayout(models_tab)

        self.gemini_model = QComboBox()
        for model_id, display_name in GEMINI_MODELS:
            self.gemini_model.addItem(display_name, model_id)
        # Set current selection based on config
        gemini_idx = self.gemini_model.findData(self.config.gemini_model)
        if gemini_idx >= 0:
            self.gemini_model.setCurrentIndex(gemini_idx)
        models_layout.addRow("Gemini Model:", self.gemini_model)

        self.openai_model = QComboBox()
        for model_id, display_name in OPENAI_MODELS:
            self.openai_model.addItem(display_name, model_id)
        openai_idx = self.openai_model.findData(self.config.openai_model)
        if openai_idx >= 0:
            self.openai_model.setCurrentIndex(openai_idx)
        models_layout.addRow("OpenAI Model:", self.openai_model)

        self.mistral_model = QComboBox()
        for model_id, display_name in MISTRAL_MODELS:
            self.mistral_model.addItem(display_name, model_id)
        mistral_idx = self.mistral_model.findData(self.config.mistral_model)
        if mistral_idx >= 0:
            self.mistral_model.setCurrentIndex(mistral_idx)
        models_layout.addRow("Mistral Model:", self.mistral_model)

        tabs.addTab(models_tab, "Models")

        # Behavior tab
        behavior_tab = QWidget()
        behavior_layout = QFormLayout(behavior_tab)

        self.start_minimized = QCheckBox()
        self.start_minimized.setChecked(self.config.start_minimized)
        behavior_layout.addRow("Start minimized to tray:", self.start_minimized)

        self.sample_rate = QComboBox()
        self.sample_rate.addItems(["16000", "22050", "44100", "48000"])
        self.sample_rate.setCurrentText(str(self.config.sample_rate))
        behavior_layout.addRow("Sample Rate:", self.sample_rate)

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

        self.hotkey_start = HotkeyEdit()
        self.hotkey_start.setText(self.config.hotkey_start_recording.upper())
        hotkeys_form.addRow("Start Recording:", self.hotkey_start)

        self.hotkey_stop = HotkeyEdit()
        self.hotkey_stop.setText(self.config.hotkey_stop_recording.upper())
        hotkeys_form.addRow("Stop Recording (discard):", self.hotkey_stop)

        self.hotkey_stop_transcribe = HotkeyEdit()
        self.hotkey_stop_transcribe.setText(self.config.hotkey_stop_and_transcribe.upper())
        hotkeys_form.addRow("Stop && Transcribe:", self.hotkey_stop_transcribe)

        hotkeys_layout.addLayout(hotkeys_form)

        # Suggested hotkeys button
        suggest_btn = QPushButton("Use Suggested (F14-F16)")
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

    def _use_suggested_hotkeys(self):
        """Fill in the suggested hotkeys (F14-F16)."""
        self.hotkey_start.setText(SUGGESTED_HOTKEYS["start_recording"])
        self.hotkey_stop.setText(SUGGESTED_HOTKEYS["stop_recording"])
        self.hotkey_stop_transcribe.setText(SUGGESTED_HOTKEYS["stop_and_transcribe"])

    def save_settings(self):
        self.config.gemini_api_key = self.gemini_key.text()
        self.config.openai_api_key = self.openai_key.text()
        self.config.mistral_api_key = self.mistral_key.text()
        self.config.gemini_model = self.gemini_model.currentData()
        self.config.openai_model = self.openai_model.currentData()
        self.config.mistral_model = self.mistral_model.currentData()
        self.config.start_minimized = self.start_minimized.isChecked()
        self.config.sample_rate = int(self.sample_rate.currentText())
        self.config.cleanup_prompt = self.cleanup_prompt.toPlainText()
        # Hotkeys (store lowercase for consistency)
        self.config.hotkey_start_recording = self.hotkey_start.text().lower()
        self.config.hotkey_stop_recording = self.hotkey_stop.text().lower()
        self.config.hotkey_stop_and_transcribe = self.hotkey_stop_transcribe.text().lower()
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
        """Set up the main UI."""
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # Header with settings
        header = QHBoxLayout()
        title = QLabel("Voice Notepad")
        title.setFont(QFont("Sans", 16, QFont.Weight.Bold))
        header.addWidget(title)
        header.addStretch()

        settings_btn = QPushButton("Settings")
        settings_btn.clicked.connect(self.show_settings)
        header.addWidget(settings_btn)
        layout.addLayout(header)

        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)

        # Provider and model selection
        provider_layout = QHBoxLayout()

        provider_layout.addWidget(QLabel("Provider:"))
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["Gemini", "OpenAI", "Mistral"])
        self.provider_combo.setCurrentText(self.config.selected_provider.title())
        self.provider_combo.currentTextChanged.connect(self.on_provider_changed)
        provider_layout.addWidget(self.provider_combo)

        provider_layout.addSpacing(20)

        provider_layout.addWidget(QLabel("Mic:"))
        self.mic_combo = QComboBox()
        self.refresh_microphones()
        provider_layout.addWidget(self.mic_combo, 1)

        layout.addLayout(provider_layout)

        # Recording status and duration
        status_layout = QHBoxLayout()
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #666;")
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        self.duration_label = QLabel("0:00")
        self.duration_label.setFont(QFont("Monospace", 12))
        status_layout.addWidget(self.duration_label)
        layout.addLayout(status_layout)

        # Recording controls
        controls = QHBoxLayout()
        controls.setSpacing(8)

        self.record_btn = QPushButton("Record")
        self.record_btn.setMinimumHeight(45)
        self.record_btn.setStyleSheet("""
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
            QPushButton:disabled {
                background-color: #6c757d;
            }
        """)
        self.record_btn.clicked.connect(self.toggle_recording)
        controls.addWidget(self.record_btn)

        self.pause_btn = QPushButton("Pause")
        self.pause_btn.setMinimumHeight(45)
        self.pause_btn.setEnabled(False)
        self.pause_btn.clicked.connect(self.toggle_pause)
        controls.addWidget(self.pause_btn)

        self.stop_btn = QPushButton("Stop & Transcribe")
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

        self.new_btn = QPushButton("New Note")
        self.new_btn.setMinimumHeight(38)
        self.new_btn.clicked.connect(self.new_note)
        bottom.addWidget(self.new_btn)

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

        # Ctrl+N for new note
        new_shortcut = QShortcut(QKeySequence("Ctrl+N"), self)
        new_shortcut.activated.connect(self.new_note)

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
        if self.config.hotkey_start_recording:
            self.hotkey_listener.register(
                "start_recording",
                self.config.hotkey_start_recording,
                lambda: QTimer.singleShot(0, self._hotkey_start_recording)
            )

        if self.config.hotkey_stop_recording:
            self.hotkey_listener.register(
                "stop_recording",
                self.config.hotkey_stop_recording,
                lambda: QTimer.singleShot(0, self._hotkey_stop_recording)
            )

        if self.config.hotkey_stop_and_transcribe:
            self.hotkey_listener.register(
                "stop_and_transcribe",
                self.config.hotkey_stop_and_transcribe,
                lambda: QTimer.singleShot(0, self._hotkey_stop_and_transcribe)
            )

    def _hotkey_start_recording(self):
        """Handle global hotkey for starting recording."""
        if not self.recorder.is_recording:
            self.toggle_recording()

    def _hotkey_stop_recording(self):
        """Handle global hotkey for stopping recording (discard)."""
        if self.recorder.is_recording:
            self.delete_recording()

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

    def refresh_microphones(self):
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

        # Default to Samson Q2U if available
        for i in range(self.mic_combo.count()):
            if "Samson" in self.mic_combo.itemText(i) or "Q2U" in self.mic_combo.itemText(i):
                self.mic_combo.setCurrentIndex(i)
                return

    def on_provider_changed(self, provider: str):
        """Handle provider change."""
        self.config.selected_provider = provider.lower()
        save_config(self.config)

    def toggle_recording(self):
        """Start or stop recording."""
        if not self.recorder.is_recording:
            # Set microphone
            mic_idx = self.mic_combo.currentData()
            self.recorder.set_device(mic_idx)
            self.config.selected_microphone = self.mic_combo.currentText()

            self.recorder.start_recording()
            self.record_btn.setText("Recording...")
            self.record_btn.setEnabled(False)
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
        self.timer.stop()
        audio_data = self.recorder.stop_recording()

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

    def on_transcription_complete(self, text: str):
        """Handle completed transcription."""
        self.text_output.setMarkdown(text)
        self.reset_ui()
        self.status_label.setText("Done!")
        self.status_label.setStyleSheet("color: #28a745; font-weight: bold;")

    def on_transcription_error(self, error: str):
        """Handle transcription error."""
        QMessageBox.critical(self, "Transcription Error", error)
        self.reset_ui()

    def reset_ui(self):
        """Reset UI to initial state."""
        self.record_btn.setText("Record")
        self.record_btn.setEnabled(True)
        self.pause_btn.setText("Pause")
        self.pause_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.delete_btn.setEnabled(False)
        self.duration_label.setText("0:00")
        self.status_label.setText("Ready")
        self.status_label.setStyleSheet("color: #666;")

    def delete_recording(self):
        """Delete current recording."""
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

    def new_note(self):
        """Clear for a new note."""
        self.text_output.clear()
        self.reset_ui()

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
        dialog = SettingsDialog(self.config, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.config = load_config()
            self.recorder.sample_rate = self.config.sample_rate
            # Re-register hotkeys with new settings
            self._register_hotkeys()

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
