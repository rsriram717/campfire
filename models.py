from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Enum
import enum

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
        return f'<Restaurant {self.name}>'

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