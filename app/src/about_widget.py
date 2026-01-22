"""About widget showing version and keyboard shortcuts."""

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QGroupBox,
    QScrollArea,
    QFrame,
    QHBoxLayout,
    QDialog,
    QDialogButtonBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QPixmap
from pathlib import Path
import re

# Fallback version (updated by release.sh)
_FALLBACK_VERSION = "1.13.13"


def get_version() -> str:
    """Get version from pyproject.toml (dev) or fallback (installed)."""
    # Try to find pyproject.toml (development mode)
    src_dir = Path(__file__).parent
    for parent in [src_dir.parent, src_dir.parent.parent]:
        pyproject = parent / "pyproject.toml"
        if pyproject.exists():
            try:
                content = pyproject.read_text()
                match = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)
                if match:
                    return match.group(1)
            except Exception:
                pass
    return _FALLBACK_VERSION


VERSION = get_version()


class AboutWidget(QWidget):
    """Widget showing app info and keyboard shortcuts."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Scroll area for content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(12)
        layout.setContentsMargins(12, 12, 12, 12)

        # App title and version
        title = QLabel("AI Transcription Utility")
        title.setFont(QFont("Sans", 24, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        version_label = QLabel(f"Version {VERSION}")
        version_label.setStyleSheet("color: #666; font-size: 16px;")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version_label)

        desc = QLabel("Voice recording with AI-powered transcription and cleanup")
        desc.setStyleSheet("color: #888; font-size: 11px;")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # GitHub link
        repo_link = QLabel(
            '<a href="https://github.com/danielrosehill/Voice-Notepad">'
            'github.com/danielrosehill/Voice-Notepad</a>'
        )
        repo_link.setOpenExternalLinks(True)
        repo_link.setAlignment(Qt.AlignmentFlag.AlignCenter)
        repo_link.setStyleSheet("font-size: 11px;")
        layout.addWidget(repo_link)

        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("background-color: #ddd;")
        layout.addWidget(line)

        # Collaborative credits section
        by_label = QLabel("By")
        by_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        by_label.setStyleSheet("color: #888; font-size: 14px; margin-top: 8px;")
        layout.addWidget(by_label)

        # Split layout for human and AI
        collab_layout = QHBoxLayout()
        collab_layout.setSpacing(40)
        collab_layout.setContentsMargins(20, 10, 20, 10)

        # Human side
        human_container = QVBoxLayout()
        human_container.setSpacing(8)
        human_container.setAlignment(Qt.AlignmentFlag.AlignCenter)

        human_icon_path = Path(__file__).parent / "icons" / "human.png"
        if human_icon_path.exists():
            human_icon = QLabel()
            human_pixmap = QPixmap(str(human_icon_path)).scaled(
                64, 64, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            human_icon.setPixmap(human_pixmap)
            human_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            human_container.addWidget(human_icon)
        else:
            # Fallback emoji
            human_emoji = QLabel("👤")
            human_emoji.setStyleSheet("font-size: 48px;")
            human_emoji.setAlignment(Qt.AlignmentFlag.AlignCenter)
            human_container.addWidget(human_emoji)

        human_name = QLabel('<a href="https://danielrosehill.com" style="text-decoration: none; color: #333;">Daniel Rosehill</a>')
        human_name.setOpenExternalLinks(True)
        human_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        human_name.setStyleSheet("font-size: 14px; font-weight: bold;")
        human_container.addWidget(human_name)

        human_widget = QWidget()
        human_widget.setLayout(human_container)
        collab_layout.addWidget(human_widget)

        # Bot side
        bot_container = QVBoxLayout()
        bot_container.setSpacing(8)
        bot_container.setAlignment(Qt.AlignmentFlag.AlignCenter)

        bot_icon_path = Path(__file__).parent / "icons" / "claude.png"
        if bot_icon_path.exists():
            bot_icon = QLabel()
            bot_pixmap = QPixmap(str(bot_icon_path)).scaled(
                64, 64, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            bot_icon.setPixmap(bot_pixmap)
            bot_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            bot_container.addWidget(bot_icon)
        else:
            # Fallback emoji
            bot_emoji = QLabel("🤖")
            bot_emoji.setStyleSheet("font-size: 48px;")
            bot_emoji.setAlignment(Qt.AlignmentFlag.AlignCenter)
            bot_container.addWidget(bot_emoji)

        bot_name = QLabel("Claude Opus 4.5")
        bot_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bot_name.setStyleSheet("font-size: 14px; font-weight: bold; color: #333;")
        bot_container.addWidget(bot_name)

        bot_widget = QWidget()
        bot_widget.setLayout(bot_container)
        collab_layout.addWidget(bot_widget)

        collab_widget = QWidget()
        collab_widget.setLayout(collab_layout)
        layout.addWidget(collab_widget)

        # Separator
        line2 = QFrame()
        line2.setFrameShape(QFrame.Shape.HLine)
        line2.setStyleSheet("background-color: #ddd; margin-top: 12px;")
        layout.addWidget(line2)

        # Scope section
        scope_group = QGroupBox("Scope")
        scope_layout = QVBoxLayout(scope_group)
        scope_layout.setSpacing(8)

        scope_intro = QLabel(
            "This app focuses on <b>audio multimodal models</b>—AI models that "
            "directly process audio for transcription, eliminating the need for "
            "separate ASR + LLM pipelines."
        )
        scope_intro.setWordWrap(True)
        scope_intro.setStyleSheet("color: #444; font-size: 11px;")
        scope_layout.addWidget(scope_intro)

        scope_is = QLabel(
            "<b>What this app is:</b><br>"
            "• A simple interface for single-pass transcription + basic cleanup<br>"
            "• Focused on audio-capable multimodal models<br>"
            "• A lightweight tool with a standard cleanup prompt"
        )
        scope_is.setWordWrap(True)
        scope_is.setStyleSheet("color: #444; font-size: 11px;")
        scope_layout.addWidget(scope_is)

        scope_not = QLabel(
            "<b>What this app is not:</b><br>"
            "• A platform for elaborate text formatting prompts<br>"
            "• A general-purpose ASR tool<br>"
            "• An omnimodel showcase (focus is audio→text only)"
        )
        scope_not.setWordWrap(True)
        scope_not.setStyleSheet("color: #666; font-size: 11px;")
        scope_layout.addWidget(scope_not)

        scope_note = QLabel(
            "API providers with audio multimodal models: open an issue or PR!"
        )
        scope_note.setWordWrap(True)
        scope_note.setStyleSheet("color: #888; font-size: 10px; font-style: italic;")
        scope_layout.addWidget(scope_note)

        layout.addWidget(scope_group)

        # Control Buttons
        controls_group = QGroupBox("Control Buttons")
        controls_layout = QVBoxLayout(controls_group)
        controls_layout.setSpacing(6)

        controls_intro = QLabel(
            "The main recording interface provides the following controls:"
        )
        controls_intro.setWordWrap(True)
        controls_intro.setStyleSheet("color: #444; font-size: 11px; margin-bottom: 8px;")
        controls_layout.addWidget(controls_intro)

        control_buttons = [
            ("Record", "Start a new recording (clears any cached audio)"),
            ("Pause", "Pause/resume the current recording (available only while recording)"),
            ("Stop", "Stop recording and cache audio without transcribing. You can append more clips or transcribe later."),
            ("Append", "Record additional audio and combine with cached audio. Useful for recording in segments."),
            ("Transcribe", "Smart button that adapts to the current state:\n  • While recording: Stops and transcribes immediately\n  • After stopping: Transcribes all cached audio clips"),
            ("Delete", "Discard all cached audio without transcribing"),
        ]

        for button, desc in control_buttons:
            button_label = QLabel(f"<b>{button}:</b> {desc}")
            button_label.setWordWrap(True)
            button_label.setStyleSheet("margin-left: 10px; margin-bottom: 4px;")
            controls_layout.addWidget(button_label)

        layout.addWidget(controls_group)

        # Keyboard shortcuts
        shortcuts_group = QGroupBox("Keyboard Shortcuts")
        shortcuts_layout = QVBoxLayout(shortcuts_group)
        shortcuts_layout.setSpacing(6)

        # In-app shortcuts
        inapp_label = QLabel("<b>In-App Shortcuts</b> (when window is focused)")
        inapp_label.setWordWrap(True)
        shortcuts_layout.addWidget(inapp_label)

        inapp_shortcuts = [
            ("Ctrl+R", "Start/toggle recording"),
            ("Ctrl+Space", "Pause/resume recording"),
            ("Ctrl+Return", "Stop and transcribe"),
            ("Ctrl+S", "Save to file"),
            ("Ctrl+Shift+C", "Copy to clipboard"),
            ("Ctrl+N", "Clear transcription"),
        ]

        for key, desc in inapp_shortcuts:
            shortcut_label = QLabel(f"<code>{key}</code> - {desc}")
            shortcut_label.setWordWrap(True)
            shortcut_label.setStyleSheet("margin-left: 10px;")
            shortcuts_layout.addWidget(shortcut_label)

        # Global hotkeys section
        global_label = QLabel("<b>Global Hotkeys</b> (work when minimized)")
        global_label.setStyleSheet("margin-top: 10px;")
        global_label.setWordWrap(True)
        shortcuts_layout.addWidget(global_label)

        global_note = QLabel(
            "Configure in Settings > Hotkeys. Recommended: F14-F20 (macro keys)"
        )
        global_note.setStyleSheet("color: #666; font-size: 11px; margin-left: 10px;")
        global_note.setWordWrap(True)
        shortcuts_layout.addWidget(global_note)

        global_shortcuts = [
            ("Record Toggle", "Start recording / stop and discard"),
            ("Stop & Transcribe", "Stop recording and send to AI"),
        ]

        for action, desc in global_shortcuts:
            shortcut_label = QLabel(f"<b>{action}</b> - {desc}")
            shortcut_label.setWordWrap(True)
            shortcut_label.setStyleSheet("margin-left: 10px;")
            shortcuts_layout.addWidget(shortcut_label)

        layout.addWidget(shortcuts_group)

        # Supported providers
        providers_group = QGroupBox("Supported AI Providers")
        providers_layout = QVBoxLayout(providers_group)

        providers = [
            "Google Gemini via OpenRouter - Gemini 3 Flash (Default), Gemini 3 Pro",
            "All models accessed through OpenRouter's unified API",
        ]
        for p in providers:
            p_label = QLabel(p)
            p_label.setStyleSheet("color: #444; font-size: 11px;")
            p_label.setWordWrap(True)
            providers_layout.addWidget(p_label)

        layout.addWidget(providers_group)

        # Voice Activity Detection
        vad_group = QGroupBox("Voice Activity Detection (VAD)")
        vad_layout = QVBoxLayout(vad_group)

        vad_intro = QLabel(
            "VAD removes silence from recordings before sending to the API, "
            "reducing file size and cost."
        )
        vad_intro.setWordWrap(True)
        vad_intro.setStyleSheet("color: #444; font-size: 11px;")
        vad_layout.addWidget(vad_intro)

        vad_model = QLabel(
            '<b>Model:</b> <a href="https://github.com/snakers4/silero-vad">Silero VAD</a> (ONNX)'
        )
        vad_model.setOpenExternalLinks(True)
        vad_model.setWordWrap(True)
        vad_model.setStyleSheet("font-size: 11px; margin-top: 5px;")
        vad_layout.addWidget(vad_model)

        vad_details = QLabel(
            "<b>Parameters:</b> 16kHz sample rate, 512-sample window (~32ms), "
            "0.5 speech probability threshold"
        )
        vad_details.setWordWrap(True)
        vad_details.setStyleSheet("color: #666; font-size: 10px;")
        vad_layout.addWidget(vad_details)

        vad_storage = QLabel(
            "<b>Storage:</b> ~/.config/voice-notepad-v3/models/silero_vad.onnx (~1.4MB)"
        )
        vad_storage.setWordWrap(True)
        vad_storage.setStyleSheet("color: #666; font-size: 10px;")
        vad_layout.addWidget(vad_storage)

        layout.addWidget(vad_group)

        # MIT License
        license_group = QGroupBox("License")
        license_layout = QVBoxLayout(license_group)
        license_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # MIT logo
        mit_icon_path = Path(__file__).parent / "icons" / "mit_small.png"
        if mit_icon_path.exists():
            mit_icon = QLabel()
            mit_pixmap = QPixmap(str(mit_icon_path))
            mit_icon.setPixmap(mit_pixmap)
            mit_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            license_layout.addWidget(mit_icon)

        license_text = QLabel(
            "This software is licensed under the MIT License. "
            "See the GitHub repository for full license text."
        )
        license_text.setWordWrap(True)
        license_text.setStyleSheet("color: #666; font-size: 11px;")
        license_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        license_layout.addWidget(license_text)

        layout.addWidget(license_group)

        # Spacer
        layout.addStretch()

        # Footer
        footer = QLabel(
            "Audio is processed locally before upload. "
            "VAD (silence removal) reduces API costs."
        )
        footer.setStyleSheet("color: #888; font-size: 10px;")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setWordWrap(True)
        layout.addWidget(footer)

        scroll.setWidget(content)
        main_layout.addWidget(scroll)


class AboutDialog(QDialog):
    """About dialog window containing the about widget."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle("About AI Transcription Utility")
        self.setMinimumSize(500, 450)
        self.resize(550, 650)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Embed the about widget
        self.about_widget = AboutWidget(self)
        layout.addWidget(self.about_widget)

        # Close button at the bottom
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(self.accept)
        button_box.setContentsMargins(12, 8, 12, 12)
        layout.addWidget(button_box)
