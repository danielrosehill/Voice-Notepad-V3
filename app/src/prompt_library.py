"""Prompt library management for Voice Notepad V3.

This module defines the unified prompt system with:
- PromptConfig: User-facing prompt configurations (favorites, custom prompts)
- PromptLibrary: Manager for all prompts (builtins + custom + favorites)
- PromptTemplate: Internal prompt template representation

Architecture:
- Everything is a "PromptConfig" - simple formats or complex stacks
- Users can favorite any config for quick access (15-20 slots)
- Built-in prompts are editable (user modifications stored separately)
- Verbatim is just another prompt that instructs verbatim output
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
from pathlib import Path
import json
import uuid


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


# =============================================================================
# UNIFIED PROMPT SYSTEM
# =============================================================================
# PromptConfig: User-facing prompt configurations (what users interact with)
# PromptLibrary: Manager for all prompts (builtins + custom + favorites)
# =============================================================================


class PromptConfigCategory(str, Enum):
    """User-facing categories for prompt configurations.

    Categories are organized to group related prompts in the favorites bar:
    - FOUNDATIONAL: Core transcription modes (General, Verbatim)
    - STYLISTIC: Writing styles and formats (Email, Meeting Notes, etc.)
    - PROMPTS: AI prompt formats (AI Prompt, Dev Prompt, System Prompt)
    - TODO_LISTS: List formats (To-Do, Shopping List)
    - BLOG: Blog/content creation formats
    - DOCUMENTATION: Technical and reference documentation
    - CREATIVE: Creative writing and social media
    - WORK: Business/professional formats
    - CUSTOM: User-created prompts
    """
    FOUNDATIONAL = "foundational"
    STYLISTIC = "stylistic"
    PROMPTS = "prompts"
    TODO_LISTS = "todo_lists"
    BLOG = "blog"
    DOCUMENTATION = "documentation"
    CREATIVE = "creative"
    WORK = "work"
    CUSTOM = "custom"


# Display names for user-facing categories
PROMPT_CONFIG_CATEGORY_NAMES = {
    PromptConfigCategory.FOUNDATIONAL: "Foundational",
    PromptConfigCategory.STYLISTIC: "Format",
    PromptConfigCategory.PROMPTS: "Prompts",
    PromptConfigCategory.TODO_LISTS: "To-Do Lists",
    PromptConfigCategory.BLOG: "Blog",
    PromptConfigCategory.DOCUMENTATION: "Documentation",
    PromptConfigCategory.CREATIVE: "Creative",
    PromptConfigCategory.WORK: "Work",
    PromptConfigCategory.CUSTOM: "Custom",
}


@dataclass
class PromptConfig:
    """A unified prompt configuration.

    This represents a complete prompt setup that can be:
    - A simple format preset (like "email" or "todo")
    - A complex stack of elements (like "meeting notes + action items + formal")
    - A user-created custom prompt

    All prompts are treated equally - the distinction between "presets" and
    "stacks" is purely in how they're constructed internally.
    """
    id: str                              # Unique identifier (uuid)
    name: str                            # Display name
    category: str                        # PromptConfigCategory value
    description: str                     # User-facing description

    # How the prompt is built (mutually exclusive)
    # Option A: Direct instruction (simple format)
    instruction: str = ""                # The format instruction
    adherence: str = ""                  # How strictly to follow

    # Option B: Element-based (stack of elements)
    elements: List[str] = field(default_factory=list)  # Element keys to combine

    # Metadata
    is_builtin: bool = True              # True for app defaults
    is_modified: bool = False            # True if user edited a builtin
    is_favorite: bool = False            # Show in quick-access bar
    favorite_order: int = 999            # Position in favorites (lower = earlier)

    # Optional overrides (None = use global settings)
    formality: Optional[str] = None      # Override formality level
    verbosity: Optional[str] = None      # Override verbosity reduction

    # Email-specific settings
    use_business_signature: bool = True  # Use business vs personal signature

    # Timestamps
    created_at: Optional[str] = None
    modified_at: Optional[str] = None

    def __post_init__(self):
        """Generate ID if not provided."""
        if not self.id:
            self.id = str(uuid.uuid4())
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON storage."""
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "instruction": self.instruction,
            "adherence": self.adherence,
            "elements": self.elements,
            "is_builtin": self.is_builtin,
            "is_modified": self.is_modified,
            "is_favorite": self.is_favorite,
            "favorite_order": self.favorite_order,
            "formality": self.formality,
            "verbosity": self.verbosity,
            "use_business_signature": self.use_business_signature,
            "created_at": self.created_at,
            "modified_at": self.modified_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PromptConfig":
        """Create from dict (JSON storage)."""
        return cls(
            id=data.get("id", ""),
            name=data["name"],
            category=data.get("category", PromptConfigCategory.CUSTOM),
            description=data.get("description", ""),
            instruction=data.get("instruction", ""),
            adherence=data.get("adherence", ""),
            elements=data.get("elements", []),
            is_builtin=data.get("is_builtin", False),
            is_modified=data.get("is_modified", False),
            is_favorite=data.get("is_favorite", False),
            favorite_order=data.get("favorite_order", 999),
            formality=data.get("formality"),
            verbosity=data.get("verbosity"),
            use_business_signature=data.get("use_business_signature", True),
            created_at=data.get("created_at"),
            modified_at=data.get("modified_at"),
        )

    def is_element_based(self) -> bool:
        """Check if this config uses element stacking."""
        return len(self.elements) > 0

    def clone(self, new_name: str = None) -> "PromptConfig":
        """Create a copy of this config (for user customization)."""
        data = self.to_dict()
        data["id"] = str(uuid.uuid4())
        data["name"] = new_name or f"{self.name} (copy)"
        data["is_builtin"] = False
        data["is_modified"] = False
        data["is_favorite"] = False
        data["favorite_order"] = 999
        data["created_at"] = datetime.now().isoformat()
        data["modified_at"] = None
        return PromptConfig.from_dict(data)


