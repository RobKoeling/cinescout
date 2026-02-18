"""Tests for the TMDb API client."""

from unittest.mock import AsyncMock, MagicMock, patch

from cinescout.services.tmdb_client import TMDbClient


# ---------------------------------------------------------------------------
# Sample fixture data
# ---------------------------------------------------------------------------

SAMPLE_SEARCH_RESPONSE = {
    "results": [
        {
            "id": 12345,
            "title": "Nosferatu",
            "release_date": "2024-12-25",
            "overview": "A horror film.",
            "poster_path": "/nosferatu.jpg",
        }
    ]
}

SAMPLE_DETAILS_RESPONSE = {
    "id": 12345,
    "title": "Nosferatu",
    "release_date": "2024-12-25",
    "runtime": 132,
    "production_countries": [
        {"name": "United States of America"},
        {"name": "Germany"},
    ],
    "credits": {
        "crew": [
            {"name": "Robert Eggers", "job": "Director"},
            {"name": "John Smith", "job": "Producer"},
        ],
        "cast": [
            {"name": "Bill Skarsgård"},
            {"name": "Lily-Rose Depp"},
            {"name": "Nicholas Hoult"},
            {"name": "Aaron Taylor-Johnson"},
        ],
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_http_response(json_data: dict, status_code: int = 200) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = json_data
    if status_code >= 400:
        response.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    else:
        response.raise_for_status = MagicMock()
    return response


def make_async_client_ctx(response: MagicMock) -> AsyncMock:
    """Return an async context manager whose .get() always returns *response*."""
    inner = AsyncMock()
    inner.get = AsyncMock(return_value=response)
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=inner)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


# ---------------------------------------------------------------------------
# search_film
# ---------------------------------------------------------------------------


class TestSearchFilm:
    async def test_returns_none_without_api_key(self) -> None:
        client = TMDbClient(api_key="dummy")
        client.api_key = None  # type: ignore[assignment]
        result = await client.search_film("Nosferatu")
        assert result is None

    async def test_returns_first_result_on_success(self) -> None:
        client = TMDbClient(api_key="test-key")
        ctx = make_async_client_ctx(make_http_response(SAMPLE_SEARCH_RESPONSE))
        with patch("httpx.AsyncClient", return_value=ctx):
            result = await client.search_film("Nosferatu")
        assert result is not None
        assert result["id"] == 12345
        assert result["title"] == "Nosferatu"

    async def test_includes_year_in_params_when_provided(self) -> None:
        client = TMDbClient(api_key="test-key")
        ctx = make_async_client_ctx(make_http_response(SAMPLE_SEARCH_RESPONSE))
        with patch("httpx.AsyncClient", return_value=ctx):
            await client.search_film("Nosferatu", year=2024)
        params = ctx.__aenter__.return_value.get.call_args.kwargs["params"]
        assert params["year"] == 2024

    async def test_does_not_include_year_when_not_provided(self) -> None:
        client = TMDbClient(api_key="test-key")
        ctx = make_async_client_ctx(make_http_response(SAMPLE_SEARCH_RESPONSE))
        with patch("httpx.AsyncClient", return_value=ctx):
            await client.search_film("Nosferatu")
        params = ctx.__aenter__.return_value.get.call_args.kwargs["params"]
        assert "year" not in params

    async def test_returns_none_when_results_empty(self) -> None:
        client = TMDbClient(api_key="test-key")
        ctx = make_async_client_ctx(make_http_response({"results": []}))
        with patch("httpx.AsyncClient", return_value=ctx):
            result = await client.search_film("UnknownFilm")
        assert result is None

    async def test_returns_none_on_http_error(self) -> None:
        client = TMDbClient(api_key="test-key")
        ctx = make_async_client_ctx(make_http_response({}, status_code=500))
        with patch("httpx.AsyncClient", return_value=ctx):
            result = await client.search_film("Nosferatu")
        assert result is None

    async def test_returns_none_on_network_error(self) -> None:
        client = TMDbClient(api_key="test-key")
        inner = AsyncMock()
        inner.get = AsyncMock(side_effect=Exception("Connection refused"))
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=inner)
        ctx.__aexit__ = AsyncMock(return_value=False)
        with patch("httpx.AsyncClient", return_value=ctx):
            result = await client.search_film("Nosferatu")
        assert result is None

    async def test_uses_language_en_gb(self) -> None:
        client = TMDbClient(api_key="test-key")
        ctx = make_async_client_ctx(make_http_response(SAMPLE_SEARCH_RESPONSE))
        with patch("httpx.AsyncClient", return_value=ctx):
            await client.search_film("Nosferatu")
        params = ctx.__aenter__.return_value.get.call_args.kwargs["params"]
        assert params["language"] == "en-GB"


# ---------------------------------------------------------------------------
# get_film_details
# ---------------------------------------------------------------------------


