# Location Standardization Implementation Plan

*Status: Draft – temporary file to track work on steps 1 & 2; remove once implemented*

---

## 1  Goals

• Eliminate spelling-based duplicates by grounding every restaurant to a stable external **place_id**.
• Add an internal **slug** + UNIQUE index for extra collision safety and quick look-ups.

## 2  High-Level Tasks

| # | Task | Owner | Notes |
|---|------|-------|-------|
|1|Choose primary Places provider (default **Google Places**) | ✅ | Fallbacks: Yelp, Foursquare |
|2|Extend database schema (no migration yet) |  | Add `provider`, `place_id`, `slug` columns on `Restaurant` model |
|3|Implement slug generation helper |  | Use `python-slugify` or custom regex |
|4|Create `services/places.py` abstraction |  | `autocomplete()`, `place_details()` |
|5|Expose `/autocomplete` proxy endpoint |  | Keeps API keys server-side |
|6|Update `/get_recommendations` flow |  | Accept `place_id`, derive/lookup restaurant |
|7|Add front-end autocomplete UI |  | JS hits `/autocomplete` while typing |
|8|Upsert logic w/ UNIQUE(provider, place_id) |  | Ensures deduplication |
|9|Unit + integration tests |  | Slug, upsert, API wrapper |
|10|Update docs & `.env.example` |  | New vars: `GOOGLE_API_KEY`, `YELP_API_KEY`, `PLACES_PROVIDER` |

## 3  Schema Changes (SQLAlchemy)

```python
class Restaurant(db.Model):
    # ... existing columns ...
    provider = db.Column(db.String(20), default="google", nullable=False)
    place_id = db.Column(db.String(128), nullable=False)
    slug = db.Column(db.String(200), nullable=False)

    __table_args__ = (
        db.UniqueConstraint("provider", "place_id", name="uq_restaurant_provider_place"),
        db.UniqueConstraint("slug", name="uq_restaurant_slug"),
    )
```

*All new columns can be nullable during the development phase if needed; enforce NOT NULL once back-filled.*

## 4  Slug Generation

```python
from slugify import slugify

def make_slug(name: str, city: str | None = None) -> str:
    base = f"{name}-{city}" if city else name
    return slugify(base, lowercase=True)
```

–– Add helper in `utils/slug.py`.

## 5  Places Service Abstraction

File: `services/places.py`

```python
class PlacesService:
    def autocomplete(self, query: str, city: str | None = None) -> list[dict]:
        ...

    def place_details(self, place_id: str) -> dict:
        ...
```

Pick provider at runtime via `PLACES_PROVIDER` env var. Each provider module (`google_places.py`, `yelp_places.py`, …) implements the same interface.

## 6  Backend Routes

```
GET  /autocomplete?query=gio&city=Chicago   -> list[{ name, address, place_id }]
POST /get_recommendations                   -> payload may include place_id & provider
```

## 7  Front-End Changes

1. Replace free-text restaurant fields with `<input class="autocomplete">`.
2. Use AJAX to call `/autocomplete` as user types.
3. On selection, store `{name, place_id, provider}` in hidden inputs.

## 8  Upsert Logic

```
if place_id:
    restaurant = Restaurant.query.filter_by(provider=prov, place_id=pid).first()
    if not restaurant:
        restaurant = Restaurant(name=canon_name, provider=prov, place_id=pid, slug=make_slug(canon_name, city), ...)
        db.session.add(restaurant)
```

## 9  Testing Checklist

- Slug collision & case-insensitivity
- Autocomplete returns < 5 results & hides API key
- Duplicate prevention across multiple users

## 10  Environment Variables

```
# Primary provider API key
GOOGLE_API_KEY=your_key

# Optional fallback provider
YELP_API_KEY=your_key

# Controls which service is used
PLACES_PROVIDER=google  # or yelp
```

## 11  Timeline (est.)

1 day – prototype service & slug helper  
1 day – front-end autocomplete  
0.5 day – integrate with recommendation flow  
0.5 day – tests & docs

---

*End of plan – delete this file when features are merged.* 