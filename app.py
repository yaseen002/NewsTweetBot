from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
import requests
import tweepy
from google.cloud import aiplatform
from newsapi import NewsApiClient
from datetime import datetime, timedelta
import threading
import time
import schedule
from config import Config
from models import db, User, ApiKeys, Tweet
from tweet_scheduler import start_scheduler, stop_scheduler

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def mask_api_key(key):
    """Mask API key, showing first 2 and last 2 characters (e.g., '38************93')."""
    if not key or len(key) < 4:
        return "Not set"
    return f"{key[:2]}{'*' * (len(key) - 4)}{key[-2:]}"

def init_db():
    try:
        instance_path = app.instance_path
        os.makedirs(instance_path, exist_ok=True)
        db_path = os.path.join(instance_path, 'app.db')
        print(f"Attempting to create database at: {db_path}")
        with app.app_context():
            db.create_all()
            print(f"Database created successfully at: {db_path}")
    except Exception as e:
        print(f"Error creating database: {str(e)}")
        raise Exception(f"Failed to initialize database: {str(e)}")

init_db()

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Invalid credentials', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form['current_password']
        new_password = request.form['new_password']
        if check_password_hash(current_user.password, current_password):
            current_user.password = generate_password_hash(new_password)
            db.session.commit()
            flash('Password changed successfully', 'success')
            return redirect(url_for('dashboard'))
        flash('Current password is incorrect', 'danger')
    return render_template('change_password.html')

@app.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    recent_tweets = Tweet.query.filter_by(user_id=current_user.id).order_by(Tweet.posted_at.desc()).limit(2).all()
    total_tweets = Tweet.query.filter_by(user_id=current_user.id).count()
    last_tweet = Tweet.query.filter_by(user_id=current_user.id).order_by(Tweet.posted_at.desc()).first()
    # Calculate average tweets per day
    first_tweet = Tweet.query.filter_by(user_id=current_user.id).order_by(Tweet.posted_at.asc()).first()
    avg_tweets_per_day = 0
    if first_tweet and last_tweet:
        days = (last_tweet.posted_at - first_tweet.posted_at).days
        avg_tweets_per_day = total_tweets / (days or 1)

    if request.method == 'POST':
        if 'start' in request.form:
            interval = int(request.form['interval'])
            start_scheduler(app, interval, current_user.id)  # Pass app object
            session['scheduler_running'] = True
            flash('Tweet scheduler started', 'success')
        elif 'stop' in request.form:
            stop_scheduler()
            session['scheduler_running'] = False
            flash('Tweet scheduler stopped', 'success')
    return render_template('dashboard.html', recent_tweets=recent_tweets, 
                         total_tweets=total_tweets, last_tweet=last_tweet,
                         avg_tweets_per_day=avg_tweets_per_day)

@app.route('/configs', methods=['GET', 'POST'])
@login_required
def configs():
    api_keys = ApiKeys.query.filter_by(user_id=current_user.id).first()
    
    # Prepare masked keys for display
    masked_keys = {
        'gemini_key': mask_api_key(api_keys.gemini_key if api_keys else None),
        'client_id': mask_api_key(api_keys.client_id if api_keys else None),
        'client_secret': mask_api_key(api_keys.client_secret if api_keys else None),
        'consumer_key': mask_api_key(api_keys.consumer_key if api_keys else None),
        'consumer_secret': mask_api_key(api_keys.consumer_secret if api_keys else None),
        'news_api_key': mask_api_key(api_keys.news_api_key if api_keys else None),
        'stability_api_key': mask_api_key(api_keys.stability_api_key if api_keys else None)
    }

    if request.method == 'POST':
        # Get existing keys or initialize new record
        if not api_keys:
            api_keys = ApiKeys(user_id=current_user.id)
            db.session.add(api_keys)

        # Update only the submitted fields
        form_id = request.form.get('form_id')
        if form_id == 'gemini-form' and request.form.get('gemini_key'):
            api_keys.gemini_key = request.form['gemini_key']
            flash('Gemini API key updated', 'success')
        elif form_id == 'twitter-form':
            if request.form.get('client_id'):
                api_keys.client_id = request.form['client_id']
            if request.form.get('client_secret'):
                api_keys.client_secret = request.form['client_secret']
            if request.form.get('consumer_key'):
                api_keys.consumer_key = request.form['consumer_key']
            if request.form.get('consumer_secret'):
                api_keys.consumer_secret = request.form['consumer_secret']
            flash('Twitter API keys updated', 'success')
        elif form_id == 'news-form' and request.form.get('news_api_key'):
            api_keys.news_api_key = request.form['news_api_key']
            flash('News API key updated', 'success')
        elif form_id == 'stability-form' and request.form.get('stability_api_key'):
            api_keys.stability_api_key = request.form['stability_api_key']
            flash('Stability AI API key updated', 'success')

        db.session.commit()
        return redirect(url_for('configs'))

    return render_template('configs.html', api_keys=api_keys, masked_keys=masked_keys)

@app.route('/tweets')
@login_required
def tweets():
    page = request.args.get('page', 1, type=int)
    tweets = Tweet.query.filter_by(user_id=current_user.id).order_by(Tweet.posted_at.desc()).paginate(page=page, per_page=10)
    return render_template('tweets.html', tweets=tweets)

if __name__ == '__main__':
    app.run(debug=True)