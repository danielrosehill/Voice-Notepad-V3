"""Models tab widget showing available AI models by provider."""

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QScrollArea,
    QFrame,
    QHBoxLayout,
    QTabWidget,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QIcon
from pathlib import Path

from .config import GEMINI_MODELS, OPENROUTER_MODELS


# Model metadata with additional notes
MODEL_INFO = {
    # Gemini Direct models
    "gemini-flash-latest": {
        "note": "⭐ Dynamic endpoint - always points to the latest Flash model (auto-updates)",
        "audio_support": True,
        "tier": "standard",
        "recommended": True,
    },
    "gemini-2.5-flash": {
        "note": "Current stable Flash model with excellent capabilities",
        "audio_support": True,
        "tier": "standard",
    },
    "gemini-2.5-flash-lite": {
        "note": "Lighter version optimized for cost efficiency",
        "audio_support": True,
        "tier": "budget",
    },
    "gemini-2.5-pro": {
        "note": "Most capable Gemini model for complex tasks",
        "audio_support": True,
        "tier": "premium",
    },
    "gemini-3-flash-preview": {
        "note": "Preview of next-generation Flash model",
        "audio_support": True,
        "tier": "standard",
    },
    # OpenRouter models (Gemini via OpenRouter)
    "google/gemini-2.5-flash": {
        "note": "Gemini 2.5 Flash via OpenRouter",
        "audio_support": True,
        "tier": "standard",
        "recommended": True,
    },
    "google/gemini-2.5-flash-lite": {
        "note": "Budget-friendly Gemini 2.5 Flash Lite",
        "audio_support": True,
        "tier": "budget",
    },
    "google/gemini-2.0-flash-001": {
        "note": "Gemini 2.0 Flash via OpenRouter",
        "audio_support": True,
        "tier": "standard",
    },
    "google/gemini-2.0-flash-lite-001": {
        "note": "Budget-friendly Gemini 2.0 Flash Lite",
        "audio_support": True,
        "tier": "budget",
    },
    "google/gemini-3-flash-preview": {
        "note": "Preview of Gemini 3 Flash via OpenRouter",
        "audio_support": True,
        "tier": "standard",
    },
}


