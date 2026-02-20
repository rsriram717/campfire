"""
Unit tests for the candidate pre-filtering rules in get_recommendations.

We test the rules as pure list transforms so they stay fast and don't need a DB.
The logic is reproduced inline here rather than imported, so tests remain
independent of app.py internals and serve as a contract spec.
"""

import pytest


# ---------------------------------------------------------------------------
# Helpers — mirrors the filtering logic from app.py
# ---------------------------------------------------------------------------

LODGING_TYPES = {
    "hotel", "motel", "lodging", "extended_stay_hotel", "resort_hotel",
    "bed_and_breakfast", "hostel", "inn", "vacation_rental"
}
RATING_FLOOR = 3.5
FINE_DINING_PRICES = {"PRICE_LEVEL_EXPENSIVE", "PRICE_LEVEL_VERY_EXPENSIVE"}
BAR_TYPES = {"bar", "cocktail_bar", "wine_bar", "pub", "bar_and_grill"}


def filter_lodging(candidates):
    return [c for c in candidates if (c.get("primary_type") or "").lower() not in LODGING_TYPES]


def filter_excluded(candidates, excluded_place_ids):
    return [c for c in candidates if c.get("place_id") not in excluded_place_ids]


def filter_rating(candidates, floor=RATING_FLOOR):
    above = [c for c in candidates if (c.get("rating") or 0) >= floor]
    return above if len(above) >= 3 else candidates


def filter_types(candidates, restaurant_types):
    if not restaurant_types:
        return candidates

    def matches(c):
        price = c.get("price_level") or ""
        ptype = (c.get("primary_type") or "").lower()
        cats = [t.lower() for t in c.get("categories", [])]
        for rt in restaurant_types:
            if rt == "Fine Dining":
                if price in FINE_DINING_PRICES or ptype == "fine_dining_restaurant":
                    return True
            elif rt == "Bar":
                if ptype in BAR_TYPES or any(t in BAR_TYPES for t in cats):
                    return True
            elif rt == "Casual":
                if ptype != "fine_dining_restaurant" and price != "PRICE_LEVEL_VERY_EXPENSIVE":
                    return True
        return False

    filtered = [c for c in candidates if matches(c)]
    return filtered if len(filtered) >= 3 else candidates


def sort_by_rating(candidates):
    return sorted(candidates, key=lambda c: c.get("rating") or 0, reverse=True)


def _c(place_id="pid1", primary_type="restaurant", rating=4.0, price_level="PRICE_LEVEL_MODERATE", categories=None):
    return {
        "place_id": place_id,
        "name": f"Restaurant {place_id}",
        "primary_type": primary_type,
        "rating": rating,
        "price_level": price_level,
        "categories": categories or [],
    }


# ---------------------------------------------------------------------------
# Rule 1: Lodging exclusion
# ---------------------------------------------------------------------------

class TestLodgingFilter:
    def test_hotel_excluded(self):
        candidates = [_c("a", "hotel"), _c("b", "restaurant")]
        result = filter_lodging(candidates)
        assert len(result) == 1
        assert result[0]["place_id"] == "b"

    def test_all_lodging_types_excluded(self):
        for ltype in LODGING_TYPES:
            result = filter_lodging([_c("x", ltype)])
            assert result == [], f"Expected {ltype} to be excluded"

    def test_non_lodging_passes_through(self):
        candidates = [_c("a", "restaurant"), _c("b", "bar"), _c("c", "cafe")]
        assert filter_lodging(candidates) == candidates

    def test_primary_type_none_passes(self):
        c = _c("a")
        c["primary_type"] = None
        assert filter_lodging([c]) == [c]


# ---------------------------------------------------------------------------
# Rule 2: Exclusion set (liked / disliked / input)
# ---------------------------------------------------------------------------

class TestExclusionFilter:
    def test_excluded_place_id_removed(self):
        candidates = [_c("a"), _c("b"), _c("c")]
        result = filter_excluded(candidates, {"b"})
        assert [x["place_id"] for x in result] == ["a", "c"]

    def test_empty_exclusion_set_keeps_all(self):
        candidates = [_c("a"), _c("b")]
        assert filter_excluded(candidates, set()) == candidates

    def test_all_excluded_returns_empty(self):
        candidates = [_c("a"), _c("b")]
        result = filter_excluded(candidates, {"a", "b"})
        assert result == []


# ---------------------------------------------------------------------------
# Rule 3: Rating floor
# ---------------------------------------------------------------------------

