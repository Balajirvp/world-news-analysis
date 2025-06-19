"""
Integration tests for the main pipeline.
"""
import pytest
from unittest.mock import Mock, patch, mock_open
import json
import os
from pathlib import Path

# Import main module
import main


class TestMainPipeline:
    """Integration test suite for the main pipeline."""
    
    @pytest.fixture
    def mock_env_vars(self):
        """Mock environment variables for testing."""
        env_vars = {
            'REDDIT_CLIENT_ID': 'test_client_id',
            'REDDIT_CLIENT_SECRET_ID': 'test_client_secret',
            'REDDIT_USER_AGENT': 'test_user_agent',
            'SUBREDDIT': 'worldnews',
            'NER_MODEL': 'test_ner_model',
            'SENTIMENT_MODEL': 'test_sentiment_model'
        }
        
        with patch.dict(os.environ, env_vars, clear=False):
            yield env_vars
    
    @pytest.fixture
    def sample_reddit_data(self):
        """Sample Reddit data for testing."""
        posts = [
            {
                'post_id': 'test_post_1',
                'title': 'Test Post 1',
                'url': 'https://test1.com',
                'created_utc': 1749595657.0,
                'score': 100
            }
        ]
        
        comments = [
            {
                'comment_id': 'test_comment_1',
                'post_id': 'test_post_1',
                'body': 'Test comment 1',
                'created_utc': 1749595757.0,
                'score': 25,
                'author': 'user1',
                'parent_id': 'test_post_1'
            }
        ]
        
        return posts, comments
    
    @patch('main.ElasticsearchClient')
    @patch('main.Utils')
    @patch('main.WikipediaPersonProcessor')
    @patch('main.LocationProcessor')
    @patch('main.RedditDataEnricher')
    @patch('main.RedditDataCollector')
    @patch('main.load_dotenv')
    def test_main_pipeline_success_flow(self, mock_load_dotenv, mock_reddit_class,
                                       mock_enricher_class, mock_location_class,
                                       mock_person_class, mock_utils_class,
                                       mock_es_class, mock_env_vars, sample_reddit_data):
        """Test successful execution of the complete main pipeline."""
        posts, comments = sample_reddit_data
        
        # Setup Reddit collector
        mock_reddit_collector = Mock()
        mock_reddit_collector.collect_posts.return_value = (posts, ['test_post_1'])
        mock_reddit_collector.collect_comments.return_value = comments
        mock_reddit_class.return_value = mock_reddit_collector
        
        # Setup NLP enricher
        mock_enricher = Mock()
        mock_enricher.enrich_post.side_effect = lambda post: {
            **post, 
            'domain': 'test.com',
            'sentiment_score': 0.5,
            'persons_mentioned': ['Test Person'],
            'locations_mentioned': ['Test Location']
        }
        mock_enricher.enrich_comment.side_effect = lambda comment: {
            **comment, 
            'sentiment_score': 0.3
        }
        mock_enricher_class.return_value = mock_enricher
        
        # Setup location processor
        mock_location_processor = Mock()
        mock_location_processor.process_posts.side_effect = lambda posts: [
            {**post, 'locations_mentioned_updated': ['United States']} for post in posts
        ]
        mock_location_class.return_value = mock_location_processor
        
        # Setup person processor
        mock_person_processor = Mock()
        mock_person_processor.update_persons_mentioned.side_effect = lambda posts: [
            {**post, 'persons_mentioned_updated': ['Donald Trump']} for post in posts
        ]
        mock_person_class.return_value = mock_person_processor
        
        # Setup utils
        mock_utils = Mock()
        mock_utils.add_comment_metrics.side_effect = lambda posts, comments: posts
        mock_utils.add_post_metrics.side_effect = lambda posts, comments: comments
        mock_utils_class.return_value = mock_utils
        
        # Setup Elasticsearch client
        mock_es_client = Mock()
        mock_es_client.is_connected.return_value = True
        mock_es_client.create_indices.return_value = ('posts_index', 'comments_index')
        mock_es_class.return_value = mock_es_client
        
        # Mock file and directory operations
        with patch('pathlib.Path.mkdir'), \
             patch('builtins.open', mock_open()), \
             patch('json.dump') as mock_json_dump:
            
            main.main()
        
        # Verify pipeline steps were executed in correct order
        mock_reddit_collector.collect_posts.assert_called_once_with('worldnews')
        mock_reddit_collector.collect_comments.assert_called_once_with(['test_post_1'])
        
        # Verify enrichment steps
        assert mock_enricher.enrich_post.call_count == 1
        assert mock_enricher.enrich_comment.call_count == 1
        
        # Verify processing steps
        mock_location_processor.process_posts.assert_called_once()
        mock_person_processor.update_persons_mentioned.assert_called_once()
        
        # Verify metrics building
        mock_utils.add_comment_metrics.assert_called_once()
        mock_utils.add_post_metrics.assert_called_once()
        
        # Verify file operations - should have 2 JSON dumps (posts and comments)
        assert mock_json_dump.call_count == 2, f"Expected 2 JSON dumps, got {mock_json_dump.call_count}"
        
        # Verify Elasticsearch operations
        mock_es_client.is_connected.assert_called_once()
        mock_es_client.create_indices.assert_called_once()
        assert mock_es_client.load_from_file.call_count == 2  # posts and comments
    
    @patch('main.ElasticsearchClient')
    @patch('main.Utils')
    @patch('main.WikipediaPersonProcessor')
    @patch('main.LocationProcessor')
    @patch('main.RedditDataEnricher')
    @patch('main.RedditDataCollector')
    @patch('main.load_dotenv')
    def test_main_pipeline_no_posts_collected(self, mock_load_dotenv, mock_reddit_class,
                                             mock_enricher_class, mock_location_class,
                                             mock_person_class, mock_utils_class,
                                             mock_es_class, mock_env_vars):
        """Test pipeline behavior when no posts are collected."""
        
        # Setup Reddit collector to return no posts
        mock_reddit_collector = Mock()
        mock_reddit_collector.collect_posts.return_value = ([], [])  # No posts, no post_ids
        mock_reddit_class.return_value = mock_reddit_collector
        
        # Setup other components
        mock_enricher = Mock()
        mock_enricher.enrich_post.side_effect = lambda x: x
        mock_enricher_class.return_value = mock_enricher
        
        mock_location_processor = Mock()
        mock_location_processor.process_posts.side_effect = lambda x: x
        mock_location_class.return_value = mock_location_processor
        
        mock_person_processor = Mock()
        mock_person_processor.update_persons_mentioned.side_effect = lambda x: x
        mock_person_class.return_value = mock_person_processor
        
        mock_utils = Mock()
        mock_utils.add_comment_metrics.side_effect = lambda posts, comments: posts
        mock_utils.add_post_metrics.side_effect = lambda posts, comments: comments
        mock_utils_class.return_value = mock_utils
        
        mock_es_client = Mock()
        mock_es_client.is_connected.return_value = True
        mock_es_client.create_indices.return_value = ('posts_index', 'comments_index')
        mock_es_class.return_value = mock_es_client
        
        with patch('pathlib.Path.mkdir'), \
             patch('builtins.open', mock_open()), \
             patch('json.dump') as mock_json_dump:
            
            main.main()
        
        # Verify posts collection was attempted
        mock_reddit_collector.collect_posts.assert_called_once_with('worldnews')
        
        # Comments collection should not be called when no posts
        mock_reddit_collector.collect_comments.assert_not_called()
        
        # Should still save empty data files
        assert mock_json_dump.call_count == 2  # posts and comments files
        
        # Should still proceed with Elasticsearch operations
        mock_es_client.is_connected.assert_called_once()
        mock_es_client.create_indices.assert_called_once()
        assert mock_es_client.load_from_file.call_count == 2
    
    @patch('main.ElasticsearchClient')
    @patch('main.Utils')
    @patch('main.WikipediaPersonProcessor')
    @patch('main.LocationProcessor')
    @patch('main.RedditDataEnricher')
    @patch('main.RedditDataCollector')
    @patch('main.load_dotenv')
    def test_main_pipeline_elasticsearch_connection_failure(self, mock_load_dotenv, 
                                                           mock_reddit_class, mock_enricher_class,
                                                           mock_location_class, mock_person_class,
                                                           mock_utils_class, mock_es_class,
                                                           mock_env_vars, sample_reddit_data):
        """Test pipeline behavior when Elasticsearch connection fails."""
        posts, comments = sample_reddit_data
        
        # Setup successful data collection
        mock_reddit_collector = Mock()
        mock_reddit_collector.collect_posts.return_value = (posts, ['test_post_1'])
        mock_reddit_collector.collect_comments.return_value = comments
        mock_reddit_class.return_value = mock_reddit_collector
        
        # Setup other components to work
        mock_enricher = Mock()
        mock_enricher.enrich_post.side_effect = lambda x: x
        mock_enricher.enrich_comment.side_effect = lambda x: x
        mock_enricher_class.return_value = mock_enricher
        
        mock_location_processor = Mock()
        mock_location_processor.process_posts.side_effect = lambda x: x
        mock_location_class.return_value = mock_location_processor
        
        mock_person_processor = Mock()
        mock_person_processor.update_persons_mentioned.side_effect = lambda x: x
        mock_person_class.return_value = mock_person_processor
        
        mock_utils = Mock()
        mock_utils.add_comment_metrics.side_effect = lambda posts, comments: posts
        mock_utils.add_post_metrics.side_effect = lambda posts, comments: comments
        mock_utils_class.return_value = mock_utils
        
        # Setup Elasticsearch to fail connection
        mock_es_client = Mock()
        mock_es_client.is_connected.return_value = False
        mock_es_class.return_value = mock_es_client
        
        with patch('pathlib.Path.mkdir'), \
             patch('builtins.open', mock_open()), \
             patch('json.dump'):
            
            main.main()
        
        # Verify connection check was made
        mock_es_client.is_connected.assert_called_once()
        
        # But no indices should be created or data loaded
        mock_es_client.create_indices.assert_not_called()
        mock_es_client.load_from_file.assert_not_called()
    
    @patch('main.ElasticsearchClient')
    @patch('main.Utils')
    @patch('main.WikipediaPersonProcessor')
    @patch('main.LocationProcessor')
    @patch('main.RedditDataEnricher')
    @patch('main.RedditDataCollector')
    @patch('main.load_dotenv')
    def test_main_pipeline_environment_variables(self, mock_load_dotenv, mock_reddit_class,
                                                mock_enricher_class, mock_location_class,
                                                mock_person_class, mock_utils_class,
                                                mock_es_class, mock_env_vars, sample_reddit_data):
        """Test that pipeline uses environment variables correctly."""
        posts, comments = sample_reddit_data
        
        # Setup working mocks
        mock_reddit_collector = Mock()
        mock_reddit_collector.collect_posts.return_value = (posts, ['test_post_1'])
        mock_reddit_collector.collect_comments.return_value = comments
        mock_reddit_class.return_value = mock_reddit_collector
        
        mock_enricher = Mock()
        mock_enricher.enrich_post.side_effect = lambda x: x
        mock_enricher.enrich_comment.side_effect = lambda x: x
        mock_enricher_class.return_value = mock_enricher
        
        mock_location_processor = Mock()
        mock_location_processor.process_posts.side_effect = lambda x: x
        mock_location_class.return_value = mock_location_processor
        
        mock_person_processor = Mock()
        mock_person_processor.update_persons_mentioned.side_effect = lambda x: x
        mock_person_class.return_value = mock_person_processor
        
        mock_utils = Mock()
        mock_utils.add_comment_metrics.side_effect = lambda posts, comments: posts
        mock_utils.add_post_metrics.side_effect = lambda posts, comments: comments
        mock_utils_class.return_value = mock_utils
        
        mock_es_client = Mock()
        mock_es_client.is_connected.return_value = False  # Avoid ES operations
        mock_es_class.return_value = mock_es_client
        
        with patch('pathlib.Path.mkdir'), \
             patch('builtins.open', mock_open()), \
             patch('json.dump'):
            
            main.main()
        
        # Verify environment variables were loaded
        mock_load_dotenv.assert_called_once()
        
        # Verify Reddit collector was initialized with correct credentials
        mock_reddit_class.assert_called_once()
        call_args = mock_reddit_class.call_args[0][0]  # First positional argument
        
        assert call_args['client_id'] == 'test_client_id'
        assert call_args['client_secret'] == 'test_client_secret'
        assert call_args['user_agent'] == 'test_user_agent'
        
        # Verify enricher was initialized with correct models
        mock_enricher_class.assert_called_once_with('test_ner_model', 'test_sentiment_model')
        
        # Verify subreddit was used correctly
        mock_reddit_collector.collect_posts.assert_called_once_with('worldnews')
    
    @patch('main.datetime')
    @patch('main.ElasticsearchClient')
    @patch('main.Utils')
    @patch('main.WikipediaPersonProcessor')
    @patch('main.LocationProcessor')
    @patch('main.RedditDataEnricher')
    @patch('main.RedditDataCollector')
    @patch('main.load_dotenv')
    def test_main_pipeline_date_handling(self, mock_load_dotenv, mock_reddit_class,
                                        mock_enricher_class, mock_location_class,
                                        mock_person_class, mock_utils_class,
                                        mock_es_class, mock_datetime, mock_env_vars,
                                        sample_reddit_data):
        """Test that pipeline handles dates correctly for file naming and indexing."""
        posts, comments = sample_reddit_data
        
        # Mock datetime
        mock_now = Mock()
        mock_now.strftime.side_effect = lambda fmt: {
            '%Y-%m-%d %H:%M:%S': '2025-06-18 14:30:00',
            '%Y-%m-%d': '2025-06-18'
        }[fmt]
        mock_datetime.now.return_value = mock_now
        
        # Setup working components
        mock_reddit_collector = Mock()
        mock_reddit_collector.collect_posts.return_value = (posts, ['test_post_1'])
        mock_reddit_collector.collect_comments.return_value = comments
        mock_reddit_class.return_value = mock_reddit_collector
        
        mock_enricher = Mock()
        mock_enricher.enrich_post.side_effect = lambda x: x
        mock_enricher.enrich_comment.side_effect = lambda x: x
        mock_enricher_class.return_value = mock_enricher
        
        mock_location_processor = Mock()
        mock_location_processor.process_posts.side_effect = lambda x: x
        mock_location_class.return_value = mock_location_processor
        
        mock_person_processor = Mock()
        mock_person_processor.update_persons_mentioned.side_effect = lambda x: x
        mock_person_class.return_value = mock_person_processor
        
        mock_utils = Mock()
        mock_utils.add_comment_metrics.side_effect = lambda posts, comments: posts
        mock_utils.add_post_metrics.side_effect = lambda posts, comments: comments
        mock_utils_class.return_value = mock_utils
        
        mock_es_client = Mock()
        mock_es_client.is_connected.return_value = True
        mock_es_client.create_indices.return_value = ('posts_index', 'comments_index')
        mock_es_class.return_value = mock_es_client
        
        with patch('pathlib.Path.mkdir'), \
             patch('builtins.open', mock_open()) as mock_file, \
             patch('json.dump'):
            
            main.main()
        
        # Verify date-based file names were used
        file_calls = [str(call[0][0]) for call in mock_file.call_args_list]
        
        # Check for posts and comments files with date
        posts_file_found = any('posts_2025-06-18.json' in call for call in file_calls)
        comments_file_found = any('comments_2025-06-18.json' in call for call in file_calls)
        
        assert posts_file_found, f"Posts file not found in calls: {file_calls}"
        assert comments_file_found, f"Comments file not found in calls: {file_calls}"
        
        # Verify Elasticsearch index creation with correct date format
        mock_es_client.create_indices.assert_called_once_with('2025.06.18')
    
    @patch('main.ElasticsearchClient')
    @patch('main.Utils')
    @patch('main.WikipediaPersonProcessor')
    @patch('main.LocationProcessor')
    @patch('main.RedditDataEnricher')
    @patch('main.RedditDataCollector')
    @patch('main.load_dotenv')
    def test_main_pipeline_data_transformation_flow(self, mock_load_dotenv, mock_reddit_class,
                                                   mock_enricher_class, mock_location_class,
                                                   mock_person_class, mock_utils_class,
                                                   mock_es_class, mock_env_vars, sample_reddit_data):
        """Test that data flows correctly through all transformation steps."""
        posts, comments = sample_reddit_data
        
        # Track data transformations
        transformation_calls = []
        
        def track_call(stage, data):
            transformation_calls.append((stage, len(data)))
            return data
        
        # Setup Reddit collector
        mock_reddit_collector = Mock()
        mock_reddit_collector.collect_posts.return_value = (list(posts), ['test_post_1'])
        mock_reddit_collector.collect_comments.return_value = list(comments)
        mock_reddit_class.return_value = mock_reddit_collector
        
        # Setup enricher with tracking
        mock_enricher = Mock()
        mock_enricher.enrich_post.side_effect = lambda post: {**post, 'enriched': True}
        mock_enricher.enrich_comment.side_effect = lambda comment: {**comment, 'enriched': True}
        mock_enricher_class.return_value = mock_enricher
        
        # Setup location processor with tracking
        mock_location_processor = Mock()
        def process_posts_tracked(posts):
            result = [{**post, 'location_processed': True} for post in posts]
            track_call('location_processed', result)
            return result
        mock_location_processor.process_posts.side_effect = process_posts_tracked
        mock_location_class.return_value = mock_location_processor
        
        # Setup person processor with tracking
        mock_person_processor = Mock()
        def update_persons_tracked(posts):
            result = [{**post, 'person_processed': True} for post in posts]
            track_call('person_processed', result)
            return result
        mock_person_processor.update_persons_mentioned.side_effect = update_persons_tracked
        mock_person_class.return_value = mock_person_processor
        
        # Setup utils with tracking
        mock_utils = Mock()
        def add_comment_metrics_tracked(posts, comments):
            result = [{**post, 'comment_metrics_added': True} for post in posts]
            track_call('comment_metrics_added', result)
            return result
        
        def add_post_metrics_tracked(posts, comments):
            result = [{**comment, 'post_metrics_added': True} for comment in comments]
            track_call('post_metrics_added', result)
            return result
        
        mock_utils.add_comment_metrics.side_effect = add_comment_metrics_tracked
        mock_utils.add_post_metrics.side_effect = add_post_metrics_tracked
        mock_utils_class.return_value = mock_utils
        
        # Setup Elasticsearch
        mock_es_client = Mock()
        mock_es_client.is_connected.return_value = False
        mock_es_class.return_value = mock_es_client
        
        with patch('pathlib.Path.mkdir'), \
             patch('builtins.open', mock_open()), \
             patch('json.dump'):
            
            main.main()
        
        # Verify data flow through all stages
        expected_stages = ['location_processed', 'person_processed', 'comment_metrics_added', 'post_metrics_added']
        actual_stages = [call[0] for call in transformation_calls]
        
        for stage in expected_stages:
            assert stage in actual_stages, f"Stage {stage} not found in transformation flow"
        
        # Verify data count consistency (1 post, 1 comment)
        for stage, count in transformation_calls:
            if 'post' in stage or 'location' in stage or 'person' in stage or 'comment_metrics' in stage:
                assert count == 1, f"Expected 1 post in {stage}, got {count}"
            elif 'post_metrics' in stage:
                assert count == 1, f"Expected 1 comment in {stage}, got {count}"
    
    @patch('main.ElasticsearchClient')
    @patch('main.Utils')
    @patch('main.WikipediaPersonProcessor')
    @patch('main.LocationProcessor')
    @patch('main.RedditDataEnricher')
    @patch('main.RedditDataCollector')
    @patch('main.load_dotenv')
    def test_main_pipeline_exception_handling(self, mock_load_dotenv, mock_reddit_class,
                                            mock_enricher_class, mock_location_class,
                                            mock_person_class, mock_utils_class,
                                            mock_es_class, mock_env_vars):
        """Test pipeline behavior when components raise exceptions."""
        
        # Setup Reddit collector to raise exception
        mock_reddit_collector = Mock()
        mock_reddit_collector.collect_posts.side_effect = Exception("Reddit API Error")
        mock_reddit_class.return_value = mock_reddit_collector
        
        # Setup other mocks (won't be reached due to exception)
        mock_enricher_class.return_value = Mock()
        mock_location_class.return_value = Mock()
        mock_person_class.return_value = Mock()
        mock_utils_class.return_value = Mock()
        mock_es_client = Mock()
        mock_es_client.is_connected.return_value = False
        mock_es_class.return_value = mock_es_client
        
        # Pipeline should propagate the exception
        with pytest.raises(Exception, match="Reddit API Error"):
            with patch('pathlib.Path.mkdir'):
                main.main()
    
    @patch('main.ElasticsearchClient')
    @patch('main.Utils')
    @patch('main.WikipediaPersonProcessor')
    @patch('main.LocationProcessor')
    @patch('main.RedditDataEnricher')
    @patch('main.RedditDataCollector')
    @patch('main.load_dotenv')
    def test_main_pipeline_directory_creation(self, mock_load_dotenv, mock_reddit_class,
                                            mock_enricher_class, mock_location_class,
                                            mock_person_class, mock_utils_class,
                                            mock_es_class, mock_env_vars, sample_reddit_data):
        """Test that pipeline creates necessary directories."""
        posts, comments = sample_reddit_data
        
        # Setup working mocks
        mock_reddit_collector = Mock()
        mock_reddit_collector.collect_posts.return_value = (posts, ['test_post_1'])
        mock_reddit_collector.collect_comments.return_value = comments
        mock_reddit_class.return_value = mock_reddit_collector
        
        mock_enricher = Mock()
        mock_enricher.enrich_post.side_effect = lambda x: x
        mock_enricher.enrich_comment.side_effect = lambda x: x
        mock_enricher_class.return_value = mock_enricher
        
        mock_location_processor = Mock()
        mock_location_processor.process_posts.side_effect = lambda x: x
        mock_location_class.return_value = mock_location_processor
        
        mock_person_processor = Mock()
        mock_person_processor.update_persons_mentioned.side_effect = lambda x: x
        mock_person_class.return_value = mock_person_processor
        
        mock_utils = Mock()
        mock_utils.add_comment_metrics.side_effect = lambda posts, comments: posts
        mock_utils.add_post_metrics.side_effect = lambda posts, comments: comments
        mock_utils_class.return_value = mock_utils
        
        mock_es_client = Mock()
        mock_es_client.is_connected.return_value = False
        mock_es_client.create_indices.return_value = ('posts_index', 'comments_index')
        mock_es_client.load_from_file.return_value = None
        mock_es_class.return_value = mock_es_client
        
        with patch('pathlib.Path.mkdir') as mock_mkdir, \
             patch('builtins.open', mock_open()), \
             patch('json.dump'):
            
            main.main()
        
        # Verify directories were created
        # Should create: data, data/posts, data/comments
        assert mock_mkdir.call_count >= 3
        
        # Check that exist_ok=True was used for main data dir
        mkdir_calls = mock_mkdir.call_args_list
        assert any(call.kwargs.get('exist_ok') is True for call in mkdir_calls)
        
        # Check that parents=True was used for subdirectories
        assert any(call.kwargs.get('parents') is True for call in mkdir_calls)

    @patch('main.ElasticsearchClient')
    @patch('main.Utils')
    @patch('main.WikipediaPersonProcessor')
    @patch('main.LocationProcessor')
    @patch('main.RedditDataEnricher')
    @patch('main.RedditDataCollector')
    @patch('main.load_dotenv')
    def test_main_pipeline_comments_only_when_posts_exist(self, mock_load_dotenv, mock_reddit_class,
                                                        mock_enricher_class, mock_location_class,
                                                        mock_person_class, mock_utils_class,
                                                        mock_es_class, mock_env_vars, sample_reddit_data):
        """Test that comments are only collected when posts exist."""
        posts, comments = sample_reddit_data
        
        # Setup Reddit collector
        mock_reddit_collector = Mock()
        mock_reddit_collector.collect_posts.return_value = (posts, ['test_post_1'])
        mock_reddit_collector.collect_comments.return_value = comments
        mock_reddit_class.return_value = mock_reddit_collector
        
        # Setup other components
        mock_enricher = Mock()
        mock_enricher.enrich_post.side_effect = lambda x: x
        mock_enricher.enrich_comment.side_effect = lambda x: x
        mock_enricher_class.return_value = mock_enricher
        
        mock_location_processor = Mock()
        mock_location_processor.process_posts.side_effect = lambda x: x
        mock_location_class.return_value = mock_location_processor
        
        mock_person_processor = Mock()
        mock_person_processor.update_persons_mentioned.side_effect = lambda x: x
        mock_person_class.return_value = mock_person_processor
        
        mock_utils = Mock()
        mock_utils.add_comment_metrics.side_effect = lambda posts, comments: posts
        mock_utils.add_post_metrics.side_effect = lambda posts, comments: comments
        mock_utils_class.return_value = mock_utils
        
        mock_es_client = Mock()
        mock_es_client.is_connected.return_value = False
        mock_es_class.return_value = mock_es_client
        
        with patch('pathlib.Path.mkdir'), \
             patch('builtins.open', mock_open()), \
             patch('json.dump'):
            
            main.main()
        
        # Verify posts collection was called
        mock_reddit_collector.collect_posts.assert_called_once_with('worldnews')
        
        # Verify comments collection was called since we have post_ids
        mock_reddit_collector.collect_comments.assert_called_once_with(['test_post_1'])
        
        # Verify comment enrichment was called
        assert mock_enricher.enrich_comment.call_count == 1

    @patch('main.ElasticsearchClient')
    @patch('main.Utils')
    @patch('main.WikipediaPersonProcessor')
    @patch('main.LocationProcessor')
    @patch('main.RedditDataEnricher')
    @patch('main.RedditDataCollector')
    @patch('main.load_dotenv')
    def test_main_pipeline_initialization_order(self, mock_load_dotenv, mock_reddit_class,
                                               mock_enricher_class, mock_location_class,
                                               mock_person_class, mock_utils_class,
                                               mock_es_class, mock_env_vars, sample_reddit_data):
        """Test that components are initialized in the correct order."""
        posts, comments = sample_reddit_data
        
        # Track initialization order
        init_order = []
        
        def track_reddit_init(*args, **kwargs):
            init_order.append('reddit')
            mock = Mock()
            mock.collect_posts.return_value = (posts, ['test_post_1'])
            mock.collect_comments.return_value = comments
            return mock
        
        def track_enricher_init(*args, **kwargs):
            init_order.append('enricher')
            mock = Mock()
            mock.enrich_post.side_effect = lambda x: x
            mock.enrich_comment.side_effect = lambda x: x
            return mock
        
        def track_location_init(*args, **kwargs):
            init_order.append('location')
            mock = Mock()
            mock.process_posts.side_effect = lambda x: x
            return mock
        
        def track_person_init(*args, **kwargs):
            init_order.append('person')
            mock = Mock()
            mock.update_persons_mentioned.side_effect = lambda x: x
            return mock
        
        def track_utils_init(*args, **kwargs):
            init_order.append('utils')
            mock = Mock()
            mock.add_comment_metrics.side_effect = lambda posts, comments: posts
            mock.add_post_metrics.side_effect = lambda posts, comments: comments
            return mock
        
        def track_es_init(*args, **kwargs):
            init_order.append('elasticsearch')
            mock = Mock()
            mock.is_connected.return_value = False
            return mock
        
        # Setup tracking mocks
        mock_reddit_class.side_effect = track_reddit_init
        mock_enricher_class.side_effect = track_enricher_init
        mock_location_class.side_effect = track_location_init
        mock_person_class.side_effect = track_person_init
        mock_utils_class.side_effect = track_utils_init
        mock_es_class.side_effect = track_es_init
        
        with patch('pathlib.Path.mkdir'), \
             patch('builtins.open', mock_open()), \
             patch('json.dump'):
            
            main.main()
        
        # Verify initialization order
        expected_order = ['reddit', 'enricher', 'location', 'person', 'utils', 'elasticsearch']
        assert init_order == expected_order, f"Expected {expected_order}, got {init_order}"
    
    @patch('main.ElasticsearchClient')
    @patch('main.Utils')
    @patch('main.WikipediaPersonProcessor')
    @patch('main.LocationProcessor')
    @patch('main.RedditDataEnricher')
    @patch('main.RedditDataCollector')
    @patch('main.load_dotenv')
    def test_main_pipeline_empty_comments_list_handling(self, mock_load_dotenv, mock_reddit_class,
                                                       mock_enricher_class, mock_location_class,
                                                       mock_person_class, mock_utils_class,
                                                       mock_es_class, mock_env_vars, sample_reddit_data):
        """Test pipeline handles empty comments list gracefully."""
        posts, _ = sample_reddit_data
        
        # Setup Reddit collector to return posts but no comments
        mock_reddit_collector = Mock()
        mock_reddit_collector.collect_posts.return_value = (posts, ['test_post_1'])
        mock_reddit_collector.collect_comments.return_value = []  # Empty comments
        mock_reddit_class.return_value = mock_reddit_collector
        
        # Setup other components
        mock_enricher = Mock()
        mock_enricher.enrich_post.side_effect = lambda x: x
        mock_enricher.enrich_comment.side_effect = lambda x: x
        mock_enricher_class.return_value = mock_enricher
        
        mock_location_processor = Mock()
        mock_location_processor.process_posts.side_effect = lambda x: x
        mock_location_class.return_value = mock_location_processor
        
        mock_person_processor = Mock()
        mock_person_processor.update_persons_mentioned.side_effect = lambda x: x
        mock_person_class.return_value = mock_person_processor
        
        mock_utils = Mock()
        mock_utils.add_comment_metrics.side_effect = lambda posts, comments: posts
        mock_utils.add_post_metrics.side_effect = lambda posts, comments: []
        mock_utils_class.return_value = mock_utils
        
        mock_es_client = Mock()
        mock_es_client.is_connected.return_value = True
        mock_es_client.create_indices.return_value = ('posts_index', 'comments_index')
        mock_es_class.return_value = mock_es_client
        
        with patch('pathlib.Path.mkdir'), \
             patch('builtins.open', mock_open()), \
             patch('json.dump') as mock_json_dump:
            
            main.main()
        
        # Verify pipeline completes successfully
        mock_reddit_collector.collect_posts.assert_called_once()
        mock_reddit_collector.collect_comments.assert_called_once()
        
        # Verify enrichment was not called for comments (empty list)
        mock_enricher.enrich_comment.assert_not_called()
        
        # Verify files are still saved (empty comments list)
        assert mock_json_dump.call_count == 2
        
        # Verify Elasticsearch operations still proceed
        mock_es_client.load_from_file.assert_called()
    
    @patch('main.ElasticsearchClient')
    @patch('main.Utils')
    @patch('main.WikipediaPersonProcessor')
    @patch('main.LocationProcessor')
    @patch('main.RedditDataEnricher')
    @patch('main.RedditDataCollector')
    @patch('main.load_dotenv')
    def test_main_pipeline_file_path_construction(self, mock_load_dotenv, mock_reddit_class,
                                                 mock_enricher_class, mock_location_class,
                                                 mock_person_class, mock_utils_class,
                                                 mock_es_class, mock_env_vars,
                                                 sample_reddit_data):
        """Test that file paths are constructed correctly."""
        posts, comments = sample_reddit_data
        
        # Setup working components
        mock_reddit_collector = Mock()
        mock_reddit_collector.collect_posts.return_value = (posts, ['test_post_1'])
        mock_reddit_collector.collect_comments.return_value = comments
        mock_reddit_class.return_value = mock_reddit_collector
        
        mock_enricher = Mock()
        mock_enricher.enrich_post.side_effect = lambda x: x
        mock_enricher.enrich_comment.side_effect = lambda x: x
        mock_enricher_class.return_value = mock_enricher
        
        mock_location_processor = Mock()
        mock_location_processor.process_posts.side_effect = lambda x: x
        mock_location_class.return_value = mock_location_processor
        
        mock_person_processor = Mock()
        mock_person_processor.update_persons_mentioned.side_effect = lambda x: x
        mock_person_class.return_value = mock_person_processor
        
        mock_utils = Mock()
        mock_utils.add_comment_metrics.side_effect = lambda posts, comments: posts
        mock_utils.add_post_metrics.side_effect = lambda posts, comments: comments
        mock_utils_class.return_value = mock_utils
        
        mock_es_client = Mock()
        mock_es_client.is_connected.return_value = False
        mock_es_class.return_value = mock_es_client
        
        # Track directory creation calls
        mkdir_calls = []
        
        def track_mkdir(*args, **kwargs):
            mkdir_calls.append((args, kwargs))
        
        with patch('pathlib.Path.mkdir', side_effect=track_mkdir), \
             patch('builtins.open', mock_open()), \
             patch('json.dump'):
            
            main.main()
        
        # Verify that mkdir was called at least 3 times (data, posts, comments dirs)
        assert len(mkdir_calls) >= 3, f"Expected at least 3 mkdir calls, got {len(mkdir_calls)}"
        
        # Verify that exist_ok=True was used
        exist_ok_calls = [call for call in mkdir_calls if call[1].get('exist_ok') is True]
        assert len(exist_ok_calls) > 0, "Expected at least one mkdir call with exist_ok=True"
        
        # Verify that parents=True was used for subdirectories
        parents_calls = [call for call in mkdir_calls if call[1].get('parents') is True]
        assert len(parents_calls) > 0, "Expected at least one mkdir call with parents=True"