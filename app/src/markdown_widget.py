"""Text widget for transcription output."""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTextEdit
from PyQt6.QtGui import QFont
from PyQt6.QtCore import pyqtSignal


class MarkdownTextWidget(QWidget):
    """Simple text widget for transcription output."""

    textChanged = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._markdown_text = ""
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Editable text area that also renders markdown
        self.source_view = QTextEdit()
        self.source_view.setFont(QFont("Sans", 11))
        self.source_view.setStyleSheet("QTextEdit { border: 1px solid #ced4da; border-radius: 4px; }")
        self.source_view.textChanged.connect(self._on_source_changed)

        layout.addWidget(self.source_view, 1)

    def _on_source_changed(self):
        """Handle source text changes."""
        self._markdown_text = self.source_view.toPlainText()
        self.textChanged.emit()

    def setMarkdown(self, text: str):
        """Set the markdown text content."""
        self._markdown_text = text
        self.source_view.setPlainText(text)

    def setPlainText(self, text: str):
        """Alias for setMarkdown for compatibility."""
        self.setMarkdown(text)

    def toPlainText(self) -> str:
        """Get the markdown text content."""
        return self.source_view.toPlainText()

    def clear(self):
        """Clear the content."""
        self._markdown_text = ""
        self.source_view.clear()

    def setPlaceholderText(self, text: str):
        """Set placeholder text for the source view."""
        self.source_view.setPlaceholderText(text)

    def setFont(self, font: QFont):
        """Set font for the source view."""
        self.source_view.setFont(font)