# =============================================================================
# DEFAULT PROMPT CONFIGS
# =============================================================================
# These are the built-in prompts that ship with the app.
# Users can edit them (modifications stored separately) or create custom ones.
# =============================================================================

DEFAULT_PROMPT_CONFIGS: List[PromptConfig] = [
    # ==========================================================================
    # FOUNDATIONAL - Core transcription modes (Row 1 in favorites bar)
    # ==========================================================================
    PromptConfig(
        id="general",
        name="General",
        category=PromptConfigCategory.FOUNDATIONAL,
        description="Standard cleanup with no specific formatting",
        instruction="",
        adherence="",
        is_favorite=True,
        favorite_order=0,
    ),
    PromptConfig(
        id="verbatim",
        name="Verbatim",
        category=PromptConfigCategory.FOUNDATIONAL,
        description="Minimal transformation - closest to raw transcription",
        instruction="Preserve the original wording and structure as much as possible while applying only essential cleanup.",
        adherence="Keep the transcription very close to the original speech. Only remove obvious filler words, add basic punctuation, and create paragraph breaks. Do not rephrase, restructure, or add formatting beyond the absolute minimum needed for readability.",
        is_favorite=True,
        favorite_order=1,
    ),
    PromptConfig(
        id="brief",
        name="Brief",
        category=PromptConfigCategory.FOUNDATIONAL,
        description="Maximum conciseness - as brief as possible",
        instruction="Be as brief as possible. Condense the content to its essential core message with maximum conciseness.",
        adherence="Ruthlessly cut unnecessary words, qualifiers, and redundant phrases. Prefer short sentences. Eliminate preamble and filler. Every word must earn its place. Aim for the minimum viable length while preserving meaning.",
        is_favorite=True,
        favorite_order=2,
    ),
    PromptConfig(
        id="quick_note",
        name="Quick Note",
        category=PromptConfigCategory.FOUNDATIONAL,
        description="Quick personal note - minimal formatting",
        instruction="Format as a quick personal note. Minimal formatting, just capture the thought clearly.",
        adherence="Keep it informal and quick. No headers, no elaborate structure. Just the thought, clearly expressed. Suitable for jotting down ideas or reminders.",
    ),

    # ==========================================================================
    # STYLISTIC - Writing styles and formats (Row 2 in favorites bar)
    # ==========================================================================
    PromptConfig(
        id="email",
        name="Email",
        category=PromptConfigCategory.STYLISTIC,
        description="Professional email format with greeting and sign-off",
        instruction="Format the output as an email with an appropriate greeting and sign-off.",
        adherence="Follow standard email formatting conventions. Include a clear subject line suggestion if the content is substantial. Use proper email etiquette.",
        is_favorite=True,
        favorite_order=10,
    ),
    PromptConfig(
        id="meeting_notes",
        name="Meeting Notes",
        category=PromptConfigCategory.STYLISTIC,
        description="Structured meeting notes with action items",
        instruction="Format as meeting notes with clear sections, bullet points for key points, and a separate 'Action Items' section at the end.",
        adherence="Include: meeting date/time if mentioned, attendees if mentioned, discussion points as bullets, decisions made, and action items with assignees if specified.",
        is_favorite=True,
        favorite_order=11,
    ),
    PromptConfig(
        id="bullet_points",
        name="Bullet Points",
        category=PromptConfigCategory.STYLISTIC,
        description="Simple bullet point list",
        instruction="Format as concise bullet points. One idea per bullet.",
        adherence="Each bullet must be self-contained and parallel in structure. Use consistent formatting throughout.",
        is_favorite=True,
        favorite_order=12,
    ),
    PromptConfig(
        id="persuasive",
        name="Persuasive",
        category=PromptConfigCategory.STYLISTIC,
        description="Persuasive writing to convince or influence",
        instruction="Write with persuasive language designed to convince or influence the reader. Use rhetorical techniques, emotional appeals, and compelling arguments.",
        adherence="Employ persuasive techniques: strong opening hook, clear value proposition, social proof if available, address potential objections, use active voice, include call-to-action. Balance logic with emotional appeal. Be assertive but not pushy.",
    ),
    PromptConfig(
        id="slack_message",
        name="Slack Message",
        category=PromptConfigCategory.STYLISTIC,
        description="Workplace chat message (Slack/Teams)",
        instruction="Format as a workplace chat message (Slack/Teams style). Keep it conversational, direct, and appropriately informal for workplace communication.",
        adherence="Be concise and scannable. Use line breaks for readability. Emoji are okay if tone suits. Get to the point quickly. Can use bullet points for multiple items. Maintain professional-casual balance.",
    ),

    # ==========================================================================
    # PROMPTS - AI prompt formats (Row 3 in favorites bar)
    # ==========================================================================
    PromptConfig(
        id="ai_prompt",
        name="AI Prompt",
        category=PromptConfigCategory.PROMPTS,
        description="General AI assistant instructions",
        instruction="Format the output as clear, well-organized instructions for an AI assistant. Use imperative voice, organize tasks logically, and ensure instructions are unambiguous and actionable.",
        adherence="Strictly follow AI prompt engineering best practices: be specific, use clear command language, break complex tasks into numbered steps, and include context where needed.",
        is_favorite=True,
        favorite_order=20,
    ),
    PromptConfig(
        id="dev_prompt",
        name="Dev Prompt",
        category=PromptConfigCategory.PROMPTS,
        description="Software development instructions for AI",
        instruction="Format the output as a development prompt for a software development AI assistant. Include technical requirements, implementation details, and expected outcomes. Use imperative voice and be explicit about technical constraints.",
        adherence="Follow software development prompt conventions: specify programming languages, frameworks, file paths if mentioned, testing requirements, and code quality expectations.",
        is_favorite=True,
        favorite_order=21,
    ),
    PromptConfig(
        id="system_prompt",
        name="System Prompt",
        category=PromptConfigCategory.PROMPTS,
        description="AI system prompt (second-person, 'You are...' style)",
        instruction="Format as a system prompt for an AI assistant. Write in second-person, addressing the AI directly. Define its role, capabilities, constraints, and behavioral guidelines using 'You are...' and 'You should...' statements.",
        adherence="Always use second-person perspective addressing the AI directly (e.g., 'You are a helpful assistant', 'You should respond concisely'). Never use third-person ('The assistant should...'). Define role clearly upfront. Specify constraints and boundaries. Include behavioral guidelines. Be comprehensive but concise.",
        is_favorite=True,
        favorite_order=22,
    ),

    # ==========================================================================
    # TODO_LISTS - List formats (Row 4 in favorites bar)
    # ==========================================================================
    PromptConfig(
        id="todo",
        name="To-Do",
        category=PromptConfigCategory.TODO_LISTS,
        description="Checkbox to-do list format",
        instruction="Format as a to-do list with checkbox items (- [ ] task). Use action verbs and be concise.",
        adherence="Each item must start with an action verb. Keep items specific and actionable. Group related items under headers if there are distinct categories.",
        is_favorite=True,
        favorite_order=30,
    ),
    PromptConfig(
        id="shopping_list",
        name="Shopping List",
        category=PromptConfigCategory.TODO_LISTS,
        description="Categorized shopping list",
        instruction="Format as a shopping list. Group items by category (produce, dairy, meat, pantry, household, etc.) if there are multiple items.",
        adherence="Always organize by store section categories. Use consistent item naming (e.g., quantities if mentioned).",
        is_favorite=True,
        favorite_order=31,
    ),

    # ==========================================================================
    # BLOG - Blog/content creation formats (Row 5 in favorites bar)
    # ==========================================================================
    PromptConfig(
        id="blog",
        name="Blog Post",
        category=PromptConfigCategory.BLOG,
        description="Blog post format with sections and flow",
        instruction="Format as a blog post with a compelling title, engaging introduction, well-organized body sections, and a conclusion.",
        adherence="Structure for readability. Use subheadings to break up content. Maintain a conversational yet informative tone. Note where examples or images might enhance the content.",
        is_favorite=True,
        favorite_order=40,
    ),
    PromptConfig(
        id="blog_outline",
        name="Blog Outline",
        category=PromptConfigCategory.BLOG,
        description="Blog post outline with sections",
        instruction="Format as a blog post outline with a compelling title, introduction hook, main sections, and conclusion.",
        adherence="Structure for readability. Include suggested subheadings. Note where examples or images might enhance the content.",
    ),

    # ==========================================================================
    # DOCUMENTATION - Technical and reference documentation
    # ==========================================================================
    PromptConfig(
        id="documentation",
        name="Documentation",
        category=PromptConfigCategory.DOCUMENTATION,
        description="Clear, structured documentation format",
        instruction="Format as structured documentation with clear headings, organized sections, and logical flow.",
        adherence="Use markdown formatting. Structure content hierarchically. Be clear and precise. Include examples where helpful.",
        is_favorite=True,
        favorite_order=50,
    ),
    PromptConfig(
        id="tech_docs",
        name="Tech Docs",
        category=PromptConfigCategory.DOCUMENTATION,
        description="Technical documentation with code examples",
        instruction="Format as technical documentation with clear headings, code examples in fenced blocks, and structured explanations.",
        adherence="Use markdown formatting. Include code blocks with language tags. Be precise with technical terminology.",
    ),
    PromptConfig(
        id="readme",
        name="README",
        category=PromptConfigCategory.DOCUMENTATION,
        description="GitHub README format",
        instruction="Format as a README.md file for a software project. Include clear sections for project description, installation, usage, and other relevant information.",
        adherence="Follow standard README conventions: project title as H1, sections as H2, code blocks for commands, and clear installation/usage instructions.",
    ),
    PromptConfig(
        id="api_docs",
        name="API Docs",
        category=PromptConfigCategory.DOCUMENTATION,
        description="API endpoint documentation",
        instruction="Format as API documentation with endpoint details, request/response formats, and parameter descriptions.",
        adherence="Include HTTP methods, URL patterns, request bodies, response examples, and error codes. Use code blocks for JSON examples.",
    ),

    # ==========================================================================
    # WORK - Business/professional formats
    # ==========================================================================
    PromptConfig(
        id="bug_report",
        name="Bug Report",
        category=PromptConfigCategory.WORK,
        description="Structured bug report format",
        instruction="Format as a bug report with sections for Description, Steps to Reproduce, Expected Behavior, Actual Behavior, and Environment (if mentioned).",
        adherence="Use clear technical language. Ensure steps are numbered and specific. Include any error messages or codes mentioned.",
    ),
    PromptConfig(
        id="status_update",
        name="Status Update",
        category=PromptConfigCategory.WORK,
        description="Brief project status update",
        instruction="Format as a concise status update with what was completed, what's in progress, and any blockers.",
        adherence="Keep it brief and scannable. Use bullet points. Focus on facts rather than details.",
        is_favorite=True,
        favorite_order=61,
    ),
    PromptConfig(
        id="software_spec",
        name="Software Spec",
        category=PromptConfigCategory.WORK,
        description="Software requirements specification",
        instruction="Format as a software specification document with clear requirements. Include: Overview, Functional Requirements (numbered list), Non-Functional Requirements, Constraints, and Acceptance Criteria if mentioned.",
        adherence="Use precise, unambiguous language. Number all requirements for reference (REQ-001, REQ-002, etc. or simple numbering). Each requirement should be testable and specific. Use 'shall' for mandatory requirements, 'should' for recommendations. Group related requirements under clear headings.",
    ),

    # ==========================================================================
    # CREATIVE - Creative writing and social media
    # ==========================================================================
    PromptConfig(
        id="social_post",
        name="Social Post",
        category=PromptConfigCategory.CREATIVE,
        description="Social media post format",
        instruction="Format as a social media post. Keep it engaging, concise, and appropriate for platforms like Twitter/X or LinkedIn.",
        adherence="Optimize for engagement. Use appropriate hashtags if relevant. Keep within typical character limits.",
        is_favorite=True,
        favorite_order=70,
    ),
    PromptConfig(
        id="community_post",
        name="Community Post",
        category=PromptConfigCategory.CREATIVE,
        description="Community/forum post (Reddit, Discord, etc.)",
        instruction="Format as an online community post (Reddit, forums, Discord, etc.). Start with a brief friendly intro or context, use short paragraphs for readability, and maintain an approachable conversational tone.",
        adherence="Start with context or a brief 'Hi' intro if appropriate. Use short paragraphs (2-3 sentences max). Add line breaks between paragraphs for readability. Be genuine and conversational. Include a clear question or discussion point if asking for help. End with thanks if requesting assistance.",
        is_favorite=True,
        favorite_order=71,
    ),
    PromptConfig(
        id="story_notes",
        name="Story Notes",
        category=PromptConfigCategory.CREATIVE,
        description="Creative writing notes and ideas",
        instruction="Format as creative writing notes. Capture character ideas, plot points, settings, and any narrative elements mentioned.",
        adherence="Preserve creative details and mood. Organize by narrative element (characters, plot, setting, themes).",
    ),
]


