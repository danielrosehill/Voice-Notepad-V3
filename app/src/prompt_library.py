"""Prompt library management for Voice Notepad V3.

This module defines the prompt template system, categories, and output formats.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime


class PromptCategory(str, Enum):
    """Prompt categories for organization."""
    FOUNDATION = "foundation"              # Always applied (current foundation layer)
    FORMATTING = "formatting"              # Document structure
    DATA_FORMAT = "data_format"            # Data representation
    STYLISTIC = "stylistic"                # Tone and voice
    GRAMMATICAL = "grammatical"            # Grammar transformations
    CONTENT_TRANSFORM = "content_transform"  # Content changes
    AUDIENCE = "audience"                  # Audience-specific
    SPECIAL_PURPOSE = "special_purpose"    # Task-specific


class OutputFormat(str, Enum):
    """Output format for transcriptions."""
    TEXT = "text"           # Plain text
    MARKDOWN = "markdown"   # Markdown (current default)
    HTML = "html"           # HTML markup
    JSON = "json"           # JSON structure
    XML = "xml"             # XML structure
    YAML = "yaml"           # YAML structure


# Display names for output formats
OUTPUT_FORMAT_DISPLAY_NAMES = {
    OutputFormat.TEXT: "Plain Text",
    OutputFormat.MARKDOWN: "Markdown",
    OutputFormat.HTML: "HTML",
    OutputFormat.JSON: "JSON",
    OutputFormat.XML: "XML",
    OutputFormat.YAML: "YAML",
}


# Display names for prompt categories
CATEGORY_DISPLAY_NAMES = {
    PromptCategory.FOUNDATION: "Foundation (Always Applied)",
    PromptCategory.FORMATTING: "Formatting & Structure",
    PromptCategory.DATA_FORMAT: "Data Format",
    PromptCategory.STYLISTIC: "Style & Tone",
    PromptCategory.GRAMMATICAL: "Grammar & Voice",
    PromptCategory.CONTENT_TRANSFORM: "Content Transformation",
    PromptCategory.AUDIENCE: "Audience-Specific",
    PromptCategory.SPECIAL_PURPOSE: "Special Purpose",
}


@dataclass
class PromptTemplate:
    """A single prompt template.

    This is the Python representation. MongoDB stores as dict.
    """
    id: Optional[str]                # MongoDB ID (as string)
    name: str                        # Display name
    category: str                    # PromptCategory value
    description: str                 # User-facing description
    instruction: str                 # The actual prompt text
    is_builtin: bool = True          # True for app builtins, False for user-created
    is_enabled: bool = True          # Can be toggled on/off
    priority: int = 100              # Order of application (lower = earlier)
    subcategory: Optional[str] = None  # Optional subcategory
    conflicts_with: List[str] = field(default_factory=list)  # IDs of conflicting prompts
    requires: List[str] = field(default_factory=list)        # IDs of required prompts
    tags: List[str] = field(default_factory=list)            # Searchable tags
    has_parameters: bool = False     # Whether prompt accepts parameters
    parameters: Dict[str, Any] = field(default_factory=dict)  # Parameter definitions
    created_at: Optional[str] = None  # ISO timestamp
    modified_at: Optional[str] = None  # ISO timestamp

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for MongoDB storage."""
        d = {
            'name': self.name,
            'category': self.category,
            'description': self.description,
            'instruction': self.instruction,
            'is_builtin': self.is_builtin,
            'is_enabled': self.is_enabled,
            'priority': self.priority,
            'subcategory': self.subcategory,
            'conflicts_with': self.conflicts_with,
            'requires': self.requires,
            'tags': self.tags,
            'has_parameters': self.has_parameters,
            'parameters': self.parameters,
        }

        if self.created_at:
            d['created_at'] = self.created_at
        if self.modified_at:
            d['modified_at'] = self.modified_at

        return d

    @classmethod
    def from_dict(cls, doc: Dict[str, Any]) -> "PromptTemplate":
        """Create from MongoDB document."""
        return cls(
            id=doc.get('id'),
            name=doc['name'],
            category=doc['category'],
            description=doc['description'],
            instruction=doc['instruction'],
            is_builtin=doc.get('is_builtin', True),
            is_enabled=doc.get('is_enabled', True),
            priority=doc.get('priority', 100),
            subcategory=doc.get('subcategory'),
            conflicts_with=doc.get('conflicts_with', []),
            requires=doc.get('requires', []),
            tags=doc.get('tags', []),
            has_parameters=doc.get('has_parameters', False),
            parameters=doc.get('parameters', {}),
            created_at=doc.get('created_at'),
            modified_at=doc.get('modified_at'),
        )


