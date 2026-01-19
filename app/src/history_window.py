"""Standalone history window with tabbed interface for browsing and searching transcriptions.

Features:
- View History tab: Browse transcripts with sidebar/detail layout
- Search tab: Semantic search with date filtering (uses embeddings)
"""

from datetime import datetime, date
from typing import Optional, List, Tuple
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QScrollArea,
    QFrame,
    QApplication,
    QSplitter,
    QSizePolicy,
    QTabWidget,
    QDateEdit,
    QCheckBox,
    QProgressBar,
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QDate
from PyQt6.QtGui import QFont, QIcon

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
            return f"Today at {dt.strftime('%H:%M')}"
        elif delta == 1:
            return f"Yesterday at {dt.strftime('%H:%M')}"
        elif delta <= 7:
            return f"{delta} days ago"
        else:
            return dt.strftime("%b %d, %Y at %H:%M")
    except (ValueError, TypeError):
        return timestamp_str[:16] if timestamp_str else "Unknown"


def format_date_header(record_date: date) -> str:
    """Format a date for display in a date divider header."""
    today = date.today()
    delta = (today - record_date).days

    if delta == 0:
        return "Today"
    elif delta == 1:
        return "Yesterday"
    else:
        if delta < 7:
            return record_date.strftime("%A")
        else:
            return record_date.strftime("%A, %B %d, %Y")


def get_preview_text(text: str, max_chars: int = 80) -> str:
    """Get preview text, truncating at max_chars with ellipsis if needed."""
    clean_text = text.replace("\n", " ").strip()
    clean_text = " ".join(clean_text.split())
    if len(clean_text) <= max_chars:
        return clean_text
    truncated = clean_text[:max_chars].rsplit(" ", 1)[0]
    return truncated + "..."


class DateDivider(QFrame):
    """A horizontal divider with a date label for separating days in history."""

    def __init__(self, label_text: str, parent=None):
        super().__init__(parent)
        self.setup_ui(label_text)

    def setup_ui(self, label_text: str):
        self.setFixedHeight(28)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 6, 0, 4)
        layout.setSpacing(8)

        left_line = QFrame()
        left_line.setFrameShape(QFrame.Shape.HLine)
        left_line.setStyleSheet("background-color: #ccc;")
        left_line.setFixedHeight(1)
        layout.addWidget(left_line, 1)

        label = QLabel(label_text)
        label.setStyleSheet("color: #666; font-size: 10px; font-weight: bold;")
        layout.addWidget(label)

        right_line = QFrame()
        right_line.setFrameShape(QFrame.Shape.HLine)
        right_line.setStyleSheet("background-color: #ccc;")
        right_line.setFixedHeight(1)
        layout.addWidget(right_line, 1)


class SidebarItem(QFrame):
    """A single transcript item in the sidebar list."""

    clicked = pyqtSignal(object)  # Emits the TranscriptionRecord

    def __init__(self, record: TranscriptionRecord, parent=None):
        super().__init__(parent)
        self.record = record
        self._selected = False
        self.setup_ui()

    def setup_ui(self):
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._update_style()
        self.setFixedHeight(52)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setSpacing(2)
        layout.setContentsMargins(10, 6, 10, 6)

        # Preview text (single line)
        preview_text = get_preview_text(self.record.transcript_text, 60)
        self.preview = QLabel(preview_text)
        self.preview.setStyleSheet("color: #333; font-size: 12px;")
        self.preview.setWordWrap(False)
        layout.addWidget(self.preview)

        # Timestamp and word count on second line
        time_str = format_relative_time(self.record.timestamp)
        word_count = self.record.word_count or len(self.record.transcript_text.split())
        meta_text = f"{time_str} · {word_count} words"
        self.meta = QLabel(meta_text)
        self.meta.setStyleSheet("color: #888; font-size: 10px;")
        layout.addWidget(self.meta)

    def _update_style(self):
        if self._selected:
            self.setStyleSheet("""
                SidebarItem {
                    background-color: #007bff;
                    border: 1px solid #0056b3;
                    border-radius: 4px;
                }
            """)
            # Update label colors for selected state
            if hasattr(self, 'preview'):
                self.preview.setStyleSheet("color: white; font-size: 12px;")
                self.meta.setStyleSheet("color: rgba(255, 255, 255, 0.8); font-size: 10px;")
        else:
            self.setStyleSheet("""
                SidebarItem {
                    background-color: #ffffff;
                    border: 1px solid #e0e0e0;
                    border-radius: 4px;
                }
                SidebarItem:hover {
                    background-color: #f0f7ff;
                    border-color: #b3d7ff;
                }
            """)
            if hasattr(self, 'preview'):
                self.preview.setStyleSheet("color: #333; font-size: 12px;")
                self.meta.setStyleSheet("color: #888; font-size: 10px;")

    def set_selected(self, selected: bool):
        self._selected = selected
        self._update_style()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.record)
        super().mousePressEvent(event)


