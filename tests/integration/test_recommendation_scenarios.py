"""
Integration scenario tests for POST /get_recommendations.

Mocked boundaries:
  - places_service.get_details              → fake restaurant detail dict
  - places_service.search_nearby_candidates → fixed pool of fake candidates
  - openai_example.rank_candidates          → echoes first 3 candidates (deterministic)

Each test seeds the DB, fires the route, and asserts on:
  1. HTTP response shape
  2. DB state (restaurants created, request records saved)
  3. What rank_candidates *received* (via mock.call_args) — this is the key assertion
     for candidate pool construction correctness.

NOTE: Do NOT use ``with app.app_context():`` anywhere in tests — the session-scoped
``app`` fixture already holds an active context.  Nesting contexts triggers
Flask-SQLAlchemy's teardown_appcontext which removes the wrong scoped session.
"""

import json
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

# conftest helpers
from tests.conftest import (
    seed_user, seed_restaurant, seed_preference, seed_prev_recommendation,
    DEFAULT_CANDIDATES, make_details, make_candidate, rank_candidates_echo,
)
from models import (
    db, Restaurant, UserRequest, RequestRestaurant, RequestType,
    UserRestaurantPreference, PreferenceType,
)


# ---------------------------------------------------------------------------
# Shared mock targets
# ---------------------------------------------------------------------------

SEARCH_TARGET = "services.places_service.search_nearby_candidates"
DETAILS_TARGET = "services.places_service.get_details"
# app.py does `from openai_example import rank_candidates`, so patch the name
# bound in the app module — not the one in openai_example.
RANK_TARGET = "app.rank_candidates"


def _post(client, payload):
    return client.post(
        "/get_recommendations",
        data=json.dumps(payload),
        content_type="application/json",
    )


def _base_payload(**overrides):
    base = {
        "user": "testuser",
        "city": "Chicago",
        "place_ids": [],
        "input_restaurants": [],
        "input_weight": 0.7,
        "revisit_weight": 0.0,
        "restaurant_types": [],
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Scenario 1: Fresh user, brand-new input restaurants
# ---------------------------------------------------------------------------

class TestFreshUserNewInputs:
    def test_restaurants_created_and_returned(self, client, app):
        """
        Two new place_ids not in DB.
        get_details should be called once per place_id.
        Three recommendations should be returned and persisted.
        """
        detail_a = make_details("Alpha", "pid_new_a", rating=4.6)
        detail_b = make_details("Beta", "pid_new_b", rating=4.4)

        def fake_details(place_id, *a, **kw):
            return {"pid_new_a": detail_a, "pid_new_b": detail_b}[place_id]

        with patch(DETAILS_TARGET, side_effect=fake_details) as mock_details, \
             patch(SEARCH_TARGET, return_value=DEFAULT_CANDIDATES) as mock_search, \
             patch(RANK_TARGET, side_effect=rank_candidates_echo) as mock_rank:

            resp = _post(client, _base_payload(
                place_ids=["pid_new_a", "pid_new_b"],
            ))

        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["recommendations"]) == 3

        # get_details called exactly once per new place_id
        assert mock_details.call_count == 2
        called_pids = {c.args[0] for c in mock_details.call_args_list}
        assert called_pids == {"pid_new_a", "pid_new_b"}

        # Google search was called
        mock_search.assert_called_once()

        assert Restaurant.query.filter_by(place_id="pid_new_a").count() == 1
        assert Restaurant.query.filter_by(place_id="pid_new_b").count() == 1
        # 3 recommendation records saved
        latest_req = UserRequest.query.order_by(UserRequest.id.desc()).first()
        recs = RequestRestaurant.query.filter_by(
            user_request_id=latest_req.id,
            type=RequestType.recommendation,
        ).all()
        assert len(recs) == 3


# ---------------------------------------------------------------------------
# Scenario 2: Returning user, inputs already cached in DB
# ---------------------------------------------------------------------------

class TestReturningUserCachedInputs:
    def test_get_details_not_called_for_cached(self, client, app):
        """
        Input place_ids already exist in DB. get_details should NOT be called.
        History liked restaurants should appear in liked_restaurant_objs passed to rank_candidates.
        """
        user = seed_user("returninguser")
        cached = seed_restaurant("Cached Place", "pid_cached", city="Chicago")
        liked_hist = seed_restaurant("Liked History", "pid_liked", city="Chicago")
        seed_preference(user, liked_hist, PreferenceType.like)
        db.session.commit()

        with patch(DETAILS_TARGET) as mock_details, \
             patch(SEARCH_TARGET, return_value=DEFAULT_CANDIDATES), \
             patch(RANK_TARGET, side_effect=rank_candidates_echo) as mock_rank:

            resp = _post(client, _base_payload(
                user="returninguser",
                place_ids=["pid_cached"],
            ))

        assert resp.status_code == 200
        mock_details.assert_not_called()

        # rank_candidates received liked history objs
        _, kwargs = mock_rank.call_args
        liked_objs = kwargs.get("liked_restaurant_objs", [])
        liked_names = [r.name for r in liked_objs]
        assert "Liked History" in liked_names


