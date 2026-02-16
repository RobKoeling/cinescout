"""Unit tests for text normalisation utilities."""

from cinescout.utils.text import normalise_title, slugify


class TestNormaliseTitle:
    def test_passthrough_clean_title(self) -> None:
        assert normalise_title("Nosferatu") == "Nosferatu"

    def test_removes_year_suffix(self) -> None:
        assert normalise_title("Nosferatu (2024)") == "Nosferatu"

    def test_removes_year_range_suffix(self) -> None:
        assert normalise_title("The Crown (2016-23)") == "The Crown"

    def test_removes_preview_prefix(self) -> None:
        assert normalise_title("Preview: The Film") == "The Film"

    def test_removes_sneak_preview_prefix(self) -> None:
        assert normalise_title("Sneak Preview: The Film") == "The Film"

    def test_removes_q_and_a_prefix(self) -> None:
        assert normalise_title("Q&A: The Film") == "The Film"

    def test_removes_intro_prefix(self) -> None:
        assert normalise_title("Intro: The Film") == "The Film"

    def test_removes_nt_live_prefix(self) -> None:
        assert normalise_title("NT Live: The Film") == "The Film"

    def test_removes_square_bracket_format_tag(self) -> None:
        assert normalise_title("Nosferatu [35mm]") == "Nosferatu"

    def test_removes_mid_title_square_bracket_tag(self) -> None:
        assert normalise_title("Nosferatu [Q&A] (2024)") == "Nosferatu"

    def test_removes_trailing_non_numeric_parenthetical(self) -> None:
        assert normalise_title("Nosferatu (Director's Cut)") == "Nosferatu"

    def test_removes_year_at_end(self) -> None:
        # Years are stripped for matching purposes
        assert normalise_title("Mission: Impossible (1996)") == "Mission: Impossible"

    def test_collapses_extra_whitespace(self) -> None:
        assert normalise_title("The   Film") == "The Film"

    def test_strips_leading_and_trailing_whitespace(self) -> None:
        assert normalise_title("  The Film  ") == "The Film"

    def test_returns_empty_string_unchanged(self) -> None:
        assert normalise_title("") == ""

    def test_prefix_removal_is_case_insensitive(self) -> None:
        assert normalise_title("PREVIEW: The Film") == "The Film"

    def test_combines_multiple_normalizations(self) -> None:
        # Preview prefix + square bracket tag + year suffix all removed
        assert normalise_title("Preview: The Film [35mm] (2024)") == "The Film"


class TestSlugify:
    def test_lowercases_input(self) -> None:
        assert slugify("Nosferatu") == "nosferatu"

    def test_replaces_spaces_with_hyphens(self) -> None:
        assert slugify("The Grand Budapest Hotel") == "the-grand-budapest-hotel"

    def test_removes_special_characters(self) -> None:
        assert slugify("Mission: Impossible") == "mission-impossible"

    def test_collapses_multiple_hyphens(self) -> None:
        assert slugify("word  word") == "word-word"

    def test_strips_leading_and_trailing_hyphens(self) -> None:
        assert slugify(":test:") == "test"

    def test_preserves_numbers(self) -> None:
        assert slugify("nosferatu 2024") == "nosferatu-2024"

    def test_converts_underscores_to_hyphens(self) -> None:
        assert slugify("some_title") == "some-title"

    def test_returns_empty_string_unchanged(self) -> None:
        assert slugify("") == ""
