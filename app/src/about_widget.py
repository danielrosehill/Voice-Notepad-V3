"""About tab widget showing version and keyboard shortcuts."""

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QGroupBox,
    QScrollArea,
    QFrame,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

# Application version
VERSION = "1.2.0"


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
        title = QLabel("Voice Notepad")
        title.setFont(QFont("Sans", 18, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        version_label = QLabel(f"Version {VERSION}")
        version_label.setStyleSheet("color: #666; font-size: 13px;")
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
            "Gemini (Google) - gemini-2.0-flash-lite, gemini-flash-latest",
            "OpenAI - gpt-4o-audio-preview",
            "Mistral - voxtral-mini-latest",
        ]
        for p in providers:
            p_label = QLabel(p)
            p_label.setStyleSheet("color: #444; font-size: 11px;")
            p_label.setWordWrap(True)
            providers_layout.addWidget(p_label)

        layout.addWidget(providers_group)

        # Credits
        credits_group = QGroupBox("Credits")
        credits_layout = QVBoxLayout(credits_group)

        human_label = QLabel(
            'Human: <a href="https://danielrosehill.com">Daniel Rosehill</a>'
        )
        human_label.setOpenExternalLinks(True)
        human_label.setWordWrap(True)
        credits_layout.addWidget(human_label)

        coding_label = QLabel("Coding: Claude Code (Anthropic)")
        coding_label.setWordWrap(True)
        credits_layout.addWidget(coding_label)

        layout.addWidget(credits_group)

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
