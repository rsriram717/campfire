from flask import Flask, request, jsonify, render_template
import openai
import os
from openai_example import get_similar_restaurants
# Initialize Flask app
app = Flask(__name__)

# Load GPT-4 API key
openai.api_key = os.getenv("OPENAI_API_KEY")

@app.route('/')
def index():
    return render_template('index.html')  # Serve the HTML file

# Flask route for getting recommendations
@app.route('/get_recommendations', methods=['POST'])
def get_recommendations():
    try:
        # Get data from POST request
        data = request.json
        favorite_restaurants = data['favorite_restaurants']
        city = data['city']
        
        # Call the GPT-4 recommendation function
        recommendations = get_similar_restaurants(favorite_restaurants, city)
        
        # Return the recommendations as JSON
        return jsonify({"recommendations": recommendations})

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": "Failed to generate recommendations"}), 500

# Run the Flask app
if __name__ == "__main__":
    app.run(debug=True)
