# Campfire - Project Context

## Development Workflow

Every non-trivial change follows this lifecycle. Do not skip steps.

1. **Design** — Write a plan to `features/<feature-name>.md` covering what, why, and how. Call out open questions.
2. **Implement** — Build against the plan. Keep commits focused.
3. **Test** — Add or update tests in `tests/`. All 78+ tests must pass (`venv/bin/python -m pytest`). The pre-push hook enforces this automatically.
4. **Document** — Update `README.md`, `CLAUDE.md`, and `memory/MEMORY.md` to reflect the change.
5. **Clean up** — Delete `features/<feature-name>.md` (the commit history is the permanent record). Remove any dead code, stale files, or temporary scaffolding.
6. **Push** — `git push` triggers the pre-push hook which runs the full test suite. Push only when green.

For trivial fixes (typos, one-line bugs), steps 1 and 5 can be skipped.

## What It Is
AI-powered restaurant recommendation web app. Users input favorite restaurants → a two-stage pipeline (deterministic scoring + MMR selection) picks 3 candidates, then Claude Haiku writes personalized explanations, based on liked/disliked history, city, neighborhood, type filters, and two weighting sliders.

## Stack
- **Backend**: Flask (Python 3.9), SQLAlchemy ORM, Flask-Migrate/Alembic
- **DB**: SQLite (dev) / PostgreSQL via Supabase (prod), env-selected via `FLASK_ENV`
- **AI**: Claude Haiku (`claude-haiku-4-5-20251001`) via `openai_example.py` + `prompt_rank.txt` for personalized explanation of pre-selected candidates; legacy GPT-4 path preserved in `prompt.txt` but unused by main flow
- **Places**: Google Places or Yelp Fusion (configured via `PLACES_PROVIDER` env var), abstracted in `services/`
- **Frontend**: Vanilla JS + Bootstrap 4, no build step — just `static/script.js` and `static/styles.css`
- **Deployment**: Vercel (`vercel.json`), instance path set to `/tmp/instance` for writable FS

## Key Files
- `app.py` — all Flask routes, DB logic, `_restaurant_to_candidate()` helper
- `models.py` — SQLAlchemy models
- `openai_example.py` — `build_taste_profile`, `score_candidates`, `mmr_select`, `rank_candidates` (Claude Haiku), legacy `get_similar_restaurants` (GPT-4)
- `prompt_rank.txt` — Claude Haiku explanation prompt (active); Haiku writes personalized descriptions for pre-selected candidates
- `prompt.txt` — legacy GPT-4 prompt template (inactive/preserved)
- `services/` — Google/Yelp Places abstraction (`places_service` imported in app.py)
- `utils.py` — `generate_slug(name, city)`
- `templates/index.html` — single-page UI with tab panels
- `static/script.js` — tab switching, autocomplete, form submission, preference UI, slider logic
- `features/todo.md` — tracked bugs and open improvements

## DB Models
- `User` — name (unique), email
- `Restaurant` — name, location, cuisine_type, provider, place_id, slug (unique constraint on provider+place_id and slug)
- `UserRequest` — user_id, city, timestamp
- `RequestRestaurant` — links request ↔ restaurant, type = `input` or `recommendation`
- `UserRestaurantPreference` — user_id, restaurant_id, preference = `like/dislike/neutral`
- `FeedbackSuggestion` + `FeedbackVote` — community feedback leaderboard with upvote/downvote

## Recommendation Flow

### 1. Input & DB setup
User submits `place_ids` + `city`/`neighborhood`/`types` + `input_weight` (α) + `revisit_weight` (β). `app.py` fetches or creates `Restaurant` records for each input place_id via the Places API, then loads liked/disliked history from `UserRestaurantPreference`.

### 2. Candidate pool construction
`prev_recommended` = prior `RequestRestaurant(type=recommendation)` for this user+city, excluding disliked.

Controlled by β:
- **β=0.0** — Google `searchNearby` for 20 candidates; `prev_recommended` added to exclusion set
- **β=0.5** — Google search + top-rated revisit candidates injected into pool
- **β=1.0, ≥3 revisits** — skip Google entirely; use revisit pool only
- **β=1.0, <3 revisits** — fall back silently to Google

### 3. Pre-filtering (in order, each with a ≥3 fallback)
1. Remove lodging types (hotels, motels, etc.) — skipped for revisit-only pool
2. Remove place_ids already seen (liked, disliked, input) — skipped for revisit-only pool
3. Remove candidates rated below 3.5 — skipped if fewer than 3 would survive
4. Remove type mismatches (Fine Dining / Bar / Casual) — skipped if fewer than 3 would match

### 4. Taste profile — `build_taste_profile(history_objs, input_objs, alpha)`
Produces a weighted profile dict from liked history and current session inputs. α=1.0 means session-only; α=0.0 means history-only. Each source is normalized to sum to its weight before being combined.

