"""Unit tests for distance enrichment function."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cinescout.models import Cinema
from cinescout.api.routes.showings import enrich_cinemas_with_distance


@pytest.fixture
def sample_london_cinema():
    """Create a sample London cinema."""
    return Cinema(
        id="bfi-southbank",
        name="BFI Southbank",
        city="london",
        address="Belvedere Rd",
        postcode="SE1 8XT",
        latitude=51.5067,
        longitude=-0.1154,
        scraper_type="bfi",
        scraper_config={},
        has_online_booking=True,
        supports_availability_check=False,
    )


@pytest.fixture
def sample_brighton_cinema():
    """Create a sample Brighton cinema."""
    return Cinema(
        id="depot-lewes",
        name="Depot Lewes",
        city="brighton",
        address="1 Depot St",
        postcode="BN7 2AG",
        latitude=50.8733,
        longitude=0.0127,
        scraper_type="depot",
        scraper_config={},
        has_online_booking=True,
        supports_availability_check=False,
    )


@pytest.mark.asyncio
async def test_enrich_calculates_haversine_distance(sample_london_cinema):
    """Test that enrichment always calculates straight-line distance."""
    cinemas = [sample_london_cinema]

    # User location: Trafalgar Square (51.5080, -0.1281)
    await enrich_cinemas_with_distance(
        cinemas=cinemas,
        user_lat=51.5080,
        user_lng=-0.1281,
        use_tfl=False,
        transport_mode="public",
    )

    # Check distance was calculated
    assert sample_london_cinema.distance_km is not None
    assert sample_london_cinema.distance_miles is not None

    # BFI Southbank to Trafalgar Square is about 0.8-1.0 km
    assert 0.7 < sample_london_cinema.distance_km < 1.1

    # Check miles conversion
    expected_miles = round(sample_london_cinema.distance_km * 0.621371, 2)
    assert sample_london_cinema.distance_miles == expected_miles

    # No TfL data since use_tfl=False
    assert not hasattr(sample_london_cinema, "travel_time_minutes") or sample_london_cinema.travel_time_minutes is None
    assert not hasattr(sample_london_cinema, "travel_mode") or sample_london_cinema.travel_mode is None


@pytest.mark.asyncio
async def test_enrich_skips_cinemas_without_coordinates():
    """Test that cinemas with missing coordinates are skipped."""
    cinema_no_coords = Cinema(
        id="test-no-coords",
        name="Cinema Without Coords",
        city="london",
        address="123 Test St",
        postcode="SW1A 1AA",
        latitude=None,
        longitude=None,
        scraper_type="placeholder",
        scraper_config={},
        has_online_booking=False,
        supports_availability_check=False,
    )

    cinemas = [cinema_no_coords]

    await enrich_cinemas_with_distance(
        cinemas=cinemas,
        user_lat=51.5080,
        user_lng=-0.1281,
        use_tfl=False,
        transport_mode="public",
    )

    # Cinema should not have distance fields populated
    assert not hasattr(cinema_no_coords, "distance_km") or cinema_no_coords.distance_km is None
    assert not hasattr(cinema_no_coords, "distance_miles") or cinema_no_coords.distance_miles is None


@pytest.mark.asyncio
async def test_enrich_with_tfl_calls_api_for_london_only(
    sample_london_cinema, sample_brighton_cinema
):
    """Test that TfL API is only called for London cinemas."""
    cinemas = [sample_london_cinema, sample_brighton_cinema]

    # Mock TfL client
    mock_tfl_result = {
        "distance_meters": 800,
        "duration_minutes": 10,
        "status": "ok",
    }

    with patch("cinescout.services.tfl_client.TfLClient") as MockTfLClient:
        mock_client = MockTfLClient.return_value
        mock_client.get_journey_time = AsyncMock(return_value=mock_tfl_result)

        await enrich_cinemas_with_distance(
            cinemas=cinemas,
            user_lat=51.5080,
            user_lng=-0.1281,
            use_tfl=True,
            transport_mode="walking",
        )

        # TfL API should be called once (only for London cinema)
        assert mock_client.get_journey_time.call_count == 1

        # Verify it was called with London cinema coordinates
        call_args = mock_client.get_journey_time.call_args
        # First 4 args are positional: user_lat, user_lng, cinema.latitude, cinema.longitude
        assert call_args.args[2] == sample_london_cinema.latitude
        assert call_args.args[3] == sample_london_cinema.longitude
        assert call_args.kwargs["mode"] == "walking"

    # London cinema should have both distance and travel time
    assert sample_london_cinema.distance_km is not None
    assert sample_london_cinema.travel_time_minutes == 10
    assert sample_london_cinema.travel_mode == "walking"

    # Brighton cinema should only have distance, no travel time
    assert sample_brighton_cinema.distance_km is not None
    assert not hasattr(sample_brighton_cinema, "travel_time_minutes") or sample_brighton_cinema.travel_time_minutes is None
    assert not hasattr(sample_brighton_cinema, "travel_mode") or sample_brighton_cinema.travel_mode is None


@pytest.mark.asyncio
async def test_enrich_handles_tfl_api_failure_gracefully(sample_london_cinema):
    """Test that TfL API failures don't break enrichment."""
    cinemas = [sample_london_cinema]

    # Mock TfL client to return None (API failure)
    with patch("cinescout.services.tfl_client.TfLClient") as MockTfLClient:
        mock_client = MockTfLClient.return_value
        mock_client.get_journey_time = AsyncMock(return_value=None)

        await enrich_cinemas_with_distance(
            cinemas=cinemas,
            user_lat=51.5080,
            user_lng=-0.1281,
            use_tfl=True,
            transport_mode="public",
        )

    # Cinema should still have distance (Haversine always calculated)
    assert sample_london_cinema.distance_km is not None

    # But no travel time (TfL API failed)
    assert not hasattr(sample_london_cinema, "travel_time_minutes") or sample_london_cinema.travel_time_minutes is None


