"""Configuration management for Voice Notepad V3."""

import json
import os
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import Optional


CONFIG_DIR = Path.home() / ".config" / "voice-notepad-v3"
CONFIG_FILE = CONFIG_DIR / "config.json"


# Available models per provider (model_id, display_name)
GEMINI_MODELS = [
    ("gemini-flash-latest", "Gemini Flash (Latest)"),
    ("gemini-2.5-flash", "Gemini 2.5 Flash"),
    ("gemini-2.5-flash-lite", "Gemini 2.5 Flash Lite (Budget)"),
    ("gemini-2.5-pro", "Gemini 2.5 Pro"),
    ("gemini-3-flash-preview", "Gemini 3 Flash (Preview)"),
]

OPENAI_MODELS = [
    ("gpt-4o-audio-preview", "GPT-4o Audio Preview"),
    ("gpt-4o-mini-audio-preview", "GPT-4o Mini Audio Preview (Budget)"),
    ("gpt-audio", "GPT Audio"),
    ("gpt-audio-mini", "GPT Audio Mini (Budget)"),
]

MISTRAL_MODELS = [
    ("voxtral-small-latest", "Voxtral Small (Latest)"),
    ("voxtral-mini-latest", "Voxtral Mini (Budget)"),
]

# OpenRouter models (using OpenAI-compatible API)
OPENROUTER_MODELS = [
    ("google/gemini-2.5-flash", "Gemini 2.5 Flash"),
    ("google/gemini-2.5-flash-lite", "Gemini 2.5 Flash Lite (Budget)"),
    ("google/gemini-2.0-flash-001", "Gemini 2.0 Flash"),
    ("google/gemini-2.0-flash-lite-001", "Gemini 2.0 Flash Lite (Budget)"),
    ("google/gemini-3-flash-preview", "Gemini 3 Flash (Preview)"),
    ("openai/gpt-4o-audio-preview", "GPT-4o Audio Preview"),
    ("mistralai/voxtral-small-24b-2507", "Voxtral Small 24B"),
]

# Standard and Budget model tiers per provider
# These define which models the quick-toggle buttons select
MODEL_TIERS = {
    "openrouter": {
        "standard": "google/gemini-2.5-flash",
        "budget": "google/gemini-2.5-flash-lite",
    },
    "gemini": {
        "standard": "gemini-2.5-flash",
        "budget": "gemini-2.5-flash-lite",
    },
    "openai": {
        "standard": "gpt-4o-audio-preview",
        "budget": "gpt-4o-mini-audio-preview",
    },
    "mistral": {
        "standard": "voxtral-small-latest",
        "budget": "voxtral-mini-latest",
    },
}


