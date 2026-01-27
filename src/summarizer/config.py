"""
Configuration management for smart-pigeon (formerly work-journal-summarizer).

This module handles loading settings from config.yaml with sensible defaults.
The config file is optional - everything works with defaults for quick setup.

Configuration hierarchy:
1. config/config.yaml (if exists)
2. Built-in defaults (if config missing or key not specified)

Why YAML?
- Human-readable and editable
- Supports comments (unlike JSON)
- Python has good YAML library support
- Standard for config files in modern tools
"""

from pathlib import Path
from typing import Any

import yaml  # PyYAML - installed via: uv add pyyaml


# ---------------------------------------------------------------------------
# Config File Paths
# ---------------------------------------------------------------------------

def get_project_root() -> Path:
    """
    Get the project root directory.

    We navigate up from this file's location to find the project root.
    This file is at: src/summarizer/config.py
    Project root is: ../../ from here

    Syntax notes:
    - __file__ is a special variable containing this file's path
    - Path(__file__) converts it to a Path object
    - .resolve() makes it absolute (removes any .. or symlinks)
    - .parent gets the containing directory

    Returns:
        Path to the project root directory
    """
    # This file: src/summarizer/config.py
    # Parent 1:   src/summarizer/
    # Parent 2:   src/
    # Parent 3:   project root
    return Path(__file__).resolve().parent.parent.parent


def get_config_path() -> Path:
    """
    Get the path to the config file.

    Returns:
        Path to config/config.yaml
    """
    return get_project_root() / "config" / "config.yaml"


# ---------------------------------------------------------------------------
# Default Configuration
# ---------------------------------------------------------------------------

# These defaults are used when config.yaml is missing or a key isn't set.
# They represent sensible values for Sean's setup.
#
# Structure mirrors the YAML file for easy mental mapping.

DEFAULT_CONFIG = {
    "journal": {
        "path": "~/code-directory-top/_meta/work-journal",
        "summary_prefix": "SUMMARY-14-days",
        "lookback_days": 14,
        # Subfolder structure (new Jan 2026)
        "entries_subfolder": "daily-entries",
        "summaries_subfolder": "periodic-summaries",
        "staging_subfolder": "daily-staging",
    },
    "email": {
        "to": "sean@das.llc",
        "from": "robots@das.llc",
        "subject_prefix": "[Work Journal]",
    },
    "anthropic": {
        # Latest models as of Jan 2026 (from Anthropic announcements)
        # claude-sonnet-4-5: Best for coding, agents, complex reasoning
        # claude-haiku-4-5: 4-5x faster than Sonnet, ideal for classification
        "summary_model": "claude-sonnet-4-5",
        "classify_model": "claude-haiku-4-5",
        "max_tokens": 4096,
    },
    "secrets": {
        "base_path": "~/.secrets",
        "shared_folder": "shared",
        "project_folder": "smart-pigeon",
    },
}


# ---------------------------------------------------------------------------
# Config Loading
# ---------------------------------------------------------------------------

def load_config() -> dict:
    """
    Load configuration from file, falling back to defaults.

    Merge strategy:
    - Start with DEFAULT_CONFIG
    - If config.yaml exists, overlay its values
    - Missing keys in YAML use defaults
    - Extra keys in YAML are preserved

    Syntax notes:
    - dict.update() merges another dict into the first
    - We do a "deep merge" manually for nested dicts
    - YAML parsing returns Python dicts/lists directly

    Returns:
        Configuration dictionary with all settings
    """
    config = _deep_copy(DEFAULT_CONFIG)

    config_path = get_config_path()
    if config_path.exists():
        try:
            # yaml.safe_load() parses YAML to Python objects
            # "safe" means it won't execute arbitrary Python (security)
            with open(config_path) as f:
                user_config = yaml.safe_load(f)

            if user_config:
                # Deep merge user config over defaults
                config = _deep_merge(config, user_config)

        except yaml.YAMLError as e:
            print(f"Warning: Error parsing config.yaml: {e}")
            print("Using default configuration.")

    return config


