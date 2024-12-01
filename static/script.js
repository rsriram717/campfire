// script.js
document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('restaurant-form');
    const loadingIndicator = document.getElementById('loading');
    const recommendationsOutput = document.getElementById('recommendations-output');

    let currentPreferences = new Map(); // Store current DB state of preferences

    form.addEventListener('submit', function(event) {
        event.preventDefault();

        loadingIndicator.style.display = 'block';

        const name = document.getElementById('name').value;
        const restaurants = [
            document.getElementById('restaurant1').value,
            document.getElementById('restaurant2').value,
            document.getElementById('restaurant3').value,
            document.getElementById('restaurant4').value,
            document.getElementById('restaurant5').value
        ].filter(Boolean);
        const city = document.getElementById('city').value;

        fetch('/get_recommendations', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                user: name,
                input_restaurants: restaurants,
                city: city,
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
