"""Analysis tab widget for viewing model performance statistics."""

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QFrame,
    QGroupBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from .database import get_db


def format_size(size_bytes: int) -> str:
    """Format bytes to human readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


class AnalysisWidget(QWidget):
    """Widget for viewing transcription analytics."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.refresh()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(12, 12, 12, 12)

        # Header
        header = QHBoxLayout()
        title = QLabel("Performance Analytics")
        title.setFont(QFont("Sans", 14, QFont.Weight.Bold))
        header.addWidget(title)
        header.addStretch()

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        header.addWidget(refresh_btn)

        layout.addLayout(header)

        # Summary stats
        stats_group = QGroupBox("Summary (Last 7 Days)")
        stats_layout = QHBoxLayout(stats_group)

        self.stat_labels = {}
        stat_items = [
            ("transcriptions", "Transcriptions"),
            ("total_cost", "Total Cost"),
            ("avg_inference", "Avg Inference"),
            ("total_words", "Total Words"),
        ]

        for key, label in stat_items:
            stat_widget = QWidget()
            stat_vbox = QVBoxLayout(stat_widget)
            stat_vbox.setSpacing(2)

            value_label = QLabel("--")
            value_label.setFont(QFont("Sans", 18, QFont.Weight.Bold))
            value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            stat_vbox.addWidget(value_label)

            name_label = QLabel(label)
            name_label.setStyleSheet("color: #666;")
            name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            stat_vbox.addWidget(name_label)

            self.stat_labels[key] = value_label
            stats_layout.addWidget(stat_widget)

        layout.addWidget(stats_group)

        # Model performance table
        model_group = QGroupBox("Model Performance")
        model_layout = QVBoxLayout(model_group)

        model_layout.addWidget(QLabel(
            "Performance metrics based on all transcriptions. "
            "Chars/sec measures how quickly each model generates output text."
        ))

        self.model_table = QTableWidget()
        self.model_table.setColumnCount(6)
        self.model_table.setHorizontalHeaderLabels([
            "Provider", "Model", "Count", "Avg Inference (ms)", "Chars/sec", "Total Cost"
        ])
        self.model_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.model_table.setAlternatingRowColors(True)
        self.model_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.model_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        model_layout.addWidget(self.model_table)

        layout.addWidget(model_group, 1)

        # Storage info
        storage_group = QGroupBox("Storage")
        storage_layout = QVBoxLayout(storage_group)

        self.storage_info = QLabel("")
        self.storage_info.setWordWrap(True)
        storage_layout.addWidget(self.storage_info)

        storage_actions = QHBoxLayout()
        storage_actions.addStretch()

        clear_btn = QPushButton("Clear All Data")
        clear_btn.setStyleSheet("color: #dc3545;")
        clear_btn.clicked.connect(self.clear_all_data)
        storage_actions.addWidget(clear_btn)

        storage_layout.addLayout(storage_actions)
        layout.addWidget(storage_group)

    def refresh(self):
        """Refresh all analytics data."""
        db = get_db()

        # Recent stats
        recent = db.get_recent_stats(days=7)
        self.stat_labels["transcriptions"].setText(str(recent["count"]))
        self.stat_labels["total_cost"].setText(f"${recent['total_cost']:.2f}")
        self.stat_labels["avg_inference"].setText(
            f"{recent['avg_inference_ms']:.0f}ms" if recent['avg_inference_ms'] else "--"
        )
        self.stat_labels["total_words"].setText(f"{recent['total_words']:,}")

        # Model performance
        performance = db.get_model_performance()
        self.model_table.setRowCount(len(performance))

        for row, perf in enumerate(performance):
            self.model_table.setItem(row, 0, QTableWidgetItem(perf["provider"].title()))
            self.model_table.setItem(row, 1, QTableWidgetItem(perf["model"]))
            self.model_table.setItem(row, 2, QTableWidgetItem(str(perf["count"])))
            self.model_table.setItem(row, 3, QTableWidgetItem(f"{perf['avg_inference_ms']:.0f}"))
            self.model_table.setItem(row, 4, QTableWidgetItem(f"{perf['avg_chars_per_sec']:.1f}"))
            self.model_table.setItem(row, 5, QTableWidgetItem(f"${perf['total_cost']:.2f}"))

        # Storage stats
        storage = db.get_storage_stats()
        self.storage_info.setText(
            f"Total records: {storage['total_records']:,}\n"
            f"Records with audio: {storage['records_with_audio']:,}\n"
            f"Database size: {format_size(storage['db_size_bytes'])}\n"
            f"Audio archive size: {format_size(storage['audio_size_bytes'])}\n"
            f"Total storage: {format_size(storage['total_size_bytes'])}"
        )

    def clear_all_data(self):
        """Clear all transcription data after confirmation."""
        from PyQt6.QtWidgets import QMessageBox

        reply = QMessageBox.warning(
            self,
            "Clear All Data",
            "This will permanently delete ALL transcription history and audio archives.\n\n"
            "This action cannot be undone!\n\n"
            "Are you absolutely sure?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            # Double confirm
            reply2 = QMessageBox.question(
                self,
                "Final Confirmation",
                "Please confirm: Delete all data?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            if reply2 == QMessageBox.StandardButton.Yes:
                db = get_db()
                deleted = db.delete_all()
                QMessageBox.information(
                    self,
                    "Data Cleared",
                    f"Deleted {deleted} transcriptions.",
                )
                self.refresh()
