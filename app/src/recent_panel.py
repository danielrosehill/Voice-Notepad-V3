"""Recent Transcriptions Panel - Quick access to last N transcripts.

A collapsible panel at the bottom of the main window showing the most recent
transcriptions with one-click copy functionality.
"""

from datetime import datetime
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont, QCursor
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QScrollArea,
    QSizePolicy,
)

from .clipboard import copy_to_clipboard


def format_relative_time(timestamp_str: str) -> str:
    """Convert ISO timestamp to relative time string.

    Examples:
        - "2m" (2 minutes ago)
        - "45m" (45 minutes ago)
        - "2h" (2 hours ago)
        - "1d" (yesterday)
        - "Jan 10" (older)
    """
    try:
        timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        now = datetime.now(timestamp.tzinfo) if timestamp.tzinfo else datetime.now()
        delta = now - timestamp

        seconds = delta.total_seconds()
        minutes = seconds / 60
        hours = minutes / 60
        days = hours / 24

        if minutes < 1:
            return "now"
        elif minutes < 60:
            return f"{int(minutes)}m"
        elif hours < 24:
            return f"{int(hours)}h"
        elif days < 7:
            return f"{int(days)}d"
        else:
            return timestamp.strftime("%b %d")
    except Exception:
        return ""


def truncate_text(text: str, max_length: int = 50) -> str:
    """Truncate text to max_length chars with ellipsis."""
    if not text:
        return ""
    # Replace newlines with spaces for preview
    text = " ".join(text.split())
    if len(text) <= max_length:
        return text
    return text[:max_length - 1] + "…"


