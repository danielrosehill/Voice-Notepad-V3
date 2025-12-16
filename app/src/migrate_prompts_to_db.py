"""Migrate existing hardcoded prompts from config.py to Mongita database.

This script reads the FOUNDATION_PROMPT_COMPONENTS and OPTIONAL_PROMPT_COMPONENTS
from config.py and creates PromptTemplate objects in the database.

Run this ONCE to populate the initial prompt library.
"""

from datetime import datetime
from database_mongo import get_db
from prompt_library import PromptCategory
from config import FOUNDATION_PROMPT_COMPONENTS, OPTIONAL_PROMPT_COMPONENTS


def migrate_foundation_prompts():
    """Migrate foundation layer prompts."""
    db = get_db()

    print("Migrating foundation prompts...")

    for idx, instruction in enumerate(FOUNDATION_PROMPT_COMPONENTS, start=1):
        # Generate a stable ID based on instruction content
        prompt_id = f"foundation_{idx}"

        # Create descriptive names from instructions
        name_map = {
            1: "Remove Filler Words",
            2: "Remove Verbal Tics",
            3: "Remove Standalone Acknowledgments",
            4: "Add Proper Punctuation",
            5: "Add Natural Paragraph Spacing",
        }

        prompt_doc = {
            'name': name_map.get(idx, f"Foundation {idx}"),
            'category': PromptCategory.FOUNDATION,
            'description': instruction[:100],  # Use first 100 chars as description
            'instruction': instruction,
            'is_builtin': True,
            'is_enabled': True,  # Foundation is always enabled
            'priority': idx,  # Lower priority = applied first
            'subcategory': None,
            'conflicts_with': [],
            'requires': [],
            'tags': ['foundation', 'cleanup', 'basic'],
            'has_parameters': False,
            'parameters': {},
        }

        # Check if already exists (by name to avoid duplicates)
        existing = list(db._get_db().prompts.find({'name': prompt_doc['name']}).limit(1))

        if not existing:
            prompt_id = db.save_prompt(prompt_doc)
            print(f"  ✓ Created: {prompt_doc['name']}")
        else:
            print(f"  ⊘ Skipped (exists): {prompt_doc['name']}")


def migrate_optional_prompts():
    """Migrate optional layer 2 prompts."""
    db = get_db()

    print("\nMigrating optional prompts...")

    for idx, (config_field, instruction, description) in enumerate(OPTIONAL_PROMPT_COMPONENTS, start=10):
        # Determine category based on instruction content
        category = PromptCategory.FORMATTING

        if 'verbal instructions' in instruction.lower():
            category = PromptCategory.SPECIAL_PURPOSE
        elif 'subheadings' in instruction.lower() or 'markdown' in instruction.lower():
            category = PromptCategory.FORMATTING
        elif 'dialogue' in instruction.lower():
            category = PromptCategory.CONTENT_TRANSFORM
        elif 'prompt' in instruction.lower() and 'ai' in instruction.lower():
            category = PromptCategory.SPECIAL_PURPOSE

        # Extract name from description
        name = description

        prompt_doc = {
            'name': name,
            'category': category,
            'description': description,
            'instruction': instruction,
            'is_builtin': True,
            'is_enabled': False,  # Optional prompts default to disabled
            'priority': idx,
            'subcategory': None,
            'conflicts_with': [],
            'requires': [],
            'tags': ['optional', 'enhancement'],
            'has_parameters': False,
            'parameters': {},
        }

        # Check if already exists
        existing = list(db._get_db().prompts.find({'name': prompt_doc['name']}).limit(1))

        if not existing:
            prompt_id = db.save_prompt(prompt_doc)
            print(f"  ✓ Created: {prompt_doc['name']}")
        else:
            print(f"  ⊘ Skipped (exists): {prompt_doc['name']}")