class SearchResultItem(QFrame):
    """A single search result item showing similarity score."""

    clicked = pyqtSignal(object)  # Emits the TranscriptionRecord

    def __init__(self, record: TranscriptionRecord, similarity: float, parent=None):
        super().__init__(parent)
        self.record = record
        self.similarity = similarity
        self._selected = False
        self.setup_ui()

    def setup_ui(self):
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._update_style()
        self.setFixedHeight(62)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setSpacing(2)
        layout.setContentsMargins(10, 6, 10, 6)

        # Top row: similarity score and date
        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        similarity_pct = int(self.similarity * 100)
        similarity_label = QLabel(f"{similarity_pct}% match")
        similarity_label.setStyleSheet("color: #28a745; font-size: 11px; font-weight: bold;")
        top_row.addWidget(similarity_label)

        time_str = format_relative_time(self.record.timestamp)
        time_label = QLabel(time_str)
        time_label.setStyleSheet("color: #888; font-size: 10px;")
        top_row.addWidget(time_label)

        top_row.addStretch()
        layout.addLayout(top_row)

        # Preview text
        preview_text = get_preview_text(self.record.transcript_text, 70)
        self.preview = QLabel(preview_text)
        self.preview.setStyleSheet("color: #333; font-size: 12px;")
        self.preview.setWordWrap(False)
        layout.addWidget(self.preview)

        # Word count
        word_count = self.record.word_count or len(self.record.transcript_text.split())
        self.meta = QLabel(f"{word_count} words")
        self.meta.setStyleSheet("color: #888; font-size: 10px;")
        layout.addWidget(self.meta)

    def _update_style(self):
        if self._selected:
            self.setStyleSheet("""
                SearchResultItem {
                    background-color: #007bff;
                    border: 1px solid #0056b3;
                    border-radius: 4px;
                }
            """)
            if hasattr(self, 'preview'):
                self.preview.setStyleSheet("color: white; font-size: 12px;")
                self.meta.setStyleSheet("color: rgba(255, 255, 255, 0.8); font-size: 10px;")
        else:
            self.setStyleSheet("""
                SearchResultItem {
                    background-color: #ffffff;
                    border: 1px solid #e0e0e0;
                    border-radius: 4px;
                }
                SearchResultItem:hover {
                    background-color: #f0f7ff;
                    border-color: #b3d7ff;
                }
            """)
            if hasattr(self, 'preview'):
                self.preview.setStyleSheet("color: #333; font-size: 12px;")
                self.meta.setStyleSheet("color: #888; font-size: 10px;")

    def set_selected(self, selected: bool):
        self._selected = selected
        self._update_style()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.record)
        super().mousePressEvent(event)


