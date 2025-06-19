"""
Unit tests for RedditDataCollector class.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import praw
from data_collection.reddit_data_collector import RedditDataCollector
from tests.fixtures.mock_responses import MockResponses


class TestRedditDataCollector:
    """Test suite for RedditDataCollector."""
    
    @pytest.fixture
    def collector(self, mock_env_vars):
        """Create a RedditDataCollector instance for testing."""
        credentials = {
            'client_id': mock_env_vars['REDDIT_CLIENT_ID'],
            'client_secret': mock_env_vars['REDDIT_CLIENT_SECRET_ID'],
            'user_agent': mock_env_vars['REDDIT_USER_AGENT']
        }
        
        with patch('praw.Reddit') as mock_reddit:
            collector = RedditDataCollector(credentials)
            collector.reddit = mock_reddit
            return collector
    
    def test_init_with_valid_credentials(self, mock_env_vars):
        """Test initialization with valid credentials."""
        credentials = {
            'client_id': mock_env_vars['REDDIT_CLIENT_ID'],
            'client_secret': mock_env_vars['REDDIT_CLIENT_SECRET_ID'],
            'user_agent': mock_env_vars['REDDIT_USER_AGENT']
        }
        
        with patch('praw.Reddit') as mock_reddit:
            collector = RedditDataCollector(credentials)
            mock_reddit.assert_called_once_with(**credentials)
    
    def test_collect_posts_success(self, collector):
        """Test successful post collection."""
        # Setup mock data
        mock_author = Mock()
        mock_author.name = 'test_user'
        
        mock_post = Mock()
        mock_post.id = 'test123'
        mock_post.title = 'Test Post Title'
        mock_post.author = mock_author
        mock_post.created_utc = 1749595657.0
        mock_post.url = 'https://test.com'
        mock_post.num_comments = 10
        mock_post.score = 100
        mock_post.selftext = 'Test description'
        mock_post.upvote_ratio = 0.8
        mock_post.link_flair_text = 'News'
        
        mock_subreddit = Mock()
        mock_subreddit.top.return_value = [mock_post]
        
        collector.reddit.subreddit.return_value = mock_subreddit
        
        # Test collection
        posts, post_ids = collector.collect_posts('worldnews')
        
        # Assertions
        assert len(posts) == 1
        assert len(post_ids) == 1
        assert post_ids[0] == 'test123'
        
        expected_post = {
            'post_id': 'test123',
            'title': 'Test Post Title',
            'author': 'test_user',
            'created_utc': 1749595657.0,
            'url': 'https://test.com',
            'num_comments': 10,
            'score': 100,
            'description': 'Test description',
            'upvote_ratio': 0.8,
            'post_flair': 'News'
        }
        
        assert posts[0] == expected_post
        collector.reddit.subreddit.assert_called_once_with('worldnews')
        mock_subreddit.top.assert_called_once_with(time_filter="day")
    
    def test_collect_posts_no_author(self, collector):
        """Test post collection when author is None."""
        mock_post = Mock()
        mock_post.id = 'test123'
        mock_post.title = 'Test Post Title'
        mock_post.author = None  # Deleted user
        mock_post.created_utc = 1749595657.0
        mock_post.url = 'https://test.com'
        mock_post.num_comments = 10
        mock_post.score = 100
        mock_post.selftext = 'Test description'
        mock_post.upvote_ratio = 0.8
        mock_post.link_flair_text = 'News'
        
        mock_subreddit = Mock()
        mock_subreddit.top.return_value = [mock_post]
        collector.reddit.subreddit.return_value = mock_subreddit
        
        posts, post_ids = collector.collect_posts('worldnews')
        
        assert len(posts) == 1
        assert posts[0]['author'] is None
    
    def test_collect_posts_empty_subreddit(self, collector):
        """Test collection from empty subreddit."""
        mock_subreddit = Mock()
        mock_subreddit.top.return_value = []
        collector.reddit.subreddit.return_value = mock_subreddit
        
        posts, post_ids = collector.collect_posts('worldnews')
        
        assert len(posts) == 0
        assert len(post_ids) == 0
    
    def test_collect_comments_success(self, collector):
        """Test successful comment collection."""
        # Setup mock comment
        mock_author = Mock()
        mock_author.name = 'commenter'
        
        mock_comment = Mock()
        mock_comment.id = 'comment123'
        mock_comment.body = 'Test comment body'
        mock_comment.author = mock_author
        mock_comment.created_utc = 1749595757.0
        mock_comment.parent_id = 't3_test123'  # Reddit format with prefix
        mock_comment.score = 25
        
        # Mock submission
        mock_submission = Mock()
        mock_submission.comments.replace_more = Mock()
        mock_submission.comments.list.return_value = [mock_comment]
        
        collector.reddit.submission.return_value = mock_submission
        
        # Test collection
        comments = collector.collect_comments(['test123'])
        
        # Assertions
        assert len(comments) == 1
        expected_comment = {
            'comment_id': 'comment123',
            'post_id': 'test123',
            'body': 'Test comment body',
            'author': 'commenter',
            'created_utc': 1749595757.0,
            'parent_id': 'test123',  # Prefix should be removed
            'score': 25
        }
        
        assert comments[0] == expected_comment
        collector.reddit.submission.assert_called_once_with('test123')
        mock_submission.comments.replace_more.assert_called_once_with(limit=0)
    
    def test_collect_comments_no_author(self, collector):
        """Test comment collection when author is None."""
        mock_comment = Mock()
        mock_comment.id = 'comment123'
        mock_comment.body = 'Test comment body'
        mock_comment.author = None  # Deleted user
        mock_comment.created_utc = 1749595757.0
        mock_comment.parent_id = 't3_test123'
        mock_comment.score = 25
        
        mock_submission = Mock()
        mock_submission.comments.replace_more = Mock()
        mock_submission.comments.list.return_value = [mock_comment]
        
        collector.reddit.submission.return_value = mock_submission
        
        comments = collector.collect_comments(['test123'])
        
        assert len(comments) == 1
        assert comments[0]['author'] is None
    
    def test_collect_comments_multiple_posts(self, collector):
        """Test comment collection for multiple posts."""
        # Mock comments for different posts
        mock_comment1 = Mock()
        mock_comment1.id = 'comment1'
        mock_comment1.body = 'Comment 1'
        mock_comment1.author.name = 'user1'
        mock_comment1.created_utc = 1749595757.0
        mock_comment1.parent_id = 't3_post1'
        mock_comment1.score = 10
        
        mock_comment2 = Mock()
        mock_comment2.id = 'comment2'
        mock_comment2.body = 'Comment 2'
        mock_comment2.author.name = 'user2'
        mock_comment2.created_utc = 1749595857.0
        mock_comment2.parent_id = 't3_post2'
        mock_comment2.score = 20
        
        def mock_submission_side_effect(post_id):
            mock_submission = Mock()
            mock_submission.comments.replace_more = Mock()
            if post_id == 'post1':
                mock_submission.comments.list.return_value = [mock_comment1]
            else:
                mock_submission.comments.list.return_value = [mock_comment2]
            return mock_submission
        
        collector.reddit.submission.side_effect = mock_submission_side_effect
        
        comments = collector.collect_comments(['post1', 'post2'])
        
        assert len(comments) == 2
        assert comments[0]['post_id'] == 'post1'
        assert comments[1]['post_id'] == 'post2'
        assert collector.reddit.submission.call_count == 2
    
    def test_collect_comments_empty_post(self, collector):
        """Test comment collection for post with no comments."""
        mock_submission = Mock()
        mock_submission.comments.replace_more = Mock()
        mock_submission.comments.list.return_value = []
        
        collector.reddit.submission.return_value = mock_submission
        
        comments = collector.collect_comments(['test123'])
        
        assert len(comments) == 0
    
    def test_collect_comments_parent_id_edge_cases(self, collector):
        """Test parent_id handling edge cases."""
        # Test short parent_id
        mock_comment1 = Mock()
        mock_comment1.id = 'comment1'
        mock_comment1.body = 'Test'
        mock_comment1.author.name = 'user'
        mock_comment1.created_utc = 1749595757.0
        mock_comment1.parent_id = 'ab'  # Too short
        mock_comment1.score = 10
        
        # Test None parent_id
        mock_comment2 = Mock()
        mock_comment2.id = 'comment2'
        mock_comment2.body = 'Test'
        mock_comment2.author.name = 'user'
        mock_comment2.created_utc = 1749595757.0
        mock_comment2.parent_id = None
        mock_comment2.score = 10
        
        mock_submission = Mock()
        mock_submission.comments.replace_more = Mock()
        mock_submission.comments.list.return_value = [mock_comment1, mock_comment2]
        
        collector.reddit.submission.return_value = mock_submission
        
        comments = collector.collect_comments(['test123'])
        
        assert len(comments) == 2
        assert comments[0]['parent_id'] == 'ab'  # Unchanged if too short
        assert comments[1]['parent_id'] is None  # None remains None
    
    def test_collect_comments_invalid_objects(self, collector):
        """Test handling of invalid comment objects."""
        # Mock a MoreComments object or other non-comment
        mock_invalid = Mock(spec=[])  # No body attribute
        
        mock_valid_comment = Mock()
        mock_valid_comment.id = 'comment123'
        mock_valid_comment.body = 'Valid comment'
        mock_valid_comment.author.name = 'user'
        mock_valid_comment.created_utc = 1749595757.0
        mock_valid_comment.parent_id = 't3_test123'
        mock_valid_comment.score = 25
        
        mock_submission = Mock()
        mock_submission.comments.replace_more = Mock()
        mock_submission.comments.list.return_value = [mock_invalid, mock_valid_comment]
        
        collector.reddit.submission.return_value = mock_submission
        
        comments = collector.collect_comments(['test123'])
        
        # Should only get the valid comment
        assert len(comments) == 1
        assert comments[0]['comment_id'] == 'comment123'
    
    @patch('praw.Reddit')
    def test_reddit_api_exception_handling(self, mock_reddit_class):
        """Test handling of Reddit API exceptions."""
        # Mock Reddit to raise an exception
        mock_reddit_class.side_effect = Exception("API Error")
        
        credentials = {
            'client_id': 'test',
            'client_secret': 'test',
            'user_agent': 'test'
        }
        
        with pytest.raises(Exception, match="API Error"):
            RedditDataCollector(credentials)
