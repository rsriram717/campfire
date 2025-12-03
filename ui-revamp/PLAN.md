# UI Revamp Implementation Plan

This document outlines the step-by-step technical implementation plan for the Campfire UI redesign.

---

## Overview

Transform the current Bootstrap-based light theme into a modern dark/warm theme with a two-column layout, inline navigation, and enhanced UX components.

---

## Phase 1: HTML Structure Overhaul

### 1.1 Replace Header Structure

**Current (REMOVE):**
```html
<header class="bg-primary text-white text-center py-4">
    <h1 class="display-4">Campfire</h1>
    <div class="subtitle mt-3 mb-2">
        <p class="lead">More than just a meal</p>
    </div>
</header>
```

**New Structure:**
```html
<header class="app-header">
    <div class="header-content">
        <div class="logo">
            <span class="fire-icon">🔥</span>
            <span class="logo-text">Campfire</span>
            <span class="fire-icon">🔥</span>
        </div>
        <nav class="main-nav">
            <button class="nav-tab active" data-tab="recommendations">Get Recommendations</button>
            <button class="nav-tab" data-tab="preferences">Restaurant Preferences</button>
            <button class="nav-tab" data-tab="history">Request History</button>
        </nav>
        <div class="user-profile">
            <span class="user-icon">👤</span>
            <span class="user-name" id="header-user-name">User Name</span>
        </div>
    </div>
</header>
```

### 1.2 Replace Tab Navigation

**Current (REMOVE):**
```html
<ul class="nav nav-tabs" id="myTab" role="tablist">
    <li class="nav-item">
        <a class="nav-link active" id="recommendations-tab" data-toggle="tab" href="#recommendations" ...>
    </li>
    ...
</ul>
```

**Action:** Remove Bootstrap tab structure entirely. Navigation moves to header (see 1.1).

### 1.3 Create Two-Column Layout

**Current (REMOVE):**
```html
<div class="container mt-5">
    <!-- Tab panes -->
    <div class="tab-content">
        <div class="tab-pane fade show active" id="recommendations" ...>
            <form id="restaurant-form" class="mt-4">
                ...
            </form>
            <div id="recommendations-output" class="recommendations-output mt-4"></div>
        </div>
        ...
    </div>
</div>
```

**New Structure:**
```html
<main class="app-main">
    <div class="main-container">
        <!-- Tab: Get Recommendations -->
        <div class="tab-panel active" id="recommendations-panel">
            <div class="two-column-layout">
                <div class="left-panel">
                    <!-- Form content here -->
                </div>
                <div class="right-panel">
                    <h2 class="panel-title">Your Personalized Suggestions</h2>
                    <div id="recommendations-output" class="recommendations-cards">
                        <!-- Recommendation cards rendered here -->
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Tab: Restaurant Preferences -->
        <div class="tab-panel" id="preferences-panel">
            <!-- Single column layout for preferences -->
        </div>
        
        <!-- Tab: Request History (NEW) -->
        <div class="tab-panel" id="history-panel">
            <!-- History content -->
        </div>
    </div>
</main>
```

### 1.4 Redesign Form Inputs (Left Panel)

**Current Name Input (REMOVE):**
```html
<div class="form-group">
    <label for="name">Name:</label>
    <small class="form-text text-muted mb-2">This name saves your preferences...</small>
    <input type="text" id="name" placeholder="Enter your name" required class="uiverse-input form-control" ...>
    <small id="name-char-count" class="form-text text-muted"></small>
    <div class="form-check mt-2">
        <input type="checkbox" class="form-check-input" id="remember-me">
        <label class="form-check-label" for="remember-me">Remember me</label>
    </div>
</div>
```

**New Name Input:**
```html
<div class="form-field">
    <div class="field-header">
        <span class="field-icon">👤</span>
        <span class="field-label">Enter your name</span>
    </div>
    <input type="text" id="name" placeholder="Cnheces" class="input-field" required>
</div>
```