class ModelsWidget(QWidget):
    """Widget showing available models grouped by provider in tabs."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        # White background container
        container = QFrame()
        container.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 8px;
            }
        """)
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(16, 16, 16, 16)
        container_layout.setSpacing(12)

        # Header
        title = QLabel("Available Models")
        title.setFont(QFont("Sans", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #333;")
        container_layout.addWidget(title)

        intro = QLabel(
            "Voice Notepad uses Gemini models exclusively for audio transcription. "
            "The recommended setup is <b>Gemini Direct</b> with the <b>gemini-flash-latest</b> endpoint."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #666; font-size: 11px;")
        container_layout.addWidget(intro)

        # Rationale box
        rationale = QLabel(
            "<b>Why Gemini Flash Latest?</b><br>"
            "After extensive testing (~1000 transcriptions), the Flash models have proven highly "
            "cost-effective for voice transcription workloads—typically just a few dollars for "
            "heavy usage. The dynamic 'gemini-flash-latest' endpoint automatically points to "
            "Google's latest Flash model, eliminating the need for manual updates when new "
            "versions are released. This endpoint is only available through the direct Gemini API, "
            "not through OpenRouter."
        )
        rationale.setWordWrap(True)
        rationale.setStyleSheet(
            "background-color: #e7f5ff; border: 1px solid #74c0fc; "
            "border-radius: 4px; padding: 10px; font-size: 11px; color: #1971c2; margin: 8px 0;"
        )
        container_layout.addWidget(rationale)

        # Tier legend (horizontal)
        legend_widget = QWidget()
        legend_layout = QHBoxLayout(legend_widget)
        legend_layout.setContentsMargins(0, 4, 0, 8)
        legend_layout.setSpacing(16)

        legend_label = QLabel("<b>Tiers:</b>")
        legend_label.setStyleSheet("color: #333; font-size: 11px;")
        legend_layout.addWidget(legend_label)

        tiers = [
            ("Budget", "#28a745", "Lower cost"),
            ("Standard", "#007bff", "Balanced"),
            ("Premium", "#6f42c1", "Highest capability"),
        ]

        for tier_name, color, description in tiers:
            tier_label = QLabel(
                f"<span style='color: {color};'>●</span> "
                f"<span style='color: #333;'>{tier_name}</span> "
                f"<span style='color: #888;'>({description})</span>"
            )
            tier_label.setStyleSheet("font-size: 11px;")
            legend_layout.addWidget(tier_label)

        legend_layout.addStretch()
        container_layout.addWidget(legend_widget)

        # Tabbed interface for providers
        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #ddd;
                border-radius: 4px;
                background: white;
            }
            QTabBar::tab {
                background: #f5f5f5;
                border: 1px solid #ddd;
                border-bottom: none;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background: white;
                border-bottom: 1px solid white;
                margin-bottom: -1px;
            }
            QTabBar::tab:hover:!selected {
                background: #e8e8e8;
            }
        """)

        # Icons directory
        icons_dir = Path(__file__).parent / "icons"

        # Add provider tabs with icons
        # Gemini Direct (recommended - first tab)
        gemini_tab_idx = tabs.addTab(
            self._create_provider_tab(
                GEMINI_MODELS,
                "https://ai.google.dev/gemini-api/docs/models",
                "⭐ <b>Recommended:</b> Direct access to Google's Gemini models. "
                "The 'gemini-flash-latest' endpoint automatically updates to the latest Flash model, "
                "eliminating manual version management. Best for users who want the latest model "
                "without configuration changes."
            ),
            "Gemini Direct ⭐"
        )
        gemini_icon_path = icons_dir / "gemini_icon.png"
        if gemini_icon_path.exists():
            tabs.setTabIcon(gemini_tab_idx, QIcon(str(gemini_icon_path)))

        # OpenRouter (alternative)
        or_tab_idx = tabs.addTab(
            self._create_provider_tab(
                OPENROUTER_MODELS,
                "https://openrouter.ai/models?fmt=cards&input_modalities=audio",
                "Alternative access to Gemini models via OpenRouter's OpenAI-compatible API. "
                "Useful if you already have an OpenRouter account. Note: The dynamic "
                "'gemini-flash-latest' endpoint is not available through OpenRouter."
            ),
            "OpenRouter"
        )
        or_icon_path = icons_dir / "or_icon.png"
        if or_icon_path.exists():
            tabs.setTabIcon(or_tab_idx, QIcon(str(or_icon_path)))

        container_layout.addWidget(tabs)

        # Info note about local storage
        note = QLabel(
            "<b>Note:</b> This model list is stored locally and may be periodically updated. "
            "Models can be manually updated in the application configuration if new models "
            "become available from providers."
        )
        note.setWordWrap(True)
        note.setStyleSheet(
            "background-color: #e7f3ff; border: 1px solid #b6d4fe; "
            "border-radius: 4px; padding: 8px; font-size: 11px; color: #084298;"
        )
        container_layout.addWidget(note)

        main_layout.addWidget(container)

    def _create_provider_tab(
        self,
        models: list,
        docs_url: str,
        description: str
    ) -> QWidget:
        """Create a tab for a provider's models."""
        tab = QWidget()
        tab.setStyleSheet("background: white;")

        # Scroll area for models
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: white; border: none;")

        content = QWidget()
        content.setStyleSheet("background: white;")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Provider description
        desc_label = QLabel(description)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #666; font-size: 11px; padding-bottom: 4px;")
        layout.addWidget(desc_label)

        # Docs link
        docs_link = QLabel(f'<a href="{docs_url}" style="color: #0066cc;">View Documentation →</a>')
        docs_link.setOpenExternalLinks(True)
        docs_link.setStyleSheet("font-size: 11px; padding-bottom: 12px;")
        layout.addWidget(docs_link)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("background-color: #eee;")
        separator.setFixedHeight(1)
        layout.addWidget(separator)

        # Models list
        for model_id, display_name in models:
            model_widget = self._create_model_entry(model_id, display_name)
            layout.addWidget(model_widget)

        layout.addStretch()

        scroll.setWidget(content)

        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.addWidget(scroll)

        return tab

    def _create_model_entry(self, model_id: str, display_name: str) -> QWidget:
        """Create a widget for a single model entry."""
        info = MODEL_INFO.get(model_id, {})
        is_recommended = info.get("recommended", False)

        # Choose background color based on recommendation status
        if is_recommended:
            bg_color = "#fff3cd"  # Orange/amber background
            hover_color = "#ffe5b4"
        else:
            bg_color = "#fafafa"
            hover_color = "#f0f0f0"

        widget = QWidget()
        widget.setStyleSheet(f"""
            QWidget {{
                background: {bg_color};
                border-radius: 6px;
                padding: 4px;
            }}
            QWidget:hover {{
                background: {hover_color};
            }}
        """)

        # Horizontal layout for two-column display
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(16)

        # Left column: Tier indicator + Model name + Recommended badge
        left_layout = QHBoxLayout()
        left_layout.setSpacing(8)

        # Tier indicator
        tier = info.get("tier", "standard")
        tier_colors = {
            "budget": "#28a745",
            "standard": "#007bff",
            "premium": "#6f42c1",
        }
        color = tier_colors.get(tier, "#007bff")

        tier_dot = QLabel("●")
        tier_dot.setStyleSheet(f"color: {color}; font-size: 14px; background: transparent;")
        tier_dot.setFixedWidth(20)
        left_layout.addWidget(tier_dot)

        # Model name (larger font)
        name_label = QLabel(f"<b style='color: #333;'>{display_name}</b>")
        name_label.setStyleSheet("background: transparent; font-size: 13px;")
        name_label.setFixedWidth(300)  # Fixed width for alignment
        left_layout.addWidget(name_label)

        # Recommended badge (if applicable)
        if is_recommended:
            rec_badge = QLabel("Recommended")
            rec_badge.setStyleSheet("""
                background: #ff8800;
                color: white;
                font-size: 10px;
                font-weight: bold;
                padding: 3px 8px;
                border-radius: 4px;
            """)
            rec_badge.setFixedHeight(20)
            left_layout.addWidget(rec_badge)

        layout.addLayout(left_layout)

        # Right column: Description
        note = info.get("note", "")
        note_label = QLabel(note if note else "—")
        note_label.setStyleSheet("color: #666; font-size: 12px; background: transparent;")
        note_label.setWordWrap(True)
        layout.addWidget(note_label, 1)  # Stretch factor of 1 to fill remaining space

        return widget
