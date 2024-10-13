from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
import openai
import os
from .openai_example import get_similar_restaurants
from .models import db, User, Restaurant, UserRequest  # Import models
from flask_migrate import Migrate

# Initialize Flask app
app = Flask(__name__)

# Configure SQLite database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///C:/Users/Rishi Sriram/Documents/personal/campfire/restaurant_recommendations.db'
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
        user_name = data['user']  # User's name
        email = "test@test.com"  # Always record this email
        favorite_restaurants = data['favorite_restaurants']
        city = data['city']
        
        # Check if the user already exists
        existing_user = User.query.filter_by(email=email).first()
        if not existing_user:
            # Create a new user if they don't exist
            new_user = User(name=user_name, email=email)  # Create a new User instance
            db.session.add(new_user)
            db.session.commit()
        else:
            new_user = existing_user  # Use the existing user

        # Call the GPT-4 recommendation function
        recommendations = get_similar_restaurants(favorite_restaurants, city)
        
        # Save user request and recommendations
        for restaurant_name in favorite_restaurants:
            restaurant = Restaurant.query.filter_by(name=restaurant_name).first()
            if restaurant:
                # Log the user request
                for rec in recommendations:
                    recommended_restaurant = Restaurant.query.filter_by(name=rec['name']).first()
                    if recommended_restaurant:
                        user_request = UserRequest(
                            user_id=new_user.id,
                            input_restaurant_id=restaurant.id,
                            recommended_restaurant_id=recommended_restaurant.id
                        )
                        db.session.add(user_request)

        db.session.commit()

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