class SemanticSearchWorker(QThread):
    """Background thread for semantic search."""

    finished = pyqtSignal(list)  # List of (TranscriptionRecord, similarity) tuples
    error = pyqtSignal(str)

    def __init__(self, query: str, api_key: str, date_from: Optional[str] = None, date_to: Optional[str] = None):
        super().__init__()
        self.query = query
        self.api_key = api_key
        self.date_from = date_from
        self.date_to = date_to

    def run(self):
        try:
            from .embeddings import GeminiEmbeddingClient
            from .embedding_store import get_embedding_store

            # Get embedding store
            store = get_embedding_store()
            if store is None:
                self.error.emit("Embedding store not available")
                return

            # Check if we have any embeddings
            stats = store.get_stats()
            if stats['total_embeddings'] == 0:
                self.error.emit("No embeddings available. Embeddings are generated in batches of 100 transcripts.")
                return

            # Embed the query
            client = GeminiEmbeddingClient(self.api_key)
            query_embedding = client.embed_query(self.query)

            if not query_embedding:
                self.error.emit("Failed to embed query")
                return

            # Search for similar transcripts
            results = store.search_similar(
                query_embedding,
                top_k=20,
                min_similarity=0.3,
                date_from=self.date_from,
                date_to=self.date_to,
            )

            # Get full transcript records
            db = get_db()
            result_records = []
            for transcript_id, similarity in results:
                record = db.get_transcription(transcript_id)
                if record:
                    result_records.append((record, similarity))

            self.finished.emit(result_records)

        except Exception as e:
            self.error.emit(str(e))


