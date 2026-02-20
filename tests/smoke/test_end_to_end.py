"""
Smoke test — real network, real Claude Haiku, real Google Places.

Excluded from normal CI via the `smoke` mark.
Run manually: pytest tests/smoke -m smoke -s

Requires:
  ANTHROPIC_API_KEY, GOOGLE_API_KEY set (from .env)
  FLASK_ENV=development (dev SQLite DB)
"""

import json
import pytest


pytestmark = pytest.mark.smoke


@pytest.mark.smoke
def test_full_recommendation_flow_no_inputs(client, app):
    """
    Submit a request with no input restaurants but a valid city.
    Expect 3 recommendations back from real Haiku + Google Places.
    """
    payload = {
        "user": "smoketest_user",
        "city": "Chicago",
        "place_ids": [],
        "input_restaurants": [],
        "input_weight": 0.7,
        "revisit_weight": 0.0,
        "restaurant_types": [],
    }
    resp = client.post(
        "/get_recommendations",
        data=json.dumps(payload),
        content_type="application/json",
    )
    data = resp.get_json()
    assert resp.status_code == 200, f"Unexpected status: {resp.status_code}, body: {data}"
    recs = data.get("recommendations", [])
    assert len(recs) == 3, f"Expected 3 recommendations, got {len(recs)}"
    for r in recs:
        assert r.get("name"), "Recommendation missing name"
        assert r.get("description"), "Recommendation missing description"