class RecentTranscriptItem(QFrame):
    """Single row in the recent transcriptions panel."""

    copy_clicked = pyqtSignal(str)  # Emits transcript_id
    item_clicked = pyqtSignal(str)  # Emits transcript_id for loading into editor

    def __init__(
        self,
        transcript_id: str,
        transcript_text: str,
        timestamp: str,
        word_count: int,
        parent=None
    ):
        super().__init__(parent)
        self.transcript_id = transcript_id
        self.transcript_text = transcript_text

        self.setFrameStyle(QFrame.Shape.NoFrame)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setStyleSheet("""
            RecentTranscriptItem {
                background-color: transparent;
                border-radius: 4px;
                padding: 2px;
            }
            RecentTranscriptItem:hover {
                background-color: rgba(0, 0, 0, 0.03);
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        # Preview text (truncated)
        preview = truncate_text(transcript_text, 50)
        self.preview_label = QLabel(preview)
        self.preview_label.setStyleSheet("color: #333; font-size: 12px;")
        self.preview_label.setToolTip(transcript_text[:500] + ("..." if len(transcript_text) > 500 else ""))
        layout.addWidget(self.preview_label, 1)

        # Word count
        word_label = QLabel(f"{word_count}w")
        word_label.setStyleSheet("color: #888; font-size: 10px;")
        layout.addWidget(word_label)

        # Relative time
        rel_time = format_relative_time(timestamp)
        time_label = QLabel(rel_time)
        time_label.setStyleSheet("color: #888; font-size: 10px; min-width: 35px;")
        time_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(time_label)

        # Copy button
        copy_btn = QPushButton("Copy")
        copy_btn.setFixedSize(50, 24)
        copy_btn.setStyleSheet("""
            QPushButton {
                background-color: #f0f0f0;
                border: 1px solid #ccc;
                border-radius: 4px;
                font-size: 11px;
                color: #555;
            }
            QPushButton:hover {
                background-color: #e8e8e8;
                border-color: #bbb;
            }
            QPushButton:pressed {
                background-color: #ddd;
            }
        """)
        copy_btn.clicked.connect(self._on_copy_clicked)
        layout.addWidget(copy_btn)

        self.setFixedHeight(36)

    def _on_copy_clicked(self):
        """Handle copy button click."""
        self.copy_clicked.emit(self.transcript_id)

    def mousePressEvent(self, event):
        """Handle click on the item (not the copy button)."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.item_clicked.emit(self.transcript_id)
        super().mousePressEvent(event)


class RecentPanel(QWidget):
    """Collapsible panel showing the last N transcriptions."""

    # Signals
    view_all_clicked = pyqtSignal()
    transcript_selected = pyqtSignal(str)  # Emits transcript_id
    transcript_copied = pyqtSignal(str)    # Emits transcript_id after copy

    def __init__(self, database, max_items: int = 5, parent=None):
        super().__init__(parent)
        self.database = database
        self.max_items = max_items
        self.collapsed = False
        self._transcripts = []  # Cache of recent transcripts

        self.setObjectName("RecentPanel")

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header bar (always visible)
        self.header = QFrame()
        self.header.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border-top: 1px solid #e0e0e0;
            }
        """)
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(12, 6, 12, 6)
        header_layout.setSpacing(8)

        # Collapse/expand arrow
        self.toggle_btn = QPushButton("▼")
        self.toggle_btn.setFixedSize(20, 20)
        self.toggle_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                font-size: 10px;
                color: #666;
            }
            QPushButton:hover {
                color: #333;
            }
        """)
        self.toggle_btn.clicked.connect(self.toggle_collapse)
        header_layout.addWidget(self.toggle_btn)

        # Title
        self.title_label = QLabel("Recent")
        self.title_label.setStyleSheet("font-weight: bold; color: #333; font-size: 12px;")
        header_layout.addWidget(self.title_label)

        # Count badge
        self.count_label = QLabel("(0)")
        self.count_label.setStyleSheet("color: #666; font-size: 11px;")
        header_layout.addWidget(self.count_label)

        # Summary (shown when collapsed)
        self.summary_label = QLabel("")
        self.summary_label.setStyleSheet("color: #888; font-size: 11px;")
        self.summary_label.hide()
        header_layout.addWidget(self.summary_label, 1)

        header_layout.addStretch()

        # View All link
        self.view_all_btn = QPushButton("View All →")
        self.view_all_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                color: #007bff;
                font-size: 11px;
            }
            QPushButton:hover {
                color: #0056b3;
                text-decoration: underline;
            }
        """)
        self.view_all_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.view_all_btn.clicked.connect(self.view_all_clicked.emit)
        header_layout.addWidget(self.view_all_btn)

        main_layout.addWidget(self.header)

        # Content area (collapsible)
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)

        # Items container
        self.items_container = QWidget()
        self.items_layout = QVBoxLayout(self.items_container)
        self.items_layout.setContentsMargins(4, 4, 4, 4)
        self.items_layout.setSpacing(2)

        self.content_layout.addWidget(self.items_container)

        main_layout.addWidget(self.content)

        # Animation for collapse/expand
        self.animation = QPropertyAnimation(self.content, b"maximumHeight")
        self.animation.setDuration(200)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        # Load initial data
        self.refresh()

    def refresh(self):
        """Reload transcripts from database and rebuild the list."""
        # Clear existing items
        while self.items_layout.count():
            item = self.items_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Fetch recent transcripts
        self._transcripts = self.database.get_recent_transcriptions(limit=self.max_items)

        # Update count
        count = len(self._transcripts)
        self.count_label.setText(f"({count})")

        # Add items
        for doc in self._transcripts:
            item = RecentTranscriptItem(
                transcript_id=doc.get("id") or str(doc.get("_id", "")),
                transcript_text=doc.get("transcript_text", ""),
                timestamp=doc.get("timestamp", ""),
                word_count=doc.get("word_count", 0),
            )
            item.copy_clicked.connect(self._on_item_copy)
            item.item_clicked.connect(self._on_item_clicked)
            self.items_layout.addWidget(item)

        # Update summary for collapsed state
        self._update_summary()

        # Update content height
        if not self.collapsed:
            self.content.setMaximumHeight(16777215)  # QWIDGETSIZE_MAX

    def _update_summary(self):
        """Update the summary label for collapsed state."""
        if not self._transcripts:
            self.summary_label.setText("No recent transcriptions")
            return

        # Show first transcript preview when collapsed
        first = self._transcripts[0]
        preview = truncate_text(first.get("transcript_text", ""), 40)
        self.summary_label.setText(preview)

    def _on_item_copy(self, transcript_id: str):
        """Handle copy button click on an item."""
        # Find the transcript
        for doc in self._transcripts:
            doc_id = doc.get("id") or str(doc.get("_id", ""))
            if doc_id == transcript_id:
                text = doc.get("transcript_text", "")
                if text:
                    copy_to_clipboard(text)
                    self.transcript_copied.emit(transcript_id)
                break

    def _on_item_clicked(self, transcript_id: str):
        """Handle item click (load into editor)."""
        self.transcript_selected.emit(transcript_id)

    def toggle_collapse(self):
        """Toggle between collapsed and expanded states."""
        if self.collapsed:
            self.expand()
        else:
            self.collapse()

    def collapse(self):
        """Collapse the panel to just the header."""
        if self.collapsed:
            return

        self.collapsed = True
        self.toggle_btn.setText("▶")
        self.summary_label.show()

        # Animate
        self.animation.stop()
        self.animation.setStartValue(self.content.height())
        self.animation.setEndValue(0)
        self.animation.start()

    def expand(self):
        """Expand the panel to show all items."""
        if not self.collapsed:
            return

        self.collapsed = False
        self.toggle_btn.setText("▼")
        self.summary_label.hide()

        # Calculate target height
        target_height = self.items_container.sizeHint().height() + 8

        # Animate
        self.animation.stop()
        self.animation.setStartValue(0)
        self.animation.setEndValue(target_height)
        self.animation.finished.connect(self._on_expand_finished)
        self.animation.start()

    def _on_expand_finished(self):
        """Called when expand animation finishes."""
        self.animation.finished.disconnect(self._on_expand_finished)
        self.content.setMaximumHeight(16777215)  # QWIDGETSIZE_MAX

    def set_collapsed(self, collapsed: bool):
        """Set collapsed state without animation."""
        self.collapsed = collapsed
        if collapsed:
            self.toggle_btn.setText("▶")
            self.summary_label.show()
            self.content.setMaximumHeight(0)
        else:
            self.toggle_btn.setText("▼")
            self.summary_label.hide()
            self.content.setMaximumHeight(16777215)

    def copy_by_index(self, index: int) -> bool:
        """Copy transcript at given index (0-based). Returns True if copied."""
        if 0 <= index < len(self._transcripts):
            doc = self._transcripts[index]
            text = doc.get("transcript_text", "")
            if text:
                copy_to_clipboard(text)
                transcript_id = doc.get("id") or str(doc.get("_id", ""))
                self.transcript_copied.emit(transcript_id)
                return True
        return False

    def get_most_recent_text(self) -> Optional[str]:
        """Get the text of the most recent transcript, or None if empty."""
        if self._transcripts:
            return self._transcripts[0].get("transcript_text", "")
        return None