def _deep_copy(d: dict) -> dict:
    """
    Create a deep copy of a nested dictionary.

    We can't just use d.copy() because that's shallow -
    nested dicts would still reference the originals.

    Args:
        d: Dictionary to copy

    Returns:
        New dictionary with all nested dicts also copied
    """
    result = {}
    for key, value in d.items():
        if isinstance(value, dict):
            result[key] = _deep_copy(value)
        else:
            result[key] = value
    return result


def _deep_merge(base: dict, overlay: dict) -> dict:
    """
    Deep merge overlay into base, returning a new dict.

    - Keys in overlay overwrite keys in base
    - Nested dicts are merged recursively
    - Lists and other values are replaced entirely

    Args:
        base: Base configuration (defaults)
        overlay: User configuration to merge in

    Returns:
        Merged configuration
    """
    result = _deep_copy(base)

    for key, value in overlay.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            # Both are dicts - merge recursively
            result[key] = _deep_merge(result[key], value)
        else:
            # Replace the value
            result[key] = value

    return result


# ---------------------------------------------------------------------------
# Config Access Helpers
# ---------------------------------------------------------------------------

# Global config cache - loaded once, reused
_config_cache: dict | None = None


def get_config() -> dict:
    """
    Get the configuration, loading it if necessary.

    Uses a module-level cache so we only parse YAML once.

    Returns:
        Configuration dictionary
    """
    global _config_cache
    if _config_cache is None:
        _config_cache = load_config()
    return _config_cache


def get(key_path: str, default: Any = None) -> Any:
    """
    Get a config value using dot-notation path.

    This is a convenience function for accessing nested values.

    Examples:
        get("email.to")  # Returns "sean@das.llc"
        get("anthropic.summary_model")  # Returns "claude-sonnet-4-20250514"
        get("nonexistent.key", "fallback")  # Returns "fallback"

    Syntax notes:
    - .split(".") breaks "a.b.c" into ["a", "b", "c"]
    - We traverse the dict using each key in sequence
    - If any key is missing, we return the default

    Args:
        key_path: Dot-separated path like "email.to" or "anthropic.model"
        default: Value to return if path not found

    Returns:
        The config value, or default if not found
    """
    config = get_config()
    keys = key_path.split(".")

    value = config
    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return default

    return value


# ---------------------------------------------------------------------------
# Path Expansion
# ---------------------------------------------------------------------------

def expand_path(path_str: str) -> Path:
    """
    Expand a path string to a full Path object.

    Handles:
    - ~ expansion (home directory)
    - Converts to absolute path

    Args:
        path_str: Path string, possibly with ~ prefix

    Returns:
        Expanded Path object
    """
    return Path(path_str).expanduser().resolve()


def get_journal_path() -> Path:
    """Get the configured journal path as a Path object."""
    return expand_path(get("journal.path"))


def get_entries_path() -> Path:
    """Get the path to daily journal entries (daily-entries/)."""
    return get_journal_path() / get("journal.entries_subfolder", "daily-entries")


def get_summaries_path() -> Path:
    """Get the path to periodic summaries (periodic-summaries/)."""
    return get_journal_path() / get("journal.summaries_subfolder", "periodic-summaries")


def get_staging_path() -> Path:
    """Get the path to checkpoint staging (daily-staging/)."""
    return get_journal_path() / get("journal.staging_subfolder", "daily-staging")


def get_secrets_base_path() -> Path:
    """Get the base secrets path (~/.secrets)."""
    return expand_path(get("secrets.base_path"))


def get_shared_secrets_path() -> Path:
    """Get the shared secrets path (~/.secrets/shared/)."""
    return get_secrets_base_path() / get("secrets.shared_folder")


def get_project_secrets_path() -> Path:
    """Get this project's secrets path (~/.secrets/smart-pigeon/)."""
    return get_secrets_base_path() / get("secrets.project_folder")


# ---------------------------------------------------------------------------
# Testing
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Quick test: print current configuration
    print("Current configuration:")
    print("-" * 40)

    import json
    config = get_config()
    print(json.dumps(config, indent=2))

    print("-" * 40)
    print(f"Journal path: {get_journal_path()}")
    print(f"Email to: {get('email.to')}")
    print(f"Summary model: {get('anthropic.summary_model')}")