@dataclass
class Config:
    """Application configuration."""

    # API Keys
    gemini_api_key: str = ""
    openai_api_key: str = ""
    mistral_api_key: str = ""
    openrouter_api_key: str = ""

    # Selected model provider: "openrouter", "gemini", "openai", "mistral"
    selected_provider: str = "openrouter"

    # Model names per provider
    gemini_model: str = "gemini-flash-latest"
    openai_model: str = "gpt-4o-mini-audio-preview"
    mistral_model: str = "voxtral-small-latest"
    openrouter_model: str = "google/gemini-2.5-flash"

    # Audio settings
    # Legacy field - kept for backwards compatibility, migrated to preferred_mic_name
    selected_microphone: str = "pulse"
    sample_rate: int = 48000

    # Microphone preferences with nicknames
    preferred_mic_name: str = ""       # Device name (e.g., "Samson Q2U Microphone")
    preferred_mic_nickname: str = ""   # User nickname (e.g., "Q2U")
    fallback_mic_name: str = ""        # Fallback device name
    fallback_mic_nickname: str = ""    # Fallback nickname

    # UI settings
    window_width: int = 500
    window_height: int = 600
    start_minimized: bool = False

    # Hotkeys (global keyboard shortcuts)
    # Supported keys: F14-F20 (macro keys), F1-F12, or modifier combinations
    #
    # Four hotkey modes:
    # - "single_key": One key for everything - press to start, press again to stop & transcribe (RECOMMENDED)
    # - "tap_toggle": One key toggles start/stop and caches audio, separate key transcribes all cached audio
    # - "separate": Different keys for start, stop (discard), and stop & transcribe
    # - "ptt": Push-to-talk - hold key to record, release to stop
    hotkey_mode: str = "single_key"

    # Single Key mode (recommended - simplest workflow)
    hotkey_single_key: str = "f15"  # One key: press to start, press again to stop & transcribe

    # Tap-to-Toggle mode hotkeys
    hotkey_record_toggle: str = "f16"  # Toggle recording on/off (caches for append mode)
    hotkey_stop_and_transcribe: str = "f17"  # Transcribe all cached audio

    # Separate mode hotkeys
    hotkey_start: str = ""  # Start recording only
    hotkey_stop_discard: str = ""  # Stop and discard

    # PTT mode settings
    hotkey_ptt: str = ""  # Push-to-talk key (hold to record)
    ptt_release_action: str = "transcribe"  # "transcribe" or "discard" on key release

    # Storage settings
    store_audio: bool = False  # Archive audio recordings
    vad_enabled: bool = True   # Enable Voice Activity Detection (silence removal)

    # Audio feedback
    beep_on_record: bool = True  # Play beep when recording starts/stops
    beep_on_clipboard: bool = True  # Play beep when text copied to clipboard

    # Prompt customization options (checkboxes) - Layer 2 only
    # Foundation layer (fillers, punctuation, paragraph spacing) is always applied
    prompt_follow_instructions: bool = True  # Follow verbal instructions (don't include this, etc.)
    prompt_add_subheadings: bool = False     # Add ## headings for lengthy content
    prompt_markdown_formatting: bool = False  # Use bold, lists, etc.
    prompt_remove_unintentional_dialogue: bool = False  # Remove accidental dialogue from others
    prompt_enhancement_enabled: bool = False  # Enhance prompts for maximum AI effectiveness

    # Legacy field - kept for backwards compatibility but not used directly
    # The prompt is now built from the above boolean flags
    cleanup_prompt: str = ""

    # Format preset and formality settings
    format_preset: str = "general"      # general, email, todo, grocery, meeting_notes, bullet_points
    formality_level: str = "neutral"    # casual, neutral, professional
    verbosity_reduction: str = "none"   # none, minimum, short, medium, maximum

    # Writing sample for one-shot style copying
    writing_sample: str = ""

    # User profile settings (used when format_preset == "email" or similar)
    user_name: str = ""
    user_phone: str = ""

    # Business email settings
    business_email: str = ""
    business_signature: str = ""

    # Personal email settings
    personal_email: str = ""
    personal_signature: str = ""

    # Legacy fields (kept for backward compatibility)
    user_email: str = ""  # Migrated to business_email or personal_email
    email_signature: str = "Best regards"  # Migrated to business/personal signatures

    # NEW: Prompt library system
    output_format: str = "markdown"  # text, markdown, html, json, xml, yaml
    active_prompt_ids: list = field(default_factory=list)  # List of enabled prompt IDs

    # NEW: Prompt stack system (multi-select elements)
    prompt_stack_elements: list = field(default_factory=list)  # List of selected element keys
    use_prompt_stacks: bool = False  # Whether to use prompt stacks instead of legacy format system


def load_config() -> Config:
    """Load configuration from disk, or create default."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
            # Filter to only known fields to handle schema changes gracefully
            known_fields = {f.name for f in Config.__dataclass_fields__.values()}
            filtered_data = {k: v for k, v in data.items() if k in known_fields}
            config = Config(**filtered_data)

            # Migration: copy selected_microphone to preferred_mic_name if not set
            if config.selected_microphone and not config.preferred_mic_name:
                # Only migrate non-default values (not "pulse" or "default")
                if config.selected_microphone not in ("pulse", "default"):
                    config.preferred_mic_name = config.selected_microphone

            # Migration: move user_email to business_email if business_email is empty
            if config.user_email and not config.business_email:
                config.business_email = config.user_email

            # Migration: move email_signature to business_signature if business_signature is empty
            # and email_signature is not the default value
            if config.email_signature and not config.business_signature:
                if config.email_signature != "Best regards":
                    config.business_signature = config.email_signature

            return config
        except (json.JSONDecodeError, TypeError) as e:
            print(f"Warning: Could not load config: {e}")
            pass

    # Return default config
    return Config()


def save_config(config: Config) -> None:
    """Save configuration to disk."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    with open(CONFIG_FILE, "w") as f:
        json.dump(asdict(config), f, indent=2)


