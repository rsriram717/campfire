# Campfire Recommendation Flow

## Overview

Campfire uses a **two-stage pipeline** to produce restaurant recommendations:

1. **Deterministic selection** — a scoring function (`score_candidates`) and diversity filter (`mmr_select`) pick the 3 best candidates from a real Google Places pool, using the user's taste profile and dislike history.
2. **LLM explanation** — Claude Haiku receives the pre-selected 3 and writes a personalized explanation for each. It does not select or reorder.

This approach:
- Eliminates hallucinated restaurant names (Haiku only sees real, verified candidates)
- Produces consistent, principled selection (the same taste profile + candidate pool always yields the same picks)
- Lets Haiku focus on explanation quality rather than splitting attention between selection and description

The explanation step uses **Claude Haiku** (`claude-haiku-4-5-20251001`). The task is format-constrained writing from structured input — speed and cost matter more than deep reasoning. Haiku costs ~70× less than GPT-4 and performs well here.

---

## End-to-End Request Flow

```
User submits place_ids + city + neighborhood + types + input_weight (α) + revisit_weight (β)
        │
        ▼
1. Input & DB setup
   Fetch or create Restaurant records for each input place_id
   Load liked/disliked history from UserRestaurantPreference
        │
        ▼
2. Candidate pool construction  (controlled by β)
   β=0:   Google searchNearby → 20 candidates; exclude prev_recommended
   β=0.5: Google searchNearby + inject top-rated revisit candidates
   β=1.0: Use revisit pool only (fall back to Google if <3 revisits)
        │
        ▼
3. Pre-filtering
   Remove lodging, already-seen, low-rated (<3.5), type mismatches
   Each filter has a ≥3 survival fallback (skip filter if too few would remain)
        │
        ▼
4. Taste profile
   build_taste_profile(history_objs, input_objs, alpha)
   → preferred_price_level, top_cuisine_types, min_rating
        │
        ▼
5. Scoring
   score_candidates(candidates, taste_profile, disliked_objs)
   → full list sorted by _score descending
        │
        ▼
6. MMR selection
   top_n = max(5, round(len * 0.30))
   mmr_select(scored[:top_n], n=3)
   → 3 diverse, high-scoring final picks
        │
        ▼
7. Haiku explanation
   rank_candidates() sends final 3 to Haiku via prompt_rank.txt
   Haiku writes "Because you liked X and Y — 10-15 word description" for each
   Results resolved via candidate_index (no extra API call)
        │
        ▼
8. Persist + return
   Save all 3 as RequestRestaurant(type=recommendation)
   Return [{place_id, name, description, reason, address, rating, price_level}]
```

---

## Step-by-Step Detail

### 1. Input & DB Setup

The frontend sends `place_ids` (Google Place IDs from autocomplete). For each:

1. Check if a `Restaurant` with that `place_id` exists in the DB.
2. If not, call `google_service.get_details(place_id)` to fetch rich metadata and create the record.
3. Link to the current `UserRequest` via `RequestRestaurant(type=input)`.

Then load `UserRestaurantPreference` for the current user, splitting into `liked_restaurant_objs` and `disliked_restaurant_objs` (ORM `Restaurant` objects).

---

### 2. Candidate Pool Construction

`prev_recommended` = all `RequestRestaurant(type=recommendation)` for this user+city, excluding disliked places.

Behaviour is controlled by **β** (`revisit_weight`, 0.0–1.0):

| β | Behaviour |
|---|---|
| 0.0 | `searchNearby` → 20 candidates from Google; `prev_recommended` added to exclusion set |
| 0.0–1.0 | `searchNearby` + inject top `round(β × min(len(prev_recommended), 10))` revisit candidates |
| 1.0, ≥3 revisits | Skip Google entirely; candidate pool = `prev_recommended` only |
| 1.0, <3 revisits | Fall back silently to `searchNearby` |

`searchNearby` endpoint: `POST https://places.googleapis.com/v1/places:searchNearby`
Returns up to 20 restaurants near city centre coordinates. All rich fields come back in a single call — no per-restaurant follow-up needed.

**Note on pool quality:** The initial `searchNearby` seed is biased toward mainstream/popular restaurants from the city centre. The pool improves over time as users input niche favourites via autocomplete — each autocomplete selection runs `get_details()` and stores the result with `city_hint`, making it a candidate for all future requests in that city.

---

### 3. Pre-Filtering

Applied in order. Each filter has a **≥3 fallback**: if applying the filter would leave fewer than 3 candidates, the filter is skipped entirely.

| # | Filter | Skipped when |
|---|---|---|
| 1 | Remove lodging types (hotels, motels, hostels, etc.) | Revisit-only pool (β=1.0) |
| 2 | Remove already-seen place_ids (liked + disliked + current inputs) | Revisit-only pool (β=1.0) |
| 3 | Remove candidates with rating < 3.5 | Fewer than 3 would survive |
| 4 | Remove type mismatches (Fine Dining / Bar / Casual) | Fewer than 3 would match |