# Output format instructions (added to beginning of prompt)
OUTPUT_FORMAT_INSTRUCTIONS = {
    OutputFormat.TEXT: "Output as plain text with no special formatting.",
    OutputFormat.MARKDOWN: "",  # Markdown is default, no special instruction needed
    OutputFormat.HTML: "Output as valid HTML markup. Use appropriate HTML tags for structure (p, h1-h6, ul, ol, etc.).",
    OutputFormat.JSON: "Output as valid JSON. Structure the content as a JSON object with appropriate fields.",
    OutputFormat.XML: "Output as valid XML. Use appropriate XML tags to structure the content.",
    OutputFormat.YAML: "Output as valid YAML. Use proper YAML syntax with appropriate indentation.",
}


def get_output_format_instruction(output_format: OutputFormat) -> str:
    """Get the instruction text for a given output format."""
    return OUTPUT_FORMAT_INSTRUCTIONS.get(output_format, "")


def detect_conflicts(prompts: List[PromptTemplate]) -> List[tuple[str, str]]:
    """Detect conflicts between prompts.

    Returns list of (prompt1_id, prompt2_id) tuples representing conflicts.
    """
    conflicts = []
    prompt_ids = {p.id for p in prompts}

    for prompt in prompts:
        for conflict_id in prompt.conflicts_with:
            if conflict_id in prompt_ids:
                # Add as sorted tuple to avoid duplicates
                conflict_pair = tuple(sorted([prompt.id, conflict_id]))
                if conflict_pair not in conflicts:
                    conflicts.append(conflict_pair)

    return conflicts


def validate_requirements(prompts: List[PromptTemplate]) -> List[tuple[str, str]]:
    """Validate that all required prompts are present.

    Returns list of (prompt_id, missing_requirement_id) tuples.
    """
    missing = []
    prompt_ids = {p.id for p in prompts}

    for prompt in prompts:
        for required_id in prompt.requires:
            if required_id not in prompt_ids:
                missing.append((prompt.id, required_id))

    return missing


def build_prompt_from_templates(
    prompts: List[PromptTemplate],
    output_format: OutputFormat = OutputFormat.MARKDOWN,
    include_format_instruction: bool = True,
) -> str:
    """Build a complete prompt from a list of prompt templates.

    Prompts are concatenated in priority order (lower priority first).
    Output format instruction is added at the beginning.

    Args:
        prompts: List of PromptTemplate objects (should be sorted by priority)
        output_format: Output format for the transcription
        include_format_instruction: Whether to include format instruction

    Returns:
        Complete prompt string
    """
    lines = []

    # Add output format instruction if needed
    if include_format_instruction:
        format_inst = get_output_format_instruction(output_format)
        if format_inst:
            lines.append("## Output Format")
            lines.append(f"- {format_inst}")
            lines.append("")

    # Group prompts by category for better organization
    prompts_by_category = {}
    for prompt in sorted(prompts, key=lambda p: p.priority):
        if prompt.category not in prompts_by_category:
            prompts_by_category[prompt.category] = []
        prompts_by_category[prompt.category].append(prompt)

    # Add prompts grouped by category
    for category in [
        PromptCategory.FOUNDATION,
        PromptCategory.FORMATTING,
        PromptCategory.STYLISTIC,
        PromptCategory.GRAMMATICAL,
        PromptCategory.CONTENT_TRANSFORM,
        PromptCategory.DATA_FORMAT,
        PromptCategory.AUDIENCE,
        PromptCategory.SPECIAL_PURPOSE,
    ]:
        if category in prompts_by_category:
            category_prompts = prompts_by_category[category]

            # Add category header
            lines.append(f"## {CATEGORY_DISPLAY_NAMES.get(category, category)}")

            # Add each prompt's instruction
            for prompt in category_prompts:
                lines.append(f"- {prompt.instruction}")

            lines.append("")

    return "\n".join(lines)
