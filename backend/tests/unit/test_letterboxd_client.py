"""Unit tests for the Letterboxd RSS client.

The sample feed below mirrors the real structure of a Letterboxd diary RSS
feed (verified against a live public profile during development), including
a non-diary item (no watchedDate) to confirm it's correctly skipped.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from cinescout.services.letterboxd_client import LetterboxdClient

SAMPLE_FEED = """<?xml version='1.0' encoding='utf-8'?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:letterboxd="https://letterboxd.com" xmlns:tmdb="https://themoviedb.org">
<channel>
<title>Letterboxd - testuser</title>
<link>https://letterboxd.com/testuser/</link>
<item>
<title>Magazine Dreams, 2023 - &#9733;&#9733;&#9733;&#189;</title>
<link>https://letterboxd.com/testuser/film/magazine-dreams/</link>
<guid isPermaLink="false">letterboxd-watch-1</guid>
<pubDate>Sat, 5 Sep 2026 06:15:40 +1200</pubDate>
<letterboxd:watchedDate>2026-09-04</letterboxd:watchedDate>
<letterboxd:rewatch>No</letterboxd:rewatch>
<letterboxd:filmTitle>Magazine Dreams</letterboxd:filmTitle>
<letterboxd:filmYear>2023</letterboxd:filmYear>
<letterboxd:memberRating>3.5</letterboxd:memberRating>
<tmdb:movieId>784524</tmdb:movieId>
<dc:creator>testuser</dc:creator>
</item>
<item>
<title>Frailty, 2001 - &#9733;&#9733;&#9733;&#189; (rewatch)</title>
<link>https://letterboxd.com/testuser/film/frailty/</link>
<guid isPermaLink="false">letterboxd-watch-2</guid>
<pubDate>Thu, 3 Sep 2026 06:30:17 +1200</pubDate>
<letterboxd:watchedDate>2026-09-02</letterboxd:watchedDate>
<letterboxd:rewatch>Yes</letterboxd:rewatch>
<letterboxd:filmTitle>Frailty</letterboxd:filmTitle>
<letterboxd:filmYear>2001</letterboxd:filmYear>
<letterboxd:memberRating>3.5</letterboxd:memberRating>
<tmdb:movieId>12149</tmdb:movieId>
<dc:creator>testuser</dc:creator>
</item>
<item>
<title>A film with no rating logged</title>
<link>https://letterboxd.com/testuser/film/unrated-film/</link>
<guid isPermaLink="false">letterboxd-watch-3</guid>
<letterboxd:watchedDate>2026-08-30</letterboxd:watchedDate>
<letterboxd:rewatch>No</letterboxd:rewatch>
<letterboxd:filmTitle>Unrated Film</letterboxd:filmTitle>
<letterboxd:filmYear>2020</letterboxd:filmYear>
<dc:creator>testuser</dc:creator>
</item>
<item>
<title>testuser's list: My Favourites</title>
<link>https://letterboxd.com/testuser/list/my-favourites/</link>
<guid isPermaLink="false">letterboxd-list-1</guid>
<dc:creator>testuser</dc:creator>
</item>
</channel>
</rss>
"""


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


class TestFetchDiary:
    async def test_parses_watched_entries_from_sample_feed(self) -> None:
        client = LetterboxdClient()
        with patch("httpx.AsyncClient.get", AsyncMock(return_value=make_response(text=SAMPLE_FEED))):
            entries = await client.fetch_diary("testuser")

        assert entries is not None
        assert len(entries) == 3  # the list item has no watchedDate and is skipped

        assert entries[0].film_title == "Magazine Dreams"
        assert entries[0].film_year == 2023
        assert entries[0].rating == 3.5
        assert entries[0].rewatch is False
        assert entries[0].tmdb_id == 784524
        assert entries[0].letterboxd_url == "https://letterboxd.com/testuser/film/magazine-dreams/"

        assert entries[1].rewatch is True

    def test_skips_items_without_watched_date(self) -> None:
        client = LetterboxdClient()
        entries = client._parse_diary(SAMPLE_FEED)
        titles = [e.film_title for e in entries]
        assert "My Favourites" not in " ".join(titles)
        assert len(entries) == 3

    def test_handles_missing_optional_fields(self) -> None:
        client = LetterboxdClient()
        entries = client._parse_diary(SAMPLE_FEED)
        unrated = next(e for e in entries if e.film_title == "Unrated Film")
        assert unrated.rating is None
        assert unrated.tmdb_id is None

    async def test_returns_none_on_404(self) -> None:
        client = LetterboxdClient()
        with patch("httpx.AsyncClient.get", AsyncMock(return_value=make_response(status_code=404))):
            entries = await client.fetch_diary("nonexistent-user")
        assert entries is None

    async def test_returns_none_on_network_error(self) -> None:
        client = LetterboxdClient()
        with patch("httpx.AsyncClient.get", AsyncMock(side_effect=httpx.ConnectError("boom"))):
            entries = await client.fetch_diary("testuser")
        assert entries is None

    async def test_returns_empty_list_for_valid_feed_with_no_items(self) -> None:
        client = LetterboxdClient()
        empty_feed = (
            '<?xml version="1.0"?><rss xmlns:letterboxd="https://letterboxd.com" '
            'xmlns:tmdb="https://themoviedb.org"><channel></channel></rss>'
        )
        with patch("httpx.AsyncClient.get", AsyncMock(return_value=make_response(text=empty_feed))):
            entries = await client.fetch_diary("testuser")
        assert entries == []

    async def test_returns_none_on_malformed_xml(self) -> None:
        client = LetterboxdClient()
        with patch(
            "httpx.AsyncClient.get", AsyncMock(return_value=make_response(text="not xml at all <<<"))
        ):
            entries = await client.fetch_diary("testuser")
        assert entries is None


class TestProfileExists:
    async def test_returns_true_for_reachable_profile(self) -> None:
        client = LetterboxdClient()
        with patch("httpx.AsyncClient.get", AsyncMock(return_value=make_response(status_code=200))):
            assert await client.profile_exists("testuser") is True

    async def test_returns_false_for_404(self) -> None:
        client = LetterboxdClient()
        with patch("httpx.AsyncClient.get", AsyncMock(return_value=make_response(status_code=404))):
            assert await client.profile_exists("testuser") is False

    async def test_returns_none_on_network_error(self) -> None:
        client = LetterboxdClient()
        with patch("httpx.AsyncClient.get", AsyncMock(side_effect=httpx.ConnectError("boom"))):
            assert await client.profile_exists("testuser") is None


@pytest.mark.live
class TestFetchDiaryLive:
    async def test_fetches_a_real_public_profile(self) -> None:
        client = LetterboxdClient()
        entries = await client.fetch_diary("scottn")
        assert entries is not None
        assert len(entries) > 0
