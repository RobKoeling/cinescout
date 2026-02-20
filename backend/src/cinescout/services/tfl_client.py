"""TfL (Transport for London) API client for journey planning."""

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class TfLClient:
    """
    Client for TfL Journey Planner API with optional Redis caching.

    Fetches journey times and distances using public transport, walking, or cycling
    modes within London. The API is free to use with optional app key for higher
    rate limits.
    """

    BASE_URL = "https://api.tfl.gov.uk"

    def __init__(self, app_key: str | None = None, redis_client: Any | None = None):
        """
        Initialize TfL API client.

        Args:
            app_key: Optional TfL app key for higher rate limits (500/min vs 50/min)
            redis_client: Optional Redis client for caching results
        """
        self.app_key = app_key
        self.redis = redis_client

    async def get_journey_time(
        self,
        origin_lat: float,
        origin_lng: float,
        dest_lat: float,
        dest_lng: float,
        mode: str = "public",
    ) -> dict[str, Any] | None:
        """
        Get journey time from TfL Journey Planner API.

        Args:
            origin_lat: Starting point latitude
            origin_lng: Starting point longitude
            dest_lat: Destination latitude
            dest_lng: Destination longitude
            mode: Transport mode - "public" (tube/bus), "walking", or "cycling"

        Returns:
            Dict with journey info:
            {
                "distance_meters": int,
                "duration_minutes": int,
                "status": "ok"
            }

            Returns None if:
            - API call fails
            - No journey found
            - Coordinates are invalid
        """
        # Check cache first
        cache_key = self._build_cache_key(origin_lat, origin_lng, dest_lat, dest_lng, mode)
        cached = await self._get_from_cache(cache_key)
        if cached:
            logger.debug(f"TfL cache hit for {cache_key}")
            return cached

        # Call TfL API
        try:
            result = await self._fetch_from_api(
                origin_lat, origin_lng, dest_lat, dest_lng, mode
            )

            if result:
                # Store in cache (24 hour TTL)
                await self._store_in_cache(cache_key, result, ttl=86400)
                return result

            return None

        except Exception as e:
            logger.error(f"TfL API error: {e}", exc_info=True)
            return None

    async def _fetch_from_api(
        self,
        origin_lat: float,
        origin_lng: float,
        dest_lat: float,
        dest_lng: float,
        mode: str,
    ) -> dict[str, Any] | None:
        """
        Fetch journey from TfL API.

        API endpoint: GET /Journey/JourneyResults/{from}/to/{to}
        """
        # Format coordinates for TfL API
        from_point = f"{origin_lat},{origin_lng}"
        to_point = f"{dest_lat},{dest_lng}"

        # Map mode to TfL mode string
        mode_mapping = {
            "public": "tube,bus,overground,dlr,elizabeth-line,tram",
            "walking": "walking",
            "cycling": "cycling",
        }
        tfl_mode = mode_mapping.get(mode, mode_mapping["public"])

        # Build URL
        url = f"{self.BASE_URL}/Journey/JourneyResults/{from_point}/to/{to_point}"

        # Build query params
        params = {"mode": tfl_mode}
        if self.app_key:
            params["app_key"] = self.app_key

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(10.0),
                verify=False  # Disable SSL verification for development
            ) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()

                data = response.json()

                # Parse response
                return self._parse_journey_response(data)

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 300:
                # Multiple journey options - TfL sometimes returns 300 with journey data
                try:
                    data = e.response.json()
                    return self._parse_journey_response(data)
                except Exception:
                    logger.warning(f"TfL API returned 300 but couldn't parse: {e}")
                    return None
            else:
                logger.error(f"TfL API HTTP error: {e.response.status_code}")
                return None

        except httpx.TimeoutException:
            logger.error("TfL API timeout")
            return None

        except Exception as e:
            logger.error(f"TfL API request failed: {e}")
            return None

    def _parse_journey_response(self, data: dict) -> dict[str, Any] | None:
        """
        Parse TfL API response to extract journey time and distance.

        Args:
            data: JSON response from TfL API

        Returns:
            Normalized journey data or None if parsing fails
        """
        try:
            # Check if journeys exist
            journeys = data.get("journeys", [])
            if not journeys:
                logger.debug("No journeys found in TfL response")
                return None

            # Get first (fastest) journey
            journey = journeys[0]

            # Extract duration (in minutes)
            duration_minutes = journey.get("duration", 0)

            # Extract distance (sum of all legs)
            # TfL doesn't always provide distance in meters, so we'll use duration as primary metric
            legs = journey.get("legs", [])
            total_distance_meters = 0

            for leg in legs:
                distance = leg.get("distance", {})
                if isinstance(distance, dict):
                    # Distance can be in "value" field (meters)
                    total_distance_meters += distance.get("value", 0)

            # If no distance data, estimate based on duration (rough approximation)
            if total_distance_meters == 0 and duration_minutes > 0:
                # Estimate: ~4 km/h walking speed = 67 meters/minute
                total_distance_meters = int(duration_minutes * 67)

            return {
                "distance_meters": total_distance_meters,
                "duration_minutes": duration_minutes,
                "status": "ok",
            }

        except (KeyError, IndexError, TypeError) as e:
            logger.error(f"Failed to parse TfL response: {e}")
            return None

    def _build_cache_key(
        self,
        origin_lat: float,
        origin_lng: float,
        dest_lat: float,
        dest_lng: float,
        mode: str,
    ) -> str:
        """
        Build Redis cache key for journey.

        Rounds coordinates to 4 decimal places (~11m precision) to improve cache hit rate.
        """
        # Round to 4 decimals for caching (~11 meters precision)
        orig_lat_r = round(origin_lat, 4)
        orig_lng_r = round(origin_lng, 4)
        dest_lat_r = round(dest_lat, 4)
        dest_lng_r = round(dest_lng, 4)

        return f"tfl:{dest_lat_r}:{dest_lng_r}:{orig_lat_r}:{orig_lng_r}:{mode}"

    async def _get_from_cache(self, key: str) -> dict[str, Any] | None:
        """Get journey data from Redis cache."""
        if not self.redis:
            return None

        try:
            # Try to get from Redis
            # Assuming redis client has async methods
            cached = await self.redis.get(key)
            if cached:
                # Parse JSON
                import json
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"Redis cache get failed: {e}")

        return None

    async def _store_in_cache(
        self, key: str, value: dict[str, Any], ttl: int = 86400
    ) -> None:
        """Store journey data in Redis cache with TTL."""
        if not self.redis:
            return

        try:
            import json
            # Store JSON string with TTL (default 24 hours)
            await self.redis.setex(key, ttl, json.dumps(value))
        except Exception as e:
            logger.warning(f"Redis cache set failed: {e}")