Type matching rules:
- **Fine Dining**: `price_level` in `{EXPENSIVE, VERY_EXPENSIVE}` OR `primary_type == fine_dining_restaurant`
- **Bar**: `primary_type` or any category in `{bar, cocktail_bar, wine_bar, pub, bar_and_grill}`
- **Casual**: anything not Fine Dining

---

### 4. Taste Profile — `build_taste_profile(history_objs, input_objs, alpha)`

Derives a weighted profile from liked history and current session inputs. Returns an empty dict if no signal exists.

**α** (`input_weight`, 0.0–1.0): controls how much the session inputs vs. history dominate.
- α=1.0 → session inputs fully control
- α=0.0 → liked history fully controls
- Each source is normalized to its weight fraction before combining

Output fields (omitted entirely if no signal):

| Field | Derivation |
|---|---|
| `preferred_price_level` | Most-common `price_level` by weighted vote across history + inputs |
| `top_cuisine_types` | Top 3 `primary_type` values by weighted vote (e.g. `["italian_restaurant", "sushi_restaurant"]`) |
| `min_rating` | Weighted average of `rating` values, rounded to 1 decimal |

**Note:** `serves_dine_in`, `serves_takeout`, `serves_delivery`, and `reservable` are stored in the DB but are not used in the taste profile or recommendation logic.

---

### 5. Scoring — `score_candidates(candidates, taste_profile, disliked_restaurant_objs)`

Scores every pre-filtered candidate against the taste profile. Weights are fixed — α's influence is already encoded in `taste_profile`.

```
score = 0.0

── Cuisine (W = 0.40) ────────────────────────────────────────────────────────
  candidate.primary_type in top_cuisine_types          → +0.40  (full credit)
  any candidate.category in top_cuisine_types          → +0.20  (half credit)
  no match, or top_cuisine_types is empty              → +0.00

── Price (W = 0.30) ──────────────────────────────────────────────────────────
  Tiers (in order): INEXPENSIVE(0), MODERATE(1), EXPENSIVE(2), VERY_EXPENSIVE(3)
  dist = |index(preferred_price_level) - index(candidate.price_level)|
  score += 0.30 × max(0, 1 - dist/3)

  dist=0 (exact match)  → +0.30
  dist=1 (one tier off) → +0.20
  dist=2 (two tiers)    → +0.10
  dist=3 (three tiers)  → +0.00
  Either price absent   → +0.00 (skipped)

── Rating (W = 0.25) ─────────────────────────────────────────────────────────
  Normalized above 3.5 floor (pre-filter already enforces rating ≥ 3.5)
  score += 0.25 × min(1.0, (rating - 3.5) / 1.5)

  rating 3.5 → +0.00
  rating 4.25 → +0.125
  rating 5.0  → +0.25

── Dislike penalty (soft) ────────────────────────────────────────────────────
  count = number of disliked restaurants with the same primary_type
  score -= min(0.30, 0.10 × count)

  1 dislike of this type → -0.10
  2 dislikes             → -0.20
  3+ dislikes            → -0.30 (cap)
```

Returns the full candidate list sorted by `_score` descending, with `_score` added to each dict. Original candidate dicts are not mutated (a copy is made).

Maximum possible score: 0.40 + 0.30 + 0.25 = **0.95** (perfect cuisine + price + rating=5.0, no penalty).

---

### 6. MMR Selection — `mmr_select(scored_candidates, n=3, lambda_=0.7)`

Selects a diverse final set from the top-scored candidates.

**Top-N filter** (applied in `rank_candidates` before calling `mmr_select`):
```
n_top = max(5, round(len(candidates) × 0.30))
pool  = scored_candidates[:n_top]
```
For a typical 20-candidate pool: n_top = max(5, 6) = 6. Minimum of 5 prevents MMR from having too small a pool on short lists.

**MMR selection loop** — iteratively picks the candidate that maximises:
```
MMR(c) = λ × c._score  −  (1 − λ) × max_similarity(c, already_selected)
```
λ=0.7 weights 70% relevance, 30% diversity. The first pick is always the highest-scored candidate (no selected set yet, so no penalty).

**Similarity** is defined on the joint `(primary_type, price_level)` key:
```
both match  → 1.0   (same cuisine AND same price tier)
one matches → 0.5   (same cuisine OR same price tier)
neither     → 0.0
```

**Example (Scenario B — Italian history, sushi dislikes):**
```
Scored pool (top 5):
  Spacca Napoli  italian / MODERATE  score=0.900
  Monteverde     italian / MODERATE  score=0.883
  Eataly         italian / EXPENSIVE score=0.767
  Au Cheval      american / MODERATE score=0.467
  Avec           mediterr / MODERATE score=0.467

Pick 1: Spacca Napoli (0.900)
Pick 2: MMR scores:
  Monteverde:  0.7×0.883 − 0.3×1.0 = 0.318  (same type+price → sim=1.0)
  Eataly:      0.7×0.767 − 0.3×0.5 = 0.387  (same type, diff price → sim=0.5)
  Au Cheval:   0.7×0.467 − 0.3×0.0 = 0.327  (diff type+price → sim=0.0)
  → Eataly wins (0.387)
Pick 3: MMR scores against [Spacca, Eataly]:
  Monteverde:  0.7×0.883 − 0.3×max(1.0,0.5) = 0.318
  Au Cheval:   0.7×0.467 − 0.3×max(0.0,0.0) = 0.327
  → Au Cheval wins (0.327)
Final: Spacca Napoli, Eataly, Au Cheval
```

