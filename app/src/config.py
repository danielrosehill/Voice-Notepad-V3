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
    quiet_mode: bool = False  # Suppress all beeps (overrides above settings when True)

    # Text injection (auto-paste after clipboard copy)
    auto_paste: bool = False  # Automatically paste (Ctrl+V) after copying to clipboard

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

    # Favorite formats for quick buttons in main UI
    favorite_formats: list = field(default_factory=lambda: ["general", "email", "todo", "ai_prompt"])


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


# =============================================================================
# FOUNDATION CLEANUP PROMPT
# =============================================================================
# Always applied to every transcription. This is the core cleanup that
# distinguishes Voice Notepad from traditional speech-to-text.
#
# This is single-pass dictation processing: audio in, edited text out.
# The output should reflect what the speaker meant to communicate, not merely
# what sounds were produced.
#
# Organized into sections so individual components can be modified if needed.
# See CLAUDE.md "Foundation Cleanup Prompt" section for full documentation.
# =============================================================================

FOUNDATION_PROMPT_SECTIONS = {
    # Section 1: Task definition and framing
    "task_definition": {
        "heading": "Task Definition",
        "instructions": [
            "You are an intelligent transcription editor. Transform the audio into polished, publication-ready text—not a verbatim transcript.",
            "Apply intelligent editing, removing the artifacts of natural speech while preserving the speaker's intended meaning.",
            "Natural speech contains false starts, filler words, self-corrections, and thinking pauses that serve no purpose in written text. Produce clean, readable prose that captures the speaker's intent.",
            "Output only the transformed text. Do not include preamble, commentary, or explanations about your edits. Do not wrap the output in quotes or code blocks.",
        ],
    },

    # Section 2: User personalization
    "user_details": {
        "heading": "User Details",
        "instructions": [
            "The user's name is Daniel. Use this for signatures where appropriate (e.g., emails).",
            "The system prompt may include additional personalization elements (email address, signature). Inject these where appropriate into templates.",
        ],
    },

    # Section 3: Background audio filtering
    "background_audio": {
        "heading": "Background Audio",
        "instructions": [
            "Infer and exclude audio content not intended for transcription: greetings to other people, conversations with visitors, handling deliveries, background interruptions, side conversations, or other interactions clearly separate from the main dictation.",
            "Include only content that represents the user's intended message.",
        ],
    },

    # Section 4: Filler words
    "filler_words": {
        "heading": "Filler Words",
        "instructions": [
            "Remove filler words and verbal hesitations that add no meaning: \"um\", \"uh\", \"er\", \"ah\", \"like\" (when used as filler), \"you know\", \"I mean\", \"basically\", \"actually\" (when used as filler), \"sort of\", \"kind of\" (when hedging rather than describing), \"well\" (at sentence beginnings), and similar verbal padding.",
            "Preserve these words only when they carry semantic meaning in context.",
        ],
    },

    # Section 5: Repetitions
    "repetitions": {
        "heading": "Repetitions",
        "instructions": [
            "Identify and remove redundant repetitions where the user expresses the same thought, idea, or instruction multiple times.",
            "If the user explicitly states they want to remove or not include something mentioned earlier, honor that instruction.",
            "Consolidate repeated concepts into a single, clear expression while preserving the user's intended meaning.",
        ],
    },

    # Section 6: Meta instructions (including verbal directives)
    "meta_instructions": {
        "heading": "Meta Instructions",
        "instructions": [
            "When the user provides verbal instructions to modify the transcript (such as \"scratch that\", \"don't include that in the transcript\", \"ignore what I just said\", \"new paragraph\", or similar directives), act upon these instructions by removing or modifying the content as directed.",
            "Do not include these meta-instructions themselves in the final output.",
        ],
    },

    # Section 7: Spelling clarifications
    "spelling_clarifications": {
        "heading": "Spelling Clarifications",
        "instructions": [
            "The user might spell out a word to avoid mistranscription for infrequently encountered words. Example: \"We want to use Zod to resolve TypeScript errors. Zod is spelled Z-O-D.\"",
            "Do not include the spelling instruction. Simply ensure the word is spelled as requested. Example output: \"We want to use Zod to resolve TypeScript errors.\"",
        ],
    },

    # Section 8: Grammar and typos
    "grammar_and_typos": {
        "heading": "Grammar & Typos",
        "instructions": [
            "Correct spelling errors, typos, and grammatical mistakes.",
            "Apply standard grammar rules for subject-verb agreement, tense consistency, and proper word usage.",
            "Fix homophones used incorrectly (their/there/they're, your/you're) and correct common mistranscriptions where context makes the intended word clear.",
            "Fix minor grammatical errors that occur naturally in speech (e.g., wrong pluralization like \"into the option\" → \"into the options\").",
        ],
    },

    # Section 9: Punctuation and structure
    "punctuation": {
        "heading": "Punctuation",
        "instructions": [
            "Add appropriate punctuation including periods, commas, colons, semicolons, question marks, and quotation marks where contextually appropriate.",
            "Break text into logical paragraphs based on topic shifts and natural thought boundaries.",
            "Ensure sentences are properly capitalized.",
        ],
    },

    # Section 10: Format detection
    "format_detection": {
        "heading": "Format Detection",
        "instructions": [
            "If you can infer that the transcript was intended to be formatted in a specific and commonly used format (such as an email, to-do list, or meeting notes), ensure the text conforms to the expected format.",
            "Match language tone to detected context: business emails should use professional language, casual notes can be informal.",
        ],
    },

    # Section 11: Clarity (optional tightening)
    "clarity": {
        "heading": "Clarity",
        "instructions": [
            "Make language more direct and concise—tighten rambling sentences without removing information.",
            "Clarify confusing or illogical phrasing while preserving all details and original meaning.",
        ],
    },

    # Section 12: Subheadings for structure
    "subheadings": {
        "heading": "Subheadings",
        "instructions": [
            "For lengthy transcriptions with distinct sections or topics, add markdown subheadings (## Heading) to organize the content.",
            "Only add subheadings when the content naturally breaks into separate sections; do not force structure on short or single-topic transcriptions.",
        ],
    },

    # Section 13: Markdown formatting
    "markdown_formatting": {
        "heading": "Markdown Formatting",
        "instructions": [
            "Use markdown formatting where appropriate to enhance readability: **bold** for emphasis, *italics* for terms or titles, bullet lists for multiple items, numbered lists for sequences or steps.",
            "Apply formatting judiciously based on content type—technical content benefits from code formatting, lists benefit from bullet points, important terms benefit from emphasis.",
        ],
    },
}


