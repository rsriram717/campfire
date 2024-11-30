// script.js
document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('restaurant-form');
    const loadingIndicator = document.getElementById('loading');
    const recommendationsOutput = document.getElementById('recommendations');

    form.addEventListener('submit', async function(event) {
        event.preventDefault(); // Prevent the default form submission

        // Show loading indicator
        loadingIndicator.style.display = 'block';

        // Gather form data
        const name = document.getElementById('name').value;
        const restaurants = [
            document.getElementById('restaurant1').value,
            document.getElementById('restaurant2').value,
            document.getElementById('restaurant3').value,
            document.getElementById('restaurant4').value,
            document.getElementById('restaurant5').value
        ].filter(Boolean); // Remove empty values
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
            // Hide loading indicator
            loadingIndicator.style.display = 'none';
        }
    });
});
