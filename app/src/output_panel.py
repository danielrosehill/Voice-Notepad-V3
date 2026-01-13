"""Dual Output Panel - Side-by-side transcription output for queue workflow.

Provides two output slots that can display transcriptions simultaneously,
supporting the rapid dictation queue workflow.
"""

from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QSplitter,
    QSizePolicy,
)

from .markdown_widget import MarkdownTextWidget
from .clipboard import copy_to_clipboard


class OutputSlot(QFrame):
    """Single output panel with text and copy button."""

    copy_clicked = pyqtSignal(int)  # slot_number
    text_changed = pyqtSignal(int)  # slot_number

    def __init__(self, slot_number: int, parent=None):
        super().__init__(parent)
        self.slot_number = slot_number
        self.item_id: Optional[str] = None
        self._has_content = False

        self.setFrameStyle(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            OutputSlot {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 6px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        # Header with slot label and copy button
        header = QHBoxLayout()
        header.setSpacing(8)

        self.slot_label = QLabel(f"Slot {slot_number + 1}")
        self.slot_label.setStyleSheet("color: #888; font-size: 10px; font-weight: bold;")
        header.addWidget(self.slot_label)

        header.addStretch()

        # Status label (shows "Transcribing..." or timestamp)
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #888; font-size: 10px;")
        header.addWidget(self.status_label)

        # Copy button
        self.copy_btn = QPushButton("Copy")
        self.copy_btn.setFixedSize(50, 24)
        self.copy_btn.setStyleSheet("""
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
            QPushButton:disabled {
                color: #aaa;
                background-color: #f8f8f8;
            }
        """)
        self.copy_btn.clicked.connect(self._on_copy)
        self.copy_btn.setEnabled(False)
        header.addWidget(self.copy_btn)

        layout.addLayout(header)

        # Text widget
        self.text_widget = MarkdownTextWidget()
        self.text_widget.setPlaceholderText("")
        self.text_widget.setFont(QFont("Sans", 11))
        self.text_widget.setMinimumHeight(60)
        self.text_widget.textChanged.connect(self._on_text_changed)
        layout.addWidget(self.text_widget, 1)

        # Set minimum size
        self.setMinimumWidth(200)

    def set_content(self, text: str, item_id: str):
        """Display transcription result."""
        self.item_id = item_id
        self._has_content = True
        self.text_widget.setMarkdown(text)
        self.status_label.setText("")
        self.status_label.setStyleSheet("color: #888; font-size: 10px;")
        self.copy_btn.setEnabled(True)
        self.setStyleSheet("""
            OutputSlot {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 6px;
            }
        """)

    def set_transcribing(self, item_id: str):
        """Show transcribing state with spinner/status."""
        self.item_id = item_id
        self._has_content = False
        self.text_widget.setMarkdown("")
        self.text_widget.setPlaceholderText("Transcribing...")
        self.status_label.setText("⏳ Transcribing...")
        self.status_label.setStyleSheet("color: #0d6efd; font-size: 10px;")
        self.copy_btn.setEnabled(False)
        self.setStyleSheet("""
            OutputSlot {
                background-color: #f8f9ff;
                border: 1px solid #b6d4fe;
                border-radius: 6px;
            }
        """)

    def set_status(self, status: str):
        """Update the status label."""
        self.status_label.setText(f"⏳ {status}")

    def set_error(self, item_id: str, error: str):
        """Display error state."""
        self.item_id = item_id
        self._has_content = False
        self.text_widget.setMarkdown(f"**Error:** {error}")
        self.status_label.setText("❌ Failed")
        self.status_label.setStyleSheet("color: #dc3545; font-size: 10px;")
        self.copy_btn.setEnabled(False)
        self.setStyleSheet("""
            OutputSlot {
                background-color: #fff5f5;
                border: 1px solid #f5c6cb;
                border-radius: 6px;
            }
        """)

    def clear(self):
        """Reset to empty state."""
        self.item_id = None
        self._has_content = False
        self.text_widget.setMarkdown("")
        self.text_widget.setPlaceholderText("")
        self.status_label.setText("")
        self.copy_btn.setEnabled(False)
        self.setStyleSheet("""
            OutputSlot {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 6px;
            }
        """)

    def has_content(self) -> bool:
        """Check if this slot has content."""
        return self._has_content

    def is_transcribing(self) -> bool:
        """Check if this slot is actively transcribing (waiting for result)."""
        return self.item_id is not None and not self._has_content

    def get_text(self) -> str:
        """Get the current text content."""
        return self.text_widget.toPlainText()

    def _on_copy(self):
        """Handle copy button click."""
        text = self.get_text()
        if text:
            copy_to_clipboard(text)
            self.copy_clicked.emit(self.slot_number)

    def _on_text_changed(self):
        """Handle text changes."""
        self.text_changed.emit(self.slot_number)


class DualOutputPanel(QWidget):
    """Container for two side-by-side output slots with queue indicator."""

    copy_clicked = pyqtSignal(int)  # slot_number
    text_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self._dual_mode = False
        self._slot_assignments: dict[str, int] = {}  # item_id -> slot_number

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Splitter for side-by-side slots
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #e0e0e0;
                width: 4px;
            }
            QSplitter::handle:hover {
                background-color: #c0c0c0;
            }
        """)

        # Create two slots
        self.slot1 = OutputSlot(0)
        self.slot1.copy_clicked.connect(self.copy_clicked.emit)
        self.slot1.text_changed.connect(lambda: self.text_changed.emit())

        self.slot2 = OutputSlot(1)
        self.slot2.copy_clicked.connect(self.copy_clicked.emit)
        self.slot2.text_changed.connect(lambda: self.text_changed.emit())

        self.splitter.addWidget(self.slot1)
        self.splitter.addWidget(self.slot2)

        # Start in single mode (slot2 hidden)
        self.slot2.hide()

        layout.addWidget(self.splitter, 1)

        # Queue indicator bar
        self.queue_bar = QFrame()
        self.queue_bar.setStyleSheet("""
            QFrame {
                background-color: #f0f0f0;
                border-radius: 4px;
            }
        """)
        queue_layout = QHBoxLayout(self.queue_bar)
        queue_layout.setContentsMargins(8, 4, 8, 4)

        self.queue_label = QLabel("")
        self.queue_label.setStyleSheet("color: #666; font-size: 11px;")
        queue_layout.addWidget(self.queue_label)

        queue_layout.addStretch()

        self.queue_bar.hide()
        layout.addWidget(self.queue_bar)

    def on_transcription_queued(self, item_id: str):
        """Handle new item queued - update queue indicator."""
        self._update_queue_indicator()

    def on_transcription_started(self, item_id: str):
        """Show transcribing state in next available slot."""
        slot = self._get_available_slot()
        if slot is None:
            # Both slots in use - this shouldn't happen with max_concurrent=2
            # but handle gracefully by using slot 2
            slot = self.slot2

        self._slot_assignments[item_id] = slot.slot_number

        # Switch to dual mode if using slot2
        if slot.slot_number == 1 and not self._dual_mode:
            self._enable_dual_mode()

        slot.set_transcribing(item_id)
        self._update_queue_indicator()

    def on_transcription_status(self, item_id: str, status: str):
        """Update status for an item."""
        slot = self._get_slot_for_item(item_id)
        if slot:
            slot.set_status(status)

    def on_transcription_complete(self, item_id: str, text: str):
        """Display result in the slot that was transcribing."""
        slot = self._get_slot_for_item(item_id)
        if slot:
            slot.set_content(text, item_id)
        self._update_queue_indicator()

    def on_transcription_error(self, item_id: str, error: str):
        """Display error in the slot that was transcribing."""
        slot = self._get_slot_for_item(item_id)
        if slot:
            slot.set_error(item_id, error)
        self._update_queue_indicator()

    def update_queue_status(self, pending_count: int, active_count: int):
        """Update the queue indicator with current counts."""
        if pending_count > 0:
            self.queue_label.setText(f"Queue: {pending_count} waiting")
            self.queue_bar.show()
        else:
            self.queue_bar.hide()

    def _get_available_slot(self) -> Optional[OutputSlot]:
        """Get the next available slot for a new transcription.

        Slot2 is only used when slot1 is actively transcribing (concurrent mode).
        For sequential transcriptions (one at a time), we always reuse slot1.
        """
        # If slot1 is empty, use it
        if self.slot1.item_id is None:
            return self.slot1

        # If slot1 is actively transcribing, check if we need concurrent mode
        if self.slot1.is_transcribing():
            # Slot1 is busy - use slot2 for concurrent transcription
            if self.slot2.item_id is None or not self.slot2.is_transcribing():
                return self.slot2
            # Both slots are transcribing - shouldn't happen with max_concurrent=2
            # but handle gracefully by clearing slot1
            self.slot1.clear()
            return self.slot1

        # Slot1 has completed content from previous transcription
        # Clear it and reuse for sequential mode (no dual panel)
        self.slot1.clear()
        # Disable dual mode if it was enabled - we're back to sequential mode
        if self._dual_mode:
            self._disable_dual_mode()
        return self.slot1

    def _get_slot_for_item(self, item_id: str) -> Optional[OutputSlot]:
        """Find which slot is assigned to an item."""
        slot_num = self._slot_assignments.get(item_id)
        if slot_num == 0:
            return self.slot1
        elif slot_num == 1:
            return self.slot2
        return None

    def _enable_dual_mode(self):
        """Switch to dual-slot mode."""
        if self._dual_mode:
            return
        self._dual_mode = True
        self.slot2.show()
        self.splitter.setSizes([1, 1])  # Equal widths

    def _disable_dual_mode(self):
        """Switch back to single-slot mode."""
        if not self._dual_mode:
            return
        self._dual_mode = False
        self.slot2.hide()
        self.slot2.clear()

    def _update_queue_indicator(self):
        """Update the queue bar visibility."""
        # This will be called with actual counts from the queue
        pass

    def is_dual_mode(self) -> bool:
        """Check if we're in dual mode."""
        return self._dual_mode

    def get_primary_text(self) -> str:
        """Get text from the primary (slot1) output."""
        return self.slot1.get_text()

    def get_all_text(self) -> str:
        """Get combined text from both slots."""
        text1 = self.slot1.get_text()
        text2 = self.slot2.get_text() if self._dual_mode else ""
        if text1 and text2:
            return text1 + "\n\n" + text2
        return text1 or text2

    def set_text(self, text: str):
        """Set text in the primary slot (for compatibility with single-output mode)."""
        self.slot1.set_content(text, "")
        self._slot_assignments[""] = 0

    def clear(self):
        """Clear both slots."""
        self.slot1.clear()
        self.slot2.clear()
        self._slot_assignments.clear()
        self._disable_dual_mode()

    def clear_slot(self, slot_number: int):
        """Clear a specific slot."""
        if slot_number == 0:
            # Remove assignment
            for item_id, num in list(self._slot_assignments.items()):
                if num == 0:
                    del self._slot_assignments[item_id]
            self.slot1.clear()
        elif slot_number == 1:
            for item_id, num in list(self._slot_assignments.items()):
                if num == 1:
                    del self._slot_assignments[item_id]
            self.slot2.clear()
            # Consider disabling dual mode if slot1 is also empty
            if not self.slot1.has_content():
                self._disable_dual_mode()
