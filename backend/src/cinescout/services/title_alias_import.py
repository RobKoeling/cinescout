"""Import title aliases (exported by scripts/export_title_aliases.py).

Each entry maps a cleaned listing title to a film identified by tmdb_id. Films
are looked up by tmdb_id and created from TMDb if missing (film ids can differ
between databases). Existing aliases are never overwritten.
"""

import logging
from typing import Any, Literal, TypedDict

from sqlalchemy import select

from cinescout.database import AsyncSessionLocal
from cinescout.models.film import Film
from cinescout.models.film_alias import FilmAlias
from cinescout.services.film_matcher import FilmMatcher
from cinescout.services.tmdb_client import TMDbClient

logger = logging.getLogger(__name__)

COMMIT_EVERY = 50


class AliasImportStatus(TypedDict):
    status: Literal["idle", "running", "done", "error"]
    total: int
    processed: int
    added: int
    skipped_existing: int
    films_created: int
    missing_film: int
    error: str | None


_status: AliasImportStatus = {
    "status": "idle",
    "total": 0,
    "processed": 0,
    "added": 0,
    "skipped_existing": 0,
    "films_created": 0,
    "missing_film": 0,
    "error": None,
}


def get_alias_import_status() -> AliasImportStatus:
    return _status


def mark_alias_import_pending(total: int) -> None:
    _status["status"] = "running"
    _status["total"] = total
    _status["processed"] = 0
    _status["added"] = 0
    _status["skipped_existing"] = 0
    _status["films_created"] = 0
    _status["missing_film"] = 0
    _status["error"] = None


def validate_entries(data: Any) -> list[dict[str, Any]]:
    """Return clean entries, raising ValueError on a malformed payload."""
    if not isinstance(data, list):
        raise ValueError("Expected a JSON list of alias entries")
    entries = []
    for e in data:
        if not isinstance(e, dict) or not isinstance(e.get("alias"), str) or not isinstance(e.get("tmdb_id"), int):
            raise ValueError(f"Bad entry (need 'alias' str and 'tmdb_id' int): {str(e)[:100]}")
        if not e["alias"].strip() or len(e["alias"]) > 500:
            raise ValueError(f"Bad alias: {e['alias'][:100]!r}")
        entries.append({"alias": e["alias"], "tmdb_id": e["tmdb_id"]})
    return entries


async def import_title_aliases(entries: list[dict[str, Any]]) -> None:
    """Import validated entries. Call mark_alias_import_pending first."""
    try:
        async with AsyncSessionLocal() as db:
            existing = set((await db.execute(select(FilmAlias.normalized_title))).scalars().all())
            matcher = FilmMatcher(db, TMDbClient())
            film_ids: dict[int, str | None] = {}

            for i, e in enumerate(entries, 1):
                alias, tmdb_id = e["alias"], e["tmdb_id"]
                _status["processed"] = i
                if alias in existing:
                    _status["skipped_existing"] += 1
                    continue

                if tmdb_id not in film_ids:
                    film = (await db.execute(select(Film).where(Film.tmdb_id == tmdb_id))).scalar_one_or_none()
                    if film is None:
                        film = await matcher.match_by_tmdb_id(tmdb_id)
                        if film is not None:
                            _status["films_created"] += 1
                    film_ids[tmdb_id] = film.id if film else None

                film_id = film_ids[tmdb_id]
                if film_id is None:
                    _status["missing_film"] += 1
                    continue

                db.add(FilmAlias(normalized_title=alias, film_id=film_id))
                existing.add(alias)
                _status["added"] += 1
                if i % COMMIT_EVERY == 0:
                    await db.commit()

            await db.commit()
        _status["status"] = "done"
    except Exception as exc:
        logger.error(f"Alias import failed: {exc}", exc_info=True)
        _status["status"] = "error"
        _status["error"] = str(exc)
