"""Cost tracking tab widget for viewing API spending (OpenRouter Only)."""

from datetime import date
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QGroupBox,
    QFrame,
    QGridLayout,
    QDateEdit,
    QFileDialog,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QFont

from .database_mongo import get_db
from .config import load_config


class BigStatCard(QFrame):
    """Large stat display card."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            BigStatCard {
                background-color: #f8f9fa;
                border: 2px solid #dee2e6;
                border-radius: 8px;
            }
        """)
        self.setMinimumHeight(100)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)

        # Title
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("color: #6c757d; font-size: 12px; font-weight: bold;")
        layout.addWidget(self.title_label)

        # Value
        self.value_label = QLabel("--")
        self.value_label.setFont(QFont("Sans", 24, QFont.Weight.Bold))
        self.value_label.setStyleSheet("color: #212529;")
        layout.addWidget(self.value_label)

        # Subtitle
        self.subtitle_label = QLabel("")
        self.subtitle_label.setStyleSheet("color: #adb5bd; font-size: 10px;")
        layout.addWidget(self.subtitle_label)

        layout.addStretch()

    def set_value(self, value: str, subtitle: str = "", color: str = "#212529"):
        """Set the displayed value."""
        self.value_label.setText(value)
        self.value_label.setStyleSheet(f"color: {color}; font-size: 24px; font-weight: bold;")
        self.subtitle_label.setText(subtitle)


