"""LLM-powered film title extractor using a local Ollama instance."""

import logging

import httpx

logger = logging.getLogger(__name__)

_OLLAMA_URL = "http://localhost:11434/api/chat"
_MODEL = "llama3.2"

_SYSTEM = """\
You are a film title extractor. Given a raw cinema listing string, return the \
canonical theatrical film title and nothing else — no explanation, no punctuation \
around the title, just the title itself on a single line.

Rules:
- Strip event/season branding prefixes such as "Exhibition on Screen:", \
"Jewish Culture Month:", "[Name] Presents:", "Birthday Season:", "Film Club:", \
"Documentary:", "Shorts:", or any other "Event Name:" pattern before the real title.
- Strip suffixes such as "+ intro by ...", "+ Q&A", "- Birthday Season", \
"Encore", "2026 Encore", "Season", or any descriptive qualifier after the title.
- Keep real subtitles that are part of the film's release title \
(e.g. "2001: A Space Odyssey", "Aliens: Director's Cut", "Mad Max: Fury Road").
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
Preview: The Substance → The Substance\
"""

# In-memory cache: input → extracted title
_cache: dict[str, str] = {}


async def extract_film_title(raw_title: str) -> str:
    """
    Use a local Ollama model to extract the canonical film title.

    Results are cached in-memory so each unique title is only sent to
    Ollama once per process lifetime.  Falls back to returning the input
    unchanged if Ollama is unavailable or returns an empty response.
    """
    key = raw_title.strip()
    if key in _cache:
        return _cache[key]

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                _OLLAMA_URL,
                json={
                    "model": _MODEL,
                    "stream": False,
                    "messages": [
                        {"role": "system", "content": _SYSTEM},
                        {"role": "user", "content": key},
                    ],
                },
            )
            r.raise_for_status()
            result = str(r.json()["message"]["content"]).strip()
    except Exception as e:
        logger.warning(f"Ollama title extraction failed for {key!r}: {e}")
        _cache[key] = key
        return key

    if not result:
        _cache[key] = key
        return key

    _cache[key] = result
    if result != key:
        logger.debug(f"Title extracted: {key!r} → {result!r}")
    return result
