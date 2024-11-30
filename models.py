from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Enum, DateTime
import enum
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)

    def __repr__(self):
        return f'<User {self.name}>'

class Restaurant(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    location = db.Column(db.String(100), nullable=False)
    cuisine_type = db.Column(db.String(50))

    def __repr__(self):
        return f'<Restaurant {self.name.lower()}>'

class RequestType(enum.Enum):
    input = "input"
    recommendation = "recommendation"

class UserRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())

    def __repr__(self):
        return f'<UserRequest {self.id}>'

class RequestRestaurant(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_request_id = db.Column(db.Integer, db.ForeignKey('user_request.id'), nullable=False)
    restaurant_id = db.Column(db.Integer, db.ForeignKey('restaurant.id'), nullable=False)
    type = db.Column(Enum(RequestType), nullable=False)

    def __repr__(self):
        return f'<RequestRestaurant {self.id}>'

class PreferenceType(enum.Enum):
    like = "like"
    dislike = "dislike"
    neutral = "neutral"

class UserRestaurantPreference(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    restaurant_id = db.Column(db.Integer, db.ForeignKey('restaurant.id'), nullable=False)
    preference = db.Column(Enum(PreferenceType), nullable=False)
    timestamp = db.Column(DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('user_id', 'restaurant_id', name='_user_restaurant_uc'),)

    def __repr__(self):
        return f'<UserRestaurantPreference {self.user_id} {self.restaurant_id} {self.preference}>'