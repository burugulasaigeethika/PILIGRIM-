import os
import re
from typing import Dict, Any, List

def format_temple_name(dir_name: str) -> str:
    """Format a directory name into a title-cased temple name."""
    cleaned = dir_name.strip()
    return cleaned.title()

def clean_text(text: str) -> str:
    """Clean and normalize whitespace in text while preserving newlines."""
    if not isinstance(text, str):
        return str(text)
    lines = [line.rstrip() for line in text.splitlines()]
    return "\n".join(lines).strip()

def sanitize_json_value(val: Any) -> str:
    """Convert any JSON value into a human-readable clean string representation."""
    if val is None:
        return ""
    if isinstance(val, bool):
        return "Yes" if val else "No"
    if isinstance(val, (int, float)):
        return str(val)
    if isinstance(val, str):
        return val.strip()
    return str(val)
