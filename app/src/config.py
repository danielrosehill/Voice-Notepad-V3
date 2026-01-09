"""Configuration management for Voice Notepad V3."""

import json
import os
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import Optional


# Legacy OutputMode enum - kept for migration reference only
# New system uses three independent booleans: output_to_app, output_to_clipboard, output_to_inject


# TTS Voice Packs for audio feedback announcements
# Each voice pack has pre-generated WAV files in app/assets/tts/<pack_name>/
# "ryan" is the default (Edge TTS British male) stored directly in app/assets/tts/
TTS_VOICE_PACKS = {
    "ryan": {
        "name": "Ryan",
        "description": "Professional British male (Edge TTS)",
        "directory": "",  # Root tts directory (no subdirectory)
    },
    "herman": {
        "name": "Herman Poppleberry",
        "description": "Talking donkey - expressive, friendly",
        "directory": "herman",
    },
    "corn": {
        "name": "Cornelius Badonde",
        "description": "Elderly sloth - calm, quirky",
        "directory": "corn",
    },
    "venti": {
        "name": "Venti",
        "description": "Expressive natural voice",
        "directory": "venti",
    },
    "napoleon": {
        "name": "Napoleon Hill",
        "description": "Motivational speaker - authoritative",
        "directory": "napoleon",
    },
    "wizard": {
        "name": "Old Wizard",
        "description": "Mystical elderly wizard",
        "directory": "wizard",
    },
}


CONFIG_DIR = Path.home() / ".config" / "voice-notepad-v3"
CONFIG_FILE = CONFIG_DIR / "config.json"


# Available models per provider (model_id, display_name)
# Gemini Direct (recommended) - uses Google's dynamic "latest" endpoint
GEMINI_MODELS = [
    ("gemini-flash-latest", "Gemini Flash (Latest)"),
    ("gemini-2.5-flash", "Gemini 2.5 Flash"),
    ("gemini-2.5-flash-lite", "Gemini 2.5 Flash Lite (Budget)"),
    ("gemini-2.5-pro", "Gemini 2.5 Pro"),
    ("gemini-3-flash-preview", "Gemini 3 Flash (Preview)"),
]

# OpenRouter models - Gemini models only (OpenAI-compatible API)
# Note: OpenRouter doesn't support the dynamic "gemini-flash-latest" endpoint
OPENROUTER_MODELS = [
    ("google/gemini-2.5-flash", "Gemini 2.5 Flash"),
    ("google/gemini-2.5-flash-lite", "Gemini 2.5 Flash Lite (Budget)"),
    ("google/gemini-2.0-flash-001", "Gemini 2.0 Flash"),
    ("google/gemini-2.0-flash-lite-001", "Gemini 2.0 Flash Lite (Budget)"),
    ("google/gemini-3-flash-preview", "Gemini 3 Flash (Preview)"),
]

# Standard and Budget model tiers per provider
# These define which models the quick-toggle buttons select
MODEL_TIERS = {
    "gemini": {
        "standard": "gemini-flash-latest",
        "budget": "gemini-2.5-flash-lite",
    },
    "openrouter": {
        "standard": "google/gemini-3-flash-preview",
        "budget": "google/gemini-2.5-flash-lite",
    },
}

# Short audio optimization: use minimal prompt for brief recordings
# This reduces API overhead for quick notes (< 30 seconds)
SHORT_AUDIO_THRESHOLD_SECONDS = 30.0

# =============================================================================
# TRANSLATION MODE
# =============================================================================
# Languages available for translation mode
# Format: (language_code, display_name, flag_emoji)
TRANSLATION_LANGUAGES = [
    ("auto", "Auto-detect", "🌐"),
    ("en", "English", "🇬🇧"),
    ("es", "Spanish", "🇪🇸"),
    ("fr", "French", "🇫🇷"),
    ("de", "German", "🇩🇪"),
    ("it", "Italian", "🇮🇹"),
    ("pt", "Portuguese", "🇵🇹"),
    ("nl", "Dutch", "🇳🇱"),
    ("ru", "Russian", "🇷🇺"),
    ("zh", "Chinese (Simplified)", "🇨🇳"),
    ("zh-TW", "Chinese (Traditional)", "🇹🇼"),
    ("ja", "Japanese", "🇯🇵"),
    ("ko", "Korean", "🇰🇷"),
    ("ar", "Arabic", "🇸🇦"),
    ("he", "Hebrew", "🇮🇱"),
    ("hi", "Hindi", "🇮🇳"),
    ("th", "Thai", "🇹🇭"),
    ("vi", "Vietnamese", "🇻🇳"),
    ("tr", "Turkish", "🇹🇷"),
    ("pl", "Polish", "🇵🇱"),
    ("uk", "Ukrainian", "🇺🇦"),
    ("cs", "Czech", "🇨🇿"),
    ("sv", "Swedish", "🇸🇪"),
    ("da", "Danish", "🇩🇰"),
    ("no", "Norwegian", "🇳🇴"),
    ("fi", "Finnish", "🇫🇮"),
    ("el", "Greek", "🇬🇷"),
    ("ro", "Romanian", "🇷🇴"),
    ("hu", "Hungarian", "🇭🇺"),
    ("id", "Indonesian", "🇮🇩"),
    ("ms", "Malay", "🇲🇾"),
]

# Helper function to get language display name from code
def get_language_display_name(language_code: str) -> str:
    """Get the display name for a language code."""
    for code, name, _ in TRANSLATION_LANGUAGES:
        if code == language_code:
            return name
    return language_code

# Helper function to get language flag from code
def get_language_flag(language_code: str) -> str:
    """Get the flag emoji for a language code."""
    for code, _, flag in TRANSLATION_LANGUAGES:
        if code == language_code:
            return flag
    return "🌐"

