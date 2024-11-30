from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
import openai
import os
from flask_migrate import Migrate
from dotenv import load_dotenv
import sys
import uuid
import pdb
import logging

load_dotenv()

# Add the PYTHONPATH to sys.path
python_path = os.getenv("PYTHONPATH")
if python_path and python_path not in sys.path:
    sys.path.append(python_path)

from openai_example import get_similar_restaurants, sanitize_name
from models import db, User, Restaurant, UserRequest  # Import models

# Check if the OPENAI_API_KEY environment variable is set
if not os.getenv("OPENAI_API_KEY"):
    raise ValueError("OPENAI_API_KEY environment variable is not set.")

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

# Set up basic logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

@app.route('/')
def index():
    return render_template('index.html')  # Serve the HTML file

# Flask route for getting recommendations
@app.route('/get_recommendations', methods=['POST'])
def get_recommendations():
    try:
        # Get data from POST request
        data = request.json
        user_name = data['user']
        email = "test@test.com"  # Always record this email for testing purposes
        input_restaurants = data['input_restaurants']
        city = data['city']
        
        # Check if the user already exists
        existing_user = User.query.filter_by(email=email).first()
        if not existing_user:
            # Create a new user if they don't exist
            new_user = User(name=user_name, email=email)
            db.session.add(new_user)
            db.session.commit()
        else:
            new_user = existing_user

        # Ensure input restaurants are added to the Restaurant table
        for restaurant_name in input_restaurants:
            restaurant = Restaurant.query.filter_by(name=restaurant_name).first()
            if not restaurant:
                # Log the restaurant name and city for debugging
                logging.debug(f"Adding new restaurant: {restaurant_name} in {city}")
                
                # Use the city as the location if no specific location is provided
                new_restaurant = Restaurant(name=restaurant_name, location=city, cuisine_type=None)
                db.session.add(new_restaurant)
                db.session.commit()
                restaurant = new_restaurant

            # Get recommendations from OpenAI
            recommended_restaurants = get_similar_restaurants(input_restaurants, city)

            # Add recommended restaurants to the database and UserRequest
            for rec in recommended_restaurants:
                recommended_restaurant = Restaurant.query.filter_by(name=rec['name']).first()
                if not recommended_restaurant:
                    # Use the city as the location for recommended restaurants
                    new_recommended_restaurant = Restaurant(name=rec['name'], location=city, cuisine_type=None)
                    db.session.add(new_recommended_restaurant)
                    db.session.commit()
                    recommended_restaurant = new_recommended_restaurant

                # Record the user request in the UserRequest table
                user_request = UserRequest(
                    user_id=new_user.id,
                    input_restaurant_id=restaurant.id,
                    recommended_restaurant_id=recommended_restaurant.id
                )
                db.session.add(user_request)

        # Commit all changes
        db.session.commit()

        logging.debug(f"\n\n\nRecommended restaurants: {recommended_restaurants}")
        return jsonify({"recommendations": recommended_restaurants})

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)})

if __name__ == '__main__':
    print('test')
    app.run(debug=True)
