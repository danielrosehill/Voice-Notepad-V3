"""Cost tracking tab widget for viewing API spending."""

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QGroupBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from .database import get_db


class CostWidget(QWidget):
    """Widget for viewing API cost tracking."""

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
        title = QLabel("API Cost Tracking")
        title.setFont(QFont("Sans", 14, QFont.Weight.Bold))
        header.addWidget(title)
        header.addStretch()

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        header.addWidget(refresh_btn)

        layout.addLayout(header)

        # Future feature notice
        notice = QLabel(
            "Detailed cost breakdown by time period is planned for a future release.\n"
            "The tables below show cumulative usage since tracking began."
        )
        notice.setStyleSheet(
            "color: #0c5460; background-color: #d1ecf1; border: 1px solid #bee5eb; "
            "border-radius: 4px; padding: 10px; font-size: 12px;"
        )
        notice.setWordWrap(True)
        layout.addWidget(notice)

        # Provider breakdown table
        provider_group = QGroupBox("Cost by Provider")
        provider_layout = QVBoxLayout(provider_group)

        self.provider_table = QTableWidget()
        self.provider_table.setColumnCount(3)
        self.provider_table.setHorizontalHeaderLabels(["Provider", "Transcriptions", "Total Cost"])
        self.provider_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.provider_table.setAlternatingRowColors(True)
        self.provider_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.provider_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.provider_table.setMaximumHeight(150)
        provider_layout.addWidget(self.provider_table)

        layout.addWidget(provider_group)

        # Model breakdown table
        model_group = QGroupBox("Cost by Model")
        model_layout = QVBoxLayout(model_group)

        self.model_table = QTableWidget()
        self.model_table.setColumnCount(4)
        self.model_table.setHorizontalHeaderLabels(["Provider", "Model", "Transcriptions", "Total Cost"])
        self.model_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.model_table.setAlternatingRowColors(True)
        self.model_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.model_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        model_layout.addWidget(self.model_table)

        layout.addWidget(model_group, 1)

        # Warning about estimates
        note_label = QLabel(
            "All costs shown are estimates based on token usage and may not reflect actual billing. "
            "Audio token pricing varies by provider. Check your provider's dashboard for precise costs."
        )
        note_label.setWordWrap(True)
        note_label.setStyleSheet(
            "color: #856404; background-color: #fff3cd; border: 1px solid #ffeeba; "
            "border-radius: 4px; padding: 8px; font-size: 11px;"
        )
        layout.addWidget(note_label)

    def refresh(self):
        """Refresh all cost data."""
        db = get_db()

        # Provider breakdown
        providers = db.get_cost_by_provider()
        self.provider_table.setRowCount(len(providers))
        for row, provider_data in enumerate(providers):
            self.provider_table.setItem(row, 0, QTableWidgetItem(provider_data["provider"].title()))
            self.provider_table.setItem(row, 1, QTableWidgetItem(str(provider_data["count"])))
            self.provider_table.setItem(row, 2, QTableWidgetItem(f"~${provider_data['total_cost']:.4f}"))

        # Model breakdown
        models = db.get_cost_by_model()
        self.model_table.setRowCount(len(models))
        for row, model_data in enumerate(models):
            self.model_table.setItem(row, 0, QTableWidgetItem(model_data["provider"].title()))
            self.model_table.setItem(row, 1, QTableWidgetItem(model_data["model"]))
            self.model_table.setItem(row, 2, QTableWidgetItem(str(model_data["count"])))
            self.model_table.setItem(row, 3, QTableWidgetItem(f"~${model_data['total_cost']:.4f}"))