SHORT_AUDIO_PROMPT = """Transcribe the audio. Apply only essential cleanup:
- Add punctuation (periods, commas, question marks)
- Capitalize sentences properly
- Remove filler words (um, uh, like, you know)
- Fix obvious grammar errors
- Break into paragraphs if multiple distinct thoughts

Output only the cleaned text, no commentary."""


def get_model_display_name(model_id: str, provider: str = "gemini") -> str:
    """Get the human-readable display name for a model ID.

    Args:
        model_id: The model identifier (e.g., "gemini-flash-latest", "google/gemini-2.5-flash")
        provider: The provider name ("gemini" or "openrouter")

    Returns:
        Human-readable display name (e.g., "Gemini Flash (Latest) ⭐")
    """
    # Build lookup dictionary from model lists
    model_lookup = {}
    for model_id_key, display_name in GEMINI_MODELS:
        model_lookup[model_id_key] = display_name
    for model_id_key, display_name in OPENROUTER_MODELS:
        model_lookup[model_id_key] = display_name

    # Return display name if found, otherwise return the model_id as-is
    return model_lookup.get(model_id, model_id)


@dataclass
class Config:
    """Application configuration."""

    # API Keys
    gemini_api_key: str = ""
    openrouter_api_key: str = ""

    # Selected model provider: "gemini" or "openrouter"
    # OpenRouter with Gemini 3 Flash Preview is recommended for best latency.
    selected_provider: str = "openrouter"

    # Model names per provider
    gemini_model: str = "gemini-flash-latest"
    openrouter_model: str = "google/gemini-3-flash-preview"

    # Primary and Fallback models - quick presets for switching with automatic failover
    # Primary: Your main transcription model (default: Gemini 3 Flash Preview via OpenRouter)
    # Fallback: Used automatically if primary fails (default: Gemini Flash Latest direct)
    # Using different providers for primary/fallback is recommended for resilience
    primary_name: str = "Gemini 3 Flash (OpenRouter)"
    primary_provider: str = "openrouter"
    primary_model: str = "google/gemini-3-flash-preview"

    fallback_name: str = "Gemini Flash (Latest)"
    fallback_provider: str = "gemini"
    fallback_model: str = "gemini-flash-latest"

    # Enable automatic failover to fallback model if primary fails
    failover_enabled: bool = True

    # Which model preset is currently active: "primary" or "fallback"
    active_model_preset: str = "primary"

    # Legacy fields for migration
    favorite_1_name: str = ""
    favorite_1_provider: str = ""
    favorite_1_model: str = ""
    favorite_2_name: str = ""
    favorite_2_provider: str = ""
    favorite_2_model: str = ""

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
    window_width: int = 850
    window_height: int = 800
    start_minimized: bool = False

    # Hotkeys (global keyboard shortcuts)
    # Each function can be mapped to an F-key from F13-F24, or left empty to disable.
    # These are designed for use with a macropad or programmable keyboard.
    #
    # Available functions:
    # - toggle: Simple toggle - press to start, press again to stop & transcribe
    # - tap_toggle: Tap toggle - press to start, press again to stop & cache (for append mode)
    # - transcribe: Transcribe cached audio without starting new recording
    # - clear: Clear/delete current recording and cached audio
    # - append: Start new recording that appends to cached audio
    # - retake: Discard current recording and start fresh
    #
    # Default mappings (F15-F20):
    hotkey_toggle: str = "f15"       # Simple toggle: start/stop+transcribe
    hotkey_tap_toggle: str = "f16"   # Tap toggle: start/stop+cache (for append workflow)
    hotkey_transcribe: str = "f17"   # Transcribe cached audio
    hotkey_clear: str = "f18"        # Clear/delete recording and cache
    hotkey_append: str = "f19"       # Append: start recording to add to cache
    hotkey_retake: str = "f20"       # Retake: discard current and start fresh recording

    # Legacy hotkey fields - kept for migration, mapped to new fields
    hotkey_mode: str = ""  # Deprecated
    hotkey_single_key: str = ""  # Migrated to hotkey_toggle
    hotkey_record_toggle: str = ""  # Migrated to hotkey_tap_toggle
    hotkey_stop_and_transcribe: str = ""  # Migrated to hotkey_transcribe
    hotkey_start: str = ""  # Deprecated (use hotkey_toggle)
    hotkey_stop_discard: str = ""  # Deprecated (use hotkey_clear)
    hotkey_ptt: str = ""  # Deprecated (PTT mode removed)
    ptt_release_action: str = ""  # Deprecated

    # Storage settings
    store_audio: bool = False  # Archive audio recordings
    vad_enabled: bool = True   # Enable Voice Activity Detection (silence removal)

    # Prompt optimization settings
    # Short audio prompt: Use a minimal prompt for brief recordings (< 30s) to reduce API overhead
    # When enabled, recordings under 30 seconds use a compact prompt (~300 chars vs ~4300 chars)
    short_audio_prompt_enabled: bool = False  # Disabled by default - user must opt in

    # OpenRouter balance polling settings
    # Instead of fetching cost per-transcription (which adds latency),
    # we poll the balance periodically in the background.
    # Options: 15, 30, 60 minutes
    balance_poll_interval_minutes: int = 30

    # Semantic search / embeddings settings
    # Embeddings enable semantic search in transcription history
    # Uses Gemini gemini-embedding-001 (free, 1500 RPM)
    embedding_enabled: bool = True  # Enable semantic search embeddings
    embedding_model: str = "gemini-embedding-001"  # Gemini embedding model
    embedding_dimensions: int = 768  # Embedding vector dimensions (768 = good balance)
    embedding_batch_size: int = 100  # Process embeddings in batches of N transcripts

    # Audio feedback mode: "beeps" (default), "tts" (voice announcements), "silent" (no audio)
    audio_feedback_mode: str = "beeps"

    # Duration display mode during recording
    # Options: "none" (hidden), "mm_ss" (minutes:seconds from 0:00), "minutes_only" (1M, 2M from 1 min)
    duration_display_mode: str = "mm_ss"  # Default to full MM:SS display

    # TTS voice pack: which voice to use for TTS announcements
    # Options: "ryan" (default Edge TTS), "herman", "corn", "venti", "napoleon", "wizard"
    tts_voice_pack: str = "ryan"

    # Legacy audio settings - kept for migration
    beep_on_record: bool = True
    beep_on_clipboard: bool = True
    quiet_mode: bool = False
    tts_announcements_enabled: bool = False

    # Output modes: where transcribed text is sent (can combine multiple)
    # These are independent toggles - any combination is valid
    output_to_app: bool = True       # Show text in app UI
    output_to_clipboard: bool = True  # Copy to clipboard via wl-copy
    output_to_inject: bool = False    # Type directly at cursor via ydotool

    # Legacy fields - kept for migration
    output_mode: str = ""  # Migrated to output_to_* booleans
    auto_paste: bool = False  # Migrated to output_to_inject

    # Append mode behavior
    append_position: str = "end"  # "end" (append at document end) or "cursor" (insert at cursor)

    # Prompt customization options (checkboxes) - Layer 2 only
    # Foundation layer (fillers, punctuation, paragraph spacing) is always applied
    prompt_follow_instructions: bool = True  # Follow verbal instructions (don't include this, etc.)
    prompt_add_subheadings: bool = False     # Add ## headings for lengthy content
    prompt_markdown_formatting: bool = False  # Use bold, lists, etc.
    prompt_remove_unintentional_dialogue: bool = False  # Remove accidental dialogue from others
    prompt_enhancement_enabled: bool = False  # Enhance prompts for maximum AI effectiveness
    prompt_infer_format: bool = False  # Infer output format (email, todo, etc.) from content (experimental)

    # Legacy field - kept for backwards compatibility but not used directly
    # The prompt is now built from the above boolean flags
    cleanup_prompt: str = ""

    # Format preset and formality settings
    format_preset: str = "general"      # general, email, todo, grocery, meeting_notes, bullet_points
    formality_level: str = "neutral"    # casual, neutral, professional
    verbosity_reduction: str = "none"   # none, minimum, short, medium, maximum

    # Writing sample for one-shot style copying
    writing_sample: str = ""

    # ==========================================================================
    # PERSONALIZED FIELDS
    # ==========================================================================
    # These fields are injected into prompts that require personalization
    # (e.g., Cover Letter, Email). Each prompt specifies which fields it uses.

    # Identity
    user_name: str = ""  # Full name (e.g., "Daniel Rosehill")
    short_name: str = ""  # Informal name for friends/family (e.g., "Daniel")
    user_role: str = ""  # Job title/role
    business_name: str = ""

    # Email
    email_business: str = ""
    email_personal: str = ""
    signature_business: str = ""
    signature_personal: str = ""

    # Phone
    phone_business: str = ""
    phone_personal: str = ""

    # Address
    address_business: str = ""
    address_personal: str = ""

    # Online Profiles
    website_business: str = ""
    website_personal: str = ""
    github_profile: str = ""
    huggingface_profile: str = ""
    linkedin_profile: str = ""

    # Context (free-form bio/background)
    user_context: str = ""

    # Legacy fields (kept for backward compatibility, migrated to new names)
    user_phone: str = ""  # Migrated to phone_business or phone_personal
    business_email: str = ""  # Migrated to email_business
    business_signature: str = ""  # Migrated to signature_business
    personal_email: str = ""  # Migrated to email_personal
    personal_signature: str = ""  # Migrated to signature_personal
    user_email: str = ""  # Migrated to email_business or email_personal
    email_signature: str = "Best regards"  # Migrated to signatures

    # ==========================================================================
    # PERSONALIZATION CONTROLS
    # ==========================================================================
    # When enabled, adds personalization elements (name, email, signature) to prompts
    # Note: Always enabled automatically for email format preset
    personalization_enabled: bool = False
    add_date_enabled: bool = False  # When enabled, adds today's date to the prompt

    # ==========================================================================
    # TLDR MODIFIER
    # ==========================================================================
    # When enabled, adds a TLDR/summary section to the output
    tldr_enabled: bool = False
    tldr_position: str = "top"  # "top" or "bottom"

    # ==========================================================================
    # STACK BUILDER SETTINGS
    # ==========================================================================
    # Multi-select writing styles (stackable)
    selected_styles: list = field(default_factory=list)  # e.g., ["persuasive", "serious"]

    # Word limit constraints
    word_limit_target: int = 0  # 0 = no limit
    word_limit_direction: str = "down"  # "up" (expand to target) or "down" (condense to target)

    # NEW: Prompt library system
    output_format: str = "markdown"  # text, markdown, html, json, xml, yaml
    active_prompt_ids: list = field(default_factory=list)  # List of enabled prompt IDs

    # NEW: Prompt stack system (multi-select elements)
    prompt_stack_elements: list = field(default_factory=list)  # List of selected element keys
    use_prompt_stacks: bool = False  # Whether to use prompt stacks instead of legacy format system

    # UI state
    prompt_stack_collapsed: bool = True  # Whether the prompt stack is collapsed (default: collapsed)

    # ==========================================================================
    # TRANSLATION MODE
    # ==========================================================================
    # When enabled, transcriptions are translated to the target language
    translation_mode_enabled: bool = False
    translation_source_language: str = "auto"  # "auto" for auto-detect, or language code
    translation_target_language: str = "en"    # Target language code (default: English)


