from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

class ApiKeys(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    gemini_key = db.Column(db.String(200))
    client_id = db.Column(db.String(200))
    client_secret = db.Column(db.String(200))
    consumer_key = db.Column(db.String(200))
    consumer_secret = db.Column(db.String(200))
    news_api_key = db.Column(db.String(200))
    stability_api_key = db.Column(db.String(200))  # New field for Stability AI API key

class Tweet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    image_path = db.Column(db.String(200))
    posted_at = db.Column(db.DateTime, default=datetime.utcnow)

class UsedNews(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    news_url = db.Column(db.String(500), unique=True, nullable=False)
    used_at = db.Column(db.DateTime, default=datetime.utcnow)