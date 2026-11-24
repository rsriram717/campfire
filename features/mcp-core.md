# MCP Core: Implementation Plan

> Tracks GitHub issue #1. This file is the working copy of the plan. Product direction lives in `docs/vision.md`.

## Isolation: a parallel app

The new engine is built alongside the existing app and doesn't touch it.

- **Branch:** all work happens on `claude/restaurant-discovery-mcp-zdbfp4`, which stays unmerged until the engine is ready and the UI cutover has been approved separately.
- **Code:** a new top-level `engine/` package. It does not import from `app.py`, `models.py`, `openai_example.py` or `services/`, and the old code does not import from it.
- **Database:** its own database (`ENGINE_DATABASE_URL`) with its own SQLAlchemy metadata. The old schema and Alembic migrations stay untouched.
- **Dependencies:** `engine/requirements.txt`, layered on top of the root `requirements.txt`.
- **Tests:** in `tests/engine/`, with their own `conftest.py`, so they never share fixtures or the database with the old suite. The old 78+ tests must keep passing at every commit.
- **Deployment:** the existing Vercel app is unchanged. The engine is not deployed until Phase 8.

## Layout

```
engine/
  __init__.py
  config.py        # env vars, model IDs, latency budget
  db.py            # engine/session factory for ENGINE_DATABASE_URL
  models.py        # engine-only SQLAlchemy models
  places.py        # Google Places (New) text search client, live facts only
  web.py           # website fetch + readable-text extraction
  llm.py           # query generation + tag extraction (Claude)
  embeddings.py    # embedding provider interface + per-tag cache
  profiles.py      # user/restaurant tag profiles, outcome updates
  scoring.py       # text score, people score, inverse-variance blend
  discover.py      # search + recommend orchestration
  mcp_server.py    # MCP tool definitions (stdio now, HTTP in Phase 8)
  requirements.txt
tests/engine/
  conftest.py      # in-memory SQLite, fake Places/LLM/embeddings
  fixtures/        # recorded Places + website responses (JSON/HTML)
  test_*.py
scripts/
  engine_eval.py   # offline evaluation harness (Phase 7)
```

## Data model (engine DB)

We store IDs, tags, outcomes and predictions. No Google content is stored: no names, addresses, ratings, hours or review text.

| Table | Columns | Notes |
|---|---|---|
| `users` | id, external_id (unique), created_at | `external_id` comes from auth later. For stdio it comes from config. |
| `restaurants` | place_id (PK), website_url_hash, website_content_hash, tags_extracted_at, extraction_status (`none`/`pending`/`done`/`failed`/`no_website`) | Place ID only. Hashes are for detecting website changes. |
| `tags` | id, text (unique, normalized: lowercased, trimmed), embedding (blob in SQLite, `vector` in Postgres via pgvector), created_at | One row per distinct tag text. No merging of near-duplicates, because embeddings handle similarity at scoring time, so there's no merge threshold to tune. |
| `restaurant_tags` | place_id, tag_id, source (`website`/`user`/`agent`), count, first_seen, last_seen | Descriptive only: what the place *is*. Ratings never write here. |
| `user_tags` | user_id, tag_id, weight (float, signed), evidence_count, updated_at | Positive weight = likes, negative = dislikes. |
| `outcomes` | id, user_id, place_id, verdict (`loved`/`meh`/`disliked`), request_id (nullable), created_at | Match data. Feeds the user profile and the people signal. |
| `outcome_tags` | outcome_id, tag_id | Descriptive tags from the user or agent at feedback time, e.g. "loud". |
| `requests` | id, user_id, lat, lng, request_text, created_at | One per `discover` or `score_candidates` call. |
| `predictions` | request_id, place_id, query_bucket, text_score, text_var, people_score, people_var, n_raters, final_score, returned (bool) | Logged so text-prediction error can be measured against later outcomes. |
| `extraction_queue` | place_id, enqueued_at, attempts, last_error | Tag extraction that didn't fit the latency budget. Worked off in the background. |

Dev runs on SQLite with embeddings computed in numpy. Prod (Phase 8) runs on Supabase Postgres with pgvector.

## External dependencies

- **Google Places API (New):**
  - Calls: `places:searchText` with `locationBias.circle`, `pageSize=20`, following `nextPageToken` up to 3 pages (60 results per query, the API maximum). Also `places/{id}` for `resolve_place` and `score_candidates`.
  - Field mask: `id, displayName, formattedAddress, location, businessStatus, currentOpeningHours, priceLevel, primaryType, types, websiteUri, editorialSummary, googleMapsUri, rating, userRatingCount`.
  - Cost: `websiteUri` and opening hours move requests to a higher-priced SKU. Measure cost per `discover` call in Phase 1.
- **LLM:** Claude Haiku (`claude-haiku-5-5`) through the `anthropic` SDK. Used for query generation and tag extraction, both with structured (JSON) output. The model ID lives in `config.py`.
- **Embeddings:** an interface in `embeddings.py`.
  - Default is OpenAI `text-embedding-3-small`, since `OPENAI_API_KEY` already exists. Voyage is the alternative.
  - Each tag's embedding is computed once and cached in `tags.embedding`. Tags are short and reused heavily, so this cost is small.