class PromptLibrary:
    """Manages all prompt configurations (builtins + custom + favorites).

    Provides a unified interface for:
    - Loading and saving prompts
    - Managing favorites for quick access
    - User modifications to builtin prompts
    - Creating custom prompts
    """

    def __init__(self, config_dir: Path):
        """Initialize the prompt library.

        Args:
            config_dir: Path to config directory (e.g., ~/.config/voice-notepad-v3/)
        """
        self.config_dir = config_dir
        self.prompts_dir = config_dir / "prompts"
        self.prompts_dir.mkdir(parents=True, exist_ok=True)

        # Storage files
        self.custom_prompts_file = self.prompts_dir / "custom.json"
        self.modifications_file = self.prompts_dir / "modifications.json"
        self.favorites_file = self.prompts_dir / "favorites.json"

        # In-memory cache
        self._builtins: Dict[str, PromptConfig] = {}
        self._custom: Dict[str, PromptConfig] = {}
        self._modifications: Dict[str, Dict[str, Any]] = {}  # id -> modified fields
        self._favorites_order: Dict[str, int] = {}  # id -> order

        # Load data
        self._load_builtins()
        self._load_custom()
        self._load_modifications()
        self._load_favorites()

    def _load_builtins(self):
        """Load builtin prompts into cache."""
        for config in DEFAULT_PROMPT_CONFIGS:
            self._builtins[config.id] = config

    def _load_custom(self):
        """Load custom prompts from disk."""
        if not self.custom_prompts_file.exists():
            return

        try:
            with open(self.custom_prompts_file) as f:
                data = json.load(f)
            for item in data.get("prompts", []):
                config = PromptConfig.from_dict(item)
                self._custom[config.id] = config
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Error loading custom prompts: {e}")

    def _load_modifications(self):
        """Load user modifications to builtin prompts."""
        if not self.modifications_file.exists():
            return

        try:
            with open(self.modifications_file) as f:
                self._modifications = json.load(f)
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Error loading modifications: {e}")

    def _load_favorites(self):
        """Load favorites order from disk."""
        if not self.favorites_file.exists():
            # Initialize from builtin defaults
            for config in DEFAULT_PROMPT_CONFIGS:
                if config.is_favorite:
                    self._favorites_order[config.id] = config.favorite_order
            return

        try:
            with open(self.favorites_file) as f:
                self._favorites_order = json.load(f)
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Error loading favorites: {e}")

    def _save_custom(self):
        """Save custom prompts to disk."""
        data = {"prompts": [c.to_dict() for c in self._custom.values()]}
        with open(self.custom_prompts_file, "w") as f:
            json.dump(data, f, indent=2)

    def _save_modifications(self):
        """Save modifications to disk."""
        with open(self.modifications_file, "w") as f:
            json.dump(self._modifications, f, indent=2)

    def _save_favorites(self):
        """Save favorites order to disk."""
        with open(self.favorites_file, "w") as f:
            json.dump(self._favorites_order, f, indent=2)

    def get(self, prompt_id: str) -> Optional[PromptConfig]:
        """Get a prompt config by ID, applying any user modifications."""
        # Check custom first
        if prompt_id in self._custom:
            config = self._custom[prompt_id]
        elif prompt_id in self._builtins:
            config = self._builtins[prompt_id]
        else:
            return None

        # Apply modifications if any
        if prompt_id in self._modifications:
            data = config.to_dict()
            data.update(self._modifications[prompt_id])
            data["is_modified"] = True
            config = PromptConfig.from_dict(data)

        # Apply favorite status
        if prompt_id in self._favorites_order:
            config.is_favorite = True
            config.favorite_order = self._favorites_order[prompt_id]
        else:
            config.is_favorite = False

        return config

    def get_all(self) -> List[PromptConfig]:
        """Get all prompts (builtins + custom), with modifications applied."""
        all_ids = set(self._builtins.keys()) | set(self._custom.keys())
        return [self.get(pid) for pid in all_ids if self.get(pid) is not None]

    def get_by_category(self, category: str) -> List[PromptConfig]:
        """Get all prompts in a category."""
        return [p for p in self.get_all() if p.category == category]

    def get_favorites(self) -> List[PromptConfig]:
        """Get favorite prompts, sorted by order."""
        favorites = [self.get(pid) for pid in self._favorites_order.keys()]
        favorites = [f for f in favorites if f is not None]
        return sorted(favorites, key=lambda p: p.favorite_order)

    def add_favorite(self, prompt_id: str, order: int = None):
        """Add a prompt to favorites."""
        if order is None:
            # Add at end
            order = max(self._favorites_order.values(), default=-1) + 1
        self._favorites_order[prompt_id] = order
        self._save_favorites()

    def remove_favorite(self, prompt_id: str):
        """Remove a prompt from favorites."""
        if prompt_id in self._favorites_order:
            del self._favorites_order[prompt_id]
            self._save_favorites()

    def reorder_favorites(self, ordered_ids: List[str]):
        """Reorder favorites by providing a list of IDs in desired order."""
        self._favorites_order = {pid: idx for idx, pid in enumerate(ordered_ids)}
        self._save_favorites()

    def create_custom(self, config: PromptConfig) -> PromptConfig:
        """Create a new custom prompt."""
        config.is_builtin = False
        config.created_at = datetime.now().isoformat()
        self._custom[config.id] = config
        self._save_custom()
        return config

    def update_custom(self, config: PromptConfig):
        """Update an existing custom prompt."""
        if config.id not in self._custom:
            raise ValueError(f"Custom prompt {config.id} not found")
        config.modified_at = datetime.now().isoformat()
        self._custom[config.id] = config
        self._save_custom()

    def delete_custom(self, prompt_id: str):
        """Delete a custom prompt."""
        if prompt_id in self._custom:
            del self._custom[prompt_id]
            self._save_custom()
        # Also remove from favorites
        self.remove_favorite(prompt_id)

    def modify_builtin(self, prompt_id: str, modifications: Dict[str, Any]):
        """Modify a builtin prompt (stores delta, not full copy)."""
        if prompt_id not in self._builtins:
            raise ValueError(f"Builtin prompt {prompt_id} not found")
        modifications["modified_at"] = datetime.now().isoformat()
        self._modifications[prompt_id] = modifications
        self._save_modifications()

    def reset_builtin(self, prompt_id: str):
        """Reset a builtin prompt to its default state."""
        if prompt_id in self._modifications:
            del self._modifications[prompt_id]
            self._save_modifications()

    def is_modified(self, prompt_id: str) -> bool:
        """Check if a builtin prompt has been modified."""
        return prompt_id in self._modifications

    def search(self, query: str) -> List[PromptConfig]:
        """Search prompts by name or description."""
        query = query.lower()
        results = []
        for config in self.get_all():
            if query in config.name.lower() or query in config.description.lower():
                results.append(config)
        return results

    def build_prompt(self, prompt_id: str, app_config: Any = None) -> str:
        """Build a complete cleanup prompt from a prompt config.

        Args:
            prompt_id: ID of the prompt config to use
            app_config: Optional app Config object for additional settings
                       (formality, verbosity, email signature, etc.)

        Returns:
            Complete cleanup prompt string ready to send to the API
        """
        config = self.get(prompt_id)
        if config is None:
            # Fallback to general
            config = self.get("general")

        return build_prompt_from_config(config, app_config)


