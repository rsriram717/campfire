"""Unit tests for score_candidates() and mmr_select()."""

import pytest
from unittest.mock import MagicMock
from openai_example import score_candidates, mmr_select, W_CUISINE, W_PRICE, W_RATING


def _c(name="Restaurant", primary_type=None, price_level=None, rating=None, categories=None):
    return {
        "place_id": name.lower().replace(" ", "_"),
        "name": name,
        "primary_type": primary_type,
        "price_level": price_level,
        "rating": rating,
        "categories": categories or [],
        "address": "123 Main St",
    }


def _dislike(primary_type):
    m = MagicMock()
    m.primary_type = primary_type
    return m


class TestScoreCandidates:
    def test_cuisine_primary_type_match_adds_full_weight(self):
        profile = {"top_cuisine_types": ["mexican_restaurant"], "preferred_price_level": None, "min_rating": None}
        c = _c(primary_type="mexican_restaurant")
        result = score_candidates([c], profile)
        assert result[0]["_score"] >= W_CUISINE

    def test_cuisine_category_match_adds_half_weight(self):
        profile = {"top_cuisine_types": ["mexican_restaurant"]}
        c = _c(primary_type="restaurant", categories=["mexican_restaurant"])
        result = score_candidates([c], profile)
        assert result[0]["_score"] >= W_CUISINE * 0.5
        assert result[0]["_score"] < W_CUISINE

    def test_no_cuisine_match_adds_nothing(self):
        profile = {"top_cuisine_types": ["mexican_restaurant"]}
        c = _c(primary_type="sushi_restaurant", categories=[])
        result = score_candidates([c], profile)
        assert result[0]["_score"] < W_CUISINE

    def test_perfect_price_match_adds_full_weight(self):
        profile = {"preferred_price_level": "PRICE_LEVEL_MODERATE"}
        c = _c(price_level="PRICE_LEVEL_MODERATE")
        result = score_candidates([c], profile)
        # Score should include W_PRICE (full)
        assert result[0]["_score"] >= W_PRICE * 0.99

    def test_price_one_tier_off_adds_partial_weight(self):
        profile = {"preferred_price_level": "PRICE_LEVEL_MODERATE"}
        c = _c(price_level="PRICE_LEVEL_EXPENSIVE")  # dist=1
        result = score_candidates([c], profile)
        # W_PRICE * (1 - 1/3) = W_PRICE * 0.667
        expected = W_PRICE * (1.0 - 1 / 3.0)
        assert abs(result[0]["_score"] - expected) < 0.01

    def test_price_three_tiers_off_adds_nothing(self):
        profile = {"preferred_price_level": "PRICE_LEVEL_INEXPENSIVE"}
        c = _c(price_level="PRICE_LEVEL_VERY_EXPENSIVE")  # dist=3
        result = score_candidates([c], profile)
        # W_PRICE * max(0, 1 - 3/3) = 0
        assert result[0]["_score"] < 0.01

    def test_rating_5_adds_full_rating_weight(self):
        profile = {}
        c = _c(rating=5.0)
        result = score_candidates([c], profile)
        assert abs(result[0]["_score"] - W_RATING) < 0.01

    def test_rating_3_5_adds_nothing(self):
        profile = {}
        c = _c(rating=3.5)
        result = score_candidates([c], profile)
        assert result[0]["_score"] == pytest.approx(0.0, abs=0.01)

    def test_dislike_penalty_one_dislike(self):
        profile = {"top_cuisine_types": ["sushi_restaurant"]}
        c = _c(primary_type="sushi_restaurant", rating=5.0)
        disliked = [_dislike("sushi_restaurant")]
        without_penalty = score_candidates([c], profile)[0]["_score"]
        with_penalty = score_candidates([c], profile, disliked)[0]["_score"]
        assert with_penalty == pytest.approx(without_penalty - 0.10, abs=0.001)

    def test_dislike_penalty_capped_at_0_30(self):
        profile = {}
        c = _c(primary_type="sushi_restaurant", rating=5.0)
        disliked = [_dislike("sushi_restaurant")] * 5  # 5 dislikes but cap at 0.30
        without_penalty = score_candidates([c], profile)[0]["_score"]
        with_penalty = score_candidates([c], profile, disliked)[0]["_score"]
        assert with_penalty == pytest.approx(without_penalty - 0.30, abs=0.001)

    def test_empty_profile_rating_only(self):
        profile = {}
        c = _c(primary_type="mexican_restaurant", price_level="PRICE_LEVEL_MODERATE", rating=4.5)
        result = score_candidates([c], profile)
        # Only rating contributes: W_RATING * (4.5 - 3.5) / 1.5
        expected = W_RATING * (1.0 / 1.5)
        assert abs(result[0]["_score"] - expected) < 0.01

    def test_output_sorted_descending_by_score(self):
        profile = {"top_cuisine_types": ["mexican_restaurant"], "preferred_price_level": "PRICE_LEVEL_INEXPENSIVE"}
        candidates = [
            _c("Low", primary_type="sushi_restaurant", rating=4.0),
            _c("High", primary_type="mexican_restaurant", price_level="PRICE_LEVEL_INEXPENSIVE", rating=4.5),
            _c("Mid", primary_type="mexican_restaurant", rating=3.8),
        ]
        result = score_candidates(candidates, profile)
        scores = [r["_score"] for r in result]
        assert scores == sorted(scores, reverse=True)
        assert result[0]["name"] == "High"

    def test_score_key_added_to_each_candidate(self):
        profile = {}
        candidates = [_c("A"), _c("B")]
        result = score_candidates(candidates, profile)
        for r in result:
            assert "_score" in r

    def test_original_candidates_not_mutated(self):
        profile = {}
        c = _c("A", rating=4.5)
        score_candidates([c], profile)
        assert "_score" not in c


