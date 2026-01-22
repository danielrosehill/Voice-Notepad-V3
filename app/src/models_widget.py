"""Models tab widget showing available AI models by provider."""

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QScrollArea,
    QFrame,
    QHBoxLayout,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from .config import OPENROUTER_MODELS


# Model metadata with additional notes
# Note: Gemini 2.5 models removed as deprecated by Google
MODEL_INFO = {
    "google/gemini-3-flash-preview": {
        "note": "⭐ Gemini 3 Flash - fast, capable, recommended default",
        "audio_support": True,
        "tier": "standard",
        "recommended": True,
    },
    "google/gemini-3-pro-preview": {
        "note": "Gemini 3 Pro - most capable model for complex tasks",
        "audio_support": True,
        "tier": "premium",
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
            "Voice Notepad uses Gemini models via <b>OpenRouter</b> for audio transcription. "
            "The default model is <b>Gemini 3 Flash</b> which offers excellent speed and quality."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #666; font-size: 11px;")
        container_layout.addWidget(intro)

        # Rationale box
        rationale = QLabel(
            "<b>Why Gemini via OpenRouter?</b><br>"
            "After extensive testing (~2000 transcriptions), the Gemini Flash models have proven highly "
            "cost-effective for voice transcription workloads—typically just a few dollars for "
            "heavy usage. OpenRouter provides a unified API with competitive latency and "
            "access to the latest Gemini models including the Gemini 3 preview."
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

        # Models list (OpenRouter only)
        models_widget = self._create_models_list(
            OPENROUTER_MODELS,
            "https://openrouter.ai/models?fmt=cards&input_modalities=audio",
            "Access to Gemini models via OpenRouter's OpenAI-compatible API. "
            "All models support audio input for transcription."
        )
        container_layout.addWidget(models_widget)

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

    def _create_models_list(
        self,
        models: list,
        docs_url: str,
        description: str
    ) -> QWidget:
        """Create a list of models."""
        container = QWidget()
        container.setStyleSheet("background: white;")

        # Scroll area for models
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: white; border: 1px solid #ddd; border-radius: 4px;")

        content = QWidget()
        content.setStyleSheet("background: white;")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Description
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

        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.addWidget(scroll)

        return container

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
