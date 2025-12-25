"""Unified Settings widget combining all configuration options."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTabWidget,
    QLineEdit, QCheckBox, QComboBox, QGroupBox, QFormLayout,
    QPushButton, QSpinBox, QFrame, QMessageBox, QFileDialog,
    QTextEdit, QScrollArea, QDialog, QDialogButtonBox,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from .config import (
    Config, save_config, load_env_keys,
    GEMINI_MODELS, OPENROUTER_MODELS,
    MODEL_TIERS,
)
from .mic_test_widget import MicTestWidget
from PyQt6.QtCore import QSize
from PyQt6.QtGui import QIcon
from pathlib import Path


class APIKeysWidget(QWidget):
    """API Keys configuration section."""

    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        self.config = config
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
        save_config(self.config)


class AudioMicWidget(QWidget):
    """Audio device and microphone testing section."""

    def __init__(self, config: Config, recorder, parent=None):
        super().__init__(parent)
        self.config = config
        self.recorder = recorder
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(16, 16, 16, 16)

        # Title
        title = QLabel("Mic")
        title.setFont(QFont("Sans", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        # Audio device selection
        device_group = QGroupBox("Input Device")
        device_layout = QFormLayout(device_group)
        device_layout.setSpacing(12)

        self.device_combo = QComboBox()
        self.device_combo.currentIndexChanged.connect(self._on_device_changed)
        self._populate_devices()

        device_row = QHBoxLayout()
        device_row.addWidget(self.device_combo, 1)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setFixedWidth(80)
        refresh_btn.clicked.connect(self._populate_devices)
        device_row.addWidget(refresh_btn)

        device_layout.addRow("Microphone:", device_row)
        layout.addWidget(device_group)

        # Integrated Mic Test
        mic_test_title = QLabel("Microphone Test")
        mic_test_title.setFont(QFont("Sans", 13, QFont.Weight.Bold))
        mic_test_title.setStyleSheet("margin-top: 12px;")
        layout.addWidget(mic_test_title)

        self.mic_test_widget = MicTestWidget()
        layout.addWidget(self.mic_test_widget)

        layout.addStretch()

    def _populate_devices(self):
        """Populate device dropdown."""
        self.device_combo.clear()
        self.device_combo.addItem("Default", None)

        devices = self.recorder.get_input_devices()
        for idx, name in devices:
            self.device_combo.addItem(name, idx)
            if idx == self.config.audio_device_index:
                self.device_combo.setCurrentIndex(self.device_combo.count() - 1)

    def _on_device_changed(self):
        """Handle device selection change."""
        self.config.audio_device_index = self.device_combo.currentData()
        save_config(self.config)
        if self.config.audio_device_index is not None:
            self.recorder.set_device(self.config.audio_device_index)


class BehaviorWidget(QWidget):
    """Behavior settings section."""

    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        self.config = config
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

        # Beep on recording
        self.beep_on_record = QCheckBox()
        self.beep_on_record.setChecked(self.config.beep_on_record)
        self.beep_on_record.toggled.connect(lambda v: self._save_bool("beep_on_record", v))
        form.addRow("Beep on recording start/stop:", self.beep_on_record)

        # Beep on clipboard/inject
        beep_clipboard_layout = QVBoxLayout()
        self.beep_on_clipboard = QCheckBox()
        self.beep_on_clipboard.setChecked(self.config.beep_on_clipboard)
        self.beep_on_clipboard.toggled.connect(lambda v: self._save_bool("beep_on_clipboard", v))
        beep_clipboard_layout.addWidget(self.beep_on_clipboard)
        beep_clipboard_help = QLabel("Plays when text is copied to clipboard or injected at cursor.")
        beep_clipboard_help.setStyleSheet("color: #666; font-size: 10px;")
        beep_clipboard_layout.addWidget(beep_clipboard_help)
        form.addRow("Beep on output:", beep_clipboard_layout)

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

        layout.addLayout(form)
        layout.addStretch()

    def _save_bool(self, key: str, value: bool):
        """Save boolean config value."""
        setattr(self.config, key, value)
        save_config(self.config)

    def _on_append_position_changed(self, index: int):
        """Save append position setting."""
        value = self.append_position.itemData(index)
        self.config.append_position = value
        save_config(self.config)


class PersonalizationWidget(QWidget):
    """Personalization settings section."""

    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
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

        desc = QLabel("Customize your email signatures for business and personal communications.")
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #666; margin-bottom: 12px;")
        layout.addWidget(desc)

        # Form
        form = QFormLayout()
        form.setSpacing(12)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        # Name
        self.name_edit = QLineEdit()
        self.name_edit.setText(self.config.user_name)
        self.name_edit.setPlaceholderText("Your name")
        self.name_edit.textChanged.connect(lambda: self._save_str("user_name", self.name_edit.text()))
        form.addRow("Name:", self.name_edit)

        layout.addLayout(form)

        # Business Email Section
        business_group = QGroupBox("Business Email")
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
        personal_group = QGroupBox("Personal Email")
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


class HotkeysWidget(QWidget):
    """Hotkeys configuration section."""

    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        self.config = config
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
            "Global hotkeys are currently fixed to F15-F19. "
            "Customizable hotkeys will be available in a future release."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #666; margin-bottom: 12px;")
        layout.addWidget(desc)

        # Hotkey reference
        ref_group = QGroupBox("Fixed Hotkey Mapping")
        ref_layout = QFormLayout(ref_group)
        ref_layout.setSpacing(8)

        hotkeys = [
            ("F15", "Toggle Recording"),
            ("F16", "Tap (same as F15)"),
            ("F17", "Transcribe Only"),
            ("F18", "Clear/Delete"),
            ("F19", "Append"),
        ]

        for key, action in hotkeys:
            key_label = QLabel(f"<b>{key}</b>")
            action_label = QLabel(action)
            action_label.setStyleSheet("color: #666;")
            ref_layout.addRow(key_label, action_label)

        layout.addWidget(ref_group)
        layout.addStretch()


class DatabaseWidget(QWidget):
    """Database management section."""

    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        self.config = config
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

    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        self.config = config
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
            icon = self._get_provider_icon(provider_key)
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
        layout.addStretch()

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
        return QIcon()

    def _get_model_icon(self, model_id: str) -> QIcon:
        """Get the icon for a model based on its originator."""
        icons_dir = Path(__file__).parent / "icons"
        model_lower = model_id.lower()

        # All models are now Gemini-based
        if model_lower.startswith("google/") or model_lower.startswith("gemini"):
            icon_filename = "gemini_icon.png"
        else:
            return QIcon()

        icon_path = icons_dir / icon_filename
        if icon_path.exists():
            return QIcon(str(icon_path))
        return QIcon()

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
            model_icon = self._get_model_icon(model_id)
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
        self._update_tier_buttons()


class SettingsWidget(QWidget):
    """Unified settings widget with tabbed sections."""

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

        # Add sections as tabs
        self.tabs.addTab(ModelSelectionWidget(self.config), "Model")
        self.tabs.addTab(APIKeysWidget(self.config), "API Keys")
        self.tabs.addTab(AudioMicWidget(self.config, self.recorder), "Mic")
        self.tabs.addTab(BehaviorWidget(self.config), "Behavior")
        self.tabs.addTab(PersonalizationWidget(self.config), "Personalization")
        self.tabs.addTab(HotkeysWidget(self.config), "Hotkeys")
        self.tabs.addTab(DatabaseWidget(self.config), "Database")

        layout.addWidget(self.tabs)

    def refresh(self):
        """Refresh all sub-widgets."""
        pass  # No specific refresh needed


class SettingsDialog(QDialog):
    """Settings dialog window containing the settings widget."""

    # Signal emitted when settings dialog is closed (settings may have changed)
    settings_closed = pyqtSignal()

    def __init__(self, config: Config, recorder, parent=None):
        super().__init__(parent)
        self.config = config
        self.recorder = recorder
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle("Settings")
        self.setMinimumSize(700, 550)
        self.resize(750, 600)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Embed the settings widget
        self.settings_widget = SettingsWidget(self.config, self.recorder, self)
        layout.addWidget(self.settings_widget)

        # Bottom bar with auto-save note and close button
        bottom_bar = QHBoxLayout()
        bottom_bar.setContentsMargins(16, 8, 16, 12)

        # Auto-save indicator
        auto_save_note = QLabel("Changes are saved automatically")
        auto_save_note.setStyleSheet("color: #666; font-size: 11px; font-style: italic;")
        bottom_bar.addWidget(auto_save_note)

        bottom_bar.addStretch()

        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        close_btn.setFixedWidth(80)
        bottom_bar.addWidget(close_btn)

        layout.addLayout(bottom_bar)

    def refresh(self):
        """Refresh the settings widget."""
        self.settings_widget.refresh()

    def closeEvent(self, event):
        """Emit signal when dialog is closed."""
        self.settings_closed.emit()
        super().closeEvent(event)
