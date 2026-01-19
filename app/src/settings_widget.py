"""Unified Settings widget combining all configuration options."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTabWidget,
    QLineEdit, QCheckBox, QComboBox, QGroupBox, QFormLayout,
    QPushButton, QSpinBox, QFrame, QMessageBox, QFileDialog,
    QTextEdit, QScrollArea, QDialog, QDialogButtonBox,
    QGraphicsOpacityEffect,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont

from .config import (
    Config, save_config, load_env_keys,
    GEMINI_MODELS, OPENROUTER_MODELS,
    MODEL_TIERS,
    TRANSLATION_LANGUAGES, get_language_display_name, get_language_flag,
)
from .mic_test_widget import MicTestWidget
from .ui_utils import get_provider_icon, get_model_icon
from PyQt6.QtCore import QSize
from PyQt6.QtGui import QIcon
from pathlib import Path


class SettingsToast(QLabel):
    """A toast notification that fades out after displaying a message."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QLabel {
                background-color: #28a745;
                color: white;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 12px;
            }
        """)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hide()

        # Opacity effect for fade animation
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_effect)
        self._opacity_effect.setOpacity(1.0)

        # Fade out animation
        self._fade_animation = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._fade_animation.setDuration(500)
        self._fade_animation.setStartValue(1.0)
        self._fade_animation.setEndValue(0.0)
        self._fade_animation.setEasingCurve(QEasingCurve.Type.OutQuad)
        self._fade_animation.finished.connect(self.hide)

        # Timer to start fade after delay
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._start_fade)

    def show_message(self, message: str = "Settings saved", duration_ms: int = 1500):
        """Show a toast message that fades out after duration."""
        self.setText(message)
        self._opacity_effect.setOpacity(1.0)
        self._fade_animation.stop()
        self._hide_timer.stop()
        self.show()
        self._hide_timer.start(duration_ms)

    def _start_fade(self):
        """Start the fade out animation."""
        self._fade_animation.start()


class APIKeysWidget(QWidget):
    """API Keys configuration section."""

    def __init__(self, config: Config, settings_parent=None, parent=None):
        super().__init__(parent)
        self.config = config
        self.settings_parent = settings_parent
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(16, 16, 16, 16)

        # Title
        title = QLabel("API Keys")
        title.setFont(QFont("Sans", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        desc = QLabel(
            "Configure API keys for transcription providers. "
            "Gemini direct is recommended for access to the dynamic 'gemini-flash-latest' endpoint."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #666; margin-bottom: 12px;")
        layout.addWidget(desc)

        # API Keys form
        api_form = QFormLayout()
        api_form.setSpacing(12)
        api_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        # Gemini (recommended)
        self.gemini_key = QLineEdit()
        self.gemini_key.setText(self.config.gemini_api_key)
        self.gemini_key.setPlaceholderText("AI...")
        self.gemini_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.gemini_key.textChanged.connect(lambda: self._save_key("gemini_api_key", self.gemini_key.text()))

        gem_layout = QVBoxLayout()
        gem_layout.addWidget(self.gemini_key)
        gem_help = QLabel("⭐ Recommended: Supports dynamic 'gemini-flash-latest' endpoint")
        gem_help.setStyleSheet("color: #28a745; font-size: 10px; margin-left: 2px;")
        gem_layout.addWidget(gem_help)
        api_form.addRow("Gemini API Key:", gem_layout)

        # OpenRouter (alternative)
        self.openrouter_key = QLineEdit()
        self.openrouter_key.setText(self.config.openrouter_api_key)
        self.openrouter_key.setPlaceholderText("sk-or-v1-...")
        self.openrouter_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.openrouter_key.textChanged.connect(lambda: self._save_key("openrouter_api_key", self.openrouter_key.text()))

        or_layout = QVBoxLayout()
        or_layout.addWidget(self.openrouter_key)
        or_help = QLabel("Alternative: Access Gemini models via OpenAI-compatible API")
        or_help.setStyleSheet("color: #666; font-size: 10px; margin-left: 2px;")
        or_layout.addWidget(or_help)
        api_form.addRow("OpenRouter API Key:", or_layout)

        layout.addLayout(api_form)

        # Available models section
        models_group = QGroupBox("Available Models by Provider")
        models_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #ced4da;
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 12px;
            }
        """)
        models_layout = QVBoxLayout(models_group)
        models_layout.setSpacing(8)

        # Gemini models (primary)
        gem_models = [name for _, name in GEMINI_MODELS]
        gem_label = QLabel("<b>Gemini (Direct):</b> " + ", ".join(gem_models))
        gem_label.setWordWrap(True)
        gem_label.setStyleSheet("padding: 4px;")
        models_layout.addWidget(gem_label)

        # OpenRouter models
        or_models = [name for _, name in OPENROUTER_MODELS]
        or_label = QLabel("<b>OpenRouter:</b> " + ", ".join(or_models))
        or_label.setWordWrap(True)
        or_label.setStyleSheet("padding: 4px;")
        models_layout.addWidget(or_label)

        layout.addWidget(models_group)
        layout.addStretch()

    def _save_key(self, key_name: str, value: str):
        """Save API key to config."""
        setattr(self.config, key_name, value)
        if save_config(self.config):
            if self.settings_parent:
                self.settings_parent.notify_saved()
        else:
            # Save failed - show error and revert display to actual saved value
            print(f"ERROR: Failed to save {key_name}")

    def refresh(self):
        """Refresh display from current config values."""
        # Block signals to prevent triggering saves while refreshing
        self.gemini_key.blockSignals(True)
        self.openrouter_key.blockSignals(True)

        self.gemini_key.setText(self.config.gemini_api_key)
        self.openrouter_key.setText(self.config.openrouter_api_key)

        self.gemini_key.blockSignals(False)
        self.openrouter_key.blockSignals(False)


