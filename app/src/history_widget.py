"""History tab widget for browsing and retrieving past transcriptions."""

from datetime import datetime, date, timedelta
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QScrollArea,
    QFrame,
    QTextEdit,
    QApplication,
    QSplitter,
    QMessageBox,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from .database_mongo import get_db, TranscriptionRecord
from .audio_feedback import get_feedback
from .config import Config


def format_relative_time(timestamp_str: str) -> str:
    """Format timestamp as relative time (Today, Yesterday, X days ago, or date)."""
    try:
        dt = datetime.fromisoformat(timestamp_str)
        dt_date = dt.date()
        today = date.today()
        delta = (today - dt_date).days

        if delta == 0:
            # Today - show "Today at HH:MM"
            return f"Today at {dt.strftime('%H:%M')}"
        elif delta == 1:
            return "Yesterday"
        elif delta <= 7:
            return f"{delta} days ago"
        else:
            # Older - show date only
            return dt.strftime("%b %d, %Y")
    except (ValueError, TypeError):
        return timestamp_str[:16] if timestamp_str else "Unknown"


class TranscriptItem(QFrame):
    """A single transcript item in the history list."""

    item_clicked = pyqtSignal(object)  # Emits the TranscriptionRecord

    def __init__(self, record: TranscriptionRecord, parent=None):
        super().__init__(parent)
        self.record = record
        self.setup_ui()

    def setup_ui(self):
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            TranscriptItem {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                padding: 8px;
            }
            TranscriptItem:hover {
                background-color: #f8f9fa;
                border-color: #007bff;
            }
        """)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(10, 8, 10, 8)

        # Header row: relative timestamp
        header = QHBoxLayout()

        time_str = format_relative_time(self.record.timestamp)
        time_label = QLabel(time_str)
        time_label.setStyleSheet("color: #666; font-size: 11px;")
        header.addWidget(time_label)

        header.addStretch()

        layout.addLayout(header)

        # Preview text (first ~120 chars)
        preview_text = self.record.transcript_text.replace("\n", " ").strip()
        if len(preview_text) > 120:
            preview_text = preview_text[:117] + "..."

        preview = QLabel(preview_text)
        preview.setWordWrap(True)
        preview.setStyleSheet("color: #333; font-size: 12px;")
        layout.addWidget(preview)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.item_clicked.emit(self.record)
        super().mousePressEvent(event)


class HistoryWidget(QWidget):
    """Widget for browsing and retrieving past transcriptions."""

    transcription_selected = pyqtSignal(str)  # Emitted when user wants to load transcript

    def __init__(self, config: Config = None, parent=None):
        super().__init__(parent)
        self.config = config
        self.current_search = ""
        self.current_offset = 0
        self.page_size = 20
        self.total_count = 0
        self.selected_record = None
        self.setup_ui()
        self.refresh()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(12, 12, 12, 12)

        # Header with title and search
        header = QHBoxLayout()

        title = QLabel("Transcriptions")
        title.setFont(QFont("Sans", 14, QFont.Weight.Bold))
        header.addWidget(title)

        header.addStretch()

        # Search box
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search transcriptions...")
        self.search_input.setFixedWidth(250)
        self.search_input.setStyleSheet("""
            QLineEdit {
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 6px 10px;
                font-size: 12px;
            }
            QLineEdit:focus {
                border-color: #007bff;
            }
        """)
        self.search_input.returnPressed.connect(self._on_search)
        header.addWidget(self.search_input)

        search_btn = QPushButton("Search")
        search_btn.clicked.connect(self._on_search)
        header.addWidget(search_btn)

        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._on_clear_search)
        header.addWidget(clear_btn)

        layout.addLayout(header)

        # Main content: splitter with list and preview
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Scrollable list of transcripts
        list_container = QWidget()
        list_layout = QVBoxLayout(list_container)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea {
                border: 1px solid #ddd;
                border-radius: 6px;
                background-color: #f5f5f5;
            }
        """)

        self.list_widget = QWidget()
        self.list_layout = QVBoxLayout(self.list_widget)
        self.list_layout.setSpacing(8)
        self.list_layout.setContentsMargins(8, 8, 8, 8)
        self.list_layout.addStretch()

        scroll.setWidget(self.list_widget)
        list_layout.addWidget(scroll)

        # Pagination controls
        pagination = QHBoxLayout()

        self.prev_btn = QPushButton("← Previous")
        self.prev_btn.clicked.connect(self._on_prev_page)
        self.prev_btn.setEnabled(False)
        pagination.addWidget(self.prev_btn)

        pagination.addStretch()

        self.page_label = QLabel("Page 1")
        self.page_label.setStyleSheet("color: #666;")
        pagination.addWidget(self.page_label)

        pagination.addStretch()

        self.next_btn = QPushButton("Next →")
        self.next_btn.clicked.connect(self._on_next_page)
        pagination.addWidget(self.next_btn)

        list_layout.addLayout(pagination)

        splitter.addWidget(list_container)

        # Preview panel
        preview_container = QWidget()
        preview_layout = QVBoxLayout(preview_container)
        preview_layout.setContentsMargins(0, 8, 0, 0)

        preview_header = QHBoxLayout()
        preview_title = QLabel("Preview")
        preview_title.setFont(QFont("Sans", 11, QFont.Weight.Bold))
        preview_header.addWidget(preview_title)

        preview_header.addStretch()

        self.preview_info = QLabel("")
        self.preview_info.setStyleSheet("color: #666; font-size: 11px;")
        preview_header.addWidget(self.preview_info)

        preview_layout.addLayout(preview_header)

        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setStyleSheet("""
            QTextEdit {
                border: 1px solid #ddd;
                border-radius: 6px;
                padding: 8px;
                font-size: 13px;
                background-color: #ffffff;
            }
        """)
        self.preview_text.setPlaceholderText("Click a transcript to preview it here")
        preview_layout.addWidget(self.preview_text)

        # Preview action buttons
        preview_actions = QHBoxLayout()

        self.copy_full_btn = QPushButton("Copy Full Text")
        self.copy_full_btn.setEnabled(False)
        self.copy_full_btn.clicked.connect(self._on_copy_full)
        self.copy_full_btn.setStyleSheet("""
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
            QPushButton:disabled {
                background-color: #6c757d;
            }
        """)
        preview_actions.addWidget(self.copy_full_btn)

        self.load_btn = QPushButton("Load to Editor")
        self.load_btn.setEnabled(False)
        self.load_btn.clicked.connect(self._on_load_to_editor)
        self.load_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #218838;
            }
            QPushButton:disabled {
                background-color: #6c757d;
            }
        """)
        preview_actions.addWidget(self.load_btn)

        preview_actions.addStretch()

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setEnabled(False)
        self.delete_btn.clicked.connect(self._on_delete)
        self.delete_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #dc3545;
                border: 1px solid #dc3545;
                border-radius: 4px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #dc3545;
                color: white;
            }
            QPushButton:disabled {
                color: #999;
                border-color: #999;
            }
        """)
        preview_actions.addWidget(self.delete_btn)

        preview_layout.addLayout(preview_actions)

        splitter.addWidget(preview_container)

        # Set initial splitter sizes (60% list, 40% preview)
        splitter.setSizes([300, 200])

        layout.addWidget(splitter, 1)

        # Status bar
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(self.status_label)

    def refresh(self):
        """Refresh the transcript list."""
        db = get_db()

        # Get total count
        self.total_count = db.get_total_count(search=self.current_search if self.current_search else None)

        # Get transcripts for current page
        records = db.get_transcriptions(
            limit=self.page_size,
            offset=self.current_offset,
            search=self.current_search if self.current_search else None,
        )

        # Clear existing items
        while self.list_layout.count() > 1:  # Keep the stretch
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Add new items
        for record in records:
            item = TranscriptItem(record)
            item.item_clicked.connect(self._on_item_selected)
            self.list_layout.insertWidget(self.list_layout.count() - 1, item)

        # Update pagination
        current_page = (self.current_offset // self.page_size) + 1
        total_pages = max(1, (self.total_count + self.page_size - 1) // self.page_size)
        self.page_label.setText(f"Page {current_page} of {total_pages}")
        self.prev_btn.setEnabled(self.current_offset > 0)
        self.next_btn.setEnabled(self.current_offset + self.page_size < self.total_count)

        # Update status
        if self.current_search:
            self.status_label.setText(f"Found {self.total_count} transcriptions matching \"{self.current_search}\"")
        else:
            self.status_label.setText(f"{self.total_count} transcriptions total")

    def _on_search(self):
        """Handle search."""
        self.current_search = self.search_input.text().strip()
        self.current_offset = 0
        self.refresh()

    def _on_clear_search(self):
        """Clear search and show all."""
        self.search_input.clear()
        self.current_search = ""
        self.current_offset = 0
        self.refresh()

    def _on_prev_page(self):
        """Go to previous page."""
        self.current_offset = max(0, self.current_offset - self.page_size)
        self.refresh()

    def _on_next_page(self):
        """Go to next page."""
        self.current_offset += self.page_size
        self.refresh()

    def _on_item_selected(self, record: TranscriptionRecord):
        """Show selected transcript in preview and copy to clipboard."""
        self.selected_record = record

        # Copy to clipboard immediately
        clipboard = QApplication.clipboard()
        clipboard.setText(record.transcript_text)

        # Play clipboard beep
        if self.config:
            feedback = get_feedback()
            feedback.enabled = self.config.beep_on_clipboard
            feedback.play_clipboard_beep()

        # Update preview
        self.preview_text.setPlainText(record.transcript_text)

        # Update preview info with relative time
        time_str = format_relative_time(record.timestamp)
        self.preview_info.setText(f"{time_str} • {record.word_count} words • Copied!")

        # Enable action buttons
        self.copy_full_btn.setEnabled(True)
        self.load_btn.setEnabled(True)
        self.delete_btn.setEnabled(True)

    def _on_copy_full(self):
        """Copy full transcript to clipboard."""
        if self.selected_record:
            clipboard = QApplication.clipboard()
            clipboard.setText(self.selected_record.transcript_text)

            # Play clipboard beep
            if self.config:
                feedback = get_feedback()
                feedback.enabled = self.config.beep_on_clipboard
                feedback.play_clipboard_beep()

            self.status_label.setText("Copied to clipboard!")

    def _on_load_to_editor(self):
        """Load transcript to main editor."""
        if self.selected_record:
            self.transcription_selected.emit(self.selected_record.transcript_text)
            self.status_label.setText("Loaded to editor")

    def _on_delete(self):
        """Delete selected transcript."""
        if not self.selected_record:
            return

        reply = QMessageBox.question(
            self,
            "Delete Transcript",
            "Are you sure you want to delete this transcript?\n\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            db = get_db()
            if db.delete_transcription(self.selected_record.id):
                self.status_label.setText("Transcript deleted")
                self.selected_record = None
                self.preview_text.clear()
                self.preview_info.setText("")
                self.copy_full_btn.setEnabled(False)
                self.load_btn.setEnabled(False)
                self.delete_btn.setEnabled(False)
                self.refresh()
            else:
                self.status_label.setText("Failed to delete transcript")

