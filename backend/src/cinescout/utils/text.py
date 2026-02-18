"""Text normalization utilities for film title matching."""

import re


def normalise_title(title: str) -> str:
    """
    Normalize a film title for matching.

    Removes common variations to improve matching accuracy:
    - Year suffixes: "Film (2024)" → "Film"
    - Dash suffixes: "Film — Restoration", "Film - Subtitled" → "Film"
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

    # Remove dash suffixes BEFORE year strip so "Film (1929) — Restoration"
    # becomes "Film (1929)" and the year can then be stripped correctly.
    # Matches hyphen/en-dash/em-dash preceded by whitespace to avoid
    # breaking hyphenated titles like "Spider-Man".
    # Examples: "Film — Restoration", "Film - Subtitled", "Film – Director's Cut"
    title = re.sub(r"\s+[-–—]\s+\S.*$", "", title)

    # Remove year suffixes: "Title (2024)" or "Title (2024-25)"
    title = re.sub(r"\s*\(\d{4}(?:-\d{2,4})?\)\s*$", "", title)

    # Remove square bracket tags: "Title [35mm]", "Title [Q&A]"
    title = re.sub(r"\s*\[[^\]]+\]\s*", " ", title)

    # Remove parenthetical notes at the end: "Title (Director's Cut)"
    # But keep mid-title parentheses like "Mission: Impossible (1996)"
    # Only remove if it's the last element and doesn't contain numbers
    title = re.sub(r"\s*\([^)]*(?<!\d)\)\s*$", "", title)

    # Remove common prefixes — both generic screening types and known event-series names.
    # When a cinema uses "Series Name: Film Title", the series name is stripped so the
    # title can be matched against TMDb. Add new event-series names here as they appear.
    prefixes = [
        # Generic screening descriptors
        r"^Preview:\s+",
        r"^Sneak Preview:\s+",
        r"^Advanced Screening:\s+",
        r"^Special Screening:\s+",
        r"^Member Screening:\s+",
        r"^Q&A:\s+",
        r"^Intro:\s+",
        r"^NT Live:\s+",
        r"^ROH:\s+",  # Royal Opera House
        # Event-series names used by specific cinemas
        r"^Film Club:\s+",
        r"^Dochouse:\s+",
        r"^Doc House:\s+",
        r"^Shorts:\s+",
        r"^Shorts Club:\s+",
        r"^Documentary:\s+",
        r"^Relaxed:\s+",
        r"^Relaxed Screening:\s+",
        r"^Dementia Friendly:\s+",
        r"^Silver Screen:\s+",
        r"^Parent & Baby:\s+",
        r"^Baby Cinema:\s+",
        r"^Autism Friendly:\s+",
    ]
    for prefix in prefixes:
        title = re.sub(prefix, "", title, flags=re.IGNORECASE)

    # Collapse multiple spaces into one
    title = re.sub(r"\s+", " ", title)

    # Remove leading/trailing whitespace again
    title = title.strip()

    return title


def split_double_bill(title: str) -> list[str]:
    """
    Split a double-bill event title into individual film titles.

    Uses a year in parentheses immediately before the conjunction as the
    signal that this is a double bill rather than a single title containing
    "and" (e.g. "Crime and Punishment", "Love and Mercy").

    Examples:
        "The Devil-Doll (1936) and Witchcraft (1964)"
            → ["The Devil-Doll", "Witchcraft"]
        "Near Dark (1987) and Blue Steel (1990)"
            → ["Near Dark", "Blue Steel"]
        "Love Story"  →  ["Love Story"]   (no split)
        "Crime and Punishment"  →  ["Crime and Punishment"]  (no year → no split)

    Returns a list of normalised titles; single-film titles return a
    one-element list.
    """
    # Only split when a year "(YYYY)" immediately precedes " and "
    # so we don't accidentally split titles like "Love and Mercy".
    m = re.match(r'^(.+\(\d{4}\))\s+and\s+(.+)$', title.strip(), re.IGNORECASE)
    if m:
        parts = [normalise_title(m.group(1).strip()), normalise_title(m.group(2).strip())]
        valid = [p for p in parts if p and len(p) >= 2]
        if len(valid) == 2:
            return valid

    return [normalise_title(title)]


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
