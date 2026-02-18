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
from datetime import datetime, timedelta
from sqlalchemy.exc import IntegrityError
from sqlalchemy import Enum, DateTime, inspect, text
from supabase import create_client, Client

from services import places_service
from utils import generate_slug

from openai_example import build_taste_profile, rank_candidates
from models import db, User, Restaurant, UserRequest, RequestRestaurant, RequestType, UserRestaurantPreference, PreferenceType, FeedbackSuggestion, FeedbackVote

# Initialize Flask app, explicitly setting a writable instance path for Vercel
app = Flask(__name__, instance_path='/tmp/instance')

# Configure database based on environment
ENVIRONMENT = os.getenv('FLASK_ENV', 'development')

# Get the appropriate database URL based on environment
if ENVIRONMENT == 'production':
    DATABASE_URL = os.getenv('POSTGRES_URL') or os.getenv('DATABASE_URL')
elif ENVIRONMENT == 'staging':
    DATABASE_URL = os.getenv('STAGING_DATABASE_URL')
else:
    # Development environment
    DATABASE_URL = os.getenv('DEV_DATABASE_URL') or os.getenv('STAGING_DATABASE_URL') or 'sqlite:////tmp/restaurant_recommendations.db'

# Clean and validate database URL
if DATABASE_URL:
    # First ensure it uses postgresql:// protocol
    if DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
    
    # Remove any non-standard parameters (like supa=)
    if '?' in DATABASE_URL:
        base_url = DATABASE_URL.split('?')[0]
        params = DATABASE_URL.split('?')[1].split('&')
        valid_params = ['sslmode', 'connect_timeout', 'application_name']
        cleaned_params = [p for p in params if any(p.startswith(v + '=') for v in valid_params)]
        DATABASE_URL = base_url
        if cleaned_params:
            DATABASE_URL += '?' + '&'.join(cleaned_params)

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
logging.info(f"Using database for {ENVIRONMENT} environment")

# Supabase configuration (only needed in production)
if ENVIRONMENT == 'production':
    SUPABASE_URL = os.getenv('SUPABASE_URL', '')  # Default to empty string instead of None
    SUPABASE_KEY = os.getenv('SUPABASE_KEY', '')  # Default to empty string instead of None
    
    if not all([SUPABASE_URL, SUPABASE_KEY]):
        missing = []
        if not SUPABASE_URL: missing.append('SUPABASE_URL')
        if not SUPABASE_KEY: missing.append('SUPABASE_KEY')
        raise ValueError(f"Missing required Supabase credentials in production environment: {', '.join(missing)}")
    
    try:
        # Initialize Supabase client
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        logging.info("Successfully configured Supabase client")
    except Exception as e:
        logging.error(f"Failed to initialize database connection: {str(e)}")
        raise

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
        with app.app_context():
            # Check if tables exist first
            from sqlalchemy import inspect, text
            inspector = inspect(db.engine)
            existing_tables = inspector.get_table_names()
            logging.info(f"Found existing tables: {existing_tables}")
            
            # Log detailed schema information
            if 'restaurant' in existing_tables:
                columns = inspector.get_columns('restaurant')
                logging.info("Restaurant table schema:")
                for col in columns:
                    logging.info(f"Column: {col['name']}, Type: {col['type']}, Nullable: {col['nullable']}")
            
            # Check if alembic_version table exists and has our initial migration
            initial_migration_id = 'c9e344f09bd8'  # from our initial migration file
            cuisine_type_migration_id = '2024_03_14_01'  # from increase_cuisine_type_length.py
            rich_metadata_migration_id = 'a1b2c3d4e5f6'  # add_rich_metadata_to_restaurant
            up_to_date_ids = {cuisine_type_migration_id, rich_metadata_migration_id}
            has_alembic = 'alembic_version' in existing_tables
            should_run_migrations = True

            if has_alembic:
                # Check if our migrations are recorded
                with db.engine.connect() as conn:
                    result = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
                    logging.info(f"Current migration version: {result}")
                    if result in up_to_date_ids:
                        logging.info("All migrations already applied, skipping migrations")
                        should_run_migrations = False
                    elif result == initial_migration_id:
                        logging.info("Need to apply cuisine_type length migration")
                    else:
                        logging.info(f"Unknown migration state: {result}")
            
            if should_run_migrations:
                if not existing_tables:
                    # Only create tables if none exist
                    logging.info("No tables found. Creating initial schema...")
                    db.create_all()
                    
                    # Record our initial migration
                    if not has_alembic:
                        with db.engine.connect() as conn:
                            conn.execute(text("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL)"))
                            conn.execute(text(f"INSERT INTO alembic_version (version_num) VALUES ('{cuisine_type_migration_id}')"))
                            conn.commit()
                    logging.info("Recorded initial migration")
                else:
                    logging.info("Tables exist but migrations not recorded. Recording initial state...")
                    if not has_alembic:
                        with db.engine.connect() as conn:
                            conn.execute(text("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL)"))
                            conn.execute(text(f"INSERT INTO alembic_version (version_num) VALUES ('{cuisine_type_migration_id}')"))
                            conn.commit()
                    
                    # Ensure cuisine_type column is the right length
                    with db.engine.connect() as conn:
                        conn.execute(text("ALTER TABLE restaurant ALTER COLUMN cuisine_type TYPE VARCHAR(200)"))
                        conn.commit()
                        logging.info("Updated cuisine_type column length to 200")
            
            # Verify final table state
            if 'restaurant' in existing_tables:
                columns = inspector.get_columns('restaurant')
                logging.info("Final restaurant table schema:")
                for col in columns:
                    logging.info(f"Column: {col['name']}, Type: {col['type']}, Nullable: {col['nullable']}")
        
    except Exception as e:
        logging.error(f"Database migration failed: {str(e)}")
        if ENVIRONMENT == 'production':
            raise