# ---------------------------------------------------------------------------
# Scenario 3: β=0 — previously recommended restaurants excluded from pool
# ---------------------------------------------------------------------------

class TestBeta0ExcludesPrevRecommended:
    def test_prev_recommended_in_exclusion_when_beta_zero(self, client, app):
        """
        With revisit_weight=0, previously recommended restaurants should be added
        to the exclusion set so they don't appear in candidates.
        """
        user = seed_user("beta0user")
        prev_rec = seed_restaurant("Old Pick", "pid_old_pick", city="Chicago")
        seed_prev_recommendation(user, prev_rec, city="Chicago")
        db.session.commit()

        # Inject the prev-recommended place_id into the candidate pool
        candidates_with_prev = DEFAULT_CANDIDATES + [
            make_candidate("Old Pick", "pid_old_pick", rating=4.7)
        ]

        with patch(DETAILS_TARGET, return_value=make_details()), \
             patch(SEARCH_TARGET, return_value=candidates_with_prev), \
             patch(RANK_TARGET, side_effect=rank_candidates_echo) as mock_rank:

            resp = _post(client, _base_payload(
                user="beta0user",
                place_ids=[],
                revisit_weight=0.0,
            ))

        assert resp.status_code == 200
        _, kwargs = mock_rank.call_args
        candidate_pids = [c["place_id"] for c in kwargs.get("candidates", [])]
        assert "pid_old_pick" not in candidate_pids


# ---------------------------------------------------------------------------
# Scenario 4: β=0.5 — revisit candidates injected into Google pool
# ---------------------------------------------------------------------------

class TestBetaHalfInjectsRevisits:
    def test_revisit_candidates_injected(self, client, app):
        """
        With revisit_weight=0.5 and prev recommendations, top-rated revisits
        should be injected into the candidate pool alongside Google results.
        """
        user = seed_user("betahalfuser")
        prev_recs = []
        for i in range(5):
            r = seed_restaurant(f"Past Pick {i}", f"pid_past_{i}", rating=4.0 + i * 0.1)
            seed_prev_recommendation(user, r, city="Chicago")
            prev_recs.append(r)
        db.session.commit()

        with patch(DETAILS_TARGET, return_value=make_details()), \
             patch(SEARCH_TARGET, return_value=DEFAULT_CANDIDATES) as mock_search, \
             patch(RANK_TARGET, side_effect=rank_candidates_echo) as mock_rank:

            resp = _post(client, _base_payload(
                user="betahalfuser",
                place_ids=[],
                revisit_weight=0.5,
            ))

        assert resp.status_code == 200
        mock_search.assert_called_once()  # Google was still called

        _, kwargs = mock_rank.call_args
        all_candidates = kwargs.get("candidates", [])
        revisit_candidates = [c for c in all_candidates if c.get("_is_revisit")]
        assert len(revisit_candidates) > 0, "Expected revisit candidates injected into pool"


# ---------------------------------------------------------------------------
# Scenario 5: β=1.0, enough revisits — Google skipped entirely
# ---------------------------------------------------------------------------

class TestBeta1SkipsGoogle:
    def test_google_not_called_with_enough_revisits(self, client, app):
        """
        revisit_weight=1.0 and ≥3 prev recommended → search_nearby_candidates
        should NOT be called; pool is revisit-only.
        """
        user = seed_user("beta1user")
        for i in range(4):
            r = seed_restaurant(f"Revisit {i}", f"pid_revisit_{i}", rating=4.5)
            seed_prev_recommendation(user, r, city="Chicago")
        db.session.commit()

        with patch(DETAILS_TARGET, return_value=make_details()), \
             patch(SEARCH_TARGET, return_value=DEFAULT_CANDIDATES) as mock_search, \
             patch(RANK_TARGET, side_effect=rank_candidates_echo) as mock_rank:

            resp = _post(client, _base_payload(
                user="beta1user",
                place_ids=[],
                revisit_weight=1.0,
            ))

        assert resp.status_code == 200
        mock_search.assert_not_called()

        _, kwargs = mock_rank.call_args
        all_candidates = kwargs.get("candidates", [])
        assert all(c.get("_is_revisit") for c in all_candidates)


# ---------------------------------------------------------------------------
# Scenario 6: β=1.0, insufficient revisits — falls back to Google
# ---------------------------------------------------------------------------