**Note:** Remove "Remember me" checkbox from visible UI. Handle persistence automatically or via settings.

### 1.5 Redesign Restaurant Inputs

**Current (REMOVE):**
```html
<div class="form-group">
    <label>Favorite Restaurants:</label>
    <div id="restaurant-inputs">
        <div class="restaurant-input-group">
            <div class="awesomplete">
                <input type="text" name="restaurant_name" placeholder="Start typing..." class="form-control">
            </div>
            <input type="hidden" name="place_id">
            <button type="button" class="btn btn-danger remove-restaurant-btn">
                <i class="bi bi-x-circle"></i>
            </button>
        </div>
    </div>
    <button type="button" id="add-restaurant-btn" class="btn btn-secondary btn-sm mt-2">+ Add Another</button>
</div>
```

**New Structure (6 static inputs, no add/remove buttons):**
```html
<div class="restaurant-inputs-section">
    <div class="input-field-wrapper">
        <input type="text" name="restaurant_name" placeholder="Favorite Restaurants" class="input-field" data-index="0">
        <input type="hidden" name="place_id" data-index="0">
    </div>
    <div class="input-field-wrapper">
        <input type="text" name="restaurant_name" placeholder="Favorite Restaurants" class="input-field" data-index="1">
        <input type="hidden" name="place_id" data-index="1">
    </div>
    <!-- Repeat for indices 2-5 (total 6 inputs) -->
</div>
```

### 1.6 Redesign Filters Section

**Current Location Section (REMOVE):**
```html
<div class="form-group filter-section">
    <label>Location</label>
    <div class="form-row">
        <div class="form-group col-md-6">
            <label for="city" class="sub-label">City</label>
            <select id="city" class="uiverse-select">...</select>
        </div>
        <div class="form-group col-md-6">
            <label for="neighborhood" class="sub-label">Neighborhood (Optional)</label>
            <input type="text" id="neighborhood" placeholder="e.g. West Loop" class="uiverse-input">
        </div>
    </div>
</div>
```

**Current Type Filter (REMOVE):**
```html
<div class="form-group filter-section">
    <label>Restaurant Type</label>
    <div class="type-filter-group">
        <div class="type-filter-option">
            <input type="checkbox" id="type_casual" value="casual">
            <label for="type_casual">Casual</label>
        </div>
        ...
    </div>
</div>
```

**New Neighborhood Section:**
```html
<div class="filter-section">
    <div class="section-header">
        <span class="section-icon">⭐</span>
        <span class="section-label">Neighborhood</span>
    </div>
    <div class="filter-row">
        <div class="pill-dropdown">
            <select id="city" class="pill-select">
                <option value="Chicago">City Chicago</option>
                <option value="New York">City New York</option>
            </select>
        </div>
        <div class="pill-dropdown">
            <select id="neighborhood" class="pill-select">
                <option value="">Neighborhood</option>
                <option value="Wicker Park">Wicker Park</option>
                <option value="West Loop">West Loop</option>
                <!-- Dynamic based on city -->
            </select>
        </div>
        <div class="pill-dropdown">
            <select id="restaurant-type-dropdown" class="pill-select">
                <option value="">Restaurant Type</option>
                <option value="casual">Casual</option>
                <option value="sit-down">Sit-Down</option>
                <option value="bar">Bar</option>
            </select>
        </div>
    </div>
    <div class="toggle-row">
        <div class="toggle-option">
            <span class="toggle-dot"></span>
            <span class="toggle-label">Casual</span>
        </div>
        <div class="toggle-option">
            <span class="toggle-dot"></span>
            <span class="toggle-label">Sit-Down</span>
        </div>
        <div class="toggle-option active">
            <span class="toggle-dot"></span>
            <input type="checkbox" id="type_bar" class="toggle-switch" checked>
            <span class="toggle-label">Bar</span>
        </div>
    </div>
</div>
```

