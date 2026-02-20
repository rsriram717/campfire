// script.js

// --- Constants & Config ---
const NEIGHBORHOODS = {
    'Chicago': ['West Loop', 'Wicker Park', 'Lincoln Park', 'River North', 'Logan Square', 'Pilsen', 'Gold Coast', 'Loop', 'Lakeview'],
    'New York': ['Manhattan', 'Brooklyn', 'Williamsburg', 'SoHo', 'East Village', 'Tribeca', 'West Village', 'Upper East Side']
};

const RESTAURANT_TYPES = ['Casual', 'Fine Dining', 'Bar'];

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

// --- Utils ---
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func.apply(this, args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

function generateSessionToken() {
    if (typeof crypto !== 'undefined' && crypto.randomUUID) {
        return crypto.randomUUID();
    }
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
        var r = Math.random() * 16 | 0, v = c == 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
}

// Global session token
let currentSessionToken = generateSessionToken();

// --- Autocomplete & Inputs ---
function initializeAutocomplete(inputElement) {
    const awesomplete = new Awesomplete(inputElement, {
        minChars: 2,
        autoFirst: true,
        maxItems: 5,
        // Trust the API results (Google is smarter than simple string matching)
        filter: function() { return true; },
        // Preserve Google's ranking order
        sort: false
    });

    const debouncedFetch = debounce(function() {
        const query = inputElement.value;
        const city = document.getElementById('city').value;
        if (query.length < 2) return;

        fetch(`/autocomplete?query=${encodeURIComponent(query)}&city=${encodeURIComponent(city)}&session_token=${encodeURIComponent(currentSessionToken)}`)
            .then(res => res.json())
            .then(data => {
                awesomplete.list = data.map(r => ({ 
                    label: `${r.name} (${r.address})`, 
                    value: r.place_id 
                }));
            })
            .catch(console.error);
    }, 300);

    inputElement.addEventListener('keyup', debouncedFetch);

    inputElement.addEventListener('awesomplete-selectcomplete', function(event) {
        const { label, value } = event.text;
        const name = label.split(' (')[0];
        this.value = name;
        // Update hidden place_id input in same wrapper
        const wrapper = this.closest('.input-field-wrapper');
        wrapper.querySelector('input[name="place_id"]').value = value;
        
        // Regenerate token after selection (start new session)
        currentSessionToken = generateSessionToken();
    });
}

// --- Dynamic Dropdowns & Toggles ---
function initDropdowns() {
    const citySelect = document.getElementById('city');
    const neighborhoodSelect = document.getElementById('neighborhood');
    const typeContainer = document.getElementById('type-toggles');

    // Populate Restaurant Types Toggles
    typeContainer.innerHTML = '';
    RESTAURANT_TYPES.forEach(type => {
        const value = type.toLowerCase();
        typeContainer.innerHTML += `
            <label class="toggle-option">
                <input type="checkbox" value="${value}" class="toggle-input">
                <span class="toggle-dot"></span>
                <span class="toggle-label">${type}</span>
            </label>
        `;
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
            ${rec.address ? `<p class="restaurant-address"><i class="bi bi-geo-alt"></i> ${rec.address}</p>` : ''}
            ${rec.reason ? `<p class="recommendation-context"><i class="bi bi-lightbulb-fill"></i> ${rec.reason}</p>` : ''}
            <p class="recommendation-reason">
                <span class="reason-label">Why:</span> ${rec.description}
            </p>
            <div class="card-actions">
                <button type="button" class="action-btn like-btn" data-id="${rec.id}" title="Like">
                    <i class="bi bi-hand-thumbs-up"></i>
                </button>
                <button type="button" class="action-btn dislike-btn" data-id="${rec.id}" title="Dislike">
                    <i class="bi bi-hand-thumbs-down"></i>
                </button>
            </div>
        </div>
    `).join('');

    // Attach listeners to new buttons
    attachCardListeners();

    // Mobile UX: Scroll to results
    if (window.innerWidth <= 768) {
        container.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
}

function attachCardListeners() {
    document.querySelectorAll('.recommendation-card .action-btn').forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.preventDefault(); // Prevent any form submission
            
            // toggle active state visually
            const isLike = this.classList.contains('like-btn');
            const parent = this.closest('.card-actions');
            const restaurantId = this.dataset.id;
            const preference = isLike ? 'like' : 'dislike';
            
            // If already active, maybe toggle off? For now just standard toggle behavior
            // If clicking same button, do nothing? Or untoggle? 
            // Let's assume untoggling isn't primary flow yet, just standard selection.
            
            parent.querySelectorAll('.action-btn').forEach(b => b.classList.remove('active'));
            this.classList.add('active');

            // Persist immediately
            const userName = document.getElementById('name').value;
            if (userName && restaurantId) {
                saveSinglePreference(userName, parseInt(restaurantId), preference);
            }
        });
    });
}

function saveSinglePreference(userName, restaurantId, preference) {
    fetch('/save_preferences', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            user_name: userName,
            preferences: [{ restaurant_id: restaurantId, preference: preference }]
        })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            console.log(`Saved preference: ${preference} for ID ${restaurantId}`);
        }
    })
    .catch(console.error);
}

// --- Form Submission ---
function initForm() {
    const form = document.getElementById('restaurant-form');
    const loading = document.getElementById('loading');
    const nameInput = document.getElementById('name');

    // Update slider label on change
    const slider = document.getElementById('input-weight-slider');
    const sliderLabel = document.getElementById('input-weight-label');
    if (slider && sliderLabel) {
        const updateSliderLabel = () => {
            const val = parseInt(slider.value);
            if (val === 50) {
                sliderLabel.textContent = 'Balanced (50%)';
            } else if (val < 50) {
                sliderLabel.textContent = `History (${100 - val}%)`;
            } else {
                sliderLabel.textContent = `This Session (${val}%)`;
            }
        };
        slider.addEventListener('input', updateSliderLabel);
        updateSliderLabel();
    }

    // Update revisit weight slider label on change
    const revisitSlider = document.getElementById('revisit-weight-slider');
    const revisitLabel = document.getElementById('revisit-weight-label');
    if (revisitSlider && revisitLabel) {
        const updateRevisitLabel = () => {
            const val = parseInt(revisitSlider.value);
            if (val === 0) {
                revisitLabel.textContent = 'All New';
            } else if (val === 100) {
                revisitLabel.textContent = 'Revisit Picks';
            } else {
                revisitLabel.textContent = `Mixed (${val}% revisit)`;
            }
        };
        revisitSlider.addEventListener('input', updateRevisitLabel);
        updateRevisitLabel();
    }

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

        // Toggle types
        document.querySelectorAll('.toggle-input:checked').forEach(cb => {
            types.push(cb.value);
        });

        // Read input weight slider (0-100 → 0.0-1.0)
        const inputWeightSlider = document.getElementById('input-weight-slider');
        const inputWeight = inputWeightSlider ? parseInt(inputWeightSlider.value) / 100 : 0.7;

        // Read revisit weight slider (0-100 → 0.0-1.0)
        const revisitWeightSlider = document.getElementById('revisit-weight-slider');
        const revisitWeight = revisitWeightSlider ? parseInt(revisitWeightSlider.value) / 100 : 0.0;

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
                restaurant_types: [...new Set(types)], // dedupe
                input_weight: inputWeight,
                revisit_weight: revisitWeight
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

// --- Feedback Logic ---
function initFeedback() {
    const submitBtn = document.getElementById('submit-feedback-btn');
    const contentInput = document.getElementById('feedback-content');
    const listContainer = document.getElementById('feedback-list');

    // Expose load function
    window.loadFeedback = function() {
        const name = UsernameHandler.sanitize(document.getElementById('name').value);
        
        // Even if no name, we can show feedback, but voting/submitting requires name
        let url = '/get_feedback';
        if (name) url += `?user_name=${encodeURIComponent(name)}`;

        listContainer.innerHTML = `
            <div class="empty-state">
                <div class="spinner"></div>
                <p>Loading community ideas...</p>
            </div>`;

        fetch(url)
            .then(res => res.json())
            .then(data => {
                if (data.error) {
                    listContainer.innerHTML = `<div class="empty-state"><p>${data.error}</p></div>`;
                    return;
                }
                renderFeedbackList(data.suggestions);
            })
            .catch(err => {
                console.error(err);
                listContainer.innerHTML = `<div class="empty-state"><p>Error loading suggestions.</p></div>`;
            });
    };

    function renderFeedbackList(suggestions) {
        if (!suggestions || suggestions.length === 0) {
            listContainer.innerHTML = `
                <div class="empty-state">
                    <p>No suggestions yet. Be the first!</p>
                </div>`;
            return;
        }

        listContainer.innerHTML = suggestions.map(s => `
            <div class="recommendation-card feedback-card">
                <div class="vote-controls">
                    <button class="vote-btn upvote ${s.user_vote === 1 ? 'active' : ''}" data-id="${s.id}" data-type="1">
                        <i class="bi bi-caret-up-fill"></i>
                    </button>
                    <span class="vote-score">${s.score}</span>
                    <button class="vote-btn downvote ${s.user_vote === -1 ? 'active' : ''}" data-id="${s.id}" data-type="-1">
                        <i class="bi bi-caret-down-fill"></i>
                    </button>
                </div>
                <div class="feedback-content">
                    <p>${s.content}</p>
                </div>
            </div>
        `).join('');

        // Attach vote listeners
        document.querySelectorAll('.vote-btn').forEach(btn => {
            btn.addEventListener('click', handleVote);
        });
    }

    function handleVote() {
        const name = UsernameHandler.sanitize(document.getElementById('name').value);
        if (!name) {
            alert('Please enter your name in the main form to vote.');
            return;
        }

        const btn = this;
        const id = btn.dataset.id;
        const type = parseInt(btn.dataset.type);
        
        // Optimistic UI update could go here, but we'll wait for server for accuracy
        // Actually, let's do optimistic to feel fast
        const parent = btn.parentElement;
        const scoreSpan = parent.querySelector('.vote-score');
        let currentScore = parseInt(scoreSpan.textContent);
        
        // Logic matches backend: Toggle or Switch
        // But simpler to just reload or wait for response. Let's wait for response.
        
        fetch('/vote_feedback', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_name: name,
                suggestion_id: id,
                vote_type: type
            })
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                // Update score
                scoreSpan.textContent = data.new_score;
                
                // Update active classes
                const upBtn = parent.querySelector('.upvote');
                const downBtn = parent.querySelector('.downvote');
                
                // Reset both
                upBtn.classList.remove('active');
                downBtn.classList.remove('active');
                
                // Determine new state based on what we clicked and what backend likely did
                // Actually, checking 'active' state before click is hard if we don't track it.
                // Let's just reload the list to be 100% sure of state, 
                // OR return the new vote status from backend.
                // Backend returns {success, new_score}. It doesn't return new_vote_status.
                // Let's reload the list quietly? No that flickers.
                
                // Better: Logic on client.
                // If I clicked Up and it WASN'T active -> Now Active.
                // If I clicked Up and it WAS active -> Now Inactive.
                // But wait, what if I clicked Up and Down was active?
                // I'll just reload the list for correctness. It's fast enough locally.
                window.loadFeedback(); 
            } else {
                alert(data.error);
            }
        });
    }

    submitBtn.addEventListener('click', () => {
        const name = UsernameHandler.sanitize(document.getElementById('name').value);
        const content = contentInput.value.trim();

        if (!name) {
            alert('Please enter your name in the main form first.');
            return;
        }
        if (!content) return;

        submitBtn.disabled = true;
        submitBtn.textContent = 'Submitting...';

        fetch('/submit_feedback', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_name: name, content: content })
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                contentInput.value = '';
                window.loadFeedback();
            } else {
                alert(data.error);
            }
        })
        .finally(() => {
            submitBtn.disabled = false;
            submitBtn.textContent = 'Submit Idea';
        });
    });
}

// --- Feedback Logic ---
function initFeedback() {
    const submitBtn = document.getElementById('submit-feedback-btn');
    const contentInput = document.getElementById('feedback-content');
    const listContainer = document.getElementById('feedback-list');

    // Expose load function
    window.loadFeedback = function() {
        const name = UsernameHandler.sanitize(document.getElementById('name').value);
        
        // Even if no name, we can show feedback, but voting/submitting requires name
        let url = '/get_feedback';
        if (name) url += `?user_name=${encodeURIComponent(name)}`;

        listContainer.innerHTML = `
            <div class="empty-state">
                <div class="spinner"></div>
                <p>Loading community ideas...</p>
            </div>`;

        fetch(url)
            .then(res => res.json())
            .then(data => {
                if (data.error) {
                    listContainer.innerHTML = `<div class="empty-state"><p>${data.error}</p></div>`;
                    return;
                }
                renderFeedbackList(data.suggestions);
            })
            .catch(err => {
                console.error(err);
                listContainer.innerHTML = `<div class="empty-state"><p>Error loading suggestions.</p></div>`;
            });
    };

    function renderFeedbackList(suggestions) {
        if (!suggestions || suggestions.length === 0) {
            listContainer.innerHTML = `
                <div class="empty-state">
                    <p>No suggestions yet. Be the first!</p>
                </div>`;
            return;
        }

        listContainer.innerHTML = suggestions.map(s => `
            <div class="recommendation-card feedback-card">
                <div class="vote-controls">
                    <button type="button" class="vote-btn upvote ${s.user_vote === 1 ? 'active' : ''}" data-id="${s.id}" data-type="1">
                        <i class="bi bi-caret-up-fill"></i>
                    </button>
                    <span class="vote-score">${s.score}</span>
                    <button type="button" class="vote-btn downvote ${s.user_vote === -1 ? 'active' : ''}" data-id="${s.id}" data-type="-1">
                        <i class="bi bi-caret-down-fill"></i>
                    </button>
                </div>
                <div class="feedback-content">
                    <p>${s.content}</p>
                </div>
            </div>
        `).join('');

        // Attach vote listeners
        document.querySelectorAll('.vote-btn').forEach(btn => {
            btn.addEventListener('click', handleVote);
        });
    }

    function handleVote() {
        const name = UsernameHandler.sanitize(document.getElementById('name').value);
        if (!name) {
            alert('Please enter your name in the main form to vote.');
            return;
        }

        const btn = this;
        const id = btn.dataset.id;
        const type = parseInt(btn.dataset.type);
        
        fetch('/vote_feedback', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_name: name,
                suggestion_id: id,
                vote_type: type
            })
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                window.loadFeedback(); 
            } else {
                alert(data.error);
            }
        });
    }

    submitBtn.addEventListener('click', () => {
        const name = UsernameHandler.sanitize(document.getElementById('name').value);
        const content = contentInput.value.trim();

        if (!name) {
            alert('Please enter your name in the main form first.');
            return;
        }
        if (!content) return;

        submitBtn.disabled = true;
        submitBtn.textContent = 'Submitting...';

        fetch('/submit_feedback', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_name: name, content: content })
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                contentInput.value = '';
                window.loadFeedback();
            } else {
                alert(data.error);
            }
        })
        .finally(() => {
            submitBtn.disabled = false;
            submitBtn.textContent = 'Submit Idea';
        });
    });
}

// --- Preferences Logic ---
function initPreferences() {
    const listContainer = document.getElementById('restaurant-list');
    const prefNameSpan = document.getElementById('pref-user-name');

    // Expose load function globally or attach to tab
    window.loadPreferences = function() {
        const name = UsernameHandler.sanitize(document.getElementById('name').value);
        if (!name) {
            listContainer.innerHTML = `
                <div class="empty-state">
                    <p>Please enter your name in the main form first.</p>
                </div>`;
            prefNameSpan.textContent = "Guest";
            return;
        }

        prefNameSpan.textContent = name;
        listContainer.innerHTML = `
            <div class="empty-state">
                <div class="spinner"></div>
                <p>Loading your taste profile...</p>
            </div>`;

        fetch(`/get_user_preferences?name=${encodeURIComponent(name)}`)
            .then(res => res.json())
            .then(data => {
                if (data.error) {
                    listContainer.innerHTML = `<div class="empty-state"><p>${data.error}</p></div>`;
                    return;
                }
                
                if (data.restaurants && data.restaurants.length > 0) {
                    renderPreferencesList(data.restaurants, name);
                } else {
                     listContainer.innerHTML = `
                        <div class="empty-state">
                            <p>No dining history found yet.</p>
                            <p>Get some recommendations to start building your profile!</p>
                        </div>`;
                }
            })
            .catch(err => {
                console.error(err);
                listContainer.innerHTML = `<div class="empty-state"><p>Error loading preferences.</p></div>`;
            });
    };

    function renderPreferencesList(restaurants, userName) {
        listContainer.innerHTML = restaurants.map(r => `
            <div class="preference-card">
                <h5>${r.name}</h5>
                <div class="preference-toggle" data-id="${r.id}">
                    <button type="button" class="like ${r.preference === 'like' ? 'active' : ''}" data-val="like">Like</button>
                    <button type="button" class="neutral ${r.preference === 'neutral' ? 'active' : ''}" data-val="neutral">Neutral</button>
                    <button type="button" class="dislike ${r.preference === 'dislike' ? 'active' : ''}" data-val="dislike">Dislike</button>
                </div>
            </div>
        `).join('');

        // Attach toggle listeners with Auto-Save
        document.querySelectorAll('.preference-toggle button').forEach(btn => {
            btn.addEventListener('click', function() {
                const parent = this.parentElement;
                
                // Visual Update
                parent.querySelectorAll('button').forEach(b => b.classList.remove('active'));
                this.classList.add('active');
                
                // Auto-Save
                const id = parseInt(parent.dataset.id);
                const val = this.dataset.val;
                
                if (userName && id) {
                    saveSinglePreference(userName, id, val);
                }
            });
        });
    }
}

// --- Mobile Menu Logic ---
function initMobileMenu() {
    const menuBtn = document.querySelector('.mobile-menu-btn');
    const nav = document.querySelector('.main-nav');
    const tabs = document.querySelectorAll('.nav-tab');

    if (!menuBtn || !nav) return;

    menuBtn.addEventListener('click', () => {
        nav.classList.toggle('show');
        // Toggle icon between list and x-lg
        const icon = menuBtn.querySelector('i');
        if (nav.classList.contains('show')) {
            icon.classList.replace('bi-list', 'bi-x-lg');
        } else {
            icon.classList.replace('bi-x-lg', 'bi-list');
        }
    });

    // Close menu when a tab is clicked
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            if (window.innerWidth <= 768) {
                nav.classList.remove('show');
                menuBtn.querySelector('i').classList.replace('bi-x-lg', 'bi-list');
            }
        });
    });
}

// --- Initialization ---
document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    initMobileMenu();
    initDropdowns();
    initForm();
    initPreferences();
    initFeedback();

    // Hook into tab switching
    document.querySelector('.nav-tab[data-tab="preferences"]').addEventListener('click', () => {
        if (window.loadPreferences) window.loadPreferences();
    });
    document.querySelector('.nav-tab[data-tab="feedback"]').addEventListener('click', () => {
        if (window.loadFeedback) window.loadFeedback();
    });

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
