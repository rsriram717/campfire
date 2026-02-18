# Campfire Recommendation Flow

## Overview

Campfire uses a **candidate ranking** approach to restaurant recommendations. Rather than asking an LLM to invent restaurant names from its training data (which produced well-known tourist spots and frequent hallucinations), the model is given a pool of **real, verified restaurants** from the Google Places API and asked to rank them based on the user's taste profile.

This approach:
- Eliminates hallucinated or invented restaurant names
- Allows niche and local spots to surface as the restaurant DB grows from user inputs
- Reduces Google API calls from ~9 per request down to 2, and often 1 with DB caching

The ranking step uses **Claude Haiku** (`claude-haiku-4-5-20251001`). The task is constrained selection from a structured list — format adherence and speed matter more than deep reasoning, making Haiku the right fit at ~70x lower cost than GPT-4.

---

## End-to-End Request Flow

```
User submits place_ids + city + neighborhood + types
        │
        ▼
1. Resolve input restaurants
   get_details() for each place_id → enrich + store as Restaurant records
        │
        ▼
2. Build taste profile
   Aggregate liked Restaurant ORM objects → price level, rating, cuisine types
        │
        ▼
3. Get candidate pool
   Check DB cache → if ≥20 fresh records for city: use DB (no API call)
                 → if cache miss: call searchNearby → upsert all results to DB
        │
        ▼
4. Rank candidates
   Haiku receives: taste profile + numbered real candidates
   Haiku selects 3, returns numbers + explanations
   Parse numbers → resolve via candidate_index (no API call)
        │
        ▼
5. Persist + return
   Upsert 3 Restaurant records, create RequestRestaurant links
   Return [{id, name, description, reason, address}]
```

---

## Step-by-Step Detail

### 1. Resolve Input Restaurants

The frontend sends `place_ids` (Google Place IDs from autocomplete). For each:

1. Check if a `Restaurant` record with that `place_id` already exists in the DB.
2. If not, call `google_service.get_details(place_id)` to fetch rich metadata.
3. Create a `Restaurant` record with all fields populated (see schema below).
4. Link to the current `UserRequest` via `RequestRestaurant(type=input)`.

Rich fields fetched: `price_level`, `rating`, `user_rating_count`, `editorial_summary`, `primary_type`, `serves_dine_in`, `serves_takeout`, `serves_delivery`, `reservable`. Both `last_enriched_at` and `city_hint` are set to support caching.

---

### 2. Build Taste Profile

`build_taste_profile(liked_restaurant_objs)` in `openai_example.py` aggregates signal from the user's liked restaurants (`UserRestaurantPreference`) plus the current inputs:

| Field | Derivation |
|---|---|
| `preferred_price_level` | Mode of `price_level` across liked restaurants |
| `min_rating` | Mean of `rating` values, rounded to 1 decimal |
| `top_cuisine_types` | Top 3 most common `primary_type` values |
| `prefers_dine_in` | True if ≥50% of liked restaurants with the field set are True |
| `prefers_takeout` | True if ≥50% of liked restaurants with the field set are True |
| `prefers_reservable` | True if ≥50% of liked restaurants with the field set are True |

For new users, or users whose liked restaurants predate the rich schema (all fields NULL), the profile will be sparse — the ranking prompt still works, just with less signal.

---

### 3. Get Candidate Pool

The `Restaurant` table acts as a **local restaurant index** that accumulates over time. Before calling the Places API, the DB is checked for a warm cache:

```python
fresh_cutoff = datetime.utcnow() - timedelta(days=30)
cached = Restaurant.query.filter(
    Restaurant.city_hint == city,
    Restaurant.last_enriched_at >= fresh_cutoff,
    Restaurant.provider == 'google'
).limit(40).all()

if len(cached) >= 20:
    # Use DB cache — no API call
    candidates = [restaurant_to_candidate_dict(r) for r in cached]
else:
    # Cache miss — call Places API and store results
    candidates = places_service.search_nearby_candidates(city, neighborhood)
    for c in candidates:
        upsert_or_update(c, city)
```

#### `searchNearby` call details

- Endpoint: `POST https://places.googleapis.com/v1/places:searchNearby`
- Returns up to 20 restaurants near the city's centre coordinates (hardcoded in `google_service.py`)
- Field mask uses `places.` prefix (unlike single-place `get_details` requests)
- All rich fields are returned in a single call — no per-restaurant follow-up needed

#### Honest assessment of the candidate pool

The `searchNearby` cold-cache seed is **biased toward mainstream restaurants**. Google ranks results by its own popularity signal from the city centre, so the initial pool tends to include well-known chains, tourist spots, and even hotels. In testing, the first Chicago `searchNearby` call returned McDonald's, Giordano's chain locations, and several hotels alongside better matches.

The candidate pool improves over time primarily through **user inputs**, not `searchNearby`:

