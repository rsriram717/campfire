from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)  # Auto-incrementing ID
    name = db.Column(db.String(50), unique=True, nullable=False)  # User's name
    email = db.Column(db.String(120), unique=True, nullable=False)  # User's email

    def __repr__(self):
        return f'<User {self.name}>'

class Restaurant(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)  # Auto-incrementing ID
    name = db.Column(db.String(100), nullable=False, unique=True)  # Restaurant name
    location = db.Column(db.String(100), nullable=False)  # Restaurant location
    cuisine_type = db.Column(db.String(50))  # Type of cuisine

    def __repr__(self):
        return f'<Restaurant {self.name}>'

class UserRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)  # Auto-incrementing ID
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # Foreign key referencing User
    input_restaurant_id = db.Column(db.Integer, db.ForeignKey('restaurant.id'), nullable=False)  # Foreign key referencing input restaurant
    recommended_restaurant_id = db.Column(db.Integer, db.ForeignKey('restaurant.id'), nullable=False)  # Foreign key referencing recommended restaurant

    def __repr__(self):
        return f'<UserRequest {self.id}>'