- **MCP:** the official `mcp` Python SDK (2.x, Python ≥3.10).

## Algorithms

### Query generation (`llm.generate_queries`)
- **Input:** the user's top tags by |weight| (positives and negatives labelled), plus the optional request text.
- **Output:** 3–6 facets, each with a Places text query and the user tags it targets. The LLM decides the number by how many distinct facets the profile has; we don't fix it.
- **Cold start (no tags yet):**
  - With a request: one query, the request itself.
  - Without one: return an error telling the agent to call `record_outcome` with a few loved places first.

### Candidate search (`places.search`)
- Run one text search per facet in parallel, with pagination.
- Remove duplicates by place ID, keeping the list of facets that found each one.
- Drop anything whose `businessStatus != OPERATIONAL`.
- Drop places the user has already given an outcome for, unless the request asks for revisits.
- The live facts are kept in memory for this request only.

### Tags for candidates (`profiles.ensure_tags`)
- `done`: use the stored tags.
- `none` with a `websiteUri`:
  - Fetch the homepage, plus up to 2 linked pages whose link text matches menu or about.
  - Extract readable text and hash it.
  - The LLM returns 8–20 short descriptive tags.
  - Store the tags with `source=website`.
- `no_website`: no stored tags. The candidate is scored from live Places text only (below).
- **Latency budget:** extraction runs in parallel under a single time budget. This is a product requirement (target: `discover` under about 8 s), not a ranking parameter. Candidates that miss the budget go to `extraction_queue` and are scored from live text this time.
- **Refresh on events:**
  - On a later fetch, a changed `website_content_hash` triggers re-extraction.
  - User or agent tags that conflict with stored tags trigger it too, e.g. "loud" vs "quiet" by embedding opposition. That detection is deferred to Phase 6; for now user tags are simply added.

### Live-text fallback
- For candidates without stored tags, embed the transient Places `editorialSummary` plus `primaryType`, and score it against user tags like a single pseudo-tag.
- It is used for this request only and never stored.
- It carries higher variance, so the blend automatically trusts it less.

### Text score (`scoring.text_score`)
- The user profile U is a set of (embedding u_i, weight w_i). The restaurant R is a set of tag embeddings r_j.
- `text_score = Σ_i w_i · max_j cos(u_i, r_j) / Σ_i |w_i|`, rescaled to [0, 1].
- Each user tag is matched against its best restaurant tag, so a restaurant isn't rewarded for having many tags.
- Negative weights penalize matches with things the user dislikes.
- **Calibration:** map `text_score` to P(loved) using logistic regression fitted on logged `predictions` joined to `outcomes`. Until the logged outcomes include both loved and disliked verdicts (the minimum a logistic fit needs), use the identity mapping.

### People score (`scoring.people_score`)
- Raters are the other users with an outcome for this place.
- Each rater gets a similarity weight s_k: the cosine between the two users' tag profiles (weighted mean embeddings), clipped at 0.
- Outcome values: loved = 1, meh = 0.5, disliked = 0.
- `people_score = Σ s_k·o_k / Σ s_k`
- Effective count: `n_eff = (Σ s_k)² / Σ s_k²`
- `people_var = p(1−p) / n_eff`, using a Beta(1,1) posterior mean for p so that n_eff = 0 gives variance 0.25.

### Blend (`scoring.blend`), with no tuned weights
- `text_var` is the measured mean squared error between calibrated text scores and outcomes, across all logged predictions that have outcomes.
- Before any outcomes exist, it is 0.25, the variance of a coin flip. That is the uninformative value, not a tuned one.
- The live-text fallback uses its own measured error, tracked separately with the same default.
- `final = (text/text_var + people/people_var) / (1/text_var + 1/people_var)`

### Diversify (`discover.select`)
- For each facet, take its highest `final_score` candidate that hasn't been selected yet.
- Order the results by score. The result count equals the facet count, capped by an `n` the caller can pass.
- There is no diversity parameter: variety comes from the facets.

### Outcome updates (`profiles.record_outcome`)
- Insert the outcome. Attach descriptive tags to `outcome_tags` and to `restaurant_tags` (`source=user` or `agent`).
- **User profile:**
  - For each of the restaurant's tags: loved adds +1 to `user_tags.weight`, disliked adds −1, meh adds 0.
  - `evidence_count` is incremented.
  - The weight used in scoring is `weight / evidence_count`, so frequently seen tags don't dominate just by appearing often.
- If the restaurant has no tags yet, extract them first (synchronously; this is the seeding path).

## MCP tools

All tools return structured JSON. The agent writes the prose.