class ViewHistoryTab(QWidget):
    """Tab for browsing transcription history with sidebar/detail layout."""

    transcription_copied = pyqtSignal(str)

    def __init__(self, config: Config = None, parent=None):
        super().__init__(parent)
        self.config = config
        self.current_offset = 0
        self.page_size = 10
        self.total_count = 0
        self.selected_record: TranscriptionRecord | None = None
        self._sidebar_items: list[SidebarItem] = []
        self.date_filter_mode = "all"  # "all", "today", "range"
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Date filter row
        date_row = QHBoxLayout()

        self.all_btn = QPushButton("All")
        self.all_btn.setCheckable(True)
        self.all_btn.setChecked(True)
        self.all_btn.clicked.connect(lambda: self._set_date_filter("all"))
        date_row.addWidget(self.all_btn)

        self.today_btn = QPushButton("Today")
        self.today_btn.setCheckable(True)
        self.today_btn.clicked.connect(lambda: self._set_date_filter("today"))
        date_row.addWidget(self.today_btn)

        self.range_btn = QPushButton("Date Range")
        self.range_btn.setCheckable(True)
        self.range_btn.clicked.connect(lambda: self._set_date_filter("range"))
        date_row.addWidget(self.range_btn)

        date_row.addSpacing(12)

        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(QDate.currentDate().addDays(-7))
        self.date_from.setEnabled(False)
        self.date_from.dateChanged.connect(self._on_date_changed)
        date_row.addWidget(QLabel("From:"))
        date_row.addWidget(self.date_from)

        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(QDate.currentDate())
        self.date_to.setEnabled(False)
        self.date_to.dateChanged.connect(self._on_date_changed)
        date_row.addWidget(QLabel("To:"))
        date_row.addWidget(self.date_to)

        date_row.addStretch()

        # Style for toggle buttons
        toggle_style = """
            QPushButton {
                background-color: #f0f0f0;
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 4px 12px;
                font-size: 11px;
            }
            QPushButton:checked {
                background-color: #007bff;
                color: white;
                border-color: #0056b3;
            }
            QPushButton:hover:!checked {
                background-color: #e0e0e0;
            }
        """
        self.all_btn.setStyleSheet(toggle_style)
        self.today_btn.setStyleSheet(toggle_style)
        self.range_btn.setStyleSheet(toggle_style)

        main_layout.addLayout(date_row)

        # Splitter with sidebar and detail panel
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #ddd;
            }
        """)

        # Left sidebar - scrollable list of transcripts
        sidebar_container = QWidget()
        sidebar_layout = QVBoxLayout(sidebar_container)
        sidebar_layout.setSpacing(0)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)

        sidebar_scroll = QScrollArea()
        sidebar_scroll.setWidgetResizable(True)
        sidebar_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sidebar_scroll.setStyleSheet("""
            QScrollArea {
                border: 1px solid #ddd;
                border-radius: 6px;
                background-color: #f8f9fa;
            }
        """)

        self.sidebar_widget = QWidget()
        self.sidebar_layout = QVBoxLayout(self.sidebar_widget)
        self.sidebar_layout.setSpacing(4)
        self.sidebar_layout.setContentsMargins(6, 6, 6, 6)
        self.sidebar_layout.addStretch()

        sidebar_scroll.setWidget(self.sidebar_widget)
        sidebar_layout.addWidget(sidebar_scroll, 1)

        # Pagination controls under sidebar
        pagination = QHBoxLayout()
        pagination.setContentsMargins(0, 8, 0, 0)

        self.start_btn = QPushButton("⏮")
        self.start_btn.setFixedWidth(32)
        self.start_btn.setToolTip("First page")
        self.start_btn.clicked.connect(self._on_start)
        self.start_btn.setEnabled(False)
        pagination.addWidget(self.start_btn)

        self.prev_btn = QPushButton("←")
        self.prev_btn.setFixedWidth(32)
        self.prev_btn.setToolTip("Previous page")
        self.prev_btn.clicked.connect(self._on_prev_page)
        self.prev_btn.setEnabled(False)
        pagination.addWidget(self.prev_btn)

        pagination.addStretch()

        self.page_label = QLabel("1 / 1")
        self.page_label.setStyleSheet("color: #666; font-size: 11px;")
        pagination.addWidget(self.page_label)

        pagination.addStretch()

        self.next_btn = QPushButton("→")
        self.next_btn.setFixedWidth(32)
        self.next_btn.setToolTip("Next page")
        self.next_btn.clicked.connect(self._on_next_page)
        pagination.addWidget(self.next_btn)

        sidebar_layout.addLayout(pagination)

        splitter.addWidget(sidebar_container)

        # Right detail panel
        detail_container = QWidget()
        detail_layout = QVBoxLayout(detail_container)
        detail_layout.setSpacing(8)
        detail_layout.setContentsMargins(0, 0, 0, 0)

        # Detail header with metadata and copy button
        detail_header = QHBoxLayout()

        self.detail_meta = QLabel("")
        self.detail_meta.setStyleSheet("color: #666; font-size: 11px;")
        detail_header.addWidget(self.detail_meta)

        detail_header.addStretch()

        self.copy_btn = QPushButton("Copy")
        self.copy_btn.setToolTip("Copy to clipboard")
        self.copy_btn.setFixedHeight(32)
        self.copy_btn.setStyleSheet("""
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 12px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.copy_btn.clicked.connect(self._on_copy)
        self.copy_btn.setEnabled(False)
        detail_header.addWidget(self.copy_btn)

        detail_layout.addLayout(detail_header)

        # Full text display
        self.detail_text = QLabel("")
        self.detail_text.setWordWrap(True)
        self.detail_text.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.detail_text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.detail_text.setStyleSheet("""
            QLabel {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 6px;
                padding: 12px;
                font-size: 13px;
                line-height: 1.5;
            }
        """)
        self.detail_text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        detail_scroll = QScrollArea()
        detail_scroll.setWidgetResizable(True)
        detail_scroll.setWidget(self.detail_text)
        detail_scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
        """)

        detail_layout.addWidget(detail_scroll, 1)

        splitter.addWidget(detail_container)

        # Set initial splitter sizes (sidebar narrower than detail)
        splitter.setSizes([280, 520])

        main_layout.addWidget(splitter, 1)

        # Status bar
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #888; font-size: 11px;")
        main_layout.addWidget(self.status_label)

    def refresh(self):
        """Refresh the transcript list."""
        db = get_db()

        # Get date filter
        date_from, date_to = self._get_date_filter()

        # Get total count
        self.total_count = db.get_total_count(date_from=date_from, date_to=date_to)

        # Get transcripts for current page
        records = db.get_transcriptions(
            limit=self.page_size,
            offset=self.current_offset,
            date_from=date_from,
            date_to=date_to,
        )

        # Clear existing sidebar items
        self._sidebar_items.clear()
        while self.sidebar_layout.count() > 1:  # Keep the stretch
            item = self.sidebar_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Add new items with date dividers
        current_date = None
        for record in records:
            try:
                record_dt = datetime.fromisoformat(record.timestamp)
                record_date = record_dt.date()
            except (ValueError, TypeError):
                record_date = None

            # Insert date divider when date changes
            if record_date and record_date != current_date:
                should_show_divider = not (
                    self.current_offset == 0
                    and current_date is None
                    and record_date == date.today()
                )
                if should_show_divider:
                    divider = DateDivider(format_date_header(record_date))
                    self.sidebar_layout.insertWidget(self.sidebar_layout.count() - 1, divider)
                current_date = record_date

            item = SidebarItem(record)
            item.clicked.connect(self._on_item_clicked)
            self._sidebar_items.append(item)
            self.sidebar_layout.insertWidget(self.sidebar_layout.count() - 1, item)

        # Auto-select first item if we have records and nothing selected
        if records and not self.selected_record:
            self._select_record(records[0])
        elif self.selected_record:
            # Try to maintain selection
            found = False
            for record in records:
                if record.id == self.selected_record.id:
                    self._select_record(record)
                    found = True
                    break
            if not found and records:
                self._select_record(records[0])
            elif not records:
                self._clear_selection()

        # Update pagination
        current_page = (self.current_offset // self.page_size) + 1
        total_pages = max(1, (self.total_count + self.page_size - 1) // self.page_size)
        self.page_label.setText(f"{current_page} / {total_pages}")
        self.start_btn.setEnabled(self.current_offset > 0)
        self.prev_btn.setEnabled(self.current_offset > 0)
        self.next_btn.setEnabled(self.current_offset + self.page_size < self.total_count)

        # Update status
        self.status_label.setText(f"{self.total_count} transcriptions")

    def _select_record(self, record: TranscriptionRecord):
        """Select a record and show its details."""
        self.selected_record = record

        # Update sidebar selection state
        for item in self._sidebar_items:
            item.set_selected(item.record.id == record.id)

        # Update detail panel
        self.detail_text.setText(record.transcript_text)

        # Build metadata string
        time_str = format_relative_time(record.timestamp)
        word_count = record.word_count or len(record.transcript_text.split())
        char_count = record.text_length or len(record.transcript_text)
        meta_parts = [time_str, f"{word_count} words", f"{char_count} chars"]

        if record.model:
            meta_parts.append(record.model)

        self.detail_meta.setText(" · ".join(meta_parts))
        self.copy_btn.setEnabled(True)

    def _clear_selection(self):
        """Clear the current selection."""
        self.selected_record = None
        for item in self._sidebar_items:
            item.set_selected(False)
        self.detail_text.setText("")
        self.detail_meta.setText("")
        self.copy_btn.setEnabled(False)

    def _on_item_clicked(self, record: TranscriptionRecord):
        """Handle sidebar item click."""
        self._select_record(record)

    def _set_date_filter(self, mode: str):
        """Set the date filter mode."""
        self.date_filter_mode = mode

        # Update button states
        self.all_btn.setChecked(mode == "all")
        self.today_btn.setChecked(mode == "today")
        self.range_btn.setChecked(mode == "range")

        # Enable/disable date pickers
        self.date_from.setEnabled(mode == "range")
        self.date_to.setEnabled(mode == "range")

        # Reset to first page and refresh
        self.current_offset = 0
        self.selected_record = None
        self.refresh()

    def _on_date_changed(self):
        """Handle date range change."""
        if self.date_filter_mode == "range":
            self.current_offset = 0
            self.selected_record = None
            self.refresh()

    def _get_date_filter(self) -> tuple:
        """Get current date filter as (from_date, to_date) or (None, None)."""
        if self.date_filter_mode == "all":
            return (None, None)
        elif self.date_filter_mode == "today":
            today = date.today().isoformat()
            return (today, today)
        else:  # range
            from_date = self.date_from.date().toString("yyyy-MM-dd")
            to_date = self.date_to.date().toString("yyyy-MM-dd")
            return (from_date, to_date)

    def _on_start(self):
        """Go to the first page."""
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

    def _on_copy(self):
        """Copy selected transcript to clipboard."""
        if not self.selected_record:
            return

        clipboard = QApplication.clipboard()
        clipboard.setText(self.selected_record.transcript_text)

        # Play clipboard feedback
        if self.config:
            feedback = get_feedback()
            feedback.enabled = self.config.beep_on_clipboard
            feedback.play_clipboard_beep()

        self.status_label.setText("Copied to clipboard!")
        self.transcription_copied.emit(self.selected_record.transcript_text)


class SearchTab(QWidget):
    """Tab for semantic search with date filtering."""

    transcription_copied = pyqtSignal(str)

    def __init__(self, config: Config = None, parent=None):
        super().__init__(parent)
        self.config = config
        self.selected_record: TranscriptionRecord | None = None
        self._result_items: list[SearchResultItem] = []
        self._search_worker: Optional[SemanticSearchWorker] = None
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Search controls
        search_row = QHBoxLayout()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by meaning...")
        self.search_input.setStyleSheet("""
            QLineEdit {
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 8px 12px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: #007bff;
            }
        """)
        self.search_input.returnPressed.connect(self._on_search)
        search_row.addWidget(self.search_input, 1)

        self.search_btn = QPushButton("Search")
        self.search_btn.setFixedHeight(36)
        self.search_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 16px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #218838;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        self.search_btn.clicked.connect(self._on_search)
        search_row.addWidget(self.search_btn)

        main_layout.addLayout(search_row)

        # Date filter row
        date_row = QHBoxLayout()

        date_row.addWidget(QLabel("From:"))
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(QDate.currentDate().addMonths(-1))
        self.date_from.setStyleSheet("padding: 4px;")
        date_row.addWidget(self.date_from)

        date_row.addWidget(QLabel("To:"))
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(QDate.currentDate())
        self.date_to.setStyleSheet("padding: 4px;")
        date_row.addWidget(self.date_to)

        self.use_date_filter = QCheckBox("Enable date filter")
        self.use_date_filter.setChecked(False)
        date_row.addWidget(self.use_date_filter)

        date_row.addStretch()

        main_layout.addLayout(date_row)

        # Embedding status row
        status_row = QHBoxLayout()

        self.embedding_status = QLabel("")
        self.embedding_status.setStyleSheet("color: #666; font-size: 11px;")
        status_row.addWidget(self.embedding_status)

        status_row.addStretch()

        self.generate_btn = QPushButton("Generate Embeddings")
        self.generate_btn.setToolTip("Generate embeddings for unprocessed transcriptions")
        self.generate_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 12px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        self.generate_btn.clicked.connect(self._on_generate_embeddings)
        status_row.addWidget(self.generate_btn)

        main_layout.addLayout(status_row)

        # Splitter with results and detail panel
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #ddd;
            }
        """)

        # Left results panel
        results_container = QWidget()
        results_layout = QVBoxLayout(results_container)
        results_layout.setSpacing(4)
        results_layout.setContentsMargins(0, 0, 0, 0)

        results_header = QLabel("Search Results")
        results_header.setStyleSheet("font-weight: bold; font-size: 12px; color: #333;")
        results_layout.addWidget(results_header)

        results_scroll = QScrollArea()
        results_scroll.setWidgetResizable(True)
        results_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        results_scroll.setStyleSheet("""
            QScrollArea {
                border: 1px solid #ddd;
                border-radius: 6px;
                background-color: #f8f9fa;
            }
        """)

        self.results_widget = QWidget()
        self.results_layout = QVBoxLayout(self.results_widget)
        self.results_layout.setSpacing(4)
        self.results_layout.setContentsMargins(6, 6, 6, 6)
        self.results_layout.addStretch()

        results_scroll.setWidget(self.results_widget)
        results_layout.addWidget(results_scroll, 1)

        splitter.addWidget(results_container)

        # Right detail panel
        detail_container = QWidget()
        detail_layout = QVBoxLayout(detail_container)
        detail_layout.setSpacing(8)
        detail_layout.setContentsMargins(0, 0, 0, 0)

        # Detail header
        detail_header = QHBoxLayout()

        self.detail_meta = QLabel("")
        self.detail_meta.setStyleSheet("color: #666; font-size: 11px;")
        detail_header.addWidget(self.detail_meta)

        detail_header.addStretch()

        self.copy_btn = QPushButton("Copy")
        self.copy_btn.setToolTip("Copy to clipboard")
        self.copy_btn.setFixedHeight(32)
        self.copy_btn.setStyleSheet("""
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 12px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.copy_btn.clicked.connect(self._on_copy)
        self.copy_btn.setEnabled(False)
        detail_header.addWidget(self.copy_btn)

        detail_layout.addLayout(detail_header)

        # Full text display
        self.detail_text = QLabel("")
        self.detail_text.setWordWrap(True)
        self.detail_text.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.detail_text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.detail_text.setStyleSheet("""
            QLabel {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 6px;
                padding: 12px;
                font-size: 13px;
                line-height: 1.5;
            }
        """)
        self.detail_text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        detail_scroll = QScrollArea()
        detail_scroll.setWidgetResizable(True)
        detail_scroll.setWidget(self.detail_text)
        detail_scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
        """)

        detail_layout.addWidget(detail_scroll, 1)

        splitter.addWidget(detail_container)
        splitter.setSizes([350, 450])

        main_layout.addWidget(splitter, 1)

        # Status bar
        self.status_label = QLabel("Enter a search query to find similar transcriptions")
        self.status_label.setStyleSheet("color: #888; font-size: 11px;")
        main_layout.addWidget(self.status_label)

    def refresh(self):
        """Update embedding statistics."""
        try:
            from .embedding_store import get_embedding_store
            store = get_embedding_store()
            if store:
                stats = store.get_stats()
                self.embedding_status.setText(
                    f"Embeddings: {stats['total_embeddings']} / {stats['total_transcripts']} "
                    f"({stats['coverage_percent']}% coverage)"
                )
            else:
                self.embedding_status.setText("Embedding store not available")
        except Exception as e:
            self.embedding_status.setText(f"Error: {e}")

    def _on_search(self):
        """Start semantic search."""
        query = self.search_input.text().strip()
        if not query:
            self.status_label.setText("Enter a search query")
            return

        # Check for API key
        if not self.config or not self.config.openrouter_api_key:
            self.status_label.setText("OpenRouter API key required for semantic search")
            return

        # Disable search while processing
        self.search_btn.setEnabled(False)
        self.status_label.setText("Searching...")

        # Get date filters
        date_from = None
        date_to = None
        if self.use_date_filter.isChecked():
            date_from = self.date_from.date().toString("yyyy-MM-dd")
            date_to = self.date_to.date().toString("yyyy-MM-dd")

        # Start search in background thread
        self._search_worker = SemanticSearchWorker(
            query,
            self.config.openrouter_api_key,
            date_from,
            date_to,
        )
        self._search_worker.finished.connect(self._on_search_finished)
        self._search_worker.error.connect(self._on_search_error)
        self._search_worker.start()

    def _on_search_finished(self, results: List[Tuple[TranscriptionRecord, float]]):
        """Handle search results."""
        self.search_btn.setEnabled(True)

        # Clear existing results
        self._result_items.clear()
        while self.results_layout.count() > 1:
            item = self.results_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not results:
            self.status_label.setText("No matching transcriptions found")
            self._clear_selection()
            return

        # Add result items
        for record, similarity in results:
            item = SearchResultItem(record, similarity)
            item.clicked.connect(self._on_item_clicked)
            self._result_items.append(item)
            self.results_layout.insertWidget(self.results_layout.count() - 1, item)

        # Auto-select first result
        self._select_record(results[0][0], results[0][1])

        self.status_label.setText(f"Found {len(results)} matching transcriptions")

    def _on_search_error(self, error: str):
        """Handle search error."""
        self.search_btn.setEnabled(True)
        self.status_label.setText(f"Search error: {error}")

    def _select_record(self, record: TranscriptionRecord, similarity: float = 0.0):
        """Select a record and show its details."""
        self.selected_record = record

        # Update result selection state
        for item in self._result_items:
            item.set_selected(item.record.id == record.id)

        # Update detail panel
        self.detail_text.setText(record.transcript_text)

        # Build metadata string
        time_str = format_relative_time(record.timestamp)
        word_count = record.word_count or len(record.transcript_text.split())
        similarity_pct = int(similarity * 100)
        meta_parts = [f"{similarity_pct}% match", time_str, f"{word_count} words"]

        if record.model:
            meta_parts.append(record.model)

        self.detail_meta.setText(" · ".join(meta_parts))
        self.copy_btn.setEnabled(True)

    def _clear_selection(self):
        """Clear the current selection."""
        self.selected_record = None
        for item in self._result_items:
            item.set_selected(False)
        self.detail_text.setText("")
        self.detail_meta.setText("")
        self.copy_btn.setEnabled(False)

    def _on_item_clicked(self, record: TranscriptionRecord):
        """Handle result item click."""
        # Find the similarity score
        similarity = 0.0
        for item in self._result_items:
            if item.record.id == record.id:
                similarity = item.similarity
                break
        self._select_record(record, similarity)

    def _on_copy(self):
        """Copy selected transcript to clipboard."""
        if not self.selected_record:
            return

        clipboard = QApplication.clipboard()
        clipboard.setText(self.selected_record.transcript_text)

        if self.config:
            feedback = get_feedback()
            feedback.enabled = self.config.beep_on_clipboard
            feedback.play_clipboard_beep()

        self.status_label.setText("Copied to clipboard!")
        self.transcription_copied.emit(self.selected_record.transcript_text)

    def _on_generate_embeddings(self):
        """Manually trigger embedding generation."""
        if not self.config or not self.config.openrouter_api_key:
            self.status_label.setText("OpenRouter API key required")
            return

        try:
            from .embedding_store import get_embedding_store, get_batch_processor

            store = get_embedding_store()
            if store is None:
                self.status_label.setText("Embedding store not available")
                return

            # Check if there are any unembedded transcripts
            unembedded = store.get_unembedded_count()
            if unembedded == 0:
                self.status_label.setText("All transcripts already have embeddings")
                return

            # Get batch processor
            processor = get_batch_processor(self.config.openrouter_api_key)
            if processor is None:
                self.status_label.setText("Failed to initialize processor")
                return

            if processor.is_processing():
                self.status_label.setText("Already processing...")
                return

            # Disable button and show progress
            self.generate_btn.setEnabled(False)
            self.status_label.setText(f"Generating embeddings for up to 100 of {unembedded} transcripts...")

            def on_complete(count, error):
                self.generate_btn.setEnabled(True)
                if error:
                    self.status_label.setText(f"Error: {error}")
                elif count > 0:
                    self.status_label.setText(f"Generated {count} embeddings")
                    self.refresh()  # Update stats
                else:
                    self.status_label.setText("No embeddings generated")

            processor.process_batch_async(callback=on_complete)

        except Exception as e:
            self.generate_btn.setEnabled(True)
            self.status_label.setText(f"Error: {e}")


