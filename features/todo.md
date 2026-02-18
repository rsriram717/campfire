# Future Improvements & Bug Fixes

## Bugs / Issues
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

- [ ] **Improve loading states**
    - **Observation**: Loading UI is basic.
    - **Evidence**: 
        - `script.js`: Uses simple `.style.display = 'flex'` on a generic `#loading` overlay.
        - Feedback and Preferences tabs use a basic `.spinner` div.
    - **Action**: Implement skeleton loaders or more polished spinner animations.