class TestGetFilmDetails:
    async def test_returns_none_without_api_key(self) -> None:
        client = TMDbClient(api_key="dummy")
        client.api_key = None  # type: ignore[assignment]
        result = await client.get_film_details(12345)
        assert result is None

    async def test_returns_film_details_on_success(self) -> None:
        client = TMDbClient(api_key="test-key")
        ctx = make_async_client_ctx(make_http_response(SAMPLE_DETAILS_RESPONSE))
        with patch("httpx.AsyncClient", return_value=ctx):
            result = await client.get_film_details(12345)
        assert result is not None
        assert result["id"] == 12345
        assert result["runtime"] == 132

    async def test_appends_credits_to_request(self) -> None:
        client = TMDbClient(api_key="test-key")
        ctx = make_async_client_ctx(make_http_response(SAMPLE_DETAILS_RESPONSE))
        with patch("httpx.AsyncClient", return_value=ctx):
            await client.get_film_details(12345)
        params = ctx.__aenter__.return_value.get.call_args.kwargs["params"]
        assert params["append_to_response"] == "credits"

    async def test_calls_correct_endpoint(self) -> None:
        client = TMDbClient(api_key="test-key")
        ctx = make_async_client_ctx(make_http_response(SAMPLE_DETAILS_RESPONSE))
        with patch("httpx.AsyncClient", return_value=ctx):
            await client.get_film_details(99)
        url = ctx.__aenter__.return_value.get.call_args.args[0]
        assert url.endswith("/movie/99")

    async def test_returns_none_on_http_error(self) -> None:
        client = TMDbClient(api_key="test-key")
        ctx = make_async_client_ctx(make_http_response({}, status_code=404))
        with patch("httpx.AsyncClient", return_value=ctx):
            result = await client.get_film_details(99999)
        assert result is None

    async def test_returns_none_on_network_error(self) -> None:
        client = TMDbClient(api_key="test-key")
        inner = AsyncMock()
        inner.get = AsyncMock(side_effect=Exception("Timeout"))
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=inner)
        ctx.__aexit__ = AsyncMock(return_value=False)
        with patch("httpx.AsyncClient", return_value=ctx):
            result = await client.get_film_details(12345)
        assert result is None


# ---------------------------------------------------------------------------
# extract_directors
# ---------------------------------------------------------------------------


class TestExtractDirectors:
    def test_extracts_director_names(self) -> None:
        client = TMDbClient(api_key="key")
        directors = client.extract_directors(SAMPLE_DETAILS_RESPONSE["credits"])
        assert directors == ["Robert Eggers"]

    def test_excludes_non_director_crew(self) -> None:
        client = TMDbClient(api_key="key")
        credits = {"crew": [{"name": "Jane Doe", "job": "Producer"}]}
        assert client.extract_directors(credits) == []

    def test_returns_empty_list_when_crew_missing(self) -> None:
        client = TMDbClient(api_key="key")
        assert client.extract_directors({}) == []

    def test_returns_multiple_directors(self) -> None:
        client = TMDbClient(api_key="key")
        credits = {
            "crew": [
                {"name": "Stanley Donen", "job": "Director"},
                {"name": "Gene Kelly", "job": "Director"},
                {"name": "Someone Else", "job": "Cinematographer"},
            ]
        }
        assert client.extract_directors(credits) == ["Stanley Donen", "Gene Kelly"]


# ---------------------------------------------------------------------------
# extract_countries
# ---------------------------------------------------------------------------


class TestExtractCountries:
    def test_extracts_country_names(self) -> None:
        client = TMDbClient(api_key="key")
        result = client.extract_countries(SAMPLE_DETAILS_RESPONSE)
        assert result == ["United States of America", "Germany"]

    def test_returns_empty_list_when_no_countries(self) -> None:
        client = TMDbClient(api_key="key")
        assert client.extract_countries({"production_countries": []}) == []

    def test_returns_empty_list_when_field_missing(self) -> None:
        client = TMDbClient(api_key="key")
        assert client.extract_countries({}) == []


# ---------------------------------------------------------------------------
# extract_cast
# ---------------------------------------------------------------------------


class TestExtractCast:
    def test_extracts_top_three_by_default(self) -> None:
        client = TMDbClient(api_key="key")
        cast = client.extract_cast(SAMPLE_DETAILS_RESPONSE["credits"])
        assert cast == ["Bill Skarsgård", "Lily-Rose Depp", "Nicholas Hoult"]

    def test_respects_n_parameter(self) -> None:
        client = TMDbClient(api_key="key")
        cast = client.extract_cast(SAMPLE_DETAILS_RESPONSE["credits"], n=1)
        assert cast == ["Bill Skarsgård"]

    def test_returns_all_when_fewer_than_n(self) -> None:
        client = TMDbClient(api_key="key")
        credits = {"cast": [{"name": "Only Actor"}]}
        cast = client.extract_cast(credits, n=5)
        assert cast == ["Only Actor"]

    def test_returns_empty_list_when_cast_missing(self) -> None:
        client = TMDbClient(api_key="key")
        assert client.extract_cast({}) == []
