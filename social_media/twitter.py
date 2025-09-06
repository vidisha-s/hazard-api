# Create Twitter API Integration
twitter_api_content = '''
"""
Twitter API integration for ocean hazard monitoring
"""
import logging
import tweepy
import time
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from django.conf import settings
from django.utils import timezone
from django.contrib.gis.geos import Point

from .models import SocialMediaPlatform, SocialMediaPost, APIUsage, KeywordMonitoring
from apps.ml_models.training_utils import get_ml_pipeline

logger = logging.getLogger(__name__)


class TwitterAPIClient:
    """Twitter API client for fetching ocean hazard related tweets"""
    
    def __init__(self):
        self.api = None
        self.client = None
        self.platform = None
        self.ml_pipeline = get_ml_pipeline()
        self._initialize_api()
        self._setup_platform()
    
    def _initialize_api(self):
        """Initialize Twitter API clients"""
        try:
            # Twitter API v2 client
            self.client = tweepy.Client(
                bearer_token=settings.TWITTER_BEARER_TOKEN,
                consumer_key=settings.TWITTER_API_KEY,
                consumer_secret=settings.TWITTER_API_SECRET,
                access_token=settings.TWITTER_ACCESS_TOKEN,
                access_token_secret=settings.TWITTER_ACCESS_TOKEN_SECRET,
                wait_on_rate_limit=True
            )
            
            # Twitter API v1.1 for additional features
            auth = tweepy.OAuthHandler(
                settings.TWITTER_API_KEY,
                settings.TWITTER_API_SECRET
            )
            auth.set_access_token(
                settings.TWITTER_ACCESS_TOKEN,
                settings.TWITTER_ACCESS_TOKEN_SECRET
            )
            self.api = tweepy.API(auth, wait_on_rate_limit=True)
            
            logger.info("Twitter API client initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Twitter API: {str(e)}")
            raise
    
    def _setup_platform(self):
        """Setup or get Twitter platform record"""
        try:
            self.platform, created = SocialMediaPlatform.objects.get_or_create(
                name='Twitter',
                defaults={
                    'api_endpoint': 'https://api.twitter.com/2/',
                    'is_active': True,
                    'rate_limit': 300  # Twitter API v2 rate limit
                }
            )
            if created:
                logger.info("Twitter platform record created")
            
        except Exception as e:
            logger.error(f"Failed to setup Twitter platform: {str(e)}")
            raise
    
    def search_tweets(self, query: str, max_results: int = 100, 
                     start_time: Optional[datetime] = None,
                     end_time: Optional[datetime] = None) -> List[Dict]:
        """Search for tweets using Twitter API v2"""
        tweets_data = []
        
        try:
            # Default time range (last 24 hours)
            if not start_time:
                start_time = datetime.now() - timedelta(days=1)
            if not end_time:
                end_time = datetime.now()
            
            # Tweet fields to retrieve
            tweet_fields = [
                'author_id', 'created_at', 'public_metrics', 'lang',
                'geo', 'context_annotations', 'entities', 'referenced_tweets'
            ]
            
            user_fields = [
                'username', 'name', 'verified', 'public_metrics'
            ]
            
            expansions = ['author_id', 'geo.place_id']
            
            # Search tweets
            tweets = tweepy.Paginator(
                self.client.search_recent_tweets,
                query=query,
                tweet_fields=tweet_fields,
                user_fields=user_fields,
                expansions=expansions,
                start_time=start_time,
                end_time=end_time,
                max_results=min(max_results, 100)  # API limit per request
            ).flatten(limit=max_results)
            
            # Process tweets
            for tweet in tweets:
                tweet_data = self._process_tweet(tweet)
                if tweet_data:
                    tweets_data.append(tweet_data)
            
            logger.info(f"Retrieved {len(tweets_data)} tweets for query: {query}")
            
            # Log API usage
            self._log_api_usage('search_recent_tweets', len(tweets_data), True)
            
        except Exception as e:
            logger.error(f"Error searching tweets: {str(e)}")
            self._log_api_usage('search_recent_tweets', 0, False)
        
        return tweets_data
    
    def _process_tweet(self, tweet) -> Optional[Dict]:
        """Process individual tweet data"""
        try:
            # Extract basic tweet information
            tweet_data = {
                'id': str(tweet.id),
                'text': tweet.text,
                'created_at': tweet.created_at,
                'author_id': str(tweet.author_id),
                'lang': getattr(tweet, 'lang', 'en'),
                'public_metrics': getattr(tweet, 'public_metrics', {}),
                'geo': getattr(tweet, 'geo', None),
                'entities': getattr(tweet, 'entities', {}),
                'context_annotations': getattr(tweet, 'context_annotations', []),
            }
            
            # Extract author information if available
            if hasattr(tweet, 'includes') and 'users' in tweet.includes:
                for user in tweet.includes['users']:
                    if str(user.id) == tweet_data['author_id']:
                        tweet_data['author'] = {
                            'username': user.username,
                            'name': user.name,
                            'verified': getattr(user, 'verified', False),
                            'public_metrics': getattr(user, 'public_metrics', {})
                        }
                        break
            
            # Extract location information
            location = None
            if tweet_data.get('geo'):
                # Handle different geo formats
                geo_data = tweet_data['geo']
                if 'coordinates' in geo_data:
                    coords = geo_data['coordinates']
                    if isinstance(coords, dict) and 'coordinates' in coords:
                        lng, lat = coords['coordinates']
                        location = Point(lng, lat)
                elif 'place_id' in geo_data:
                    # Would need to fetch place details
                    pass
            
            # Extract hashtags and mentions
            entities = tweet_data.get('entities', {})
            hashtags = []
            mentions = []
            urls = []
            
            if 'hashtags' in entities:
                hashtags = [tag['tag'] for tag in entities['hashtags']]
            
            if 'mentions' in entities:
                mentions = [mention['username'] for mention in entities['mentions']]
            
            if 'urls' in entities:
                urls = [url['expanded_url'] for url in entities['urls']]
            
            # Prepare final tweet data
            processed_data = {
                'tweet_id': tweet_data['id'],
                'text': tweet_data['text'],
                'author_id': tweet_data['author_id'],
                'author_username': tweet_data.get('author', {}).get('username', ''),
                'author_display_name': tweet_data.get('author', {}).get('name', ''),
                'created_at': tweet_data['created_at'],
                'language': tweet_data['lang'],
                'location': location,
                'hashtags': hashtags,
                'mentions': mentions,
                'urls': urls,
                'public_metrics': tweet_data['public_metrics'],
                'is_verified': tweet_data.get('author', {}).get('verified', False),
                'raw_data': tweet_data
            }
            
            return processed_data
            
        except Exception as e:
            logger.error(f"Error processing tweet: {str(e)}")
            return None
    
    def save_tweets_to_db(self, tweets_data: List[Dict]) -> int:
        """Save tweets to database with ML analysis"""
        saved_count = 0
        
        for tweet_data in tweets_data:
            try:
                # Check if tweet already exists
                post_id = tweet_data['tweet_id']
                existing_post = SocialMediaPost.objects.filter(
                    platform=self.platform,
                    post_id=post_id
                ).first()
                
                if existing_post:
                    logger.debug(f"Tweet {post_id} already exists, skipping")
                    continue
                
                # Run ML analysis
                ml_results = self.ml_pipeline.process_text(tweet_data['text'])
                
                # Extract analysis results
                disaster_classification = ml_results.get('disaster_classification', {})
                sentiment_analysis = ml_results.get('sentiment_analysis', {})
                
                # Prepare post data
                post_data = {
                    'platform': self.platform,
                    'post_id': post_id,
                    'author_username': tweet_data['author_username'],
                    'author_display_name': tweet_data['author_display_name'],
                    'content': tweet_data['text'],
                    'original_language': tweet_data['language'],
                    'location': tweet_data['location'],
                    'posted_at': tweet_data['created_at'],
                    'hashtags': tweet_data['hashtags'],
                    'mentions': tweet_data['mentions'],
                    'is_verified_account': tweet_data['is_verified'],
                    'raw_data': tweet_data['raw_data'],
                    
                    # Engagement metrics
                    'likes': tweet_data['public_metrics'].get('like_count', 0),
                    'shares': tweet_data['public_metrics'].get('retweet_count', 0),
                    'comments': tweet_data['public_metrics'].get('reply_count', 0),
                    
                    # ML Analysis results
                    'is_disaster_related': disaster_classification.get('is_disaster', False),
                    'disaster_confidence': disaster_classification.get('confidence', 0.0),
                    'sentiment': sentiment_analysis.get('sentiment', 'neutral'),
                    'sentiment_confidence': sentiment_analysis.get('confidence', 0.0),
                    
                    # Calculate credibility score
                    'credibility_score': self._calculate_credibility_score(tweet_data),
                    
                    'last_analyzed': timezone.now()
                }
                
                # Create post
                SocialMediaPost.objects.create(**post_data)
                saved_count += 1
                
                logger.debug(f"Saved tweet {post_id} from @{tweet_data['author_username']}")
                
            except Exception as e:
                logger.error(f"Error saving tweet to database: {str(e)}")
                continue
        
        logger.info(f"Saved {saved_count} new tweets to database")
        return saved_count
    
    def _calculate_credibility_score(self, tweet_data: Dict) -> float:
        """Calculate credibility score for a tweet"""
        score = 0.5  # Base score
        
        # Verified account boost
        if tweet_data['is_verified']:
            score += 0.2
        
        # Author metrics (if available)
        author_metrics = tweet_data.get('raw_data', {}).get('author', {}).get('public_metrics', {})
        if author_metrics:
            followers_count = author_metrics.get('followers_count', 0)
            
            # Follower count boost (logarithmic scale)
            if followers_count > 1000000:  # 1M+
                score += 0.2
            elif followers_count > 100000:  # 100K+
                score += 0.15
            elif followers_count > 10000:  # 10K+
                score += 0.1
            elif followers_count > 1000:  # 1K+
                score += 0.05
        
        # Engagement boost
        public_metrics = tweet_data['public_metrics']
        total_engagement = (
            public_metrics.get('like_count', 0) +
            public_metrics.get('retweet_count', 0) +
            public_metrics.get('reply_count', 0)
        )
        
        if total_engagement > 100:
            score += 0.1
        elif total_engagement > 10:
            score += 0.05
        
        # Ensure score is within bounds
        return max(0.0, min(1.0, score))
    
    def fetch_ocean_hazard_tweets(self, max_results: int = 500) -> int:
        """Fetch tweets related to ocean hazards using predefined keywords"""
        
        # Ocean hazard related search terms
        ocean_keywords = [
            'tsunami OR "tidal wave"',
            'hurricane OR typhoon OR cyclone',
            '"storm surge" OR "coastal flooding"',
            '"ocean disaster" OR "marine emergency"',
            '"ship disaster" OR "maritime accident"',
            '"rogue wave" OR "dangerous waves"',
            '"oil spill" OR "marine pollution"',
            '"red tide" OR "algae bloom"',
            '"coastal erosion" OR "beach erosion"',
            'drowning OR "water rescue"'
        ]
        
        all_tweets = []
        total_saved = 0
        
        for keyword in ocean_keywords:
            try:
                logger.info(f"Searching for tweets with keyword: {keyword}")
                
                tweets = self.search_tweets(
                    query=f"{keyword} -is:retweet lang:en",  # Exclude retweets, English only
                    max_results=max_results // len(ocean_keywords)
                )
                
                if tweets:
                    saved_count = self.save_tweets_to_db(tweets)
                    total_saved += saved_count
                    all_tweets.extend(tweets)
                
                # Small delay between requests to be respectful
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Error fetching tweets for keyword '{keyword}': {str(e)}")
                continue
        
        logger.info(f"Fetched {len(all_tweets)} total tweets, saved {total_saved} new tweets")
        return total_saved
    
    def _log_api_usage(self, endpoint: str, data_count: int, success: bool):
        """Log API usage for monitoring"""
        try:
            now = timezone.now()
            
            usage, created = APIUsage.objects.get_or_create(
                platform=self.platform,
                endpoint=endpoint,
                date=now.date(),
                hour=now.hour,
                defaults={
                    'requests_made': 0,
                    'successful_requests': 0,
                    'failed_requests': 0,
                    'data_retrieved': 0
                }
            )
            
            usage.requests_made += 1
            if success:
                usage.successful_requests += 1
                usage.data_retrieved += data_count
            else:
                usage.failed_requests += 1
            
            usage.save()
            
        except Exception as e:
            logger.error(f"Error logging API usage: {str(e)}")
    
    def get_trending_topics(self, woeid: int = 1) -> List[Dict]:
        """Get trending topics from Twitter (requires API v1.1)"""
        trending_data = []
        
        try:
            trends = self.api.get_place_trends(woeid)
            
            for trend_group in trends:
                for trend in trend_group['trends']:
                    # Filter for potentially disaster-related trends
                    trend_name = trend['name'].lower()
                    if any(keyword in trend_name for keyword in [
                        'hurricane', 'tsunami', 'flood', 'storm', 'earthquake',
                        'disaster', 'emergency', 'evacuation', 'rescue'
                    ]):
                        trending_data.append({
                            'name': trend['name'],
                            'url': trend['url'],
                            'volume': trend.get('tweet_volume'),
                            'promoted': trend.get('promoted_content')
                        })
            
            logger.info(f"Retrieved {len(trending_data)} disaster-related trending topics")
            
        except Exception as e:
            logger.error(f"Error getting trending topics: {str(e)}")
        
        return trending_data


# Global Twitter client instance
_twitter_client = None

def get_twitter_client():
    """Get global Twitter client instance"""
    global _twitter_client
    if _twitter_client is None:
        _twitter_client = TwitterAPIClient()
    return _twitter_client
'''

with open("ocean_hazard_monitor/apps/social_media/twitter_api.py", "w") as f:
    f.write(twitter_api_content)

print("✅ Twitter API integration created")