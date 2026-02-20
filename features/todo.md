# Future Improvements & Bug Fixes

## Bugs / Issues

- [ ] **"Why" descriptions don't match the recommended restaurant (high priority)**
    - **Observation**: The "Why" text describes a completely different restaurant than the one shown. E.g. Aba (Mediterranean) gets "Local pizza institution with moderate pricing"; The Dearborn (American brasserie) gets "Classic pizza parlor"; Au Cheval (burger bar) gets "Family-owned pizza chain".
    - **Root cause**: Haiku's output uses the format `N. Name - Because ... - Description`. The `rank_candidates` parser resolves the restaurant by **candidate number** (`candidate_index[N]`), which correctly picks the right restaurant — but the **description text** is whatever Haiku wrote for that line. If Haiku hallucinates or gets confused about which candidate is which, the name/place_id are correct (from the index) but the description is wrong.
    - **Likely causes**:
        1. Haiku may be writing descriptions based on the input restaurants' cuisine (pizza) rather than the actual candidate's profile.
        2. The candidate list sent to Haiku may lack enough metadata (editorial_summary, cuisine_type) for Haiku to write accurate descriptions.
        3. The `max_tokens=300` limit may cause Haiku to rush and produce generic/wrong descriptions.
    - **Possible fixes**: Include more candidate metadata in the numbered list (editorial_summary, categories); post-validate descriptions against candidate data; increase max_tokens.

- [ ] **Session-only recommendations are off (high priority)**
    - **Observation**: Inputting two taquerias (Taqueria Moran + Taqueria Los Comales Logan Square) with no liked history produces unrelated recommendations.
    - **Suspected causes** (needs investigation):
        1. `searchNearby` uses city-center coordinates with no cuisine signal — returns 20 generic top-rated restaurants near the city center, not filtered by Mexican/casual. The session input restaurants' `primary_type` (e.g. `mexican_restaurant`) flows into `build_taste_profile` → `top_cuisine_types` but **this never filters the candidate pool** — it's only visible to Haiku in the prompt's taste profile section, which Haiku apparently ignores when ranking.
        2. When user has no liked history, `liked_names` is `"none"`, so the prompt's "cite two specific restaurants" instruction can't be satisfied — Haiku may fall back to arbitrary picks.
        3. Input restaurants are included in `all_liked_objs` for exclusion but the candidate pool itself has no cuisine affinity signal.
    - **Likely fix**: Pre-filter or bias the `searchNearby` candidate pool using the cuisine types derived from input restaurants (e.g. pass `includedTypes: ["mexican_restaurant"]` when inputs are all Mexican). Or strengthen the ranking prompt so Haiku weights cuisine match more heavily when session inputs are the only signal.
    - **Test case**: Taqueria Moran + Taqueria Los Comales Logan Square → expect Mexican/taqueria-style picks in Logan Square area, not generic top-rated city-center restaurants.
- [ ] **Fix lowercase restaurant names in "Restaurant Preferences"**
    - **Observation**: User reports personalized preferences appear in lowercase.
    - **Evidence**: 
        - `app.py`'s `get_user_preferences` returns raw database names.
        - AI-generated recommendations (`openai_example.py`) might be returning lowercase names, or `sanitize_name` might be effectively stripping formatting if the AI output isn't Title Cased.
        - **Critical Finding**: `get_recommendations` in `app.py` currently ignores `input_restaurants` (text-only inputs) completely. It only processes `place_ids`. This means manual text inputs aren't even factored into the recommendation logic!
    - **Action**: Ensure AI output is Title Cased and properly handle text-only inputs.

- [ ] **Auto-like manual inputs**
    - **Observation**: Manually input restaurants are not automatically "liked".
    - **Evidence**: 
        - `app.py`: `get_recommendations` creates `RequestRestaurant` entries (line 257) but does *not* create `UserRestaurantPreference` entries.
        - `UserRestaurantPreference` is only created via the `/save_preferences` endpoint.
    - **Action**: In `get_recommendations`, explicitly create `UserRestaurantPreference` entries with `PreferenceType.like` for all valid inputs.

- [ ] **Autocomplete feedback**
    - **Observation**: No visual confirmation when autocomplete is selected.
    - **Evidence**: 
        - `script.js`: `initializeAutocomplete` updates the hidden `place_id` field but provides no UI feedback (e.g., checkmark, green border).
        - `styles.css`: No specific styles for a "verified" or "selected" state on inputs.
    - **Action**: Add a visual indicator (icon or class) when `awesomplete-selectcomplete` fires.

- [ ] **Liked restaurant name typo in reason field** *(low priority)*
    - **Observation**: The `reason` field sometimes contains a misspelling of a liked restaurant name (e.g. "Au Chavel" instead of "Au Cheval"). Haiku reconstructs the name from context rather than copying it verbatim.
    - **Action**: Post-process `reason` text in `rank_candidates()` — fuzzy-match each word sequence against the canonical liked restaurant names and substitute the correct spelling.

- [ ] **Improve loading states**
    - **Observation**: Loading UI is basic.
    - **Evidence**: 
        - `script.js`: Uses simple `.style.display = 'flex'` on a generic `#loading` overlay.
        - Feedback and Preferences tabs use a basic `.spinner` div.
    - **Action**: Implement skeleton loaders or more polished spinner animations.