@pytest.mark.asyncio
async def test_enrich_handles_tfl_api_exception(sample_london_cinema):
    """Test that TfL API exceptions are caught and logged."""
    cinemas = [sample_london_cinema]

    # Mock TfL client to raise exception
    with patch("cinescout.services.tfl_client.TfLClient") as MockTfLClient:
        mock_client = MockTfLClient.return_value
        mock_client.get_journey_time = AsyncMock(side_effect=Exception("Network error"))

        # Should not raise exception
        await enrich_cinemas_with_distance(
            cinemas=cinemas,
            user_lat=51.5080,
            user_lng=-0.1281,
            use_tfl=True,
            transport_mode="public",
        )

    # Cinema should still have distance
    assert sample_london_cinema.distance_km is not None

    # But no travel time (exception caught)
    assert not hasattr(sample_london_cinema, "travel_time_minutes") or sample_london_cinema.travel_time_minutes is None


@pytest.mark.asyncio
async def test_enrich_uses_correct_transport_mode(sample_london_cinema):
    """Test that transport mode is passed correctly to TfL API."""
    cinemas = [sample_london_cinema]

    mock_tfl_result = {
        "distance_meters": 1200,
        "duration_minutes": 15,
        "status": "ok",
    }

    with patch("cinescout.services.tfl_client.TfLClient") as MockTfLClient:
        mock_client = MockTfLClient.return_value
        mock_client.get_journey_time = AsyncMock(return_value=mock_tfl_result)

        await enrich_cinemas_with_distance(
            cinemas=cinemas,
            user_lat=51.5080,
            user_lng=-0.1281,
            use_tfl=True,
            transport_mode="cycling",
        )

        # Verify transport mode was passed to API
        call_args = mock_client.get_journey_time.call_args
        assert call_args.kwargs["mode"] == "cycling"

    # Verify transport mode was stored on cinema
    assert sample_london_cinema.travel_mode == "cycling"


@pytest.mark.asyncio
async def test_enrich_processes_multiple_cinemas_in_parallel(
    sample_london_cinema, sample_brighton_cinema
):
    """Test that multiple London cinemas are processed in parallel."""
    # Create second London cinema
    london_cinema_2 = Cinema(
        id="curzon-soho",
        name="Curzon Soho",
        city="london",
        address="99 Shaftesbury Ave",
        postcode="W1D 5DY",
        latitude=51.5128,
        longitude=-0.1313,
        scraper_type="curzon",
        scraper_config={},
        has_online_booking=True,
        supports_availability_check=False,
    )

    cinemas = [sample_london_cinema, london_cinema_2, sample_brighton_cinema]

    mock_tfl_result = {
        "distance_meters": 800,
        "duration_minutes": 10,
        "status": "ok",
    }

    with patch("cinescout.services.tfl_client.TfLClient") as MockTfLClient:
        mock_client = MockTfLClient.return_value
        mock_client.get_journey_time = AsyncMock(return_value=mock_tfl_result)

        await enrich_cinemas_with_distance(
            cinemas=cinemas,
            user_lat=51.5080,
            user_lng=-0.1281,
            use_tfl=True,
            transport_mode="public",
        )

        # TfL API should be called twice (for both London cinemas)
        assert mock_client.get_journey_time.call_count == 2

    # Both London cinemas should have travel time
    assert sample_london_cinema.travel_time_minutes == 10
    assert london_cinema_2.travel_time_minutes == 10

    # Brighton cinema should not have travel time
    assert not hasattr(sample_brighton_cinema, "travel_time_minutes") or sample_brighton_cinema.travel_time_minutes is None