class HistoryWindow(QMainWindow):
    """Standalone window for browsing and searching transcription history."""

    transcription_copied = pyqtSignal(str)  # Emitted when a transcript is copied

    def __init__(self, config: Config = None, parent=None):
        super().__init__(parent)
        self.config = config

        self.setWindowTitle("Transcription History")
        self.setMinimumSize(800, 500)
        self.resize(950, 650)

        # Set window icon
        icon = QIcon.fromTheme("document-open-recent")
        if not icon.isNull():
            self.setWindowIcon(icon)

        self.setup_ui()

    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(12, 12, 12, 12)

        # Header with title
        header = QHBoxLayout()
        title = QLabel("Transcription History")
        title.setFont(QFont("Sans", 16, QFont.Weight.Bold))
        header.addWidget(title)
        header.addStretch()
        main_layout.addLayout(header)
        main_layout.addSpacing(8)

        # Tab widget
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #ddd;
                border-radius: 6px;
                background-color: white;
            }
            QTabBar::tab {
                background-color: #f0f0f0;
                border: 1px solid #ddd;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background-color: white;
                border-bottom-color: white;
            }
            QTabBar::tab:hover:!selected {
                background-color: #e0e0e0;
            }
        """)

        # View History tab
        self.view_tab = ViewHistoryTab(self.config)
        self.view_tab.transcription_copied.connect(self.transcription_copied.emit)
        self.tabs.addTab(self.view_tab, "View History")

        # Search tab
        self.search_tab = SearchTab(self.config)
        self.search_tab.transcription_copied.connect(self.transcription_copied.emit)
        self.tabs.addTab(self.search_tab, "Search")

        main_layout.addWidget(self.tabs, 1)

    def refresh(self):
        """Refresh both tabs."""
        self.view_tab.refresh()
        self.search_tab.refresh()

    def showEvent(self, event):
        """Refresh data when window is shown."""
        super().showEvent(event)
        self.refresh()
