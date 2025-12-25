"""Dialog for entering rewrite instructions."""

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QTextEdit,
    QPushButton,
    QLabel,
)
from PyQt6.QtCore import Qt


class RewriteDialog(QDialog):
    """Dialog for entering rewrite instructions."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Rewrite Transcript")
        self.setMinimumSize(500, 300)
        self.instruction = ""

        self.setup_ui()

    def setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Header
        header_label = QLabel(
            "Enter instructions for how you'd like to rewrite the transcript:"
        )
        header_label.setWordWrap(True)
        header_label.setStyleSheet("font-weight: bold; color: #495057;")
        layout.addWidget(header_label)

        # Instruction text area
        self.instruction_edit = QTextEdit()
        self.instruction_edit.setPlaceholderText(
            "Example: Fix any typos and make this more concise...\n"
            "Example: Rewrite this as a formal email...\n"
            "Example: Add section headers and bullet points..."
        )
        self.instruction_edit.setMinimumHeight(150)
        self.instruction_edit.setStyleSheet("""
            QTextEdit {
                border: 2px solid #ced4da;
                border-radius: 4px;
                padding: 8px;
                font-size: 13px;
            }
            QTextEdit:focus {
                border-color: #007bff;
            }
        """)
        layout.addWidget(self.instruction_edit)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setMinimumSize(100, 36)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        rewrite_btn = QPushButton("Rewrite")
        rewrite_btn.setMinimumSize(100, 36)
        rewrite_btn.setStyleSheet("""
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
        """)
        rewrite_btn.clicked.connect(self.accept)
        rewrite_btn.setDefault(True)
        button_layout.addWidget(rewrite_btn)

        layout.addLayout(button_layout)

    def get_instruction(self) -> str:
        """Get the entered instruction."""
        return self.instruction_edit.toPlainText().strip()
