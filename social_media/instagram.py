# Create Instagram API Integration
instagram_api_content = '''
"""
Instagram API integration for ocean hazard monitoring
"""
import logging
import requests
import time
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from django.conf import settings
from django.utils import timezone
from django.contrib.gis.geos import Point

from .models import SocialMediaPlatform, SocialMediaPost, APIUsage
from apps.ml_models.training_utils import get_ml_pipeline

logger = logging.getLogger(__name__)


class InstagramAPIClient:
    """Instagram Basic Display API client for fetching ocean hazard related posts"""
    
    def __init__(self):
        self.platform = None
        self.ml_pipeline = get_ml_pipeline()
        self.base_url = "https://graph.instagram.com"
        self.access_token = settings.INSTAGRAM_ACCESS_TOKEN
        self._setup_platform()
    
    def _setup_platform(self):
        """Setup or get Instagram platform record"""
        try:
            self.platform, created = SocialMediaPlatform.objects.get_or_create(
                name='Instagram',
                defaults={
                    'api_endpoint': 'https://graph.instagram.com/',
                    'is_active': True,
                    'rate_limit': 200  # Instagram API rate limit
                }
            )
            if created:
                logger.info("Instagram platform record created")
            
        except Exception as e:
            logger.error(f"Failed to setup Instagram platform: {str(e)}")
            raise
    
    def _make_api_request(self, endpoint: str, params: Dict = None) -> Optional[Dict]:
        """Make authenticated request to Instagram API"""
        try:
            if params is None:
                params = {}
            
            params['access_token'] = self.access_token
            
            response = requests.get(f"{self.base_url}/{endpoint}", params=params)
            
            if response.status_code == 200:
                self._log_api_usage(endpoint, 1, True)
                return response.json()
            
            elif response.status_code == 429:  # Rate limited
                logger.warning(f"Instagram API rate limited for endpoint: {endpoint}")
                self._log_api_usage(endpoint, 0, False, rate_limited=True)
                return None
            
            else:
                logger.error(f"Instagram API error {response.status_code}: {response.text}")
                self._log_api_usage(endpoint, 0, False)
                return None
                
        except Exception as e:
            logger.error(f"Error making Instagram API request: {str(e)}")
            self._log_api_usage(endpoint, 0, False)
            return None
    
    def get_user_profile(self, user_id: str = 'me') -> Optional[Dict]:
        """Get user profile information"""
        endpoint = f"{user_id}"
        params = {
            'fields': 'id,username,account_type,media_count'
        }
        
        return self._make_api_request(endpoint, params)
    
    def get_user_media(self, user_id: str = 'me', limit: int = 25) -> List[Dict]:
        """Get user's media posts"""
        media_data = []
        
        try:
            endpoint = f"{user_id}/media"
            params = {
                'fields': 'id,caption,media_type,media_url,permalink,thumbnail_url,timestamp',
                'limit': min(limit, 25)  # Instagram API limit
            }
            
            response = self._make_api_request(endpoint, params)
            
            if response and 'data' in response:
                for media in response['data']:
                    media_info = self._process_media_item(media)
                    if media_info:
                        media_data.append(media_info)
                
                logger.info(f"Retrieved {len(media_data)} media items for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error getting user media: {str(e)}")
        
        return media_data
    
    def _process_media_item(self, media: Dict) -> Optional[Dict]:
        """Process individual media item"""
        try:
            # Extract basic media information
            media_data = {
                'id': media['id'],
                'caption': media.get('caption', ''),
                'media_type': media.get('media_type', 'IMAGE'),
                'media_url': media.get('media_url', ''),
                'permalink': media.get('permalink', ''),
                'thumbnail_url': media.get('thumbnail_url', ''),
                'timestamp': media.get('timestamp', ''),
            }
            
            # Get additional insights if available (requires Instagram Business API)
            insights = self.get_media_insights(media['id'])
            if insights:
                media_data['insights'] = insights
            
            return media_data
            
        except Exception as e:
            logger.error(f"Error processing media item: {str(e)}")
            return None
    
    def get_media_insights(self, media_id: str) -> Optional[Dict]:
        """Get insights for a specific media post (Business accounts only)"""
        try:
            endpoint = f"{media_id}/insights"
            params = {
                'metric': 'engagement,impressions,reach,saves'
            }
            
            response = self._make_api_request(endpoint, params)
            
            if response and 'data' in response:
                insights = {}
                for metric in response['data']:
                    insights[metric['name']] = metric['values'][0]['value']
                return insights
            
        except Exception as e:
            logger.debug(f"Could not get insights for media {media_id}: {str(e)}")
            # This is expected for non-business accounts
            return None
    
    def search_hashtags(self, hashtag: str) -> List[Dict]:
        """Search for hashtag information (requires Instagram Business API)"""
        hashtag_data = []
        
        try:
            # This endpoint requires Business Discovery which has limited access
            # For basic access, we'll focus on user's own content analysis
            logger.info(f"Hashtag search for '{hashtag}' requires Business API access")
            
        except Exception as e:
            logger.error(f"Error searching hashtags: {str(e)}")
        
        return hashtag_data
    
    def analyze_ocean_hazard_content(self, user_ids: List[str] = None) -> int:
        """Analyze posts from specified users for ocean hazard content"""
        if not user_ids:
            user_ids = ['me']  # Analyze own content by default
        
        total_analyzed = 0
        
        for user_id in user_ids:
            try:
                logger.info(f"Analyzing content for Instagram user: {user_id}")
                
                # Get user profile
                profile = self.get_user_profile(user_id)
                if not profile:
                    logger.warning(f"Could not get profile for user {user_id}")
                    continue
                
                # Get user media
                media_items = self.get_user_media(user_id, limit=50)
                
                for media in media_items:
                    if self._analyze_and_save_media(media, profile):
                        total_analyzed += 1
                
                # Small delay between users
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"Error analyzing content for user {user_id}: {str(e)}")
                continue
        
        logger.info(f"Analyzed {total_analyzed} Instagram posts")
        return total_analyzed
    
    def _analyze_and_save_media(self, media: Dict, profile: Dict) -> bool:
        """Analyze media item and save if ocean hazard related"""
        try:
            # Check if post already exists
            post_id = media['id']
            existing_post = SocialMediaPost.objects.filter(
                platform=self.platform,
                post_id=post_id
            ).first()
            
            if existing_post:
                logger.debug(f"Instagram post {post_id} already exists, skipping")
                return False
            
            # Get caption text for analysis
            caption = media.get('caption', '')
            if not caption:
                logger.debug(f"Instagram post {post_id} has no caption, skipping")
                return False
            
            # Run ML analysis on caption
            ml_results = self.ml_pipeline.process_text(caption)
            disaster_classification = ml_results.get('disaster_classification', {})
            sentiment_analysis = ml_results.get('sentiment_analysis', {})
            
            # Only save if disaster-related with reasonable confidence
            is_disaster_related = disaster_classification.get('is_disaster', False)
            disaster_confidence = disaster_classification.get('confidence', 0.0)
            
            if not is_disaster_related or disaster_confidence < 0.3:
                logger.debug(f"Instagram post {post_id} not disaster-related enough, skipping")
                return False
            
            # Extract hashtags from caption
            hashtags = self._extract_hashtags(caption)
            mentions = self._extract_mentions(caption)
            
            # Parse timestamp
            posted_at = datetime.fromisoformat(
                media['timestamp'].replace('Z', '+00:00')
            ) if media.get('timestamp') else timezone.now()
            
            # Determine media types
            media_types = []
            media_urls = []
            
            if media.get('media_url'):
                media_urls.append(media['media_url'])
                media_types.append(media.get('media_type', 'IMAGE').lower())
            
            if media.get('thumbnail_url'):
                media_urls.append(media['thumbnail_url'])
            
            # Get engagement metrics from insights
            insights = media.get('insights', {})
            
            # Prepare post data
            post_data = {
                'platform': self.platform,
                'post_id': post_id,
                'author_username': profile.get('username', ''),
                'author_display_name': profile.get('username', ''),
                'content': caption,
                'original_language': 'en',  # Instagram API doesn't provide language detection
                'posted_at': posted_at,
                'hashtags': hashtags,
                'mentions': mentions,
                'has_media': len(media_urls) > 0,
                'media_urls': media_urls,
                'media_types': media_types,
                'raw_data': media,
                
                # Engagement metrics from insights
                'likes': insights.get('engagement', 0),
                'shares': 0,  # Instagram doesn't provide shares in basic API
                'comments': 0,  # Would need additional API calls
                'views': insights.get('impressions', 0),
                
                # Account information
                'is_verified_account': profile.get('account_type') == 'BUSINESS',
                'account_followers': 0,  # Not available in basic API
                
                # ML Analysis results
                'is_disaster_related': is_disaster_related,
                'disaster_confidence': disaster_confidence,
                'sentiment': sentiment_analysis.get('sentiment', 'neutral'),
                'sentiment_confidence': sentiment_analysis.get('confidence', 0.0),
                
                # Credibility score (simplified for Instagram)
                'credibility_score': self._calculate_credibility_score(profile, insights),
                
                'last_analyzed': timezone.now()
            }
            
            # Create post
            SocialMediaPost.objects.create(**post_data)
            
            logger.info(f"Saved Instagram post {post_id} from @{profile.get('username')}")
            return True
            
        except Exception as e:
            logger.error(f"Error analyzing and saving media: {str(e)}")
            return False
    
    def _extract_hashtags(self, text: str) -> List[str]:
        """Extract hashtags from text"""
        import re
        hashtags = re.findall(r'#(\w+)', text)
        return hashtags
    
    def _extract_mentions(self, text: str) -> List[str]:
        """Extract mentions from text"""
        import re
        mentions = re.findall(r'@(\w+)', text)
        return mentions
    
    def _calculate_credibility_score(self, profile: Dict, insights: Dict) -> float:
        """Calculate credibility score for Instagram post"""
        score = 0.5  # Base score
        
        # Business account boost
        if profile.get('account_type') == 'BUSINESS':
            score += 0.2
        
        # Engagement boost
        engagement = insights.get('engagement', 0)
        if engagement > 1000:
            score += 0.2
        elif engagement > 100:
            score += 0.15
        elif engagement > 10:
            score += 0.1
        
        # Reach/impressions boost
        reach = insights.get('reach', 0) or insights.get('impressions', 0)
        if reach > 10000:
            score += 0.15
        elif reach > 1000:
            score += 0.1
        
        # Ensure score is within bounds
        return max(0.0, min(1.0, score))
    
    def monitor_ocean_keywords(self) -> int:
        """Monitor posts with ocean hazard keywords (limited with basic API)"""
        # With Instagram Basic Display API, we can only analyze user's own content
        # For broader monitoring, would need Instagram Business API with proper permissions
        
        logger.info("Starting Instagram ocean keyword monitoring")
        
        # Analyze current user's content
        analyzed_count = self.analyze_ocean_hazard_content()
        
        logger.info(f"Instagram monitoring completed, analyzed {analyzed_count} posts")
        return analyzed_count
    
    def _log_api_usage(self, endpoint: str, data_count: int, success: bool, rate_limited: bool = False):
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
                    'rate_limited': 0,
                    'data_retrieved': 0
                }
            )
            
            usage.requests_made += 1
            if success:
                usage.successful_requests += 1
                usage.data_retrieved += data_count
            elif rate_limited:
                usage.rate_limited += 1
            else:
                usage.failed_requests += 1
            
            usage.save()
            
        except Exception as e:
            logger.error(f"Error logging Instagram API usage: {str(e)}")
    
    def get_api_status(self) -> Dict[str, any]:
        """Get current API status and usage statistics"""
        try:
            # Make a simple test request
            profile = self.get_user_profile()
            
            if profile:
                return {
                    'status': 'active',
                    'user_id': profile.get('id'),
                    'username': profile.get('username'),
                    'account_type': profile.get('account_type'),
                    'media_count': profile.get('media_count', 0)
                }
            else:
                return {
                    'status': 'error',
                    'message': 'Could not connect to Instagram API'
                }
                
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)
            }


# Global Instagram client instance
_instagram_client = None

def get_instagram_client():
    """Get global Instagram client instance"""
    global _instagram_client
    if _instagram_client is None:
        _instagram_client = InstagramAPIClient()
    return _instagram_client
'''

with open("ocean_hazard_monitor/apps/social_media/instagram_api.py", "w") as f:
    f.write(instagram_api_content)

print("✅ Instagram API integration created")