# Debug: Check API key in deployment (remove after verification)
api_key = os.getenv('OPENAI_API_KEY')
if api_key:
    logging.info(f"OpenAI API key loaded: {api_key[:15]}...")
else:
    logging.error("No OpenAI API key found in environment!")

@app.route('/')
def index():
    # Main entry point for the application
    return render_template('index.html')

@app.route('/get_recommendations', methods=['POST'])
def get_recommendations():
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No data provided"}), 400
            
        user_name = data.get('user', '').lower()
        if not user_name:
            return jsonify({"error": "User name is required"}), 400
            
        place_ids = data.get('place_ids', [])
        input_restaurant_names = data.get('input_restaurants', [])
        city = data.get('city')
        neighborhood = data.get('neighborhood', None)
        restaurant_types = data.get('restaurant_types', [])
        if not city:
            return jsonify({"error": "City is required"}), 400
        
        logging.debug(f"Request: user='{user_name}', city='{city}', neighborhood='{neighborhood}', types='{restaurant_types}', place_ids={place_ids}, names={input_restaurant_names}")
        
        # Get or create user
        user = User.query.filter_by(name=user_name).first()
        if not user:
            # If user does not exist, create a new one with a unique email
            user_email = f"{user_name.lower().replace(' ', '_')}@example.com"
            user = User(name=user_name, email=user_email)
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
                if not details or 'name' not in details:
                    logging.warning(f"Could not fetch valid details for place_id: {place_id}. Skipping.")
                    continue

                # Create new restaurant with debug logging
                logging.info(f"Creating new restaurant with details: {details}")
                
                slug = generate_slug(details.get('name', ''), city)
                # Handle potential slug collision
                if Restaurant.query.filter_by(slug=slug).first():
                    slug = f"{slug}-{uuid.uuid4().hex[:6]}"

                restaurant = Restaurant(
                    name=details.get('name'),
                    location=details.get('address', ''),
                    cuisine_type=", ".join(details.get('categories', [])),
                    provider=provider,
                    place_id=place_id,
                    slug=slug,
                    price_level=details.get('price_level'),
                    rating=details.get('rating'),
                    user_rating_count=details.get('user_rating_count'),
                    editorial_summary=details.get('editorial_summary'),
                    primary_type=details.get('primary_type'),
                    serves_dine_in=details.get('serves_dine_in'),
                    serves_takeout=details.get('serves_takeout'),
                    serves_delivery=details.get('serves_delivery'),
                    reservable=details.get('reservable'),
                    last_enriched_at=datetime.utcnow(),
                    city_hint=city
                )
                logging.info(f"Restaurant object created: {restaurant.__dict__}")
                
                db.session.add(restaurant)
                db.session.flush()  # Get the ID without committing
                logging.info(f"Restaurant added to session with ID: {restaurant.id}")
            
            processed_place_ids.add(place_id)
            input_restaurants.append(restaurant)
            
            # Add to user request
            req_rest = RequestRestaurant(user_request_id=user_request.id, restaurant_id=restaurant.id, type=RequestType.input)
            db.session.add(req_rest)
        
        # Get user preferences (full ORM objects for taste profile)
        liked_restaurant_objs = db.session.query(Restaurant).join(UserRestaurantPreference).filter(
            UserRestaurantPreference.user_id == user.id,
            UserRestaurantPreference.preference == PreferenceType.like
        ).all()
        disliked_restaurants = db.session.query(Restaurant.name).join(UserRestaurantPreference).filter(
            UserRestaurantPreference.user_id == user.id,
            UserRestaurantPreference.preference == PreferenceType.dislike
        ).all()

        liked_restaurant_names = list({r.name for r in liked_restaurant_objs})
        disliked_restaurant_names = list({r.name for r in disliked_restaurants})

        # Add current input restaurants to liked list for prompt context
        all_liked_objs = liked_restaurant_objs + input_restaurants
        liked_restaurant_names = list({r.name for r in all_liked_objs})

        # Build taste profile from liked ORM objects
        taste_profile = build_taste_profile(all_liked_objs)

        # Get candidate pool — check DB cache first
        CACHE_TTL_DAYS = 30
        fresh_cutoff = datetime.utcnow() - timedelta(days=CACHE_TTL_DAYS)
        cached_candidates = Restaurant.query.filter(
            Restaurant.city_hint == city,
            Restaurant.last_enriched_at >= fresh_cutoff,
            Restaurant.provider == 'google'
        ).limit(40).all()

        def restaurant_to_candidate_dict(r):
            return {
                "place_id": r.place_id,
                "name": r.name,
                "address": r.location,
                "categories": r.cuisine_type.split(", ") if r.cuisine_type else [],
                "price_level": r.price_level,
                "rating": r.rating,
                "user_rating_count": r.user_rating_count,
                "editorial_summary": r.editorial_summary,
                "primary_type": r.primary_type,
                "serves_dine_in": r.serves_dine_in,
                "serves_takeout": r.serves_takeout,
                "serves_delivery": r.serves_delivery,
                "reservable": r.reservable,
            }

        if len(cached_candidates) >= 20:
            logging.info(f"Using {len(cached_candidates)} cached candidates for {city}")
            candidates = [restaurant_to_candidate_dict(r) for r in cached_candidates]
        else:
            logging.info(f"Cache miss for {city} — calling searchNearby")
            candidates = places_service.search_nearby_candidates(city, neighborhood, restaurant_types)
            # Upsert all returned candidates into DB
            for c in candidates:
                if not c.get('place_id') or not c.get('name'):
                    continue
                existing = Restaurant.query.filter_by(provider='google', place_id=c['place_id']).first()
                if existing:
                    existing.last_enriched_at = datetime.utcnow()
                    existing.city_hint = city
                else:
                    cand_slug = generate_slug(c['name'], city)
                    if Restaurant.query.filter_by(slug=cand_slug).first():
                        cand_slug = f"{cand_slug}-{uuid.uuid4().hex[:6]}"
                    new_cand = Restaurant(
                        name=c['name'],
                        location=c.get('address', city),
                        cuisine_type=", ".join(c.get('categories', [])),
                        provider='google',
                        place_id=c['place_id'],
                        slug=cand_slug,
                        price_level=c.get('price_level'),
                        rating=c.get('rating'),
                        user_rating_count=c.get('user_rating_count'),
                        editorial_summary=c.get('editorial_summary'),
                        primary_type=c.get('primary_type'),
                        serves_dine_in=c.get('serves_dine_in'),
                        serves_takeout=c.get('serves_takeout'),
                        serves_delivery=c.get('serves_delivery'),
                        reservable=c.get('reservable'),
                        last_enriched_at=datetime.utcnow(),
                        city_hint=city
                    )
                    db.session.add(new_cand)
            db.session.flush()

        if not candidates:
            return jsonify({"error": "Could not retrieve candidate restaurants at this time."}), 500

        # Use GPT-4 to rank real candidates
        ranked = rank_candidates(
            taste_profile=taste_profile,
            candidates=candidates,
            liked_names=liked_restaurant_names,
            disliked_names=disliked_restaurant_names,
            city=city,
            neighborhood=neighborhood,
            restaurant_types=restaurant_types
        )

        if not ranked:
            return jsonify({"error": "Could not retrieve recommendations at this time."}), 500

        # Save ranked recommendations as Restaurant records and RequestRestaurant links
        output_restaurants = []
        for rec in ranked:
            rec_place_id = rec.get('place_id')
            if not rec_place_id:
                continue

            resolved_restaurant = Restaurant.query.filter_by(provider='google', place_id=rec_place_id).first()
            if not resolved_restaurant:
                slug = generate_slug(rec['name'], city)
                if Restaurant.query.filter_by(slug=slug).first():
                    slug = f"{slug}-{uuid.uuid4().hex[:6]}"
                resolved_restaurant = Restaurant(
                    name=rec['name'],
                    location=rec.get('address', city),
                    cuisine_type="",
                    provider='google',
                    place_id=rec_place_id,
                    slug=slug,
                    price_level=rec.get('price_level'),
                    rating=rec.get('rating'),
                    last_enriched_at=datetime.utcnow(),
                    city_hint=city
                )
                db.session.add(resolved_restaurant)
                db.session.flush()

            req_rec = RequestRestaurant(
                user_request_id=user_request.id,
                restaurant_id=resolved_restaurant.id,
                type=RequestType.recommendation
            )
            db.session.add(req_rec)

            output_restaurants.append({
                "id": resolved_restaurant.id,
                "name": resolved_restaurant.name,
                "description": rec.get('description', ''),
                "reason": rec.get('reason'),
                "address": resolved_restaurant.location
            })

        db.session.commit()
        return jsonify({"recommendations": output_restaurants})
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error in get_recommendations: {str(e)}", exc_info=True)
        return jsonify({"error": "An internal server error occurred."}), 500

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

        # 1. Get existing preferences
        preferences = UserRestaurantPreference.query.filter_by(user_id=user.id).all()
        pref_map = {p.restaurant_id: p.preference.value for p in preferences}

        # 2. Get restaurants recommended to the user (History)
        # Join UserRequest -> RequestRestaurant -> Restaurant
        recommended_restaurants = db.session.query(Restaurant).join(RequestRestaurant).join(UserRequest)\
            .filter(UserRequest.user_id == user.id, RequestRestaurant.type == RequestType.recommendation).all()

        # 3. Get restaurants explicitly rated (even if not recommended recently)
        rated_restaurants = db.session.query(Restaurant).join(UserRestaurantPreference)\
            .filter(UserRestaurantPreference.user_id == user.id).all()

        # Combine and deduplicate
        all_relevant_restaurants = {r.id: r for r in recommended_restaurants + rated_restaurants}.values()

        # Build response
        restaurant_list = []
        for r in all_relevant_restaurants:
            restaurant_list.append({
                "id": r.id,
                "name": r.name,
                "preference": pref_map.get(r.id, "neutral") # Default to neutral if not rated
            })
            
        # Sort by name
        restaurant_list.sort(key=lambda x: x['name'])

        logging.debug(f"Returning {len(restaurant_list)} restaurants for user {user_name}")
        return jsonify({"user_name": user.name, "restaurants": restaurant_list})

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
    session_token = request.args.get('session_token')
    
    if not query or not city:
        return jsonify([])
    
    results = places_service.autocomplete(query, city, session_token=session_token)
    if results is None:
        return jsonify({"error": "API call failed. Check server logs and API key configuration."}), 500
    
    return jsonify(results)

