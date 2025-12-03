# Code Removal Checklist

This document lists all code that must be removed to avoid conflicts with the new UI.

---

## templates/index.html

### Complete Removal

| Lines | Element | Reason |
|-------|---------|--------|
| 14-19 | `<header class="bg-primary">` block | Replaced by new `.app-header` |
| 22-30 | `<ul class="nav nav-tabs">` block | Navigation moves to header |
| 33-103 | `<div class="tab-content">` wrapper | Replaced by `.tab-panel` structure |
| 36-45 | Name input with "Remember me" checkbox | Simplified input design |
| 47-61 | Restaurant inputs with add/remove buttons | Static 6-input design |
| 63-78 | Restaurant type checkboxes | Replaced by toggle switches |
| 81-96 | Location filter section | Replaced by pill dropdowns |
| 98-99 | Submit button and loading div | Replaced by new CTA |
| 104-126 | Preferences tab content | Will be restructured |

### Specific Elements to Remove

```html
<!-- REMOVE: Old header -->
<header class="bg-primary text-white text-center py-4">
    ...
</header>

<!-- REMOVE: Bootstrap tab navigation -->
<ul class="nav nav-tabs" id="myTab" role="tablist">
    ...
</ul>

<!-- REMOVE: "Remember me" checkboxes (both tabs) -->
<div class="form-check mt-2">
    <input type="checkbox" class="form-check-input" id="remember-me">
    <label class="form-check-label" for="remember-me">Remember me</label>
</div>

<!-- REMOVE: Add restaurant button -->
<button type="button" id="add-restaurant-btn" class="btn btn-secondary btn-sm mt-2">+ Add Another</button>

<!-- REMOVE: Remove restaurant buttons -->
<button type="button" class="btn btn-danger remove-restaurant-btn">
    <i class="bi bi-x-circle"></i>
</button>

<!-- REMOVE: Old filter sections -->
<div class="form-group filter-section">
    ...
</div>

<!-- REMOVE: Bootstrap classes throughout -->
- class="container mt-5"
- class="tab-content"
- class="tab-pane fade show active"
- class="form-group"
- class="form-control"
- class="form-row"
- class="col-md-6"
- class="btn btn-primary btn-block"
- class="btn btn-secondary"
- class="card mb-3"
- class="card-body"
- class="d-flex justify-content-between"
```

---

## static/styles.css

### Complete Removal (Delete Entire File)

The entire file should be deleted and rewritten. Here's what each section was for:

| Lines | Section | Status |
|-------|---------|--------|
| 1-7 | `:root` variables | REPLACE with new theme |
| 9-12 | `body` | REPLACE |
| 14-16 | `header.bg-primary` | DELETE (Bootstrap override) |
| 18-44 | `.uiverse-input, .uiverse-select` | REPLACE with `.input-field` |
| 46-50 | `.loading` | REPLACE with `.loading-indicator` |
| 52-56 | `.recommendations-output` | REPLACE with `.recommendations-cards` |
| 58-70 | `.preference-btn`, `.btn-group` | DELETE (Bootstrap) |
| 71-102 | `.custom-checkbox` | DELETE (not used) |
| 104-121 | `.preference-container`, `.checkbox-wrapper` | DELETE |
| 123-157 | `.preference-toggle` | KEEP concept, RESTYLE |
| 159-176 | `header h1`, `header .subtitle` | DELETE (old header) |
| 178-204 | `.btn-primary`, `.btn-secondary`, `.nav-tabs` | DELETE (Bootstrap overrides) |
| 206-213 | `.card`, `.card-title` | DELETE (Bootstrap cards) |
| 215-263 | `.restaurant-input-group`, `.awesomplete` | REPLACE |
| 265-273 | Validation styles | REPLACE |
| 275-333 | `.filter-section`, `.type-filter-group` | REPLACE |

---

## static/script.js

### Functions to Remove

| Lines | Function/Code | Reason |
|-------|---------------|--------|
| 137-146 | `updateRemoveButtons()` | No more dynamic add/remove |
| 187-189 | `updateAddButtonState()` | No more add button |
| 192-215 | `addRestaurantBtn.addEventListener` | No more add button |
| 217-223 | `restaurantInputsContainer.addEventListener` (remove btn) | No more remove buttons |
| 231-232 | `updateAddButtonState()`, `updateRemoveButtons()` calls | Cleanup |

### Code Blocks to Modify

```javascript
// REMOVE: Add button listener (lines 192-215)
addRestaurantBtn.addEventListener('click', function() {
    const count = restaurantInputsContainer.querySelectorAll('.restaurant-input-group').length;
    if (count >= MAX_RESTAURANTS) return;
    // ... entire block
});

// REMOVE: Remove button listener (lines 217-223)
restaurantInputsContainer.addEventListener('click', function(event) {
    if (event.target.classList.contains('remove-restaurant-btn')) {
        // ... entire block
    }
});

// REMOVE: These function calls
updateAddButtonState();
updateRemoveButtons();
```

### Variables to Remove

```javascript
// REMOVE: These variables (no longer needed)
const addRestaurantBtn = document.getElementById('add-restaurant-btn');
const MAX_RESTAURANTS = 5;
```

### DOM Selectors to Update

```javascript
// OLD → NEW
'#restaurant-form' → '#recommendation-form'
'.restaurant-input-group' → '.input-field-wrapper'
'.form-control' → '.input-field'
'.card mb-3' → '.recommendation-card'
'.card-body' → (removed, content directly in card)
'.card-title' → '.restaurant-name'
'.card-text' → '.recommendation-reason'
'.nav-link' → '.nav-tab'
'.tab-pane' → '.tab-panel'
```

### Bootstrap Dependencies to Remove

```javascript
// REMOVE: Bootstrap tab toggle reliance
// Currently relies on data-toggle="tab" in HTML
// Replace with custom tab switching logic
```

---

## Summary: What Gets Deleted vs Replaced

### Deleted Entirely
- Bootstrap tab structure
- "Remember me" checkboxes
- Add/remove restaurant buttons
- Character count displays
- Old header with subtitle
- All Bootstrap utility classes

### Replaced with New Implementation
- Header → New app header with inline nav
- Tab navigation → Custom JS tab switching
- Form inputs → New styled inputs
- Filter sections → Pill dropdowns + toggles
- Recommendation cards → New card design with actions
- Loading indicator → New spinner design

### Kept but Modified
- Autocomplete functionality (Awesomplete)
- Username handling logic (UsernameHandler)
- Form submission logic
- Preference toggle concept
- API calls (fetch)

---

## Pre-Implementation Backup

Before starting, create backups:

```bash
cp templates/index.html templates/index.html.bak
cp static/styles.css static/styles.css.bak
cp static/script.js static/script.js.bak
```

Or simply rely on git:
```bash
git stash
# or
git checkout main -- templates/ static/
```