### 1.7 Redesign CTA Button

**Current (REMOVE):**
```html
<button type="submit" class="btn btn-primary btn-block">Get Recommendations</button>
<div id="loading" class="loading mt-3" style="display: none;">Loading...</div>
```

**New:**
```html
<button type="submit" class="cta-button" id="submit-btn">
    <span class="cta-text">Get Recommendations</span>
</button>
<div id="loading" class="loading-indicator" style="display: none;">
    <span class="spinner"></span>
</div>
```

### 1.8 Redesign Recommendation Cards (Right Panel)

**Current JS-generated (REMOVE from script.js):**
```javascript
recommendationsOutput.innerHTML = data.recommendations.map(rec => `
    <div class="card mb-3">
        <div class="card-body">
            <h5 class="card-title text-primary">${rec.name}</h5>
            <p class="card-text">${rec.description}</p>
        </div>
    </div>
`).join('');
```

**New JS-generated:**
```javascript
recommendationsOutput.innerHTML = data.recommendations.map(rec => `
    <div class="recommendation-card">
        <h3 class="restaurant-name">${rec.name}</h3>
        <p class="recommendation-reason">
            <span class="reason-label">Why it's recommended:</span> ${rec.description}
        </p>
        <div class="card-actions">
            <button class="action-btn like-btn" data-restaurant="${rec.name}">👍</button>
            <button class="action-btn dislike-btn" data-restaurant="${rec.name}">👎</button>
        </div>
    </div>
`).join('');
```

---

## Phase 2: CSS Complete Rewrite

### 2.1 CSS Variables (New Theme)

**Current (REMOVE all):**
```css
:root {
    --campfire-red: #B85042;
    --campfire-orange: #E09F3E;
    --campfire-yellow: #DDB892;
    --campfire-dark: #2C1810;
    --campfire-bg: #FFF5EB;
}
```

**New:**
```css
:root {
    /* Background colors */
    --bg-primary: #3D2B22;
    --bg-secondary: #4A3728;
    --bg-card: #5C4033;
    --bg-input: #F5E6D3;
    
    /* Text colors */
    --text-primary: #F5E6D3;
    --text-secondary: #C4A77D;
    --text-dark: #2C1810;
    
    /* Accent colors */
    --accent-orange: #E07B4C;
    --accent-coral: #D4654A;
    --accent-glow: rgba(224, 123, 76, 0.4);
    
    /* UI colors */
    --border-color: #6B5344;
    --border-glow: rgba(224, 123, 76, 0.6);
    
    /* Shadows */
    --card-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
    --glow-shadow: 0 0 20px var(--accent-glow);
}
```

### 2.2 Sections to Remove from styles.css

Remove these entire sections:
- Lines 9-12: `body` (will rewrite)
- Lines 14-16: `header.bg-primary` (Bootstrap override)
- Lines 18-44: `.uiverse-input, .uiverse-select` (will rewrite)
- Lines 46-50: `.loading` (will rewrite)
- Lines 52-56: `.recommendations-output` (will rewrite)
- Lines 58-70: `.preference-btn.active`, `.btn-group` (Bootstrap)
- Lines 71-102: `.custom-checkbox` (not used in new design)
- Lines 104-121: `.preference-container`, `.checkbox-wrapper`, `.checkbox-label`
- Lines 159-176: `header h1`, `header .subtitle` (old header)
- Lines 178-204: `.btn-primary`, `.btn-secondary`, `.nav-tabs` (Bootstrap overrides)
- Lines 206-213: `.card`, `.card-title` (Bootstrap cards)
- Lines 215-263: `.restaurant-input-group`, `.awesomplete` styles (will rewrite)
- Lines 265-273: Validation styles (will rewrite)
- Lines 275-333: `.filter-section`, `.type-filter-group` (will rewrite)

**Essentially: Delete entire styles.css and rewrite from scratch.**

