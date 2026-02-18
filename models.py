from flask_sqlalchemy import SQLAlchemy
import enum
from datetime import datetime

db = SQLAlchemy()

class PreferenceType(enum.Enum):
    like = "like"
    dislike = "dislike"
    neutral = "neutral"

class RequestType(enum.Enum):
    input = "input"
    recommendation = "recommendation"

class Restaurant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(100), nullable=False)
    cuisine_type = db.Column(db.String(200))
    
    provider = db.Column(db.String(20), default="google", nullable=False)
    place_id = db.Column(db.String(128), nullable=False)
    slug = db.Column(db.String(200), nullable=False)

    price_level        = db.Column(db.String(50), nullable=True)
    rating             = db.Column(db.Float, nullable=True)
    user_rating_count  = db.Column(db.Integer, nullable=True)
    editorial_summary  = db.Column(db.Text, nullable=True)
    primary_type       = db.Column(db.String(100), nullable=True)
    serves_dine_in     = db.Column(db.Boolean, nullable=True)
    serves_takeout     = db.Column(db.Boolean, nullable=True)
    serves_delivery    = db.Column(db.Boolean, nullable=True)
    reservable         = db.Column(db.Boolean, nullable=True)
    last_enriched_at   = db.Column(db.DateTime, nullable=True)
    city_hint          = db.Column(db.String(100), nullable=True)

    preferences = db.relationship('UserRestaurantPreference', back_populates='restaurant')
    # Can't have two relationships with the same back_populates.
    # recommendations = db.relationship('Recommendation', back_populates='restaurant') 

    __table_args__ = (
        db.UniqueConstraint("provider", "place_id", name="uq_restaurant_provider_place"),
        db.UniqueConstraint("slug", name="uq_restaurant_slug"),
    )

    def __repr__(self):
        return f'<Restaurant {self.name}>'

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    requests = db.relationship('UserRequest', backref='user', lazy=True)
    preferences = db.relationship('UserRestaurantPreference', back_populates='user')

    def __repr__(self):
        return f'<User {self.name}>'

class UserRestaurantPreference(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    restaurant_id = db.Column(db.Integer, db.ForeignKey('restaurant.id'), nullable=False)
    preference = db.Column(db.Enum(PreferenceType), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', back_populates='preferences')
    restaurant = db.relationship('Restaurant', back_populates='preferences')

class UserRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    city = db.Column(db.String(100))
    restaurants = db.relationship('RequestRestaurant', backref='user_request', lazy=True)

class Recommendation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_request_id = db.Column(db.Integer, db.ForeignKey('user_request.id'), nullable=False)
    restaurant_id = db.Column(db.Integer, db.ForeignKey('restaurant.id'), nullable=False)
    description = db.Column(db.Text, nullable=True)
    # restaurant = db.relationship('Restaurant', back_populates='recommendations')

class RequestRestaurant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_request_id = db.Column(db.Integer, db.ForeignKey('user_request.id'), nullable=False)
    restaurant_id = db.Column(db.Integer, db.ForeignKey('restaurant.id'), nullable=False)
    type = db.Column(db.Enum(RequestType), nullable=False)

class FeedbackSuggestion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    score = db.Column(db.Integer, default=0)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    author = db.relationship('User', backref='suggestions')
    votes = db.relationship('FeedbackVote', backref='suggestion', lazy=True, cascade="all, delete-orphan")

class FeedbackVote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    suggestion_id = db.Column(db.Integer, db.ForeignKey('feedback_suggestion.id'), nullable=False)
    vote_type = db.Column(db.Integer, nullable=False) # 1 for upvote, -1 for downvote
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("user_id", "suggestion_id", name="uq_feedback_user_suggestion"),
    )