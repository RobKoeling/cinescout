"""Geolocation utilities for distance calculations."""

import math


def calculate_haversine_distance(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """
    Calculate straight-line distance between two points using Haversine formula.

    Args:
        lat1: Latitude of first point in decimal degrees
        lon1: Longitude of first point in decimal degrees
        lat2: Latitude of second point in decimal degrees
        lon2: Longitude of second point in decimal degrees

    Returns:
        Distance in kilometers (float)

    Example:
        >>> # Trafalgar Square to British Museum (~1.4km)
        >>> distance = calculate_haversine_distance(51.5080, -0.1281, 51.5194, -0.1270)
        >>> 1.2 < distance < 1.6
        True
    """
    # Earth's radius in kilometers
    R = 6371.0

    # Convert decimal degrees to radians
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)

    # Differences
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad

    # Haversine formula
    # d = 2r × arcsin(√(sin²(Δφ/2) + cos(φ1)×cos(φ2)×sin²(Δλ/2)))
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.asin(math.sqrt(a))

    # Distance in kilometers
    distance = R * c

    return distance
