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
from datetime import datetime
from sqlalchemy.exc import IntegrityError
from sqlalchemy import Enum, DateTime

load_dotenv()

from openai_example import get_similar_restaurants, sanitize_name
from models import db, User, Restaurant, UserRequest, RequestRestaurant, RequestType, UserRestaurantPreference, PreferenceType

# Check if the OPENAI_API_KEY environment variable is set
if not os.getenv("OPENAI_API_KEY"):
    raise ValueError("OPENAI_API_KEY environment variable is not set.")

# Initialize Flask app
app = Flask(__name__)

# Configure SQLite database
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///restaurant_recommendations.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize SQLAlchemy
db.init_app(app)

# Initialize Flask-Migrate
migrate = Migrate(app, db)

# Load GPT-4 API key
openai.api_key = os.getenv("OPENAI_API_KEY")

# Set up logging with configurable level
log_level = os.getenv('LOG_LEVEL', 'DEBUG').upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.DEBUG),
    format='%(asctime)s - %(levelname)s - %(message)s'
)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_recommendations', methods=['POST'])
def get_recommendations():
    try:
        data = request.json
        user_name = data['user'].lower()
        email = os.getenv('DEFAULT_USER_EMAIL', 'user@example.com')
        input_restaurants = data['input_restaurants']
        city = data['city']
        
        logging.debug(f"Received request for user: {user_name}, city: {city}, input restaurants: {input_restaurants}")
        
        # Get or create user
        existing_user = User.query.filter_by(name=user_name).first()
        if not existing_user:
            new_user = User(name=user_name, email=email)
            db.session.add(new_user)
            db.session.commit()
        else:
            new_user = existing_user
            db.session.add(new_user)

        # Create user request
        new_user_request = UserRequest(user_id=new_user.id, city=city)
        db.session.add(new_user_request)
        db.session.commit()

        # Process input restaurants and get user preferences
        for restaurant_name in input_restaurants:
            # Get or create restaurant
            restaurant = Restaurant.query.filter_by(name=restaurant_name).first()
            if not restaurant:
                logging.debug(f"Adding new restaurant: {restaurant_name} in {city}")
                new_restaurant = Restaurant(name=restaurant_name, location=city, cuisine_type=None)
                db.session.add(new_restaurant)
                db.session.commit()
                restaurant = new_restaurant

            # Add to request restaurants
            request_restaurant = RequestRestaurant(
                user_request_id=new_user_request.id,
                restaurant_id=restaurant.id,
                type=RequestType.input
            )
            db.session.add(request_restaurant)
            db.session.commit()

            # Update or add user preference to "Liked"
            user_pref = UserRestaurantPreference.query.filter_by(
                user_id=new_user.id,
                restaurant_id=restaurant.id
            ).first()

            if user_pref:
                if user_pref.preference != PreferenceType.like:
                    user_pref.preference = PreferenceType.like
                    user_pref.timestamp = datetime.utcnow()
            else:
                new_pref = UserRestaurantPreference(
                    user_id=new_user.id,
                    restaurant_id=restaurant.id,
                    preference=PreferenceType.like,
                    timestamp=datetime.utcnow()
                )
                db.session.add(new_pref)
            db.session.commit()

        # Get user's restaurant preferences
        user_preferences = UserRestaurantPreference.query.filter_by(user_id=new_user.id).join(
            Restaurant
        ).with_entities(
            Restaurant.name,
            UserRestaurantPreference.preference,
            UserRestaurantPreference.timestamp
        ).all()

        # Organize preferences
        liked_restaurants = [rest.name for rest in user_preferences if rest.preference == PreferenceType.like]
        disliked_restaurants = [rest.name for rest in user_preferences if rest.preference == PreferenceType.dislike]

        # Add input restaurants to liked restaurants if not already present
        liked_restaurants.extend([r for r in input_restaurants if r not in liked_restaurants])

        recommended_restaurants = get_similar_restaurants(
            liked_restaurants=liked_restaurants,
            disliked_restaurants=disliked_restaurants,
            city=city
        )
        logging.debug(f"Recommended restaurants: {recommended_restaurants}")

        # Store recommended restaurants in database
        for rec in recommended_restaurants:
            restaurant_name = rec['name']
            # Get or create restaurant
            restaurant = Restaurant.query.filter_by(name=restaurant_name).first()
            if not restaurant:
                logging.debug(f"Adding new recommended restaurant: {restaurant_name} in {city}")
                new_restaurant = Restaurant(name=restaurant_name, location=city, cuisine_type=None)
                db.session.add(new_restaurant)
                db.session.commit()
                restaurant = new_restaurant

            # Link recommendation to user request
            request_restaurant = RequestRestaurant(
                user_request_id=new_user_request.id,
                restaurant_id=restaurant.id,
                type=RequestType.recommendation
            )
            db.session.add(request_restaurant)
            db.session.commit()

        return jsonify({"recommendations": recommended_restaurants})

    except Exception as e:
        logging.error(f"Error in get_recommendations: {e}")
        db.session.rollback()
        return jsonify({"error": str(e)})

