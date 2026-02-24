"""Unit tests for cuisine type extraction logic used to bias candidate search."""

import pytest


# Mirrors the constant and logic in app.py so tests stay self-contained
GENERIC_PLACE_TYPES = {
    "restaurant", "food", "point_of_interest", "establishment",
    "meal_delivery", "meal_takeaway"
}


def extract_cuisine_types(top_cuisine_types, input_weight):
    """Replicate the extraction logic from app.py for testing."""
    if input_weight <= 0.3:
        return None
    specific = [t for t in top_cuisine_types if t not in GENERIC_PLACE_TYPES]
    return specific or None


class TestGenericTypeFiltering:
    def test_generic_restaurant_filtered_out(self):
        result = extract_cuisine_types(["restaurant"], input_weight=0.7)
        assert result is None

    def test_generic_food_filtered_out(self):
        result = extract_cuisine_types(["food"], input_weight=0.7)
        assert result is None

    def test_all_generic_returns_none(self):
        result = extract_cuisine_types(
            ["restaurant", "food", "point_of_interest", "establishment"],
            input_weight=0.7
        )
        assert result is None

    def test_specific_type_passes_through(self):
        result = extract_cuisine_types(["mexican_restaurant"], input_weight=0.7)
        assert result == ["mexican_restaurant"]

    def test_mixed_list_returns_only_specific(self):
        result = extract_cuisine_types(
            ["mexican_restaurant", "restaurant", "food"],
            input_weight=0.7
        )
        assert result == ["mexican_restaurant"]
        assert "restaurant" not in result
        assert "food" not in result

    def test_multiple_specific_types_all_returned(self):
        result = extract_cuisine_types(
            ["mexican_restaurant", "sushi_restaurant"],
            input_weight=0.7
        )
        assert set(result) == {"mexican_restaurant", "sushi_restaurant"}

    def test_empty_input_returns_none(self):
        result = extract_cuisine_types([], input_weight=0.7)
        assert result is None


class TestInputWeightGating:
    def test_at_threshold_returns_none(self):
        """input_weight == 0.3 → no cuisine filter (boundary excluded)."""
        result = extract_cuisine_types(["mexican_restaurant"], input_weight=0.3)
        assert result is None

    def test_just_above_threshold_applies_filter(self):
        """input_weight just above 0.3 → cuisine filter applied."""
        result = extract_cuisine_types(["mexican_restaurant"], input_weight=0.4)
        assert result == ["mexican_restaurant"]

    def test_above_threshold_applies_filter(self):
        """input_weight > 0.5 → cuisine filter applied."""
        result = extract_cuisine_types(["italian_restaurant"], input_weight=0.9)
        assert result == ["italian_restaurant"]

    def test_zero_weight_returns_none(self):
        result = extract_cuisine_types(["mexican_restaurant"], input_weight=0.0)
        assert result is None

    def test_max_weight_applies_filter(self):
        result = extract_cuisine_types(["korean_restaurant"], input_weight=1.0)
        assert result == ["korean_restaurant"]