# --- Feedback Routes ---

@app.route('/submit_feedback', methods=['POST'])
def submit_feedback():
    try:
        data = request.json
        user_name = data.get('user_name')
        content = data.get('content')
        
        if not user_name or not content:
            return jsonify({"error": "Missing user name or content"}), 400
            
        user = User.query.filter_by(name=user_name).first()
        if not user:
            return jsonify({"error": "User not found"}), 404
            
        suggestion = FeedbackSuggestion(
            user_id=user.id,
            content=content,
            score=0
        )
        db.session.add(suggestion)
        db.session.commit()
        
        return jsonify({"success": True, "id": suggestion.id})
        
    except Exception as e:
        logging.error(f"Error submitting feedback: {e}")
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/get_feedback', methods=['GET'])
def get_feedback():
    try:
        user_name = request.args.get('user_name')
        user_id = None
        if user_name:
            user = User.query.filter_by(name=user_name).first()
            if user:
                user_id = user.id
        
        # Get all suggestions sorted by score desc
        suggestions = FeedbackSuggestion.query.order_by(FeedbackSuggestion.score.desc()).limit(50).all()
        
        # Get user's votes if user exists
        user_votes = {} # suggestion_id -> vote_type
        if user_id:
            votes = FeedbackVote.query.filter_by(user_id=user_id).all()
            for v in votes:
                user_votes[v.suggestion_id] = v.vote_type
        
        result = []
        for s in suggestions:
            result.append({
                "id": s.id,
                "content": s.content,
                "score": s.score,
                "user_vote": user_votes.get(s.id, 0) # 0 if no vote, 1 if up, -1 if down
            })
            
        return jsonify({"suggestions": result})
        
    except Exception as e:
        logging.error(f"Error getting feedback: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/vote_feedback', methods=['POST'])
def vote_feedback():
    try:
        data = request.json
        user_name = data.get('user_name')
        suggestion_id = data.get('suggestion_id')
        vote_type = data.get('vote_type') # 1 or -1
        
        if not all([user_name, suggestion_id, vote_type]):
            return jsonify({"error": "Missing data"}), 400
            
        user = User.query.filter_by(name=user_name).first()
        if not user:
            return jsonify({"error": "User not found"}), 404
            
        suggestion = FeedbackSuggestion.query.get(suggestion_id)
        if not suggestion:
            return jsonify({"error": "Suggestion not found"}), 404
            
        # Check existing vote
        existing_vote = FeedbackVote.query.filter_by(
            user_id=user.id, 
            suggestion_id=suggestion.id
        ).first()
        
        new_score_delta = 0
        
        if existing_vote:
            if existing_vote.vote_type == vote_type:
                # Toggle off (remove vote)
                db.session.delete(existing_vote)
                new_score_delta = -vote_type
            else:
                # Switch vote (e.g. 1 to -1)
                # Score change: -1 - 1 = -2
                new_score_delta = vote_type - existing_vote.vote_type
                existing_vote.vote_type = vote_type
        else:
            # New vote
            new_vote = FeedbackVote(
                user_id=user.id,
                suggestion_id=suggestion.id,
                vote_type=vote_type
            )
            db.session.add(new_vote)
            new_score_delta = vote_type
            
        # Update cached score
        suggestion.score += new_score_delta
        db.session.commit()
        
        return jsonify({"success": True, "new_score": suggestion.score})
        
    except Exception as e:
        logging.error(f"Error voting: {e}")
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# This is required for Vercel deployment
app.debug = True

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3001)
    