"""
Prompt Elements and Stacks

This module defines individual prompt elements (format, style, grammar) and
allows users to combine them into reusable "prompt stacks".

Architecture:
- Prompt Elements: Individual instructions (e.g., "email format", "casual tone", "add punctuation")
- Prompt Stacks: Saved combinations of elements that can be applied together
- Multi-select: Users can select multiple elements from different categories
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, field
import json
from pathlib import Path


@dataclass
class PromptElement:
    """A single prompt element (format, style, or grammar instruction)."""
    key: str
    name: str
    category: str  # "format", "style", "grammar"
    instruction: str
    adherence: str = ""
    description: str = ""


@dataclass
class PromptStack:
    """A saved combination of prompt elements."""
    name: str
    elements: List[str]  # List of element keys
    description: str = ""


# ===== FORMAT ELEMENTS =====
# These define the output format (email, todo list, meeting notes, etc.)

FORMAT_ELEMENTS = {
    "email": PromptElement(
        key="email",
        name="Email",
        category="format",
        instruction="Format the output as an email with an appropriate greeting and sign-off.",
        adherence="Follow standard email formatting conventions. Include a clear subject line suggestion if the content is substantial. Use proper email etiquette.",
        description="Professional email format with greeting and sign-off"
    ),
    "todo": PromptElement(
        key="todo",
        name="To-Do List",
        category="format",
        instruction="Format as a to-do list with checkbox items (- [ ] task). Use action verbs and be concise.",
        adherence="Each item must start with an action verb. Keep items specific and actionable. Group related items under headers if there are distinct categories.",
        description="Checkbox to-do list format"
    ),
    "meeting_notes": PromptElement(
        key="meeting_notes",
        name="Meeting Notes",
        category="format",
        instruction="Format as meeting notes with clear sections, bullet points for key points, and a separate 'Action Items' section at the end.",
        adherence="Include: meeting date/time if mentioned, attendees if mentioned, discussion points as bullets, decisions made, and action items with assignees if specified.",
        description="Structured meeting notes with action items"
    ),
    "bullet_points": PromptElement(
        key="bullet_points",
        name="Bullet Points",
        category="format",
        instruction="Format as concise bullet points. One idea per bullet.",
        adherence="Each bullet must be self-contained and parallel in structure. Use consistent formatting throughout.",
        description="Simple bullet point list"
    ),
    "ai_prompt": PromptElement(
        key="ai_prompt",
        name="AI Prompt",
        category="format",
        instruction="Format the output as clear, well-organized instructions for an AI assistant. Use imperative voice, organize tasks logically, and ensure instructions are unambiguous and actionable.",
        adherence="Strictly follow AI prompt engineering best practices: be specific, use clear command language, break complex tasks into numbered steps, and include context where needed.",
        description="General AI assistant instructions"
    ),
    "dev_prompt": PromptElement(
        key="dev_prompt",
        name="Dev Prompt",
        category="format",
        instruction="Format the output as a development prompt for a software development AI assistant. Include technical requirements, implementation details, and expected outcomes. Use imperative voice and be explicit about technical constraints.",
        adherence="Follow software development prompt conventions: specify programming languages, frameworks, file paths if mentioned, testing requirements, and code quality expectations.",
        description="Software development instructions for AI"
    ),
    "readme": PromptElement(
        key="readme",
        name="README",
        category="format",
        instruction="Format as a README.md file for a software project. Include clear sections for project description, installation, usage, and other relevant information.",
        adherence="Follow standard README conventions: project title as H1, sections as H2, code blocks for commands, and clear installation/usage instructions.",
        description="GitHub README format"
    ),
    "grocery": PromptElement(
        key="grocery",
        name="Grocery List",
        category="format",
        instruction="Format as a grocery list. Group items by category (produce, dairy, meat, pantry, etc.) if there are multiple items.",
        adherence="Always organize by store section categories. Use consistent item naming (e.g., quantities if mentioned).",
        description="Categorized grocery shopping list"
    ),
}


# ===== STYLE ELEMENTS =====
# These define writing style (casual, formal, concise, detailed, etc.)

STYLE_ELEMENTS = {
    "casual": PromptElement(
        key="casual",
        name="Casual Tone",
        category="style",
        instruction="Use a casual, conversational tone. Write as if speaking to a friend.",
        adherence="Avoid overly formal language. Use contractions where natural. Keep it friendly and approachable.",
        description="Friendly, conversational style"
    ),
    "formal": PromptElement(
        key="formal",
        name="Formal Tone",
        category="style",
        instruction="Use a formal, professional tone. Avoid contractions and colloquialisms.",
        adherence="Maintain professional language throughout. Use complete sentences and proper grammar.",
        description="Professional, business-appropriate style"
    ),
    "concise": PromptElement(
        key="concise",
        name="Concise",
        category="style",
        instruction="Be extremely concise. Remove all unnecessary words and get straight to the point.",
        adherence="Every sentence should be essential. Eliminate redundancy and wordiness.",
        description="Brief and to the point"
    ),
    "detailed": PromptElement(
        key="detailed",
        name="Detailed",
        category="style",
        instruction="Provide comprehensive detail. Expand on ideas and include relevant context.",
        adherence="Ensure thoroughness. Include examples and explanations where helpful.",
        description="Comprehensive and thorough"
    ),
    "technical": PromptElement(
        key="technical",
        name="Technical",
        category="style",
        instruction="Use precise technical language. Include specific terminology and avoid simplification.",
        adherence="Maintain technical accuracy. Use industry-standard terms and be specific.",
        description="Technical and precise language"
    ),
    "simple": PromptElement(
        key="simple",
        name="Simple Language",
        category="style",
        instruction="Use simple, accessible language. Explain concepts clearly without jargon.",
        adherence="Avoid technical terms unless necessary. Write for a general audience.",
        description="Clear and accessible for all readers"
    ),
}


# ===== GRAMMAR ELEMENTS =====
# These define grammar and structure preferences

GRAMMAR_ELEMENTS = {
    "add_punctuation": PromptElement(
        key="add_punctuation",
        name="Add Punctuation",
        category="grammar",
        instruction="Add proper punctuation and sentence breaks.",
        adherence="Use commas, periods, and other punctuation correctly. Create proper sentences.",
        description="Ensure correct punctuation"
    ),
    "add_paragraphs": PromptElement(
        key="add_paragraphs",
        name="Add Paragraphs",
        category="grammar",
        instruction="Add natural paragraph spacing for readability.",
        adherence="Group related ideas into paragraphs. Use blank lines between paragraphs.",
        description="Organize into readable paragraphs"
    ),
    "fix_grammar": PromptElement(
        key="fix_grammar",
        name="Fix Grammar",
        category="grammar",
        instruction="Correct any grammatical errors and awkward phrasing.",
        adherence="Ensure subject-verb agreement, proper tense usage, and clear sentence structure.",
        description="Correct grammatical errors"
    ),
    "remove_fillers": PromptElement(
        key="remove_fillers",
        name="Remove Filler Words",
        category="grammar",
        instruction="Remove filler words (um, uh, like, you know, etc.).",
        adherence="Eliminate verbal tics and hedging phrases while preserving meaning.",
        description="Strip out um, uh, like, etc."
    ),
}


# ===== ALL ELEMENTS =====
ALL_ELEMENTS = {**FORMAT_ELEMENTS, **STYLE_ELEMENTS, **GRAMMAR_ELEMENTS}


# ===== DEFAULT PROMPT STACKS =====
DEFAULT_STACKS = [
    PromptStack(
        name="Quick Email",
        elements=["email", "formal", "add_punctuation", "add_paragraphs", "remove_fillers"],
        description="Professional email with formal tone"
    ),
    PromptStack(
        name="Casual Todo",
        elements=["todo", "casual", "concise", "remove_fillers"],
        description="Quick to-do list with casual language"
    ),
    PromptStack(
        name="Meeting Minutes",
        elements=["meeting_notes", "formal", "detailed", "add_punctuation", "add_paragraphs"],
        description="Comprehensive meeting notes"
    ),
    PromptStack(
        name="Dev Instructions",
        elements=["dev_prompt", "technical", "detailed", "add_punctuation", "add_paragraphs"],
        description="Detailed technical development prompt"
    ),
    PromptStack(
        name="Quick Notes",
        elements=["bullet_points", "concise", "remove_fillers"],
        description="Fast bullet-point notes"
    ),
]


def build_prompt_from_elements(element_keys: List[str], user_instructions: str = "") -> str:
    """
    Build a cleanup prompt from a list of element keys.

    Args:
        element_keys: List of element keys to include
        user_instructions: Optional additional user instructions

    Returns:
        Complete cleanup prompt as string
    """
    lines = []

    # Group elements by category
    format_elements = []
    style_elements = []
    grammar_elements = []

    for key in element_keys:
        if key not in ALL_ELEMENTS:
            continue

        element = ALL_ELEMENTS[key]
        if element.category == "format":
            format_elements.append(element)
        elif element.category == "style":
            style_elements.append(element)
        elif element.category == "grammar":
            grammar_elements.append(element)

    # Build prompt layers
    lines.append("# Transcription Cleanup Instructions")
    lines.append("")

    # Layer 1: Grammar and structure
    if grammar_elements:
        lines.append("## Grammar & Structure")
        for elem in grammar_elements:
            lines.append(f"- {elem.instruction}")
        lines.append("")

    # Layer 2: Style
    if style_elements:
        lines.append("## Writing Style")
        for elem in style_elements:
            lines.append(f"- {elem.instruction}")
            if elem.adherence:
                lines.append(f"  {elem.adherence}")
        lines.append("")

    # Layer 3: Format
    if format_elements:
        lines.append("## Output Format")
        for elem in format_elements:
            lines.append(f"- {elem.instruction}")
            if elem.adherence:
                lines.append(f"  {elem.adherence}")
        lines.append("")

    # Layer 4: User instructions
    if user_instructions:
        lines.append("## Additional Instructions")
        lines.append(user_instructions)
        lines.append("")

    return "\n".join(lines)


def save_custom_stack(stack: PromptStack, config_dir: Path):
    """Save a custom prompt stack to disk."""
    stacks_file = config_dir / "prompt_stacks.json"

    # Load existing stacks
    if stacks_file.exists():
        with open(stacks_file) as f:
            data = json.load(f)
    else:
        data = {"stacks": []}

    # Add or update stack
    existing = next((s for s in data["stacks"] if s["name"] == stack.name), None)
    stack_dict = {"name": stack.name, "elements": stack.elements, "description": stack.description}

    if existing:
        data["stacks"] = [stack_dict if s["name"] == stack.name else s for s in data["stacks"]]
    else:
        data["stacks"].append(stack_dict)

    # Save
    with open(stacks_file, "w") as f:
        json.dump(data, f, indent=2)


def load_custom_stacks(config_dir: Path) -> List[PromptStack]:
    """Load custom prompt stacks from disk."""
    stacks_file = config_dir / "prompt_stacks.json"
    if not stacks_file.exists():
        return []

    with open(stacks_file) as f:
        data = json.load(f)

    return [
        PromptStack(name=s["name"], elements=s["elements"], description=s.get("description", ""))
        for s in data.get("stacks", [])
    ]


def get_all_stacks(config_dir: Path) -> List[PromptStack]:
    """Get all stacks (default + custom)."""
    return DEFAULT_STACKS + load_custom_stacks(config_dir)
