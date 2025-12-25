"""
Unified Prompt Editor Window

A single window for all prompt configuration using a tabbed interface:
1. Prompts - browse and edit all prompts (builtin + custom)
2. Foundation - view base system prompt
3. Stacks - create element-based stacks
4. Style - formality, verbosity, optional checkboxes
"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTextEdit, QPushButton, QScrollArea, QFrame, QCheckBox,
    QGroupBox, QRadioButton, QButtonGroup, QComboBox,
    QGridLayout, QSizePolicy, QMessageBox, QLineEdit,
    QDialog, QDialogButtonBox, QToolButton, QTabWidget,
    QListWidget, QListWidgetItem, QSplitter
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from pathlib import Path
from typing import List, Set, Optional

from .config import (
    Config, save_config,
    FOUNDATION_PROMPT_SECTIONS,
    FORMAT_TEMPLATES, FORMAT_DISPLAY_NAMES, FORMAT_CATEGORIES,
    OPTIONAL_PROMPT_COMPONENTS,
    FORMALITY_DISPLAY_NAMES, VERBOSITY_DISPLAY_NAMES,
    TONE_DISPLAY_NAMES, STYLE_DISPLAY_NAMES
)
from .prompt_elements import (
    FORMAT_ELEMENTS, STYLE_ELEMENTS, GRAMMAR_ELEMENTS,
    PromptStack, get_all_stacks, save_custom_stack, delete_stack,
    build_prompt_from_elements
)
from .prompt_library import (
    PromptLibrary, PromptConfig, PromptConfigCategory,
    PROMPT_CONFIG_CATEGORY_NAMES
)


class PromptEditDialog(QDialog):
    """Dialog for editing a prompt configuration."""

    def __init__(self, prompt: Optional[PromptConfig] = None, parent=None):
        super().__init__(parent)
        self.prompt = prompt
        self.is_new = prompt is None

        self.setWindowTitle("New Prompt" if self.is_new else f"Edit: {prompt.name}")
        self.setMinimumSize(500, 500)
        self.resize(550, 600)

        self._init_ui()
        if prompt:
            self._load_prompt()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Name
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Name:"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g., Quick Email, Dev Notes")
        name_layout.addWidget(self.name_edit)
        layout.addLayout(name_layout)

        # Category
        cat_layout = QHBoxLayout()
        cat_layout.addWidget(QLabel("Category:"))
        self.category_combo = QComboBox()
        for cat in PromptConfigCategory:
            if cat.value not in ("stylistic", "todo_lists", "blog"):  # Skip legacy
                self.category_combo.addItem(
                    PROMPT_CONFIG_CATEGORY_NAMES.get(cat, cat.value),
                    cat.value
                )
        cat_layout.addWidget(self.category_combo)
        cat_layout.addStretch()
        layout.addLayout(cat_layout)

        # Description
        layout.addWidget(QLabel("Description:"))
        self.desc_edit = QLineEdit()
        self.desc_edit.setPlaceholderText("Brief description of what this prompt does")
        layout.addWidget(self.desc_edit)

        # Instruction
        layout.addWidget(QLabel("Format Instruction:"))
        self.instruction_edit = QTextEdit()
        self.instruction_edit.setPlaceholderText(
            "Describe how the output should be formatted.\n"
            "e.g., 'Format as a professional email with greeting and sign-off.'"
        )
        self.instruction_edit.setMaximumHeight(100)
        layout.addWidget(self.instruction_edit)

        # Adherence
        layout.addWidget(QLabel("Adherence Guidelines (optional):"))
        self.adherence_edit = QTextEdit()
        self.adherence_edit.setPlaceholderText(
            "Additional guidelines for how strictly to follow the format.\n"
            "e.g., 'Use proper email etiquette. Include a subject line suggestion.'"
        )
        self.adherence_edit.setMaximumHeight(100)
        layout.addWidget(self.adherence_edit)

        # Formality override
        formality_layout = QHBoxLayout()
        formality_layout.addWidget(QLabel("Formality Override:"))
        self.formality_combo = QComboBox()
        self.formality_combo.addItem("Use Global Setting", "")
        for key, display in TONE_DISPLAY_NAMES.items():
            self.formality_combo.addItem(display, key)
        formality_layout.addWidget(self.formality_combo)
        formality_layout.addStretch()
        layout.addLayout(formality_layout)

        # Verbosity override
        verbosity_layout = QHBoxLayout()
        verbosity_layout.addWidget(QLabel("Verbosity Override:"))
        self.verbosity_combo = QComboBox()
        self.verbosity_combo.addItem("Use Global Setting", "")
        for key, display in VERBOSITY_DISPLAY_NAMES.items():
            self.verbosity_combo.addItem(display, key)
        verbosity_layout.addWidget(self.verbosity_combo)
        verbosity_layout.addStretch()
        layout.addLayout(verbosity_layout)

        layout.addStretch()

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_prompt(self):
        """Load prompt data into fields."""
        self.name_edit.setText(self.prompt.name)
        self.desc_edit.setText(self.prompt.description)
        self.instruction_edit.setPlainText(self.prompt.instruction)
        self.adherence_edit.setPlainText(self.prompt.adherence)

        # Category
        idx = self.category_combo.findData(self.prompt.category)
        if idx >= 0:
            self.category_combo.setCurrentIndex(idx)

        # Formality
        if self.prompt.formality:
            idx = self.formality_combo.findData(self.prompt.formality)
            if idx >= 0:
                self.formality_combo.setCurrentIndex(idx)

        # Verbosity
        if self.prompt.verbosity:
            idx = self.verbosity_combo.findData(self.prompt.verbosity)
            if idx >= 0:
                self.verbosity_combo.setCurrentIndex(idx)

        # Disable name editing for builtin prompts
        if self.prompt.is_builtin:
            self.name_edit.setReadOnly(True)
            self.name_edit.setStyleSheet("background-color: #f0f0f0;")

    def _on_save(self):
        """Validate and accept."""
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Name Required", "Please enter a prompt name.")
            return
        self.accept()

    def get_prompt_data(self) -> dict:
        """Get the edited prompt data."""
        return {
            "name": self.name_edit.text().strip(),
            "category": self.category_combo.currentData(),
            "description": self.desc_edit.text().strip(),
            "instruction": self.instruction_edit.toPlainText().strip(),
            "adherence": self.adherence_edit.toPlainText().strip(),
            "formality": self.formality_combo.currentData() or None,
            "verbosity": self.verbosity_combo.currentData() or None,
        }


class PromptEditorWindow(QMainWindow):
    """Unified window for all prompt configuration."""

    # Signal emitted when prompts change (main window should refresh search)
    prompts_changed = pyqtSignal()

    def __init__(self, config: Config, config_dir: Path, parent=None):
        super().__init__(parent)
        self.config = config
        self.config_dir = config_dir
        self.library = PromptLibrary(config_dir)

        self.setWindowTitle("Prompt Manager")
        self.setMinimumSize(800, 700)
        self.resize(900, 800)

        # Track UI elements
        self.element_checkboxes = {}  # element_key -> QCheckBox
        self.selected_elements: Set[str] = set()

        self._init_ui()

    def _init_ui(self):
        """Initialize the UI with a tabbed interface."""
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # Header
        header = QLabel("Prompt Manager")
        header.setFont(QFont("Sans", 18, QFont.Weight.Bold))
        main_layout.addWidget(header)

        desc = QLabel(
            "Manage your prompts. Create custom prompts, edit existing ones, "
            "or view the foundation settings that are always applied."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #6c757d; margin-bottom: 8px;")
        main_layout.addWidget(desc)

        # Tabbed interface
        self.tabs = QTabWidget()

        # Tab 1: Prompts List
        prompts_tab = QWidget()
        prompts_layout = QVBoxLayout(prompts_tab)
        prompts_layout.setContentsMargins(12, 12, 12, 12)
        self._create_prompts_content(prompts_layout)
        self.tabs.addTab(prompts_tab, "Prompts")

        # Tab 2: Foundation Prompt
        foundation_tab = QWidget()
        foundation_layout = QVBoxLayout(foundation_tab)
        foundation_layout.setContentsMargins(12, 12, 12, 12)
        self._create_foundation_content(foundation_layout)
        foundation_layout.addStretch()
        self.tabs.addTab(foundation_tab, "Foundation")

        # Tab 3: Stack Builder
        stacks_tab = QWidget()
        stacks_layout = QVBoxLayout(stacks_tab)
        stacks_layout.setContentsMargins(12, 12, 12, 12)
        self._create_stack_content(stacks_layout)
        stacks_layout.addStretch()
        self.tabs.addTab(stacks_tab, "Stacks")

        # Tab 4: Tone & Style
        style_tab = QWidget()
        style_layout = QVBoxLayout(style_tab)
        style_layout.setContentsMargins(12, 12, 12, 12)
        self._create_tone_content(style_layout)
        style_layout.addStretch()
        self.tabs.addTab(style_tab, "Style")

        main_layout.addWidget(self.tabs, stretch=1)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.setMinimumHeight(36)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                padding: 8px 24px;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
        """)
        close_btn.clicked.connect(self.close)
        main_layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)

    def _create_prompts_content(self, parent_layout):
        """Create the Prompts list content for the tab."""
        desc = QLabel(
            "Browse and manage all available prompts. "
            "Create custom prompts or modify existing ones."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #6c757d; font-size: 11px; margin-bottom: 8px;")
        parent_layout.addWidget(desc)

        # Filter and actions row
        filter_layout = QHBoxLayout()

        # Category filter
        filter_layout.addWidget(QLabel("Category:"))
        self.category_filter = QComboBox()
        self.category_filter.addItem("All Categories", "all")
        for cat in PromptConfigCategory:
            if cat.value not in ("stylistic", "todo_lists", "blog"):  # Skip legacy
                self.category_filter.addItem(
                    PROMPT_CONFIG_CATEGORY_NAMES.get(cat, cat.value),
                    cat.value
                )
        self.category_filter.currentIndexChanged.connect(self._filter_prompts)
        filter_layout.addWidget(self.category_filter)

        # Search
        filter_layout.addWidget(QLabel("Search:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Type to filter...")
        self.search_edit.setMaximumWidth(200)
        self.search_edit.textChanged.connect(self._filter_prompts)
        filter_layout.addWidget(self.search_edit)

        filter_layout.addStretch()

        # New prompt button
        new_btn = QPushButton("+ New Prompt")
        new_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                padding: 6px 16px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
        """)
        new_btn.clicked.connect(self._create_new_prompt)
        filter_layout.addWidget(new_btn)

        parent_layout.addLayout(filter_layout)

        # Splitter for list and details
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Prompts list
        list_container = QWidget()
        list_layout = QVBoxLayout(list_container)
        list_layout.setContentsMargins(0, 0, 0, 0)

        self.prompts_list = QListWidget()
        self.prompts_list.setMinimumWidth(280)
        self.prompts_list.currentItemChanged.connect(self._on_prompt_selected)
        list_layout.addWidget(self.prompts_list)

        splitter.addWidget(list_container)

        # Details panel
        details_container = QWidget()
        details_layout = QVBoxLayout(details_container)
        details_layout.setContentsMargins(12, 0, 0, 0)

        self.details_title = QLabel("Select a prompt")
        self.details_title.setFont(QFont("Sans", 14, QFont.Weight.Bold))
        details_layout.addWidget(self.details_title)

        self.details_category = QLabel("")
        self.details_category.setStyleSheet("color: #6c757d; font-size: 11px;")
        details_layout.addWidget(self.details_category)

        self.details_desc = QLabel("")
        self.details_desc.setWordWrap(True)
        self.details_desc.setStyleSheet("margin-top: 8px;")
        details_layout.addWidget(self.details_desc)

        # Instruction preview
        details_layout.addWidget(QLabel("Instruction:"))
        self.details_instruction = QTextEdit()
        self.details_instruction.setReadOnly(True)
        self.details_instruction.setMaximumHeight(100)
        self.details_instruction.setStyleSheet("""
            QTextEdit {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                font-size: 11px;
            }
        """)
        details_layout.addWidget(self.details_instruction)

        # Action buttons
        btn_layout = QHBoxLayout()

        self.edit_btn = QPushButton("Edit")
        self.edit_btn.setEnabled(False)
        self.edit_btn.clicked.connect(self._edit_selected_prompt)
        btn_layout.addWidget(self.edit_btn)

        self.duplicate_btn = QPushButton("Duplicate")
        self.duplicate_btn.setEnabled(False)
        self.duplicate_btn.clicked.connect(self._duplicate_selected_prompt)
        btn_layout.addWidget(self.duplicate_btn)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setEnabled(False)
        self.delete_btn.setStyleSheet("color: #dc3545;")
        self.delete_btn.clicked.connect(self._delete_selected_prompt)
        btn_layout.addWidget(self.delete_btn)

        self.reset_btn = QPushButton("Reset to Default")
        self.reset_btn.setEnabled(False)
        self.reset_btn.setVisible(False)
        self.reset_btn.clicked.connect(self._reset_selected_prompt)
        btn_layout.addWidget(self.reset_btn)

        btn_layout.addStretch()
        details_layout.addLayout(btn_layout)

        details_layout.addStretch()
        splitter.addWidget(details_container)

        splitter.setSizes([300, 400])
        parent_layout.addWidget(splitter, stretch=1)

        # Populate list
        self._populate_prompts_list()

    def _populate_prompts_list(self):
        """Populate the prompts list widget."""
        self.prompts_list.clear()

        all_prompts = self.library.get_all()

        # Apply filters
        category_filter = self.category_filter.currentData()
        search_text = self.search_edit.text().lower().strip()

        for prompt in sorted(all_prompts, key=lambda p: p.name.lower()):
            # Category filter
            if category_filter != "all" and prompt.category != category_filter:
                continue

            # Search filter
            if search_text:
                if search_text not in prompt.name.lower() and search_text not in prompt.description.lower():
                    continue

            # Create list item
            item = QListWidgetItem()
            label = prompt.name
            if prompt.is_modified:
                label += " (modified)"
            if not prompt.is_builtin:
                label += " [custom]"
            item.setText(label)
            item.setData(Qt.ItemDataRole.UserRole, prompt.id)
            self.prompts_list.addItem(item)

    def _filter_prompts(self):
        """Filter prompts list based on current filters."""
        self._populate_prompts_list()

    def _on_prompt_selected(self, current, previous):
        """Handle prompt selection in list."""
        if current is None:
            self.details_title.setText("Select a prompt")
            self.details_category.setText("")
            self.details_desc.setText("")
            self.details_instruction.setPlainText("")
            self.edit_btn.setEnabled(False)
            self.duplicate_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
            self.reset_btn.setVisible(False)
            return

        prompt_id = current.data(Qt.ItemDataRole.UserRole)
        prompt = self.library.get(prompt_id)

        if prompt is None:
            return

        self.details_title.setText(prompt.name)

        cat_name = PROMPT_CONFIG_CATEGORY_NAMES.get(
            PromptConfigCategory(prompt.category) if prompt.category in [c.value for c in PromptConfigCategory] else None,
            prompt.category
        )
        builtin_label = "Built-in" if prompt.is_builtin else "Custom"
        self.details_category.setText(f"{cat_name} • {builtin_label}")

        self.details_desc.setText(prompt.description or "No description")

        instruction_text = prompt.instruction or "(No specific instruction)"
        if prompt.adherence:
            instruction_text += f"\n\nAdherence:\n{prompt.adherence}"
        self.details_instruction.setPlainText(instruction_text)

        # Enable buttons
        self.edit_btn.setEnabled(True)
        self.duplicate_btn.setEnabled(True)
        self.delete_btn.setEnabled(not prompt.is_builtin)
        self.reset_btn.setVisible(prompt.is_builtin and prompt.is_modified)
        self.reset_btn.setEnabled(prompt.is_builtin and prompt.is_modified)

    def _create_new_prompt(self):
        """Create a new custom prompt."""
        dialog = PromptEditDialog(parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_prompt_data()

            prompt = PromptConfig(
                id="",  # Will be auto-generated
                name=data["name"],
                category=data["category"],
                description=data["description"],
                instruction=data["instruction"],
                adherence=data["adherence"],
                formality=data["formality"],
                verbosity=data["verbosity"],
                is_builtin=False,
            )

            self.library.create_custom(prompt)
            self._populate_prompts_list()
            self.prompts_changed.emit()

            QMessageBox.information(
                self, "Prompt Created",
                f"Prompt '{data['name']}' has been created."
            )

    def _edit_selected_prompt(self):
        """Edit the selected prompt."""
        current = self.prompts_list.currentItem()
        if current is None:
            return

        prompt_id = current.data(Qt.ItemDataRole.UserRole)
        prompt = self.library.get(prompt_id)
        if prompt is None:
            return

        dialog = PromptEditDialog(prompt, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_prompt_data()

            if prompt.is_builtin:
                # Store modification for builtin
                self.library.modify_builtin(prompt_id, {
                    "description": data["description"],
                    "instruction": data["instruction"],
                    "adherence": data["adherence"],
                    "formality": data["formality"],
                    "verbosity": data["verbosity"],
                })
            else:
                # Update custom prompt
                prompt.name = data["name"]
                prompt.category = data["category"]
                prompt.description = data["description"]
                prompt.instruction = data["instruction"]
                prompt.adherence = data["adherence"]
                prompt.formality = data["formality"]
                prompt.verbosity = data["verbosity"]
                self.library.update_custom(prompt)

            self._populate_prompts_list()
            self.prompts_changed.emit()

    def _duplicate_selected_prompt(self):
        """Duplicate the selected prompt as a new custom prompt."""
        current = self.prompts_list.currentItem()
        if current is None:
            return

        prompt_id = current.data(Qt.ItemDataRole.UserRole)
        prompt = self.library.get(prompt_id)
        if prompt is None:
            return

        new_prompt = prompt.clone(f"{prompt.name} (Copy)")
        self.library.create_custom(new_prompt)
        self._populate_prompts_list()
        self.prompts_changed.emit()

        QMessageBox.information(
            self, "Prompt Duplicated",
            f"Created '{new_prompt.name}' as a copy of '{prompt.name}'."
        )

    def _delete_selected_prompt(self):
        """Delete the selected custom prompt."""
        current = self.prompts_list.currentItem()
        if current is None:
            return

        prompt_id = current.data(Qt.ItemDataRole.UserRole)
        prompt = self.library.get(prompt_id)
        if prompt is None or prompt.is_builtin:
            return

        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete prompt '{prompt.name}'?\n\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.library.delete_custom(prompt_id)
            self._populate_prompts_list()
            self.prompts_changed.emit()

    def _reset_selected_prompt(self):
        """Reset a modified builtin prompt to its default."""
        current = self.prompts_list.currentItem()
        if current is None:
            return

        prompt_id = current.data(Qt.ItemDataRole.UserRole)

        reply = QMessageBox.question(
            self, "Reset to Default",
            "Reset this prompt to its default settings?\n\nYour modifications will be lost.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.library.reset_builtin(prompt_id)
            self._populate_prompts_list()
            self.prompts_changed.emit()

            # Refresh details
            self._on_prompt_selected(self.prompts_list.currentItem(), None)

    def _create_foundation_content(self, parent_layout):
        """Create the Foundation Prompt content for the tab."""
        desc = QLabel(
            "These rules are always applied to every transcription. "
            "They define the core cleanup behavior."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #6c757d; font-size: 11px; margin-bottom: 8px;")
        parent_layout.addWidget(desc)

        # Build foundation prompt text
        foundation_text = self._build_foundation_display()

        self.foundation_text = QTextEdit()
        self.foundation_text.setPlainText(foundation_text)
        self.foundation_text.setReadOnly(True)
        self.foundation_text.setStyleSheet("""
            QTextEdit {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                font-family: monospace;
                font-size: 11px;
                padding: 8px;
            }
        """)
        parent_layout.addWidget(self.foundation_text, 1)  # Give it stretch

        # Edit/Reset buttons (disabled for now - read-only)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        info_label = QLabel("Foundation prompt is read-only")
        info_label.setStyleSheet("color: #6c757d; font-size: 10px; font-style: italic;")
        btn_layout.addWidget(info_label)

        parent_layout.addLayout(btn_layout)

    def _build_foundation_display(self) -> str:
        """Build a formatted display of the foundation prompt."""
        lines = []
        for section_key, section_data in FOUNDATION_PROMPT_SECTIONS.items():
            lines.append(f"## {section_data['heading']}")
            for instruction in section_data['instructions']:
                # Truncate long instructions
                if len(instruction) > 120:
                    instruction = instruction[:117] + "..."
                lines.append(f"* {instruction}")
            lines.append("")
        return "\n".join(lines)

    def _create_stack_content(self, parent_layout):
        """Create the Stack Builder content for the tab."""
        desc = QLabel(
            "Build custom prompt stacks by combining format, style, and grammar elements. "
            "Save stacks for reuse."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #6c757d; font-size: 11px; margin-bottom: 8px;")
        parent_layout.addWidget(desc)

        # Stack selector
        stack_row = QHBoxLayout()
        stack_row.addWidget(QLabel("Load Stack:"))

        self.stack_combo = QComboBox()
        self.stack_combo.setMinimumWidth(180)
        self._load_stacks_into_combo()
        self.stack_combo.currentIndexChanged.connect(self._on_stack_selected)
        stack_row.addWidget(self.stack_combo)

        save_btn = QPushButton("Save Stack")
        save_btn.clicked.connect(self._save_current_stack)
        stack_row.addWidget(save_btn)

        delete_btn = QPushButton("Delete")
        delete_btn.setStyleSheet("color: #dc3545;")
        delete_btn.clicked.connect(self._delete_current_stack)
        stack_row.addWidget(delete_btn)

        stack_row.addStretch()
        parent_layout.addLayout(stack_row)

        # Element checkboxes by category
        elements_container = QWidget()
        elements_layout = QHBoxLayout(elements_container)
        elements_layout.setContentsMargins(0, 8, 0, 0)
        elements_layout.setSpacing(16)

        # Format elements
        format_group = self._create_element_group("Format", FORMAT_ELEMENTS)
        elements_layout.addWidget(format_group)

        # Style elements
        style_group = self._create_element_group("Style", STYLE_ELEMENTS)
        elements_layout.addWidget(style_group)

        # Grammar elements
        grammar_group = self._create_element_group("Grammar", GRAMMAR_ELEMENTS)
        elements_layout.addWidget(grammar_group)

        parent_layout.addWidget(elements_container)

        # Preview button
        preview_btn = QPushButton("Preview Stack Prompt")
        preview_btn.clicked.connect(self._preview_stack)
        parent_layout.addWidget(preview_btn)

    def _create_element_group(self, title: str, elements: dict) -> QGroupBox:
        """Create a group box for element checkboxes."""
        group = QGroupBox(title)
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                margin-top: 8px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
            }
        """)

        layout = QVBoxLayout()
        layout.setSpacing(4)

        for key, element in elements.items():
            checkbox = QCheckBox(element.name)
            checkbox.setProperty("element_key", key)
            checkbox.setToolTip(element.description)
            checkbox.stateChanged.connect(self._on_element_toggled)
            self.element_checkboxes[key] = checkbox
            layout.addWidget(checkbox)

        group.setLayout(layout)
        return group

    def _load_stacks_into_combo(self):
        """Load all stacks into the combo box."""
        self.stack_combo.clear()
        self.stack_combo.addItem("-- Select Stack --", None)

        all_stacks = get_all_stacks(self.config_dir)
        for stack in all_stacks:
            self.stack_combo.addItem(stack.name, stack)

    def _on_stack_selected(self, index: int):
        """Handle stack selection."""
        stack = self.stack_combo.currentData()
        if stack is None:
            return

        # Apply the stack
        for key, checkbox in self.element_checkboxes.items():
            checkbox.blockSignals(True)
            checkbox.setChecked(key in stack.elements)
            checkbox.blockSignals(False)

        self.selected_elements = set(stack.elements)

    def _on_element_toggled(self):
        """Handle element checkbox toggle."""
        self.selected_elements.clear()
        for key, checkbox in self.element_checkboxes.items():
            if checkbox.isChecked():
                self.selected_elements.add(key)

        # Reset combo to "Select Stack"
        self.stack_combo.blockSignals(True)
        self.stack_combo.setCurrentIndex(0)
        self.stack_combo.blockSignals(False)

    def _save_current_stack(self):
        """Save the current element selection as a stack."""
        if not self.selected_elements:
            QMessageBox.warning(
                self, "No Elements",
                "Please select at least one element before saving."
            )
            return

        # Get name from user
        dialog = QDialog(self)
        dialog.setWindowTitle("Save Stack")
        dialog.setMinimumWidth(300)

        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Stack Name:"))

        name_edit = QLineEdit()
        name_edit.setPlaceholderText("e.g., Quick Email, Dev Notes")
        layout.addWidget(name_edit)

        layout.addWidget(QLabel("Description (optional):"))
        desc_edit = QLineEdit()
        layout.addWidget(desc_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            name = name_edit.text().strip()
            if not name:
                QMessageBox.warning(self, "Name Required", "Please enter a stack name.")
                return

            stack = PromptStack(
                name=name,
                elements=list(self.selected_elements),
                description=desc_edit.text().strip()
            )
            save_custom_stack(stack, self.config_dir)
            self._load_stacks_into_combo()

            QMessageBox.information(
                self, "Stack Saved",
                f"Stack '{name}' has been saved."
            )

    def _delete_current_stack(self):
        """Delete the currently selected stack."""
        stack = self.stack_combo.currentData()
        if stack is None:
            QMessageBox.warning(self, "No Stack Selected", "Please select a stack to delete.")
            return

        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete stack '{stack.name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            delete_stack(stack.name, self.config_dir)
            self._load_stacks_into_combo()

    def _preview_stack(self):
        """Preview the generated prompt from current elements."""
        if not self.selected_elements:
            QMessageBox.warning(
                self, "No Elements",
                "Please select elements to preview."
            )
            return

        prompt = build_prompt_from_elements(list(self.selected_elements))

        dialog = QDialog(self)
        dialog.setWindowTitle("Stack Prompt Preview")
        dialog.resize(600, 400)

        layout = QVBoxLayout(dialog)

        text = QTextEdit()
        text.setPlainText(prompt)
        text.setReadOnly(True)
        text.setStyleSheet("font-family: monospace; font-size: 11px;")
        layout.addWidget(text)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)

        dialog.exec()

    def _create_tone_content(self, parent_layout):
        """Create the Tone & Style content for the tab."""
        desc = QLabel(
            "Configure writing tone, verbosity, and optional enhancements."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #6c757d; font-size: 11px; margin-bottom: 8px;")
        parent_layout.addWidget(desc)

        # Formality
        formality_row = QHBoxLayout()
        formality_row.addWidget(QLabel("Formality:"))

        self.formality_group = QButtonGroup(self)
        for formality_key, display_name in FORMALITY_DISPLAY_NAMES.items():
            radio = QRadioButton(display_name)
            radio.setProperty("formality_key", formality_key)
            if formality_key == self.config.formality_level:
                radio.setChecked(True)
            self.formality_group.addButton(radio)
            formality_row.addWidget(radio)
        self.formality_group.buttonClicked.connect(self._on_tone_changed)

        formality_row.addStretch()
        parent_layout.addLayout(formality_row)

        # Verbosity
        verbosity_row = QHBoxLayout()
        verbosity_row.addWidget(QLabel("Verbosity Reduction:"))

        self.verbosity_combo = QComboBox()
        self.verbosity_combo.setMinimumWidth(150)
        for verbosity_key in ["none", "minimum", "short", "medium", "maximum"]:
            self.verbosity_combo.addItem(VERBOSITY_DISPLAY_NAMES[verbosity_key], verbosity_key)
        idx = self.verbosity_combo.findData(self.config.verbosity_reduction)
        if idx >= 0:
            self.verbosity_combo.setCurrentIndex(idx)
        self.verbosity_combo.currentIndexChanged.connect(self._on_tone_changed)

        verbosity_row.addWidget(self.verbosity_combo)
        verbosity_row.addStretch()
        parent_layout.addLayout(verbosity_row)

        # Optional enhancements (only the 2 remaining)
        if OPTIONAL_PROMPT_COMPONENTS:
            parent_layout.addWidget(QLabel("Optional Enhancements:"))

            self.optional_checkboxes = {}
            for field_name, _, ui_description in OPTIONAL_PROMPT_COMPONENTS:
                checkbox = QCheckBox(ui_description)
                checkbox.setChecked(getattr(self.config, field_name, False))
                checkbox.stateChanged.connect(
                    lambda state, fn=field_name: self._on_optional_changed(fn, state)
                )
                self.optional_checkboxes[field_name] = checkbox
                parent_layout.addWidget(checkbox)

        # Writing sample
        parent_layout.addWidget(QLabel("Writing Sample (optional):"))
        ws_desc = QLabel(
            "Provide a sample of your writing to guide the AI's output style."
        )
        ws_desc.setStyleSheet("color: #6c757d; font-size: 10px;")
        parent_layout.addWidget(ws_desc)

        self.writing_sample_edit = QTextEdit()
        self.writing_sample_edit.setPlaceholderText(
            "Paste a sample of your writing here..."
        )
        self.writing_sample_edit.setMaximumHeight(120)
        self.writing_sample_edit.setText(self.config.writing_sample)
        self.writing_sample_edit.textChanged.connect(self._on_writing_sample_changed)
        parent_layout.addWidget(self.writing_sample_edit)

    def _on_tone_changed(self):
        """Handle formality or verbosity change."""
        # Update formality
        for button in self.formality_group.buttons():
            if button.isChecked():
                self.config.formality_level = button.property("formality_key")
                break

        # Update verbosity
        self.config.verbosity_reduction = self.verbosity_combo.currentData()

        save_config(self.config)

    def _on_optional_changed(self, field_name: str, state: int):
        """Handle optional checkbox change."""
        setattr(self.config, field_name, state == Qt.CheckState.Checked.value)
        save_config(self.config)

    def _on_writing_sample_changed(self):
        """Handle writing sample change."""
        self.config.writing_sample = self.writing_sample_edit.toPlainText()
        save_config(self.config)