class TestBeta1FallsBackWithFewRevisits:
    def test_falls_back_to_google_when_fewer_than_3_revisits(self, client, app):
        user = seed_user("beta1fallback")
        for i in range(2):  # Only 2 revisits — below threshold of 3
            r = seed_restaurant(f"FewRevisit {i}", f"pid_fewrev_{i}", rating=4.5)
            seed_prev_recommendation(user, r, city="Chicago")
        db.session.commit()

        with patch(DETAILS_TARGET, return_value=make_details()), \
             patch(SEARCH_TARGET, return_value=DEFAULT_CANDIDATES) as mock_search, \
             patch(RANK_TARGET, side_effect=rank_candidates_echo):

            resp = _post(client, _base_payload(
                user="beta1fallback",
                place_ids=[],
                revisit_weight=1.0,
            ))

        assert resp.status_code == 200
        mock_search.assert_called_once()


# ---------------------------------------------------------------------------
# Scenario 7: Mixed inputs — one cached, one new place_id
# ---------------------------------------------------------------------------

class TestMixedCachedAndNewInputs:
    def test_get_details_called_only_for_new(self, client, app):
        """
        One input place_id in DB, one not. get_details called only for the new one.
        Both end up in input_restaurants list passed to build_taste_profile.
        """
        user = seed_user("mixeduser")
        seed_restaurant("Cached Mix", "pid_mix_cached", city="Chicago")
        db.session.commit()

        detail_new = make_details("New Mix", "pid_mix_new")

        with patch(DETAILS_TARGET, return_value=detail_new) as mock_details, \
             patch(SEARCH_TARGET, return_value=DEFAULT_CANDIDATES), \
             patch(RANK_TARGET, side_effect=rank_candidates_echo) as mock_rank:

            resp = _post(client, _base_payload(
                user="mixeduser",
                place_ids=["pid_mix_cached", "pid_mix_new"],
            ))

        assert resp.status_code == 200
        # get_details called once — only for the new place
        assert mock_details.call_count == 1
        assert mock_details.call_args.args[0] == "pid_mix_new"

        # Both appear in input_restaurant_objs sent to rank_candidates
        _, kwargs = mock_rank.call_args
        input_objs = kwargs.get("input_restaurant_objs", [])
        input_names = [r.name for r in input_objs]
        assert "Cached Mix" in input_names
        assert "New Mix" in input_names


# ---------------------------------------------------------------------------
# Scenario 8: Disliked restaurants excluded from candidates
# ---------------------------------------------------------------------------

class TestDislikedExcluded:
    def test_disliked_place_id_not_in_candidates(self, client, app):
        """
        Disliked restaurants must not appear in the candidate pool passed to Haiku.
        """
        user = seed_user("dislikeuser")
        disliked = seed_restaurant("Bad Place", "pid_bad", city="Chicago")
        seed_preference(user, disliked, PreferenceType.dislike)
        db.session.commit()

        candidates_with_disliked = DEFAULT_CANDIDATES + [
            make_candidate("Bad Place", "pid_bad", rating=4.9)
        ]

        with patch(DETAILS_TARGET, return_value=make_details()), \
             patch(SEARCH_TARGET, return_value=candidates_with_disliked), \
             patch(RANK_TARGET, side_effect=rank_candidates_echo) as mock_rank:

            resp = _post(client, _base_payload(
                user="dislikeuser",
                place_ids=[],
                revisit_weight=0.0,
            ))

        assert resp.status_code == 200
        _, kwargs = mock_rank.call_args
        candidate_pids = [c["place_id"] for c in kwargs.get("candidates", [])]
        assert "pid_bad" not in candidate_pids


# ---------------------------------------------------------------------------
# Scenario 9: Duplicate place_ids in input — de-duplicated
# ---------------------------------------------------------------------------

class TestDuplicatePlaceIdsDeduplicated:
    def test_same_place_id_twice_creates_one_restaurant(self, client, app):
        """
        Sending the same place_id twice should result in get_details called once
        and a single Restaurant record.
        """
        detail = make_details("Dupe Place", "pid_dupe")

        with patch(DETAILS_TARGET, return_value=detail) as mock_details, \
             patch(SEARCH_TARGET, return_value=DEFAULT_CANDIDATES), \
             patch(RANK_TARGET, side_effect=rank_candidates_echo):

            resp = _post(client, _base_payload(
                place_ids=["pid_dupe", "pid_dupe"],
            ))

        assert resp.status_code == 200
        assert mock_details.call_count == 1

        assert Restaurant.query.filter_by(place_id="pid_dupe").count() == 1


# ---------------------------------------------------------------------------
# Scenario 10: Missing required fields → 400
# ---------------------------------------------------------------------------

class TestValidation:
    def test_missing_city_returns_400(self, client, app):
        resp = _post(client, {"user": "testuser", "place_ids": []})
        assert resp.status_code == 400

    def test_missing_user_returns_400(self, client, app):
        resp = _post(client, {"city": "Chicago", "place_ids": []})
        assert resp.status_code == 400

    def test_empty_json_object_returns_400(self, client, app):
        # Empty dict passes JSON parse but triggers the `if not data` guard → 400
        resp = _post(client, {})
        # `not {}` is True in Python, so the route returns 400 for empty payload
        # (user name is missing — missing_user check fires first for {} payload)
        assert resp.status_code == 400
