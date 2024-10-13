from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class user(db.Model):
    user = db.Column(db.String(50), primary_key=True)  # Set user as primary key
    email = db.Column(db.String(120), unique=True, nullable=False)
    favorite_restaurants = db.relationship('FavoriteRestaurant', backref='user', lazy=True)

    def __repr__(self):
        return f'<user {self.user}>'

class Restaurant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(100), nullable=False)
    cuisine_type = db.Column(db.String(50))

    def __repr__(self):
        return f'<Restaurant {self.name}>'

class FavoriteRestaurant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(50), db.ForeignKey('user.user'), nullable=False)  # Update foreign key reference
    restaurant_id = db.Column(db.Integer, db.ForeignKey('restaurant.id'), nullable=False)

    def __repr__(self):
        return f'<FavoriteRestaurant {self.id}>'

class Recommendation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(50), db.ForeignKey('user.user'), nullable=False)  # Update foreign key reference
    restaurant_id = db.Column(db.Integer, db.ForeignKey('restaurant.id'), nullable=False)
    description = db.Column(db.String(255))

    def __repr__(self):
        return f'<Recommendation {self.id}>'
