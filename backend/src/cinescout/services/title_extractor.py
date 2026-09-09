"""LLM-powered film title extractor using a local Ollama instance."""

import logging
import re

import httpx

logger = logging.getLogger(__name__)

_OLLAMA_URL = "http://localhost:11434/api/chat"
_MODEL = "llama3.2"

_SYSTEM = """\
You are a film title extractor. Given a raw cinema listing string, return the \
canonical theatrical film title and nothing else — no explanation, no arrows, \
no punctuation around the title, just the title itself on a single line.

Rules:
- Strip event/season branding prefixes such as "Exhibition on Screen:", \
"Jewish Culture Month:", "[Name] Presents:", "Birthday Season:", "Film Club:", \
"Documentary:", "Shorts:", "Parent & Baby Screening:", "Dog-Friendly Screening:", \
"Seniors' Paid Matinee:", or any other "Event Type:" pattern before the real title.
- Strip suffixes such as "+ intro by ...", "+ Q&A", "- Birthday Season", \
"Encore", "2026 Encore", "Season", "+ Panel Discussion", "+ Discussion", \
"+ Live Recording", or any descriptive qualifier after the title.
- Keep real subtitles that are part of the film's release title \
(e.g. "2001: A Space Odyssey", "Aliens: Director's Cut", "Mad Max: Fury Road", \
"Ready or Not 2: Here I Come").
- Preserve all punctuation that is part of the title, including !, ?, and trailing periods.
- When a person's name precedes a colon and together they form a show or \
documentary title, keep the full title \
(e.g. "James Acaster: Cinemagoers Welcome", "Mercedes Sosa: The Voice Of Latin America").
- When two films appear in a double bill separated by "+", return only the first film \
(e.g. "San Francisco (1968) + Zabriskie Point (1970) + Introduction" → "San Francisco").
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
Dog-Friendly Screening: Wuthering Heights → Wuthering Heights
Parent & Baby Screening: Nosferatu → Nosferatu
RIO FOREVER: ORLANDO ON 35MM WITH SALLY POTTER AND SO MAYER → ORLANDO
RIO FOREVER: APPROPRIATE BEHAVIOUR → APPROPRIATE BEHAVIOUR
Doc'n Roll 2026: A Century in Sound + Director Q&A → A Century in Sound
James Acaster: Cinemagoers Welcome → James Acaster: Cinemagoers Welcome
James Acaster: Cinemagoers Welcome + James Acaster & Stuart Laws Q&A → James Acaster: Cinemagoers Welcome
Mercedes Sosa: The Voice Of Latin America → Mercedes Sosa: The Voice Of Latin America
Chaplin: Spirit of The Tramp → Chaplin: Spirit of The Tramp
FREEWAY: CONFESSIONS OF A TRICKBABY → FREEWAY: CONFESSIONS OF A TRICKBABY
Ready or Not 2: Here I Come → Ready or Not 2: Here I Come
DOA: A RIGHT OF PASSAGE → DOA: A RIGHT OF PASSAGE
Avant-Drag! + Q&A → Avant-Drag!
Good Night, and Good Luck. + Live Recording of PPF Podcast → Good Night, and Good Luck.
Mamma Mia! → Mamma Mia!
Goodbye Breasts! + director Q&A → Goodbye Breasts!
Normal + Ben Wheatley Q&A → Normal
Normal + Q&A with Bob Odenkirk and director Ben Wheatley → Normal
EVERYBODY TO KENMURE STREET + Q&A → EVERYBODY TO KENMURE STREET
Searching for Satyrus + Q&A with Director Rena Effendi → Searching for Satyrus
From Cable Street to Brick Lane + Directors Q&A → From Cable Street to Brick Lane
Enter The Void- Birthday Season → Enter the Void
San Francisco (1968) + Zabriskie Point (1970) + Introduction by series curator → San Francisco
Sporting Love + Marry the Girl + intro by Rosie Rowan Taylor → Sporting Love
Summer of Soul + Funk Is Its Own Reward book launch → Summer of Soul
MilkTea presents – UK Premiere: Last Days + Q&A with actor Sky Yang → Last Days
Bar Trash: Red Sonja → Red Sonja
Queer East: The Outsiders → The Outsiders
Queer East: Queer as Punk → Queer as Punk\
"""

# In-memory cache: input → extracted title
_cache: dict[str, str] = {}

# Strips model chain-of-thought leakage like "Foo Bar → Foo Bar" or "Title → Title"
_ARROW_SUFFIX = re.compile(r"\s*→.*$")


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

    # Strip any " → ..." chain-of-thought leak (e.g. "Foo → Foo" or "X → Y")
    result = _ARROW_SUFFIX.sub("", result).strip()

    # Sanity-check: if the model returned multi-line output or something very long
    # compared to the input, it probably hallucinated — fall back to the raw title.
    first_line = result.splitlines()[0].strip() if result else ""
    if not first_line or len(first_line) > len(key) * 2 + 50:
        logger.warning(f"Ollama returned suspicious output for {key!r}, falling back")
        _cache[key] = key
        return key

    result = first_line
    _cache[key] = result
    if result != key:
        logger.debug(f"Title extracted: {key!r} → {result!r}")
    return result