def load_env_keys(config: Config) -> Config:
    """Load API keys from environment variables if not already set."""
    if not config.gemini_api_key:
        config.gemini_api_key = os.environ.get("GEMINI_API_KEY", "")
    if not config.openai_api_key:
        config.openai_api_key = os.environ.get("OPENAI_API_KEY", "")
    if not config.mistral_api_key:
        config.mistral_api_key = os.environ.get("MISTRAL_API_KEY", "")
    if not config.openrouter_api_key:
        config.openrouter_api_key = os.environ.get("OPENROUTER_API_KEY", "")
    return config


# Foundation layer - ALWAYS APPLIED (mandatory, no verbatim option)
# This distinguishes the app from traditional speech-to-text
FOUNDATION_PROMPT_COMPONENTS = [
    "Remove filler words (um, uh, like, you know, so, well, etc.)",
    "Remove conversational verbal tics and hedging phrases (e.g., \"you know\", \"I mean\", \"kind of\", \"sort of\", \"basically\", \"actually\" when used as fillers)",
    "Remove standalone acknowledgments that don't add meaning (e.g., \"Okay.\" or \"Right.\" as their own sentences)",
    "Add proper punctuation and sentence structure",
    "Add natural paragraph spacing",
]

# Layer 2: Optional formatting enhancements (checkboxes)
# These enhance output without changing format adherence
# Each tuple: (config_field, instruction_text, description_for_ui)
OPTIONAL_PROMPT_COMPONENTS = [
    (
        "prompt_follow_instructions",
        "If the user makes any verbal instructions during the recording (such as \"don't include this\" or \"new paragraph\"), follow those instructions",
        "Follow verbal instructions (\"don't include this\"...)"
    ),
    (
        "prompt_add_subheadings",
        "Add markdown subheadings (## Heading) if it's a lengthy transcription with distinct sections",
        "Add subheadings for long transcriptions"
    ),
    (
        "prompt_markdown_formatting",
        "Use markdown formatting where appropriate (bold, lists, etc.)",
        "Use markdown formatting (bold, lists...)"
    ),
    (
        "prompt_remove_unintentional_dialogue",
        "If you detect dialogue that appears to be unintentional (e.g., someone else speaking to the user during the recording), only remove it if you can infer with high certainty that it was accidental. If uncertain, keep the dialogue in the transcription.",
        "Remove unintentional dialogue (if detectable)"
    ),
    (
        "prompt_enhancement_enabled",
        "If the output is a prompt for an AI assistant, optimize it for maximum effectiveness by: ensuring clarity and specificity, adding relevant context, structuring instructions logically, using imperative language, and following prompt engineering best practices. If the content is not a prompt, apply standard formatting only.",
        "Enhance AI prompts for effectiveness (prompt formats only)"
    ),
]


