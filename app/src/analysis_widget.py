"""Analysis tab widget for viewing model performance statistics."""

import json
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

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
    QFileDialog,
    QMessageBox,
    QButtonGroup,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

import pyqtgraph as pg

from .database_mongo import get_db
from .config import OPENROUTER_MODELS


# Build a lookup dict from model_id -> display_name
MODEL_DISPLAY_NAMES = {}
for model_id, display_name in OPENROUTER_MODELS:
    MODEL_DISPLAY_NAMES[model_id] = display_name

# Provider display names (keep gemini for legacy data display)
PROVIDER_DISPLAY_NAMES = {
    "gemini": "Google Gemini (Legacy)",
    "openrouter": "OpenRouter",
}

# Time period options: (key, display_name, days) - days=-1 means all time
TIME_PERIODS = [
    ("today", "Today", 1),
    ("7days", "7 Days", 7),
    ("30days", "30 Days", 30),
    ("all", "All Time", -1),
]

# Metric options for the chart (words first as default)
CHART_METRICS = [
    ("words", "Words"),
    ("transcripts", "Transcripts"),
    ("characters", "Characters"),
]


def get_model_display_name(model_id: str) -> str:
    """Get human-readable display name for a model ID."""
    return MODEL_DISPLAY_NAMES.get(model_id, model_id)


def get_provider_display_name(provider: str) -> str:
    """Get human-readable display name for a provider."""
    return PROVIDER_DISPLAY_NAMES.get(provider.lower(), provider.title())


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


def format_word_count(count: int) -> str:
    """Format word count to K notation (rounded up to nearest thousand)."""
    import math
    if count == 0:
        return "0"
    if count < 1000:
        return str(count)
    # Round up to nearest thousand
    thousands = math.ceil(count / 1000)
    return f"{thousands}K"


def format_number(count: int) -> str:
    """Format large numbers with K/M suffix."""
    if count < 1000:
        return str(count)
    elif count < 1_000_000:
        return f"{count / 1000:.1f}K"
    else:
        return f"{count / 1_000_000:.1f}M"


