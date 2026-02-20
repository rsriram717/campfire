# Campfire 🔥

> *More than just a meal*

Campfire is an intelligent restaurant recommendation system that leverages OpenAI's GPT-4 to provide personalized dining suggestions based on user preferences and dining history. The application learns from your favorite restaurants and provides thoughtful recommendations tailored to your taste.

## 🌟 Features

### Core Functionality
- **AI-Powered Recommendations**: Uses Claude Haiku to rank real Google Places candidates against your taste profile
- **Preference Learning**: Tracks and learns from your restaurant likes and dislikes over time
- **City-Specific Suggestions**: Currently supports Chicago and New York with localized recommendations
- **Neighborhood Filtering**: Optionally narrow recommendations to specific neighborhoods
- **Restaurant Type Filtering**: Filter by Casual, Fine Dining, or Bar styles
- **Places Autocomplete**: Google/Yelp API integration for restaurant search
- **User Profile Management**: Maintains individual user profiles with preference history
- **Interactive Web Interface**: Clean, responsive Bootstrap-based UI with tabbed navigation

### Key Capabilities
- **Restaurant Input**: Enter up to 5 favorite restaurants to seed recommendations
- **Preference Tracking**: Like/dislike system that improves future recommendations
- **History vs. Session Weighting**: Slider controls how much current inputs vs. past history shape recommendations
- **Revisit Mode**: Slider to surface previously recommended restaurants instead of always finding new ones
- **Request History**: Maintains a history of all recommendation requests and responses
- **Smart Filtering**: Avoids recommending restaurants similar to ones you've disliked
- **Database Persistence**: All user data, preferences, and restaurant information stored locally

## 🏗️ Architecture

### Technology Stack
- **Backend**: Flask (Python 3.9+)
- **Database**: SQLite (dev) / PostgreSQL via Supabase (prod) with SQLAlchemy ORM
- **AI Integration**: OpenAI GPT-4 API
- **Places APIs**: Google Places / Yelp Fusion (configurable)
- **Frontend**: Bootstrap 4, jQuery, vanilla JavaScript
- **Database Migrations**: Flask-Migrate with Alembic

### Database Schema
The application uses 5 main tables to store user data, restaurant information, and preferences.

A detailed breakdown of the database schema, including an Entity-Relationship Diagram, is available in the [Database Documentation](./docs/database.md).

### AI Recommendation Engine
The recommendation system works by:
1. Collecting user's liked/disliked history and current session inputs
2. Fetching up to 20 real candidate restaurants from Google Places (`searchNearby`)
3. Pre-filtering candidates (exclude lodging, low-rated, already-seen, type mismatches)
4. Optionally injecting previously recommended restaurants based on `revisit_weight`
5. Building a weighted taste profile from history and session inputs (controlled by `input_weight`)
6. Sending the numbered candidate list to Claude Haiku (`prompt_rank.txt`) to pick and explain the top 3
7. Returning ranked results by candidate number — no additional API resolution needed
8. Storing recommendations in the database as `RequestRestaurant` records

## 🚀 Setup & Installation

### Prerequisites
- Python 3.9 or higher
- OpenAI API key
- Git (for cloning the repository)

### Installation Steps

1. **Clone the Repository**
   ```bash
   git clone <repository-url>
   cd campfire
   ```

2. **Create Virtual Environment**
   ```bash
   python3 -m venv campfire_env
   source campfire_env/bin/activate  # On Windows: campfire_env\Scripts\activate
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set Up Environment Variables**
   Copy the example environment file and configure it:
   ```bash
   cp .env.example .env
   ```
   
   Then edit `.env` with your specific values:
   ```bash
   # Required: Add your OpenAI API key
   OPENAI_API_KEY=your_openai_api_key_here
   
   # Optional: Customize other settings as needed
   FLASK_DEBUG=True
   FLASK_PORT=3001
   LOG_LEVEL=DEBUG
   
   # Places API (choose one provider)
   PLACES_PROVIDER=google
   GOOGLE_API_KEY=your_google_api_key_here
   ```

5. **Initialize Database**
   ```bash
   python -c "import sys; sys.path.append('.'); from app import app, db; app.app_context().push(); db.create_all(); print('Database initialized!')"
   ```

6. **Run the Application**
   ```bash
   python app.py
   ```

The application will be available at `http://localhost:3001` (or your configured host/port)

