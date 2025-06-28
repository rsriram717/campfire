# Username Input & "Remember Me" Guidelines (Frontend)

These rules govern how username handling should work in both the **Get Recommendations** and **Restaurant Preferences** tabs. They keep each user's data private while making it simple to reuse the same name.

---

## 1. Input Sanitisation (Client-side)

* Trim leading/trailing whitespace on every submit.
* Collapse multiple inner spaces into a single space (`"Jane   Doe" → "Jane Doe"`).
* Allowed characters: letters, numbers, spaces, hyphen (`-`), apostrophe (`'`).
* Enforce length 2-50 characters; display a live character counter in the UI.

## 2. "Remember me" (Opt-in, Local Only)

* Checkbox beside the username field, default **unchecked**.
* If checked, store the sanitised username in `localStorage` under the key `campfire_username`.
* On page load:
  * If the key exists, pre-fill both username fields and tick both checkboxes.
  * Show a small alert: `"Continuing as Jane Doe — Not you? Clear."`  Clicking **Clear** removes the key and empties the inputs.

## 3. Validation Feedback

* Inline indicator (green check) once the name passes regex & length tests.

## 4. Shared Component

* Put trimming, validation, and "Remember me" logic in one JS module or helper so both tabs stay in sync.

## 5. No Cross-user Discovery

* Do **not** offer autocomplete, recent users, or search across usernames.
* The only hint is the local username stored via "Remember me".

---

Adhering to these guidelines keeps the username flow smooth and private while retaining the simple text-based model already in place. 