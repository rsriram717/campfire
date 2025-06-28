// script.js
document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('restaurant-form');
    const loadingIndicator = document.getElementById('loading');
    const recommendationsOutput = document.getElementById('recommendations-output');
    const addRestaurantBtn = document.getElementById('add-restaurant-btn');
    const restaurantInputsContainer = document.getElementById('restaurant-inputs');

    let currentPreferences = new Map(); // Store current DB state of preferences

    // --- Autocomplete and Dynamic Inputs ---

    const MAX_RESTAURANTS = 5;

    function updateRemoveButtons() {
        const groups = restaurantInputsContainer.querySelectorAll('.restaurant-input-group');
        groups.forEach((group, index) => {
            const button = group.querySelector('.remove-restaurant-btn');
            if (button) {
                // Show button only if there is more than one input, or hide if it's the last one
                button.style.display = groups.length > 1 ? 'inline-block' : 'none';
            }
        });
    }

    function initializeAutocomplete(inputElement) {
        console.log("Initializing autocomplete for:", inputElement); // Diagnostic log
        const awesomplete = new Awesomplete(inputElement, {
            minChars: 2,
            autoFirst: true,
        });

        inputElement.addEventListener('keyup', function(event) {
            const query = inputElement.value;
            const city = document.getElementById('city').value;
            if (query.length < 2) return;

            fetch(`/autocomplete?query=${encodeURIComponent(query)}&city=${encodeURIComponent(city)}`)
                .then(response => {
                    if (!response.ok) {
                        // For 500 errors, etc., the response body might have our specific error message
                        return response.json().then(err => Promise.reject(err));
                    }
                    return response.json();
                })
                .then(data => {
                    awesomplete.list = data.map(r => ({ label: `${r.name} (${r.address})`, value: r.place_id }));
                })
                .catch(error => {
                    console.error('Autocomplete Error:', error.error || 'A network or server error occurred.');
                    awesomplete.list = []; // Clear suggestions on error
                });
        });

        inputElement.addEventListener('awesomplete-selectcomplete', function(event) {
            const { label, value } = event.text;
            const placeId = value;
            const name = label.split(' (')[0];

            this.value = name; // Set visible input to just the name
            this.closest('.restaurant-input-group').querySelector('input[name="place_id"]').value = placeId;
        });
    }

    function updateAddButtonState() {
        const count = restaurantInputsContainer.querySelectorAll('.restaurant-input-group').length;
        addRestaurantBtn.disabled = count >= MAX_RESTAURANTS;
    }

    addRestaurantBtn.addEventListener('click', function() {
        const count = restaurantInputsContainer.querySelectorAll('.restaurant-input-group').length;
        if (count >= MAX_RESTAURANTS) return;

        const newInputGroupHTML = `
            <div class="restaurant-input-group mt-2">
                <div class="awesomplete">
                    <input type="text" name="restaurant_name" placeholder="Start typing a restaurant name..." class="form-control">
                </div>
                <input type="hidden" name="place_id">
                <button type="button" class="btn btn-danger remove-restaurant-btn">
                    <i class="bi bi-x-circle"></i>
                </button>
            </div>`;
        restaurantInputsContainer.insertAdjacentHTML('beforeend', newInputGroupHTML);
        
        const newInputGroups = restaurantInputsContainer.querySelectorAll('.restaurant-input-group');
        const latestInputGroup = newInputGroups[newInputGroups.length - 1];
        const latestInput = latestInputGroup.querySelector('input[name="restaurant_name"]');
        initializeAutocomplete(latestInput);
        
        updateAddButtonState();
        updateRemoveButtons();
    });
    
    restaurantInputsContainer.addEventListener('click', function(event) {
        if (event.target.classList.contains('remove-restaurant-btn')) {
            event.target.closest('.restaurant-input-group').remove();
            updateAddButtonState();
            updateRemoveButtons();
        }
    });

    // Initialize for the first input, which is now pre-wrapped
    const firstInput = document.querySelector('#restaurant-inputs input[name="restaurant_name"]');
    if (firstInput) {
        initializeAutocomplete(firstInput);
    }
    
    updateAddButtonState();
    updateRemoveButtons(); // Call on load to set initial state

    // --- Form Submission ---

    form.addEventListener('submit', function(event) {
        event.preventDefault();
        loadingIndicator.style.display = 'block';

        const name = document.getElementById('name').value;
        const city = document.getElementById('city').value;
        
        // Collect place IDs and names from the restaurant inputs
        const restaurantInputs = document.querySelectorAll('.restaurant-input-group');
        const placeIds = [];
        const restaurantNames = [];
        restaurantInputs.forEach(group => {
            const placeId = group.querySelector('input[name="place_id"]').value;
            const restaurantName = group.querySelector('input[name="restaurant_name"]').value;
            if (placeId) {
                placeIds.push(placeId);
            } else if (restaurantName) {
                restaurantNames.push(restaurantName);
            }
        });

        // Collect selected restaurant types
        const restaurantTypes = [];
        document.querySelectorAll('input[type="checkbox"]:checked').forEach(checkbox => {
            restaurantTypes.push(checkbox.value);
        });

        const neighborhood = document.getElementById('neighborhood').value;

        // Make the API call to the backend
        fetch('/get_recommendations', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ 
                user: name,
                place_ids: placeIds, 
                input_restaurants: restaurantNames,
                city: city,
                neighborhood: neighborhood,
                restaurant_types: restaurantTypes
            }),
        })
        .then(response => response.json())
        .then(data => {
            if (data.recommendations) {
                recommendationsOutput.innerHTML = data.recommendations.map(rec => `
                    <div class="card mb-3">
                        <div class="card-body">
                            <h5 class="card-title text-primary">${rec.name}</h5>
                            <p class="card-text">${rec.description}</p>
                        </div>
                    </div>
                `).join('');
            } else {
                recommendationsOutput.innerHTML = `<p>No recommendations found.</p>`;
            }
        })
        .catch(error => {
            console.error('Error fetching recommendations:', error);
            recommendationsOutput.innerHTML = `<p>Error fetching recommendations. Please try again later.</p>`;
        })
        .finally(() => {
            loadingIndicator.style.display = 'none';
        });
    });

    // Restaurant Preferences Tab Functionality
    const fetchRestaurantsBtn = document.getElementById('fetch-restaurants');
    const savePreferencesBtn = document.getElementById('save-preferences');
    const restaurantList = document.getElementById('restaurant-list');
    const userNameInput = document.getElementById('user-name');

    if (fetchRestaurantsBtn) {
        // Initially hide the savePreferencesBtn
        savePreferencesBtn.style.display = 'none';

        // Add event listener to userNameInput to enable/disable fetchRestaurantsBtn
        userNameInput.addEventListener('input', function() {
            const userName = userNameInput.value.trim();
            if (userName) {
                fetchRestaurantsBtn.disabled = false;
                fetchRestaurantsBtn.classList.add('btn-primary');
                fetchRestaurantsBtn.classList.remove('btn-secondary');
            } else {
                fetchRestaurantsBtn.disabled = true;
                fetchRestaurantsBtn.classList.add('btn-secondary');
                fetchRestaurantsBtn.classList.remove('btn-primary');
            }
        });

        fetchRestaurantsBtn.addEventListener('click', function() {
            const userName = userNameInput.value.trim();
            if (!userName) {
                alert('Please enter your name');
                return;
            }

            // Fetch restaurants from the server
            fetch('/get_restaurants')
                .then(response => response.json())
                .then(data => {
                    if (data.restaurants) {
                        const restaurantsHTML = data.restaurants.map(restaurant => `
                            <div class="card mb-3">
                                <div class="card-body d-flex justify-content-between align-items-center">
                                    <h5 class="card-title mb-0">${restaurant.name}</h5>
                                    <div class="preference-toggle" data-restaurant-id="${restaurant.id}">
                                        <button type="button" class="like" data-preference="like">Like</button>
                                        <button type="button" class="neutral" data-preference="neutral">Neutral</button>
                                        <button type="button" class="dislike" data-preference="dislike">Dislike</button>
                                    </div>
                                </div>
                            </div>
                        `).join('');
                        
                        restaurantList.innerHTML = restaurantsHTML;
                        savePreferencesBtn.style.display = 'block';

                        // Add click handlers for preference toggles
                        document.querySelectorAll('.preference-toggle').forEach(toggle => {
                            toggle.querySelectorAll('button').forEach(button => {
                                button.addEventListener('click', function() {
                                    // Remove active class from all buttons in this toggle
                                    toggle.querySelectorAll('button').forEach(btn => 
                                        btn.classList.remove('active'));
                                    // Add active class to clicked button
                                    this.classList.add('active');
                                    
                                    // Check if any preferences have changed
                                    let hasChanges = false;
                                    document.querySelectorAll('.preference-toggle').forEach(t => {
                                        const restaurantId = t.dataset.restaurantId;
                                        const activeBtn = t.querySelector('button.active');
                                        const currentPreference = activeBtn ? activeBtn.dataset.preference : 'neutral';
                                        
                                        if (currentPreference !== currentPreferences.get(restaurantId)) {
                                            hasChanges = true;
                                        }
                                    });
                                    
                                    // Enable/disable save button based on changes
                                    if (hasChanges) {
                                        savePreferencesBtn.disabled = false;
                                        savePreferencesBtn.classList.add('btn-primary');
                                        savePreferencesBtn.classList.remove('btn-secondary');
                                    } else {
                                        savePreferencesBtn.disabled = true;
                                        savePreferencesBtn.classList.add('btn-secondary');
                                        savePreferencesBtn.classList.remove('btn-primary');
                                    }
                                });
                            });
                        });

                        // Load existing preferences
                        fetch(`/get_user_preferences?name=${encodeURIComponent(userName)}`)
                            .then(response => response.json())
                            .then(data => {
                                // First set all restaurants to neutral and store initial state
                                document.querySelectorAll('.preference-toggle').forEach(toggle => {
                                    const restaurantId = toggle.dataset.restaurantId;
                                    currentPreferences.set(restaurantId, 'neutral');
                                    
                                    const neutralButton = toggle.querySelector('button[data-preference="neutral"]');
                                    if (neutralButton) {
                                        neutralButton.classList.add('active');
                                    }
                                });

                                // Then apply stored preferences
                                if (data.preferences) {
                                    data.preferences.forEach(pref => {
                                        const toggle = document.querySelector(
                                            `.preference-toggle[data-restaurant-id="${pref.restaurant_id}"]`
                                        );
                                        if (toggle) {
                                            // Store the current preference
                                            currentPreferences.set(pref.restaurant_id.toString(), pref.preference);
                                            
                                            // Remove neutral state first
                                            toggle.querySelector('button[data-preference="neutral"]')?.classList.remove('active');
                                            // Set stored preference
                                            const button = toggle.querySelector(
                                                `button[data-preference="${pref.preference}"]`
                                            );
                                            if (button) {
                                                button.classList.add('active');
                                            }
                                        }
                                    });
                                }
                                
                                // Initially disable save button
                                savePreferencesBtn.disabled = true;
                                savePreferencesBtn.classList.add('btn-secondary');
                                savePreferencesBtn.classList.remove('btn-primary');
                            });
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    restaurantList.innerHTML = '<p class="text-danger">Error loading restaurants</p>';
                });
        });
    }

    if (savePreferencesBtn) {
        savePreferencesBtn.addEventListener('click', function() {
            const userName = userNameInput.value.trim();
            if (!userName) {
                alert('Please enter your name');
                return;
            }

            // Collect all preferences that have changed from their current state
            const preferences = [];
            document.querySelectorAll('.preference-toggle').forEach(toggle => {
                const restaurantId = toggle.dataset.restaurantId;
                const activeButton = toggle.querySelector('button.active');
                const newPreference = activeButton ? activeButton.dataset.preference : 'neutral';
                const currentPreference = currentPreferences.get(restaurantId);

                // Only include if the preference has changed
                if (newPreference !== currentPreference) {
                    preferences.push({
                        restaurant_id: parseInt(restaurantId),
                        preference: newPreference
                    });
                }
            });

            console.log('Saving preferences:', preferences);

            // Save to server
            fetch('/save_preferences', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    user_name: userName,
                    preferences: preferences
                })
            })
            .then(response => response.json())
            .then(data => {
                console.log('Server response:', data);
                if (data.success) {
                    // Update currentPreferences with new values
                    document.querySelectorAll('.preference-toggle').forEach(toggle => {
                        const restaurantId = toggle.dataset.restaurantId;
                        const activeBtn = toggle.querySelector('button.active');
                        const preference = activeBtn ? activeBtn.dataset.preference : 'neutral';
                        currentPreferences.set(restaurantId, preference);
                    });
                    
                    // Disable save button after successful save
                    savePreferencesBtn.disabled = true;
                    savePreferencesBtn.classList.add('btn-secondary');
                    savePreferencesBtn.classList.remove('btn-primary');
                    
                    alert('Preferences saved successfully!');
                } else {
                    alert('Error: ' + (data.error || 'Failed to save preferences'));
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Error saving preferences');
            });
        });
    }
});
