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
            favorite_restaurants: restaurants,
            city: city
        }),
    })
    .then(response => response.json())
    .then(data => {
        const recommendationsDiv = document.getElementById('recommendations');
        recommendationsDiv.innerHTML = ''; // Clear previous recommendations

        if (data.recommendations && data.recommendations.length > 0) {
            data.recommendations.forEach(rec => {
                const p = document.createElement('p'); // Create a paragraph for each recommendation
                p.innerHTML = `<strong>${rec.name}</strong>: ${rec.description}`;
                recommendationsDiv.appendChild(p); // Add each recommendation to the div
            });
        } else {
            recommendationsDiv.innerHTML = '<p>No recommendations found.</p>';
        }
    })
    .catch(error => {
        console.error('Error:', error);
        document.getElementById('recommendations').innerHTML = '<p>Failed to load recommendations. Please try again.</p>';
    });
});