def _apply_migrations(config: Config) -> Config:
    """Apply any necessary field migrations to a Config object."""
    # Migration: copy selected_microphone to preferred_mic_name if not set
    if config.selected_microphone and not config.preferred_mic_name:
        # Only migrate non-default values (not "pulse" or "default")
        if config.selected_microphone not in ("pulse", "default"):
            config.preferred_mic_name = config.selected_microphone

    # Migration: move user_email to email_business if email_business is empty
    if config.user_email and not config.email_business:
        config.email_business = config.user_email

    # Migration: move legacy business_email to email_business
    if config.business_email and not config.email_business:
        config.email_business = config.business_email

    # Migration: move legacy personal_email to email_personal
    if config.personal_email and not config.email_personal:
        config.email_personal = config.personal_email

    # Migration: move legacy business_signature to signature_business
    if config.business_signature and not config.signature_business:
        config.signature_business = config.business_signature

    # Migration: move legacy personal_signature to signature_personal
    if config.personal_signature and not config.signature_personal:
        config.signature_personal = config.personal_signature

    # Migration: move email_signature to signature_business if not default
    if config.email_signature and config.email_signature != "Best regards" and not config.signature_business:
        config.signature_business = config.email_signature

    # Migration: move user_phone to phone_business
    if config.user_phone and not config.phone_business:
        config.phone_business = config.user_phone

    # Migration: output_mode string -> output_to_* booleans
    # Also handles legacy auto_paste field
    if config.output_mode:
        # Old output_mode was set, migrate to new booleans
        if config.output_mode == "app_only":
            config.output_to_app = True
            config.output_to_clipboard = False
            config.output_to_inject = False
        elif config.output_mode == "clipboard":
            config.output_to_app = False
            config.output_to_clipboard = True
            config.output_to_inject = False
        elif config.output_mode == "inject":
            config.output_to_app = False
            config.output_to_clipboard = False
            config.output_to_inject = True
        # Clear legacy field after migration
        config.output_mode = ""
    elif config.auto_paste:
        # Legacy auto_paste was enabled, migrate to inject mode
        config.output_to_inject = True
        config.auto_paste = False

    # Migration: legacy hotkey fields to new hotkey fields
    # Only migrate if new field is at default AND legacy field has a value
    if config.hotkey_single_key and config.hotkey_toggle == "f15":
        # If user had customized single_key, use that for toggle
        if config.hotkey_single_key.lower() != "f15":
            config.hotkey_toggle = config.hotkey_single_key.lower()
        config.hotkey_single_key = ""

    if config.hotkey_record_toggle and config.hotkey_tap_toggle == "f16":
        if config.hotkey_record_toggle.lower() != "f16":
            config.hotkey_tap_toggle = config.hotkey_record_toggle.lower()
        config.hotkey_record_toggle = ""

    if config.hotkey_stop_and_transcribe and config.hotkey_transcribe == "f17":
        if config.hotkey_stop_and_transcribe.lower() != "f17":
            config.hotkey_transcribe = config.hotkey_stop_and_transcribe.lower()
        config.hotkey_stop_and_transcribe = ""

    # Migration: legacy audio feedback settings -> audio_feedback_mode
    # Only migrate if audio_feedback_mode is at default AND legacy fields were customized
    if config.audio_feedback_mode == "beeps":
        if config.quiet_mode:
            config.audio_feedback_mode = "silent"
        elif config.tts_announcements_enabled:
            config.audio_feedback_mode = "tts"

    # Migration: favorites -> primary/fallback
    # If user had favorites configured, migrate them to primary/fallback
    if config.favorite_1_name and config.primary_name == "Gemini Flash (Latest)":
        # User had favorite_1 configured, migrate to primary
        config.primary_name = config.favorite_1_name
        config.primary_provider = config.favorite_1_provider or "gemini"
        config.primary_model = config.favorite_1_model or "gemini-flash-latest"
        # Clear legacy field
        config.favorite_1_name = ""

    if config.favorite_2_name and config.fallback_name == "Gemini 2.5 Flash (OpenRouter)":
        # User had favorite_2 configured, migrate to fallback
        config.fallback_name = config.favorite_2_name
        config.fallback_provider = config.favorite_2_provider or "openrouter"
        config.fallback_model = config.favorite_2_model or "google/gemini-2.5-flash"
        # Clear legacy field
        config.favorite_2_name = ""

    # Migration: active_model_preset "favorite_1" -> "primary", "favorite_2" -> "fallback"
    if config.active_model_preset == "favorite_1":
        config.active_model_preset = "primary"
    elif config.active_model_preset == "favorite_2":
        config.active_model_preset = "fallback"
    elif config.active_model_preset == "default":
        # "default" now maps to "primary"
        config.active_model_preset = "primary"

    return config