class AudioMicWidget(QWidget):
    """Audio device display and microphone testing section.

    The app always uses the system default microphone (via PipeWire/PulseAudio).
    To change the microphone, update your OS audio settings.
    This widget displays the active microphone and provides a test feature.
    """

    def __init__(self, config: Config, recorder, settings_parent=None, parent=None):
        super().__init__(parent)
        self.config = config
        self.recorder = recorder
        self.settings_parent = settings_parent
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(16, 16, 16, 16)

        # Title
        title = QLabel("Microphone")
        title.setFont(QFont("Sans", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        # Active microphone display (read-only)
        device_group = QGroupBox("Active Input Device")
        device_layout = QVBoxLayout(device_group)
        device_layout.setSpacing(8)

        # Current device label
        self.device_label = QLabel()
        self.device_label.setStyleSheet("""
            QLabel {
                padding: 8px 12px;
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                font-family: monospace;
            }
        """)
        self.device_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        device_layout.addWidget(self.device_label)

        # Refresh button and help text
        button_row = QHBoxLayout()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setFixedWidth(80)
        refresh_btn.setToolTip("Refresh to see the current system default microphone")
        refresh_btn.clicked.connect(self._update_device_display)
        button_row.addWidget(refresh_btn)
        button_row.addStretch()
        device_layout.addLayout(button_row)

        # Help text
        help_label = QLabel(
            "The app uses your system default microphone. "
            "To change it, update your audio settings in System Settings → Sound."
        )
        help_label.setWordWrap(True)
        help_label.setStyleSheet("color: #666; font-size: 11px; margin-top: 4px;")
        device_layout.addWidget(help_label)

        layout.addWidget(device_group)

        # Integrated Mic Test
        mic_test_title = QLabel("Microphone Test")
        mic_test_title.setFont(QFont("Sans", 13, QFont.Weight.Bold))
        mic_test_title.setStyleSheet("margin-top: 12px;")
        layout.addWidget(mic_test_title)

        self.mic_test_widget = MicTestWidget()
        layout.addWidget(self.mic_test_widget)

        layout.addStretch()

        # Initial display update
        self._update_device_display()

    def _update_device_display(self):
        """Update the display to show the current system default microphone."""
        import subprocess

        device_name = "Unknown"

        try:
            # Query PipeWire/PulseAudio for the actual default source
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
                                device_name = line.split("Description:", 1)[1].strip()
                                break
                    if device_name == "Unknown":
                        # Fallback: clean up the source name
                        device_name = source_name
        except Exception:
            # If pactl fails, try to get from PyAudio
            devices = self.recorder.get_input_devices()
            for idx, name in devices:
                if name in ("pulse", "default"):
                    device_name = "System Default (pulse)"
                    break
            else:
                if devices:
                    device_name = devices[0][1]

        self.device_label.setText(device_name)


class BehaviorWidget(QWidget):
    """Behavior settings section."""

    def __init__(self, config: Config, settings_parent=None, parent=None):
        super().__init__(parent)
        self.config = config
        self.settings_parent = settings_parent
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(16, 16, 16, 16)

        # Title
        title = QLabel("Behavior Settings")
        title.setFont(QFont("Sans", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        # Form layout for settings
        form = QFormLayout()
        form.setSpacing(12)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        # VAD
        self.vad_enabled = QCheckBox()
        self.vad_enabled.setChecked(self.config.vad_enabled)
        self.vad_enabled.toggled.connect(lambda v: self._save_bool("vad_enabled", v))
        vad_layout = QVBoxLayout()
        vad_layout.addWidget(self.vad_enabled)
        vad_help = QLabel("Removes silence before transcription (reduces cost)")
        vad_help.setStyleSheet("color: #666; font-size: 10px;")
        vad_layout.addWidget(vad_help)
        form.addRow("Enable VAD:", vad_layout)

        # AGC info (always enabled, not configurable)
        agc_info = QLabel("✓ Automatic Gain Control (AGC) is always enabled to normalize audio levels")
        agc_info.setWordWrap(True)
        agc_info.setStyleSheet("color: #28a745; font-size: 11px; margin: 8px 0;")
        form.addRow("", agc_info)

        # Audio archival
        self.store_audio = QCheckBox()
        self.store_audio.setChecked(self.config.store_audio)
        self.store_audio.toggled.connect(lambda v: self._save_bool("store_audio", v))
        archive_layout = QVBoxLayout()
        archive_layout.addWidget(self.store_audio)
        archive_help = QLabel("Save audio recordings in Opus format (~24kbps)")
        archive_help.setStyleSheet("color: #666; font-size: 10px;")
        archive_layout.addWidget(archive_help)
        form.addRow("Archive Audio:", archive_layout)

        # Audio feedback mode
        audio_feedback_layout = QVBoxLayout()
        self.audio_feedback_mode = QComboBox()
        self.audio_feedback_mode.addItem("Beeps", "beeps")
        self.audio_feedback_mode.addItem("Voice (TTS)", "tts")
        self.audio_feedback_mode.addItem("Silent", "silent")
        # Set current value
        idx = self.audio_feedback_mode.findData(self.config.audio_feedback_mode)
        if idx >= 0:
            self.audio_feedback_mode.setCurrentIndex(idx)
        self.audio_feedback_mode.currentIndexChanged.connect(self._on_audio_feedback_mode_changed)
        audio_feedback_layout.addWidget(self.audio_feedback_mode)
        audio_feedback_help = QLabel("Audio notifications for recording start/stop, transcription complete, etc.")
        audio_feedback_help.setStyleSheet("color: #666; font-size: 10px;")
        audio_feedback_layout.addWidget(audio_feedback_help)
        form.addRow("Audio feedback:", audio_feedback_layout)

        # TTS Voice pack selector (only visible when TTS mode is selected)
        voice_pack_layout = QVBoxLayout()
        self.voice_pack = QComboBox()
        # Import voice packs from config
        from .config import TTS_VOICE_PACKS
        for pack_id, pack_info in TTS_VOICE_PACKS.items():
            self.voice_pack.addItem(f"{pack_info['name']} - {pack_info['description']}", pack_id)
        # Set current value
        idx = self.voice_pack.findData(self.config.tts_voice_pack)
        if idx >= 0:
            self.voice_pack.setCurrentIndex(idx)
        self.voice_pack.currentIndexChanged.connect(self._on_voice_pack_changed)
        voice_pack_layout.addWidget(self.voice_pack)
        voice_pack_help = QLabel("Character voice for TTS announcements (requires Voice mode)")
        voice_pack_help.setStyleSheet("color: #666; font-size: 10px;")
        voice_pack_layout.addWidget(voice_pack_help)
        form.addRow("Voice pack:", voice_pack_layout)

        # Note: Output mode (App Only / Clipboard / Inject) is now on the main recording page

        # Append position (where to insert text in append mode)
        append_pos_layout = QVBoxLayout()
        self.append_position = QComboBox()
        self.append_position.addItem("End of document", "end")
        self.append_position.addItem("At cursor position", "cursor")
        # Set current value
        idx = self.append_position.findData(self.config.append_position)
        if idx >= 0:
            self.append_position.setCurrentIndex(idx)
        self.append_position.currentIndexChanged.connect(self._on_append_position_changed)
        append_pos_layout.addWidget(self.append_position)
        append_pos_help = QLabel("Where to insert text when using append mode (F16/F19 workflow).")
        append_pos_help.setStyleSheet("color: #666; font-size: 10px;")
        append_pos_layout.addWidget(append_pos_help)
        form.addRow("Append position:", append_pos_layout)

        # Duration display mode
        duration_display_layout = QVBoxLayout()
        self.duration_display_mode = QComboBox()
        self.duration_display_mode.addItem("None", "none")
        self.duration_display_mode.addItem("Minutes/Seconds", "mm_ss")
        self.duration_display_mode.addItem("Minutes Only", "minutes_only")
        # Set current value
        idx = self.duration_display_mode.findData(self.config.duration_display_mode)
        if idx >= 0:
            self.duration_display_mode.setCurrentIndex(idx)
        self.duration_display_mode.currentIndexChanged.connect(self._on_duration_display_mode_changed)
        duration_display_layout.addWidget(self.duration_display_mode)
        duration_help = QLabel("MM:SS shows from 0:00, Minutes Only shows from 1m with fade transitions")
        duration_help.setStyleSheet("color: #666; font-size: 10px;")
        duration_display_layout.addWidget(duration_help)
        form.addRow("Duration display:", duration_display_layout)

        layout.addLayout(form)
        layout.addStretch()

    def _save_bool(self, key: str, value: bool):
        """Save boolean config value."""
        setattr(self.config, key, value)
        save_config(self.config)
        if self.settings_parent:
            self.settings_parent.notify_saved()

    def _on_append_position_changed(self, index: int):
        """Save append position setting."""
        value = self.append_position.itemData(index)
        self.config.append_position = value
        save_config(self.config)
        if self.settings_parent:
            self.settings_parent.notify_saved()

    def _on_audio_feedback_mode_changed(self, index: int):
        """Save audio feedback mode setting."""
        old_value = self.config.audio_feedback_mode
        new_value = self.audio_feedback_mode.itemData(index)

        # Play TTS announcement for mode change (before saving, while TTS is still active)
        if old_value == "tts" and new_value != "tts":
            # TTS is being deactivated - announce before changing
            from .tts_announcer import get_announcer
            get_announcer().announce_tts_deactivated()

        self.config.audio_feedback_mode = new_value
        save_config(self.config)
        if self.settings_parent:
            self.settings_parent.notify_saved()

        # Play TTS announcement for mode change (after saving, when TTS is now active)
        if old_value != "tts" and new_value == "tts":
            # TTS is being activated - announce after changing
            from .tts_announcer import get_announcer
            get_announcer().announce_tts_activated()

    def _on_voice_pack_changed(self, index: int):
        """Save voice pack setting and update the announcer."""
        new_value = self.voice_pack.itemData(index)
        self.config.tts_voice_pack = new_value
        save_config(self.config)
        if self.settings_parent:
            self.settings_parent.notify_saved()

        # Update the announcer's voice pack
        from .tts_announcer import set_announcer_voice_pack
        set_announcer_voice_pack(new_value)

        # Play a sample announcement with the new voice (if TTS is active)
        if self.config.audio_feedback_mode == "tts":
            from .tts_announcer import get_announcer
            get_announcer().announce_complete()  # Play "Complete" as a sample

    def _on_duration_display_mode_changed(self, index: int):
        """Save duration display mode setting."""
        self.config.duration_display_mode = self.duration_display_mode.itemData(index)
        save_config(self.config)
        if self.settings_parent:
            self.settings_parent.notify_saved()


class PersonalizationWidget(QWidget):
    """Personalization settings section."""

    def __init__(self, config: Config, settings_parent=None, parent=None):
        super().__init__(parent)
        self.settings_parent = settings_parent
        self.config = config
        self._init_ui()

    def _init_ui(self):
        # Create scrollable area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(16)
        layout.setContentsMargins(16, 16, 16, 16)

        # Title
        title = QLabel("Personalization")
        title.setFont(QFont("Sans", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        desc = QLabel("Configure your identity and email signatures for dictated emails.")
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #666; margin-bottom: 12px;")
        layout.addWidget(desc)

        # Identity Section (grouped like the email sections)
        identity_group = QGroupBox("👤 Identity")
        identity_layout = QFormLayout(identity_group)
        identity_layout.setSpacing(12)

        # Full Name
        self.name_edit = QLineEdit()
        self.name_edit.setText(self.config.user_name)
        self.name_edit.setPlaceholderText("Your full name (e.g., Daniel Rosehill)")
        self.name_edit.textChanged.connect(lambda: self._save_str("user_name", self.name_edit.text()))
        identity_layout.addRow("Full Name:", self.name_edit)

        # Short Name (informal name for friends/family) with inline hint
        short_name_container = QWidget()
        short_name_layout = QVBoxLayout(short_name_container)
        short_name_layout.setContentsMargins(0, 0, 0, 0)
        short_name_layout.setSpacing(2)

        self.short_name_edit = QLineEdit()
        self.short_name_edit.setText(self.config.short_name)
        self.short_name_edit.setPlaceholderText("Informal name (e.g., Daniel)")
        self.short_name_edit.textChanged.connect(lambda: self._save_str("short_name", self.short_name_edit.text()))
        short_name_layout.addWidget(self.short_name_edit)

        short_name_info = QLabel("Used for casual sign-offs like 'Thanks, Daniel'")
        short_name_info.setStyleSheet("color: #888; font-size: 10px;")
        short_name_layout.addWidget(short_name_info)

        identity_layout.addRow("Short Name:", short_name_container)

        layout.addWidget(identity_group)

        # Business Email Section
        business_group = QGroupBox("💼 Business Email")
        business_layout = QFormLayout(business_group)
        business_layout.setSpacing(12)

        self.business_email_edit = QLineEdit()
        self.business_email_edit.setText(self.config.business_email)
        self.business_email_edit.setPlaceholderText("work@company.com")
        self.business_email_edit.textChanged.connect(lambda: self._save_str("business_email", self.business_email_edit.text()))
        business_layout.addRow("Email Address:", self.business_email_edit)

        business_sig_label = QLabel("Signature:")
        business_sig_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.business_signature_edit = QTextEdit()
        self.business_signature_edit.setPlainText(self.config.business_signature)
        self.business_signature_edit.setPlaceholderText("Best regards,\nJohn Doe\nSenior Engineer\nCompany Inc.\nwork@company.com\n+1-555-0100")
        self.business_signature_edit.setMaximumHeight(120)
        self.business_signature_edit.textChanged.connect(lambda: self._save_str("business_signature", self.business_signature_edit.toPlainText()))
        business_layout.addRow(business_sig_label, self.business_signature_edit)

        layout.addWidget(business_group)

        # Personal Email Section
        personal_group = QGroupBox("📧 Personal Email")
        personal_layout = QFormLayout(personal_group)
        personal_layout.setSpacing(12)

        self.personal_email_edit = QLineEdit()
        self.personal_email_edit.setText(self.config.personal_email)
        self.personal_email_edit.setPlaceholderText("personal@example.com")
        self.personal_email_edit.textChanged.connect(lambda: self._save_str("personal_email", self.personal_email_edit.text()))
        personal_layout.addRow("Email Address:", self.personal_email_edit)

        personal_sig_label = QLabel("Signature:")
        personal_sig_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.personal_signature_edit = QTextEdit()
        self.personal_signature_edit.setPlainText(self.config.personal_signature)
        self.personal_signature_edit.setPlaceholderText("Cheers,\nJohn")
        self.personal_signature_edit.setMaximumHeight(120)
        self.personal_signature_edit.textChanged.connect(lambda: self._save_str("personal_signature", self.personal_signature_edit.toPlainText()))
        personal_layout.addRow(personal_sig_label, self.personal_signature_edit)

        layout.addWidget(personal_group)

        layout.addStretch()

        scroll.setWidget(container)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)

    def _save_str(self, key: str, value: str):
        """Save string config value."""
        setattr(self.config, key, value)
        save_config(self.config)
        if self.settings_parent:
            self.settings_parent.notify_saved()


class HotkeysWidget(QWidget):
    """Hotkeys configuration section."""

    # Signal emitted when hotkeys change (so main window can re-register)
    hotkeys_changed = pyqtSignal()

    # Available F-keys for hotkey mapping (F13-F24)
    AVAILABLE_KEYS = [
        ("", "Disabled"),
        ("f13", "F13"),
        ("f14", "F14"),
        ("f15", "F15"),
        ("f16", "F16"),
        ("f17", "F17"),
        ("f18", "F18"),
        ("f19", "F19"),
        ("f20", "F20"),
        ("f21", "F21"),
        ("f22", "F22"),
        ("f23", "F23"),
        ("f24", "F24"),
    ]

    # Hotkey function definitions: (config_field, display_name, description)
    HOTKEY_FUNCTIONS = [
        ("hotkey_toggle", "Toggle", "Start recording / Stop and transcribe"),
        ("hotkey_tap_toggle", "Tap Toggle", "Start recording / Stop and cache (for append mode)"),
        ("hotkey_transcribe", "Transcribe", "Transcribe cached audio only"),
        ("hotkey_clear", "Clear", "Clear cache / Delete recording"),
        ("hotkey_append", "Append", "Start new recording to add to cache"),
        ("hotkey_retake", "Retake", "Discard current and start fresh recording"),
    ]

    def __init__(self, config: Config, settings_parent=None, parent=None):
        super().__init__(parent)
        self.config = config
        self.settings_parent = settings_parent
        self._combos = {}  # Store combo references for updates
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(16, 16, 16, 16)

        # Title
        title = QLabel("Global Hotkeys")
        title.setFont(QFont("Sans", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        desc = QLabel(
            "Configure global hotkeys for macropad or keyboard control. "
            "Use F13-F24 keys to avoid conflicts with other applications. "
            "Changes take effect immediately."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #666; margin-bottom: 12px;")
        layout.addWidget(desc)

        # Hotkey configuration group with two-column layout
        config_group = QGroupBox("Hotkey Mappings")
        columns_layout = QHBoxLayout(config_group)
        columns_layout.setSpacing(24)

        # Split hotkey functions into two columns
        left_functions = self.HOTKEY_FUNCTIONS[:3]  # Toggle, Tap Toggle, Transcribe
        right_functions = self.HOTKEY_FUNCTIONS[3:]  # Clear, Append, Pause

        for column_functions in [left_functions, right_functions]:
            column_form = QFormLayout()
            column_form.setSpacing(12)
            column_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

            for field_name, display_name, description in column_functions:
                # Create combo box for key selection
                combo = QComboBox()
                combo.setMinimumWidth(100)

                # Add available keys
                for key_value, key_display in self.AVAILABLE_KEYS:
                    combo.addItem(key_display, key_value)

                # Set current value from config
                current_value = getattr(self.config, field_name, "").lower()
                idx = combo.findData(current_value)
                if idx >= 0:
                    combo.setCurrentIndex(idx)

                # Connect change handler
                combo.currentIndexChanged.connect(
                    lambda _, f=field_name, c=combo: self._on_hotkey_changed(f, c)
                )

                # Store reference
                self._combos[field_name] = combo

                # Create row with label and description
                row_layout = QVBoxLayout()
                row_layout.setSpacing(2)
                row_layout.addWidget(combo)
                desc_label = QLabel(description)
                desc_label.setStyleSheet("color: #666; font-size: 10px;")
                row_layout.addWidget(desc_label)

                column_form.addRow(f"{display_name}:", row_layout)

            columns_layout.addLayout(column_form)

        layout.addWidget(config_group)

        # Quick reference for workflow
        ref_group = QGroupBox("Workflow Reference")
        ref_layout = QVBoxLayout(ref_group)
        ref_layout.setSpacing(6)

        workflows = [
            ("<b>Simple Workflow:</b> Toggle → Dictate → Toggle (transcribes automatically)", "#495057"),
            ("<b>Append Workflow:</b> Tap Toggle → Dictate → Tap Toggle (caches) → Append → Dictate → Transcribe", "#495057"),
        ]

        for text, color in workflows:
            label = QLabel(text)
            label.setWordWrap(True)
            label.setStyleSheet(f"color: {color}; font-size: 11px; padding: 4px;")
            ref_layout.addWidget(label)

        layout.addWidget(ref_group)

        # Reset to defaults button
        reset_layout = QHBoxLayout()
        reset_layout.addStretch()
        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.setToolTip("Reset all hotkeys to default values (F15-F20)")
        reset_btn.clicked.connect(self._reset_to_defaults)
        reset_layout.addWidget(reset_btn)
        layout.addLayout(reset_layout)

        layout.addStretch()

    def _on_hotkey_changed(self, field_name: str, combo: QComboBox):
        """Handle hotkey selection change."""
        new_value = combo.currentData()

        # Check for duplicate key assignment
        if new_value:  # Only check if not disabled
            for other_field, other_combo in self._combos.items():
                if other_field != field_name and other_combo.currentData() == new_value:
                    # Duplicate found - show warning and clear the other one
                    other_combo.blockSignals(True)
                    other_combo.setCurrentIndex(0)  # Set to "Disabled"
                    other_combo.blockSignals(False)
                    setattr(self.config, other_field, "")

        # Save the new value
        setattr(self.config, field_name, new_value)
        save_config(self.config)
        if self.settings_parent:
            self.settings_parent.notify_saved()

        # Emit signal so main window can re-register hotkeys
        self.hotkeys_changed.emit()

    def _reset_to_defaults(self):
        """Reset all hotkeys to default values."""
        defaults = {
            "hotkey_toggle": "f15",
            "hotkey_tap_toggle": "f16",
            "hotkey_transcribe": "f17",
            "hotkey_clear": "f18",
            "hotkey_append": "f19",
            "hotkey_retake": "f20",
        }

        for field_name, default_value in defaults.items():
            setattr(self.config, field_name, default_value)
            combo = self._combos.get(field_name)
            if combo:
                combo.blockSignals(True)
                idx = combo.findData(default_value)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
                combo.blockSignals(False)

        save_config(self.config)
        if self.settings_parent:
            self.settings_parent.notify_saved()
        self.hotkeys_changed.emit()


class DatabaseWidget(QWidget):
    """Database management section."""

    def __init__(self, config: Config, settings_parent=None, parent=None):
        super().__init__(parent)
        self.config = config
        self.settings_parent = settings_parent
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(16, 16, 16, 16)

        # Title
        title = QLabel("Database Management")
        title.setFont(QFont("Sans", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        desc = QLabel("Manage your transcription history and local data.")
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #666; margin-bottom: 12px;")
        layout.addWidget(desc)

        # Database info
        info_group = QGroupBox("Database Location")
        info_layout = QVBoxLayout(info_group)

        from pathlib import Path
        config_dir = Path.home() / ".config" / "voice-notepad-v3"

        path_label = QLabel(str(config_dir / "mongita"))
        path_label.setStyleSheet("font-family: monospace; color: #495057; padding: 8px;")
        path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        info_layout.addWidget(path_label)

        layout.addWidget(info_group)

        # Management actions
        actions_group = QGroupBox("Actions")
        actions_layout = QVBoxLayout(actions_group)
        actions_layout.setSpacing(8)

        # Export button
        export_btn = QPushButton("Export Database")
        export_btn.setToolTip("Export all transcriptions to JSON")
        export_btn.clicked.connect(self._export_database)
        actions_layout.addWidget(export_btn)

        # Clear history button
        clear_btn = QPushButton("Clear All History")
        clear_btn.setToolTip("Delete all transcription history")
        clear_btn.setStyleSheet("background-color: #dc3545; color: white;")
        clear_btn.clicked.connect(self._clear_history)
        actions_layout.addWidget(clear_btn)

        layout.addWidget(actions_group)
        layout.addStretch()

    def _export_database(self):
        """Export database to JSON."""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Database",
            "voice-notepad-export.json",
            "JSON Files (*.json)"
        )
        if file_path:
            try:
                from .database_mongo import get_db
                import json

                db = get_db()
                transcriptions = list(db["transcriptions"].find({}))

                # Convert ObjectId to string
                for t in transcriptions:
                    if "_id" in t:
                        t["_id"] = str(t["_id"])

                with open(file_path, "w") as f:
                    json.dump(transcriptions, f, indent=2, default=str)

                QMessageBox.information(
                    self,
                    "Export Complete",
                    f"Exported {len(transcriptions)} transcriptions to {file_path}"
                )
            except Exception as e:
                QMessageBox.critical(self, "Export Failed", f"Error: {e}")

    def _clear_history(self):
        """Clear all transcription history."""
        from .database_mongo import get_db

        db = get_db()
        total_count = db.get_total_count()

        if total_count == 0:
            QMessageBox.information(
                self,
                "No History",
                "There are no transcriptions to delete.",
            )
            return

        reply = QMessageBox.warning(
            self,
            "Delete All History",
            f"Are you sure you want to delete ALL {total_count} transcriptions?\n\n"
            "This will permanently delete:\n"
            "• All transcript text\n"
            "• All archived audio files\n"
            "• All metadata and statistics\n\n"
            "THIS CANNOT BE UNDONE!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                deleted_count = db.delete_all()
                db.vacuum()
                QMessageBox.information(
                    self,
                    "History Cleared",
                    f"Successfully deleted {deleted_count} transcriptions.\n\n"
                    "Database has been optimized to reclaim disk space.",
                )
            except Exception as e:
                QMessageBox.critical(self, "Clear Failed", f"Error: {e}")


class ModelSelectionWidget(QWidget):
    """Model and provider selection section."""

    def __init__(self, config: Config, settings_parent=None, parent=None):
        super().__init__(parent)
        self.config = config
        self.settings_parent = settings_parent
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(16, 16, 16, 16)

        # Title
        title = QLabel("Model")
        title.setFont(QFont("Sans", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        desc = QLabel(
            "Choose your transcription provider and model. "
            "Once you find a model that works within your budget, you typically won't need to change it often."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #666; margin-bottom: 12px;")
        layout.addWidget(desc)

        # Provider and model selection
        selection_group = QGroupBox("Provider & Model")
        selection_layout = QVBoxLayout(selection_group)
        selection_layout.setSpacing(12)

        # Provider selection
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
            icon = get_provider_icon(provider_key)
            self.provider_combo.addItem(icon, display_name)

        # Set current provider
        provider_map = {
            "gemini": "Google Gemini (Recommended)",
            "openrouter": "OpenRouter",
        }
        provider_display = provider_map.get(self.config.selected_provider, self.config.selected_provider.title())
        self.provider_combo.setCurrentText(provider_display)
        self.provider_combo.currentTextChanged.connect(self._on_provider_changed)
        provider_layout.addWidget(self.provider_combo, 1)

        selection_layout.addLayout(provider_layout)

        # Model selection
        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel("Model:"))

        self.model_combo = QComboBox()
        self.model_combo.setIconSize(QSize(16, 16))
        self._update_model_combo()
        self.model_combo.currentIndexChanged.connect(self._on_model_changed)
        model_layout.addWidget(self.model_combo, 1)

        selection_layout.addLayout(model_layout)

        # Model tier quick toggle (Standard / Budget)
        tier_layout = QHBoxLayout()
        tier_layout.addWidget(QLabel("Quick Select:"))

        self.standard_btn = QPushButton("Standard")
        self.standard_btn.setCheckable(True)
        self.standard_btn.setMinimumWidth(80)
        self.standard_btn.clicked.connect(lambda: self._set_model_tier("standard"))

        self.budget_btn = QPushButton("Budget")
        self.budget_btn.setCheckable(True)
        self.budget_btn.setMinimumWidth(80)
        self.budget_btn.clicked.connect(lambda: self._set_model_tier("budget"))

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

        selection_layout.addLayout(tier_layout)

        # Model explanation box
        info_frame = QFrame()
        info_frame.setFrameShape(QFrame.Shape.StyledPanel)
        info_frame.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 6px;
                padding: 8px;
            }
        """)
        info_layout = QVBoxLayout(info_frame)
        info_layout.setContentsMargins(12, 10, 12, 10)
        info_layout.setSpacing(6)

        info_text = QLabel(
            "<b>Gemini Flash (Latest)</b> is a dynamic endpoint that points to the latest "
            "Flash variant operated by Google.<br><br>"
            "The <b>Budget</b> selector chooses Flash Lite for lower cost, but the regular "
            "model is strongly recommended.<br><br>"
            "<b>Pro</b> is also available but does not significantly improve transcript quality "
            "in my experience."
        )
        info_text.setWordWrap(True)
        info_text.setStyleSheet("color: #495057; font-size: 11px; background: transparent; border: none;")
        info_layout.addWidget(info_text)

        selection_layout.addWidget(info_frame)

        # Set Default button
        default_layout = QHBoxLayout()
        default_layout.addStretch()
        self.default_btn = QPushButton("Set Default")
        self.default_btn.setToolTip("Reset to Gemini Flash (Latest)")
        self.default_btn.setFixedWidth(100)
        self.default_btn.clicked.connect(self._set_default)
        default_layout.addWidget(self.default_btn)
        selection_layout.addLayout(default_layout)

        # Update tier button states
        self._update_tier_buttons()

        layout.addWidget(selection_group)

        # ==========================================================================
        # PRIMARY & FALLBACK SECTION
        # ==========================================================================
        presets_group = QGroupBox("Primary & Fallback Models")
        presets_layout = QVBoxLayout(presets_group)
        presets_layout.setSpacing(12)

        presets_desc = QLabel(
            "Configure your primary and fallback models. If failover is enabled, "
            "the fallback model is used automatically when the primary fails."
        )
        presets_desc.setWordWrap(True)
        presets_desc.setStyleSheet("color: #666; font-size: 11px; margin-bottom: 8px;")
        presets_layout.addWidget(presets_desc)

        # Provider recommendation note
        provider_note_frame = QFrame()
        provider_note_frame.setFrameShape(QFrame.Shape.StyledPanel)
        provider_note_frame.setStyleSheet("""
            QFrame {
                background-color: #fff3cd;
                border: 1px solid #ffc107;
                border-radius: 4px;
            }
        """)
        provider_note_layout = QHBoxLayout(provider_note_frame)
        provider_note_layout.setContentsMargins(10, 8, 10, 8)
        provider_note_icon = QLabel("💡")
        provider_note_icon.setStyleSheet("background: transparent; border: none; font-size: 14px;")
        provider_note_layout.addWidget(provider_note_icon)
        provider_note_text = QLabel(
            "<b>Tip:</b> For maximum resilience, use different providers for primary and fallback. "
            "This protects against provider-level outages."
        )
        provider_note_text.setWordWrap(True)
        provider_note_text.setStyleSheet("background: transparent; border: none; color: #856404; font-size: 11px;")
        provider_note_layout.addWidget(provider_note_text, 1)
        presets_layout.addWidget(provider_note_frame)

        # Failover checkbox
        self.failover_checkbox = QCheckBox("Enable automatic failover")
        self.failover_checkbox.setToolTip(
            "When enabled, if transcription fails with the primary model, "
            "the app will automatically retry with the fallback model."
        )
        self.failover_checkbox.setChecked(self.config.failover_enabled)
        self.failover_checkbox.stateChanged.connect(self._on_failover_changed)
        presets_layout.addWidget(self.failover_checkbox)

        # Store references for preset UI elements
        self._preset_widgets = {}

        # Style for preset frames
        preset_frame_style = """
            QFrame {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 4px;
            }
        """

        # Horizontal container for Primary and Fallback side by side
        presets_row = QHBoxLayout()
        presets_row.setSpacing(12)

        # Create Primary and Fallback sections side by side
        for preset_key in ["primary", "fallback"]:
            preset_frame = QFrame()
            preset_frame.setFrameShape(QFrame.Shape.StyledPanel)
            preset_frame.setStyleSheet(preset_frame_style)
            preset_inner_layout = QVBoxLayout(preset_frame)
            preset_inner_layout.setSpacing(8)
            preset_inner_layout.setContentsMargins(10, 8, 10, 8)

            # Preset header
            header_text = "Primary" if preset_key == "primary" else "Fallback"
            preset_header = QLabel(header_text)
            preset_header.setStyleSheet("font-size: 13px; font-weight: bold; background: transparent; border: none;")
            preset_inner_layout.addWidget(preset_header)

            # Name field
            name_edit = QLineEdit()
            name_edit.setPlaceholderText("Display name...")
            current_name = getattr(self.config, f"{preset_key}_name", "")
            name_edit.setText(current_name)
            name_edit.textChanged.connect(lambda text, k=preset_key: self._on_preset_name_changed(k, text))
            preset_inner_layout.addWidget(name_edit)

            # Provider dropdown
            provider_combo = QComboBox()
            provider_combo.setIconSize(QSize(16, 16))
            provider_combo.addItem(get_provider_icon("google"), "Google Gemini", "gemini")
            provider_combo.addItem(get_provider_icon("openrouter"), "OpenRouter", "openrouter")
            current_provider = getattr(self.config, f"{preset_key}_provider", "") or "gemini"
            idx = provider_combo.findData(current_provider)
            if idx >= 0:
                provider_combo.setCurrentIndex(idx)
            provider_combo.currentIndexChanged.connect(lambda idx, k=preset_key: self._on_preset_provider_changed(k))
            preset_inner_layout.addWidget(provider_combo)

            # Model dropdown
            model_combo = QComboBox()
            model_combo.setIconSize(QSize(16, 16))
            model_combo.currentIndexChanged.connect(lambda idx, k=preset_key: self._on_preset_model_changed(k))
            preset_inner_layout.addWidget(model_combo)

            # Store widget references
            self._preset_widgets[preset_key] = {
                "name": name_edit,
                "provider": provider_combo,
                "model": model_combo,
            }

            # Add to horizontal row (both get equal space)
            presets_row.addWidget(preset_frame, 1)

            # Populate model dropdown based on current provider
            self._update_preset_model_combo(preset_key)

        presets_layout.addLayout(presets_row)

        # Swap button
        swap_layout = QHBoxLayout()
        swap_layout.addStretch()
        self.swap_btn = QPushButton("⇅ Swap Primary & Fallback")
        self.swap_btn.setToolTip("Exchange the primary and fallback configurations")
        self.swap_btn.clicked.connect(self._swap_presets)
        swap_layout.addWidget(self.swap_btn)
        swap_layout.addStretch()
        presets_layout.addLayout(swap_layout)

        layout.addWidget(presets_group)
        layout.addStretch()

    def _update_model_combo(self):
        """Update the model dropdown based on selected provider."""
        self.model_combo.blockSignals(True)
        self.model_combo.clear()

        provider = self.config.selected_provider.lower()
        if provider == "gemini":
            models = GEMINI_MODELS
            current_model = self.config.gemini_model
        else:  # openrouter
            models = OPENROUTER_MODELS
            current_model = self.config.openrouter_model

        # Add models with model originator icon
        for model_id, display_name in models:
            model_icon = get_model_icon(model_id)
            self.model_combo.addItem(model_icon, display_name, model_id)

        # Select current model
        idx = self.model_combo.findData(current_model)
        if idx >= 0:
            self.model_combo.setCurrentIndex(idx)

        self.model_combo.blockSignals(False)

    def _on_provider_changed(self, provider_display: str):
        """Handle provider change."""
        display_to_internal = {
            "Google Gemini (Recommended)": "gemini",
            "OpenRouter": "openrouter",
        }
        self.config.selected_provider = display_to_internal.get(provider_display, "gemini")
        self._update_model_combo()
        self._update_tier_buttons()
        save_config(self.config)
        if self.settings_parent:
            self.settings_parent.notify_saved()

    def _on_model_changed(self, index: int):
        """Handle model selection change."""
        if index < 0:
            return
        model_id = self.model_combo.currentData()
        provider = self.config.selected_provider.lower()

        if provider == "gemini":
            self.config.gemini_model = model_id
        else:  # openrouter
            self.config.openrouter_model = model_id

        save_config(self.config)
        if self.settings_parent:
            self.settings_parent.notify_saved()
        self._update_tier_buttons()

    def _set_model_tier(self, tier: str):
        """Set the model to the standard or budget tier for the current provider."""
        provider = self.config.selected_provider.lower()
        tiers = MODEL_TIERS.get(provider, {})
        model_id = tiers.get(tier)

        if model_id:
            idx = self.model_combo.findData(model_id)
            if idx >= 0:
                self.model_combo.setCurrentIndex(idx)

    def _update_tier_buttons(self):
        """Update tier button checked states based on current model."""
        provider = self.config.selected_provider.lower()
        tiers = MODEL_TIERS.get(provider, {})
        current_model = self.model_combo.currentData()

        self.standard_btn.blockSignals(True)
        self.budget_btn.blockSignals(True)

        self.standard_btn.setChecked(current_model == tiers.get("standard"))
        self.budget_btn.setChecked(current_model == tiers.get("budget"))

        self.standard_btn.blockSignals(False)
        self.budget_btn.blockSignals(False)

    def _set_default(self):
        """Reset to default: Gemini provider with gemini-flash-latest model."""
        # Set provider to Gemini
        self.provider_combo.setCurrentText("Google Gemini (Recommended)")
        self.config.selected_provider = "gemini"

        # Set model to gemini-flash-latest
        self._update_model_combo()
        idx = self.model_combo.findData("gemini-flash-latest")
        if idx >= 0:
            self.model_combo.setCurrentIndex(idx)
        self.config.gemini_model = "gemini-flash-latest"

        save_config(self.config)
        if self.settings_parent:
            self.settings_parent.notify_saved()
        self._update_tier_buttons()

    # ==========================================================================
    # PRESET (PRIMARY/FALLBACK) HANDLERS
    # ==========================================================================

    def _on_failover_changed(self, state: int):
        """Handle failover checkbox change."""
        self.config.failover_enabled = state == 2  # Qt.CheckState.Checked = 2
        save_config(self.config)
        if self.settings_parent:
            self.settings_parent.notify_saved()

    def _on_preset_name_changed(self, preset_key: str, text: str):
        """Handle preset name change."""
        setattr(self.config, f"{preset_key}_name", text)
        save_config(self.config)
        if self.settings_parent:
            self.settings_parent.notify_saved()

    def _on_preset_provider_changed(self, preset_key: str):
        """Handle preset provider change."""
        widgets = self._preset_widgets.get(preset_key)
        if not widgets:
            return
        provider = widgets["provider"].currentData()
        setattr(self.config, f"{preset_key}_provider", provider)
        self._update_preset_model_combo(preset_key)
        save_config(self.config)
        if self.settings_parent:
            self.settings_parent.notify_saved()

    def _on_preset_model_changed(self, preset_key: str):
        """Handle preset model change."""
        widgets = self._preset_widgets.get(preset_key)
        if not widgets:
            return
        model = widgets["model"].currentData()
        if model:  # Only save if valid model selected
            setattr(self.config, f"{preset_key}_model", model)
            save_config(self.config)
            if self.settings_parent:
                self.settings_parent.notify_saved()

    def _update_preset_model_combo(self, preset_key: str):
        """Update the model dropdown for a preset based on its provider."""
        widgets = self._preset_widgets.get(preset_key)
        if not widgets:
            return

        model_combo = widgets["model"]
        provider_combo = widgets["provider"]

        model_combo.blockSignals(True)
        model_combo.clear()

        provider = provider_combo.currentData() or "gemini"
        if provider == "gemini":
            models = GEMINI_MODELS
        else:
            models = OPENROUTER_MODELS

        # Add models with icons
        for model_id, display_name in models:
            model_icon = get_model_icon(model_id)
            model_combo.addItem(model_icon, display_name, model_id)

        # Select current model if set
        current_model = getattr(self.config, f"{preset_key}_model", "")
        if current_model:
            idx = model_combo.findData(current_model)
            if idx >= 0:
                model_combo.setCurrentIndex(idx)

        model_combo.blockSignals(False)

    def _swap_presets(self):
        """Swap primary and fallback configurations."""
        # Store current primary values
        old_primary_name = self.config.primary_name
        old_primary_provider = self.config.primary_provider
        old_primary_model = self.config.primary_model

        # Move fallback to primary
        self.config.primary_name = self.config.fallback_name
        self.config.primary_provider = self.config.fallback_provider
        self.config.primary_model = self.config.fallback_model

        # Move old primary to fallback
        self.config.fallback_name = old_primary_name
        self.config.fallback_provider = old_primary_provider
        self.config.fallback_model = old_primary_model

        # Save config
        save_config(self.config)
        if self.settings_parent:
            self.settings_parent.notify_saved()

        # Update UI widgets
        for preset_key in ["primary", "fallback"]:
            widgets = self._preset_widgets.get(preset_key)
            if widgets:
                # Update name field
                widgets["name"].blockSignals(True)
                widgets["name"].setText(getattr(self.config, f"{preset_key}_name", ""))
                widgets["name"].blockSignals(False)

                # Update provider dropdown
                widgets["provider"].blockSignals(True)
                provider = getattr(self.config, f"{preset_key}_provider", "gemini")
                idx = widgets["provider"].findData(provider)
                if idx >= 0:
                    widgets["provider"].setCurrentIndex(idx)
                widgets["provider"].blockSignals(False)

                # Update model dropdown
                self._update_preset_model_combo(preset_key)


class TranslationWidget(QWidget):
    """Translation mode configuration section."""

    # Signal emitted when translation settings change
    translation_changed = pyqtSignal()

    def __init__(self, config: Config, settings_parent=None, parent=None):
        super().__init__(parent)
        self.config = config
        self.settings_parent = settings_parent
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(16, 16, 16, 16)

        # Title
        title = QLabel("Translation Mode")
        title.setFont(QFont("Sans", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        desc = QLabel(
            "When Translation Mode is enabled, transcriptions are automatically "
            "translated to your target language after cleanup."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #666; margin-bottom: 12px;")
        layout.addWidget(desc)

        # Enable translation mode checkbox
        self.translation_enabled = QCheckBox("Enable Translation Mode")
        self.translation_enabled.setChecked(self.config.translation_mode_enabled)
        self.translation_enabled.setStyleSheet("font-weight: bold; font-size: 13px;")
        self.translation_enabled.toggled.connect(self._on_enabled_changed)
        layout.addWidget(self.translation_enabled)

        # Language settings group
        lang_group = QGroupBox("Language Settings")
        lang_layout = QFormLayout(lang_group)
        lang_layout.setSpacing(12)
        lang_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        # Source language dropdown (for future use, currently just shows auto-detect)
        source_layout = QVBoxLayout()
        self.source_language = QComboBox()
        self.source_language.setMinimumWidth(250)
        self.source_language.setIconSize(QSize(20, 20))

        # Add languages with flags
        for code, name, flag in TRANSLATION_LANGUAGES:
            self.source_language.addItem(f"{flag}  {name}", code)

        # Set current value
        idx = self.source_language.findData(self.config.translation_source_language)
        if idx >= 0:
            self.source_language.setCurrentIndex(idx)
        self.source_language.currentIndexChanged.connect(self._on_source_changed)

        source_layout.addWidget(self.source_language)
        source_help = QLabel("The language of your speech (Auto-detect recommended)")
        source_help.setStyleSheet("color: #666; font-size: 10px;")
        source_layout.addWidget(source_help)
        lang_layout.addRow("Source Language:", source_layout)

        # Target language dropdown
        target_layout = QVBoxLayout()
        self.target_language = QComboBox()
        self.target_language.setMinimumWidth(250)
        self.target_language.setIconSize(QSize(20, 20))

        # Add languages with flags (skip auto-detect for target)
        for code, name, flag in TRANSLATION_LANGUAGES:
            if code != "auto":  # Don't include auto-detect as target
                self.target_language.addItem(f"{flag}  {name}", code)

        # Set current value
        idx = self.target_language.findData(self.config.translation_target_language)
        if idx >= 0:
            self.target_language.setCurrentIndex(idx)
        self.target_language.currentIndexChanged.connect(self._on_target_changed)

        target_layout.addWidget(self.target_language)
        target_help = QLabel("The language your transcription will be translated into")
        target_help.setStyleSheet("color: #666; font-size: 10px;")
        target_layout.addWidget(target_help)
        lang_layout.addRow("Target Language:", target_layout)

        layout.addWidget(lang_group)

        # Info frame
        info_frame = QFrame()
        info_frame.setFrameShape(QFrame.Shape.StyledPanel)
        info_frame.setStyleSheet("""
            QFrame {
                background-color: #e7f3ff;
                border: 1px solid #b6d4fe;
                border-radius: 6px;
            }
        """)
        info_layout = QHBoxLayout(info_frame)
        info_layout.setContentsMargins(12, 10, 12, 10)
        info_icon = QLabel("💡")
        info_icon.setStyleSheet("background: transparent; border: none; font-size: 16px;")
        info_layout.addWidget(info_icon)
        info_text = QLabel(
            "<b>How it works:</b> When Translation Mode is enabled, the transcription "
            "will be cleaned up as usual, then the entire output will be translated "
            "to your target language. The translation happens in a single API call."
        )
        info_text.setWordWrap(True)
        info_text.setStyleSheet("background: transparent; border: none; color: #084298; font-size: 11px;")
        info_layout.addWidget(info_text, 1)
        layout.addWidget(info_frame)

        # Current status indicator
        self.status_frame = QFrame()
        self.status_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self._update_status_frame()
        layout.addWidget(self.status_frame)

        layout.addStretch()

    def _update_status_frame(self):
        """Update the status indicator frame."""
        if self.config.translation_mode_enabled:
            target_name = get_language_display_name(self.config.translation_target_language)
            target_flag = get_language_flag(self.config.translation_target_language)
            self.status_frame.setStyleSheet("""
                QFrame {
                    background-color: #d1e7dd;
                    border: 1px solid #badbcc;
                    border-radius: 6px;
                }
            """)

            # Clear and rebuild layout
            layout = self.status_frame.layout()
            if layout is None:
                layout = QHBoxLayout(self.status_frame)
                layout.setContentsMargins(12, 10, 12, 10)
            else:
                # Clear existing widgets
                while layout.count():
                    child = layout.takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()

            status_icon = QLabel(target_flag)
            status_icon.setStyleSheet("background: transparent; border: none; font-size: 24px;")
            layout.addWidget(status_icon)

            status_text = QLabel(f"<b>Translation Active:</b> Translating to {target_name}")
            status_text.setStyleSheet("background: transparent; border: none; color: #0f5132; font-size: 12px;")
            layout.addWidget(status_text, 1)
        else:
            self.status_frame.setStyleSheet("""
                QFrame {
                    background-color: #f8f9fa;
                    border: 1px solid #dee2e6;
                    border-radius: 6px;
                }
            """)

            # Clear and rebuild layout
            layout = self.status_frame.layout()
            if layout is None:
                layout = QHBoxLayout(self.status_frame)
                layout.setContentsMargins(12, 10, 12, 10)
            else:
                # Clear existing widgets
                while layout.count():
                    child = layout.takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()

            status_icon = QLabel("🌐")
            status_icon.setStyleSheet("background: transparent; border: none; font-size: 24px;")
            layout.addWidget(status_icon)

            status_text = QLabel("<b>Translation Disabled:</b> Transcriptions will not be translated")
            status_text.setStyleSheet("background: transparent; border: none; color: #495057; font-size: 12px;")
            layout.addWidget(status_text, 1)

    def _on_enabled_changed(self, checked: bool):
        """Handle translation mode toggle."""
        self.config.translation_mode_enabled = checked
        save_config(self.config)
        self._update_status_frame()
        if self.settings_parent:
            self.settings_parent.notify_saved()
        self.translation_changed.emit()

    def _on_source_changed(self, index: int):
        """Handle source language change."""
        self.config.translation_source_language = self.source_language.currentData()
        save_config(self.config)
        if self.settings_parent:
            self.settings_parent.notify_saved()
        self.translation_changed.emit()

    def _on_target_changed(self, index: int):
        """Handle target language change."""
        self.config.translation_target_language = self.target_language.currentData()
        save_config(self.config)
        self._update_status_frame()
        if self.settings_parent:
            self.settings_parent.notify_saved()
        self.translation_changed.emit()


class MiscWidget(QWidget):
    """Miscellaneous settings section."""

    def __init__(self, config: Config, settings_parent=None, parent=None):
        super().__init__(parent)
        self.config = config
        self.settings_parent = settings_parent
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(16, 16, 16, 16)

        # Title
        title = QLabel("Miscellaneous Settings")
        title.setFont(QFont("Sans", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        desc = QLabel("Additional options and optimizations.")
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #666; margin-bottom: 12px;")
        layout.addWidget(desc)

        # Prompt Optimization group
        optimization_group = QGroupBox("Prompt Optimization")
        optimization_layout = QVBoxLayout(optimization_group)
        optimization_layout.setSpacing(12)

        # Short audio prompt setting
        self.short_audio_prompt_enabled = QCheckBox("Short Audio Prompt Shortening")
        self.short_audio_prompt_enabled.setChecked(self.config.short_audio_prompt_enabled)
        self.short_audio_prompt_enabled.toggled.connect(
            lambda v: self._save_bool("short_audio_prompt_enabled", v)
        )

        short_audio_layout = QVBoxLayout()
        short_audio_layout.addWidget(self.short_audio_prompt_enabled)

        # Detailed help text
        help_text = QLabel(
            "When enabled, recordings under 30 seconds use a minimal cleanup prompt "
            "instead of the full prompt. This reduces API overhead by ~93% "
            "(~300 chars vs ~4,300 chars) for quick notes."
        )
        help_text.setWordWrap(True)
        help_text.setStyleSheet("color: #666; font-size: 11px; margin-left: 20px;")
        short_audio_layout.addWidget(help_text)

        # Warning/note about trade-off
        note_frame = QFrame()
        note_frame.setFrameShape(QFrame.Shape.StyledPanel)
        note_frame.setStyleSheet("""
            QFrame {
                background-color: #fff3cd;
                border: 1px solid #ffc107;
                border-radius: 4px;
                margin-top: 8px;
                margin-left: 20px;
            }
        """)
        note_layout = QHBoxLayout(note_frame)
        note_layout.setContentsMargins(10, 8, 10, 8)
        note_icon = QLabel("💡")
        note_icon.setStyleSheet("background: transparent; border: none; font-size: 14px;")
        note_layout.addWidget(note_icon)
        note_text = QLabel(
            "<b>Trade-off:</b> The minimal prompt applies only essential cleanup "
            "(punctuation, filler removal, grammar). Format presets, advanced options, "
            "and custom instructions are not applied to short recordings."
        )
        note_text.setWordWrap(True)
        note_text.setStyleSheet("background: transparent; border: none; color: #856404; font-size: 11px;")
        note_layout.addWidget(note_text, 1)
        short_audio_layout.addWidget(note_frame)

        optimization_layout.addLayout(short_audio_layout)
        layout.addWidget(optimization_group)

        # Balance Polling group (OpenRouter)
        polling_group = QGroupBox("OpenRouter Balance Polling")
        polling_layout = QVBoxLayout(polling_group)
        polling_layout.setSpacing(12)

        polling_desc = QLabel(
            "How often to check your OpenRouter balance in the background. "
            "This runs independently of transcriptions to minimize latency."
        )
        polling_desc.setWordWrap(True)
        polling_desc.setStyleSheet("color: #666; font-size: 11px;")
        polling_layout.addWidget(polling_desc)

        # Polling interval dropdown
        interval_row = QHBoxLayout()
        interval_label = QLabel("Poll interval:")
        self.polling_interval_combo = QComboBox()
        self.polling_interval_combo.addItems(["15 minutes", "30 minutes", "60 minutes"])

        # Set current value
        current_interval = getattr(self.config, 'balance_poll_interval_minutes', 30)
        interval_map = {15: 0, 30: 1, 60: 2}
        self.polling_interval_combo.setCurrentIndex(interval_map.get(current_interval, 1))

        self.polling_interval_combo.currentIndexChanged.connect(self._save_polling_interval)

        interval_row.addWidget(interval_label)
        interval_row.addWidget(self.polling_interval_combo)
        interval_row.addStretch()
        polling_layout.addLayout(interval_row)

        layout.addWidget(polling_group)

        layout.addStretch()

    def _save_bool(self, key: str, value: bool):
        """Save boolean config value."""
        setattr(self.config, key, value)
        save_config(self.config)
        if self.settings_parent:
            self.settings_parent.notify_saved()

    def _save_polling_interval(self, index: int):
        """Save the balance polling interval setting."""
        interval_values = [15, 30, 60]
        self.config.balance_poll_interval_minutes = interval_values[index]
        save_config(self.config)
        if self.settings_parent:
            self.settings_parent.notify_saved()
            # Restart the polling timer with new interval
            main_window = self.settings_parent.parent()
            if main_window and hasattr(main_window, '_start_balance_polling'):
                main_window._start_balance_polling()


class SettingsWidget(QWidget):
    """Unified settings widget with tabbed sections."""

    # Signal emitted when hotkeys are changed
    hotkeys_changed = pyqtSignal()

    # Signal emitted when any setting is saved
    settings_saved = pyqtSignal()

    def __init__(self, config: Config, recorder, parent=None):
        super().__init__(parent)
        self.config = config
        self.recorder = recorder
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Create tab widget for settings sections
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        # Add sections as tabs - pass self as settings_parent for toast notifications
        # Icons help users quickly identify tabs
        # Keep references to widgets that need refresh support
        self.model_widget = ModelSelectionWidget(self.config, settings_parent=self)
        self.tabs.addTab(self.model_widget, "🤖 Model")

        self.api_keys_widget = APIKeysWidget(self.config, settings_parent=self)
        self.tabs.addTab(self.api_keys_widget, "🔑 API Keys")

        self.tabs.addTab(AudioMicWidget(self.config, self.recorder, settings_parent=self), "🎤 Mic")
        self.tabs.addTab(BehaviorWidget(self.config, settings_parent=self), "⚙️ Behavior")
        self.tabs.addTab(PersonalizationWidget(self.config, settings_parent=self), "👤 Personal")

        # Translation tab
        self.translation_widget = TranslationWidget(self.config, settings_parent=self)
        self.tabs.addTab(self.translation_widget, "🌐 Translation")

        # Hotkeys tab - connect signal to propagate changes
        self.hotkeys_widget = HotkeysWidget(self.config, settings_parent=self)
        self.hotkeys_widget.hotkeys_changed.connect(self.hotkeys_changed.emit)
        self.tabs.addTab(self.hotkeys_widget, "⌨️ Hotkeys")

        self.tabs.addTab(MiscWidget(self.config, settings_parent=self), "🔧 Misc")
        self.tabs.addTab(DatabaseWidget(self.config, settings_parent=self), "💾 Database")

        layout.addWidget(self.tabs)

    def notify_saved(self):
        """Notify that settings were saved (called by child widgets)."""
        self.settings_saved.emit()

    def refresh(self):
        """Refresh all sub-widgets to show current config values."""
        # Refresh API keys widget to ensure it shows current saved values
        if hasattr(self, 'api_keys_widget'):
            self.api_keys_widget.refresh()


class SettingsDialog(QDialog):
    """Settings dialog window containing the settings widget."""

    # Signal emitted when settings dialog is closed (settings may have changed)
    settings_closed = pyqtSignal()

    # Signal emitted when hotkeys are changed (for immediate re-registration)
    hotkeys_changed = pyqtSignal()

    def __init__(self, config: Config, recorder, parent=None):
        super().__init__(parent)
        self.config = config
        self.recorder = recorder
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle("Settings")
        self.setMinimumSize(780, 620)
        self.resize(820, 680)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Embed the settings widget
        self.settings_widget = SettingsWidget(self.config, self.recorder, self)
        self.settings_widget.hotkeys_changed.connect(self.hotkeys_changed.emit)
        self.settings_widget.settings_saved.connect(self._show_saved_toast)
        layout.addWidget(self.settings_widget)

        # Bottom bar with toast area and close button
        bottom_bar = QHBoxLayout()
        bottom_bar.setContentsMargins(16, 8, 16, 12)

        # Toast notification (hidden by default)
        self.toast = SettingsToast(self)
        bottom_bar.addWidget(self.toast)

        bottom_bar.addStretch()

        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        close_btn.setFixedWidth(80)
        bottom_bar.addWidget(close_btn)

        layout.addLayout(bottom_bar)

    def _show_saved_toast(self):
        """Show the 'Settings saved' toast notification."""
        self.toast.show_message("Settings saved")

    def refresh(self):
        """Refresh the settings widget."""
        self.settings_widget.refresh()

    def closeEvent(self, event):
        """Emit signal when dialog is closed."""
        self.settings_closed.emit()
        super().closeEvent(event)
