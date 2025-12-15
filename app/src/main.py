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
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
import time
from PyQt6.QtGui import QIcon, QAction, QFont, QClipboard, QShortcut, QKeySequence

from .config import (
    Config, load_config, save_config, load_env_keys,
    GEMINI_MODELS, OPENAI_MODELS, MISTRAL_MODELS, OPENROUTER_MODELS,
    MODEL_TIERS, PROMPT_COMPONENTS, build_cleanup_prompt,
    FORMAT_TEMPLATES, FORMAT_DISPLAY_NAMES, FORMALITY_DISPLAY_NAMES, EMAIL_SIGNOFFS,
)
from .audio_recorder import AudioRecorder
from .transcription import get_client, TranscriptionResult
from .audio_processor import compress_audio_for_api, archive_audio, get_audio_info, combine_wav_segments
from .markdown_widget import MarkdownTextWidget
from .database import get_db, AUDIO_ARCHIVE_DIR
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
from .cost_widget import CostWidget
from .analysis_widget import AnalysisWidget
from .models_widget import ModelsWidget
from .about_widget import AboutWidget
from .mic_test_widget import MicTestWidget
from .audio_feedback import get_feedback
from .file_transcription_widget import FileTranscriptionWidget


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

        self.openrouter_key = QLineEdit(self.config.openrouter_api_key)
        self.openrouter_key.setEchoMode(QLineEdit.EchoMode.Password)
        api_layout.addRow("OpenRouter API Key:", self.openrouter_key)

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

        # Hotkey mode selector
        mode_layout = QFormLayout()
        self.hotkey_mode_combo = QComboBox()
        for mode_key, mode_name in HOTKEY_MODE_NAMES.items():
            self.hotkey_mode_combo.addItem(mode_name, mode_key)
        # Set current mode
        current_mode = self.config.hotkey_mode
        idx = self.hotkey_mode_combo.findData(current_mode)
        if idx >= 0:
            self.hotkey_mode_combo.setCurrentIndex(idx)
        self.hotkey_mode_combo.currentIndexChanged.connect(self._update_hotkey_fields_visibility)
        mode_layout.addRow("Shortcut Mode:", self.hotkey_mode_combo)

        # Mode description label
        self.mode_description = QLabel(HOTKEY_MODE_DESCRIPTIONS.get(current_mode, ""))
        self.mode_description.setWordWrap(True)
        self.mode_description.setStyleSheet("color: #888; font-style: italic; margin-bottom: 10px;")
        mode_layout.addRow("", self.mode_description)

        hotkeys_layout.addLayout(mode_layout)

        # Container for mode-specific fields
        self.hotkey_fields_container = QWidget()
        self.hotkey_fields_layout = QFormLayout(self.hotkey_fields_container)
        self.hotkey_fields_layout.setContentsMargins(0, 0, 0, 0)

        # Tap-to-Toggle mode fields
        self.tap_toggle_widgets = []
        self.hotkey_toggle = HotkeyEdit()
        self.hotkey_toggle.setText(self.config.hotkey_record_toggle.upper())
        self.tap_toggle_widgets.append(("Toggle Recording:", self.hotkey_toggle))

        # Separate mode fields
        self.separate_widgets = []
        self.hotkey_start = HotkeyEdit()
        self.hotkey_start.setText(self.config.hotkey_start.upper() if self.config.hotkey_start else "")
        self.separate_widgets.append(("Start Recording:", self.hotkey_start))

        self.hotkey_stop_discard = HotkeyEdit()
        self.hotkey_stop_discard.setText(self.config.hotkey_stop_discard.upper() if self.config.hotkey_stop_discard else "")
        self.separate_widgets.append(("Stop && Discard:", self.hotkey_stop_discard))

        # PTT mode fields
        self.ptt_widgets = []
        self.hotkey_ptt = HotkeyEdit()
        self.hotkey_ptt.setText(self.config.hotkey_ptt.upper() if self.config.hotkey_ptt else "")
        self.ptt_widgets.append(("Push-to-Talk Key:", self.hotkey_ptt))

        self.ptt_release_action = QComboBox()
        self.ptt_release_action.addItem("Transcribe", "transcribe")
        self.ptt_release_action.addItem("Discard", "discard")
        release_idx = self.ptt_release_action.findData(self.config.ptt_release_action)
        if release_idx >= 0:
            self.ptt_release_action.setCurrentIndex(release_idx)
        self.ptt_widgets.append(("On Key Release:", self.ptt_release_action))

        # Stop & Transcribe - shared across modes (except PTT when set to transcribe on release)
        self.hotkey_stop_transcribe = HotkeyEdit()
        self.hotkey_stop_transcribe.setText(self.config.hotkey_stop_and_transcribe.upper())

        hotkeys_layout.addWidget(self.hotkey_fields_container)

        # Suggested hotkeys button
        suggest_btn = QPushButton("Use Suggested Hotkeys")
        suggest_btn.clicked.connect(self._use_suggested_hotkeys)
        hotkeys_layout.addWidget(suggest_btn)

        hotkeys_layout.addStretch()
        tabs.addTab(hotkeys_tab, "Hotkeys")

        # Initial visibility update
        self._update_hotkey_fields_visibility()

        # Note: Prompt options are now in the main Record tab for easier access

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

    def _update_hotkey_fields_visibility(self):
        """Update which hotkey fields are visible based on selected mode."""
        mode = self.hotkey_mode_combo.currentData()

        # Update description
        self.mode_description.setText(HOTKEY_MODE_DESCRIPTIONS.get(mode, ""))

        # Clear existing widgets from layout
        while self.hotkey_fields_layout.count():
            item = self.hotkey_fields_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

        # Add appropriate widgets based on mode
        if mode == "tap_toggle":
            for label, widget in self.tap_toggle_widgets:
                self.hotkey_fields_layout.addRow(label, widget)
            self.hotkey_fields_layout.addRow("Stop && Transcribe:", self.hotkey_stop_transcribe)

        elif mode == "separate":
            for label, widget in self.separate_widgets:
                self.hotkey_fields_layout.addRow(label, widget)
            self.hotkey_fields_layout.addRow("Stop && Transcribe:", self.hotkey_stop_transcribe)

        elif mode == "ptt":
            for label, widget in self.ptt_widgets:
                self.hotkey_fields_layout.addRow(label, widget)
            # Only show stop & transcribe if PTT release action is discard
            # (otherwise transcribe happens automatically on release)
            if self.ptt_release_action.currentData() == "discard":
                self.hotkey_fields_layout.addRow("Stop && Transcribe:", self.hotkey_stop_transcribe)

        # Connect PTT release action change to update visibility
        try:
            self.ptt_release_action.currentIndexChanged.disconnect(self._update_hotkey_fields_visibility)
        except TypeError:
            pass
        self.ptt_release_action.currentIndexChanged.connect(self._update_hotkey_fields_visibility)

    def _use_suggested_hotkeys(self):
        """Fill in the suggested hotkeys based on current mode."""
        mode = self.hotkey_mode_combo.currentData()

        if mode == "tap_toggle":
            self.hotkey_toggle.setText(SUGGESTED_HOTKEYS["record_toggle"])
            self.hotkey_stop_transcribe.setText(SUGGESTED_HOTKEYS["stop_and_transcribe"])
        elif mode == "separate":
            self.hotkey_start.setText(SUGGESTED_HOTKEYS["start"])
            self.hotkey_stop_discard.setText(SUGGESTED_HOTKEYS["stop_discard"])
            self.hotkey_stop_transcribe.setText(SUGGESTED_HOTKEYS["stop_and_transcribe"])
        elif mode == "ptt":
            self.hotkey_ptt.setText(SUGGESTED_HOTKEYS["ptt"])

    def save_settings(self):
        self.config.gemini_api_key = self.gemini_key.text()
        self.config.openai_api_key = self.openai_key.text()
        self.config.mistral_api_key = self.mistral_key.text()
        self.config.openrouter_api_key = self.openrouter_key.text()
        self.config.selected_microphone = self.mic_combo.currentText()
        self.config.start_minimized = self.start_minimized.isChecked()
        self.config.sample_rate = int(self.sample_rate.currentText())

        # Hotkey mode and settings (store lowercase for consistency)
        self.config.hotkey_mode = self.hotkey_mode_combo.currentData()

        # Tap-to-Toggle mode hotkeys
        self.config.hotkey_record_toggle = self.hotkey_toggle.text().lower()

        # Separate mode hotkeys
        self.config.hotkey_start = self.hotkey_start.text().lower()
        self.config.hotkey_stop_discard = self.hotkey_stop_discard.text().lower()

        # PTT mode settings
        self.config.hotkey_ptt = self.hotkey_ptt.text().lower()
        self.config.ptt_release_action = self.ptt_release_action.currentData()

        # Shared hotkey
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

        self.setWindowTitle("Voice Notepad")
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
        # Keep transcribe enabled if we have audio
        if self.recorder.frames or self.accumulated_segments:
            self.stop_btn.setEnabled(True)
            self.delete_btn.setEnabled(True)
        else:
            self.stop_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
        self.append_btn.setEnabled(False)
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
        self.provider_combo.addItems(["Open Router", "Google", "OpenAI", "Mistral"])
        # Handle display name mapping for provider
        provider_map = {
            "openrouter": "Open Router",
            "gemini": "Google",
            "openai": "OpenAI",
            "mistral": "Mistral",
        }
        provider_display = provider_map.get(self.config.selected_provider, self.config.selected_provider.title())
        self.provider_combo.setCurrentText(provider_display)
        self.provider_combo.currentTextChanged.connect(self.on_provider_changed)
        provider_layout.addWidget(self.provider_combo)

        provider_layout.addSpacing(20)

        provider_layout.addWidget(QLabel("Model:"))
        self.model_combo = QComboBox()
        self.update_model_combo()  # Populate based on current provider
        self.model_combo.currentIndexChanged.connect(self.on_model_changed)
        provider_layout.addWidget(self.model_combo, 1)

        layout.addLayout(provider_layout)

        # Model tier quick toggle (Standard / Budget)
        tier_layout = QHBoxLayout()
        tier_layout.addStretch()

        self.standard_btn = QPushButton("Standard")
        self.standard_btn.setCheckable(True)
        self.standard_btn.setMinimumWidth(80)
        self.standard_btn.clicked.connect(lambda: self.set_model_tier("standard"))

        self.budget_btn = QPushButton("Budget")
        self.budget_btn.setCheckable(True)
        self.budget_btn.setMinimumWidth(80)
        self.budget_btn.clicked.connect(lambda: self.set_model_tier("budget"))

        # Style for tier buttons
        tier_btn_style = """
            QPushButton {
                padding: 4px 12px;
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: #f8f9fa;
            }
            QPushButton:hover {
                background-color: #e9ecef;
            }
            QPushButton:checked {
                background-color: #007bff;
                color: white;
                border-color: #0056b3;
            }
        """
        self.standard_btn.setStyleSheet(tier_btn_style)
        self.budget_btn.setStyleSheet(tier_btn_style)

        tier_layout.addWidget(self.standard_btn)
        tier_layout.addWidget(self.budget_btn)
        tier_layout.addStretch()

        layout.addLayout(tier_layout)

        # Update tier button states based on current model
        self._update_tier_buttons()

        # Prompt Controls (collapsible) - combines cleanup options and format settings
        prompt_header = QHBoxLayout()
        self.prompt_toggle_btn = QPushButton("▶ Prompt Controls")
        self.prompt_toggle_btn.setStyleSheet("""
            QPushButton {
                border: none;
                text-align: left;
                padding: 4px 8px;
                color: #555;
                font-size: 12px;
            }
            QPushButton:hover {
                color: #007bff;
            }
        """)
        self.prompt_toggle_btn.clicked.connect(self._toggle_prompt_options)
        prompt_header.addWidget(self.prompt_toggle_btn)
        prompt_header.addStretch()
        layout.addLayout(prompt_header)

        # Collapsible prompt controls container
        self.prompt_options_frame = QFrame()
        self.prompt_options_frame.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                padding: 8px;
            }
        """)
        self.prompt_options_frame.setVisible(False)  # Start collapsed

        prompt_options_layout = QVBoxLayout(self.prompt_options_frame)
        prompt_options_layout.setSpacing(8)
        prompt_options_layout.setContentsMargins(8, 8, 8, 8)

        # System prompt checkboxes in a two-column grid
        checkbox_grid = QGridLayout()
        checkbox_grid.setSpacing(4)
        self.prompt_checkboxes = {}
        for i, (field_name, _, ui_description) in enumerate(PROMPT_COMPONENTS):
            checkbox = QCheckBox(ui_description)
            checkbox.setStyleSheet("font-size: 11px;")
            checkbox.setChecked(getattr(self.config, field_name, False))
            checkbox.stateChanged.connect(self._on_prompt_option_changed)
            self.prompt_checkboxes[field_name] = checkbox
            row = i // 2
            col = i % 2
            checkbox_grid.addWidget(checkbox, row, col)
        prompt_options_layout.addLayout(checkbox_grid)

        # Separator line
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("background-color: #dee2e6;")
        separator.setFixedHeight(1)
        prompt_options_layout.addWidget(separator)

        # Format and Tone row
        format_tone_row = QHBoxLayout()

        # Format dropdown
        format_tone_row.addWidget(QLabel("Format:"))
        self.format_combo = QComboBox()
        self.format_combo.setMinimumWidth(120)
        for format_key in FORMAT_TEMPLATES.keys():
            self.format_combo.addItem(FORMAT_DISPLAY_NAMES[format_key], format_key)
        idx = self.format_combo.findData(self.config.format_preset)
        if idx >= 0:
            self.format_combo.setCurrentIndex(idx)
        self.format_combo.currentIndexChanged.connect(self._on_format_changed)
        format_tone_row.addWidget(self.format_combo)

        format_tone_row.addSpacing(20)

        # Formality radio buttons
        format_tone_row.addWidget(QLabel("Tone:"))
        self.formality_group = QButtonGroup(self)
        for formality_key, display_name in FORMALITY_DISPLAY_NAMES.items():
            radio = QRadioButton(display_name)
            radio.setStyleSheet("font-size: 11px;")
            radio.setProperty("formality_key", formality_key)
            if formality_key == self.config.formality_level:
                radio.setChecked(True)
            self.formality_group.addButton(radio)
            format_tone_row.addWidget(radio)
        self.formality_group.buttonClicked.connect(self._on_formality_changed)

        format_tone_row.addStretch()
        prompt_options_layout.addLayout(format_tone_row)

        # Email settings (conditionally visible)
        self.email_settings_frame = QFrame()
        self.email_settings_frame.setStyleSheet("""
            QFrame {
                background-color: #e9ecef;
                border: 1px solid #ced4da;
                border-radius: 4px;
                padding: 6px;
                margin-top: 4px;
            }
        """)

        email_layout = QHBoxLayout(self.email_settings_frame)
        email_layout.setSpacing(8)
        email_layout.setContentsMargins(8, 6, 8, 6)

        email_layout.addWidget(QLabel("Your name:"))
        self.user_name_edit = QLineEdit(self.config.user_name)
        self.user_name_edit.setPlaceholderText("e.g., Daniel")
        self.user_name_edit.setMaximumWidth(150)
        self.user_name_edit.textChanged.connect(self._on_email_settings_changed)
        email_layout.addWidget(self.user_name_edit)

        email_layout.addSpacing(10)

        email_layout.addWidget(QLabel("Sign-off:"))
        self.signoff_combo = QComboBox()
        self.signoff_combo.setEditable(True)
        self.signoff_combo.setMaximumWidth(120)
        for signoff in EMAIL_SIGNOFFS:
            self.signoff_combo.addItem(signoff)
        idx = self.signoff_combo.findText(self.config.email_signature)
        if idx >= 0:
            self.signoff_combo.setCurrentIndex(idx)
        else:
            self.signoff_combo.setEditText(self.config.email_signature)
        self.signoff_combo.currentTextChanged.connect(self._on_email_settings_changed)
        email_layout.addWidget(self.signoff_combo)

        email_layout.addStretch()
        prompt_options_layout.addWidget(self.email_settings_frame)

        # Show/hide email settings based on current format
        self._update_email_settings_visibility()

        layout.addWidget(self.prompt_options_frame)

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

        self.append_btn = QPushButton("Append")
        self.append_btn.setMinimumHeight(45)
        self.append_btn.setEnabled(False)
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
        self.append_btn.clicked.connect(self.append_recording)
        controls.addWidget(self.append_btn)

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

        # Spend monitor at the bottom
        self.cost_label = QLabel("")
        self.cost_label.setTextFormat(Qt.TextFormat.RichText)
        self.cost_label.setStyleSheet("color: #888; font-size: 11px;")
        self.cost_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.cost_label)

        # Initialize cost display
        self._update_cost_display()

        self.tabs.addTab(record_tab, "Record")

        # File Transcription tab (right after Record)
        self.file_transcription_widget = FileTranscriptionWidget()
        self.tabs.addTab(self.file_transcription_widget, "File")

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

        # Models tab
        self.models_widget = ModelsWidget()
        self.tabs.addTab(self.models_widget, "Models")

        # Mic Test tab
        self.mic_test_widget = MicTestWidget()
        self.tabs.addTab(self.mic_test_widget, "Mic Test")

        # About tab
        self.about_widget = AboutWidget()
        self.tabs.addTab(self.about_widget, "About")

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

        self._tray_resume_action = QAction("Resume Recording", self)
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
        """Register all configured hotkeys based on the selected mode."""
        # Unregister all existing hotkeys first
        for name in ["record_toggle", "stop_and_transcribe", "start", "stop_discard", "ptt"]:
            self.hotkey_listener.unregister(name)

        mode = self.config.hotkey_mode

        if mode == "tap_toggle":
            # Tap-to-Toggle mode: one key toggles start/stop
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

        elif mode == "separate":
            # Separate mode: different keys for start, stop/discard, stop/transcribe
            if self.config.hotkey_start:
                self.hotkey_listener.register(
                    "start",
                    self.config.hotkey_start,
                    lambda: QTimer.singleShot(0, self._hotkey_start_only)
                )
            if self.config.hotkey_stop_discard:
                self.hotkey_listener.register(
                    "stop_discard",
                    self.config.hotkey_stop_discard,
                    lambda: QTimer.singleShot(0, self._hotkey_stop_discard)
                )
            if self.config.hotkey_stop_and_transcribe:
                self.hotkey_listener.register(
                    "stop_and_transcribe",
                    self.config.hotkey_stop_and_transcribe,
                    lambda: QTimer.singleShot(0, self._hotkey_stop_and_transcribe)
                )

        elif mode == "ptt":
            # Push-to-Talk mode: hold to record, release to stop
            if self.config.hotkey_ptt:
                # Determine release action
                if self.config.ptt_release_action == "transcribe":
                    release_callback = lambda: QTimer.singleShot(0, self._hotkey_stop_and_transcribe)
                else:
                    release_callback = lambda: QTimer.singleShot(0, self._hotkey_stop_discard)

                self.hotkey_listener.register(
                    "ptt",
                    self.config.hotkey_ptt,
                    lambda: QTimer.singleShot(0, self._hotkey_start_only),
                    release_callback=release_callback
                )

            # Also allow manual stop & transcribe if PTT release is set to discard
            if self.config.ptt_release_action == "discard" and self.config.hotkey_stop_and_transcribe:
                self.hotkey_listener.register(
                    "stop_and_transcribe",
                    self.config.hotkey_stop_and_transcribe,
                    lambda: QTimer.singleShot(0, self._hotkey_stop_and_transcribe)
                )

    def _hotkey_record_toggle(self):
        """Handle global hotkey for toggling recording on/off (tap-to-toggle mode)."""
        if self.recorder.is_recording:
            self.delete_recording()  # Stop and discard
        else:
            self.toggle_recording()  # Start recording

    def _hotkey_start_only(self):
        """Handle global hotkey for starting recording only."""
        if not self.recorder.is_recording:
            self.toggle_recording()

    def _hotkey_stop_discard(self):
        """Handle global hotkey for stop and discard."""
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

    def on_tab_changed(self, index: int):
        """Handle tab change - refresh data in the selected tab."""
        # Tabs: 0=Record, 1=File, 2=History, 3=Cost, 4=Analysis, 5=Models, 6=Mic Test, 7=About
        if index == 2:  # History tab
            self.history_widget.refresh()
        elif index == 3:  # Cost tab
            self.cost_widget.refresh()
        elif index == 4:  # Analysis tab
            self.analysis_widget.refresh()
        # File (1), Models (5), Mic Test (6), About (7) don't need refresh

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
        if provider == "openrouter":
            models = OPENROUTER_MODELS
            current_model = self.config.openrouter_model
        elif provider == "gemini":
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

    def on_provider_changed(self, provider_display: str):
        """Handle provider change."""
        # Map display name back to internal name
        display_to_internal = {
            "Open Router": "openrouter",
            "Google": "gemini",
            "OpenAI": "openai",
            "Mistral": "mistral",
        }
        self.config.selected_provider = display_to_internal.get(provider_display, provider_display.lower())
        self.update_model_combo()
        self._update_tier_buttons()
        save_config(self.config)

    def on_model_changed(self, index: int):
        """Handle model selection change."""
        if index < 0:
            return
        model_id = self.model_combo.currentData()
        provider = self.config.selected_provider.lower()

        if provider == "openrouter":
            self.config.openrouter_model = model_id
        elif provider == "gemini":
            self.config.gemini_model = model_id
        elif provider == "openai":
            self.config.openai_model = model_id
        else:
            self.config.mistral_model = model_id

        save_config(self.config)
        self._update_tier_buttons()

    def set_model_tier(self, tier: str):
        """Set the model to the standard or budget tier for the current provider."""
        provider = self.config.selected_provider.lower()
        tiers = MODEL_TIERS.get(provider, {})
        model_id = tiers.get(tier)

        if model_id:
            # Find and select the model in the dropdown
            idx = self.model_combo.findData(model_id)
            if idx >= 0:
                self.model_combo.setCurrentIndex(idx)
                # on_model_changed will be triggered and save config + update buttons

    def _update_tier_buttons(self):
        """Update tier button checked states based on current model."""
        provider = self.config.selected_provider.lower()
        tiers = MODEL_TIERS.get(provider, {})
        current_model = self.model_combo.currentData()

        # Block signals to prevent triggering clicks
        self.standard_btn.blockSignals(True)
        self.budget_btn.blockSignals(True)

        self.standard_btn.setChecked(current_model == tiers.get("standard"))
        self.budget_btn.setChecked(current_model == tiers.get("budget"))

        self.standard_btn.blockSignals(False)
        self.budget_btn.blockSignals(False)

    def _toggle_prompt_options(self):
        """Toggle visibility of prompt controls panel."""
        visible = not self.prompt_options_frame.isVisible()
        self.prompt_options_frame.setVisible(visible)
        self.prompt_toggle_btn.setText("▼ Prompt Controls" if visible else "▶ Prompt Controls")

    def _on_prompt_option_changed(self):
        """Handle prompt option checkbox changes - save immediately."""
        for field_name, checkbox in self.prompt_checkboxes.items():
            setattr(self.config, field_name, checkbox.isChecked())
        save_config(self.config)

    def _on_format_changed(self, index: int):
        """Handle format preset selection change."""
        format_key = self.format_combo.currentData()
        self.config.format_preset = format_key
        save_config(self.config)
        self._update_email_settings_visibility()

    def _on_formality_changed(self, button):
        """Handle formality radio button change."""
        formality_key = button.property("formality_key")
        self.config.formality_level = formality_key
        save_config(self.config)

    def _on_email_settings_changed(self):
        """Handle email name/sign-off changes."""
        self.config.user_name = self.user_name_edit.text()
        self.config.email_signature = self.signoff_combo.currentText()
        save_config(self.config)

    def _update_email_settings_visibility(self):
        """Show email settings only when format is 'email'."""
        is_email = self.config.format_preset == "email"
        self.email_settings_frame.setVisible(is_email)

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
            # Only clear text if no accumulated segments (new recording session)
            if not self.accumulated_segments:
                self.text_output.clear()
                self.word_count_label.setText("")

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
            self.append_btn.setEnabled(True)
            self.stop_btn.setEnabled(True)
            self.delete_btn.setEnabled(True)
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

    def append_recording(self):
        """Stop current recording, save segment, and start a new recording."""
        if not self.recorder.is_recording:
            return

        # Stop current recording and get audio data
        self.timer.stop()
        audio_data = self.recorder.stop_recording()

        # Get duration of this segment
        audio_info = get_audio_info(audio_data)
        segment_duration = audio_info["duration_seconds"]

        # Store the segment
        self.accumulated_segments.append(audio_data)
        self.accumulated_duration += segment_duration

        # Update segment indicator
        self._update_segment_indicator()

        # Play a quick beep to indicate segment saved
        feedback = get_feedback()
        feedback.enabled = self.config.beep_on_record
        feedback.play_stop_beep()

        # Immediately start a new recording
        self.recorder.start_recording()
        self.timer.start(100)

        # Brief status update
        self.status_label.setText(f"Clip saved! Recording...")
        self.status_label.setStyleSheet("color: #dc3545; font-weight: bold;")

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
        """Stop recording and send for transcription."""
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

        # Get original audio info
        audio_info = get_audio_info(audio_data)
        self.last_audio_duration = audio_info["duration_seconds"]
        self.last_vad_duration = None

        # Store audio data for later archiving (VAD now happens in worker thread)
        self.last_audio_data = audio_data

        self.record_btn.setText("Record")
        self.record_btn.setEnabled(False)
        self.pause_btn.setEnabled(False)
        self.append_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
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

        self.reset_ui()
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
        mic_name = self._get_active_microphone_name()
        self.mic_label.setText(mic_name)
        self.mic_label.setToolTip(f"Active microphone: {mic_name}\nChange in Settings → Audio")

    def _get_active_microphone_name(self) -> str:
        """Get the name of the currently active microphone."""
        import subprocess

        # If user has selected a specific mic that's not "pulse" or "default"
        if self.config.selected_microphone and self.config.selected_microphone not in ("pulse", "default"):
            return self.config.selected_microphone

        # Query PipeWire/PulseAudio for the actual default source
        try:
            # Get the default source name
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
                        # Parse the output to find the description
                        lines = desc_result.stdout.split('\n')
                        found_source = False
                        for line in lines:
                            if f"Name: {source_name}" in line:
                                found_source = True
                            elif found_source and "Description:" in line:
                                description = line.split("Description:", 1)[1].strip()
                                return description
                    # Fallback: clean up the source name
                    # e.g., "alsa_input.usb-Samson_Technologies_Samson_Q2U_Microphone-00.analog-stereo"
                    # Extract the meaningful part
                    if "usb-" in source_name:
                        # Extract device name from USB source
                        parts = source_name.split("usb-")[1].split("-00")[0]
                        return parts.replace("_", " ")
                    return source_name
        except Exception:
            pass

        # Fallback to checking devices
        devices = self.recorder.get_input_devices()
        if devices:
            return devices[0][1]

        return "No microphone found"

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
        self.delete_btn.setEnabled(False)
        self.duration_label.setText("0:00")
        self.status_label.setText("Ready")
        self.status_label.setStyleSheet("color: #666;")

    def delete_recording(self):
        """Delete current recording and any accumulated segments."""
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
        elif state == 'recording':
            self.tray.setIcon(self._tray_icon_recording)
        elif state == 'stopped':
            self.tray.setIcon(self._tray_icon_stopped)
        elif state == 'transcribing':
            self.tray.setIcon(self._tray_icon_transcribing)
        elif state == 'complete':
            self.tray.setIcon(self._tray_icon_complete)
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

        # Stop recording but hold the audio
        self.timer.stop()

        # Play stop beep
        feedback = get_feedback()
        feedback.enabled = self.config.beep_on_record
        feedback.play_stop_beep()

        # Pause the recorder (keeps audio data) instead of stopping
        self.recorder.pause_recording()

        # Update UI
        self.pause_btn.setText("Resume")
        self.record_btn.setText("● Stopped")
        self.record_btn.setStyleSheet(self._record_btn_recording_style.replace("#dc3545", "#ffc107"))
        self.status_label.setText("Stopped - choose action")
        self.status_label.setStyleSheet("color: #ffc107; font-weight: bold;")

        # Set tray to stopped state
        self._set_tray_state('stopped')

        # Show notification
        self.tray.showMessage(
            "Recording Stopped",
            "Click Transcribe or Delete from tray menu, or use main window.",
            QSystemTrayIcon.MessageIcon.Information,
            3000,
        )

    def _tray_transcribe_stopped(self):
        """Transcribe the stopped recording from tray menu."""
        if self._tray_state != 'stopped':
            return

        # Resume recording briefly then stop and transcribe
        # This triggers the normal transcription flow
        if self.recorder.is_paused:
            self.recorder.resume_recording()
        self.stop_and_transcribe()

    def _tray_delete_stopped(self):
        """Delete the stopped recording from tray menu."""
        if self._tray_state != 'stopped':
            return
        self.delete_recording()

    def _tray_resume_recording(self):
        """Resume recording from stopped state via tray menu."""
        if self._tray_state != 'stopped':
            return

        if self.recorder.is_paused:
            self.recorder.resume_recording()

        # Restore recording UI
        self.pause_btn.setText("Pause")
        self.record_btn.setText("● Recording")
        self.record_btn.setStyleSheet(self._record_btn_recording_style)
        self.status_label.setText("Recording...")
        self.status_label.setStyleSheet("color: #dc3545; font-weight: bold;")
        self.timer.start(100)

        # Set tray to recording state
        self._set_tray_state('recording')

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