class TestMmrSelect:
    def test_same_cuisine_and_price_penalizes_second_pick(self):
        """Two candidates with same cuisine+price should not both be selected if a diverse option exists."""
        candidates = [
            {**_c("Italian1", primary_type="italian_restaurant", price_level="PRICE_LEVEL_MODERATE"), "_score": 0.80},
            {**_c("Italian2", primary_type="italian_restaurant", price_level="PRICE_LEVEL_MODERATE"), "_score": 0.75},
            {**_c("Mexican1", primary_type="mexican_restaurant", price_level="PRICE_LEVEL_INEXPENSIVE"), "_score": 0.60},
        ]
        result = mmr_select(candidates, n=2)
        names = [r["name"] for r in result]
        assert "Italian1" in names
        # Mexican1 should be preferred over Italian2 due to diversity
        assert "Mexican1" in names

    def test_same_cuisine_different_price_partial_penalty(self):
        """Same cuisine but different price should have a partial penalty (0.5), not a full block."""
        candidates = [
            {**_c("Italian1", primary_type="italian_restaurant", price_level="PRICE_LEVEL_MODERATE"),   "_score": 0.80},
            {**_c("Italian2", primary_type="italian_restaurant", price_level="PRICE_LEVEL_EXPENSIVE"),  "_score": 0.79},
            {**_c("Mexican1", primary_type="mexican_restaurant", price_level="PRICE_LEVEL_INEXPENSIVE"), "_score": 0.40},
        ]
        result = mmr_select(candidates, n=2, lambda_=0.7)
        names = [r["name"] for r in result]
        # Italian2 score (0.79) vs Mexican1 (0.40) after penalty — Italian2 should still win
        # MMR for Italian2: 0.7*0.79 - 0.3*0.5 = 0.553 - 0.15 = 0.403
        # MMR for Mexican1: 0.7*0.40 - 0.3*0.0 = 0.28
        assert "Italian1" in names
        assert "Italian2" in names

    def test_fewer_than_n_returns_all(self):
        candidates = [
            {**_c("A"), "_score": 0.8},
            {**_c("B"), "_score": 0.5},
        ]
        result = mmr_select(candidates, n=3)
        assert len(result) == 2

    def test_returns_exactly_n(self):
        candidates = [
            {**_c(f"R{i}"), "_score": 1.0 - i * 0.1}
            for i in range(10)
        ]
        result = mmr_select(candidates, n=3)
        assert len(result) == 3

    def test_first_pick_is_highest_scored(self):
        candidates = [
            {**_c("Best",   primary_type="italian_restaurant"), "_score": 0.90},
            {**_c("Second", primary_type="mexican_restaurant"), "_score": 0.70},
            {**_c("Third",  primary_type="sushi_restaurant"),   "_score": 0.50},
        ]
        result = mmr_select(candidates, n=3)
        assert result[0]["name"] == "Best"