def _load_from_json() -> Optional[Config]:
    """Load configuration from legacy JSON file.

    Returns Config if JSON file exists and is valid, None otherwise.
    """
    if not CONFIG_FILE.exists():
        return None

    try:
        with open(CONFIG_FILE, "r") as f:
            data = json.load(f)
        # Filter to only known fields to handle schema changes gracefully
        known_fields = {f.name for f in Config.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in known_fields}
        return Config(**filtered_data)
    except (json.JSONDecodeError, TypeError) as e:
        print(f"Warning: Could not load JSON config: {e}")
        return None


def _migrate_json_to_db() -> Optional[Config]:
    """Migrate settings from JSON to Mongita database.

    Returns the migrated Config if successful, None otherwise.
    """
    config = _load_from_json()
    if config is None:
        return None

    # Apply field migrations
    config = _apply_migrations(config)

    # Save to Mongita
    try:
        from .database_mongo import get_db
    except ImportError:
        from database_mongo import get_db

    db = get_db()
    if db.save_settings(asdict(config)):
        # Successfully migrated - rename old JSON file as backup
        backup_file = CONFIG_FILE.with_suffix('.json.migrated')
        try:
            CONFIG_FILE.rename(backup_file)
            print(f"Settings migrated to database. JSON backup: {backup_file}")
        except OSError as e:
            print(f"Warning: Could not rename old config file: {e}")
        return config

    return None


