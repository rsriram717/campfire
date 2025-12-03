// script.js

// --- Constants & Config ---
const NEIGHBORHOODS = {
    'Chicago': ['West Loop', 'Wicker Park', 'Lincoln Park', 'River North', 'Logan Square', 'Pilsen', 'Gold Coast', 'Loop', 'Lakeview'],
    'New York': ['Manhattan', 'Brooklyn', 'Williamsburg', 'SoHo', 'East Village', 'Tribeca', 'West Village', 'Upper East Side']
};

const RESTAURANT_TYPES = ['Casual', 'Sit-Down', 'Bar', 'Fine Dining', 'Cafe'];

// --- Username Handling ---
const UsernameHandler = {
    LOCAL_STORAGE_KEY: 'campfire_username',

    sanitize: (name) => {
        if (!name) return '';
        return name.trim().replace(/\s+/g, ' ');
    },

    load: () => {
        return localStorage.getItem(UsernameHandler.LOCAL_STORAGE_KEY) || '';
    },

    save: (name) => {
        if (name) {
            localStorage.setItem(UsernameHandler.LOCAL_STORAGE_KEY, name);
            updateHeaderUsername(name);
        }
    }
};

function updateHeaderUsername(name) {
    const headerName = document.getElementById('header-user-name');
    if (headerName && name) {
        headerName.textContent = name;
    }
}

// --- Tab Switching Logic ---
function initTabs() {
    const tabs = document.querySelectorAll('.nav-tab');
    const panels = document.querySelectorAll('.tab-panel');

    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            // Deactivate all
            tabs.forEach(t => t.classList.remove('active'));
            panels.forEach(p => p.classList.remove('active'));

            // Activate clicked
            tab.classList.add('active');
            const targetPanelId = `${tab.dataset.tab}-panel`;
            document.getElementById(targetPanelId).classList.add('active');
        });
    });
}

// --- Autocomplete & Inputs ---
function initializeAutocomplete(inputElement) {
    const awesomplete = new Awesomplete(inputElement, {
        minChars: 2,
        autoFirst: true,
        maxItems: 5
    });

    inputElement.addEventListener('keyup', function() {
        const query = inputElement.value;
        const city = document.getElementById('city').value;
        if (query.length < 2) return;

        fetch(`/autocomplete?query=${encodeURIComponent(query)}&city=${encodeURIComponent(city)}`)
            .then(res => res.json())
            .then(data => {
                awesomplete.list = data.map(r => ({ 
                    label: `${r.name} (${r.address})`, 
                    value: r.place_id 
                }));
            })
            .catch(console.error);
    });

    inputElement.addEventListener('awesomplete-selectcomplete', function(event) {
        const { label, value } = event.text;
        const name = label.split(' (')[0];
        this.value = name;
        // Update hidden place_id input in same wrapper
        const wrapper = this.closest('.input-field-wrapper');
        wrapper.querySelector('input[name="place_id"]').value = value;
    });
}

// --- Dynamic Dropdowns ---
function initDropdowns() {
    const citySelect = document.getElementById('city');
    const neighborhoodSelect = document.getElementById('neighborhood');
    const typeSelect = document.getElementById('restaurant-type-dropdown');

    // Populate Restaurant Types
    typeSelect.innerHTML = '<option value="">Restaurant Type</option>';
    RESTAURANT_TYPES.forEach(type => {
        typeSelect.innerHTML += `<option value="${type.toLowerCase()}">${type}</option>`;
    });

    // Handle City Change
    citySelect.addEventListener('change', function() {
        const city = this.value;
        neighborhoodSelect.innerHTML = '<option value="">Neighborhood</option>';
        
        if (NEIGHBORHOODS[city]) {
            NEIGHBORHOODS[city].forEach(n => {
                neighborhoodSelect.innerHTML += `<option value="${n}">${n}</option>`;
            });
        }
    });

    // Trigger initial population
    citySelect.dispatchEvent(new Event('change'));
}

