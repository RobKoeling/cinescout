"""LLM-powered film title extractor with in-memory cache."""

import logging

from anthropic import AsyncAnthropic

from cinescout.config import settings

logger = logging.getLogger(__name__)

_MODEL = "claude-haiku-4-5-20251001"

_SYSTEM = """\
You are a film title extractor. Given a raw cinema listing string, return the \
canonical theatrical film title and nothing else — no explanation, no punctuation \
around the title, just the title itself.

Rules:
- Strip event/season branding prefixes such as "Exhibition on Screen:", \
"Jewish Culture Month:", "[Name] Presents:", "Birthday Season:", "Film Club:", \
"Documentary:", "Shorts:", or any other "Event Name:" pattern before the real title.
- Strip suffixes such as "+ intro by ...", "+ Q&A", "- Birthday Season", \
"Encore", "2026 Encore", "Season", or any descriptive qualifier after the title.
- Keep real subtitles that are part of the film's release title \
(e.g. "2001: A Space Odyssey", "Aliens: Directors Cut", "Mad Max: Fury Road").
- If the title is already clean, return it unchanged.

Examples (input → output):
EXHIBITION ON SCREEN: Frida Kahlo 2026 Encore → Frida Kahlo
Jewish Culture Month: Menashe → Menashe
Reece Shearsmith Presents: The Bounty + intro by Reece Shearsmith → The Bounty
Tokyo Story- Birthday Season → Tokyo Story
Mandy + intro by Josephine Botting, Curator, BFI National Archive → Mandy
2001: A Space Odyssey → 2001: A Space Odyssey
Mad Max: Fury Road → Mad Max: Fury Road
The Godfather → The Godfather
Aliens: Director's Cut → Aliens: Director's Cut
Preview: The Substance → The Substance
"""

# In-memory cache: normalised input → extracted title
_cache: dict[str, str] = {}


async def extract_film_title(raw_title: str) -> str:
    """
    Use Claude Haiku to extract the canonical film title from a raw cinema string.

    Results are cached in-memory for the lifetime of the process so each unique
    title is only sent to the API once per scrape run.

    Falls back to returning ``raw_title`` unchanged if the API call fails.
    """
    key = raw_title.strip()
    if key in _cache:
        return _cache[key]

    api_key = settings.anthropic_api_key
    if not api_key:
        logger.debug("ANTHROPIC_API_KEY not set — skipping LLM title extraction")
        _cache[key] = key
        return key

    try:
        client = AsyncAnthropic(api_key=api_key)
        response = await client.messages.create(
            model=_MODEL,
            max_tokens=80,
            system=_SYSTEM,
            messages=[{"role": "user", "content": key}],
        )
        result = response.content[0].text.strip()  # type: ignore[union-attr]
        if result:
            _cache[key] = result
            if result != key:
                logger.debug(f"Title extracted: {key!r} → {result!r}")
            return result
    except Exception as e:
        logger.warning(f"LLM title extraction failed for {key!r}: {e}")

    _cache[key] = key
    return key