| Tool | Args | Returns |
|---|---|---|
| `resolve_place` | `query`, `lat?`, `lng?` | Up to 5 `{place_id, name, address}` (live). Used to turn "Au Cheval" into an ID. |
| `record_outcome` | `place_id`, `verdict`, `tags?: [str]` | Updated top user tags. Also the cold-start seeding path: "I love these 5 places." |
| `get_taste_profile` | — | Top positive and negative tags with weights and evidence counts. |
| `discover` | `lat`, `lng`, `radius_m?`, `request?`, `n?` | Picks: `{place_id, name, address, open_now, hours, price_level, maps_url, facet, matched_tags, score, confidence}`. |
| `score_candidates` | `place_ids: [str]` | Same shape as `discover`, for candidates the agent found itself. |

- **Identity (Phases 0–7):** stdio only, with the user taken from the `CAMPFIRE_USER` env var in the MCP client config.
- **Phase 8:** replace this with authenticated users.

## Phases

Each phase is one or more focused commits. Every phase must leave both test suites green.

### Phase 0: Scaffolding
- Upgrade the local venv to Python 3.11 and confirm the old 78+ tests pass unchanged. If anything breaks, fix it minimally or report it.
- Create the `engine/` skeleton, `engine/requirements.txt`, `config.py`, `db.py`, `models.py` with `create_all` for dev, and `tests/engine/conftest.py` with fakes for Places, LLM and embeddings.
- **Accept when:** `pytest` runs both suites green, and `python -m engine.mcp_server` starts and lists zero tools.

### Phase 1: Places client
- Build `places.search(query, lat, lng, radius)` with pagination, field mask, business-status filter and dedupe. Add `places.get(place_id)`.
- Record fixtures from real calls for Chicago and NYC queries.
- **Accept when:** unit tests pass on fixtures, and a manual run reports result counts and estimated cost per query.

### Phase 2: Tag extraction
- `web.fetch_site(url)`: timeouts, size cap, robots.txt respected, menu/about link discovery, readable-text extraction.
- `llm.extract_tags(text)` with structured output. `embeddings` with caching. `profiles.ensure_tags` with the latency budget and queue.
- **Accept when:** fixture-based tests pass; a manual run on 10 real restaurants gives sensible tags; re-running skips extraction when the content hash is unchanged.

### Phase 3: Profiles and outcomes
- Build `record_outcome` and `get_taste_profile`, including the seeding path.
- **Accept when:** seeding with 5 loved and 2 disliked places produces a profile whose top tags look right on manual review.

### Phase 4: Discover (text-only)
- Query generation, search, `ensure_tags`, live-text fallback, text score with identity calibration, diversify, and logging to `requests` and `predictions`.
- **Accept when:** an end-to-end test with fakes returns one pick per facet, and a manual run on a seeded profile returns picks across different facets.

### Phase 5: MCP server (stdio), the first usable milestone
- Wire all five tools in `mcp_server.py`. Document the Claude Desktop and Claude Code config in `engine/README.md`.
- **Accept when:** in a real MCP client, seed a profile, call `discover`, record outcomes, and see the profile change.

### Phase 6: People signal and calibration
- People score, measured `text_var`, logistic calibration, and conflicting-tag refresh.
- **Accept when:** a synthetic-population test (simulated users with hidden tastes) shows the blend shifting toward the people signal as raters accumulate, and final-score error drops compared with text-only.

### Phase 7: Evaluation harness
- `scripts/engine_eval.py` takes about 10 hand-built test profiles and reports, per run:
  - Facet coverage.
  - Distinct `primaryType` count.
  - Median `userRatingCount` of picks compared with a popularity baseline, as a niche-ness measure.
  - Repeat rate across runs.
  - Latency and cost.
- Run it against the old pipeline's outputs where possible, for comparison.
- **Accept when:** a baseline report is committed.

### Phase 8: Remote deployment (needs decisions first)
- Streamable HTTP transport, auth, hosting, Postgres with pgvector, and a background worker for `extraction_queue`.
- This phase is blocked on the open questions below.

### Phase 9: UI cutover (separate approval)
- Point the existing UI at the engine, then delete the old pipeline: `build_taste_profile`, `score_candidates`, `mmr_select`, `rank_candidates`, `get_similar_restaurants`, `prompt*.txt`, the stored `Restaurant` catalog, the sliders, and `services/yelp_service.py`.
- This phase is not part of the parallel build.

## Open questions

1. **Auth for remote MCP:** OAuth (spec-compliant, more work) or per-user API keys (simple)? Needed by Phase 8.
2. **Hosting:** a long-running host (Fly, Render, Railway) with Supabase Postgres and pgvector? Vercel serverless doesn't suit background extraction or persistent state.
3. **Places cost at agent volume:** our key or bring-your-own-key?
4. **Embedding provider:** OpenAI (key already exists) or Voyage?
5. **Website fetching:** robots.txt is respected; do we also need a User-Agent policy and per-domain rate limits from day one?
6. **Tag sprawl:** raw tags with no merging is the starting point. Revisit if the `tags` table grows to the point where scoring slows down.
7. **Legal:** have someone review the current Google Maps Platform terms against "store place IDs only, use content live."