// --- Recommendations Logic ---
function renderRecommendations(recommendations) {
    const container = document.getElementById('recommendations-output');
    
    if (!recommendations || recommendations.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <p>No recommendations found. Try adjusting your inputs.</p>
            </div>`;
        return;
    }

    container.innerHTML = recommendations.map(rec => `
        <div class="recommendation-card">
            <h3 class="restaurant-name">${rec.name}</h3>
            <p class="recommendation-reason">
                <span class="reason-label">Why it's recommended:</span> ${rec.description}
            </p>
            <div class="card-actions">
                <button class="action-btn like-btn" data-restaurant="${rec.name}" title="Like">
                    <i class="bi bi-hand-thumbs-up"></i>
                </button>
                <button class="action-btn dislike-btn" data-restaurant="${rec.name}" title="Dislike">
                    <i class="bi bi-hand-thumbs-down"></i>
                </button>
            </div>
        </div>
    `).join('');

    // Attach listeners to new buttons
    attachCardListeners();
}

function attachCardListeners() {
    document.querySelectorAll('.recommendation-card .action-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            // toggle active state visually
            const isLike = this.classList.contains('like-btn');
            const parent = this.closest('.card-actions');
            
            parent.querySelectorAll('.action-btn').forEach(b => b.classList.remove('active'));
            this.classList.add('active');

            // Note: Actual persistence requires restaurant ID, which we might not have 
            // for AI-generated results immediately unless we match them to DB.
            // For now, just visual feedback.
        });
    });
}

// --- Form Submission ---
function initForm() {
    const form = document.getElementById('restaurant-form');
    const loading = document.getElementById('loading');
    const nameInput = document.getElementById('name');

    form.addEventListener('submit', function(e) {
        e.preventDefault();
        loading.style.display = 'flex';

        const name = UsernameHandler.sanitize(nameInput.value);
        UsernameHandler.save(name);

        // Collect inputs
        const placeIds = [];
        const inputRestaurants = [];
        
        document.querySelectorAll('.input-field-wrapper').forEach(wrapper => {
            const nameVal = wrapper.querySelector('input[name="restaurant_name"]').value;
            const idVal = wrapper.querySelector('input[name="place_id"]').value;
            
            if (idVal) placeIds.push(idVal);
            else if (nameVal) inputRestaurants.push(nameVal);
        });

        // Collect filters
        const city = document.getElementById('city').value;
        const neighborhood = document.getElementById('neighborhood').value;
        const types = [];
        
        // Dropdown type
        const dropType = document.getElementById('restaurant-type-dropdown').value;
        if (dropType) types.push(dropType);

        // Toggle types
        document.querySelectorAll('.toggle-input:checked').forEach(cb => {
            types.push(cb.value);
        });

        // API Call
        fetch('/get_recommendations', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user: name,
                city: city,
                neighborhood: neighborhood,
                place_ids: placeIds,
                input_restaurants: inputRestaurants,
                restaurant_types: [...new Set(types)] // dedupe
            })
        })
        .then(res => res.json())
        .then(data => {
            if (data.error) throw new Error(data.error);
            renderRecommendations(data.recommendations);
        })
        .catch(err => {
            console.error(err);
            document.getElementById('recommendations-output').innerHTML = `
                <div class="empty-state" style="border-color: #ff4444;">
                    <p>Error: ${err.message || 'Failed to get recommendations'}</p>
                </div>`;
        })
        .finally(() => {
            loading.style.display = 'none';
        });
    });
}

// --- Preferences Logic ---
function initPreferences() {
    const fetchBtn = document.getElementById('fetch-restaurants');
    const saveBtn = document.getElementById('save-preferences');
    const listContainer = document.getElementById('restaurant-list');
    const currentPreferences = new Map();

    fetchBtn.addEventListener('click', () => {
        const name = UsernameHandler.sanitize(document.getElementById('name').value);
        if (!name) {
            alert('Please enter your name in the main form first.');
            // Switch to main tab
            document.querySelector('[data-tab="recommendations"]').click();
            document.getElementById('name').focus();
            return;
        }

        fetch('/get_restaurants')
            .then(res => res.json())
            .then(data => {
                if (data.restaurants) {
                    renderPreferencesList(data.restaurants);
                    loadUserPreferences(name);
                    saveBtn.disabled = false;
                }
            });
    });

    function renderPreferencesList(restaurants) {
        listContainer.innerHTML = restaurants.map(r => `
            <div class="preference-card">
                <h5>${r.name}</h5>
                <div class="preference-toggle" data-id="${r.id}">
                    <button type="button" class="like" data-val="like">Like</button>
                    <button type="button" class="neutral active" data-val="neutral">Neutral</button>
                    <button type="button" class="dislike" data-val="dislike">Dislike</button>
                </div>
            </div>
        `).join('');

        // Attach toggle listeners
        document.querySelectorAll('.preference-toggle button').forEach(btn => {
            btn.addEventListener('click', function() {
                const parent = this.parentElement;
                parent.querySelectorAll('button').forEach(b => b.classList.remove('active'));
                this.classList.add('active');
            });
        });
    }

    function loadUserPreferences(name) {
        fetch(`/get_user_preferences?name=${encodeURIComponent(name)}`)
            .then(res => res.json())
            .then(data => {
                if (data.preferences) {
                    data.preferences.forEach(pref => {
                        const toggle = document.querySelector(`.preference-toggle[data-id="${pref.restaurant_id}"]`);
                        if (toggle) {
                            toggle.querySelectorAll('button').forEach(b => b.classList.remove('active'));
                            toggle.querySelector(`button[data-val="${pref.preference}"]`)?.classList.add('active');
                            currentPreferences.set(pref.restaurant_id, pref.preference);
                        }
                    });
                }
            });
    }

    saveBtn.addEventListener('click', () => {
        const name = UsernameHandler.sanitize(document.getElementById('name').value);
        const updates = [];

        document.querySelectorAll('.preference-toggle').forEach(toggle => {
            const id = parseInt(toggle.dataset.id);
            const active = toggle.querySelector('button.active').dataset.val;
            
            // Only send if changed from initial/neutral
            // (Simplification: just send all non-neutral or changed)
            if (active !== 'neutral' || currentPreferences.get(id) !== 'neutral') {
                 updates.push({ restaurant_id: id, preference: active });
            }
        });

        fetch('/save_preferences', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_name: name, preferences: updates })
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) alert('Preferences saved!');
        });
    });
}

// --- Initialization ---
document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    initDropdowns();
    initForm();
    initPreferences();

    // Init autocomplete for all inputs
    document.querySelectorAll('input[name="restaurant_name"]').forEach(initializeAutocomplete);

    // Restore username
    const savedName = UsernameHandler.load();
    if (savedName) {
        document.getElementById('name').value = savedName;
        updateHeaderUsername(savedName);
    }

    // Sync name input to header
    document.getElementById('name').addEventListener('input', (e) => {
        updateHeaderUsername(e.target.value || 'Guest');
    });
});
