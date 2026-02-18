# Campfire - Project Context

## What It Is
AI-powered restaurant recommendation web app. Users input favorite restaurants → GPT-4 suggests 3 new ones based on liked/disliked history, city, neighborhood, and type filters.

## Stack
- **Backend**: Flask (Python 3.9), SQLAlchemy ORM, Flask-Migrate/Alembic
- **DB**: SQLite (dev) / PostgreSQL via Supabase (prod), env-selected via `FLASK_ENV`
- **AI**: OpenAI GPT-4 via `openai_example.py` + `prompt.txt` template
- **Places**: Google Places or Yelp Fusion (configured via `PLACES_PROVIDER` env var), abstracted in `services/`
- **Frontend**: Vanilla JS + Bootstrap 4, no build step — just `static/script.js` and `static/styles.css`
- **Deployment**: Vercel (`vercel.json`), instance path set to `/tmp/instance` for writable FS

## Key Files
- `app.py` — all Flask routes and DB logic
- `models.py` — SQLAlchemy models
- `openai_example.py` — GPT-4 call + response parsing
- `prompt.txt` — GPT-4 prompt template (uses `.format()` placeholders)
- `services/` — Google/Yelp Places abstraction (`places_service` imported in app.py)
- `utils.py` — `generate_slug(name, city)`
- `templates/index.html` — single-page UI with tab panels
- `static/script.js` — tab switching, autocomplete, form submission, preference UI
- `features/todo.md` — tracked bugs and open improvements

## DB Models
- `User` — name (unique), email
- `Restaurant` — name, location, cuisine_type, provider, place_id, slug (unique constraint on provider+place_id and slug)
- `UserRequest` — user_id, city, timestamp
- `RequestRestaurant` — links request ↔ restaurant, type = `input` or `recommendation`
- `UserRestaurantPreference` — user_id, restaurant_id, preference = `like/dislike/neutral`
- `FeedbackSuggestion` + `FeedbackVote` — community feedback leaderboard with upvote/downvote

## Recommendation Flow
1. User submits place_ids (from autocomplete) + city/neighborhood/types
2. `app.py` fetches/creates `Restaurant` records from Places API
3. Pulls user's liked/disliked history from `UserRestaurantPreference`
4. Calls `get_similar_restaurants()` → GPT-4 returns: `Name - Because you liked X and Y - Description`
5. Each recommendation is resolved back to a canonical Google Place (autocomplete → get_details)
6. Falls back to `provider='campfire_ai'` if resolution fails
7. All results saved as `RequestRestaurant` with type=`recommendation`

## GPT-4 Prompt Format
Output format: `Restaurant Name - Because you liked [Source 1] and [Source 2] - Description`
- Two specific liked restaurant names required as sources
- If no connection: `Name - - Description`
- 10-15 word description
- `max_tokens=150` — keep in mind this is tight for 3 recommendations

## Frontend Notes
- Username persisted in `localStorage` under key `campfire_username`
- Cities: Chicago, New York (hardcoded in `script.js` `NEIGHBORHOODS` const)
- Restaurant types: Casual, Fine Dining, Bar
- Uses Awesomplete for autocomplete
- Session tokens generated per autocomplete session for Google billing optimization

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
