"""Unit tests for geolocation utilities."""

import pytest

from cinescout.utils.geo import calculate_haversine_distance


class TestHaversineDistance:
    """Tests for Haversine distance calculation."""

    def test_same_location_zero_distance(self):
        """Distance from a point to itself should be 0."""
        distance = calculate_haversine_distance(51.5074, -0.1278, 51.5074, -0.1278)
        assert distance == 0.0

    def test_london_landmarks(self):
        """Test with known London landmarks - Trafalgar Square to British Museum."""
        # Trafalgar Square: 51.5080, -0.1281
        # British Museum: 51.5194, -0.1270
        # Expected distance: ~1.3 km
        distance = calculate_haversine_distance(51.5080, -0.1281, 51.5194, -0.1270)
        assert 1.2 < distance < 1.6, f"Expected ~1.3 km, got {distance:.2f} km"

    def test_london_to_brighton(self):
        """Test London to Brighton distance (~75 km)."""
        # London (Trafalgar Square): 51.5074, -0.1278
        # Brighton (Royal Pavilion): 50.8225, -0.1372
        distance = calculate_haversine_distance(51.5074, -0.1278, 50.8225, -0.1372)
        assert 70 < distance < 80, f"Expected ~75 km, got {distance:.2f} km"

    def test_long_distance(self):
        """Test London to New York (~5570 km)."""
        # London: 51.5074, -0.1278
        # New York: 40.7128, -74.0060
        distance = calculate_haversine_distance(51.5074, -0.1278, 40.7128, -74.0060)
        assert 5500 < distance < 5600, f"Expected ~5570 km, got {distance:.2f} km"

    def test_cross_prime_meridian(self):
        """Test distance calculation across prime meridian."""
        # West of Greenwich: 51.5, -1.0
        # East of Greenwich: 51.5, 1.0
        # Expected: ~138 km (at 51.5° latitude)
        distance = calculate_haversine_distance(51.5, -1.0, 51.5, 1.0)
        assert 135 < distance < 142, f"Expected ~138 km, got {distance:.2f} km"

    def test_cross_equator(self):
        """Test distance calculation across equator."""
        # North of equator: 1.0, 0.0
        # South of equator: -1.0, 0.0
        # Expected: ~222 km (1° latitude ≈ 111 km)
        distance = calculate_haversine_distance(1.0, 0.0, -1.0, 0.0)
        assert 220 < distance < 225, f"Expected ~222 km, got {distance:.2f} km"

    def test_negative_coordinates(self):
        """Test with negative coordinates (Southern/Western hemispheres)."""
        # Sydney: -33.8688, 151.2093
        # Melbourne: -37.8136, 144.9631
        # Expected: ~714 km
        distance = calculate_haversine_distance(-33.8688, 151.2093, -37.8136, 144.9631)
        assert 700 < distance < 730, f"Expected ~714 km, got {distance:.2f} km"