class AnalysisWidget(QWidget):
    """Widget for viewing transcription analytics."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_period = "all"  # Default to All Time
        self.current_metric = "words"
        self.setup_ui()
        self.refresh()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(12, 12, 12, 12)

        # Header with refresh and export buttons
        header = QHBoxLayout()
        title = QLabel("Performance Analytics")
        title.setFont(QFont("Sans", 14, QFont.Weight.Bold))
        header.addWidget(title)
        header.addStretch()

        export_btn = QPushButton("Export Stats")
        export_btn.clicked.connect(self.export_stats)
        header.addWidget(export_btn)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        header.addWidget(refresh_btn)

        layout.addLayout(header)

        # Combined filter row with toggle buttons
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(20)

        # Time period toggle buttons
        period_container = QHBoxLayout()
        period_container.setSpacing(0)
        period_label = QLabel("Period:")
        period_label.setStyleSheet("color: #888; margin-right: 8px;")
        period_container.addWidget(period_label)

        self.period_buttons = QButtonGroup(self)
        self.period_buttons.setExclusive(True)
        for i, (key, display, _) in enumerate(TIME_PERIODS):
            btn = QPushButton(display)
            btn.setCheckable(True)
            btn.setProperty("period_key", key)
            btn.setStyleSheet("""
                QPushButton {
                    padding: 4px 12px;
                    border: 1px solid #555;
                    background: #2d2d2d;
                    color: #ccc;
                }
                QPushButton:checked {
                    background: #4a9eff;
                    border-color: #4a9eff;
                    color: white;
                }
                QPushButton:hover:!checked {
                    background: #3d3d3d;
                }
            """)
            if i == 0:
                btn.setStyleSheet(btn.styleSheet() + "QPushButton { border-radius: 4px 0 0 4px; }")
            elif i == len(TIME_PERIODS) - 1:
                btn.setStyleSheet(btn.styleSheet() + "QPushButton { border-radius: 0 4px 4px 0; border-left: none; }")
            else:
                btn.setStyleSheet(btn.styleSheet() + "QPushButton { border-radius: 0; border-left: none; }")
            if key == self.current_period:
                btn.setChecked(True)
            self.period_buttons.addButton(btn, i)
            period_container.addWidget(btn)

        filter_layout.addLayout(period_container)

        # Metric toggle buttons
        metric_container = QHBoxLayout()
        metric_container.setSpacing(0)
        metric_label = QLabel("Show:")
        metric_label.setStyleSheet("color: #888; margin-right: 8px;")
        metric_container.addWidget(metric_label)

        self.metric_buttons = QButtonGroup(self)
        self.metric_buttons.setExclusive(True)
        for i, (key, display) in enumerate(CHART_METRICS):
            btn = QPushButton(display)
            btn.setCheckable(True)
            btn.setProperty("metric_key", key)
            btn.setStyleSheet("""
                QPushButton {
                    padding: 4px 12px;
                    border: 1px solid #555;
                    background: #2d2d2d;
                    color: #ccc;
                }
                QPushButton:checked {
                    background: #4a9eff;
                    border-color: #4a9eff;
                    color: white;
                }
                QPushButton:hover:!checked {
                    background: #3d3d3d;
                }
            """)
            if i == 0:
                btn.setStyleSheet(btn.styleSheet() + "QPushButton { border-radius: 4px 0 0 4px; }")
            elif i == len(CHART_METRICS) - 1:
                btn.setStyleSheet(btn.styleSheet() + "QPushButton { border-radius: 0 4px 4px 0; border-left: none; }")
            else:
                btn.setStyleSheet(btn.styleSheet() + "QPushButton { border-radius: 0; border-left: none; }")
            if key == self.current_metric:
                btn.setChecked(True)
            self.metric_buttons.addButton(btn, i)
            metric_container.addWidget(btn)

        filter_layout.addLayout(metric_container)
        filter_layout.addStretch()

        # Connect button groups
        self.period_buttons.buttonClicked.connect(self.on_period_button_clicked)
        self.metric_buttons.buttonClicked.connect(self.on_metric_button_clicked)

        layout.addLayout(filter_layout)

        # Summary stats
        self.stats_group = QGroupBox("Summary")
        stats_layout = QHBoxLayout(self.stats_group)

        self.stat_labels = {}
        stat_items = [
            ("total_words", "Total Words", "📝"),
            ("transcriptions", "Transcriptions", "📄"),
            ("avg_inference", "Avg Inference", "⚡"),
        ]

        for key, label, icon in stat_items:
            stat_widget = QWidget()
            stat_vbox = QVBoxLayout(stat_widget)
            stat_vbox.setSpacing(2)

            # Icon
            icon_label = QLabel(icon)
            icon_label.setFont(QFont("Sans", 20))
            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            stat_vbox.addWidget(icon_label)

            value_label = QLabel("--")
            value_label.setFont(QFont("Sans", 16, QFont.Weight.Bold))
            value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            stat_vbox.addWidget(value_label)

            name_label = QLabel(label)
            name_label.setStyleSheet("color: #666;")
            name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            stat_vbox.addWidget(name_label)

            self.stat_labels[key] = value_label
            stats_layout.addWidget(stat_widget)

        layout.addWidget(self.stats_group)

        # Daily activity chart
        chart_group = QGroupBox("Daily Activity")
        chart_layout = QVBoxLayout(chart_group)

        # PyQtGraph chart
        pg.setConfigOptions(antialias=True)
        self.chart = pg.PlotWidget()
        self.chart.setBackground('#1e1e1e')
        self.chart.setMinimumHeight(180)
        self.chart.setMaximumHeight(220)
        self.chart.showGrid(x=False, y=True, alpha=0.3)
        self.chart.getAxis('bottom').setStyle(showValues=True)
        self.chart.getAxis('left').setStyle(showValues=True)

        # Style the axes
        axis_pen = pg.mkPen(color='#888888', width=1)
        self.chart.getAxis('bottom').setPen(axis_pen)
        self.chart.getAxis('left').setPen(axis_pen)
        self.chart.getAxis('bottom').setTextPen(axis_pen)
        self.chart.getAxis('left').setTextPen(axis_pen)

        chart_layout.addWidget(self.chart)
        layout.addWidget(chart_group)

        # Model performance table
        model_group = QGroupBox("Model Performance (All Time)")
        model_layout = QVBoxLayout(model_group)

        model_layout.addWidget(QLabel(
            "Chars/sec measures how quickly each model generates output text."
        ))

        self.model_table = QTableWidget()
        self.model_table.setColumnCount(6)
        self.model_table.setHorizontalHeaderLabels([
            "Provider", "Model", "Count", "Avg Inference (s)", "Chars/sec", "Avg Audio (s)"
        ])
        self.model_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.model_table.setAlternatingRowColors(True)
        self.model_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.model_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.model_table.setMaximumHeight(200)
        model_layout.addWidget(self.model_table)

        layout.addWidget(model_group)

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

        # Add stretch at bottom
        layout.addStretch()

    def on_period_button_clicked(self, button):
        """Handle time period button click."""
        self.current_period = button.property("period_key")
        self.refresh()

    def on_metric_button_clicked(self, button):
        """Handle metric button click."""
        self.current_metric = button.property("metric_key")
        self.refresh_chart()

    def get_period_days(self) -> int:
        """Get number of days for current period. -1 means all time."""
        for key, _, days in TIME_PERIODS:
            if key == self.current_period:
                return days
        return 7

    def refresh(self):
        """Refresh all analytics data."""
        db = get_db()
        days = self.get_period_days()

        # Get stats for selected period
        if days == -1:
            # All time
            stats = db.get_all_time_stats()
            self.stats_group.setTitle("Summary (All Time)")
        elif days == 1:
            # Today
            stats = self._get_today_stats(db)
            self.stats_group.setTitle("Summary (Today)")
        else:
            stats = db.get_recent_stats(days=days)
            # Get period display name from TIME_PERIODS
            period_name = next((d for k, d, _ in TIME_PERIODS if k == self.current_period), "")
            self.stats_group.setTitle(f"Summary ({period_name})")

        # Update stat labels
        self.stat_labels["total_words"].setText(format_number(stats.get("total_words", 0)))
        self.stat_labels["transcriptions"].setText(str(stats.get("count", 0)))

        avg_ms = stats.get("avg_inference_ms", 0)
        if avg_ms:
            self.stat_labels["avg_inference"].setText(f"{avg_ms / 1000.0:.1f}s")
        else:
            self.stat_labels["avg_inference"].setText("--")

        # Refresh chart
        self.refresh_chart()

        # Model performance (always all-time)
        performance = db.get_model_performance()
        self.model_table.setRowCount(len(performance))

        for row, perf in enumerate(performance):
            provider_display = get_provider_display_name(perf["provider"])
            model_display = get_model_display_name(perf["model"])
            avg_inference_sec = perf['avg_inference_ms'] / 1000.0

            self.model_table.setItem(row, 0, QTableWidgetItem(provider_display))
            self.model_table.setItem(row, 1, QTableWidgetItem(model_display))
            self.model_table.setItem(row, 2, QTableWidgetItem(str(perf["count"])))
            self.model_table.setItem(row, 3, QTableWidgetItem(f"{avg_inference_sec:.1f}"))
            self.model_table.setItem(row, 4, QTableWidgetItem(f"{perf['avg_chars_per_sec']:.1f}"))
            self.model_table.setItem(row, 5, QTableWidgetItem(f"{perf['avg_audio_duration']:.1f}"))

        # Storage stats
        storage = db.get_storage_stats()
        self.storage_info.setText(
            f"Total records: {storage['total_records']:,}\n"
            f"Records with audio: {storage['records_with_audio']:,}\n"
            f"Database size: {format_size(storage['db_size_bytes'])}\n"
            f"Audio archive size: {format_size(storage['audio_size_bytes'])}\n"
            f"Total storage: {format_size(storage['total_size_bytes'])}"
        )

    def _get_today_stats(self, db) -> dict:
        """Get stats for today only."""
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()

        # Use existing method with 1 day lookback, but filter more precisely
        results = list(db._get_db().transcriptions.find({'timestamp': {'$gte': today_start}}))

        if results:
            count = len(results)
            total_words = sum((r.get('word_count') or 0) for r in results)
            total_chars = sum((r.get('text_length') or 0) for r in results)
            inference_times = [(r.get('inference_time_ms') or 0) for r in results if r.get('inference_time_ms')]
            avg_inference_ms = sum(inference_times) / len(inference_times) if inference_times else 0

            return {
                "count": count,
                "total_words": total_words,
                "total_chars": total_chars,
                "avg_inference_ms": round(avg_inference_ms, 1),
            }

        return {"count": 0, "total_words": 0, "total_chars": 0, "avg_inference_ms": 0}

    def refresh_chart(self):
        """Refresh the daily activity chart."""
        db = get_db()
        days = self.get_period_days()

        # Get daily breakdown data
        if days == -1:
            # All time - get up to 365 days
            daily_data = self._get_daily_breakdown(db, 365)
        elif days == 1:
            # Today - show hourly instead
            self._refresh_hourly_chart(db)
            return
        else:
            daily_data = self._get_daily_breakdown(db, days)

        if not daily_data:
            self.chart.clear()
            return

        # Prepare data for chart
        dates = list(daily_data.keys())
        dates.sort()

        if self.current_metric == "transcripts":
            values = [daily_data[d]["count"] for d in dates]
            ylabel = "Transcripts"
        elif self.current_metric == "characters":
            values = [daily_data[d]["chars"] for d in dates]
            ylabel = "Characters"
        else:  # words
            values = [daily_data[d]["words"] for d in dates]
            ylabel = "Words"

        # Create x-axis positions
        x = list(range(len(dates)))

        # Clear and plot
        self.chart.clear()

        # Create bar chart
        bar_width = 0.6
        bar_item = pg.BarGraphItem(
            x=x,
            height=values,
            width=bar_width,
            brush='#4a9eff',
            pen=pg.mkPen(color='#3a8eef', width=1)
        )
        self.chart.addItem(bar_item)

        # Set x-axis labels (show subset to avoid crowding)
        ax = self.chart.getAxis('bottom')
        if len(dates) <= 14:
            # Show all labels
            ticks = [(i, dates[i][-5:]) for i in range(len(dates))]  # MM-DD format
        else:
            # Show every Nth label
            step = max(1, len(dates) // 10)
            ticks = [(i, dates[i][-5:]) for i in range(0, len(dates), step)]
        ax.setTicks([ticks])

        # Set y-axis label
        self.chart.setLabel('left', ylabel)

    def _refresh_hourly_chart(self, db):
        """Show hourly breakdown for today."""
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        results = list(db._get_db().transcriptions.find({
            'timestamp': {'$gte': today_start.isoformat()}
        }))

        # Group by hour
        hourly = defaultdict(lambda: {"count": 0, "chars": 0, "words": 0})
        for r in results:
            try:
                ts = datetime.fromisoformat(r['timestamp'])
                hour = ts.hour
                hourly[hour]["count"] += 1
                hourly[hour]["chars"] += r.get('text_length') or 0
                hourly[hour]["words"] += r.get('word_count') or 0
            except (ValueError, KeyError):
                continue

        # Create full 24-hour data
        current_hour = datetime.now().hour
        hours = list(range(current_hour + 1))

        if self.current_metric == "transcripts":
            values = [hourly[h]["count"] for h in hours]
            ylabel = "Transcripts"
        elif self.current_metric == "characters":
            values = [hourly[h]["chars"] for h in hours]
            ylabel = "Characters"
        else:
            values = [hourly[h]["words"] for h in hours]
            ylabel = "Words"

        # Clear and plot
        self.chart.clear()

        bar_item = pg.BarGraphItem(
            x=hours,
            height=values,
            width=0.6,
            brush='#4a9eff',
            pen=pg.mkPen(color='#3a8eef', width=1)
        )
        self.chart.addItem(bar_item)

        # Set x-axis labels
        ax = self.chart.getAxis('bottom')
        ticks = [(h, f"{h:02d}:00") for h in range(0, current_hour + 1, max(1, (current_hour + 1) // 8))]
        ax.setTicks([ticks])

        self.chart.setLabel('left', ylabel)

    def _get_daily_breakdown(self, db, days: int) -> dict:
        """Get daily breakdown of transcription stats."""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        results = list(db._get_db().transcriptions.find({'timestamp': {'$gte': cutoff}}))

        daily = defaultdict(lambda: {"count": 0, "chars": 0, "words": 0})

        for r in results:
            try:
                date_str = r['timestamp'][:10]  # YYYY-MM-DD
                daily[date_str]["count"] += 1
                daily[date_str]["chars"] += r.get('text_length') or 0
                daily[date_str]["words"] += r.get('word_count') or 0
            except (KeyError, TypeError):
                continue

        return dict(daily)

    def export_stats(self):
        """Export anonymized statistics to JSON."""
        db = get_db()

        # Gather anonymized stats
        all_time = db.get_all_time_stats()
        model_perf = db.get_model_performance()
        storage = db.get_storage_stats()

        # Get daily breakdown for last 30 days
        daily_30 = self._get_daily_breakdown(db, 30)

        # Build export data (no personal info, no transcript text)
        export_data = {
            "export_date": datetime.now().isoformat(),
            "export_version": "1.0",
            "summary": {
                "total_transcriptions": all_time.get("count", 0),
                "total_words": all_time.get("total_words", 0),
                "total_characters": all_time.get("total_chars", 0),
            },
            "model_performance": [
                {
                    "provider": p["provider"],
                    "model": p["model"],
                    "count": p["count"],
                    "avg_inference_ms": p["avg_inference_ms"],
                    "avg_chars_per_sec": p["avg_chars_per_sec"],
                    "avg_audio_duration_sec": p["avg_audio_duration"],
                }
                for p in model_perf
            ],
            "daily_activity_last_30_days": [
                {
                    "date": date,
                    "transcriptions": stats["count"],
                    "characters": stats["chars"],
                    "words": stats["words"],
                }
                for date, stats in sorted(daily_30.items())
            ],
            "storage": {
                "total_records": storage["total_records"],
                "records_with_audio": storage["records_with_audio"],
                "db_size_bytes": storage["db_size_bytes"],
                "audio_archive_size_bytes": storage["audio_size_bytes"],
            },
        }

        # Ask user where to save
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Export Statistics",
            f"voice-notepad-stats-{datetime.now().strftime('%Y%m%d')}.json",
            "JSON Files (*.json)"
        )

        if filepath:
            with open(filepath, 'w') as f:
                json.dump(export_data, f, indent=2)

            QMessageBox.information(
                self,
                "Export Complete",
                f"Statistics exported to:\n{filepath}"
            )

    def clear_all_data(self):
        """Clear all transcription data after confirmation."""
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
