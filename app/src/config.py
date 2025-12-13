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
    openai_model: str = "gpt-4o-audio-preview"
    mistral_model: str = "voxtral-small-latest"
    openrouter_model: str = "google/gemini-2.5-flash"

    # Audio settings
    # Default to "pulse" which routes through PipeWire/PulseAudio
    selected_microphone: str = "pulse"
    sample_rate: int = 48000

    # UI settings
    window_width: int = 500
    window_height: int = 600
    start_minimized: bool = False

    # Hotkeys (global keyboard shortcuts)
    # Supported keys: F14-F20 (macro keys), F1-F12, or modifier combinations
    hotkey_record_toggle: str = "f15"  # Toggle recording on/off
    hotkey_stop_and_transcribe: str = "f16"  # Stop and transcribe

    # Storage settings
    store_audio: bool = False  # Archive audio recordings
    vad_enabled: bool = True   # Enable Voice Activity Detection (silence removal)

    # Audio feedback
    beep_on_record: bool = True  # Play beep when recording starts/stops

    # Prompt customization options (checkboxes)
    # These are concatenated to build the cleanup prompt
    prompt_remove_fillers: bool = True       # Remove um, uh, like, etc.
    prompt_remove_tics: bool = True          # Remove hedging phrases (you know, I mean, etc.)
    prompt_remove_acknowledgments: bool = True  # Remove standalone Okay, Right, etc.
    prompt_punctuation: bool = True          # Add proper punctuation and sentences
    prompt_paragraph_spacing: bool = True    # Add natural paragraph breaks
    prompt_follow_instructions: bool = True  # Follow verbal instructions (don't include this, etc.)
    prompt_add_subheadings: bool = False     # Add ## headings for lengthy content
    prompt_markdown_formatting: bool = False  # Use bold, lists, etc.

    # Legacy field - kept for backwards compatibility but not used directly
    # The prompt is now built from the above boolean flags
    cleanup_prompt: str = ""

    # Format preset and formality settings
    format_preset: str = "general"      # general, email, todo, grocery, meeting_notes, bullet_points
    formality_level: str = "neutral"    # casual, neutral, professional

    # Email signature settings (used when format_preset == "email")
    user_name: str = ""
    email_signature: str = "Best regards"


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
            return Config(**filtered_data)
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


# Prompt component definitions
# Each tuple: (config_field, instruction_text, description_for_ui)
PROMPT_COMPONENTS = [
    (
        "prompt_remove_fillers",
        "Remove filler words (um, uh, like, you know, so, well, etc.)",
        "Remove filler words (um, uh, like...)"
    ),
    (
        "prompt_remove_tics",
        "Remove conversational verbal tics and hedging phrases (e.g., \"you know\", \"I mean\", \"kind of\", \"sort of\", \"basically\", \"actually\" when used as fillers)",
        "Remove verbal tics (you know, I mean...)"
    ),
    (
        "prompt_remove_acknowledgments",
        "Remove standalone acknowledgments that don't add meaning (e.g., \"Okay.\" or \"Right.\" as their own sentences)",
        "Remove standalone acknowledgments (Okay, Right...)"
    ),
    (
        "prompt_punctuation",
        "Add proper punctuation and sentence structure",
        "Add punctuation and sentence structure"
    ),
    (
        "prompt_paragraph_spacing",
        "Add natural paragraph spacing",
        "Add paragraph spacing"
    ),
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
]


# Format preset templates
# Each format adds specific instructions to shape the output
FORMAT_TEMPLATES = {
    "general": "",  # No additional instructions, uses base cleanup only
    "email": "Format the output as an email with an appropriate greeting and sign-off.",
    "todo": "Format as a to-do list with checkbox items (- [ ] task). Use action verbs and be concise.",
    "grocery": "Format as a grocery list. Group items by category (produce, dairy, meat, pantry, etc.) if there are multiple items.",
    "meeting_notes": "Format as meeting notes with clear sections, bullet points for key points, and a separate 'Action Items' section at the end.",
    "bullet_points": "Format as concise bullet points. One idea per bullet.",
}

# Display names for format presets (for UI dropdowns)
FORMAT_DISPLAY_NAMES = {
    "general": "General",
    "email": "Email",
    "todo": "To-Do List",
    "grocery": "Grocery List",
    "meeting_notes": "Meeting Notes",
    "bullet_points": "Bullet Points",
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


def build_cleanup_prompt(config: Config) -> str:
    """Build the cleanup prompt from config boolean flags, format preset, and formality."""
    lines = ["Your task is to provide a cleaned transcription of the audio recorded by the user."]

    # Add cleanup instructions from checkboxes
    for field_name, instruction, _ in PROMPT_COMPONENTS:
        if getattr(config, field_name, False):
            lines.append(f"- {instruction}")

    # Add format-specific instructions
    format_template = FORMAT_TEMPLATES.get(config.format_preset, "")
    if format_template:
        lines.append(f"- {format_template}")

    # Add formality/tone instructions
    formality_template = FORMALITY_TEMPLATES.get(config.formality_level, "")
    if formality_template:
        lines.append(f"- {formality_template}")

    # Add email signature if format is email and user has configured their name
    if config.format_preset == "email" and config.user_name:
        sign_off = config.email_signature or "Best regards"
        lines.append(f"- End the email with the sign-off: \"{sign_off},\" followed by the sender's name: \"{config.user_name}\"")

    # Always include output format instruction
    lines.append("- Output ONLY the cleaned transcription in markdown format, no commentary or preamble")

    return "\n".join(lines)
