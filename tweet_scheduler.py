import threading
import time
import schedule
import tweepy
from newsapi import NewsApiClient
from models import db, Tweet, ApiKeys, UsedNews
from image_gen import generate_image
import os
import requests
from datetime import datetime

scheduler_thread = None
scheduler_running = False

def shorten_url(long_url):
    """Shorten URL using a simple placeholder (replace with a real URL shortener API if needed)."""
    return long_url[:20] + "..."  # Placeholder; use Bitly or TinyURL API for production

def generate_seo_tweet(article):
    """Generate an SEO-optimized tweet from a news article."""
    title = article['title'][:100]  # Truncate title if too long
    url = shorten_url(article['url'])
    hashtags = "#News #Trending #USNews"  # Add relevant hashtags
    tweet = f"{title} {url} {hashtags}"
    if len(tweet) > 280:
        tweet = f"{title[:280 - len(url) - len(hashtags) - 5]}... {url} {hashtags}"
    return tweet

def fetch_top_news(news_api_key, user_id):
    """Fetch top U.S. headlines and return one unused article."""
    newsapi = NewsApiClient(api_key=news_api_key)
    response = newsapi.get_top_headlines(country='us')
    if response['status'] != 'ok' or not response['articles']:
        raise Exception("Failed to fetch news articles")
    
    used_urls = {news.news_url for news in UsedNews.query.filter_by(user_id=user_id).all()}
    for article in response['articles']:
        if article['url'] not in used_urls:
            return article
    raise Exception("No unused news articles available")

def post_tweet(app, user_id, interval):
    """Fetch news, generate image, and post tweet with debugging prints, within app context."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"\n\n[{timestamp}] [User {user_id}] Starting to post tweet...\n\n")
    with app.app_context():  # Ensure Flask app context for database operations
        api_keys = ApiKeys.query.filter_by(user_id=user_id).first()
        if not api_keys or not all([api_keys.news_api_key, api_keys.stability_api_key, 
                                   api_keys.consumer_key, api_keys.consumer_secret]):
            print(f"[{timestamp}] [User {user_id}] Error: Missing API keys")
            return

        try:
            # Step 1: Fetch unused news article
            article = fetch_top_news(api_keys.news_api_key, user_id)
            print(f"[{timestamp}] [User {user_id}] News fetched: Title='{article['title']}', URL={article['url']}")

            # Step 2: Generate tweet
            tweet_content = generate_seo_tweet(article)
            print(f"[{timestamp}] [User {user_id}] Tweet generated: Content='{tweet_content}', Length={len(tweet_content)}")

            # Step 3: Generate image
            image_prompt = article['title'][:100]  # Use article title as prompt
            image_path = f"static/images/tweet_{int(time.time())}.webp"
            generate_image(image_prompt, api_keys.stability_api_key, image_path)
            print(f"[{timestamp}] [User {user_id}] Image generated: Path={image_path}")

            # Step 4: Post tweet with image
            auth = tweepy.OAuthHandler(api_keys.consumer_key, api_keys.consumer_secret)
            api = tweepy.API(auth)
            media = api.media_upload(image_path)
            tweet_status = api.update_status(status=tweet_content, media_ids=[media.media_id])
            print(f"[{timestamp}] [User {user_id}] Tweet posted: ID={tweet_status.id}, Content='{tweet_content}'")

            # Save tweet to database
            tweet = Tweet(user_id=user_id, content=tweet_content, image_path=image_path, posted_at=datetime.utcnow())
            db.session.add(tweet)
            
            # Mark news as used
            used_news = UsedNews(user_id=user_id, news_url=article['url'])
            db.session.add(used_news)
            db.session.commit()

            # Clean up image
            if os.path.exists(image_path):
                os.remove(image_path)
                print(f"[{timestamp}] [User {user_id}] Image cleaned up: Path={image_path}")
        
        except Exception as e:
            print(f"[{timestamp}] [User {user_id}] Error posting tweet: {str(e)}")

def run_scheduler(app, user_id, interval):
    """Run the scheduler to post tweets at the specified interval."""
    global scheduler_running
    schedule.every(interval).minutes.do(post_tweet, app=app, user_id=user_id, interval=interval)
    scheduler_running = True
    while scheduler_running:
        schedule.run_pending()
        time.sleep(1)

def start_scheduler(app, interval, user_id):
    """Start the scheduler in a separate thread."""
    global scheduler_thread, scheduler_running
    if scheduler_thread is None or not scheduler_running:
        scheduler_running = True
        scheduler_thread = threading.Thread(target=run_scheduler, args=(app, user_id, interval))
        scheduler_thread.daemon = True
        scheduler_thread.start()
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [User {user_id}] Scheduler started with interval {interval} minutes")
    else:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [User {user_id}] Scheduler already running")

def stop_scheduler():
    """Stop the scheduler."""
    global scheduler_thread, scheduler_running
    scheduler_running = False
    if scheduler_thread:
        scheduler_thread = None
        schedule.clear()
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Scheduler stopped")