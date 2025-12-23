"""Favorites Bar Widget

A dynamic button bar for quick access to favorite prompt configurations.
Uses a two-column layout with categories distributed for better space utilization.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QButtonGroup, QLabel, QFrame,
    QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from pathlib import Path
from typing import Optional, List, Callable
from collections import OrderedDict

try:
    from .prompt_library import PromptLibrary, PromptConfig, PromptConfigCategory, PROMPT_CONFIG_CATEGORY_NAMES
except ImportError:
    from prompt_library import PromptLibrary, PromptConfig, PromptConfigCategory, PROMPT_CONFIG_CATEGORY_NAMES


# Define the order in which category rows should appear
# Split into left and right columns for two-column layout
LEFT_COLUMN_CATEGORIES = [
    PromptConfigCategory.FOUNDATIONAL,
    PromptConfigCategory.STYLISTIC,
    PromptConfigCategory.PROMPTS,
    PromptConfigCategory.TODO_LISTS,
    PromptConfigCategory.CUSTOM,
]

RIGHT_COLUMN_CATEGORIES = [
    PromptConfigCategory.BLOG,
    PromptConfigCategory.DOCUMENTATION,
    PromptConfigCategory.WORK,
    PromptConfigCategory.CREATIVE,
]

# Full order for backwards compatibility
CATEGORY_ROW_ORDER = LEFT_COLUMN_CATEGORIES + RIGHT_COLUMN_CATEGORIES


class FavoritesBar(QWidget):
    """Dynamic button bar for favorite prompt configurations.

    Features:
    - Two-column layout for efficient space usage
    - Displays favorites grouped by category
    - Category labels at the start of each row
    - Supports up to 30 buttons total
    - Mutual exclusivity (only one selected at a time)
    - Automatic refresh when favorites change
    """

    # Emitted when a prompt is selected (prompt_id)
    prompt_selected = pyqtSignal(str)

    # Emitted when "Manage" button is clicked
    manage_clicked = pyqtSignal()

    # Maximum buttons per category row (reduced for two-column layout)
    BUTTONS_PER_ROW = 4

    # Maximum total favorites (increased for more quick access options)
    MAX_FAVORITES = 30

    def __init__(self, config_dir: Path, parent=None):
        super().__init__(parent)
        self.config_dir = config_dir
        self.library = PromptLibrary(config_dir)

        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)
        self.buttons: dict[str, QPushButton] = {}  # prompt_id -> button

        self._current_prompt_id: Optional[str] = None

        self._setup_ui()
        self.refresh()

    def _setup_ui(self):
        """Set up the UI layout."""
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(6)

        # Two-column container for category rows
        self.columns_container = QWidget()
        self.columns_layout = QHBoxLayout(self.columns_container)
        self.columns_layout.setContentsMargins(0, 0, 0, 0)
        self.columns_layout.setSpacing(16)  # Gap between columns

        # Left column
        self.left_column = QWidget()
        self.left_layout = QVBoxLayout(self.left_column)
        self.left_layout.setContentsMargins(0, 0, 0, 0)
        self.left_layout.setSpacing(4)
        self.left_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Right column
        self.right_column = QWidget()
        self.right_layout = QVBoxLayout(self.right_column)
        self.right_layout.setContentsMargins(0, 0, 0, 0)
        self.right_layout.setSpacing(4)
        self.right_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.columns_layout.addWidget(self.left_column, 1)
        self.columns_layout.addWidget(self.right_column, 1)

        self.main_layout.addWidget(self.columns_container)

        # Bottom row with Manage button
        bottom_row = QHBoxLayout()
        bottom_row.setContentsMargins(0, 4, 0, 0)

        self.manage_btn = QPushButton("Manage Prompts...")
        self.manage_btn.setFixedHeight(26)
        self.manage_btn.setStyleSheet("""
            QPushButton {
                background-color: #f8f9fa;
                color: #495057;
                border: 1px solid #ced4da;
                border-radius: 4px;
                font-size: 11px;
                padding: 4px 12px;
            }
            QPushButton:hover {
                background-color: #e9ecef;
                border-color: #adb5bd;
            }
        """)
        self.manage_btn.clicked.connect(self.manage_clicked.emit)
        bottom_row.addWidget(self.manage_btn)

        bottom_row.addStretch()
        self.main_layout.addLayout(bottom_row)

    def _clear_column(self, layout: QVBoxLayout):
        """Clear all items from a column layout."""
        while layout.count():
            item = layout.takeAt(0)
            if item.layout():
                while item.layout().count():
                    child = item.layout().takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()
                item.layout().deleteLater()
            elif item.widget():
                item.widget().deleteLater()

    def refresh(self):
        """Refresh the button bar from the library, grouped by category."""
        # Clear existing buttons
        for btn in self.buttons.values():
            self.button_group.removeButton(btn)
            btn.deleteLater()
        self.buttons.clear()

        # Clear existing layouts
        self._clear_column(self.left_layout)
        self._clear_column(self.right_layout)

        # Get favorites
        favorites = self.library.get_favorites()[:self.MAX_FAVORITES]

        if not favorites:
            # Show placeholder in left column
            placeholder = QLabel("No favorites. Click 'Manage Prompts' to add some.")
            placeholder.setStyleSheet("color: #6c757d; font-style: italic;")
            self.left_layout.addWidget(placeholder)
            return

        # Group favorites by category
        by_category: dict[str, List[PromptConfig]] = OrderedDict()
        for cat in CATEGORY_ROW_ORDER:
            by_category[cat.value] = []

        for prompt in favorites:
            category = prompt.category
            if category in by_category:
                by_category[category].append(prompt)
            else:
                # Unknown category - add to custom
                by_category[PromptConfigCategory.CUSTOM.value].append(prompt)

        # Helper to create a category row
        def create_category_row(category_value: str, prompts: List[PromptConfig]) -> QHBoxLayout:
            row = QHBoxLayout()
            row.setSpacing(6)

            # Category label (compact)
            category_name = PROMPT_CONFIG_CATEGORY_NAMES.get(
                PromptConfigCategory(category_value),
                category_value.replace("_", " ").title()
            )
            label = QLabel(f"{category_name}:")
            label.setStyleSheet("font-weight: bold; color: #495057; font-size: 10px;")
            label.setFixedWidth(70)
            label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            row.addWidget(label)

            # Sort and add buttons
            prompts.sort(key=lambda p: p.favorite_order)
            for prompt in prompts[:self.BUTTONS_PER_ROW]:
                btn = self._create_button(prompt)
                self.buttons[prompt.id] = btn
                self.button_group.addButton(btn)
                row.addWidget(btn)

            row.addStretch()
            return row

        # Build left column
        for cat in LEFT_COLUMN_CATEGORIES:
            prompts = by_category.get(cat.value, [])
            if prompts:
                row = create_category_row(cat.value, prompts)
                self.left_layout.addLayout(row)

        self.left_layout.addStretch()

        # Build right column
        for cat in RIGHT_COLUMN_CATEGORIES:
            prompts = by_category.get(cat.value, [])
            if prompts:
                row = create_category_row(cat.value, prompts)
                self.right_layout.addLayout(row)

        self.right_layout.addStretch()

        # Restore selection
        if self._current_prompt_id and self._current_prompt_id in self.buttons:
            self.buttons[self._current_prompt_id].setChecked(True)
        elif favorites:
            # Default to first favorite
            self._current_prompt_id = favorites[0].id
            self.buttons[self._current_prompt_id].setChecked(True)

    def _create_button(self, prompt: PromptConfig) -> QPushButton:
        """Create a format button for a prompt."""
        btn = QPushButton(prompt.name)
        btn.setCheckable(True)
        btn.setMinimumHeight(28)
        btn.setToolTip(prompt.description)

        # Connect click
        btn.clicked.connect(lambda checked, pid=prompt.id: self._on_button_clicked(pid))

        # Compact style for two-column layout
        btn.setStyleSheet("""
            QPushButton {
                background-color: #cfe2ff;
                color: #000000;
                border: 2px solid #9ec5fe;
                border-radius: 5px;
                font-weight: bold;
                font-size: 11px;
                padding: 3px 8px;
                min-width: 60px;
            }
            QPushButton:hover {
                background-color: #b6d4fe;
                border-color: #86b7fe;
            }
            QPushButton:checked {
                background-color: #28a745;
                color: white;
                border-color: #28a745;
            }
            QPushButton:checked:hover {
                background-color: #218838;
                border-color: #1e7e34;
            }
        """)

        return btn

    def _on_button_clicked(self, prompt_id: str):
        """Handle button click."""
        self._current_prompt_id = prompt_id
        self.prompt_selected.emit(prompt_id)

    def get_selected_prompt_id(self) -> Optional[str]:
        """Get the currently selected prompt ID."""
        return self._current_prompt_id

    def set_selected_prompt_id(self, prompt_id: str):
        """Set the selected prompt by ID."""
        self._current_prompt_id = prompt_id
        if prompt_id in self.buttons:
            self.buttons[prompt_id].setChecked(True)

    def get_selected_prompt(self) -> Optional[PromptConfig]:
        """Get the currently selected prompt config."""
        if self._current_prompt_id:
            return self.library.get(self._current_prompt_id)
        return None

    def update_library(self):
        """Reload the library and refresh display."""
        self.library = PromptLibrary(self.config_dir)
        self.refresh()
