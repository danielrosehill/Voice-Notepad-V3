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
    QGridLayout,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from .database import get_db


class CostCard(QWidget):
    """A card widget displaying a cost metric."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.title = title
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(4)
        layout.setContentsMargins(12, 12, 12, 12)

        # Title
        title_label = QLabel(self.title)
        title_label.setStyleSheet("color: #666; font-size: 11px;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        # Cost value
        self.cost_label = QLabel("$0.0000")
        self.cost_label.setFont(QFont("Sans", 20, QFont.Weight.Bold))
        self.cost_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.cost_label)

        # Count
        self.count_label = QLabel("0 transcriptions")
        self.count_label.setStyleSheet("color: #888; font-size: 10px;")
        self.count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.count_label)

        # Style the card
        self.setStyleSheet("""
            CostCard {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 8px;
            }
        """)

    def set_values(self, cost: float, count: int):
        """Update the displayed values."""
        self.cost_label.setText(f"~${cost:.4f}")
        self.count_label.setText(f"{count} transcription{'s' if count != 1 else ''}")


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

        # Time period cards
        time_group = QGroupBox("Cost by Time Period")
        time_layout = QGridLayout(time_group)
        time_layout.setSpacing(12)

        self.this_hour_card = CostCard("This Hour")
        time_layout.addWidget(self.this_hour_card, 0, 0)

        self.last_hour_card = CostCard("Last Hour")
        time_layout.addWidget(self.last_hour_card, 0, 1)

        self.today_card = CostCard("Today")
        time_layout.addWidget(self.today_card, 1, 0)

        self.this_week_card = CostCard("This Week")
        time_layout.addWidget(self.this_week_card, 1, 1)

        self.all_time_card = CostCard("All Time")
        self.all_time_card.cost_label.setStyleSheet("color: #007bff;")
        time_layout.addWidget(self.all_time_card, 2, 0, 1, 2)

        layout.addWidget(time_group)

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
        self.provider_table.setMaximumHeight(120)
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
            "⚠ All costs shown are estimates based on token usage and may not reflect actual billing. "
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

        # Time period costs
        this_hour = db.get_cost_this_hour()
        self.this_hour_card.set_values(this_hour["total_cost"], this_hour["count"])

        last_hour = db.get_cost_last_hour()
        self.last_hour_card.set_values(last_hour["total_cost"], last_hour["count"])

        today = db.get_cost_today()
        self.today_card.set_values(today["total_cost"], today["count"])

        this_week = db.get_cost_this_week()
        self.this_week_card.set_values(this_week["total_cost"], this_week["count"])

        all_time = db.get_cost_all_time()
        self.all_time_card.set_values(all_time["total_cost"], all_time["count"])

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