- Every time any user selects a restaurant from autocomplete, `get_details()` runs on it and it is stored with `city_hint` and `last_enriched_at`. That restaurant then enters the candidate pool for all future requests for that city.
- As users collectively input their favourite niche spots, those spots accumulate in the DB and get served as candidates to future users.
- After 30 days the cache expires, `searchNearby` fires again, and newly user-contributed restaurants remain in the pool (they have their own `last_enriched_at` timestamps).

So niche restaurant discovery is a collective, emergent property: the more users use the app and input restaurants they love, the better the candidate pool becomes for everyone.

---

### 4. Rank Candidates with Claude Haiku

`rank_candidates(...)` in `openai_example.py`:

1. Builds a numbered list of candidates with their metadata:
   ```
   1. Au Cheval — american_restaurant, PRICE_LEVEL_MODERATE, rating: 4.7. Classic diner-style spot known for smash burgers.
   2. Kasama — filipino_restaurant, PRICE_LEVEL_MODERATE, rating: 4.5. ...
   ...
   ```

2. Constructs a prompt from `prompt_rank.txt` with the taste profile, liked/disliked names, and the numbered candidate list.

3. Calls Claude Haiku (`max_tokens=300`). Haiku returns lines like:
   ```
   3. Avec - Because you liked Au Cheval and Girl & The Goat - Cozy Mediterranean small plates, excellent natural wine list
   ```

4. Parses the leading number → looks up `candidate_index[N]` → gets `place_id`, `name`, `address` directly. **No additional API call is needed.**

Haiku is used here because the task is constrained: select 3 from a numbered list and follow a rigid output format. The model is not being asked to reason about unknown restaurants from memory — all the data is in the prompt. Haiku handles this well at a fraction of the cost of larger models.

---

### 5. Persist and Return

For each ranked result:
- Look up or create a `Restaurant` record by `(provider='google', place_id=...)`.
- Create a `RequestRestaurant(type=recommendation)` link.
- Return `{id, name, description, reason, address}` to the frontend.

The `reason` field (e.g. "Because you liked Au Cheval and Girl & The Goat") is displayed in the UI recommendation card.

---

## Restaurant Table Schema

The `Restaurant` table serves dual purpose: canonical record of a place and candidate cache index.

| Column | Type | Description |
|---|---|---|
| `id` | Integer PK | |
| `name` | String(100) | Official name from Google |
| `location` | String(100) | Formatted address |
| `cuisine_type` | String(200) | Google `types[]` joined as string |
| `provider` | String(20) | Always `google` for real places |
| `place_id` | String(128) | Google Place ID |
| `slug` | String(200) | URL-friendly identifier |
| `price_level` | String(50) | e.g. `PRICE_LEVEL_MODERATE` |
| `rating` | Float | Google rating (1–5) |
| `user_rating_count` | Integer | Number of Google reviews |
| `editorial_summary` | Text | Google's editorial blurb, if available |
| `primary_type` | String(100) | e.g. `american_restaurant`, `filipino_restaurant` |
| `serves_dine_in` | Boolean | |
| `serves_takeout` | Boolean | |
| `serves_delivery` | Boolean | |
| `reservable` | Boolean | |
| `last_enriched_at` | DateTime | When rich fields were last fetched — drives cache TTL |
| `city_hint` | String(100) | City used when record was fetched — enables cache query |

---

## API Call Comparison

| Scenario | Old flow | New flow |
|---|---|---|
| Google API calls per request | ~9 (3× input details + 3× autocomplete + 3× resolution details) | 2 (N× input details + 1 searchNearby) |
| Warm DB cache hit | — | N× input details only (no Places API for candidates) |
| LLM calls | 1 (GPT-4 invents names) | 1 (Haiku ranks real candidates) |
| LLM cost per request | ~$0.018 (GPT-4) | ~$0.00025 (Haiku) |
| Hallucination risk | High | None — model only selects from real candidates |

---

## Known Limitations

**`searchNearby` seed quality**: The cold-cache `searchNearby` call queries from the city centre and returns Google's popularity-ranked results. This skews toward chains and well-known spots. The initial pool for a new city will not be particularly niche.

**Fixed candidate pool between cache refreshes**: Once ≥20 records exist for a city, `searchNearby` doesn't fire again for 30 days. The pool is static until user inputs add to it or the cache expires.

**Neighbourhood parameter is informational only**: The `neighborhood` value is passed as text context to Haiku in the ranking prompt but does not currently restrict the `searchNearby` geographic query. All candidates come from a fixed radius around the city centre regardless of neighbourhood selection.

---

## Key Files

| File | Role |
|---|---|
| `app.py` | `/get_recommendations` route — orchestrates the full flow |
| `openai_example.py` | `build_taste_profile()`, `rank_candidates()` |
| `prompt_rank.txt` | Haiku ranking prompt template |
| `services/google_service.py` | `get_details()`, `search_nearby_candidates()` |
| `services/places.py` | Abstract base class for places providers |
| `models.py` | `Restaurant` ORM model with all rich fields |
| `migrations/versions/add_rich_metadata_to_restaurant.py` | Migration adding 11 new columns |
