from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
import openai
import os
from openai_example import get_similar_restaurants
from models import db, user, Restaurant, FavoriteRestaurant, Recommendation  # Import models
from flask_migrate import Migrate

# Initialize Flask app
app = Flask(__name__)

# Configure SQLite database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///restaurant_recommendations.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize SQLAlchemy
db.init_app(app)  # Correctly initialize SQLAlchemy with the app

# Initialize Flask-Migrate
migrate = Migrate(app, db)

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
        user_name = data['user']  # Change to "user"
        email = "test@test.com"  # Always record this email
        favorite_restaurants = data['favorite_restaurants']
        city = data['city']
        
        # Check if the user already exists
        existing_user = user.query.filter_by(email=email).first()
        if not existing_user:
            # Create a new user if they don't exist
            new_user = user(username=user_name, email=email)  # Change to "user_name"
            db.session.add(new_user)
            db.session.commit()

        # Save favorite restaurants for the user
        for restaurant_name in favorite_restaurants:
            restaurant = Restaurant.query.filter_by(name=restaurant_name).first()
            if restaurant:
                favorite = FavoriteRestaurant(user_id=new_user.user, restaurant_id=restaurant.id)
                db.session.add(favorite)

        db.session.commit()

        # Call the GPT-4 recommendation function
        recommendations = get_similar_restaurants(favorite_restaurants, city)
        
        # Print recommendations for debugging
        print("Recommendations:", recommendations)
        
        # Return the recommendations as JSON
        return jsonify({"recommendations": recommendations})

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": "Failed to generate recommendations"}), 500

# Run the Flask app
if __name__ == "__main__":
    with app.app_context():
        db.create_all()  # Create database tables
    app.run(debug=True)