Output fields (omitted if no signal):
- `preferred_price_level` — most-common price level by weighted vote
- `top_cuisine_types` — up to 3 cuisine types by weighted vote (e.g. `["italian_restaurant", "sushi_restaurant"]`)
- `min_rating` — weighted average rating across history and inputs

### 5. Scoring — `score_candidates(candidates, taste_profile, disliked_restaurant_objs)`
Scores every candidate against the profile. α's influence is already baked into `taste_profile`; weights here are fixed.

```
score = 0.0

Cuisine (W=0.40):
  primary_type in top_cuisine_types          → +0.40
  any category in top_cuisine_types          → +0.20  (half credit)
  no match, or top_cuisine_types empty       → +0.00

Price (W=0.30), linear over 4 tiers [INEXPENSIVE, MODERATE, EXPENSIVE, VERY_EXPENSIVE]:
  dist = |index(preferred) - index(candidate)|
  score += 0.30 * max(0, 1 - dist/3)
  (exact match → +0.30; 1 tier off → +0.20; 2 tiers off → +0.10; 3 tiers off → +0.00)

Rating (W=0.25), normalized above 3.5 floor (pre-filter already enforces ≥3.5):
  score += 0.25 * min(1.0, (rating - 3.5) / 1.5)
  (3.5 → +0.00; 5.0 → +0.25)

Dislike penalty (soft, applied after the above):
  count = number of disliked restaurants with the same primary_type
  score -= min(0.30, 0.10 * count)
```

Returns the full list sorted by score descending, with `_score` added to each dict.

### 6. MMR selection — `mmr_select(scored_candidates, n=3, lambda_=0.7)`
Selects diverse final picks from the top-scored candidates.

**Top-N filter** (applied in `rank_candidates` before calling `mmr_select`):
```
n_top = max(5, round(len(candidates) * 0.30))
pool  = scored_candidates[:n_top]
```

**MMR criterion** — iteratively picks the candidate maximizing:
```
lambda_ * score  -  (1 - lambda_) * max_similarity_to_already_selected
```
λ=0.7 gives 70% weight to relevance, 30% to diversity. First pick is always the highest-scored candidate.

**Similarity** is defined on the joint `(primary_type, price_level)` key:
```
both match  → 1.0
one matches → 0.5
neither     → 0.0
```

### 7. Explanation — `rank_candidates()` → Claude Haiku
The 3 selected candidates are passed to Haiku (via `prompt_rank.txt`) as a numbered list. Haiku's sole task is to write a personalized explanation for each — it does not select or reorder.

Each candidate line sent to Haiku includes: `primary_type`, `price_level`, `rating`, `editorial_summary`, and `[previously recommended]` tag if applicable.

Output format per restaurant:
```
N. Restaurant Name - Because you liked [Name1] and [Name2] - 10-15 word description
```
`rank_candidates()` resolves each numbered line back to a `place_id` via `candidate_index`. No extra API call needed.

**Prompt context injected:**
- Session inputs (current request restaurants) and liked history — formatted as `name: type, price, rating`
- `alpha_instruction`: α≥0.7 → emphasize session; α≤0.3 → emphasize history; else empty
- `revisit_instruction`: β≥0.7 → revisits encouraged; β=0.0 → prefer new; else empty
- Liked names (avoid recommending), disliked names (avoid similar), neighborhood, type filter

`max_tokens=500`

### 8. Persistence
All 3 results saved as `RequestRestaurant(type=recommendation)` for future revisit pool and preference tracking. No additional Places API resolution is needed at this stage.

## Frontend Notes
- Username persisted in `localStorage` under key `campfire_username`
- Cities: Chicago, New York (hardcoded in `script.js` `NEIGHBORHOODS` const)
- Restaurant types: Casual, Fine Dining, Bar
- Uses Awesomplete for autocomplete
- Session tokens generated per autocomplete session for Google billing optimization
- **History/Session slider** (`input-weight-slider`): 0–100, step 10, default 70 → sent as `input_weight` (0.0–1.0)
- **Revisit slider** (`revisit-weight-slider`): 0–100, step 25, default 0 → sent as `revisit_weight` (0.0–1.0); labels: "All New" / "Mixed (X% revisit)" / "Revisit Picks"

## Known Open Issues (features/todo.md)
- Restaurant names appear lowercase in preferences tab (sanitize_name strips formatting)
- Input restaurants not auto-liked (no `UserRestaurantPreference` created on input)
- No visual confirmation when autocomplete selects a result
- Basic loading states (no skeleton loaders)

## Environment Variables
- `OPENAI_API_KEY` — required
- `FLASK_ENV` — development / staging / production
- `PLACES_PROVIDER` — google (default) or yelp
- `GOOGLE_API_KEY` / `YELP_API_KEY`
- `DEV_DATABASE_URL` / `STAGING_DATABASE_URL` / `POSTGRES_URL`
- `SUPABASE_URL` / `SUPABASE_KEY` — prod only
