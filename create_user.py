from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash
from config import Config
from models import db, User
import os

def create_first_user(username, password):
    # Initialize Flask app
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)

    # Ensure instance directory exists
    os.makedirs(app.instance_path, exist_ok=True)
    db_path = os.path.join(app.instance_path, 'app.db')

    with app.app_context():
        # Create database tables if they don't exist
        db.create_all()

        # Check if user already exists
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            print(f"User '{username}' already exists in the database.")
            return

        # Create new user
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        print(f"User '{username}' created successfully at {db_path}")

if __name__ == '__main__':
    # Default credentials (change as needed)
    DEFAULT_USERNAME = 'admin'
    DEFAULT_PASSWORD = 'admin123'

    try:
        create_first_user(DEFAULT_USERNAME, DEFAULT_PASSWORD)
    except Exception as e:
        print(f"Error creating user: {str(e)}")