def get_foundation_prompt_list() -> list:
    """Get all foundation prompt instructions as a flat list.

    Returns all enabled foundation components for backward compatibility
    with code that expects FOUNDATION_PROMPT_COMPONENTS as a list.
    """
    instructions = []
    for section in FOUNDATION_PROMPT_SECTIONS.values():
        instructions.extend(section["instructions"])
    return instructions


# Backward compatibility: keep FOUNDATION_PROMPT_COMPONENTS as a list
FOUNDATION_PROMPT_COMPONENTS = get_foundation_prompt_list()

# Layer 2: Optional formatting enhancements (checkboxes)
# These enhance output without changing format adherence
# Note: Follow instructions, subheadings, and markdown formatting have been moved
# to the foundation prompt (always applied) as of v1.8
# Each tuple: (config_field, instruction_text, description_for_ui)
OPTIONAL_PROMPT_COMPONENTS = [
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
# Categories align with PromptConfigCategory in prompt_library.py:
#   foundational, stylistic, prompts, todo_lists, blog, documentation, work, creative, experimental
FORMAT_TEMPLATES = {
    # ==========================================================================
    # FOUNDATIONAL - Core transcription modes
    # ==========================================================================
    "general": {
        "instruction": "",
        "adherence": "",
        "category": "foundational",
        "description": "No specific formatting - general cleanup only",
    },
    "verbatim": {
        "instruction": "Preserve the original wording and structure as much as possible while applying only essential cleanup.",
        "adherence": "Keep the transcription very close to the original speech. Only remove obvious filler words, add basic punctuation, and create paragraph breaks. Do not rephrase, restructure, or add formatting beyond the absolute minimum needed for readability.",
        "category": "foundational",
        "description": "Minimal transformation - closest to verbatim transcription",
    },
    "brief": {
        "instruction": "Be as brief as possible. Condense the content to its essential core message with maximum conciseness.",
        "adherence": "Ruthlessly cut unnecessary words, qualifiers, and redundant phrases. Prefer short sentences. Eliminate preamble and filler. Every word must earn its place. Aim for the minimum viable length while preserving meaning.",
        "category": "foundational",
        "description": "Maximum conciseness - as brief as possible",
    },
    "quick_note": {
        "instruction": "Format as a quick personal note. Minimal formatting, just capture the thought clearly.",
        "adherence": "Keep it informal and quick. No headers, no elaborate structure. Just the thought, clearly expressed. Suitable for jotting down ideas or reminders.",
        "category": "foundational",
        "description": "Quick personal note - minimal formatting",
    },

    # ==========================================================================
    # STYLISTIC - Writing styles and formats
    # ==========================================================================
    "email": {
        "instruction": "Format the output as an email with an appropriate greeting and sign-off.",
        "adherence": "Follow standard email formatting conventions. Include a clear subject line suggestion if the content is substantial. Use proper email etiquette.",
        "category": "stylistic",
        "description": "Professional email format with greeting and sign-off",
    },
    "meeting_notes": {
        "instruction": "Format as meeting notes with clear sections, bullet points for key points, and a separate 'Action Items' section at the end.",
        "adherence": "Include: meeting date/time if mentioned, attendees if mentioned, discussion points as bullets, decisions made, and action items with assignees if specified.",
        "category": "stylistic",
        "description": "Structured meeting notes with action items",
    },
    "bullet_points": {
        "instruction": "Format as concise bullet points. One idea per bullet.",
        "adherence": "Each bullet must be self-contained and parallel in structure. Use consistent formatting throughout.",
        "category": "stylistic",
        "description": "Simple bullet point list",
    },
    "internal_memo": {
        "instruction": "Format as an internal company memo with: TO, FROM, DATE, SUBJECT, and body with clear sections and action items if applicable.",
        "adherence": "Use professional but direct tone. Keep concise. Highlight key decisions or action items. Use proper memo formatting conventions.",
        "category": "stylistic",
        "description": "Internal company memorandum",
    },
    "press_release": {
        "instruction": "Format as a press release with: compelling headline, dateline, lead paragraph (who/what/when/where/why), body paragraphs, boilerplate, and media contact.",
        "adherence": "Follow AP style. Front-load most newsworthy information. Use quotations if mentioned. Maintain objective tone. Include standard press release structure.",
        "category": "stylistic",
        "description": "Corporate press release",
    },
    "newsletter": {
        "instruction": "Format as an email newsletter with: engaging subject line, greeting, main content sections with headers, and clear call-to-action.",
        "adherence": "Use scannable sections with headers. Include brief intro paragraph. Maintain conversational but professional tone. End with clear CTA and sign-off.",
        "category": "stylistic",
        "description": "Email newsletter content",
    },
    "persuasive": {
        "instruction": "Write with persuasive language designed to convince or influence the reader. Use rhetorical techniques, emotional appeals, and compelling arguments.",
        "adherence": "Employ persuasive techniques: strong opening hook, clear value proposition, social proof if available, address potential objections, use active voice, include call-to-action. Balance logic with emotional appeal. Be assertive but not pushy.",
        "category": "stylistic",
        "description": "Persuasive writing to convince or influence",
    },
    "slack_message": {
        "instruction": "Format as a workplace chat message (Slack/Teams style). Keep it conversational, direct, and appropriately informal for workplace communication.",
        "adherence": "Be concise and scannable. Use line breaks for readability. Emoji are okay if tone suits. Get to the point quickly. Can use bullet points for multiple items. Maintain professional-casual balance.",
        "category": "stylistic",
        "description": "Workplace chat message (Slack/Teams)",
    },

    # ==========================================================================
    # PROMPTS - AI prompt formats
    # ==========================================================================
    "ai_prompt": {
        "instruction": "Format the output as clear, well-organized instructions for an AI assistant. Use imperative voice, organize tasks logically, and ensure instructions are unambiguous and actionable.",
        "adherence": "Strictly follow AI prompt engineering best practices: be specific, use clear command language, break complex tasks into numbered steps, and include context where needed.",
        "category": "prompts",
        "description": "General AI assistant instructions",
    },
    "dev_prompt": {
        "instruction": "Format the output as a development prompt for a software development AI assistant. Include technical requirements, implementation details, and expected outcomes. Use imperative voice and be explicit about technical constraints.",
        "adherence": "Follow software development prompt conventions: specify programming languages, frameworks, file paths if mentioned, testing requirements, and code quality expectations.",
        "category": "prompts",
        "description": "Software development instructions for AI",
    },
    "system_prompt": {
        "instruction": "Format as a system prompt for an AI assistant. Write in second-person, addressing the AI directly. Define its role, capabilities, constraints, and behavioral guidelines using 'You are...' and 'You should...' statements.",
        "adherence": "Always use second-person perspective addressing the AI directly (e.g., 'You are a helpful assistant', 'You should respond concisely'). Never use third-person ('The assistant should...'). Define role clearly upfront. Specify constraints and boundaries. Include behavioral guidelines. Be comprehensive but concise.",
        "category": "prompts",
        "description": "AI system prompt (second-person, 'You are...' style)",
    },
    "image_generation_prompt": {
        "instruction": "Format as a detailed image generation prompt suitable for AI image generators (Stable Diffusion, DALL-E, Midjourney, etc.). Include: subject description, style/aesthetic, composition, lighting, camera angle, colors/mood, quality markers, and negative prompt suggestions if applicable.",
        "adherence": "Use descriptive, comma-separated keywords and phrases. Be specific about visual details. Include style modifiers (photorealistic, oil painting, anime, etc.). Specify technical aspects (4K, detailed, sharp focus). Structure as: main subject, setting, style, technical quality. Add [Negative prompt: ...] section for things to avoid if mentioned.",
        "category": "prompts",
        "description": "Image generation prompt for AI art tools",
    },

    # ==========================================================================
    # TODO_LISTS - List formats
    # ==========================================================================
    "todo": {
        "instruction": "Format as a to-do list with checkbox items (- [ ] task). Use action verbs and be concise.",
        "adherence": "Each item must start with an action verb. Keep items specific and actionable. Group related items under headers if there are distinct categories.",
        "category": "todo_lists",
        "description": "Checkbox to-do list format",
    },
    "shopping_list": {
        "instruction": "Format as a shopping list. Group items by category (produce, dairy, meat, pantry, household, etc.) if there are multiple items.",
        "adherence": "Always organize by store section categories. Use consistent item naming (e.g., quantities if mentioned).",
        "category": "todo_lists",
        "description": "Categorized shopping list",
    },
    # Keep grocery as an alias for backwards compatibility
    "grocery": {
        "instruction": "Format as a shopping list. Group items by category (produce, dairy, meat, pantry, household, etc.) if there are multiple items.",
        "adherence": "Always organize by store section categories. Use consistent item naming (e.g., quantities if mentioned).",
        "category": "todo_lists",
        "description": "Categorized grocery shopping list",
    },

    # ==========================================================================
    # BLOG - Blog/content creation formats
    # ==========================================================================
    "blog": {
        "instruction": "Format as a blog post with a compelling title, engaging introduction, well-organized body sections, and a conclusion.",
        "adherence": "Structure for readability. Use subheadings to break up content. Maintain a conversational yet informative tone. Note where examples or images might enhance the content.",
        "category": "blog",
        "description": "Blog post format with sections and flow",
    },
    "blog_outline": {
        "instruction": "Format as a blog post outline with main sections, subsections, and key points to cover under each. Include suggested introduction and conclusion hooks.",
        "adherence": "Structure as a hierarchical outline using markdown headers. Include [INTRO], [BODY], and [CONCLUSION] section markers. Each point should be brief but clear about the content to be written.",
        "category": "blog",
        "description": "Blog post structure and outline",
    },
    "blog_notes": {
        "instruction": "Format as raw notes and ideas for a blog post. Capture key points, quotes, statistics, links, or thoughts mentioned - doesn't need to be polished prose.",
        "adherence": "Preserve all ideas mentioned even if scattered. Use bullet points for discrete thoughts. Mark any action items (e.g., 'RESEARCH: [topic]', 'FIND: [statistic]') if mentioned.",
        "category": "blog",
        "description": "Unstructured blog research notes",
    },

    # ==========================================================================
    # DOCUMENTATION - Technical and reference documentation
    # ==========================================================================
    "documentation": {
        "instruction": "Format as structured documentation with clear headings, organized sections, and logical flow.",
        "adherence": "Use markdown formatting. Structure content hierarchically. Be clear and precise. Include examples where helpful.",
        "category": "documentation",
        "description": "Clear, structured documentation format",
    },
    "tech_docs": {
        "instruction": "Format as technical documentation with clear sections, code examples where appropriate, and structured explanations of technical concepts.",
        "adherence": "Use formal technical writing style. Include clear hierarchical headers, code formatting for technical terms, and structured examples. Define technical terms on first use.",
        "category": "documentation",
        "description": "Technical documentation and guides",
    },
    "readme": {
        "instruction": "Format as a README.md file for a software project. Include clear sections for project description, installation, usage, and other relevant information.",
        "adherence": "Follow GitHub README conventions: use markdown headers (# ## ###), include code blocks with language tags, format installation commands as code blocks, and structure information logically.",
        "category": "documentation",
        "description": "GitHub-style README documentation",
    },
    "reference_doc": {
        "instruction": "Format as a reference document with clear categorization, examples, and quick-lookup structure. Prioritize clarity and accessibility.",
        "adherence": "Organize information for quick reference. Use consistent formatting for similar items. Include examples where helpful. Use tables or structured lists for parameter references or option lists.",
        "category": "documentation",
        "description": "Reference material and quick-lookup docs",
    },
    "api_doc": {
        "instruction": "Format as API documentation with endpoint details, parameters, request/response examples, and usage notes.",
        "adherence": "Use consistent structure for each endpoint. Include HTTP methods, URL patterns, parameter tables, example requests/responses in code blocks. Note authentication requirements.",
        "category": "documentation",
        "description": "API endpoint documentation",
    },
    "sop": {
        "instruction": "Format as a Standard Operating Procedure (SOP) with: Purpose, Scope, Procedure (numbered steps), Safety/Compliance notes if relevant, and References if mentioned.",
        "adherence": "Use imperative voice for procedure steps. Each step must be clear and actionable. Include warnings or cautions if safety is mentioned. Maintain consistent step numbering.",
        "category": "documentation",
        "description": "Standard Operating Procedure document",
    },
    "changelog": {
        "instruction": "Format as a software changelog with version numbers, release dates, and categorized changes (Added, Changed, Fixed, Removed, Deprecated).",
        "adherence": "Follow Keep a Changelog format. Use markdown headers for versions. Group changes by category. Use bullet points. Include dates in YYYY-MM-DD format.",
        "category": "documentation",
        "description": "Software release changelog",
    },

    # ==========================================================================
    # WORK - Business/professional formats
    # ==========================================================================
    "bug_report": {
        "instruction": "Format as a software bug report with clear sections: Summary, Steps to Reproduce, Expected Behavior, Actual Behavior, Environment Details, and Additional Context.",
        "adherence": "Use technical precision. Include all mentioned error messages verbatim. Structure reproduction steps as numbered list. Categorize severity if mentioned.",
        "category": "work",
        "description": "Software bug report with technical details",
    },
    "project_plan": {
        "instruction": "Format as a project plan with: Overview, Goals/Objectives, Timeline/Milestones, Resources, Deliverables, and Risks if mentioned.",
        "adherence": "Use clear hierarchical structure. Present timeline as table or structured list. Highlight critical milestones. Be specific about deliverables and success criteria.",
        "category": "work",
        "description": "Project planning document",
    },
    "software_spec": {
        "instruction": "Format as a software specification document with clear requirements. Include: Overview, Functional Requirements (numbered list), Non-Functional Requirements, Constraints, and Acceptance Criteria if mentioned.",
        "adherence": "Use precise, unambiguous language. Number all requirements for reference (REQ-001, REQ-002, etc. or simple numbering). Each requirement should be testable and specific. Use 'shall' for mandatory requirements, 'should' for recommendations. Group related requirements under clear headings.",
        "category": "work",
        "description": "Software requirements specification",
    },
    "status_update": {
        "instruction": "Format as a brief status update or progress report. Include: what was accomplished, current status, any blockers or issues, and next steps.",
        "adherence": "Be concise and factual. Use bullet points for quick scanning. Highlight blockers or issues that need attention. Keep to essential information only. Suitable for standup updates or quick progress reports.",
        "category": "work",
        "description": "Brief status or progress update",
    },

    # ==========================================================================
    # CREATIVE - Creative writing and social media
    # ==========================================================================
    "social_post": {
        "instruction": "Format as a social media post optimized for engagement. Keep concise, use line breaks for readability, include hashtags if mentioned, and maintain conversational tone.",
        "adherence": "Respect platform character limits if specified. Use emoji strategically if mentioned. Structure for scanability. Include call-to-action if present.",
        "category": "creative",
        "description": "Social media post (Twitter, LinkedIn, etc.)",
    },
    "community_post": {
        "instruction": "Format as an online community post (Reddit, forums, Discord, etc.). Start with a brief friendly intro or context, use short paragraphs for readability, and maintain an approachable conversational tone.",
        "adherence": "Start with context or a brief 'Hi' intro if appropriate. Use short paragraphs (2-3 sentences max). Add line breaks between paragraphs for readability. Be genuine and conversational. Include a clear question or discussion point if asking for help. End with thanks if requesting assistance.",
        "category": "creative",
        "description": "Community/forum post (Reddit, Discord, etc.)",
    },
    "story_notes": {
        "instruction": "Format as creative writing notes. Capture character ideas, plot points, settings, and any narrative elements mentioned.",
        "adherence": "Preserve creative details and mood. Organize by narrative element (characters, plot, setting, themes).",
        "category": "creative",
        "description": "Creative writing notes and ideas",
    },

    # ==========================================================================
    # EXPERIMENTAL - Fun/experimental formats
    # ==========================================================================
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
    # Foundational
    "general": "General",
    "verbatim": "Verbatim",
    "brief": "Brief",
    "quick_note": "Quick Note",
    # Stylistic
    "email": "Email",
    "meeting_notes": "Meeting Notes",
    "bullet_points": "Bullet Points",
    "internal_memo": "Internal Memo",
    "press_release": "Press Release",
    "newsletter": "Newsletter",
    "persuasive": "Persuasive",
    "slack_message": "Slack Message",
    # Prompts
    "ai_prompt": "AI Prompt",
    "dev_prompt": "Development Prompt",
    "system_prompt": "System Prompt",
    "image_generation_prompt": "Image Generation Prompt",
    # To-Do Lists
    "todo": "To-Do",
    "shopping_list": "Shopping List",
    "grocery": "Grocery List",  # Legacy alias
    # Blog
    "blog": "Blog Post",
    "blog_outline": "Blog Outline",
    "blog_notes": "Blog Notes",
    # Documentation
    "documentation": "Documentation",
    "tech_docs": "Technical Documentation",
    "readme": "README",
    "reference_doc": "Reference Doc",
    "api_doc": "API Documentation",
    "sop": "SOP (Standard Operating Procedure)",
    "changelog": "Changelog",
    # Work
    "bug_report": "Bug Report",
    "project_plan": "Project Plan",
    "software_spec": "Software Spec",
    "status_update": "Status Update",
    # Creative
    "social_post": "Social Post",
    "community_post": "Community Post",
    "story_notes": "Story Notes",
    # Experimental
    "shakespearean": "Shakespearean Style",
    "medieval": "Medieval Style",
    "pirate_speak": "Pirate Speak",
    "formal_academic": "Formal Academic",
}

# Format categories for organization in Formats tab
# Aligns with PromptConfigCategory in prompt_library.py
FORMAT_CATEGORIES = {
    "foundational": "Foundational",
    "stylistic": "Stylistic",
    "prompts": "Prompts",
    "todo_lists": "To-Do Lists",
    "blog": "Blog",
    "documentation": "Documentation",
    "work": "Work",
    "creative": "Creative",
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
