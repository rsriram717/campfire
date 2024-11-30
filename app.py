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

# Add the PYTHONPATH to sys.path
python_path = os.getenv("PYTHONPATH")
if python_path and python_path not in sys.path:
    sys.path.append(python_path)

from openai_example import get_similar_restaurants, sanitize_name
from models import db, User, Restaurant, UserRequest, RequestRestaurant, RequestType, UserRestaurantPreference, PreferenceType

# Check if the OPENAI_API_KEY environment variable is set
if not os.getenv("OPENAI_API_KEY"):
    raise ValueError("OPENAI_API_KEY environment variable is not set.")

# Initialize Flask app
app = Flask(__name__)

# Configure SQLite database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///C:/Users/Rishi Sriram/Documents/personal/campfire/restaurant_recommendations.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize SQLAlchemy
db.init_app(app)

# Initialize Flask-Migrate
migrate = Migrate(app, db)

# Load GPT-4 API key
openai.api_key = os.getenv("OPENAI_API_KEY")

# Set up basic logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_recommendations', methods=['POST'])
def get_recommendations():
    try:
        data = request.json
        user_name = data['user']
        email = "test@test.com"
        input_restaurants = data['input_restaurants']
        city = data['city']
        
        logging.debug(f"Received request for user: {user_name}, city: {city}, input restaurants: {input_restaurants}")

        existing_user = User.query.filter_by(email=email).first()
        if not existing_user:
            new_user = User(name=user_name, email=email)
            db.session.add(new_user)
            db.session.commit()
        else:
            new_user = existing_user

        new_user_request = UserRequest(user_id=new_user.id, city=city)
        db.session.add(new_user_request)
        db.session.commit()

        for restaurant_name in input_restaurants:
            restaurant = Restaurant.query.filter_by(name=restaurant_name).first()
            if not restaurant:
                logging.debug(f"Adding new restaurant: {restaurant_name} in {city}")
                new_restaurant = Restaurant(name=restaurant_name, location=city, cuisine_type=None)
                db.session.add(new_restaurant)
                db.session.commit()
                restaurant = new_restaurant

            request_restaurant = RequestRestaurant(
                user_request_id=new_user_request.id,
                restaurant_id=restaurant.id,
                type=RequestType.input
            )
            db.session.add(request_restaurant)

        recommended_restaurants = get_similar_restaurants(input_restaurants, city)
        logging.debug(f"Recommended restaurants: {recommended_restaurants}")

        for rec in recommended_restaurants:
            recommended_restaurant = Restaurant.query.filter_by(name=rec['name']).first()
            if not recommended_restaurant:
                logging.debug(f"Adding recommended restaurant: {rec['name']} in {city}")
                recommended_restaurant = Restaurant(name=rec['name'], location=city, cuisine_type=None)
                db.session.add(recommended_restaurant)
                db.session.commit()

            request_restaurant = RequestRestaurant(
                user_request_id=new_user_request.id,
                restaurant_id=recommended_restaurant.id,
                type=RequestType.recommendation
            )
            db.session.add(request_restaurant)

        db.session.commit()

        logging.debug(f"\n\n\nRecommended restaurants: {recommended_restaurants}")
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

        user = User.query.filter_by(name=user_name).first()
        if not user:
            return jsonify({"error": "User not found"}), 404

        for pref in preferences:
            restaurant_id = pref['restaurant_id']
            preference_type = pref['preference']

            existing_pref = UserRestaurantPreference.query.filter_by(
                user_id=user.id,
                restaurant_id=restaurant_id
            ).first()

            if existing_pref:
                if existing_pref.preference != preference_type:
                    existing_pref.preference = preference_type
                    existing_pref.timestamp = datetime.utcnow()
            else:
                new_pref = UserRestaurantPreference(
                    user_id=user.id,
                    restaurant_id=restaurant_id,
                    preference=preference_type,
                    timestamp=datetime.utcnow()
                )
                db.session.add(new_pref)

        db.session.commit()
        return jsonify({"success": True})

    except Exception as e:
        logging.error(f"Error saving preferences: {e}")
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/get_user_preferences', methods=['GET'])
def get_user_preferences():
    try:
        user_name = request.args.get('name')
        user = User.query.filter_by(name=user_name).first()
        if not user:
            return jsonify({"error": "User not found"}), 404

        preferences = UserRestaurantPreference.query.filter_by(user_id=user.id).all()
        preference_list = [{"restaurant_id": p.restaurant_id, "preference": p.preference.value} for p in preferences]
        return jsonify({"preferences": preference_list})

    except Exception as e:
        logging.error(f"Error fetching user preferences: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print('test')
    app.run(debug=True)