@app.route('/get_restaurants', methods=['GET'])
def get_restaurants():
    try:
        restaurants = Restaurant.query.all()
        restaurant_list = [{"id": r.id, "name": r.name} for r in restaurants]
        return jsonify({"restaurants": restaurant_list})
    except Exception as e:
        logging.error(f"Error fetching restaurants: {e}")
        return jsonify({"error": str(e)})

@app.route('/check_user', methods=['GET'])
def check_user():
    try:
        user_name = request.args.get('name')
        user = User.query.filter_by(name=user_name).first()
        if user:
            return jsonify({"exists": True})
        else:
            return jsonify({"exists": False})
    except Exception as e:
        logging.error(f"Error checking user: {e}")
        return jsonify({"error": str(e)})

@app.route('/save_preferences', methods=['POST'])
def save_preferences():
    try:
        data = request.json
        user_name = data['user_name']
        preferences = data['preferences']
        
        logging.debug(f"Received preferences for user {user_name}: {preferences}")

        user = User.query.filter_by(name=user_name).first()
        if not user:
            logging.error(f"User not found: {user_name}")
            return jsonify({"error": "User not found"}), 404

        # Get all existing preferences for this user
        existing_preferences = UserRestaurantPreference.query.filter_by(user_id=user.id).all()
        existing_pref_map = {pref.restaurant_id: pref for pref in existing_preferences}

        # Process incoming preferences
        for pref in preferences:
            restaurant_id = pref['restaurant_id']
            preference_type = pref['preference'].lower()
            
            logging.debug(f"Processing preference: restaurant_id={restaurant_id}, type={preference_type}")

            try:
                pref_enum = PreferenceType[preference_type]
                
                if restaurant_id in existing_pref_map:
                    # Update existing preference
                    existing_pref = existing_pref_map[restaurant_id]
                    existing_pref.preference = pref_enum
                    existing_pref.timestamp = datetime.utcnow()
                    logging.debug(f"Updated existing preference to {pref_enum}")
                else:
                    # Create new preference
                    new_pref = UserRestaurantPreference(
                        user_id=user.id,
                        restaurant_id=restaurant_id,
                        preference=pref_enum,
                        timestamp=datetime.utcnow()
                    )
                    db.session.add(new_pref)
                    logging.debug(f"Created new preference: {pref_enum}")

            except KeyError as e:
                logging.error(f"Invalid preference type: {preference_type}")
                return jsonify({"error": f"Invalid preference type: {preference_type}"}), 400

        db.session.commit()
        logging.debug("Successfully saved all preferences")
        return jsonify({"success": True})

    except Exception as e:
        logging.error(f"Error saving preferences: {e}")
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/get_user_preferences', methods=['GET'])
def get_user_preferences():
    try:
        user_name = request.args.get('name')
        logging.debug(f"Fetching preferences for user: {user_name}")

        user = User.query.filter_by(name=user_name).first()
        if not user:
            logging.error(f"User not found: {user_name}")
            return jsonify({"error": "User not found"}), 404

        preferences = UserRestaurantPreference.query.filter_by(user_id=user.id).all()
        preference_list = []
        
        for p in preferences:
            logging.debug(f"Found preference: restaurant_id={p.restaurant_id}, preference={p.preference}")
            preference_list.append({
                "restaurant_id": p.restaurant_id, 
                "preference": p.preference.value  # Convert enum to string value
            })
            
        logging.debug(f"Returning preferences: {preference_list}")
        return jsonify({"preferences": preference_list})

    except Exception as e:
        logging.error(f"Error fetching user preferences: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/update_user', methods=['POST'])
def update_user():
    try:
        data = request.json
        user_id = data['user_id']
        new_name = data.get('name')
        new_email = data.get('email')

        user = User.query.get(user_id)
        if not user:
            return jsonify({"error": "User not found"}), 404

        if new_name:
            user.name = new_name
        if new_email:
            user.email = new_email

        db.session.commit()
        return jsonify({"success": True})

    except Exception as e:
        logging.error(f"Error updating user: {e}")
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    debug_mode = os.getenv('FLASK_DEBUG', 'True').lower() in ('true', '1', 'yes')
    port = int(os.getenv('FLASK_PORT', 5000))
    host = os.getenv('FLASK_HOST', '127.0.0.1')
    
    print(f'Starting Campfire application on {host}:{port} (debug={debug_mode})')
    app.run(debug=debug_mode, host=host, port=port)