def build_prompt_from_config(prompt_config: PromptConfig, app_config: Any = None) -> str:
    """Build a complete cleanup prompt from a PromptConfig.

    This combines:
    1. Foundation cleanup (always applied)
    2. The prompt config's format instructions
    3. App-level settings (formality, verbosity, email signature)

    Args:
        prompt_config: The PromptConfig to build from
        app_config: Optional app Config object for additional settings

    Returns:
        Complete cleanup prompt string
    """
    # Import here to avoid circular imports
    try:
        from .config import FOUNDATION_PROMPT_SECTIONS
    except ImportError:
        from config import FOUNDATION_PROMPT_SECTIONS

    lines = ["Your task is to provide a cleaned transcription of the audio recorded by the user."]

    # ===== LAYER 1: FOUNDATION (ALWAYS APPLIED) =====
    lines.append("\n## Foundation Cleanup (Always Applied)")
    for section_key, section_data in FOUNDATION_PROMPT_SECTIONS.items():
        for instruction in section_data["instructions"]:
            lines.append(f"- {instruction}")

    # ===== LAYER 2: FORMAT-SPECIFIC INSTRUCTIONS =====
    if prompt_config.is_element_based():
        # Build from elements
        try:
            from .prompt_elements import ALL_ELEMENTS
        except ImportError:
            from prompt_elements import ALL_ELEMENTS

        format_lines = []
        style_lines = []

        for elem_key in prompt_config.elements:
            if elem_key in ALL_ELEMENTS:
                elem = ALL_ELEMENTS[elem_key]
                if elem.category == "format":
                    format_lines.append(f"- {elem.instruction}")
                    if elem.adherence:
                        format_lines.append(f"  {elem.adherence}")
                elif elem.category in ("style", "grammar"):
                    style_lines.append(f"- {elem.instruction}")

        if format_lines:
            lines.append("\n## Format Requirements")
            lines.extend(format_lines)

        if style_lines:
            lines.append("\n## Style & Grammar")
            lines.extend(style_lines)

    else:
        # Use direct instruction/adherence
        if prompt_config.instruction or prompt_config.adherence:
            lines.append("\n## Format Requirements")
            if prompt_config.instruction:
                lines.append(f"- {prompt_config.instruction}")
            if prompt_config.adherence:
                lines.append(f"- {prompt_config.adherence}")

    # ===== LAYER 3: APP-LEVEL SETTINGS =====
    if app_config:
        # Import formality/verbosity templates
        try:
            from .config import FORMALITY_TEMPLATES, VERBOSITY_TEMPLATES
        except ImportError:
            from config import FORMALITY_TEMPLATES, VERBOSITY_TEMPLATES

        style_instructions = []

        # Formality (prompt override takes precedence)
        formality = prompt_config.formality or getattr(app_config, 'formality_level', None)
        if formality and formality in FORMALITY_TEMPLATES:
            template = FORMALITY_TEMPLATES[formality]
            if template:
                style_instructions.append(template)

        # Verbosity (prompt override takes precedence)
        verbosity = prompt_config.verbosity or getattr(app_config, 'verbosity_reduction', None)
        if verbosity and verbosity in VERBOSITY_TEMPLATES:
            template = VERBOSITY_TEMPLATES[verbosity]
            if template:
                style_instructions.append(template)

        if style_instructions:
            lines.append("\n## Style & Tone")
            for instruction in style_instructions:
                lines.append(f"- {instruction}")

        # Writing sample
        writing_sample = getattr(app_config, 'writing_sample', None)
        if writing_sample and writing_sample.strip():
            lines.append("\n## Writing Style Reference")
            lines.append("The user has provided the following writing sample as a reference for tone, style, and structure. "
                        "Use this as guidance for the output style:")
            lines.append(f"\n{writing_sample.strip()}\n")

        # Email signature (if email format)
        if prompt_config.id == "email" or prompt_config.name.lower() == "email":
            user_name = getattr(app_config, 'user_name', None)

            # Choose signature based on prompt config preference
            if prompt_config.use_business_signature:
                sender_email = getattr(app_config, 'business_email', None) or getattr(app_config, 'personal_email', None)
                sender_signature = getattr(app_config, 'business_signature', None) or getattr(app_config, 'personal_signature', None)
            else:
                sender_email = getattr(app_config, 'personal_email', None) or getattr(app_config, 'business_email', None)
                sender_signature = getattr(app_config, 'personal_signature', None) or getattr(app_config, 'business_signature', None)

            user_phone = getattr(app_config, 'user_phone', None)

            if user_name or sender_email or user_phone:
                lines.append("\n## User Profile")
                profile_parts = []
                if user_name:
                    profile_parts.append(f"Name: {user_name}")
                if sender_email:
                    profile_parts.append(f"Email: {sender_email}")
                if user_phone:
                    profile_parts.append(f"Phone: {user_phone}")

                profile_info = ", ".join(profile_parts)
                lines.append(f"- Draft the email from the following person: {profile_info}")

            if sender_signature:
                lines.append(f"- End the email with the following signature:\n\n{sender_signature}")
            elif user_name:
                sign_off = getattr(app_config, 'email_signature', "Best regards")
                lines.append(f"- End the email with the sign-off: \"{sign_off},\" followed by the sender's name: \"{user_name}\"")

    # Final instruction
    lines.append("\n## Output")
    lines.append("- Output ONLY the cleaned transcription in markdown format, no commentary or preamble")

    return "\n".join(lines)