# Format preset templates with adherence instructions
# Each format: (format_instruction, adherence_instruction, category)
# Categories: "general", "work", "documentation", "creative", "lists"
FORMAT_TEMPLATES = {
    "general": {
        "instruction": "",
        "adherence": "",
        "category": "general",
        "description": "No specific formatting - general cleanup only",
    },
    "verbatim": {
        "instruction": "Preserve the original wording and structure as much as possible while applying only essential cleanup.",
        "adherence": "Keep the transcription very close to the original speech. Only remove obvious filler words, add basic punctuation, and create paragraph breaks. Do not rephrase, restructure, or add formatting beyond the absolute minimum needed for readability.",
        "category": "general",
        "description": "Minimal transformation - closest to verbatim transcription",
    },
    "email": {
        "instruction": "Format the output as an email with an appropriate greeting and sign-off.",
        "adherence": "Follow standard email formatting conventions. Include a clear subject line suggestion if the content is substantial. Use proper email etiquette.",
        "category": "work",
        "description": "Professional email format with greeting and sign-off",
    },
    "ai_prompt": {
        "instruction": "Format the output as clear, well-organized instructions for an AI assistant. Use imperative voice, organize tasks logically, and ensure instructions are unambiguous and actionable.",
        "adherence": "Strictly follow AI prompt engineering best practices: be specific, use clear command language, break complex tasks into numbered steps, and include context where needed.",
        "category": "work",
        "description": "General AI assistant instructions",
    },
    "dev_prompt": {
        "instruction": "Format the output as a development prompt for a software development AI assistant. Include technical requirements, implementation details, and expected outcomes. Use imperative voice and be explicit about technical constraints.",
        "adherence": "Follow software development prompt conventions: specify programming languages, frameworks, file paths if mentioned, testing requirements, and code quality expectations.",
        "category": "work",
        "description": "Software development instructions for AI",
    },
    "todo": {
        "instruction": "Format as a to-do list with checkbox items (- [ ] task). Use action verbs and be concise.",
        "adherence": "Each item must start with an action verb. Keep items specific and actionable. Group related items under headers if there are distinct categories.",
        "category": "lists",
        "description": "Checkbox to-do list format",
    },
    "grocery": {
        "instruction": "Format as a grocery list. Group items by category (produce, dairy, meat, pantry, etc.) if there are multiple items.",
        "adherence": "Always organize by store section categories. Use consistent item naming (e.g., quantities if mentioned).",
        "category": "lists",
        "description": "Categorized grocery shopping list",
    },
    "meeting_notes": {
        "instruction": "Format as meeting notes with clear sections, bullet points for key points, and a separate 'Action Items' section at the end.",
        "adherence": "Include: meeting date/time if mentioned, attendees if mentioned, discussion points as bullets, decisions made, and action items with assignees if specified.",
        "category": "work",
        "description": "Structured meeting notes with action items",
    },
    "bullet_points": {
        "instruction": "Format as concise bullet points. One idea per bullet.",
        "adherence": "Each bullet must be self-contained and parallel in structure. Use consistent formatting throughout.",
        "category": "lists",
        "description": "Simple bullet point list",
    },
    "readme": {
        "instruction": "Format as a README.md file for a software project. Include clear sections for project description, installation, usage, and other relevant information.",
        "adherence": "Follow GitHub README conventions: use markdown headers (# ## ###), include code blocks with language tags, format installation commands as code blocks, and structure information logically.",
        "category": "documentation",
        "description": "GitHub-style README documentation",
    },
    "tech_docs": {
        "instruction": "Format as technical documentation with clear sections, code examples where appropriate, and structured explanations of technical concepts.",
        "adherence": "Use formal technical writing style. Include clear hierarchical headers, code formatting for technical terms, and structured examples. Define technical terms on first use.",
        "category": "documentation",
        "description": "Technical documentation and guides",
    },
    "reference_doc": {
        "instruction": "Format as a reference document with clear categorization, examples, and quick-lookup structure. Prioritize clarity and accessibility.",
        "adherence": "Organize information for quick reference. Use consistent formatting for similar items. Include examples where helpful. Use tables or structured lists for parameter references or option lists.",
        "category": "documentation",
        "description": "Reference material and quick-lookup docs",
    },
    "blog_outline": {
        "instruction": "Format as a blog post outline with main sections, subsections, and key points to cover under each. Include suggested introduction and conclusion hooks.",
        "adherence": "Structure as a hierarchical outline using markdown headers. Include [INTRO], [BODY], and [CONCLUSION] section markers. Each point should be brief but clear about the content to be written.",
        "category": "creative",
        "description": "Blog post structure and outline",
    },
    "blog_notes": {
        "instruction": "Format as raw notes and ideas for a blog post. Capture key points, quotes, statistics, links, or thoughts mentioned - doesn't need to be polished prose.",
        "adherence": "Preserve all ideas mentioned even if scattered. Use bullet points for discrete thoughts. Mark any action items (e.g., 'RESEARCH: [topic]', 'FIND: [statistic]') if mentioned.",
        "category": "creative",
        "description": "Unstructured blog research notes",
    },
    # NEW FORMATS - Business & Technical
    "bug_report": {
        "instruction": "Format as a software bug report with clear sections: Summary, Steps to Reproduce, Expected Behavior, Actual Behavior, Environment Details, and Additional Context.",
        "adherence": "Use technical precision. Include all mentioned error messages verbatim. Structure reproduction steps as numbered list. Categorize severity if mentioned.",
        "category": "work",
        "description": "Software bug report with technical details",
    },
    "internal_memo": {
        "instruction": "Format as an internal company memo with: TO, FROM, DATE, SUBJECT, and body with clear sections and action items if applicable.",
        "adherence": "Use professional but direct tone. Keep concise. Highlight key decisions or action items. Use proper memo formatting conventions.",
        "category": "work",
        "description": "Internal company memorandum",
    },
    "sop": {
        "instruction": "Format as a Standard Operating Procedure (SOP) with: Purpose, Scope, Procedure (numbered steps), Safety/Compliance notes if relevant, and References if mentioned.",
        "adherence": "Use imperative voice for procedure steps. Each step must be clear and actionable. Include warnings or cautions if safety is mentioned. Maintain consistent step numbering.",
        "category": "documentation",
        "description": "Standard Operating Procedure document",
    },
    "system_prompt": {
        "instruction": "Format as a system prompt for an AI assistant. Write in third-person, defining the assistant's role, capabilities, constraints, and behavioral guidelines. Use declarative statements about what the assistant 'is' or 'does'.",
        "adherence": "Use third-person perspective (e.g., 'You are...', 'The assistant should...'). Define role clearly. Specify constraints and boundaries. Include behavioral guidelines. Be comprehensive but concise. Avoid user-facing language.",
        "category": "work",
        "description": "AI system prompt (third-person, defining behavior)",
    },
    "image_generation_prompt": {
        "instruction": "Format as a detailed image generation prompt suitable for AI image generators (Stable Diffusion, DALL-E, Midjourney, etc.). Include: subject description, style/aesthetic, composition, lighting, camera angle, colors/mood, quality markers, and negative prompt suggestions if applicable.",
        "adherence": "Use descriptive, comma-separated keywords and phrases. Be specific about visual details. Include style modifiers (photorealistic, oil painting, anime, etc.). Specify technical aspects (4K, detailed, sharp focus). Structure as: main subject, setting, style, technical quality. Add [Negative prompt: ...] section for things to avoid if mentioned.",
        "category": "work",
        "description": "Image generation prompt for AI art tools",
    },
    "api_doc": {
        "instruction": "Format as API documentation with endpoint details, parameters, request/response examples, and usage notes.",
        "adherence": "Use consistent structure for each endpoint. Include HTTP methods, URL patterns, parameter tables, example requests/responses in code blocks. Note authentication requirements.",
        "category": "documentation",
        "description": "API endpoint documentation",
    },
    "changelog": {
        "instruction": "Format as a software changelog with version numbers, release dates, and categorized changes (Added, Changed, Fixed, Removed, Deprecated).",
        "adherence": "Follow Keep a Changelog format. Use markdown headers for versions. Group changes by category. Use bullet points. Include dates in YYYY-MM-DD format.",
        "category": "documentation",
        "description": "Software release changelog",
    },
    "project_plan": {
        "instruction": "Format as a project plan with: Overview, Goals/Objectives, Timeline/Milestones, Resources, Deliverables, and Risks if mentioned.",
        "adherence": "Use clear hierarchical structure. Present timeline as table or structured list. Highlight critical milestones. Be specific about deliverables and success criteria.",
        "category": "work",
        "description": "Project planning document",
    },
    # Content Creation
    "social_post": {
        "instruction": "Format as a social media post optimized for engagement. Keep concise, use line breaks for readability, include hashtags if mentioned, and maintain conversational tone.",
        "adherence": "Respect platform character limits if specified. Use emoji strategically if mentioned. Structure for scanability. Include call-to-action if present.",
        "category": "creative",
        "description": "Social media post (Twitter, LinkedIn, etc.)",
    },
    "press_release": {
        "instruction": "Format as a press release with: compelling headline, dateline, lead paragraph (who/what/when/where/why), body paragraphs, boilerplate, and media contact.",
        "adherence": "Follow AP style. Front-load most newsworthy information. Use quotations if mentioned. Maintain objective tone. Include standard press release structure.",
        "category": "work",
        "description": "Corporate press release",
    },
    "newsletter": {
        "instruction": "Format as an email newsletter with: engaging subject line, greeting, main content sections with headers, and clear call-to-action.",
        "adherence": "Use scannable sections with headers. Include brief intro paragraph. Maintain conversational but professional tone. End with clear CTA and sign-off.",
        "category": "creative",
        "description": "Email newsletter content",
    },
    # Fun/Experimental
    "shakespearean": {
        "instruction": "Rewrite the transcription in Shakespearean English style, using Early Modern English vocabulary, thou/thee pronouns, and poetic phrasing while preserving the core meaning.",
        "adherence": "Use Elizabethan vocabulary and syntax. Apply thee/thou/thy appropriately. Add poetic flourishes. Maintain iambic rhythm where natural. Preserve original meaning despite stylistic transformation.",
        "category": "experimental",
        "description": "Shakespearean English style (fun)",
    },
    "medieval": {
        "instruction": "Rewrite in Medieval/Middle English style as if written by a medieval scribe or chronicler, using archaic vocabulary and formal historical narrative style.",
        "adherence": "Use medieval English vocabulary (e.g., 'hath', 'doth', 'verily', 'forsooth'). Adopt formal chronicle-style narration. Add period-appropriate phrasing. Maintain clarity despite archaic style.",
        "category": "experimental",
        "description": "Medieval English style (fun)",
    },
    "pirate_speak": {
        "instruction": "Rewrite in pirate vernacular with nautical terms, 'arr', 'me hearty', and swashbuckling language while keeping the content recognizable.",
        "adherence": "Use pirate slang ('arr', 'matey', 'scallywag', etc.). Add nautical metaphors. Replace pronouns with pirate equivalents ('me' instead of 'my'). Keep energetic and playful tone.",
        "category": "experimental",
        "description": "Pirate speak style (fun)",
    },
    "formal_academic": {
        "instruction": "Rewrite in formal academic style suitable for scholarly publication, with proper citations structure if sources are mentioned, elevated vocabulary, and passive voice where appropriate.",
        "adherence": "Use formal academic register. Employ technical vocabulary. Structure arguments logically. Use passive voice judiciously. Add 'According to...' structures if sources mentioned. Maintain objectivity.",
        "category": "experimental",
        "description": "Formal academic writing style",
    },
}