def load_config() -> Config:
    """Load configuration from Mongita database.

    Migration path:
    1. If settings exist in Mongita, load from there
    2. If not, check for legacy JSON config and migrate it
    3. If neither exists, return default config

    All settings are now stored in the Mongita database for better
    reliability and consistency with transcript storage.
    """
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    try:
        from .database_mongo import get_db
    except ImportError:
        from database_mongo import get_db

    db = get_db()

    # Check if settings exist in Mongita
    if db.settings_exist():
        data = db.get_settings()
        # Filter to only known fields to handle schema changes gracefully
        known_fields = {f.name for f in Config.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in known_fields}
        config = Config(**filtered_data)
        return _apply_migrations(config)

    # Check for legacy JSON config and migrate
    if CONFIG_FILE.exists():
        config = _migrate_json_to_db()
        if config is not None:
            return config

    # Return default config and save it
    config = Config()
    save_config(config)
    return config


def save_config(config: Config) -> None:
    """Save configuration to Mongita database."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    try:
        from .database_mongo import get_db
    except ImportError:
        from database_mongo import get_db

    db = get_db()
    db.save_settings(asdict(config))


def load_env_keys(config: Config) -> Config:
    """Load API keys from environment variables if not already set."""
    if not config.gemini_api_key:
        config.gemini_api_key = os.environ.get("GEMINI_API_KEY", "")
    if not config.openrouter_api_key:
        config.openrouter_api_key = os.environ.get("OPENROUTER_API_KEY", "")
    return config


# =============================================================================
# MODEL PRESET HELPERS
# =============================================================================


def is_preset_configured(config: Config, preset: str) -> bool:
    """Check if a model preset is configured (has a name set).

    Args:
        config: Configuration object
        preset: "primary" or "fallback"

    Returns:
        True if the preset has a name configured
    """
    if preset == "primary":
        return bool(config.primary_name)
    elif preset == "fallback":
        return bool(config.fallback_name)
    return False


# Legacy alias for backwards compatibility
def is_favorite_configured(config: Config, favorite_num: int) -> bool:
    """Legacy function - use is_preset_configured instead."""
    preset = "primary" if favorite_num == 1 else "fallback"
    return is_preset_configured(config, preset)


def get_active_provider_and_model(config: Config) -> tuple[str, str]:
    """Get the provider and model based on the active model preset.

    Returns:
        Tuple of (provider, model) based on active_model_preset.
        Falls back to primary if the active preset is not configured.
    """
    preset = config.active_model_preset

    if preset == "primary" and is_preset_configured(config, "primary"):
        return (config.primary_provider, config.primary_model)
    elif preset == "fallback" and is_preset_configured(config, "fallback"):
        return (config.fallback_provider, config.fallback_model)

    # Default to primary
    if is_preset_configured(config, "primary"):
        return (config.primary_provider, config.primary_model)

    # Ultimate fallback: use selected_provider and corresponding model
    provider = config.selected_provider
    if provider == "gemini":
        model = config.gemini_model
    elif provider == "openrouter":
        model = config.openrouter_model
    else:
        model = config.gemini_model  # Fallback
    return (provider, model)


def get_fallback_provider_and_model(config: Config) -> tuple[str, str] | None:
    """Get the fallback provider and model if configured.

    Returns:
        Tuple of (provider, model) for the fallback, or None if not configured.
    """
    if is_preset_configured(config, "fallback"):
        return (config.fallback_provider, config.fallback_model)
    return None


def get_preset_display_name(config: Config, preset: str) -> str:
    """Get the display name for a model preset.

    Args:
        config: Configuration object
        preset: "primary" or "fallback"

    Returns:
        Display name (e.g., "Gemini Flash (Latest)", etc.)
    """
    if preset == "primary" and config.primary_name:
        return config.primary_name
    elif preset == "fallback" and config.fallback_name:
        return config.fallback_name
    else:
        # For unknown preset, show the active model display name
        provider, model = get_active_provider_and_model(config)
        return get_model_display_name(model, provider)


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

    # Section 7: Trailing/incomplete sentences
    "trailing_sentences": {
        "heading": "Trailing Sentences",
        "instructions": [
            "Remove incomplete or trailing sentences where the user clearly abandoned a thought mid-sentence without finishing it.",
            "Look for sentences that start but trail off without reaching a conclusion, verb, or complete thought—these indicate the user changed their mind or decided not to continue that line of thinking.",
            "Only remove sentences that are clearly incomplete. If a sentence could be interpreted as intentionally brief or stylistically fragmented, preserve it.",
        ],
    },

    # Section 8: Spelling clarifications
    "spelling_clarifications": {
        "heading": "Spelling Clarifications",
        "instructions": [
            "The user might spell out a word to avoid mistranscription for infrequently encountered words. Example: \"We want to use Zod to resolve TypeScript errors. Zod is spelled Z-O-D.\"",
            "Do not include the spelling instruction. Simply ensure the word is spelled as requested. Example output: \"We want to use Zod to resolve TypeScript errors.\"",
        ],
    },

    # Section 9: Grammar and typos
    "grammar_and_typos": {
        "heading": "Grammar & Typos",
        "instructions": [
            "Correct spelling errors, typos, and grammatical mistakes.",
            "Apply standard grammar rules for subject-verb agreement, tense consistency, and proper word usage.",
            "Fix homophones used incorrectly (their/there/they're, your/you're) and correct common mistranscriptions where context makes the intended word clear.",
            "Fix minor grammatical errors that occur naturally in speech (e.g., wrong pluralization like \"into the option\" → \"into the options\").",
        ],
    },

    # Section 10: Punctuation and structure
    "punctuation": {
        "heading": "Punctuation",
        "instructions": [
            "Add appropriate punctuation including periods, commas, colons, semicolons, question marks, and quotation marks where contextually appropriate.",
            "Break text into logical paragraphs based on topic shifts and natural thought boundaries.",
            "Ensure sentences are properly capitalized.",
        ],
    },

    # Section 11: Format detection
    "format_detection": {
        "heading": "Format Detection",
        "instructions": [
            "If you can infer that the transcript was intended to be formatted in a specific and commonly used format (such as an email, to-do list, or meeting notes), ensure the text conforms to the expected format.",
            "Match language tone to detected context: business emails should use professional language, casual notes can be informal.",
        ],
    },

    # Section 12: Clarity (optional tightening)
    "clarity": {
        "heading": "Clarity",
        "instructions": [
            "Make language more direct and concise—tighten rambling sentences without removing information.",
            "Clarify confusing or illogical phrasing while preserving all details and original meaning.",
        ],
    },

    # Section 13: Subheadings for structure
    "subheadings": {
        "heading": "Subheadings",
        "instructions": [
            "For lengthy transcriptions with distinct sections or topics, add markdown subheadings (## Heading) to organize the content.",
            "Only add subheadings when the content naturally breaks into separate sections; do not force structure on short or single-topic transcriptions.",
        ],
    },

    # Section 14: Markdown formatting
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
    "note_to_self": {
        "instruction": "Format as a note-to-self for future reference. Focus on capturing the key detail or reminder clearly and concisely.",
        "adherence": "Keep it brief and focused. This is something you're noting down for your future self - could be a reminder, a detail to remember, a thought to revisit, or a quick reference. No elaborate formatting needed. Just the essential information, clearly stated.",
        "category": "foundational",
        "description": "Lightweight note for future reference",
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
    "meeting_agenda": {
        "instruction": "Format as a meeting agenda with: meeting title, date/time, attendees, and numbered agenda items with time allocations if mentioned.",
        "adherence": "Structure clearly with numbered items. Include objectives if mentioned. Add time estimates per item if provided. End with 'Any Other Business (AOB)' section if appropriate.",
        "category": "stylistic",
        "description": "Meeting agenda with structured items",
    },
    "meeting_minutes": {
        "instruction": "Format as formal meeting minutes with: meeting title, date/time, attendees present/absent, agenda items discussed, decisions made, action items with owners and deadlines, and next meeting date if mentioned.",
        "adherence": "Use formal minute-taking structure. Number each agenda item. Record decisions verbatim where possible. Clearly mark ACTION items with responsible person and deadline. Include voting results if any votes were taken.",
        "category": "stylistic",
        "description": "Formal meeting minutes with decisions and actions",
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
        "instruction": "Format as a social media or community post. Works for Twitter/X, LinkedIn, Reddit, Discord, forums, and other social platforms. Keep it engaging, use line breaks for readability, and maintain a conversational tone appropriate for the platform.",
        "adherence": "Respect platform character limits if specified. Use short paragraphs (2-3 sentences max) for readability. Be genuine and conversational. For community posts (Reddit, forums), include context and a clear question if asking for help. Use hashtags or emoji strategically when appropriate.",
        "category": "creative",
        "description": "Social media & community posts (Twitter, Reddit, Discord, etc.)",
    },
    "story_notes": {
        "instruction": "Format as creative writing notes. Capture character ideas, plot points, settings, and any narrative elements mentioned.",
        "adherence": "Preserve creative details and mood. Organize by narrative element (characters, plot, setting, themes).",
        "category": "creative",
        "description": "Creative writing notes and ideas",
    },

}

# Display names for format presets (for UI)
FORMAT_DISPLAY_NAMES = {
    # Foundational
    "general": "General",
    "verbatim": "Verbatim",
    "brief": "Brief",
    "quick_note": "Quick Note",
    "note_to_self": "Note to Self",
    # Stylistic
    "email": "Email",
    "meeting_notes": "Meeting Notes",
    "meeting_agenda": "Meeting Agenda",
    "meeting_minutes": "Meeting Minutes",
    "bullet_points": "Bullet Points",
    "internal_memo": "Internal Memo",
    "press_release": "Press Release",
    "newsletter": "Newsletter",
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
    "story_notes": "Story Notes",
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
}

# =============================================================================
# TONE TEMPLATES (Mutually exclusive - pick one)
# =============================================================================
# These define the emotional register and formality of the writing.
# Only one tone can be selected at a time.

TONE_TEMPLATES = {
    # Formality spectrum
    "casual": "Use a casual, relaxed, conversational tone as if chatting with a friend.",
    "neutral": "",  # No tone modifier - let content dictate
    "professional": "Use a professional, formal tone appropriate for business communication.",
    # Emotional register
    "friendly": "Use a warm, friendly, approachable tone that puts the reader at ease.",
    "authoritative": "Use an authoritative, confident tone that conveys expertise and credibility.",
    "enthusiastic": "Use an enthusiastic, energetic tone that conveys excitement and passion.",
    "empathetic": "Use an empathetic, understanding tone that acknowledges feelings and concerns.",
    "urgent": "Use an urgent, pressing tone that conveys importance and time-sensitivity.",
    "reassuring": "Use a calm, reassuring tone that provides comfort and confidence.",
}

# Display names for tone levels (for UI)
TONE_DISPLAY_NAMES = {
    "casual": "Casual",
    "neutral": "Neutral",
    "professional": "Professional",
    "friendly": "Friendly",
    "authoritative": "Authoritative",
    "enthusiastic": "Enthusiastic",
    "empathetic": "Empathetic",
    "urgent": "Urgent",
    "reassuring": "Reassuring",
}

# Legacy aliases for backward compatibility
FORMALITY_TEMPLATES = TONE_TEMPLATES
FORMALITY_DISPLAY_NAMES = TONE_DISPLAY_NAMES

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

# =============================================================================
# WRITING STYLE TEMPLATES (Stackable - can combine multiple)
# =============================================================================
# These are writing style modifiers that can be stacked on top of format presets.
# Unlike tone (formality), multiple styles can be selected simultaneously.
# Example: "persuasive" + "serious" = persuasive but not humorous

STYLE_TEMPLATES = {
    # Core writing styles
    "analytical": "Use analytical, data-driven language focused on logic and evidence. Emphasize facts and reasoning.",
    "concise": "Be extremely brief and economical with words. Every word must earn its place. Eliminate redundancy.",
    "conversational": "Write in a conversational, approachable style as if speaking to a friend. Use natural language patterns.",
    "direct": "Be direct and to-the-point. Avoid hedging, qualifiers, and unnecessary softening. State things plainly.",
    "emotive": "Use emotionally engaging language that connects with the reader. Evoke appropriate feelings for the context.",
    "formal_academic": "Use formal academic writing style with precise terminology, proper citations format, and scholarly tone.",
    "persuasive": "Use persuasive language to convince and motivate the reader. Appeal to logic, emotion, and credibility where appropriate.",
    "serious": "Maintain a serious, professional tone throughout. Avoid humor, casualness, or levity.",
    # Fun/creative styles (moved from experimental formats)
    "medieval": "Rewrite in Medieval/Middle English style as if written by a medieval scribe or chronicler, using archaic vocabulary and formal historical narrative style.",
    "pirate_speak": "Rewrite in pirate vernacular with nautical terms, 'arr', 'me hearty', and swashbuckling language while keeping the content recognizable.",
    "shakespearean": "Rewrite in Shakespearean English style, using Early Modern English vocabulary, thou/thee pronouns, and poetic phrasing while preserving the core meaning.",
}

# Display names for writing styles (for UI)
STYLE_DISPLAY_NAMES = {
    "analytical": "Analytical",
    "concise": "Concise",
    "conversational": "Conversational",
    "direct": "Direct",
    "emotive": "Emotive",
    "formal_academic": "Academic",
    "persuasive": "Persuasive",
    "serious": "Serious",
    # Fun styles
    "medieval": "Medieval",
    "pirate_speak": "Pirate",
    "shakespearean": "Shakespearean",
}

# Display names for duration display modes (for UI)
DURATION_DISPLAY_NAMES = {
    "none": "None",
    "mm_ss": "Minutes/Seconds",
    "minutes_only": "Minutes Only",
}

# Word limit templates for up/down direction
WORD_LIMIT_TEMPLATES = {
    "up": "Expand the content to approximately {target} words. Add relevant detail, examples, and elaboration to reach the target length while maintaining quality.",
    "down": "Condense the content to approximately {target} words. Keep only the most essential information and trim unnecessary details to reach the target length.",
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


def build_cleanup_prompt(config: Config, use_prompt_library: bool = False, audio_duration_seconds: Optional[float] = None) -> str:
    """Build the cleanup prompt using the 3-layer architecture.

    Args:
        config: Configuration object
        use_prompt_library: If True, use the new prompt library system from database.
                           If False, use legacy hardcoded prompts (default for backward compat).
        audio_duration_seconds: Optional audio duration. If provided and below
                               SHORT_AUDIO_THRESHOLD_SECONDS, returns a minimal prompt
                               for efficiency on short recordings.

    Layer 1 (Foundation): Always applied - basic rewriting (filler removal, punctuation, paragraphs)
    Layer 2 (Optional): User-selected enhancements (subheadings, markdown, etc.)
    Layer 3 (Format + Style): Format-specific instructions, formality, verbosity, writing sample
    """
    # Short audio optimization: use minimal prompt for brief recordings
    # Only applies if the user has enabled this feature in Settings → Misc
    if (config.short_audio_prompt_enabled and
            audio_duration_seconds is not None and
            audio_duration_seconds < SHORT_AUDIO_THRESHOLD_SECONDS):
        return SHORT_AUDIO_PROMPT

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
    # Iterate over sections to conditionally include format_detection
    for section_key, section_data in FOUNDATION_PROMPT_SECTIONS.items():
        # Skip format_detection if prompt_infer_format is disabled
        if section_key == "format_detection" and not getattr(config, 'prompt_infer_format', True):
            continue
        for instruction in section_data["instructions"]:
            # Replace hardcoded name with configured short_name or user_name
            if section_key == "user_details":
                display_name = config.short_name or config.user_name or "the user"
                instruction = instruction.replace("Daniel", display_name)
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

    # ===== WRITING STYLES (Multi-select, stackable) =====
    selected_styles = getattr(config, 'selected_styles', [])
    if selected_styles:
        writing_style_instructions = []
        for style_key in selected_styles:
            style_template = STYLE_TEMPLATES.get(style_key, "")
            if style_template:
                writing_style_instructions.append(style_template)

        if writing_style_instructions:
            lines.append("\n## Writing Style")
            lines.append("Apply the following writing styles to the output:")
            for instruction in writing_style_instructions:
                lines.append(f"- {instruction}")

    # ===== WORD LIMIT CONSTRAINTS =====
    word_limit_target = getattr(config, 'word_limit_target', 0)
    word_limit_direction = getattr(config, 'word_limit_direction', 'down')
    if word_limit_target and word_limit_target > 0:
        word_limit_template = WORD_LIMIT_TEMPLATES.get(word_limit_direction, "")
        if word_limit_template:
            lines.append("\n## Word Count Target")
            lines.append(f"- {word_limit_template.format(target=word_limit_target)}")

    # Writing sample reference
    if config.writing_sample and config.writing_sample.strip():
        lines.append("\n## Writing Style Reference")
        lines.append("The user has provided the following writing sample as a reference for tone, style, and structure. "
                    "Use this as guidance for the output style:")
        lines.append(f"\n{config.writing_sample.strip()}\n")

    # ===== PERSONALIZATION =====
    # Add personalization for email format (always) or when explicitly enabled
    is_email_format = config.format_preset == "email"
    should_personalize = is_email_format or config.personalization_enabled

    if should_personalize:
        # Use business email/signature by default, fall back to personal, then legacy fields
        sender_email = config.business_email or config.personal_email or config.user_email
        sender_signature = config.business_signature or config.personal_signature
        # Use short_name for informal contexts, fall back to user_name
        display_name = config.short_name or config.user_name

        if display_name or sender_email or config.user_phone:
            lines.append("\n## User Profile")
            profile_parts = []
            if display_name:
                profile_parts.append(f"Name: {display_name}")
            if config.user_name and config.user_name != display_name:
                profile_parts.append(f"Full name: {config.user_name}")
            if sender_email:
                profile_parts.append(f"Email: {sender_email}")
            if config.user_phone:
                profile_parts.append(f"Phone: {config.user_phone}")

            profile_info = ", ".join(profile_parts)
            if is_email_format:
                lines.append(f"- Draft the email from the following person: {profile_info}")
            else:
                lines.append(f"- The user's profile information: {profile_info}")
                lines.append("- Use this information where appropriate (e.g., signatures, sign-offs, author attribution).")

        if is_email_format:
            # Email-specific signature handling
            if sender_signature:
                lines.append(f"- End the email with the following signature:\n\n{sender_signature}")
            elif display_name:
                # Fallback to simple sign-off if no signature configured
                sign_off = config.email_signature or "Best regards"
                lines.append(f"- End the email with the sign-off: \"{sign_off},\" followed by the sender's name: \"{display_name}\"")
        elif sender_signature:
            # For non-email formats, make signature available but don't force it
            lines.append(f"- If a signature is appropriate for this content type, use:\n\n{sender_signature}")

    # ===== DATE INJECTION =====
    if config.add_date_enabled:
        from datetime import date
        today = date.today()
        formatted_date = today.strftime("%B %d, %Y")  # e.g., "January 09, 2026"
        lines.append("\n## Date")
        lines.append(f"- Today's date is {formatted_date}.")
        lines.append("- Include this date in the output where appropriate (e.g., letter headers, document dates, meeting notes).")

    # ===== TRANSLATION MODE =====
    if config.translation_mode_enabled:
        target_lang = get_language_display_name(config.translation_target_language)
        lines.append("\n## Translation")
        lines.append(f"- After cleaning up the transcription, translate the entire output into {target_lang}.")
        lines.append(f"- The final output must be entirely in {target_lang}.")
        lines.append("- Preserve the formatting, structure, and meaning of the original while producing natural-sounding text in the target language.")

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

    # ===== PERSONALIZATION =====
    # Add personalization for email format (always) or when explicitly enabled
    is_email_format = config.format_preset == "email"
    should_personalize = is_email_format or config.personalization_enabled

    if should_personalize:
        # Use business email/signature by default, fall back to personal, then legacy fields
        sender_email = config.business_email or config.personal_email or config.user_email
        sender_signature = config.business_signature or config.personal_signature
        # Use short_name for informal contexts, fall back to user_name
        display_name = config.short_name or config.user_name

        if display_name or sender_email or config.user_phone:
            lines.append("\n## User Profile")
            profile_parts = []
            if display_name:
                profile_parts.append(f"Name: {display_name}")
            if config.user_name and config.user_name != display_name:
                profile_parts.append(f"Full name: {config.user_name}")
            if sender_email:
                profile_parts.append(f"Email: {sender_email}")
            if config.user_phone:
                profile_parts.append(f"Phone: {config.user_phone}")

            profile_info = ", ".join(profile_parts)
            if is_email_format:
                lines.append(f"- Draft the email from the following person: {profile_info}")
            else:
                lines.append(f"- The user's profile information: {profile_info}")
                lines.append("- Use this information where appropriate (e.g., signatures, sign-offs, author attribution).")

        if is_email_format:
            # Email-specific signature handling
            if sender_signature:
                lines.append(f"- End the email with the following signature:\n\n{sender_signature}")
            elif display_name:
                # Fallback to simple sign-off if no signature configured
                sign_off = config.email_signature or "Best regards"
                lines.append(f"- End the email with the sign-off: \"{sign_off},\" followed by the sender's name: \"{display_name}\"")
        elif sender_signature:
            # For non-email formats, make signature available but don't force it
            lines.append(f"- If a signature is appropriate for this content type, use:\n\n{sender_signature}")

    # ===== DATE INJECTION =====
    if config.add_date_enabled:
        from datetime import date
        today = date.today()
        formatted_date = today.strftime("%B %d, %Y")  # e.g., "January 09, 2026"
        lines.append("\n## Date")
        lines.append(f"- Today's date is {formatted_date}.")
        lines.append("- Include this date in the output where appropriate (e.g., letter headers, document dates, meeting notes).")

    # ===== TRANSLATION MODE =====
    if config.translation_mode_enabled:
        target_lang = get_language_display_name(config.translation_target_language)
        lines.append("\n## Translation")
        lines.append(f"- After cleaning up the transcription, translate the entire output into {target_lang}.")
        lines.append(f"- The final output must be entirely in {target_lang}.")
        lines.append("- Preserve the formatting, structure, and meaning of the original while producing natural-sounding text in the target language.")

    # Final instruction
    lines.append("\n## Output")
    lines.append("- Output ONLY the cleaned transcription, no commentary or preamble")

    return "\n".join(lines)
