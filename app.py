import sys
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
import os
from flask_migrate import Migrate
import uuid
import pdb
import logging
from datetime import datetime
from sqlalchemy.exc import IntegrityError
from sqlalchemy import Enum, DateTime
from supabase import create_client, Client

from services import places_service
from utils import generate_slug

from openai_example import get_similar_restaurants, sanitize_name
from models import db, User, Restaurant, UserRequest, RequestRestaurant, RequestType, UserRestaurantPreference, PreferenceType

# Initialize Flask app, explicitly setting a writable instance path for Vercel
app = Flask(__name__, instance_path='/tmp/instance')

# Configure database based on environment
ENVIRONMENT = os.getenv('FLASK_ENV', 'development')
if ENVIRONMENT == 'production':
    # Supabase configuration
    SUPABASE_URL = os.getenv('SUPABASE_URL')
    SUPABASE_KEY = os.getenv('SUPABASE_KEY')
    # Use POSTGRES_URL from Vercel integration, fallback to DATABASE_URL
    DATABASE_URL = os.getenv('POSTGRES_URL') or os.getenv('DATABASE_URL')
    
    if not all([SUPABASE_URL, SUPABASE_KEY, DATABASE_URL]):
        missing = []
        if not SUPABASE_URL: missing.append('SUPABASE_URL')
        if not SUPABASE_KEY: missing.append('SUPABASE_KEY')
        if not DATABASE_URL: missing.append('DATABASE_URL or POSTGRES_URL')
        raise ValueError(f"Missing required Supabase credentials in production environment: {', '.join(missing)}")
    
    try:
        # Initialize Supabase client
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        # Configure SQLAlchemy to use the Postgres connection string
        # Ensure URL uses postgresql:// instead of postgres://
        if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
            DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
        if not DATABASE_URL:
            raise ValueError("Database URL is required but not provided")
        app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
        # Log the database connection info (hiding credentials)
        db_url_parts = DATABASE_URL.split('@')
        if len(db_url_parts) > 1:
            logging.info("Successfully configured database connection with URL: %s", db_url_parts[0].split('://')[0] + '://*****@' + db_url_parts[1].split('/')[0])
        else:
            logging.info("Successfully configured database connection (URL format not standard)")
    except Exception as e:
        logging.error(f"Failed to initialize database connection: {str(e)}")
        raise
else:
    # Use SQLite for development
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////tmp/restaurant_recommendations.db'
    logging.info("Using SQLite database for development")

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize SQLAlchemy
db.init_app(app)

# Initialize Flask-Migrate
migrate = Migrate(app, db)

# Set up logging with configurable level
log_level = os.getenv('LOG_LEVEL', 'DEBUG').upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.DEBUG),
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Run database migrations on startup in production
if ENVIRONMENT == 'production':
    try:
        logging.info("Running database migrations...")
        from flask_migrate import upgrade
        with app.app_context():
            upgrade()
        logging.info("Database migrations completed successfully")
    except Exception as e:
        logging.error(f"Database migration failed: {str(e)}")
        # Don't raise here - let the app start even if migrations fail
        # This prevents the app from crashing if migrations have already been run

# Debug: Check API key in deployment (remove after verification)
api_key = os.getenv('OPENAI_API_KEY')
if api_key:
    logging.info(f"OpenAI API key loaded: {api_key[:15]}...")
else:
    logging.error("No OpenAI API key found in environment!")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_recommendations', methods=['POST'])
