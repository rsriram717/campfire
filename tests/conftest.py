"""
Shared fixtures and helpers for the Campfire test suite.

Patching strategy:
  - places_service.get_details         → fake restaurant detail dict
  - places_service.search_nearby_candidates → fixed list of fake candidates
  - openai_example.rank_candidates     → echo first-3 candidates back as ranked results
    (call_args lets integration tests assert on what the candidate pool looked like)
"""

import os
import pytest

# Point at in-memory SQLite BEFORE app is imported so the module-level
# DB setup picks up the right URL.
os.environ.setdefault("FLASK_ENV", "testing")
os.environ.setdefault("DEV_DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("GOOGLE_API_KEY", "test-key")

import app as flask_app_module
from models import db as _db, User, Restaurant, UserRequest, RequestRestaurant, RequestType, UserRestaurantPreference, PreferenceType
from datetime import datetime
from sqlalchemy.pool import StaticPool


# ---------------------------------------------------------------------------
# Fake data factories
# ---------------------------------------------------------------------------

def make_candidate(
    name="Test Restaurant",
    place_id="pid_test",
    rating=4.2,
    price_level="PRICE_LEVEL_MODERATE",
    primary_type="restaurant",
    address="123 Main St",
    is_revisit=False,
):
    return {
        "name": name,
        "place_id": place_id,
        "address": address,
        "categories": [],
        "price_level": price_level,
        "rating": rating,
        "user_rating_count": 100,
        "editorial_summary": None,
        "primary_type": primary_type,
        "serves_dine_in": True,
        "serves_takeout": False,
        "serves_delivery": False,
        "reservable": True,
        "_is_revisit": is_revisit,
    }


def make_details(
    name="Test Restaurant",
    place_id="pid_test",
    rating=4.2,
    price_level="PRICE_LEVEL_MODERATE",
    primary_type="restaurant",
    address="123 Main St",
):
    """Fake return value for places_service.get_details."""
    return {
        "name": name,
        "address": address,
        "categories": ["American"],
        "price_level": price_level,
        "rating": rating,
        "user_rating_count": 100,
        "editorial_summary": None,
        "primary_type": primary_type,
        "serves_dine_in": True,
        "serves_takeout": False,
        "serves_delivery": False,
        "reservable": True,
    }


# Default pool of 5 candidates returned by the mocked search_nearby_candidates.
DEFAULT_CANDIDATES = [
    make_candidate(f"Candidate {i}", f"pid_candidate_{i}", rating=4.0 + i * 0.1)
    for i in range(1, 6)
]


def rank_candidates_echo(candidates, **kwargs):
    """Mock rank_candidates: returns first 3 candidates as ranked results."""
    results = []
    for c in candidates[:3]:
        results.append({
            "place_id": c["place_id"],
            "name": c["name"],
            "description": "Mock description",
            "reason": "Because you liked X",
            "address": c.get("address", ""),
            "rating": c.get("rating"),
            "price_level": c.get("price_level"),
        })
    return results


# ---------------------------------------------------------------------------
# App / DB fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def app():
    """Create Flask app configured for testing with in-memory SQLite.

    The app context pushed here stays active for the entire test session.
    IMPORTANT: tests must NOT push nested app contexts (via
    ``with app.app_context():``) — doing so triggers Flask-SQLAlchemy's
    teardown_appcontext on exit, which removes the *outer* session (because
    the scope key is ``id(current_app_ctx)`` and the inner context has
    already been popped by that point).
    """
    flask_app = flask_app_module.app
    # StaticPool forces SQLAlchemy to reuse a single connection for all
    # sessions, which is required for in-memory SQLite: without it, each
    # session gets a different connection (and a different empty database),
    # so data seeded in the test is invisible to the route's session.
    flask_app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "SQLALCHEMY_ENGINE_OPTIONS": {
            "connect_args": {"check_same_thread": False},
            "poolclass": StaticPool,
        },
    })
    ctx = flask_app.app_context()
    ctx.push()
    _db.create_all()
    yield flask_app
    _db.drop_all()
    ctx.pop()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture(autouse=True)
def clean_db(app):
    """Wipe all rows between tests without recreating schema.

    Operates directly on the session-scoped app context — no nested
    ``with app.app_context()`` to avoid the teardown_appcontext pitfall.
    """
    for table in reversed(_db.metadata.sorted_tables):
        _db.session.execute(table.delete())
    _db.session.commit()
    yield
    for table in reversed(_db.metadata.sorted_tables):
        _db.session.execute(table.delete())
    _db.session.commit()


# ---------------------------------------------------------------------------
# DB seeding helpers (called directly in tests)
# ---------------------------------------------------------------------------

def seed_user(name="testuser") -> User:
    u = User(name=name, email=f"{name}@example.com")
    _db.session.add(u)
    _db.session.flush()
    return u


def seed_restaurant(
    name="Seed Restaurant",
    place_id="pid_seed",
    city="Chicago",
    rating=4.5,
    price_level="PRICE_LEVEL_MODERATE",
    primary_type="restaurant",
) -> Restaurant:
    from utils import generate_slug
    slug = generate_slug(name, city)
    r = Restaurant(
        name=name,
        location=f"100 Test St, {city}",
        cuisine_type="American",
        provider="google",
        place_id=place_id,
        slug=slug,
        price_level=price_level,
        rating=rating,
        user_rating_count=200,
        primary_type=primary_type,
        serves_dine_in=True,
        serves_takeout=False,
        serves_delivery=False,
        reservable=True,
        last_enriched_at=datetime.utcnow(),
        city_hint=city,
    )
    _db.session.add(r)
    _db.session.flush()
    return r


def seed_preference(user: User, restaurant: Restaurant, pref: PreferenceType):
    p = UserRestaurantPreference(
        user_id=user.id,
        restaurant_id=restaurant.id,
        preference=pref,
    )
    _db.session.add(p)
    _db.session.flush()
    return p


def seed_prev_recommendation(user: User, restaurant: Restaurant, city="Chicago"):
    """Add a restaurant to a user's recommendation history for a city."""
    req = UserRequest(user_id=user.id, city=city)
    _db.session.add(req)
    _db.session.flush()
    rr = RequestRestaurant(
        user_request_id=req.id,
        restaurant_id=restaurant.id,
        type=RequestType.recommendation,
    )
    _db.session.add(rr)
    _db.session.flush()
    return rr
