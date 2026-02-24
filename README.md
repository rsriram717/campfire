# Campfire

> *More than just a meal* — v0.2.0

Campfire is an AI-powered restaurant recommendation app. Input restaurants you love, and Campfire finds 3 personalized picks from real nearby places — no hallucinations, no invented names.

**[Changelog](CHANGELOG.md) · [Recommendation algorithm](docs/recommendation-flow.md)**

---

## How it works

1. You enter 1–5 restaurants you like (via Google Places autocomplete)
2. Campfire fetches real nearby candidates from the Google Places API
3. A scoring function ranks candidates by cuisine match, price match, and rating — weighted against your taste profile and dislike history
4. MMR (Maximal Marginal Relevance) selects 3 diverse picks from the top-scored candidates
5. Claude Haiku writes a personalized "Because you liked X" explanation for each pick

Full algorithm detail: [docs/recommendation-flow.md](docs/recommendation-flow.md)

---

## Features

- **Taste profile**: weighted blend of your liked history and current session inputs, controlled by the History/Session slider (α)
- **Revisit mode**: Revisit slider (β) surfaces previously recommended restaurants instead of always finding new ones
- **Preference tracking**: Like/dislike system that influences future recommendations via the dislike penalty in scoring
- **City + neighborhood filtering**: Chicago and New York supported; neighborhood passed as context to Haiku
- **Restaurant type filtering**: Casual, Fine Dining, Bar
- **Community feedback**: Upvote/downvote suggestions via the Feedback tab

---

## Stack

- **Backend**: Flask (Python 3.9), SQLAlchemy ORM, Flask-Migrate/Alembic
- **DB**: SQLite (dev) / PostgreSQL via Supabase (prod)
- **AI**: Claude Haiku (`claude-haiku-4-5-20251001`) via Anthropic API
- **Places**: Google Places API (or Yelp Fusion via `PLACES_PROVIDER=yelp`)
- **Frontend**: Vanilla JS + Bootstrap 4, no build step

---

## Setup

### Prerequisites
- Python 3.9+
- Anthropic API key (`ANTHROPIC_API_KEY`)
- Google API key (`GOOGLE_API_KEY`)

### Install

```bash
git clone <repository-url>
cd campfire
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Configure

```bash
cp .env.example .env
# Edit .env — set ANTHROPIC_API_KEY, GOOGLE_API_KEY at minimum
```

Key environment variables:

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | For Claude Haiku explanation calls |
| `GOOGLE_API_KEY` | Yes (if using Google) | For Places autocomplete + searchNearby |
| `OPENAI_API_KEY` | No | Legacy; only needed if using the unused GPT-4 path |
| `FLASK_ENV` | No | `development` / `staging` / `production` (default: `development`) |
| `PLACES_PROVIDER` | No | `google` (default) or `yelp` |
| `DEV_DATABASE_URL` | No | Default: `sqlite:////tmp/restaurant_recommendations.db` |
| `POSTGRES_URL` | Prod only | PostgreSQL connection string |

### Initialize DB and run

```bash
flask db upgrade
python app.py
# → http://localhost:3001
```

---

## Project structure

```
campfire/
├── app.py                  # Flask routes + full recommendation orchestration
├── models.py               # SQLAlchemy models
├── openai_example.py       # build_taste_profile, score_candidates, mmr_select, rank_candidates
├── prompt_rank.txt         # Haiku explanation prompt template
├── prompt.txt              # Legacy GPT-4 prompt (inactive, preserved)
├── utils.py                # generate_slug()
├── services/
│   ├── google_service.py   # searchNearby, get_details, autocomplete
│   ├── yelp_service.py     # Yelp stub (search_nearby_candidates returns [])
│   └── places.py           # Abstract interface
├── templates/index.html    # Single-page UI
├── static/
│   ├── script.js           # Tab switching, autocomplete, form logic, sliders
│   └── styles.css
├── tests/                  # 78 tests — run with venv/bin/python -m pytest
├── docs/
│   └── recommendation-flow.md  # Full algorithm reference
├── scripts/
│   └── benchmark_ranking.py    # Before/after selection benchmark
├── features/
│   └── todo.md             # Open bugs and improvements
├── migrations/             # Alembic migrations
└── CHANGELOG.md
```

---

## Development

### Run tests
```bash
venv/bin/python -m pytest
```
All 78 tests must pass before pushing. The pre-push hook enforces this automatically.

### Database migrations
```bash
flask db migrate -m "description"
flask db upgrade
```

### Benchmark the ranking algorithm
```bash
venv/bin/python scripts/benchmark_ranking.py --tag baseline   # before changes
venv/bin/python scripts/benchmark_ranking.py --tag new        # after changes
# Results saved to scripts/benchmark_results/
```

### Adding cities
Add the city + neighbourhood list to the `NEIGHBORHOODS` const in `static/script.js`. No backend changes needed.

---

## API

| Method | Route | Description |
|---|---|---|
| `GET` | `/` | Main UI |
| `POST` | `/get_recommendations` | Run the recommendation pipeline |
| `POST` | `/save_preferences` | Update like/dislike preferences |
| `GET` | `/get_user_preferences` | Fetch user's preferences |
| `GET` | `/check_user` | Check if user exists |
| `GET` | `/get_restaurants` | List all restaurants in DB |
| `GET` | `/autocomplete` | Places autocomplete proxy |
| `POST` | `/feedback` | Submit a feedback suggestion |
| `POST` | `/feedback/vote` | Upvote or downvote a suggestion |

**`POST /get_recommendations` request body:**
```json
{
  "user": "rishi",
  "place_ids": ["ChIJabc...", "ChIJdef..."],
  "city": "Chicago",
  "neighborhood": "West Loop",
  "restaurant_types": ["Casual"],
  "input_weight": 0.7,
  "revisit_weight": 0.0
}
```