## 📖 Usage Guide

### Getting Recommendations

1. **Navigate to "Get Recommendations" tab**
2. **Enter your name** - This creates/identifies your user profile
3. **Add favorite restaurants** - Enter 1-5 restaurants you enjoy (autocomplete helps find them)
4. **Select your city** - Choose between Chicago or New York
5. **Optionally filter** - Select neighborhood and/or restaurant types (Casual, Fine Dining, Bar)
6. **Adjust sliders** (optional):
   - *Base recommendations on*: balance between your history and this session's inputs
   - *Show me*: "All New" for fresh picks, "Revisit" to surface past recommendations, or Mixed
7. **Click "Get Recommendations"** - The AI will select 3 personalized suggestions from real nearby places

### Managing Preferences

1. **Switch to "Restaurant Preferences" tab**
2. **Enter your name** - Must match the name used for recommendations
3. **Click "Show Restaurants"** - Displays all restaurants in your history
4. **Set preferences** - Mark restaurants as liked, disliked, or neutral
5. **Save changes** - Updates your preference profile for future recommendations

### Understanding Recommendations

Each recommendation includes:
- **Restaurant name** - Sanitized and formatted for consistency
- **Why it's recommended** - 2-3 short phrases explaining the match to your preferences
- **Automatic storage** - All recommendations are saved to your profile

## 🛠️ API Endpoints

### Core Routes
- `GET /` - Main application interface
- `POST /get_recommendations` - Generate AI-powered recommendations
- `POST /save_preferences` - Update user restaurant preferences
- `GET /get_user_preferences` - Retrieve user's current preferences
- `GET /check_user` - Verify if user exists in system
- `GET /get_restaurants` - List all restaurants in database
- `POST /update_user` - Modify user account information
- `GET /autocomplete` - Restaurant search autocomplete via Places API

### Request/Response Examples

**Get Recommendations Request:**
```json
{
  "user": "john_doe",
  "place_ids": ["ChIJ...", "ChIJ..."],
  "input_restaurants": ["The Purple Pig", "Girl & Goat"],
  "city": "Chicago",
  "neighborhood": "West Loop",
  "restaurant_types": ["Casual", "Fine Dining"],
  "input_weight": 0.7,
  "revisit_weight": 0.0
}
```

**Get Recommendations Response:**
```json
{
  "recommendations": [
    {
      "name": "Au Cheval",
      "description": "Known for exceptional burgers and creative small plates, similar atmosphere to your favorites"
    },
    {
      "name": "Monteverde",
      "description": "Italian-focused menu with handmade pasta, matches your preference for chef-driven concepts"
    },
    {
      "name": "RPM Steak",
      "description": "Upscale steakhouse with innovative preparation, aligns with your taste for quality dining"
    }
  ]
}
```

## 🗂️ Project Structure

```
campfire/
├── app.py                 # Main Flask application + _restaurant_to_candidate helper
├── models.py              # SQLAlchemy database models
├── openai_example.py      # AI ranking engine (build_taste_profile, rank_candidates)
├── prompt.txt             # Legacy GPT-4 prompt template (unused by main flow)
├── prompt_rank.txt        # Claude Haiku ranking prompt template
├── utils.py               # Utility functions (slug generation)
├── requirements.txt       # Python dependencies
├── vercel.json            # Vercel deployment config
├── .env                   # Environment variables (create from .env.example)
├── services/              # External API integrations
│   ├── __init__.py        # Service factory (Google/Yelp)
│   ├── google_service.py  # Google Places API (searchNearby, get_details, autocomplete)
│   ├── yelp_service.py    # Yelp Fusion API (stub — search_nearby_candidates returns [])
│   └── places.py          # Abstract places interface
├── templates/
│   └── index.html         # Main web interface
├── static/
│   ├── styles.css         # Custom styling
│   └── script.js          # Frontend JavaScript
├── features/              # Feature specs and bug tracker
│   ├── todo.md            # Open bugs and improvements
│   ├── filters_type_and_location.md
│   └── username_input.md
├── docs/                  # Documentation
│   └── database.md        # Database schema docs
├── migrations/            # Alembic database migrations
└── campfire_env/          # Virtual environment (created during setup)
```