---

### 7. Haiku Explanation — `rank_candidates()` + `prompt_rank.txt`

The 3 selected candidates are sent to Haiku as a numbered list. Haiku **writes explanations only** — it does not select or reorder.

**Candidate line format sent to Haiku:**
```
N. Restaurant Name [previously recommended]  — primary_type, price_level, rating: X.X, editorial_summary
```
The `[previously recommended]` tag appears when `_is_revisit=True`.

**Prompt context injected:**

| Variable | Content |
|---|---|
| `session_section` | Current-session input restaurants: `- Name: type, price, rating` |
| `history_section` | Liked-history restaurants: `- Name: type, price, rating` |
| `alpha_instruction` | α≥0.7 → "emphasize session inputs"; α≤0.3 → "draw from history"; else empty |
| `revisit_instruction` | β≥0.7 → "revisits OK"; β=0.0 → "prefer new"; else empty |
| `liked_names` | Comma-separated liked restaurant names (do not recommend these) |
| `disliked_names` | Comma-separated disliked restaurant names |
| `neighborhood_section` | Neighbourhood preference string (if set) |
| `type_section` | Restaurant type preference (if set) |

**Output format:**
```
N. Restaurant Name - Because you liked [Name1] and [Name2] - 10-15 word description
```

`rank_candidates()` parses the leading number, resolves it via `candidate_index` (a dict built from `final_picks`), and returns the official Google `name` and `place_id` — no extra API call needed. Haiku's restatement of the name is discarded.

`max_tokens=500`

---

### 8. Persistence

For each of the 3 results:
1. Look up or create a `Restaurant` record by `(provider='google', place_id=...)`.
2. Create a `RequestRestaurant(type=recommendation)` link to the current `UserRequest`.

This populates `prev_recommended` for future requests, enabling the revisit pool and preference tracking.

---

## Restaurant Table Schema

The `Restaurant` table serves dual purpose: canonical record of a place and candidate pool for future requests.

| Column | Type | Used in recommendations? |
|---|---|---|
| `id` | Integer PK | — |
| `name` | String(100) | Yes — displayed to user |
| `location` | String(100) | Yes — displayed to user |
| `cuisine_type` | Text | No (legacy field) |
| `provider` | String(20) | Yes — always `google` for real places |
| `place_id` | String(128) | Yes — unique identifier |
| `slug` | String(200) | No — URL routing only |
| `price_level` | String(50) | Yes — scoring + taste profile |
| `rating` | Float | Yes — scoring + taste profile |
| `user_rating_count` | Integer | No |
| `editorial_summary` | Text | Yes — sent to Haiku |
| `primary_type` | String(100) | Yes — scoring + taste profile |
| `serves_dine_in` | Boolean | No — stored but not used in logic |
| `serves_takeout` | Boolean | No — stored but not used in logic |
| `serves_delivery` | Boolean | No — stored but not used in logic |
| `reservable` | Boolean | No — stored but not used in logic |
| `last_enriched_at` | DateTime | Yes — drives 30-day cache TTL |
| `city_hint` | String(100) | Yes — enables candidate cache query |

---

## Key Files

| File | Role |
|---|---|
| `app.py` | `/get_recommendations` route — orchestrates full flow, all pre-filtering |
| `openai_example.py` | `build_taste_profile`, `score_candidates`, `mmr_select`, `rank_candidates` |
| `prompt_rank.txt` | Haiku explanation prompt template |
| `services/google_service.py` | `get_details()`, `search_nearby_candidates()` |
| `models.py` | `Restaurant`, `UserRequest`, `RequestRestaurant`, `UserRestaurantPreference` |

---

## Known Limitations

**`searchNearby` seed quality**: Cold-cache calls query from the city centre using Google's popularity ranking. The initial pool skews toward chains and well-known spots. Niche candidates enter the pool only through user autocomplete inputs.

**Neighbourhood parameter is informational only**: `neighborhood` is passed as text context to Haiku but does not restrict the `searchNearby` geographic query. All candidates come from a fixed radius around the city centre regardless of neighbourhood selection.

**Revisit pool depends on prior usage**: The revisit pool (`prev_recommended`) is user+city specific. New users or users exploring a new city get β=1.0 silently falling back to Google.

**Input restaurants not auto-liked**: Submitting a restaurant as an input does not create a `UserRestaurantPreference(like)`. It informs the session taste profile via `input_restaurant_objs` but does not persist to history unless the user explicitly likes it in the Preferences tab.
