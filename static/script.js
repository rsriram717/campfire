// script.js
document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('restaurant-form');
    const loadingIndicator = document.getElementById('loading');
    const recommendationsOutput = document.getElementById('recommendations');
    const restaurantList = document.getElementById('restaurant-list');
    const userNameInput = document.getElementById('user-name');
    const fetchRestaurantsButton = document.getElementById('fetch-restaurants');
    const savePreferencesButton = document.getElementById('save-preferences');

    let initialCheckboxState = {};

    form.addEventListener('submit', async function(event) {
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

        try {
            const response = await fetch('/get_recommendations', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    user: name,
                    input_restaurants: restaurants,
                    city: city,
                }),
            });

            const data = await response.json();
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
        } catch (error) {
            console.error('Error fetching recommendations:', error);
            recommendationsOutput.innerHTML = `<p>Error fetching recommendations. Please try again later.</p>`;
        } finally {
            loadingIndicator.style.display = 'none';
        }
    });

    fetchRestaurantsButton.addEventListener('click', async function() {
        const userName = userNameInput.value.trim();
        if (userName) {
            try {
                const userResponse = await fetch(`/check_user?name=${encodeURIComponent(userName)}`);
                const userData = await userResponse.json();

                if (userData.exists) {
                    const [restaurantsResponse, preferencesResponse] = await Promise.all([
                        fetch('/get_restaurants', {
                            method: 'GET',
                            headers: {
                                'Content-Type': 'application/json',
                            },
                        }),
                        fetch(`/get_user_preferences?name=${encodeURIComponent(userName)}`, {
                            method: 'GET',
                            headers: {
                                'Content-Type': 'application/json',
                            },
                        })
                    ]);

                    const restaurantsData = await restaurantsResponse.json();
                    const preferencesData = await preferencesResponse.json();

                    if (restaurantsData.restaurants) {
                        const preferences = preferencesData.preferences || [];
                        restaurantList.innerHTML = restaurantsData.restaurants.map(restaurant => {
                            const userPref = preferences.find(p => p.restaurant_id === restaurant.id);
                            const likeChecked = userPref && userPref.preference === 'like' ? 'checked' : '';
                            const dislikeChecked = userPref && userPref.preference === 'dislike' ? 'checked' : '';

                            return `
                                <div class="d-flex justify-content-between align-items-center mb-2">
                                    <span>${restaurant.name}</span>
                                    <div>
                                        <input class="form-check-input" type="checkbox" value="like" id="like-${restaurant.id}" ${likeChecked}>
                                        <label class="form-check-label mr-5" for="like-${restaurant.id}">
                                            Like
                                        </label>
                                        <input class="form-check-input" type="checkbox" value="dislike" id="dislike-${restaurant.id}" ${dislikeChecked}>
                                        <label class="form-check-label" for="dislike-${restaurant.id}">
                                            Dislike
                                        </label>
                                    </div>
                                </div>
                            `;
                        }).join('');

                        initialCheckboxState = {};
                        document.querySelectorAll('.form-check-input').forEach(checkbox => {
                            initialCheckboxState[checkbox.id] = checkbox.checked;
                            checkbox.addEventListener('change', () => {
                                const hasChanges = Array.from(document.querySelectorAll('.form-check-input')).some(cb => initialCheckboxState[cb.id] !== cb.checked);
                                savePreferencesButton.disabled = !hasChanges;
                                savePreferencesButton.classList.toggle('btn-primary', hasChanges);
                                savePreferencesButton.classList.toggle('btn-secondary', !hasChanges);

                                if (checkbox.value === 'like' && checkbox.checked) {
                                    document.getElementById(`dislike-${checkbox.id.split('-')[1]}`).checked = false;
                                } else if (checkbox.value === 'dislike' && checkbox.checked) {
                                    document.getElementById(`like-${checkbox.id.split('-')[1]}`).checked = false;
                                }
                            });
                        });
                    } else {
                        restaurantList.innerHTML = `<p>No restaurants found.</p>`;
                    }
                } else {
                    restaurantList.innerHTML = `<p>No such user.</p>`;
                }
            } catch (error) {
                console.error('Error fetching restaurants or preferences:', error);
                restaurantList.innerHTML = `<p>Error fetching data. Please try again later.</p>`;
            }
        } else {
            restaurantList.innerHTML = `<p>Please enter your full name.</p>`;
        }
    });

    savePreferencesButton.addEventListener('click', async function() {
        const userName = userNameInput.value.trim();
        const preferences = [];

        document.querySelectorAll('.form-check-input').forEach(checkbox => {
            const restaurantId = checkbox.id.split('-')[1];
            if (checkbox.checked) {
                const preferenceType = checkbox.value;
                preferences.push({ restaurant_id: restaurantId, preference: preferenceType });
            } else {
                const existingPref = preferences.find(p => p.restaurant_id === restaurantId);
                if (!existingPref) {
                    preferences.push({ restaurant_id: restaurantId, preference: 'neutral' });
                }
            }
        });

        try {
            const response = await fetch('/save_preferences', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    user_name: userName,
                    preferences: preferences,
                }),
            });

            const data = await response.json();
            if (data.success) {
                alert('Preferences saved successfully!');
                savePreferencesButton.disabled = true;
                savePreferencesButton.classList.remove('btn-primary');
                savePreferencesButton.classList.add('btn-secondary');
            } else {
                alert('Error saving preferences.');
            }
        } catch (error) {
            console.error('Error saving preferences:', error);
            alert('Error saving preferences. Please try again later.');
        }
    });
});
