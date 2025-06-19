"""
Pytest configuration and shared fixtures for Reddit WorldNews Pipeline tests.
"""
import pytest
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
import sys

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

@pytest.fixture
def mock_env_vars():
    """Mock environment variables for testing."""
    env_vars = {
        'REDDIT_CLIENT_ID': 'test_client_id',
        'REDDIT_CLIENT_SECRET_ID': 'test_client_secret',
        'REDDIT_USER_AGENT': 'test_user_agent',
        'SUBREDDIT': 'worldnews',
        'NER_MODEL': 'dbmdz/bert-large-cased-finetuned-conll03-english',
        'SENTIMENT_MODEL': 'cardiffnlp/twitter-roberta-base-sentiment-latest'
    }
    with patch.dict(os.environ, env_vars, clear=False), \
        patch('os.getenv', side_effect=lambda key, default=None: env_vars.get(key, default)):
        yield env_vars

@pytest.fixture
def temp_data_dir():
    """Create a temporary directory for test data."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)

@pytest.fixture
def sample_reddit_post():
    """Sample Reddit post data for testing."""
    return {
        'post_id': 'test123',
        'title': 'Breaking: Major diplomatic talks between US and France',
        'author': 'test_user',
        'created_utc': 1749595657.0,
        'url': 'https://www.reuters.com/test-article',
        'num_comments': 150,
        'score': 1500,
        'description': 'A major diplomatic breakthrough happened today...',
        'upvote_ratio': 0.85,
        'post_flair': 'Politics'
    }

@pytest.fixture
def sample_reddit_comment():
    """Sample Reddit comment data for testing."""
    return {
        'comment_id': 'comment123',
        'post_id': 'test123',
        'body': 'This is great news for international relations between America and France.',
        'author': 'comment_user',
        'created_utc': 1749595757.0,
        'parent_id': 'test123',
        'score': 50
    }

@pytest.fixture
def sample_enriched_post():
    """Sample enriched post with NLP features."""
    return {
        'post_id': 'test123',
        'title': 'Breaking: Major diplomatic talks between US and France',
        'author': 'test_user',
        'created_utc': 1749595657.0,
        'url': 'https://www.reuters.com/test-article',
        'num_comments': 150,
        'score': 1500,
        'description': 'A major diplomatic breakthrough happened today...',
        'upvote_ratio': 0.85,
        'post_flair': 'Politics',
        'domain': 'reuters',
        'title_sentiment_score': 0.5,
        'title_sentiment_category': 'positive',
        'description_sentiment_score': 0.3,
        'description_sentiment_category': 'positive',
        'persons_mentioned': ['John Smith', 'Jane Doe'],
        'locations_mentioned': ['United States', 'France'],
        'organizations_mentioned': ['NATO', 'EU'],
        'misc_entities_mentioned': ['Agreement']
    }

@pytest.fixture
def sample_posts_list():
    """Sample list of posts for testing."""
    return [
        {
            'post_id': 'post1',
            'title': 'US-France diplomatic talks',
            'author': 'user1',
            'created_utc': 1749595657.0,
            'score': 100,
            'num_comments': 50
        },
        {
            'post_id': 'post2', 
            'title': 'Breaking: China trade news',
            'author': 'user2',
            'created_utc': 1749595757.0,
            'score': 200,
            'num_comments': 75
        }
    ]

@pytest.fixture
def sample_comments_list():
    """Sample list of comments for testing."""
    return [
        {
            'comment_id': 'comment1',
            'post_id': 'post1',
            'body': 'Great news!',
            'author': 'commenter1',
            'created_utc': 1749595767.0,
            'parent_id': 'post1',
            'score': 10
        },
        {
            'comment_id': 'comment2',
            'post_id': 'post1', 
            'body': 'I disagree with this policy.',
            'author': 'commenter2',
            'created_utc': 1749595777.0,
            'parent_id': 'comment1',
            'score': 5
        }
    ]

@pytest.fixture(autouse=True)
def cleanup_temp_files():
    """Cleanup any temporary files created during tests."""
    yield
    # Cleanup code can go here if needed
    pass