# Display names for format presets (for UI)
FORMAT_DISPLAY_NAMES = {
    "general": "General",
    "verbatim": "Verbatim",
    "email": "Email",
    "ai_prompt": "AI Prompt",
    "dev_prompt": "Development Prompt",
    "system_prompt": "System Prompt",
    "image_generation_prompt": "Image Generation Prompt",
    "todo": "To-Do List",
    "grocery": "Grocery List",
    "meeting_notes": "Meeting Notes",
    "bullet_points": "Bullet Points",
    "readme": "README",
    "tech_docs": "Technical Documentation",
    "reference_doc": "Reference Doc",
    "api_doc": "API Documentation",
    "sop": "SOP (Standard Operating Procedure)",
    "changelog": "Changelog",
    "blog_outline": "Blog Outline",
    "blog_notes": "Blog Notes",
    "bug_report": "Bug Report",
    "internal_memo": "Internal Memo",
    "project_plan": "Project Plan",
    "social_post": "Social Media Post",
    "press_release": "Press Release",
    "newsletter": "Newsletter",
    "shakespearean": "Shakespearean Style",
    "medieval": "Medieval Style",
    "pirate_speak": "Pirate Speak",
    "formal_academic": "Formal Academic",
}

# Format categories for organization in Formats tab
FORMAT_CATEGORIES = {
    "general": "General",
    "work": "Work & Productivity",
    "documentation": "Documentation",
    "creative": "Creative & Content",
    "lists": "Lists & Planning",
    "experimental": "Fun & Experimental",
}

