"""Text normalization utilities for film title matching."""

import re


def normalise_title(title: str) -> str:
    """
    Normalize a film title for matching.

    Removes common variations to improve matching accuracy:
    - Year suffixes: "Film (2024)" → "Film"
    - Prefixes: "Preview: Film" → "Film"
    - Format indicators: "Film [35mm]" → "Film"
    - Extra whitespace

    Args:
        title: Raw film title

    Returns:
        Normalized title suitable for matching
    """
    # Remove leading/trailing whitespace
    title = title.strip()

    # Remove year suffixes: "Title (2024)" or "Title (2024-25)"
    title = re.sub(r"\s*\(\d{4}(?:-\d{2,4})?\)\s*$", "", title)

    # Remove square bracket tags: "Title [35mm]", "Title [Q&A]"
    title = re.sub(r"\s*\[[^\]]+\]\s*", " ", title)

    # Remove parenthetical notes at the end: "Title (Director's Cut)"
    # But keep mid-title parentheses like "Mission: Impossible (1996)"
    # Only remove if it's the last element and doesn't contain numbers
    title = re.sub(r"\s*\([^)]*(?<!\d)\)\s*$", "", title)

    # Remove common prefixes
    prefixes = [
        r"^Preview:\s+",
        r"^Sneak Preview:\s+",
        r"^Advanced Screening:\s+",
        r"^Special Screening:\s+",
        r"^Member Screening:\s+",
        r"^Q&A:\s+",
        r"^Intro:\s+",
        r"^NT Live:\s+",
        r"^ROH:\s+",  # Royal Opera House
    ]
    for prefix in prefixes:
        title = re.sub(prefix, "", title, flags=re.IGNORECASE)

    # Collapse multiple spaces into one
    title = re.sub(r"\s+", " ", title)

    # Remove leading/trailing whitespace again
    title = title.strip()

    return title


def slugify(text: str) -> str:
    """
    Convert text to a URL-safe slug.

    Args:
        text: Text to slugify

    Returns:
        Lowercase slug with hyphens
    """
    # Convert to lowercase
    text = text.lower()

    # Replace spaces and underscores with hyphens
    text = re.sub(r"[\s_]+", "-", text)

    # Remove non-alphanumeric characters (except hyphens)
    text = re.sub(r"[^a-z0-9-]", "", text)

    # Remove multiple consecutive hyphens
    text = re.sub(r"-+", "-", text)

    # Strip leading/trailing hyphens
    text = text.strip("-")

    return text
