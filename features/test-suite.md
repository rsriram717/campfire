# Test Suite (in progress)

Files exist on disk but are NOT committed yet:
- `tests/conftest.py` — fixtures, DB seeding helpers, `rank_candidates_echo` mock
- `tests/unit/test_build_taste_profile.py` — 9 tests, all passing
- `tests/unit/test_candidate_filtering.py` — 18 tests, all passing
- `tests/integration/test_recommendation_scenarios.py` — 12 tests, 11 passing, 1 flaky
- `tests/smoke/test_end_to_end.py` — excluded from normal runs (`-m smoke`)
- `pytest.ini` — marks `smoke`, default excludes smoke tests

## Outstanding issue: `TestDislikedExcluded` flaky in sequence

Passes in isolation but fails when run after other integration tests.
Root cause: SQLAlchemy's scoped session uses `id(current_app_ctx)` as scope key.
When a nested `with app.app_context()` block exits, Flask fires `teardown_appcontext`
— but by then, the outer context is current, so `db.session.remove()` tears down
the OUTER session rather than the inner one. With StaticPool, this can leave the
shared connection in an unexpected state between tests.

## Fix options (pick one when resuming)
1. **Remove `with app.app_context()` from test seeds** — the `app` fixture already
   pushes an outer context; seed directly in that context without nesting.
2. **Use `db.session.begin_nested()` (SAVEPOINT)** per test and roll back instead
   of deleting rows — eliminates teardown session interference.
3. **File-based SQLite** (`/tmp/test_campfire.db`) — avoids in-memory per-connection
   isolation entirely; clean_db truncates tables normally.

Option 1 is probably the smallest change.
