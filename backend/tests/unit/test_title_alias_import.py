"""Tests for title alias import payload validation."""

import pytest

from cinescout.services.title_alias_import import validate_entries


def test_validate_entries_accepts_good_payload():
    data = [{"alias": "25th Anniversary: Amelie", "tmdb_id": 194, "extra": "ignored"}]
    assert validate_entries(data) == [{"alias": "25th Anniversary: Amelie", "tmdb_id": 194}]


@pytest.mark.parametrize(
    "bad",
    [
        {"alias": "x", "tmdb_id": 1},  # not a list
        [{"alias": "x"}],  # missing tmdb_id
        [{"alias": "x", "tmdb_id": "1"}],  # tmdb_id wrong type
        [{"alias": "  ", "tmdb_id": 1}],  # blank alias
        [{"alias": "a" * 501, "tmdb_id": 1}],  # too long for the column
        ["nope"],
    ],
)
def test_validate_entries_rejects_bad_payload(bad):
    with pytest.raises(ValueError):
        validate_entries(bad)
