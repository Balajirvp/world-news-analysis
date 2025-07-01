"""
Unit tests for Utils class.
"""
import pytest
from data_collection.utils import Utils


class TestUtils:
    """Test suite for Utils class."""
    
    @pytest.fixture
    def sample_data(self):
        """Sample posts and comments data for testing."""
        posts = [
            {
                'post_id': 'post1',
                'created_utc': 1749595657.0,
                'score': 100,
                'sentiment_score': 0.5
            }
        ]
        
        comments = [
            {
                'comment_id': 'comment1',
                'post_id': 'post1',
                'created_utc': 1749595757.0,  # 100 seconds after post
                'parent_id': 'post1',
                'score': 25,
                'author': 'user1',
                'sentiment_score': 0.8
            },
            {
                'comment_id': 'comment2',
                'post_id': 'post1',
                'created_utc': 1749595857.0,  # 200 seconds after post
                'parent_id': 'comment1',
                'score': 15,
                'author': 'user2',
                'sentiment_score': -0.3
            }
        ]
        
        return posts, comments
    
    def test_add_comment_metrics_basic_functionality(self, sample_data):
        """Test that add_comment_metrics adds all expected fields to posts."""
        posts, comments = sample_data
        
        result = Utils.add_comment_metrics(posts.copy(), comments.copy())
        post = result[0]
        
        # Basic counts
        assert post['comment_count'] == 2
        assert post['top_comment']['comment_id'] == 'comment1'  # Higher score
        assert post['unique_commenters'] == 2
        
        # Time-based metrics
        assert post['time_to_first_comment_min'] == pytest.approx(1.67, rel=1e-2)
        assert post['discussion_duration_min'] == pytest.approx(3.33, rel=1e-2)
        
        # Sentiment
        assert post['avg_comment_sentiment'] == pytest.approx(0.25, rel=1e-2)  # (0.8 + (-0.3)) / 2
        
        # Comment depth
        assert post['max_comment_depth'] == 2
        assert post['avg_comment_depth'] == 1.5
        
        # Time buckets (both comments in 0-1h bucket)
        assert post['comments_0_1h'] == 2
        assert post['comments_1_2h'] == 0
    
    def test_add_comment_metrics_edge_cases(self):
        """Test edge cases for add_comment_metrics."""
        # Empty comments
        posts = [{'post_id': 'post1', 'created_utc': 1749595657.0}]
        result = Utils.add_comment_metrics(posts, [])
        
        assert result[0]['comment_count'] == 0
        assert result[0]['top_comment'] is None
        assert result[0]['time_to_first_comment_min'] is None
        assert result[0]['unique_commenters'] == 0
        assert result[0]['avg_comment_sentiment'] is None
        assert result[0]['max_comment_depth'] == 0
        
        # Missing timestamps
        posts = [{'post_id': 'post1', 'created_utc': None}]
        comments = [{'comment_id': 'c1', 'post_id': 'post1', 'created_utc': 1749595757.0}]
        result = Utils.add_comment_metrics(posts, comments)
        
        assert result[0]['time_to_first_comment_min'] is None
        assert result[0]['discussion_duration_min'] is None
    
    def test_add_comment_metrics_time_buckets(self):
        """Test time bucket categorization."""
        posts = [{'post_id': 'post1', 'created_utc': 1749595657.0}]
        
        test_cases = [
            (1749595657.0 + 1800, 'comments_0_1h'),    # 30 minutes
            (1749595657.0 + 5400, 'comments_1_2h'),    # 1.5 hours
            (1749595657.0 + 28800, 'comments_6_12h'),  # 8 hours
            (1749595657.0 + 64800, 'comments_12_24h'), # 18 hours
            (1749595657.0 + 172800, 'comments_24h_plus') # 2 days
        ]
        
        for comment_time, expected_bucket in test_cases:
            comments = [{
                'comment_id': 'c1',
                'post_id': 'post1',
                'created_utc': comment_time,
                'parent_id': 'post1',
                'author': 'user1',
                'score': 10
            }]
            
            result = Utils.add_comment_metrics(posts.copy(), comments)
            assert result[0][expected_bucket] == 1
    
    def test_add_post_metrics_basic_functionality(self, sample_data):
        """Test that add_post_metrics adds all expected fields to comments."""
        posts, comments = sample_data
        posts[0]['num_comments'] = 5  # Add this field
        
        result = Utils.add_post_metrics(posts.copy(), comments.copy())
        
        comment1 = next(c for c in result if c['comment_id'] == 'comment1')
        comment2 = next(c for c in result if c['comment_id'] == 'comment2')
        
        # Time-based metrics for comment1
        assert comment1['time_from_post_in_minutes'] == pytest.approx(1.67, rel=1e-2)
        assert comment1['time_from_post_in_hours'] == pytest.approx(0.03, rel=1e-2)  # Rounded to 2 decimal places
        assert comment1['time_bucket'] == "0-1h"
        
        # Post metrics
        assert comment1['post_score'] == 100
        assert comment1['post_comment_count'] == 5
        assert comment1['post_sentiment'] == 0.5
        
        # Comment depth
        assert comment1['comment_depth'] == 1
        assert comment1['is_top_level'] is True
        assert comment2['comment_depth'] == 2
        assert comment2['is_top_level'] is False
    
    def test_add_post_metrics_edge_cases(self):
        """Test edge cases for add_post_metrics."""
        # Missing post
        comments = [{
            'comment_id': 'c1',
            'post_id': 'nonexistent',
            'created_utc': 1749595757.0,
            'parent_id': 'nonexistent'
        }]
        
        result = Utils.add_post_metrics([], comments)
        comment = result[0]
        
        assert comment['time_from_post_in_minutes'] is None
        assert comment['time_bucket'] is None
        assert comment['post_score'] is None
        
        # Missing timestamps
        posts = [{'post_id': 'post1', 'created_utc': None}]
        comments = [{'comment_id': 'c1', 'post_id': 'post1', 'created_utc': 1749595757.0}]
        
        result = Utils.add_post_metrics(posts, comments)
        assert result[0]['time_from_post_in_minutes'] is None
    
    def test_add_post_metrics_time_buckets(self):
        """Test time bucket assignment for comments."""
        posts = [{'post_id': 'post1', 'created_utc': 1749595657.0}]
        
        test_cases = [
            (1749595657.0 + 1800, "0-1h"),   # 30 minutes
            (1749595657.0 + 5400, "1-2h"),   # 1.5 hours
            (1749595657.0 + 28800, "6-12h"), # 8 hours
            (1749595657.0 + 172800, "24h+")  # 2 days
        ]
        
        for comment_time, expected_bucket in test_cases:
            comments = [{
                'comment_id': 'c1',
                'post_id': 'post1',
                'created_utc': comment_time,
                'parent_id': 'post1'
            }]
            
            result = Utils.add_post_metrics(posts, comments)
            assert result[0]['time_bucket'] == expected_bucket
    
    def test_comment_depth_calculation(self):
        """Test comment depth calculation for nested threads."""
        posts = [{'post_id': 'post1', 'created_utc': 1749595657.0}]
        
        comments = [
            {'comment_id': 'c1', 'post_id': 'post1', 'parent_id': 'post1', 'created_utc': 1749595757.0},
            {'comment_id': 'c2', 'post_id': 'post1', 'parent_id': 'c1', 'created_utc': 1749595857.0},
            {'comment_id': 'c3', 'post_id': 'post1', 'parent_id': 'c2', 'created_utc': 1749595957.0}
        ]
        
        # Test in add_comment_metrics
        posts_result = Utils.add_comment_metrics(posts.copy(), comments.copy())
        assert posts_result[0]['max_comment_depth'] == 3
        assert posts_result[0]['avg_comment_depth'] == 2.0  # (1+2+3)/3
        
        # Test in add_post_metrics
        comments_result = Utils.add_post_metrics(posts.copy(), comments.copy())
        depths = [c['comment_depth'] for c in comments_result]
        is_top_levels = [c['is_top_level'] for c in comments_result]
        
        assert depths == [1, 2, 3]
        assert is_top_levels == [True, False, False]
    
    def test_static_methods(self):
        """Test that methods can be called statically."""
        posts = [{'post_id': 'test', 'created_utc': 1749595657.0}]
        comments = [{'comment_id': 'test', 'post_id': 'test', 'created_utc': 1749595757.0, 'parent_id': 'test'}]
        
        # Should work without instance
        result1 = Utils.add_comment_metrics(posts.copy(), comments.copy())
        result2 = Utils.add_post_metrics(posts.copy(), comments.copy())
        
        assert len(result1) == 1
        assert len(result2) == 1
    
    def test_empty_inputs(self):
        """Test handling of empty inputs."""
        assert Utils.add_comment_metrics([], []) == []
        assert Utils.add_post_metrics([], []) == []