# Formality level templates
FORMALITY_TEMPLATES = {
    "casual": "Use a casual, friendly, conversational tone.",
    "neutral": "",  # No tone modifier
    "professional": "Use a professional, formal tone appropriate for business communication.",
}

# Display names for formality levels (for UI)
FORMALITY_DISPLAY_NAMES = {
    "casual": "Casual",
    "neutral": "Neutral",
    "professional": "Professional",
}

# Verbosity reduction templates
VERBOSITY_TEMPLATES = {
    "none": "",  # No verbosity reduction
    "minimum": "Make the transcription slightly more concise while retaining all key information and context.",
    "short": "Make the transcription concise and succinct, focusing on the main points while preserving important details.",
    "medium": "Apply medium verbosity reduction: make the transcription significantly more concise, keeping only essential information and removing redundant details.",
    "maximum": "Apply maximum verbosity reduction: make the transcription as concise as possible, keeping only the core message and key points. Be extremely succinct.",
}

# Display names for verbosity levels (for UI)
VERBOSITY_DISPLAY_NAMES = {
    "none": "None",
    "minimum": "Minimum",
    "short": "Short",
    "medium": "Medium",
    "maximum": "Maximum",
}

# Common email sign-offs for dropdown
EMAIL_SIGNOFFS = [
    "Best regards",
    "Best",
    "Thanks",
    "Thank you",
    "Cheers",
    "Sincerely",
    "Regards",
    "Warm regards",
    "Kind regards",
]