### 2.3 New CSS Structure

```
styles.css (new structure):
├── CSS Variables (:root)
├── Reset & Base Styles
├── Layout
│   ├── .app-header
│   ├── .app-main
│   ├── .main-container
│   └── .two-column-layout
├── Header Components
│   ├── .logo
│   ├── .main-nav
│   ├── .nav-tab
│   └── .user-profile
├── Form Components
│   ├── .form-field
│   ├── .input-field
│   ├── .pill-select
│   ├── .toggle-switch
│   └── .cta-button
├── Recommendation Cards
│   ├── .recommendation-card
│   ├── .restaurant-name
│   └── .card-actions
├── Preferences Panel
├── History Panel (new)
├── Utilities & Animations
```

---

## Phase 3: JavaScript Updates

### 3.1 Remove Bootstrap Tab Dependency

**Current (REMOVE):**
```javascript
// No explicit JS, but relies on Bootstrap's data-toggle="tab"
```

**New Tab Switching Logic:**
```javascript
// Tab switching
document.querySelectorAll('.nav-tab').forEach(tab => {
    tab.addEventListener('click', () => {
        // Remove active from all tabs and panels
        document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
        
        // Activate clicked tab and corresponding panel
        tab.classList.add('active');
        const panelId = `${tab.dataset.tab}-panel`;
        document.getElementById(panelId).classList.add('active');
    });
});
```

### 3.2 Update Username Display in Header

**Add to script.js:**
```javascript
// Update header username display
function updateHeaderUsername(name) {
    const headerUserName = document.getElementById('header-user-name');
    if (headerUserName && name) {
        headerUserName.textContent = name;
    }
}

// Call when name is entered/loaded
nameInput.addEventListener('blur', () => {
    updateHeaderUsername(UsernameHandler.sanitize(nameInput.value));
});
```

### 3.3 Remove Dynamic Add/Remove Restaurant Inputs

**Current (REMOVE):**
```javascript
// Lines 137-223: updateRemoveButtons(), addRestaurantBtn listener, remove button listener
const MAX_RESTAURANTS = 5;
function updateRemoveButtons() { ... }
addRestaurantBtn.addEventListener('click', function() { ... });
restaurantInputsContainer.addEventListener('click', function(event) { ... });
```

**New:** Initialize autocomplete on all 6 static inputs:
```javascript
// Initialize autocomplete for all restaurant inputs
document.querySelectorAll('input[name="restaurant_name"]').forEach(input => {
    initializeAutocomplete(input);
});
```

### 3.4 Update Recommendation Card Rendering

**Current (REMOVE lines 286-293):**
```javascript
recommendationsOutput.innerHTML = data.recommendations.map(rec => `
    <div class="card mb-3">
        <div class="card-body">
            <h5 class="card-title text-primary">${rec.name}</h5>
            <p class="card-text">${rec.description}</p>
        </div>
    </div>
`).join('');
```

**New:**
```javascript
recommendationsOutput.innerHTML = data.recommendations.map(rec => `
    <div class="recommendation-card">
        <h3 class="restaurant-name">${rec.name}</h3>
        <p class="recommendation-reason">
            <span class="reason-label">Why it's recommended:</span> ${rec.description}
        </p>
        <div class="card-actions">
            <button class="action-btn like-btn" data-restaurant-name="${rec.name}" title="Like">
                <span class="icon">👍</span>
            </button>
            <button class="action-btn dislike-btn" data-restaurant-name="${rec.name}" title="Dislike">
                <span class="icon">👎</span>
            </button>
        </div>
    </div>
`).join('');

// Add event listeners for inline like/dislike
attachRecommendationCardListeners();
```

### 3.5 Add Inline Like/Dislike Functionality

