// script.js
document.getElementById('restaurant-form').addEventListener('submit', function(e) {
    e.preventDefault();
    const name = document.getElementById('name').value.trim();
    const restaurants = document.getElementById('restaurants').value.split(',').map(restaurant => restaurant.trim());
    const city = document.getElementById('city').value.trim();

    // Send the input data to the Flask API
    fetch('/get_recommendations', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            user: name,
            email: "test@test.com",
            favorite_restaurants: restaurants,
            city: city
        }),
    })
    .then(response => response.json())
    .then(data => {
        const recommendationsDiv = document.getElementById('recommendations');
        recommendationsDiv.innerHTML = ''; // Clear previous recommendations

        if (data.recommendations && data.recommendations.length > 0) {
            const ul = document.createElement('ul'); // Create a list to hold recommendations
            data.recommendations.forEach(rec => {
                const li = document.createElement('li');
                const restaurantName = rec.name.replace(/\*/g, '').trim(); // Remove asterisks
                li.innerHTML = `<span class="restaurant-name" style="font-weight: bold;">${restaurantName}</span>: <span class="restaurant-description">${rec.description}</span>`;
                ul.appendChild(li);
            });
            recommendationsDiv.appendChild(ul); // Append the list to the recommendations div
        } else {
            recommendationsDiv.innerHTML = 'No recommendations found.';
        }
    })
    .catch(error => {
        console.error('Error:', error);
    });
});

