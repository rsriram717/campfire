# Changelog

All notable changes to Campfire are documented here.

---

## [0.2.0] — 2026-02-24

### Changed — Ranking algorithm overhaul
- Replaced Haiku-as-selector with a deterministic two-stage pipeline:
  - `score_candidates()`: fixed weights (cuisine 0.40, price 0.30, rating 0.25) + soft dislike penalty
  - `mmr_select()`: Maximal Marginal Relevance on top-30% pool (min 5), λ=0.7, similarity on `(primary_type, price_level)`
- Claude Haiku now writes explanations only — it no longer selects or reorders candidates
- Rewritten `prompt_rank.txt` as an explanation task
- Removed manual rating sort from candidate pre-filtering (`app.py`)
- `rank_candidates()` now accepts `disliked_restaurant_objs` and orchestrates the full pipeline

### Changed — Taste profile
- Removed `prefers_dine_in`, `prefers_takeout`, `prefers_reservable` from `build_taste_profile()` output
- Removed dine-in and reservable lines from `_format_profile_lines()` sent to Haiku
- DB columns for these fields are preserved; they are simply no longer used in recommendation logic

### Added
- `score_candidates()` in `openai_example.py`
- `mmr_select()` in `openai_example.py`
- `scripts/benchmark_ranking.py` — 3-scenario benchmark with before/after comparison
- `scripts/benchmark_results/` — baseline and post-implementation benchmark JSONs
- `docs/recommendation-flow.md` — full algorithm reference (scoring formula, MMR, prompt, schema)
- `CHANGELOG.md`
- 19 new tests in `tests/unit/test_scoring.py` (78 total, up from 39 in v0.1.0)

### Benchmark (selection only, no LLM)
| Scenario | v0.1.0 (rating sort) | v0.2.0 (score+MMR) |
|---|---|---|
| Taqueria session, no history | Alinea ★4.9, Nobu ★4.8, Eataly ★4.7 | Taqueria Chingon ★4.6, Frontera Grill ★4.5, El Torito ★4.4 |
| Italian history, sushi dislikes | Nobu ★4.9, Juno Sushi ★4.7, Spacca ★4.7 | Spacca Napoli ★4.7, Eataly ★4.5, Au Cheval ★4.5 |
| No cuisine signal (regression) | Alinea ★4.9, Smyth ★4.8, Oriole ★4.7 | Smyth ★4.8, Moody Tongue ★4.6, Temporis ★4.5 |

---

## [0.1.0] — 2026-02-19

### Initial formalized release
- Candidate-based recommendation flow replacing GPT-4 name invention with real Google Places candidates ranked by Claude Haiku
- `build_taste_profile()` with α weighting between session inputs and liked history
- Revisit pool (β slider): inject previously recommended restaurants or use revisit pool exclusively
- Pre-filtering pipeline: lodging removal, exclusion list, rating floor (3.5), type filter (Casual / Fine Dining / Bar)
- Cuisine-type biased `searchNearby` when α > 0.3
- Flask-Migrate / Alembic schema migrations; `cuisine_type` column migrated to TEXT
- 39-test suite covering integration scenarios, candidate filtering, taste profile, and rank output parsing
- Vercel deployment config
