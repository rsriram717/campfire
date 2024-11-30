// script.js
document.getElementById('restaurant-form').addEventListener('submit', function(e) {
    e.preventDefault();

    const name = document.getElementById('name').value.trim();
    console.log("User name:", name);  // Debugging
    
    const restaurants = document.getElementById('restaurants').value.split(',').map(restaurant => {
        return restaurant.replace(/^\d+\s*/, '').trim();
    });
    console.log("Input restaurants:", restaurants);  // Debugging

    const city = document.getElementById('city').value.trim();
    console.log("City:", city);  // Debugging

    // Show the loading spinner
    document.getElementById('loading').style.display = 'block';

    // Clear previous recommendations
    const recommendationsDiv = document.getElementById('recommendations');
    recommendationsDiv.innerHTML = '';

    // Send the input data to the Flask API
    fetch('/get_recommendations', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            user: name,
            input_restaurants: restaurants,
            city: city
        }),
    })
    .then(response => {
        console.log("Response status:", response.status);  // Debugging
        return response.json();
    })
    .then(data => {
        console.log('Response from backend:', data); // Debugging

        // Hide the loading spinner
        document.getElementById('loading').style.display = 'none';

        if (data.recommendations && data.recommendations.length > 0) {
            data.recommendations.forEach(rec => {
                const p = document.createElement('p');
                const restaurantName = rec.name.replace(/\*/g, '').trim();
                p.innerHTML = `<strong>${restaurantName}</strong>: ${rec.description}`;
                recommendationsDiv.appendChild(p);
            });
        } else {
            recommendationsDiv.innerHTML = '<p>No recommendations found.</p>';
        }
    })
    .catch(error => {
        console.error('Error:', error);
        document.getElementById('recommendations').innerHTML = '<p>Failed to load recommendations. Please try again.</p>';
        // Hide the loading spinner
        document.getElementById('loading').style.display = 'none';
    });
});
