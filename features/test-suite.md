# Test Suite

39 tests, all passing. Runs automatically before every `git push` via `.git/hooks/pre-push`.

## Running tests

```bash
venv/bin/python -m pytest                          # unit + integration (default)
venv/bin/python -m pytest -m smoke                 # smoke only (real APIs)
venv/bin/python -m pytest tests/unit -v            # unit only, verbose
venv/bin/python -m pytest tests/integration -v     # integration only, verbose
```

## Structure

```
tests/
  conftest.py                              # app fixture, in-memory SQLite, mock factories, DB seeders
  unit/
    test_build_taste_profile.py            # 9 tests — weighted profile from history + inputs
    test_candidate_filtering.py            # 18 tests — lodging, exclusion, rating floor, type filter, sort
  integration/
    test_recommendation_scenarios.py       # 12 tests — full route scenarios via POST /get_recommendations
  smoke/
    test_end_to_end.py                     # 1 test — real Haiku + Google Places (excluded by default)
```

## Test infrastructure

- **DB**: In-memory SQLite with `StaticPool` (single shared connection so seeds are visible to routes)
- **Isolation**: `clean_db` fixture (autouse) truncates all tables before and after each test
- **Mocked boundaries**: `places_service.get_details`, `places_service.search_nearby_candidates`, `rank_candidates`
- **Mock strategy**: `rank_candidates_echo` returns the first 3 candidates it receives — tests assert on `mock.call_args` to verify what the candidate pool looked like

### Key design decision: no nested app contexts

The session-scoped `app` fixture pushes one app context that stays active for all tests. Tests seed data and make assertions directly — never via `with app.app_context():`. Nesting contexts triggers Flask-SQLAlchemy's `teardown_appcontext`, which removes the wrong scoped session (the outer one) because the scope key is `id(current_app_ctx)` and the inner context has already been popped by teardown time.

## Integration scenarios

| # | Scenario | α | β | Key assertion |
|---|----------|---|---|---------------|
| 1 | Fresh user, new inputs | 0.7 | 0.0 | `get_details` called per new place_id; restaurants created |
| 2 | Returning user, cached inputs | 0.7 | 0.0 | `get_details` NOT called; history in `liked_restaurant_objs` |
| 3 | β=0 excludes prev recommended | 0.7 | 0.0 | Prev recommended place_ids absent from candidates |
| 4 | β=0.5 injects revisits | 0.7 | 0.5 | Revisit candidates present in pool alongside Google results |
| 5 | β=1.0 skips Google | 0.7 | 1.0 | `search_nearby_candidates` NOT called; all candidates are revisits |
| 6 | β=1.0 falls back with <3 revisits | 0.7 | 1.0 | Falls back to Google silently |
| 7 | Mixed cached + new inputs | 0.5 | 0.0 | `get_details` called only for new; both in `input_restaurant_objs` |
| 8 | Disliked excluded | 0.7 | 0.0 | Disliked place_ids absent from candidates |
| 9 | Duplicate place_ids deduped | 0.7 | 0.0 | `get_details` called once; one Restaurant created |
| 10-12 | Validation (missing city/user/empty) | — | — | Returns 400 |
