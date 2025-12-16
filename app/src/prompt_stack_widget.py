"""
Prompt Stack Widget

A UI widget for selecting multiple prompt elements and managing prompt stacks.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QPushButton,
    QGroupBox, QScrollArea, QLineEdit, QComboBox, QDialog, QDialogButtonBox,
    QTextEdit, QMessageBox
)
from PyQt6.QtCore import pyqtSignal, Qt
from pathlib import Path
from typing import List, Set

from .prompt_elements import (
    FORMAT_ELEMENTS, STYLE_ELEMENTS, GRAMMAR_ELEMENTS, PromptStack,
    get_all_stacks, save_custom_stack, build_prompt_from_elements
)


class PromptStackWidget(QWidget):
    """Widget for selecting prompt elements and managing stacks."""

    # Signal emitted when selected elements change
    elements_changed = pyqtSignal(list)  # List[str] of element keys

    def __init__(self, config_dir: Path, parent=None):
        super().__init__(parent)
        self.config_dir = config_dir
        self.element_checkboxes = {}  # key -> QCheckBox
        self.selected_elements: Set[str] = set()
        self._init_ui()

    def _init_ui(self):
        """Initialize the UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Stack selector at top
        stack_layout = QHBoxLayout()
        stack_layout.addWidget(QLabel("<b>Prompt Stack:</b>"))

        self.stack_combo = QComboBox()
        self.stack_combo.setMinimumWidth(200)
        self._load_stacks_into_combo()
        self.stack_combo.currentIndexChanged.connect(self._on_stack_selected)
        stack_layout.addWidget(self.stack_combo)

        save_stack_btn = QPushButton("Save Stack")
        save_stack_btn.clicked.connect(self._save_current_as_stack)
        stack_layout.addWidget(save_stack_btn)

        stack_layout.addStretch()
        layout.addLayout(stack_layout)

        # Scrollable area for element checkboxes
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(16)

        # Format elements
        format_group = self._create_element_group(
            "Format Elements",
            "Define the output format (email, todo list, etc.)",
            FORMAT_ELEMENTS
        )
        scroll_layout.addWidget(format_group)

        # Style elements
        style_group = self._create_element_group(
            "Style Elements",
            "Define writing style (casual, formal, concise, etc.)",
            STYLE_ELEMENTS
        )
        scroll_layout.addWidget(style_group)

        # Grammar elements
        grammar_group = self._create_element_group(
            "Grammar & Structure",
            "Grammar and structural preferences",
            GRAMMAR_ELEMENTS
        )
        scroll_layout.addWidget(grammar_group)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        # Preview button
        preview_btn = QPushButton("Preview Prompt")
        preview_btn.clicked.connect(self._preview_prompt)
        layout.addWidget(preview_btn)

    def _create_element_group(self, title: str, description: str, elements: dict) -> QGroupBox:
        """Create a group box for a category of elements."""
        group = QGroupBox(title)
        group_layout = QVBoxLayout()

        # Description
        desc_label = QLabel(description)
        desc_label.setStyleSheet("color: #6c757d; font-size: 11px;")
        desc_label.setWordWrap(True)
        group_layout.addWidget(desc_label)

        # Checkboxes for each element
        for key, element in elements.items():
            checkbox = QCheckBox(element.name)
            checkbox.setProperty("element_key", key)
            checkbox.setToolTip(element.description)
            checkbox.stateChanged.connect(self._on_element_toggled)
            self.element_checkboxes[key] = checkbox
            group_layout.addWidget(checkbox)

        group.setLayout(group_layout)
        return group

    def _on_element_toggled(self):
        """Handle element checkbox toggle."""
        # Update selected elements set
        self.selected_elements.clear()
        for key, checkbox in self.element_checkboxes.items():
            if checkbox.isChecked():
                self.selected_elements.add(key)

        # Emit signal
        self.elements_changed.emit(list(self.selected_elements))

        # Reset stack combo to "Custom" if user manually changes selections
        self.stack_combo.blockSignals(True)
        self.stack_combo.setCurrentIndex(0)  # "Custom" is always first
        self.stack_combo.blockSignals(False)

    def _load_stacks_into_combo(self):
        """Load all stacks into the combo box."""
        self.stack_combo.clear()
        self.stack_combo.addItem("Custom", None)  # Default to manual selection

        all_stacks = get_all_stacks(self.config_dir)
        for stack in all_stacks:
            self.stack_combo.addItem(stack.name, stack)

    def _on_stack_selected(self, index: int):
        """Handle stack selection from combo box."""
        stack = self.stack_combo.currentData()
        if stack is None:
            # "Custom" selected - don't change checkboxes
            return

        # Apply the stack
        self.apply_stack(stack)

    def apply_stack(self, stack: PromptStack):
        """Apply a prompt stack (select its elements)."""
        # Block signals while updating checkboxes
        for checkbox in self.element_checkboxes.values():
            checkbox.blockSignals(True)

        # Update checkboxes
        for key, checkbox in self.element_checkboxes.items():
            checkbox.setChecked(key in stack.elements)

        # Re-enable signals
        for checkbox in self.element_checkboxes.values():
            checkbox.blockSignals(False)

        # Update selected elements
        self.selected_elements = set(stack.elements)
        self.elements_changed.emit(list(self.selected_elements))

    def _save_current_as_stack(self):
        """Save the current element selection as a named stack."""
        if not self.selected_elements:
            QMessageBox.warning(self, "No Elements Selected",
                              "Please select at least one element before saving a stack.")
            return

        dialog = SaveStackDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            name, description = dialog.get_values()
            stack = PromptStack(
                name=name,
                elements=list(self.selected_elements),
                description=description
            )
            save_custom_stack(stack, self.config_dir)

            # Reload combo box
            self._load_stacks_into_combo()

            # Select the newly saved stack
            for i in range(self.stack_combo.count()):
                if self.stack_combo.itemText(i) == name:
                    self.stack_combo.setCurrentIndex(i)
                    break

            QMessageBox.information(self, "Stack Saved",
                                   f"Stack '{name}' has been saved successfully.")

    def _preview_prompt(self):
        """Preview the generated prompt from current selection."""
        if not self.selected_elements:
            QMessageBox.warning(self, "No Elements Selected",
                              "Please select at least one element to preview.")
            return

        prompt = build_prompt_from_elements(list(self.selected_elements))

        dialog = QDialog(self)
        dialog.setWindowTitle("Prompt Preview")
        dialog.resize(600, 500)

        layout = QVBoxLayout(dialog)

        text_edit = QTextEdit()
        text_edit.setPlainText(prompt)
        text_edit.setReadOnly(True)
        text_edit.setStyleSheet("font-family: monospace; font-size: 11px;")
        layout.addWidget(text_edit)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)

        dialog.exec()

    def get_selected_elements(self) -> List[str]:
        """Get list of selected element keys."""
        return list(self.selected_elements)

    def set_selected_elements(self, element_keys: List[str]):
        """Set which elements are selected."""
        # Block signals
        for checkbox in self.element_checkboxes.values():
            checkbox.blockSignals(True)

        # Update checkboxes
        for key, checkbox in self.element_checkboxes.items():
            checkbox.setChecked(key in element_keys)

        # Re-enable signals
        for checkbox in self.element_checkboxes.values():
            checkbox.blockSignals(False)

        # Update selected elements
        self.selected_elements = set(element_keys)
        self.elements_changed.emit(list(self.selected_elements))


class SaveStackDialog(QDialog):
    """Dialog for saving a new prompt stack."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Save Prompt Stack")
        self.resize(400, 200)
        self._init_ui()

    def _init_ui(self):
        """Initialize the dialog UI."""
        layout = QVBoxLayout(self)

        # Stack name
        layout.addWidget(QLabel("Stack Name:"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g., Quick Email, Dev Notes")
        layout.addWidget(self.name_input)

        # Description
        layout.addWidget(QLabel("Description (optional):"))
        self.desc_input = QLineEdit()
        self.desc_input.setPlaceholderText("Brief description of this stack")
        layout.addWidget(self.desc_input)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def accept(self):
        """Validate and accept the dialog."""
        if not self.name_input.text().strip():
            QMessageBox.warning(self, "Name Required", "Please enter a name for this stack.")
            return
        super().accept()

    def get_values(self):
        """Get the entered name and description."""
        return self.name_input.text().strip(), self.desc_input.text().strip()
