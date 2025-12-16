#!/usr/bin/env python3
"""Test script for prompt stack functionality."""

import sys
from pathlib import Path

# Add app/src to path
sys.path.insert(0, str(Path(__file__).parent / "app" / "src"))

from prompt_elements import (
    FORMAT_ELEMENTS, STYLE_ELEMENTS, GRAMMAR_ELEMENTS,
    DEFAULT_STACKS, build_prompt_from_elements
)

def test_prompt_elements():
    """Test that all prompt elements are defined correctly."""
    print("=" * 60)
    print("PROMPT ELEMENTS TEST")
    print("=" * 60)

    print(f"\n✓ Format Elements: {len(FORMAT_ELEMENTS)}")
    for key, elem in FORMAT_ELEMENTS.items():
        print(f"  - {elem.name} ({key})")

    print(f"\n✓ Style Elements: {len(STYLE_ELEMENTS)}")
    for key, elem in STYLE_ELEMENTS.items():
        print(f"  - {elem.name} ({key})")

    print(f"\n✓ Grammar Elements: {len(GRAMMAR_ELEMENTS)}")
    for key, elem in GRAMMAR_ELEMENTS.items():
        print(f"  - {elem.name} ({key})")

    print(f"\n✓ Default Stacks: {len(DEFAULT_STACKS)}")
    for stack in DEFAULT_STACKS:
        print(f"  - {stack.name}: {len(stack.elements)} elements")


def test_prompt_building():
    """Test building a prompt from elements."""
    print("\n" + "=" * 60)
    print("PROMPT BUILDING TEST")
    print("=" * 60)

    # Test 1: Quick Email stack
    print("\n--- Test 1: Quick Email Stack ---")
    elements = ["email", "formal", "add_punctuation", "add_paragraphs", "remove_fillers"]
    prompt = build_prompt_from_elements(elements)
    print(f"Generated prompt ({len(prompt)} chars):")
    print(prompt[:500] + "..." if len(prompt) > 500 else prompt)

    # Test 2: Dev Instructions
    print("\n--- Test 2: Dev Instructions ---")
    elements = ["dev_prompt", "technical", "detailed", "add_punctuation"]
    prompt = build_prompt_from_elements(elements)
    print(f"Generated prompt ({len(prompt)} chars):")
    print(prompt[:500] + "..." if len(prompt) > 500 else prompt)

    # Test 3: Simple notes
    print("\n--- Test 3: Simple Notes ---")
    elements = ["bullet_points", "concise"]
    prompt = build_prompt_from_elements(elements)
    print(f"Generated prompt ({len(prompt)} chars):")
    print(prompt)


def test_config_integration():
    """Test config integration."""
    print("\n" + "=" * 60)
    print("CONFIG INTEGRATION TEST")
    print("=" * 60)

    from config import Config, build_cleanup_prompt

    # Test with prompt stacks enabled
    print("\n--- Test: Prompt Stacks Enabled ---")
    config = Config()
    config.use_prompt_stacks = True
    config.prompt_stack_elements = ["todo", "casual", "concise", "remove_fillers"]

    prompt = build_cleanup_prompt(config)
    print(f"Generated cleanup prompt ({len(prompt)} chars):")
    print(prompt[:400] + "..." if len(prompt) > 400 else prompt)

    # Test with prompt stacks disabled (legacy)
    print("\n--- Test: Legacy System (Prompt Stacks Disabled) ---")
    config.use_prompt_stacks = False
    config.format_preset = "email"

    prompt = build_cleanup_prompt(config)
    print(f"Generated cleanup prompt ({len(prompt)} chars):")
    print(prompt[:400] + "..." if len(prompt) > 400 else prompt)


if __name__ == "__main__":
    try:
        test_prompt_elements()
        test_prompt_building()
        test_config_integration()

        print("\n" + "=" * 60)
        print("✓ ALL TESTS PASSED")
        print("=" * 60)
    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
