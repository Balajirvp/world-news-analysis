"""
Unit tests for ElasticsearchClient class.
"""
import pytest
from unittest.mock import Mock, patch
import json
from data_collection.elasticsearch_client import ElasticsearchClient
from tests.fixtures.mock_responses import MockResponses


class TestElasticsearchClient:
    """Test suite for ElasticsearchClient."""
    
    @pytest.fixture
    def mock_es(self):
        """Create a mock Elasticsearch client."""
        with patch('elasticsearch.Elasticsearch') as mock_es_class:
            mock_es_instance = Mock()
            mock_es_class.return_value = mock_es_instance
            yield mock_es_instance
    
    @pytest.fixture
    def es_client(self, mock_es, temp_data_dir):
        """Create an ElasticsearchClient instance for testing."""
        with patch('pathlib.Path.mkdir'):
            client = ElasticsearchClient(host="localhost", port=9200, scheme="http")
            client.es = mock_es
            # Use temp directory for testing
            client.elasticsearch_dir = temp_data_dir / "elasticsearch"
            client.mappings_dir = client.elasticsearch_dir / "mappings"
            return client
    
    def test_init_default_params(self):
        """Test initialization with default parameters."""
        with patch('data_collection.elasticsearch_client.Elasticsearch') as mock_es_class:
            client = ElasticsearchClient()
            mock_es_class.assert_called_once_with([{"host": "localhost", "port": 9200, "scheme": "http"}])
    
    def test_init_custom_params(self):
        """Test initialization with custom parameters."""
        with patch('data_collection.elasticsearch_client.Elasticsearch') as mock_es_class:
            client = ElasticsearchClient(host="elasticsearch", port=9200, scheme="https")
            mock_es_class.assert_called_once_with([{"host": "elasticsearch", "port": 9200, "scheme": "https"}])
    
    def test_is_connected_success(self, es_client, mock_es):
        """Test successful connection check."""
        mock_es.ping.return_value = True
        
        result = es_client.is_connected()
        
        assert result is True
        mock_es.ping.assert_called_once()
    
    def test_is_connected_failure(self, es_client, mock_es):
        """Test failed connection check."""
        mock_es.ping.return_value = False
        
        result = es_client.is_connected()
        
        assert result is False
        mock_es.ping.assert_called_once()
    
    def test_create_indices_new_indices(self, es_client, mock_es, temp_data_dir):
        """Test creating new indices that don't exist."""
        # Setup mock responses
        mock_es.indices.exists.return_value = False
        mock_es.indices.create.return_value = {"acknowledged": True}
        
        # Create mock mapping files
        mappings_dir = temp_data_dir / "elasticsearch" / "mappings"
        mappings_dir.mkdir(parents=True, exist_ok=True)
        
        post_mapping = {"mappings": {"properties": {"post_id": {"type": "keyword"}}}}
        comment_mapping = {"mappings": {"properties": {"comment_id": {"type": "keyword"}}}}
        
        (mappings_dir / "post_mapping.json").write_text(json.dumps(post_mapping))
        (mappings_dir / "comments_mapping.json").write_text(json.dumps(comment_mapping))
        
        es_client.mappings_dir = mappings_dir
        
        # Test index creation
        posts_index, comments_index = es_client.create_indices("2025.06.18")
        
        # Assertions
        assert posts_index == "reddit_worldnews_posts_2025.06.18"
        assert comments_index == "reddit_worldnews_comments_2025.06.18"
        
        # Verify ES calls
        assert mock_es.indices.exists.call_count == 2
        assert mock_es.indices.create.call_count == 2
        
        # Check create calls
        create_calls = mock_es.indices.create.call_args_list
        assert create_calls[0][1]['index'] == posts_index
        assert create_calls[1][1]['index'] == comments_index
    
    def test_create_indices_existing_indices(self, es_client, mock_es):
        """Test handling of existing indices."""
        # Setup mock responses - indices already exist
        mock_es.indices.exists.return_value = True
        
        posts_index, comments_index = es_client.create_indices("2025.06.18")
        
        # Should return index names but not create them
        assert posts_index == "reddit_worldnews_posts_2025.06.18"
        assert comments_index == "reddit_worldnews_comments_2025.06.18"
        
        # Verify no create calls were made
        mock_es.indices.create.assert_not_called()
    
    def test_load_from_file_success(self, es_client, mock_es, temp_data_dir):
        """Test successful data loading from file."""
        # Create test data file
        test_data = [
            {"post_id": "test1", "title": "Test Post 1", "score": 100},
            {"post_id": "test2", "title": "Test Post 2", "score": 200}
        ]
        
        test_file = temp_data_dir / "test_posts.json"
        test_file.write_text(json.dumps(test_data))
        
        # Setup mock ES response
        mock_es.bulk.return_value = MockResponses.get_elasticsearch_bulk_response()
        
        # Test loading
        es_client.load_from_file(test_file, "test_index", "post_id")
        
        # Verify bulk call was made
        mock_es.bulk.assert_called_once()
        
        # Check bulk data structure
        call_args = mock_es.bulk.call_args
        bulk_data = call_args[1]['body']
        
        # Should have index commands and data alternating
        assert len(bulk_data) == 4  # 2 items * 2 (index command + data)
        
        # Check first item structure
        assert bulk_data[0] == {"index": {"_index": "test_index", "_id": "test1"}}
        assert "collection_date" in bulk_data[1]  # Should add collection_date
        assert bulk_data[1]["post_id"] == "test1"
    
    def test_load_from_file_not_found(self, es_client, mock_es, temp_data_dir):
        """Test handling of non-existent file."""
        non_existent_file = temp_data_dir / "does_not_exist.json"
        
        # Should not raise exception, just print message
        es_client.load_from_file(non_existent_file, "test_index", "post_id")
        
        # Should not call bulk
        mock_es.bulk.assert_not_called()
    
    def test_load_from_file_empty_data(self, es_client, mock_es, temp_data_dir):
        """Test loading empty data file."""
        test_file = temp_data_dir / "empty.json"
        test_file.write_text("[]")
        
        es_client.load_from_file(test_file, "test_index", "post_id")
        
        # Should not call bulk for empty data
        mock_es.bulk.assert_not_called()
    
    def test_load_from_file_invalid_json(self, es_client, mock_es, temp_data_dir):
        """Test handling of invalid JSON file."""
        test_file = temp_data_dir / "invalid.json"
        test_file.write_text("invalid json content")
        
        # Should raise JSON decode error
        with pytest.raises(json.JSONDecodeError):
            es_client.load_from_file(test_file, "test_index", "post_id")
    
    def test_load_from_file_adds_collection_date(self, es_client, mock_es, temp_data_dir):
        """Test that collection_date is added to all items."""
        test_data = [{"post_id": "test1", "title": "Test"}]
        test_file = temp_data_dir / "test.json"
        test_file.write_text(json.dumps(test_data))
        
        mock_es.bulk.return_value = {"errors": False}
        
        es_client.load_from_file(test_file, "test_index", "post_id")
        
        # Check that collection_date was added
        call_args = mock_es.bulk.call_args
        bulk_data = call_args[1]['body']
        
        data_item = bulk_data[1]  # Second item is the actual data
        assert "collection_date" in data_item
        
        # Should be ISO format datetime string
        from datetime import datetime
        collection_date = data_item["collection_date"]
        # Should not raise exception when parsing
        datetime.fromisoformat(collection_date)
    
    def test_bulk_index_error_handling(self, es_client, mock_es, temp_data_dir):
        """Test handling of Elasticsearch bulk errors."""
        test_data = [{"post_id": "test1", "title": "Test"}]
        test_file = temp_data_dir / "test.json"
        test_file.write_text(json.dumps(test_data))
        
        # Mock bulk to raise exception
        mock_es.bulk.side_effect = Exception("Elasticsearch error")
        
        # Should raise the exception
        with pytest.raises(Exception, match="Elasticsearch error"):
            es_client.load_from_file(test_file, "test_index", "post_id")
    
    def test_mapping_file_not_found(self, es_client, mock_es):
        """Test handling when mapping files don't exist."""
        mock_es.indices.exists.return_value = False
        
        # Should raise FileNotFoundError when mapping file is missing
        with pytest.raises(FileNotFoundError):
            es_client.create_indices("2025.06.18")
    
    def test_create_indices_with_mixed_existence(self, es_client, mock_es, temp_data_dir):
        """Test when one index exists but the other doesn't."""
        # Setup mapping files
        mappings_dir = temp_data_dir / "elasticsearch" / "mappings"
        mappings_dir.mkdir(parents=True, exist_ok=True)
        
        post_mapping = {"mappings": {"properties": {"post_id": {"type": "keyword"}}}}
        comment_mapping = {"mappings": {"properties": {"comment_id": {"type": "keyword"}}}}
        
        (mappings_dir / "post_mapping.json").write_text(json.dumps(post_mapping))
        (mappings_dir / "comments_mapping.json").write_text(json.dumps(comment_mapping))
        
        es_client.mappings_dir = mappings_dir
        
        # Mock posts index exists, comments index doesn't
        def exists_side_effect(index):
            return "posts" in index
        
        mock_es.indices.exists.side_effect = exists_side_effect
        mock_es.indices.create.return_value = {"acknowledged": True}
        
        posts_index, comments_index = es_client.create_indices("2025.06.18")
        
        # Should create only the comments index
        mock_es.indices.create.assert_called_once()
        create_call = mock_es.indices.create.call_args
        assert create_call[1]['index'] == comments_index
    
    def test_elasticsearch_connection_params(self):
        """Test various Elasticsearch connection parameter combinations."""
        test_cases = [
            ("localhost", 9200, "http"),
            ("elasticsearch", 9200, "https"),
            ("127.0.0.1", 9300, "http"),
        ]
        
        for host, port, scheme in test_cases:
            with patch('data_collection.elasticsearch_client.Elasticsearch') as mock_es_class:
                client = ElasticsearchClient(host=host, port=port, scheme=scheme)
                expected_config = [{"host": host, "port": port, "scheme": scheme}]
                mock_es_class.assert_called_once_with(expected_config)
    
    def test_bulk_data_structure_correctness(self, es_client, mock_es, temp_data_dir):
        """Test that bulk data is structured correctly for Elasticsearch."""
        test_data = [
            {"id": "1", "title": "First", "score": 10},
            {"id": "2", "title": "Second", "score": 20}
        ]
        
        test_file = temp_data_dir / "test.json"
        test_file.write_text(json.dumps(test_data))
        
        mock_es.bulk.return_value = {"errors": False}
        
        es_client.load_from_file(test_file, "test_index", "id")
        
        # Get the bulk data
        call_args = mock_es.bulk.call_args
        bulk_data = call_args[1]['body']
        
        # Should be: [index_cmd1, data1, index_cmd2, data2]
        assert len(bulk_data) == 4
        
        # Check structure of first item
        assert bulk_data[0] == {"index": {"_index": "test_index", "_id": "1"}}
        assert bulk_data[1]["id"] == "1"
        assert bulk_data[1]["title"] == "First"
        assert "collection_date" in bulk_data[1]
        
        # Check structure of second item
        assert bulk_data[2] == {"index": {"_index": "test_index", "_id": "2"}}
        assert bulk_data[3]["id"] == "2"
        assert bulk_data[3]["title"] == "Second"
        assert "collection_date" in bulk_data[3]