def build_cleanup_prompt(config: Config, use_prompt_library: bool = False) -> str:
    """Build the cleanup prompt using the 3-layer architecture.

    Args:
        config: Configuration object
        use_prompt_library: If True, use the new prompt library system from database.
                           If False, use legacy hardcoded prompts (default for backward compat).

    Layer 1 (Foundation): Always applied - basic rewriting (filler removal, punctuation, paragraphs)
    Layer 2 (Optional): User-selected enhancements (subheadings, markdown, etc.)
    Layer 3 (Format + Style): Format-specific instructions, formality, verbosity, writing sample
    """
    # NEW: Use prompt library if enabled
    if use_prompt_library:
        return _build_prompt_from_library(config)

    # NEW: Use prompt stacks if enabled
    if config.use_prompt_stacks and config.prompt_stack_elements:
        try:
            from .prompt_elements import build_prompt_from_elements
        except ImportError:
            from prompt_elements import build_prompt_from_elements
        return build_prompt_from_elements(config.prompt_stack_elements)

    # LEGACY: Original hardcoded system (kept for backward compatibility)
    lines = ["Your task is to provide a cleaned transcription of the audio recorded by the user."]

    # ===== LAYER 1: FOUNDATION (ALWAYS APPLIED) =====
    lines.append("\n## Foundation Cleanup (Always Applied)")
    for instruction in FOUNDATION_PROMPT_COMPONENTS:
        lines.append(f"- {instruction}")

    # ===== LAYER 2: OPTIONAL ENHANCEMENTS =====
    optional_instructions = []
    for field_name, instruction, _ in OPTIONAL_PROMPT_COMPONENTS:
        if getattr(config, field_name, False):
            optional_instructions.append(instruction)

    if optional_instructions:
        lines.append("\n## Additional Formatting")
        for instruction in optional_instructions:
            lines.append(f"- {instruction}")

    # ===== LAYER 3: FORMAT + STYLE =====
    # Format-specific instructions
    format_data = FORMAT_TEMPLATES.get(config.format_preset, {})
    if isinstance(format_data, dict):
        format_instruction = format_data.get("instruction", "")
        format_adherence = format_data.get("adherence", "")

        if format_instruction or format_adherence:
            lines.append("\n## Format Requirements")
            if format_instruction:
                lines.append(f"- {format_instruction}")
            if format_adherence:
                lines.append(f"- {format_adherence}")
    elif isinstance(format_data, str):
        # Backwards compatibility for old format
        if format_data:
            lines.append("\n## Format Requirements")
            lines.append(f"- {format_data}")

    # Formality/tone and verbosity
    style_instructions = []
    formality_template = FORMALITY_TEMPLATES.get(config.formality_level, "")
    if formality_template:
        style_instructions.append(formality_template)

    verbosity_template = VERBOSITY_TEMPLATES.get(config.verbosity_reduction, "")
    if verbosity_template:
        style_instructions.append(verbosity_template)

    if style_instructions:
        lines.append("\n## Style & Tone")
        for instruction in style_instructions:
            lines.append(f"- {instruction}")

    # Writing sample reference
    if config.writing_sample and config.writing_sample.strip():
        lines.append("\n## Writing Style Reference")
        lines.append("The user has provided the following writing sample as a reference for tone, style, and structure. "
                    "Use this as guidance for the output style:")
        lines.append(f"\n{config.writing_sample.strip()}\n")

    # User-specific parameters (e.g., email signature)
    if config.format_preset == "email":
        # Use business email/signature by default, fall back to personal, then legacy fields
        sender_email = config.business_email or config.personal_email or config.user_email
        sender_signature = config.business_signature or config.personal_signature

        if config.user_name or sender_email or config.user_phone:
            lines.append("\n## User Profile")
            profile_parts = []
            if config.user_name:
                profile_parts.append(f"Name: {config.user_name}")
            if sender_email:
                profile_parts.append(f"Email: {sender_email}")
            if config.user_phone:
                profile_parts.append(f"Phone: {config.user_phone}")

            profile_info = ", ".join(profile_parts)
            lines.append(f"- Draft the email from the following person: {profile_info}")

        if sender_signature:
            lines.append(f"- End the email with the following signature:\n\n{sender_signature}")
        elif config.user_name:
            # Fallback to simple sign-off if no signature configured
            sign_off = config.email_signature or "Best regards"
            lines.append(f"- End the email with the sign-off: \"{sign_off},\" followed by the sender's name: \"{config.user_name}\"")

    # Final instruction
    lines.append("\n## Output")
    lines.append("- Output ONLY the cleaned transcription in markdown format, no commentary or preamble")

    return "\n".join(lines)