## 🔧 Configuration

### Environment Variables
All configuration is managed through environment variables defined in your `.env` file:

#### Required Configuration
- `OPENAI_API_KEY` - Your OpenAI API key for AI recommendations

#### Optional Configuration
- `DEV_DATABASE_URL` - Development database (default: `sqlite:////tmp/restaurant_recommendations.db`)
- `STAGING_DATABASE_URL` - Staging database connection string
- `POSTGRES_URL` - Production PostgreSQL connection string
- `FLASK_ENV` - Environment: development, staging, production (default: `development`)
- `FLASK_DEBUG` - Enable debug mode (default: `True`)
- `FLASK_HOST` - Host to bind the application (default: `127.0.0.1`)
- `FLASK_PORT` - Port to run the application (default: `3001`)
- `LOG_LEVEL` - Logging level: DEBUG, INFO, WARNING, ERROR (default: `DEBUG`)
- `DEFAULT_USER_EMAIL` - Default email for new users (default: `user@example.com`)

#### Places API Configuration
- `PLACES_PROVIDER` - API provider: `google` or `yelp` (default: `google`)
- `GOOGLE_API_KEY` - Google Places API key (required if using Google)
- `YELP_API_KEY` - Yelp Fusion API key (required if using Yelp)

### Database Configuration
- **Development**: SQLite database at `/tmp/restaurant_recommendations.db`
- **Staging/Production**: PostgreSQL via Supabase (set `STAGING_DATABASE_URL` or `POSTGRES_URL`)
- **Environment Selection**: Controlled by `FLASK_ENV` variable

### AI Model Configuration
- **Ranking Model**: Claude Haiku (`claude-haiku-4-5-20251001`) via Anthropic API — ranks real candidates
- **Legacy Model**: GPT-4 (`gpt-4`) — used by `get_similar_restaurants()` (not in main flow)
- **Ranking Token Limit**: 300 tokens per ranking request
- **Prompt Template**: `prompt_rank.txt` — modify to adjust ranking instructions
- **Customization**: `RANK_MODEL` constant in `openai_example.py` controls the ranking model

## 🧪 Development

### Running in Debug Mode
The application runs in debug mode by default, providing:
- Automatic reloading on code changes
- Detailed error messages and stack traces
- Interactive debugger in browser

### Database Migrations
For schema changes:
```bash
# Generate migration
flask db migrate -m "Description of changes"

# Apply migration
flask db upgrade
```

### Adding New Cities
1. Update the city dropdown in `templates/index.html`
2. No backend changes needed - the AI will adapt to new cities automatically

### Extending Preference Types
The `PreferenceType` enum in `models.py` supports:
- `like` - Positive preference
- `dislike` - Negative preference  
- `neutral` - No strong preference

## 🤝 Contributing

### For Developers
- Follow PEP 8 style guidelines
- Add logging for new features using the existing logging setup
- Ensure database operations include proper error handling and rollbacks
- Test API endpoints with both valid and invalid data

### For AI Assistants
This application serves as a complete example of:
- Flask web application with database integration
- OpenAI API integration for content generation
- User preference tracking and machine learning concepts
- RESTful API design patterns
- Frontend-backend integration with JavaScript

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙋‍♀️ Support

For questions, issues, or feature requests, please review the codebase structure and API documentation above. The application is designed to be self-documenting through its code organization and comprehensive logging system.# Updated Wed Jun 25 02:26:22 CDT 2025
