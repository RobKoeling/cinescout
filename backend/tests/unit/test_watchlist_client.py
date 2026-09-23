"""Unit tests for LetterboxdClient.fetch_watchlist.

The sample HTML snippets below mirror the real structure of a Letterboxd
watchlist page (verified against a live public profile during development):
each poster entry carries a `data-item-full-display-name="Title (Year)"`
attribute, with no TMDb id available.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from cinescout.services.letterboxd_client import LetterboxdClient

PAGE_1 = """
<li class="poster-container">
  <div data-item-full-display-name="Clayface (2026)" data-target-link="/film/clayface/">
    <div class="poster film-poster"></div>
  </div>
</li>
<li class="poster-container">
  <div data-item-full-display-name="Coyote vs. Acme" data-target-link="/film/coyote-vs-acme/">
    <div class="poster film-poster"></div>
  </div>
</li>
"""

EMPTY_PAGE = "<div>No films here</div>"


def make_response(status_code: int = 200, text: str = "") -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=resp
        )
    return resp


class TestFetchWatchlist:
    async def test_parses_entries_and_splits_off_year(self) -> None:
        client = LetterboxdClient()
        responses = [make_response(text=PAGE_1), make_response(text=EMPTY_PAGE)]
        with patch("httpx.AsyncClient.get", AsyncMock(side_effect=responses)):
            entries = await client.fetch_watchlist("testuser")

        assert entries is not None
        assert len(entries) == 2
        assert entries[0].title == "Clayface"
        assert entries[0].year == 2026
        assert entries[1].title == "Coyote vs. Acme"
        assert entries[1].year is None

    async def test_stops_pagination_on_empty_page(self) -> None:
        client = LetterboxdClient()
        responses = [make_response(text=PAGE_1), make_response(text=EMPTY_PAGE)]
        with patch("httpx.AsyncClient.get", AsyncMock(side_effect=responses)) as mock_get:
            await client.fetch_watchlist("testuser")
        assert mock_get.await_count == 2

    async def test_returns_none_on_404_first_page(self) -> None:
        client = LetterboxdClient()
        with patch("httpx.AsyncClient.get", AsyncMock(return_value=make_response(status_code=404))):
            entries = await client.fetch_watchlist("nonexistent-user")
        assert entries is None

    async def test_returns_empty_list_for_confirmed_empty_watchlist(self) -> None:
        client = LetterboxdClient()
        with patch("httpx.AsyncClient.get", AsyncMock(return_value=make_response(text=EMPTY_PAGE))):
            entries = await client.fetch_watchlist("testuser")
        assert entries == []

    async def test_returns_none_on_network_error(self) -> None:
        client = LetterboxdClient()
        with patch("httpx.AsyncClient.get", AsyncMock(side_effect=httpx.ConnectError("boom"))):
            entries = await client.fetch_watchlist("testuser")
        assert entries is None

    async def test_unescapes_html_entities_in_title(self) -> None:
        client = LetterboxdClient()
        page = '<div data-item-full-display-name="Amélie &amp; Friends (2001)"></div>'
        with patch("httpx.AsyncClient.get", AsyncMock(return_value=make_response(text=page))):
            entries = await client.fetch_watchlist("testuser")
        assert entries is not None
        assert entries[0].title == "Amélie & Friends"
        assert entries[0].year == 2001


@pytest.mark.live
class TestFetchWatchlistLive:
    async def test_fetches_a_real_public_watchlist(self) -> None:
        client = LetterboxdClient()
        entries = await client.fetch_watchlist("dave")
        assert entries is not None