**New function:**
```javascript
function attachRecommendationCardListeners() {
    document.querySelectorAll('.recommendation-card .action-btn').forEach(btn => {
        btn.addEventListener('click', async function() {
            const restaurantName = this.dataset.restaurantName;
            const isLike = this.classList.contains('like-btn');
            const preference = isLike ? 'like' : 'dislike';
            
            // Visual feedback
            this.classList.add('active');
            this.closest('.card-actions')
                .querySelectorAll('.action-btn')
                .forEach(b => { if (b !== this) b.classList.remove('active'); });
            
            // TODO: Save preference to backend
            // This requires knowing the restaurant_id, may need backend changes
        });
    });
}
```

### 3.6 Sync Username Across Tabs (Simplify)

**Current (REMOVE lines 113-131):** Complex syncing between two separate inputs.

**New:** Single source of truth - name input in form, displayed in header.

---

## Phase 4: New Features

### 4.1 Request History Tab (Backend Required)

**New endpoint needed:** `GET /get_request_history?user=<username>`

**Response format:**
```json
{
    "history": [
        {
            "id": 1,
            "timestamp": "2025-12-01T20:30:00Z",
            "city": "Chicago",
            "input_restaurants": ["Girl & The Goat", "Au Cheval"],
            "recommendations": [
                {"name": "Alinea", "description": "..."},
                {"name": "Lou Malnatis", "description": "..."}
            ]
        }
    ]
}
```

**Frontend:** Render history cards in `#history-panel`.

### 4.2 Neighborhood Dropdown Population

**Add city-to-neighborhoods mapping:**
```javascript
const NEIGHBORHOODS = {
    'Chicago': ['West Loop', 'Wicker Park', 'Lincoln Park', 'River North', 'Logan Square', 'Pilsen'],
    'New York': ['Manhattan', 'Brooklyn', 'Williamsburg', 'SoHo', 'East Village', 'Tribeca']
};

document.getElementById('city').addEventListener('change', function() {
    const neighborhoodSelect = document.getElementById('neighborhood');
    neighborhoodSelect.innerHTML = '<option value="">Neighborhood</option>';
    
    NEIGHBORHOODS[this.value].forEach(n => {
        neighborhoodSelect.innerHTML += `<option value="${n}">${n}</option>`;
    });
});
```

---

## Phase 5: External Dependencies

### 5.1 Remove Bootstrap (Optional - Gradual)

**Current dependencies in index.html:**
```html
<link href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/@popperjs/core@2.9.2/dist/umd/popper.min.js"></script>
<script src="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/js/bootstrap.min.js"></script>
```

**Action:** Keep for Phase 1, remove in later iteration once all Bootstrap classes are replaced.

### 5.2 Keep These Dependencies

```html
<!-- Keep: Icons -->
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">

<!-- Keep: Autocomplete -->
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/awesomplete/1.1.5/awesomplete.min.css" />
<script src="https://cdnjs.cloudflare.com/ajax/libs/awesomplete/1.1.5/awesomplete.min.js"></script>

<!-- Keep: jQuery (used extensively) -->
<script src="https://code.jquery.com/jquery-3.5.1.min.js"></script>
```

---

## Implementation Order

1. **Step 1:** Create new HTML structure in `index.html`
2. **Step 2:** Delete `styles.css` and create new theme
3. **Step 3:** Update `script.js` for new selectors and tab logic
4. **Step 4:** Test and iterate on styling
5. **Step 5:** Add Request History feature (backend + frontend)
6. **Step 6:** Remove Bootstrap dependency (cleanup)

---

## Files Modified

| File | Action |
|------|--------|
| `templates/index.html` | Major restructure |
| `static/styles.css` | Complete rewrite |
| `static/script.js` | Significant updates |
| `app.py` | Add `/get_request_history` endpoint (Phase 4) |

---

## Rollback Plan

Keep the original files backed up:
- `templates/index.html.bak`
- `static/styles.css.bak`
- `static/script.js.bak`

Or rely on git: `git checkout main -- templates/index.html static/styles.css static/script.js`