class CostWidget(QWidget):
    """Widget for viewing API cost tracking (OpenRouter Only)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._balance_cache = None
        self._key_info_cache = None
        self._last_api_fetch = 0
        self.setup_ui()
        self.refresh()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(12, 12, 12, 12)

        # Header
        header = QHBoxLayout()
        title = QLabel("API Cost Tracking (OpenRouter Only)")
        title.setFont(QFont("Sans", 14, QFont.Weight.Bold))
        header.addWidget(title)
        header.addStretch()

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.force_refresh)
        header.addWidget(refresh_btn)

        layout.addLayout(header)

        # OpenRouter Account Balance
        balance_group = QGroupBox("Account Balance")
        balance_layout = QHBoxLayout(balance_group)

        self.balance_card = BigStatCard("Available Balance")
        balance_layout.addWidget(self.balance_card)

        balance_right = QVBoxLayout()
        self.credits_label = QLabel("Total Credits: --")
        self.credits_label.setStyleSheet("color: #666; font-size: 11px;")
        balance_right.addWidget(self.credits_label)

        self.account_usage_label = QLabel("Account Usage: --")
        self.account_usage_label.setStyleSheet("color: #666; font-size: 11px;")
        balance_right.addWidget(self.account_usage_label)

        self.key_label = QLabel("")
        self.key_label.setStyleSheet("color: #007bff; font-size: 10px;")
        balance_right.addWidget(self.key_label)

        balance_right.addStretch()
        balance_layout.addLayout(balance_right)

        layout.addWidget(balance_group)

        # API Key Usage - Big Stats Grid
        usage_group = QGroupBox("This API Key's Usage")
        usage_grid = QGridLayout(usage_group)
        usage_grid.setSpacing(12)

        # Row 1: Today, This Week
        self.today_card = BigStatCard("Today")
        usage_grid.addWidget(self.today_card, 0, 0)

        self.week_card = BigStatCard("This Week")
        usage_grid.addWidget(self.week_card, 0, 1)

        # Row 2: This Month, All Time
        self.month_card = BigStatCard("This Month")
        usage_grid.addWidget(self.month_card, 1, 0)

        self.total_card = BigStatCard("All Time")
        usage_grid.addWidget(self.total_card, 1, 1)

        layout.addWidget(usage_group)

        # Local Statistics
        local_group = QGroupBox("Local Statistics (This App)")
        local_layout = QVBoxLayout(local_group)

        self.local_stats_label = QLabel("Transcriptions: -- | Words: -- | Characters: --")
        self.local_stats_label.setStyleSheet("color: #666; font-size: 12px;")
        local_layout.addWidget(self.local_stats_label)

        self.today_local_label = QLabel("Today: -- transcriptions")
        self.today_local_label.setStyleSheet("color: #666; font-size: 11px;")
        local_layout.addWidget(self.today_local_label)

        layout.addWidget(local_group)

        # Daily Cost Breakdown
        daily_group = QGroupBox("Daily Cost Breakdown (Last 30 Days)")
        daily_layout = QVBoxLayout(daily_group)

        # Cost efficiency summary
        self.efficiency_label = QLabel("Avg cost per transcription: --")
        self.efficiency_label.setStyleSheet("color: #666; font-size: 12px; font-weight: bold;")
        daily_layout.addWidget(self.efficiency_label)

        # Daily breakdown table
        self.daily_table = QTableWidget()
        self.daily_table.setColumnCount(4)
        self.daily_table.setHorizontalHeaderLabels(['Date', 'Count', 'Total Cost', 'Avg Cost'])
        self.daily_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.daily_table.setMaximumHeight(300)
        self.daily_table.setAlternatingRowColors(True)
        self.daily_table.setStyleSheet("""
            QTableWidget {
                gridline-color: #dee2e6;
                background-color: white;
            }
            QTableWidget::item {
                padding: 4px;
            }
            QHeaderView::section {
                background-color: #f8f9fa;
                padding: 4px;
                border: 1px solid #dee2e6;
                font-weight: bold;
            }
        """)
        daily_layout.addWidget(self.daily_table)

        layout.addWidget(daily_group)

        # Export Section
        export_group = QGroupBox("Export History")
        export_layout = QVBoxLayout(export_group)

        # Export All button
        export_all_btn = QPushButton("Export All History to CSV")
        export_all_btn.clicked.connect(self._export_all)
        export_layout.addWidget(export_all_btn)

        # Date range row
        date_range_layout = QHBoxLayout()

        date_range_layout.addWidget(QLabel("From:"))
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(QDate.currentDate().addMonths(-1))
        self.start_date.setDisplayFormat("yyyy-MM-dd")
        date_range_layout.addWidget(self.start_date)

        date_range_layout.addWidget(QLabel("To:"))
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDate(QDate.currentDate())
        self.end_date.setDisplayFormat("yyyy-MM-dd")
        date_range_layout.addWidget(self.end_date)

        export_range_btn = QPushButton("Export Range")
        export_range_btn.clicked.connect(self._export_range)
        date_range_layout.addWidget(export_range_btn)

        date_range_layout.addStretch()
        export_layout.addLayout(date_range_layout)

        layout.addWidget(export_group)

        # Status indicator
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #888; font-size: 10px;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.status_label)

        layout.addStretch()

    def force_refresh(self):
        """Force refresh, clearing cache."""
        self._last_api_fetch = 0
        self._balance_cache = None
        self._key_info_cache = None
        self.refresh()

    def refresh(self):
        """Refresh all cost data."""
        self._refresh_openrouter_data()
        self._refresh_local_stats()

    def _refresh_openrouter_data(self):
        """Refresh OpenRouter balance and key info from API."""
        import time

        config = load_config()
        api_key = config.openrouter_api_key

        if not api_key:
            self.balance_card.set_value("No API Key", "Set OpenRouter API key in Settings", "#dc3545")
            self.credits_label.setText("Total Credits: --")
            self.account_usage_label.setText("Account Usage: --")
            self.key_label.setText("")
            self.today_card.set_value("--", "No API key")
            self.week_card.set_value("--", "No API key")
            self.month_card.set_value("--", "No API key")
            self.total_card.set_value("--", "No API key")
            self.status_label.setText("")
            return

        current_time = time.time()
        use_cache = (current_time - self._last_api_fetch) < 60

        if use_cache and self._balance_cache and self._key_info_cache:
            self._display_balance(self._balance_cache)
            self._display_key_usage(self._key_info_cache)
            self.status_label.setText("(cached)")
            return

        try:
            from .openrouter_api import get_openrouter_api
            api = get_openrouter_api(api_key)

            # Fetch credits/balance
            credits = api.get_credits()
            if credits:
                self._balance_cache = credits
                self._display_balance(credits)

            # Fetch key info (key-specific usage)
            key_info = api.get_key_info()
            if key_info:
                self._key_info_cache = key_info
                self._display_key_usage(key_info)

            self._last_api_fetch = current_time
            self.status_label.setText("(live)")

        except Exception as e:
            self.balance_card.set_value("Error", str(e)[:40], "#dc3545")
            self.status_label.setText("")

    def _display_balance(self, credits):
        """Display the balance information."""
        balance = credits.balance

        if balance > 5.0:
            color = "#28a745"
        elif balance > 1.0:
            color = "#ffc107"
        else:
            color = "#dc3545"

        self.balance_card.set_value(f"${balance:.2f}", "", color)
        self.credits_label.setText(f"Total Credits: ${credits.total_credits:.2f}")
        self.account_usage_label.setText(f"Account Usage: ${credits.total_usage:.2f}")

    def _display_key_usage(self, key_info):
        """Display key-specific usage information."""
        if key_info.label:
            # Truncate key label for display
            label = key_info.label
            if len(label) > 20:
                label = label[:8] + "..." + label[-8:]
            self.key_label.setText(f"Key: {label}")
        else:
            self.key_label.setText("")

        # Today
        self.today_card.set_value(
            f"${key_info.usage_daily:.2f}",
            "from OpenRouter API"
        )

        # This week
        self.week_card.set_value(
            f"${key_info.usage_weekly:.2f}",
            "from OpenRouter API"
        )

        # This month
        self.month_card.set_value(
            f"${key_info.usage_monthly:.2f}",
            "from OpenRouter API"
        )

        # All time
        self.total_card.set_value(
            f"${key_info.usage:.2f}",
            "from OpenRouter API"
        )

    def _refresh_local_stats(self):
        """Refresh local statistics from database."""
        db = get_db()
        stats = db.get_recent_stats(days=30)
        today_stats = db.get_recent_stats(days=1)
        all_time = db.get_cost_all_time()

        self.local_stats_label.setText(
            f"Transcriptions: {stats['count']} | "
            f"Words: {stats['total_words']:,} | "
            f"Characters: {stats['total_chars']:,}"
        )

        self.today_local_label.setText(
            f"Today: {today_stats['count']} transcriptions"
        )

        # Update efficiency label
        if all_time['count'] > 0:
            avg_cost = all_time['total_cost'] / all_time['count']
            self.efficiency_label.setText(
                f"Avg cost per transcription: ${avg_cost:.4f} | "
                f"Total all-time: ${all_time['total_cost']:.4f} ({all_time['count']:,} transcriptions)"
            )
        else:
            self.efficiency_label.setText("No transcriptions yet")

        # Update daily breakdown table
        self._refresh_daily_breakdown()

    def _refresh_daily_breakdown(self):
        """Refresh the daily cost breakdown table."""
        db = get_db()
        daily_data = db.get_daily_cost_breakdown(days=30)

        self.daily_table.setRowCount(len(daily_data))

        for row, day in enumerate(daily_data):
            # Date
            date_item = QTableWidgetItem(day['date'])
            date_item.setFlags(date_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.daily_table.setItem(row, 0, date_item)

            # Count
            count_item = QTableWidgetItem(str(day['count']))
            count_item.setFlags(count_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.daily_table.setItem(row, 1, count_item)

            # Total cost
            cost_item = QTableWidgetItem(f"${day['cost']:.4f}")
            cost_item.setFlags(cost_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.daily_table.setItem(row, 2, cost_item)

            # Avg cost
            avg_item = QTableWidgetItem(f"${day['avg_cost']:.4f}")
            avg_item.setFlags(avg_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.daily_table.setItem(row, 3, avg_item)

    def _get_save_path(self, default_name: str) -> Path | None:
        """Show file dialog and return selected path."""
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Export Transcription History",
            str(Path.home() / default_name),
            "CSV Files (*.csv);;All Files (*)",
        )
        return Path(filepath) if filepath else None

    def _export_all(self):
        """Export all transcription history to CSV."""
        filepath = self._get_save_path("voice_notepad_history.csv")
        if not filepath:
            return

        db = get_db()
        try:
            _, count = db.export_to_csv(filepath)
            QMessageBox.information(
                self,
                "Export Complete",
                f"Exported {count} transcriptions to:\n{filepath}",
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Export Failed",
                f"Failed to export: {e}",
            )

    def _export_range(self):
        """Export transcription history for selected date range."""
        start = self.start_date.date().toString("yyyy-MM-dd")
        end = self.end_date.date().toString("yyyy-MM-dd")

        # Validate date range
        if self.start_date.date() > self.end_date.date():
            QMessageBox.warning(
                self,
                "Invalid Date Range",
                "Start date must be before or equal to end date.",
            )
            return

        filepath = self._get_save_path(f"voice_notepad_{start}_to_{end}.csv")
        if not filepath:
            return

        db = get_db()
        try:
            _, count = db.export_to_csv(filepath, start_date=start, end_date=end)
            QMessageBox.information(
                self,
                "Export Complete",
                f"Exported {count} transcriptions ({start} to {end}) to:\n{filepath}",
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Export Failed",
                f"Failed to export: {e}",
            )