class TestRatingFilter:
    def test_below_floor_removed_when_enough_remain(self):
        candidates = [_c("a", rating=4.5), _c("b", rating=4.0), _c("c", rating=4.2), _c("d", rating=3.0)]
        result = filter_rating(candidates)
        assert all(c["rating"] >= RATING_FLOOR for c in result)
        assert len(result) == 3

    def test_floor_skipped_when_fewer_than_3_would_survive(self):
        # Only 2 above floor → keep all 4 to avoid empty results
        candidates = [_c("a", rating=4.5), _c("b", rating=4.0), _c("c", rating=2.0), _c("d", rating=1.5)]
        result = filter_rating(candidates)
        assert len(result) == 4

    def test_none_rating_treated_as_zero(self):
        c = _c("a")
        c["rating"] = None
        candidates = [c, _c("b", rating=4.5), _c("c", rating=4.2), _c("d", rating=4.0)]
        result = filter_rating(candidates)
        assert c not in result


# ---------------------------------------------------------------------------
# Rule 4: Type filter
# ---------------------------------------------------------------------------

class TestTypeFilter:
    def test_fine_dining_by_price(self):
        # Need ≥3 fine dining matches so the fallback (< 3) is not triggered.
        candidates = [
            _c("a", price_level="PRICE_LEVEL_EXPENSIVE"),
            _c("b", price_level="PRICE_LEVEL_MODERATE"),
            _c("c", price_level="PRICE_LEVEL_VERY_EXPENSIVE"),
            _c("e", price_level="PRICE_LEVEL_EXPENSIVE"),
            _c("d", price_level="PRICE_LEVEL_MODERATE"),
        ]
        result = filter_types(candidates, ["Fine Dining"])
        pids = [c["place_id"] for c in result]
        assert "a" in pids and "c" in pids and "e" in pids
        assert "b" not in pids and "d" not in pids

    def test_fine_dining_by_primary_type(self):
        candidates = [
            _c("a", primary_type="fine_dining_restaurant", price_level="PRICE_LEVEL_MODERATE"),
            _c("b", primary_type="restaurant", price_level="PRICE_LEVEL_INEXPENSIVE"),
        ]
        result = filter_types(candidates, ["Fine Dining"])
        assert result[0]["place_id"] == "a"

    def test_bar_by_primary_type(self):
        candidates = [_c("a", primary_type="cocktail_bar"), _c("b", primary_type="restaurant")]
        result = filter_types([candidates[0], candidates[1], _c("c", primary_type="bar"),
                               _c("d", primary_type="wine_bar")], ["Bar"])
        pids = [c["place_id"] for c in result]
        assert "b" not in pids

    def test_casual_excludes_fine_dining(self):
        candidates = [
            _c("a", primary_type="restaurant", price_level="PRICE_LEVEL_MODERATE"),
            _c("b", primary_type="fine_dining_restaurant", price_level="PRICE_LEVEL_VERY_EXPENSIVE"),
            _c("c", primary_type="restaurant", price_level="PRICE_LEVEL_INEXPENSIVE"),
            _c("d", primary_type="restaurant", price_level="PRICE_LEVEL_MODERATE"),
        ]
        result = filter_types(candidates, ["Casual"])
        pids = [c["place_id"] for c in result]
        assert "b" not in pids
        assert "a" in pids and "c" in pids

    def test_type_filter_skipped_when_fewer_than_3_match(self):
        # Only 1 fine dining → fall back to full list of 4
        candidates = [
            _c("a", price_level="PRICE_LEVEL_EXPENSIVE"),
            _c("b", price_level="PRICE_LEVEL_MODERATE"),
            _c("c", price_level="PRICE_LEVEL_MODERATE"),
            _c("d", price_level="PRICE_LEVEL_MODERATE"),
        ]
        result = filter_types(candidates, ["Fine Dining"])
        assert len(result) == 4  # fell back

    def test_no_types_returns_all(self):
        candidates = [_c("a"), _c("b"), _c("c")]
        assert filter_types(candidates, []) == candidates


# ---------------------------------------------------------------------------
# Rule 5: Sort by rating descending
# ---------------------------------------------------------------------------

class TestSortByRating:
    def test_sorted_descending(self):
        candidates = [_c("a", rating=3.9), _c("b", rating=4.8), _c("c", rating=4.2)]
        result = sort_by_rating(candidates)
        ratings = [c["rating"] for c in result]
        assert ratings == sorted(ratings, reverse=True)

    def test_none_rating_sorts_last(self):
        c_none = _c("none")
        c_none["rating"] = None
        candidates = [c_none, _c("a", rating=4.5), _c("b", rating=3.8)]
        result = sort_by_rating(candidates)
        assert result[-1]["place_id"] == "none"
