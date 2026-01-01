"""Standalone window for file transcription (Beta feature)."""

from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QLabel
from PyQt6.QtGui import QIcon, QFont
from PyQt6.QtCore import Qt

from .config import Config
from .file_transcription_widget import FileTranscriptionWidget


class FileTranscriptionWindow(QMainWindow):
    """Standalone window for transcribing audio files."""

    def __init__(self, config: Config = None, parent=None):
        super().__init__(parent)
        self.config = config

        self.setWindowTitle("File Transcription (Beta)")
        self.setMinimumSize(600, 500)
        self.resize(700, 600)

        # Set window icon
        icon = QIcon.fromTheme("folder-open")
        if not icon.isNull():
            self.setWindowIcon(icon)

        self.setup_ui()

    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)

        # Beta banner
        beta_banner = QLabel("🧪 This feature is in beta. Some functionality may be incomplete.")
        beta_banner.setStyleSheet("""
            QLabel {
                background-color: #fff3cd;
                border: 1px solid #ffc107;
                border-radius: 4px;
                padding: 8px 12px;
                color: #856404;
                font-size: 12px;
            }
        """)
        beta_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(beta_banner)

        # File transcription widget
        self.file_widget = FileTranscriptionWidget(config=self.config)
        layout.addWidget(self.file_widget, 1)