def get_recommendations():
    try:
        data = request.json
        user_name = data['user'].lower()
        email = os.getenv('DEFAULT_USER_EMAIL', 'user@example.com')
        place_ids = data.get('place_ids', [])
        input_restaurant_names = data.get('input_restaurants', [])
        city = data['city']
        
        logging.debug(f"Request: user='{user_name}', city='{city}', place_ids={place_ids}, names={input_restaurant_names}")
        
        # Get or create user
        user = User.query.filter_by(name=user_name).first()
        if not user:
            user = User(name=user_name, email=email)
            db.session.add(user)
            db.session.flush()

        user_request = UserRequest(user_id=user.id, city=city)
        db.session.add(user_request)

        # Process and de-duplicate input restaurants
        input_restaurants = []
        processed_place_ids = set()

        for place_id in place_ids:
            if place_id in processed_place_ids:
                continue # Skip duplicates from user input
            
            provider = os.getenv("PLACES_PROVIDER", "google")
            restaurant = Restaurant.query.filter_by(provider=provider, place_id=place_id).first()
            
            if not restaurant:
                details = places_service.get_details(place_id)
                if not details or not details.get('name'):
                    logging.warning(f"Could not fetch valid details for place_id: {place_id}. Skipping.")
                    continue

                # Final check to prevent race conditions or slug collisions
                slug = generate_slug(details['name'], city)
                existing_by_slug = Restaurant.query.filter_by(slug=slug).first()
                if existing_by_slug:
                    restaurant = existing_by_slug
                else:
                    restaurant = Restaurant(
                        name=details['name'],
                        location=details.get('address', 'Unknown'),
                        cuisine_type=", ".join(details.get('categories', [])),
                        provider=provider,
                        place_id=place_id,
                        slug=slug
                    )
                    db.session.add(restaurant)

            if restaurant:
                input_restaurants.append(restaurant)
            processed_place_ids.add(place_id)

        # Fallback for manually entered names
        for name in input_restaurant_names:
            # A more robust implementation might try to fuzzy match or find these via API
            restaurant = Restaurant.query.filter(Restaurant.name.ilike(f'%{name}%')).first()
            if not restaurant:
                logging.debug(f"Creating fallback restaurant for name: {name}")
                restaurant = Restaurant(
                    name=name, 
                    location=city, 
                    provider='manual', 
                    place_id=str(uuid.uuid4()), # Generate a random unique ID
                    slug=generate_slug(name, city)
                )
                db.session.add(restaurant)
            input_restaurants.append(restaurant)

        # Flush to get IDs for new objects
        db.session.flush()

        # Associate input restaurants with the request and user preferences
        for restaurant in input_restaurants:
            # Link to request
            req_rest = RequestRestaurant(
                user_request_id=user_request.id,
                restaurant_id=restaurant.id,
                type=RequestType.input
            )
            db.session.add(req_rest)

            # Set preference to 'like'
            user_pref = UserRestaurantPreference.query.filter_by(user_id=user.id, restaurant_id=restaurant.id).first()
            if user_pref:
                if user_pref.preference != PreferenceType.like:
                    user_pref.preference = PreferenceType.like
                    user_pref.timestamp = datetime.utcnow()
            else:
                new_pref = UserRestaurantPreference(
                    user_id=user.id,
                    restaurant_id=restaurant.id,
                    preference=PreferenceType.like,
                    timestamp=datetime.utcnow()
                )
                db.session.add(new_pref)
        
        db.session.commit() # Commit all transaction changes

        # Get user's full preference list for the AI prompt
        user_preferences = UserRestaurantPreference.query.filter_by(user_id=user.id).join(Restaurant).all()
        liked_restaurants = [p.restaurant.name for p in user_preferences if p.preference == PreferenceType.like]
        disliked_restaurants = [p.restaurant.name for p in user_preferences if p.preference == PreferenceType.dislike]

        recommended_restaurants = get_similar_restaurants(
            liked_restaurants=list(set(liked_restaurants)), # Use set to ensure uniqueness
            disliked_restaurants=list(set(disliked_restaurants)),
            city=city
        )
        logging.debug(f"Recommended restaurants: {recommended_restaurants}")

        # Store recommended restaurants in the database
        for rec in recommended_restaurants:
            restaurant_name = rec['name']
            restaurant_slug = generate_slug(restaurant_name, city)
            
            # Check for existing recommended restaurant by slug to avoid duplicates
            restaurant = Restaurant.query.filter_by(slug=restaurant_slug).first()
            if not restaurant:
                logging.debug(f"Adding new recommended restaurant: {restaurant_name}")
                restaurant = Restaurant(
                    name=restaurant_name,
                    location=city,
                    provider='manual', # AI recommendations are manual entries
                    place_id=str(uuid.uuid4()),
                    slug=restaurant_slug
                )
                db.session.add(restaurant)
                db.session.flush() # Get ID before commit

            # Link recommendation to user request
            req_rest = RequestRestaurant(
                user_request_id=user_request.id,
                restaurant_id=restaurant.id,
                type=RequestType.recommendation
            )
            db.session.add(req_rest)
        
        db.session.commit()

        return jsonify({"recommendations": recommended_restaurants})

    except Exception as e:
        db.session.rollback()
        logging.error(f"Error in get_recommendations: {e}", exc_info=True)
        return jsonify({"error": "An internal error occurred."}), 500

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

@app.route('/autocomplete')
def autocomplete():
    query = request.args.get('query', '')
    city = request.args.get('city', '')
    if not query or not city:
        return jsonify([])
    
    results = places_service.autocomplete(query, city)
    if results is None:
        return jsonify({"error": "API call failed. Check server logs and API key configuration."}), 500
    
    return jsonify(results)

# This is required for Vercel deployment
app.debug = True

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 3000)))