def add_additional_prompts():
    """Add additional useful prompts beyond what's in config.py."""
    db = get_db()

    print("\nAdding additional prompts...")

    additional_prompts = [
        {
            'name': "Convert to First Person",
            'category': PromptCategory.GRAMMATICAL,
            'description': "Rewrite in first person perspective (I, me, my)",
            'instruction': "Rewrite the transcription in first person perspective, using 'I', 'me', 'my' pronouns.",
            'priority': 50,
            'tags': ['grammar', 'perspective', 'first-person'],
            'conflicts_with': [],  # Will be updated with IDs later if needed
        },
        {
            'name': "Convert to Third Person",
            'category': PromptCategory.GRAMMATICAL,
            'description': "Rewrite in third person perspective (he, she, they)",
            'instruction': "Rewrite the transcription in third person perspective, using appropriate third-person pronouns.",
            'priority': 51,
            'tags': ['grammar', 'perspective', 'third-person'],
            'conflicts_with': [],  # Conflicts with "Convert to First Person"
        },
        {
            'name': "Convert to Past Tense",
            'category': PromptCategory.GRAMMATICAL,
            'description': "Convert all verbs to past tense",
            'instruction': "Rewrite the transcription in past tense, converting all verbs appropriately.",
            'priority': 52,
            'tags': ['grammar', 'tense', 'past'],
            'conflicts_with': [],
        },
        {
            'name': "Convert to Present Tense",
            'category': PromptCategory.GRAMMATICAL,
            'description': "Convert all verbs to present tense",
            'instruction': "Rewrite the transcription in present tense, converting all verbs appropriately.",
            'priority': 53,
            'tags': ['grammar', 'tense', 'present'],
            'conflicts_with': [],
        },
        {
            'name': "Make Concise",
            'category': PromptCategory.STYLISTIC,
            'description': "Reduce verbosity and make more concise",
            'instruction': "Make the transcription more concise by removing redundant information while preserving all key points.",
            'priority': 60,
            'tags': ['style', 'concise', 'brevity'],
            'conflicts_with': [],  # Conflicts with "Make Detailed"
        },
        {
            'name': "Make Detailed",
            'category': PromptCategory.STYLISTIC,
            'description': "Expand and add more detail",
            'instruction': "Expand the transcription with additional detail, context, and explanations where appropriate.",
            'priority': 61,
            'tags': ['style', 'detailed', 'verbose'],
            'conflicts_with': [],  # Conflicts with "Make Concise"
        },
        {
            'name': "Extract Action Items",
            'category': PromptCategory.CONTENT_TRANSFORM,
            'description': "Extract and list action items from the content",
            'instruction': "Extract all action items from the transcription and present them as a bulleted list at the end, with clear assignees if mentioned.",
            'priority': 70,
            'tags': ['action-items', 'tasks', 'extraction'],
            'conflicts_with': [],
        },
        {
            'name': "Create Summary",
            'category': PromptCategory.CONTENT_TRANSFORM,
            'description': "Create a brief summary of the content",
            'instruction': "Create a concise summary of the main points from the transcription (3-5 sentences).",
            'priority': 71,
            'tags': ['summary', 'brief', 'extraction'],
            'conflicts_with': [],
        },
    ]

    for prompt_data in additional_prompts:
        # Add standard fields
        prompt_doc = {
            **prompt_data,
            'is_builtin': True,
            'is_enabled': False,  # Default to disabled
            'subcategory': None,
            'requires': [],
            'has_parameters': False,
            'parameters': {},
        }

        # Check if already exists
        existing = list(db._get_db().prompts.find({'name': prompt_doc['name']}).limit(1))

        if not existing:
            prompt_id = db.save_prompt(prompt_doc)
            print(f"  ✓ Created: {prompt_doc['name']}")
        else:
            print(f"  ⊘ Skipped (exists): {prompt_doc['name']}")


if __name__ == "__main__":
    print("=" * 60)
    print("Prompt Migration to Mongita Database")
    print("=" * 60)

    migrate_foundation_prompts()
    migrate_optional_prompts()
    add_additional_prompts()

    # Summary
    db = get_db()
    total_prompts = db._get_db().prompts.count_documents({})
    foundation_count = db._get_db().prompts.count_documents({'category': PromptCategory.FOUNDATION})
    optional_count = total_prompts - foundation_count

    print("\n" + "=" * 60)
    print("Migration Summary")
    print("=" * 60)
    print(f"Total prompts in database: {total_prompts}")
    print(f"  Foundation prompts: {foundation_count}")
    print(f"  Optional prompts: {optional_count}")
    print("=" * 60)
    print("\nPrompt library is ready!")
    print("You can now browse and manage prompts in the app.")
    print("=" * 60)
