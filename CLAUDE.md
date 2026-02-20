# Campfire - Project Context

## Development Guidelines
- **Documentation**: Every new feature must include updates to `README.md`, `CLAUDE.md`, and `memory/MEMORY.md` before committing.

## What It Is
AI-powered restaurant recommendation web app. Users input favorite restaurants → Claude Haiku ranks real Google Places candidates and returns 3 personalized picks, based on liked/disliked history, city, neighborhood, type filters, and two weighting sliders.

## Stack
- **Backend**: Flask (Python 3.9), SQLAlchemy ORM, Flask-Migrate/Alembic
- **DB**: SQLite (dev) / PostgreSQL via Supabase (prod), env-selected via `FLASK_ENV`
- **AI**: Claude Haiku (`claude-haiku-4-5-20251001`) via `openai_example.py` + `prompt_rank.txt` for ranking; legacy GPT-4 path preserved in `prompt.txt` but unused by main flow
- **Places**: Google Places or Yelp Fusion (configured via `PLACES_PROVIDER` env var), abstracted in `services/`
- **Frontend**: Vanilla JS + Bootstrap 4, no build step — just `static/script.js` and `static/styles.css`
- **Deployment**: Vercel (`vercel.json`), instance path set to `/tmp/instance` for writable FS

## Key Files
- `app.py` — all Flask routes, DB logic, `_restaurant_to_candidate()` helper
- `models.py` — SQLAlchemy models
- `openai_example.py` — `build_taste_profile`, `rank_candidates` (Claude Haiku), legacy `get_similar_restaurants` (GPT-4)
- `prompt_rank.txt` — Claude Haiku ranking prompt (active)
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
1. User submits `place_ids` + `city`/`neighborhood`/`types` + `input_weight` + `revisit_weight`
2. `app.py` fetches/creates `Restaurant` records for each input place_id via Places API
3. Pulls user's liked/disliked history from `UserRestaurantPreference`
4. Queries `prev_recommended` pool: prior `RequestRestaurant(type=recommendation)` for this user+city, excluding disliked
5. **Candidate pool construction** (controlled by `revisit_weight` β):
   - β=0.0: Google `searchNearby` for 20 candidates; prev_recommended added to exclusion set
   - β=0.5: Google search + top-rated revisit candidates injected into pool
   - β=1.0 (≥3 revisits available): skip Google entirely; use revisit pool only
   - β=1.0 (< 3 revisits): fall back to Google silently
6. Pre-filter candidates: remove lodging, low-rated (<3.5), already-seen, type mismatches
7. Build weighted taste profile via `build_taste_profile()` (controlled by `input_weight` α)
8. Call `rank_candidates()` → Claude Haiku reads `prompt_rank.txt`, picks top 3 by number from candidate list
9. All ranked results saved as `RequestRestaurant(type=recommendation)` — no additional API resolution needed

## Prompt Format (`prompt_rank.txt`)
Output format: `N. Restaurant Name - Because you liked [Liked 1] and [Liked 2] - 10-15 word description`
- Claude picks by candidate number; `rank_candidates()` resolves name/place_id from `candidate_index`
- Revisit candidates tagged `[previously recommended]` in the numbered list
- `{revisit_instruction}` adjusts guidance based on β (≥0.7: revisits OK, =0: prefer new, else: empty)
- `max_tokens=300`

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