def _build_prompt_from_library(config: Config) -> str:
    """Build prompt using the new prompt library system.

    This function:
    1. Loads enabled prompts from the database
    2. Adds output format instruction
    3. Applies format preset, formality, verbosity (legacy settings)
    4. Concatenates everything into a complete prompt
    """
    from database_mongo import get_db
    from prompt_library import (
        PromptTemplate,
        PromptCategory,
        OutputFormat,
        build_prompt_from_templates,
        detect_conflicts,
        validate_requirements,
    )

    db = get_db()

    # Get all enabled prompts from database
    enabled_prompt_docs = db.get_enabled_prompts()

    # Convert to PromptTemplate objects
    prompts = [PromptTemplate.from_dict(doc) for doc in enabled_prompt_docs]

    # Foundation prompts are ALWAYS enabled
    foundation_prompts = [p for p in prompts if p.category == PromptCategory.FOUNDATION]

    # User-selected prompts (from config.active_prompt_ids if set, otherwise all enabled)
    if config.active_prompt_ids:
        active_ids = set(config.active_prompt_ids)
        user_prompts = [p for p in prompts if p.id in active_ids and p.category != PromptCategory.FOUNDATION]
    else:
        # Use all enabled non-foundation prompts
        user_prompts = [p for p in prompts if p.category != PromptCategory.FOUNDATION]

    all_prompts = foundation_prompts + user_prompts

    # Detect conflicts (warn user in future UI)
    conflicts = detect_conflicts(all_prompts)
    if conflicts:
        print(f"Warning: Detected {len(conflicts)} prompt conflicts")

    # Validate requirements
    missing = validate_requirements(all_prompts)
    if missing:
        print(f"Warning: {len(missing)} prompts have missing requirements")

    # Get output format
    try:
        output_format = OutputFormat(config.output_format)
    except ValueError:
        output_format = OutputFormat.MARKDOWN  # Default

    # Build base prompt from templates
    lines = ["Your task is to provide a cleaned transcription of the audio recorded by the user."]
    lines.append("")
    lines.append(build_prompt_from_templates(all_prompts, output_format))

    # ===== ADD LEGACY FORMAT PRESET SUPPORT =====
    # (Keep format presets working during transition)
    format_data = FORMAT_TEMPLATES.get(config.format_preset, {})
    if isinstance(format_data, dict):
        format_instruction = format_data.get("instruction", "")
        format_adherence = format_data.get("adherence", "")

        if format_instruction or format_adherence:
            lines.append("\n## Format Preset")
            if format_instruction:
                lines.append(f"- {format_instruction}")
            if format_adherence:
                lines.append(f"- {format_adherence}")

    # Formality/tone and verbosity (legacy settings still work)
    style_instructions = []
    formality_template = FORMALITY_TEMPLATES.get(config.formality_level, "")
    if formality_template:
        style_instructions.append(formality_template)

    verbosity_template = VERBOSITY_TEMPLATES.get(config.verbosity_reduction, "")
    if verbosity_template:
        style_instructions.append(verbosity_template)

    if style_instructions:
        lines.append("\n## Style & Tone")
        for instruction in style_instructions:
            lines.append(f"- {instruction}")

    # Writing sample reference
    if config.writing_sample and config.writing_sample.strip():
        lines.append("\n## Writing Style Reference")
        lines.append("The user has provided the following writing sample as a reference for tone, style, and structure. "
                    "Use this as guidance for the output style:")
        lines.append(f"\n{config.writing_sample.strip()}\n")

    # User-specific parameters (e.g., email signature)
    if config.format_preset == "email":
        # Use business email/signature by default, fall back to personal, then legacy fields
        sender_email = config.business_email or config.personal_email or config.user_email
        sender_signature = config.business_signature or config.personal_signature

        if config.user_name or sender_email or config.user_phone:
            lines.append("\n## User Profile")
            profile_parts = []
            if config.user_name:
                profile_parts.append(f"Name: {config.user_name}")
            if sender_email:
                profile_parts.append(f"Email: {sender_email}")
            if config.user_phone:
                profile_parts.append(f"Phone: {config.user_phone}")

            profile_info = ", ".join(profile_parts)
            lines.append(f"- Draft the email from the following person: {profile_info}")

        if sender_signature:
            lines.append(f"- End the email with the following signature:\n\n{sender_signature}")
        elif config.user_name:
            # Fallback to simple sign-off if no signature configured
            sign_off = config.email_signature or "Best regards"
            lines.append(f"- End the email with the sign-off: \"{sign_off},\" followed by the sender's name: \"{config.user_name}\"")

    # Final instruction
    lines.append("\n## Output")
    lines.append("- Output ONLY the cleaned transcription, no commentary or preamble")

    return "\n".join(lines)
