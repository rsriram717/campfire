"""Unit tests for openai_example.build_taste_profile."""

import pytest
from unittest.mock import MagicMock
from openai_example import build_taste_profile


def _r(price=None, rating=None, primary_type=None, dine_in=None, reservable=None, takeout=None):
    """Build a minimal Restaurant-like mock object."""
    m = MagicMock()
    m.price_level = price
    m.rating = rating
    m.primary_type = primary_type
    m.serves_dine_in = dine_in
    m.serves_takeout = takeout
    m.reservable = reservable
    return m


class TestBuildTasteProfile:
    def test_empty_inputs_returns_empty_dict(self):
        assert build_taste_profile([], [], alpha=0.7) == {}

    def test_single_input_no_history(self):
        r = _r(price="PRICE_LEVEL_MODERATE", rating=4.5, primary_type="restaurant")
        profile = build_taste_profile([], [r], alpha=1.0)
        assert profile["preferred_price_level"] == "PRICE_LEVEL_MODERATE"
        assert profile["min_rating"] == 4.5
        assert "restaurant" in profile["top_cuisine_types"]

    def test_history_only_alpha_zero(self):
        h = _r(price="PRICE_LEVEL_EXPENSIVE", rating=4.8, primary_type="fine_dining_restaurant")
        profile = build_taste_profile([h], [], alpha=0.0)
        assert profile["preferred_price_level"] == "PRICE_LEVEL_EXPENSIVE"
        assert profile["min_rating"] == 4.8

    def test_alpha_weights_inputs_over_history(self):
        # alpha=1.0: inputs dominate price
        history = [_r(price="PRICE_LEVEL_INEXPENSIVE")]
        inputs = [_r(price="PRICE_LEVEL_VERY_EXPENSIVE")]
        profile = build_taste_profile(history, inputs, alpha=1.0)
        assert profile["preferred_price_level"] == "PRICE_LEVEL_VERY_EXPENSIVE"

    def test_alpha_weights_history_over_inputs(self):
        # alpha=0.0: history dominates price
        history = [_r(price="PRICE_LEVEL_INEXPENSIVE")]
        inputs = [_r(price="PRICE_LEVEL_VERY_EXPENSIVE")]
        profile = build_taste_profile(history, inputs, alpha=0.0)
        assert profile["preferred_price_level"] == "PRICE_LEVEL_INEXPENSIVE"

    def test_rating_averaged_weighted(self):
        history = [_r(rating=3.0)]
        inputs = [_r(rating=5.0)]
        # alpha=0.5: equal weight → average = 4.0
        profile = build_taste_profile(history, inputs, alpha=0.5)
        assert profile["min_rating"] == pytest.approx(4.0, abs=0.05)

    def test_top_cuisine_types_max_three(self):
        history = [
            _r(primary_type="italian_restaurant"),
            _r(primary_type="italian_restaurant"),
            _r(primary_type="sushi_restaurant"),
            _r(primary_type="ramen_restaurant"),
            _r(primary_type="burger_restaurant"),
        ]
        profile = build_taste_profile(history, [], alpha=0.0)
        assert len(profile["top_cuisine_types"]) <= 3
        assert profile["top_cuisine_types"][0] == "italian_restaurant"

    def test_dine_in_preference_captured(self):
        r = _r(dine_in=True)
        profile = build_taste_profile([], [r], alpha=1.0)
        assert profile.get("prefers_dine_in") is True

    def test_missing_fields_not_included(self):
        r = _r()  # all None
        profile = build_taste_profile([], [r], alpha=1.0)
        assert "preferred_price_level" not in profile
        assert "min_rating" not in profile
        assert "top_cuisine_types" not in profile
